"""Interfaccia web locale (solo libreria standard): python -m cwm interfaccia --porta 8765."""
from __future__ import annotations

import json
import sys
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import analysis
from . import education as edu
from .audit import FORMATO_HASH_ESITI, Registro, hash_esiti, piano, pulisci, sha256

UI = Path(__file__).resolve().parent / "ui.html"


class Applicazione:
    def __init__(self, config: str, audit: str):
        self.config = config
        self.registro = Registro(audit)
        self._bench = None
        self._lock = threading.Lock()
        self._lock_bench = threading.Lock()

    def pacchetto(self) -> dict:
        return analysis.carica_pacchetto(self.config)

    def base(self) -> dict:
        pac = self.pacchetto()
        pesi, elic = analysis.pesi_da_pacchetto(pac)
        return {"criteri": list(edu.CRITERI), "pesi_gruppo": pesi, "obiettivo_predefinito": pac["analisi"]["obiettivo"],
                "obiettivi": {k: v.get("descrizione", "") for k, v in pac["requisiti"]["obiettivi"].items()},
                "vincoli": pac["vincoli"]["vincoli"],
                "elicitazione": None if not elic else {"accettati": elic["partecipanti_accettati"], "esclusi": elic["partecipanti_esclusi"],
                                                       "dispersione": elic["dispersione"], "cr_gruppo": elic["cr_gruppo"]}}

    def analizza(self, corpo: object) -> dict:
        if not isinstance(corpo, dict):
            raise ValueError("il corpo della richiesta deve essere un oggetto JSON")
        pac = self.pacchetto()
        pesi = corpo.get("pesi")
        obiettivo = corpo.get("obiettivo")
        if obiettivo is not None and not isinstance(obiettivo, str):
            raise ValueError("'obiettivo' deve essere una stringa")
        if obiettivo is not None and obiettivo not in pac["requisiti"]["obiettivi"]:
            raise ValueError(f"obiettivo sconosciuto: {obiettivo!r}")
        for chiave in ("stabilita", "registra"):
            if not isinstance(corpo.get(chiave, False), bool):
                raise ValueError(f"'{chiave}' deve essere true o false")
        if pesi is not None:
            pesi = analysis.normalizza_pesi(pesi)
        opzioni = analysis.opzioni_esecuzione(obiettivo, pesi, con_studi=False, con_stabilita=corpo.get("stabilita", False))
        ris = analysis.riesegui(pac, opzioni)
        controlli = self.registro.controlli_uso(pac, ris, uso_richiesto=ris["obiettivo"])
        if corpo.get("registra"):
            with self._lock:
                v = self.registro.aggiungi("ANALISI", {"hash_piano": sha256(piano(pac)), "input": pac, "opzioni": opzioni,
                                                       "hash_esiti": hash_esiti(ris), "formato_hash_esiti": FORMATO_HASH_ESITI,
                                                       "sintesi": ris["sintesi"], "controlli": controlli})
            ris["voce_audit"] = {"seq": v["seq"], "hash": v["hash"]}
        return {**ris, "controlli_uso": controlli}

    def audit(self) -> dict:
        voci = self.registro.voci()
        return {"catena": self.registro.verifica_catena(), "preregistrazione": self.registro.deviazioni(self.pacchetto()),
                "ultime": [{"seq": v["seq"], "tipo": v["tipo"], "istante": v["istante"], "hash": v["hash"][:16]} for v in voci[-12:]][::-1]}

    def benchmark(self) -> dict:
        with self._lock_bench:
            if self._bench is None:
                from . import benchmark
                self._bench = benchmark.esegui(campioni_smaa=200, direzioni=12, quanti_fedelta=30)
        return self._bench


MAX_CORPO = 64 * 1024


class RichiestaNonValida(Exception):
    def __init__(self, stato: int, messaggio: str):
        super().__init__(messaggio)
        self.stato = stato


def _gestore(app: Applicazione):
    class Gestore(BaseHTTPRequestHandler):
        timeout = 30  # secondi per richiesta: una connessione lenta non tiene occupato un thread per sempre

        def log_message(self, *a):  # silenzioso
            pass

        def _invia(self, corpo: bytes, tipo: str, stato: int = 200):
            self.send_response(stato)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(corpo)

        def _json(self, dati, stato=200):
            self._invia(json.dumps(pulisci(dati), ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", stato)

        def _origini_ammesse(self) -> set[str]:
            porta = self.server.server_address[1]
            return {f"127.0.0.1:{porta}", f"localhost:{porta}"}

        def _controlla_host(self):
            # Contro il DNS rebinding: un dominio esterno che si risolve a 127.0.0.1 arriva con un Host diverso.
            if self.headers.get("Host", "") not in self._origini_ammesse():
                raise RichiestaNonValida(403, "host non ammesso")

        def _controlla_origine(self):
            # Contro il CSRF: i browser inviano Origin nei POST cross-site; deve essere l'interfaccia stessa.
            origine = self.headers.get("Origin")
            if origine is not None and origine.removeprefix("http://") not in self._origini_ammesse():
                raise RichiestaNonValida(403, "origine non ammessa")
            tipo = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if tipo != "application/json":
                raise RichiestaNonValida(415, "serve Content-Type: application/json")

        def _leggi_corpo(self) -> object:
            try:
                n = int(self.headers.get("Content-Length", ""))
            except ValueError:
                raise RichiestaNonValida(411, "Content-Length mancante o non valido") from None
            if n < 0:
                raise RichiestaNonValida(400, "Content-Length non valido")
            if n > MAX_CORPO:
                raise RichiestaNonValida(413, f"corpo troppo grande (massimo {MAX_CORPO} byte)")
            try:
                return json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                raise RichiestaNonValida(400, f"JSON non valido: {e}") from None

        def _gestisci(self, azione):
            try:
                azione()
            except RichiestaNonValida as e:
                self._json({"errore": str(e)}, e.stato)
            except ValueError as e:  # input dell'utente non valido (pesi, obiettivo, ...)
                self._json({"errore": str(e)}, 400)
            except Exception:  # noqa: BLE001
                traceback.print_exc(file=sys.stderr)
                self._json({"errore": "errore interno: dettagli nel terminale del server"}, 500)

        def do_GET(self):  # noqa: N802
            def azione():
                self._controlla_host()
                if self.path in ("/", "/index.html"):
                    self._invia(UI.read_bytes(), "text/html; charset=utf-8")
                elif self.path == "/api/base":
                    self._json(app.base())
                elif self.path == "/api/audit":
                    self._json(app.audit())
                elif self.path == "/api/benchmark":
                    self._json(app.benchmark())
                else:
                    self._json({"errore": "non trovato"}, 404)
            self._gestisci(azione)

        def do_POST(self):  # noqa: N802
            def azione():
                self._controlla_host()
                self._controlla_origine()
                if self.path != "/api/analizza":
                    raise RichiestaNonValida(404, "non trovato")
                self._json(app.analizza(self._leggi_corpo()))
            self._gestisci(azione)

    return Gestore


def crea_server(porta: int, config: str, audit: str) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", porta), _gestore(Applicazione(config, audit)))


def avvia(porta: int, config: str, audit: str, apri_browser: bool = True) -> None:
    srv = crea_server(porta, config, audit)
    url = f"http://127.0.0.1:{porta}/"
    print(f"CWM 1.2 — interfaccia su {url} (Ctrl+C per uscire)")
    if apri_browser:
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
