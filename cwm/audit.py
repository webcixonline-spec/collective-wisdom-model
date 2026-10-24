"""Audit, preregistrazione e controlli contro l'uso improprio (dalla 1.2).

- Registro a catena (append-only, JSON Lines): ogni voce contiene l'hash della precedente ed è
  firmata con HMAC-SHA256. Modificare o cancellare una voce rompe la catena.
- Preregistrazione: congela l'hash del piano di analisi PRIMA dei risultati; ogni analisi
  successiva viene confrontata con il piano e le deviazioni sono elencate.
- Riproducibilità: ogni analisi salva gli input completi; `verifica` la riesegue e confronta l'hash
  degli esiti (arrotondati a 9 cifre significative per neutralizzare differenze di libm tra macchine).
- Uso improprio: blocca l'esportazione di una raccomandazione oltre l'ambito consentito dal
  cancello delle prove, segnala pesi cambiati dopo la preregistrazione e conta i "sentieri che si
  biforcano" (analisi ripetute con configurazioni diverse).

- Scrittura sicura: lock esclusivo su file (anche tra CLI e server), fsync di ogni voce, lettura rigorosa
  (riga incompleta, chiavi ripetute o NaN rendono il registro "compromesso" invece di essere interpretati).
- Checkpoint esterno: `python -m cwm checkpoint` attesta numero di voci e hash dell'ultima; conservato
  altrove, `verifica --checkpoint` rileva troncamenti e riscritture della storia attestata.

Limite dichiarato: l'HMAC dimostra l'integrità a chi possiede la chiave, e chi ha la chiave può
riscrivere tutta la catena. Solo un checkpoint conservato fuori dalla cartella del registro (verbale,
repository pubblico, email a terzi) lo rende rilevabile.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import json
import math
import os
import secrets
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
try:
    import msvcrt
except ImportError:  # POSIX
    msvcrt = None

PACCHETTO = Path(__file__).resolve().parent
BASE = PACCHETTO.parent
GENESI = "0" * 64
FORMATO_CHECKPOINT = "cwm.checkpoint/1.2"

# Sezioni del piano che, se cambiate dopo la preregistrazione, bloccano l'uso: soglie di prova,
# diritti e preferenze decidono l'esito. Per "analisi" bloccano solo le chiavi elencate; le altre
# (semi, numero di scenari, ...) producono un avviso e vengono contate tra i sentieri che si biforcano.
SEZIONI_BLOCCANTI = frozenset({"requisiti", "vincoli", "partecipanti"})
CHIAVI_ANALISI_BLOCCANTI = frozenset({"pesi", "obiettivo", "regola_di_scelta", "validazione"})


def deviazione_bloccante(sezione: str, chiavi: list[str] | None) -> bool:
    if sezione in SEZIONI_BLOCCANTI:
        return True
    if sezione == "analisi":
        return chiavi is None or bool(CHIAVI_ANALISI_BLOCCANTI & set(chiavi))
    return False


class RegistroCorrotto(ValueError):
    """Il file del registro non si può leggere in modo univoco: nessuna voce viene aggiunta."""


def _chiavi_testuali(obj: dict, percorso: str) -> dict:
    out = {}
    for k, v in obj.items():
        s = str(k)
        if s in out:
            raise ValueError(f"chiavi che collidono dopo la conversione in testo in {percorso}: {s!r}")
        out[s] = v
    return out


def pulisci(obj, _percorso: str = "$"):
    """Rende un oggetto serializzabile in JSON standard per file e interfaccia.

    ±inf diventa None: nei risultati significa "mai" (es. uno studio mai conveniente, nessun peso che
    cambia la scelta). NaN invece segnala un calcolo rotto e non deve sparire in silenzio: è un errore.
    """
    if isinstance(obj, float):
        if math.isnan(obj):
            raise ValueError(f"valore NaN in {_percorso}")
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: pulisci(v, f"{_percorso}.{k}") for k, v in _chiavi_testuali(obj, _percorso).items()}
    if isinstance(obj, (list, tuple)):
        return [pulisci(v, f"{_percorso}[{i}]") for i, v in enumerate(obj)]
    return obj


def _controlla_json(obj, percorso: str = "$") -> None:
    if obj is None or type(obj) in (str, bool, int):
        return
    if type(obj) is float:
        if not math.isfinite(obj):
            raise ValueError(f"numero non finito in {percorso}: usare pulisci() o una rappresentazione esplicita")
        return
    if type(obj) in (list, tuple):
        for i, v in enumerate(obj):
            _controlla_json(v, f"{percorso}[{i}]")
        return
    if type(obj) is dict:
        for k, v in obj.items():
            if type(k) is not str:
                raise ValueError(f"chiave non testuale in {percorso}: {k!r}")
            _controlla_json(v, f"{percorso}.{k}")
        return
    raise ValueError(f"tipo non serializzabile in {percorso}: {type(obj).__name__}")


def canonico(obj) -> bytes:
    """JSON canonico per gli hash: chiavi ordinate, nessuno spazio, UTF-8. Rifiuta ciò che è ambiguo
    (NaN, inf, chiavi non testuali) invece di convertirlo: due oggetti diversi non devono avere lo stesso hash."""
    _controlla_json(obj)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256(obj) -> str:
    return hashlib.sha256(canonico(obj)).hexdigest()


def _rifiuta_doppie(coppie: list[tuple[str, object]]) -> dict:
    out = {}
    for k, v in coppie:
        if k in out:
            raise ValueError(f"chiave JSON ripetuta: {k!r}")
        out[k] = v
    return out


def _rifiuta_costante(nome: str):
    raise ValueError(f"numero JSON non valido: {nome}")


def carica_json_rigoroso(testo: str | bytes):
    """Lettura senza ambiguità: niente chiavi ripetute (vincerebbe l'ultima), niente NaN/Infinity."""
    try:
        return json.loads(testo, object_pairs_hook=_rifiuta_doppie, parse_constant=_rifiuta_costante)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ValueError(f"JSON non valido: {e}") from None


# Formato 1 (fino alla 1.2.0): ±inf e NaN diventavano tutti null. Formato 2: ±inf restano distinguibili,
# NaN è un errore. Le voci salvano il formato con cui è stato calcolato l'hash, così le vecchie restano verificabili.
FORMATO_HASH_ESITI = 2


def _arrotonda_v1(obj):
    if isinstance(obj, float):
        return float(f"{obj:.9g}") if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {str(k): _arrotonda_v1(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_arrotonda_v1(v) for v in obj]
    return obj


def _arrotonda_v2(obj, percorso: str = "$"):
    if isinstance(obj, float):
        if math.isnan(obj):
            raise ValueError(f"valore NaN negli esiti in {percorso}")
        if math.isinf(obj):
            return "+inf" if obj > 0 else "-inf"
        return float(f"{obj:.9g}")
    if isinstance(obj, dict):
        return {k: _arrotonda_v2(v, f"{percorso}.{k}") for k, v in _chiavi_testuali(obj, percorso).items()}
    if isinstance(obj, (list, tuple)):
        return [_arrotonda_v2(v, f"{percorso}[{i}]") for i, v in enumerate(obj)]
    return obj


def hash_esiti(risultato: dict, formato: int = FORMATO_HASH_ESITI) -> str:
    if formato == 1:
        return sha256(_arrotonda_v1(risultato))
    if formato == 2:
        return sha256(_arrotonda_v2(risultato))
    raise ValueError(f"formato dell'hash degli esiti sconosciuto: {formato}")


def impronta_codice() -> str:
    h = hashlib.sha256()
    for f in sorted(PACCHETTO.glob("*.py")):
        h.update(f.name.encode())
        h.update(f.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def piano(pacchetto: dict) -> dict:
    """Il piano di analisi preregistrabile: tutto tranne il registro delle prove (che può aggiornarsi)."""
    return {k: pacchetto[k] for k in ("analisi", "requisiti", "vincoli", "partecipanti") if k in pacchetto}


class Registro:
    def __init__(self, cartella: Path | str | None = None):
        self.cartella = Path(cartella) if cartella else BASE / "registro_audit"
        self.cartella.mkdir(parents=True, exist_ok=True)
        self.file = self.cartella / "ledger.jsonl"

    # --- chiave ------------------------------------------------------------------
    def _chiave(self) -> bytes:
        env = os.environ.get("CWM_CHIAVE_AUDIT")
        if env:
            return env.encode()
        f = self.cartella / ".chiave"
        if not f.exists():
            f.write_text(secrets.token_hex(32), encoding="utf-8")
            try:
                os.chmod(f, 0o600)
            except OSError:
                pass
        return f.read_text(encoding="utf-8").strip().encode()

    # --- lettura/scrittura --------------------------------------------------------
    @contextmanager
    def _bloccato(self):
        """Lock esclusivo su file: serializza scrittori e lettori anche tra processi diversi (CLI e server).
        Non è rientrante: i metodi pubblici lo prendono una volta sola e usano _leggi() all'interno."""
        with (self.cartella / ".registro.lock").open("a+b") as f:
            if fcntl is not None:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            elif msvcrt is not None:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:  # pragma: no cover - nessuna piattaforma nota senza uno dei due
                raise RuntimeError("lock su file non disponibile su questa piattaforma: il registro non è protetto")

    def _leggi(self) -> list[dict]:
        if not self.file.exists():
            return []
        grezzo = self.file.read_bytes()
        if grezzo and not grezzo.endswith(b"\n"):
            raise RegistroCorrotto("l'ultima voce del registro è incompleta (scrittura interrotta?): nessuna riparazione automatica")
        voci = []
        for n, riga in enumerate(grezzo.split(b"\n")[:-1], 1):
            try:
                v = carica_json_rigoroso(riga.decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as e:
                raise RegistroCorrotto(f"riga {n} del registro illeggibile: {e}") from None
            if not isinstance(v, dict):
                raise RegistroCorrotto(f"riga {n} del registro non è un oggetto JSON")
            voci.append(v)
        return voci

    def voci(self) -> list[dict]:
        with self._bloccato():
            return self._leggi()

    def aggiungi(self, tipo: str, contenuto: dict) -> dict:
        with self._bloccato():
            voci = self._leggi()
            prec = voci[-1]["hash"] if voci else GENESI
            voce = {"seq": len(voci) + 1, "tipo": tipo,
                    "istante": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
                    "codice": impronta_codice(), "contenuto": pulisci(contenuto), "hash_precedente": prec}
            voce["hash"] = sha256(voce)
            voce["firma"] = hmac.new(self._chiave(), voce["hash"].encode(), hashlib.sha256).hexdigest()
            riga = json.dumps(voce, ensure_ascii=False, allow_nan=False) + "\n"  # ordine delle chiavi preservato
            with self.file.open("a", encoding="utf-8") as f:
                f.write(riga)
                f.flush()
                os.fsync(f.fileno())  # la voce è su disco prima di restituirla come registrata
        return voce

    # --- checkpoint esterno -------------------------------------------------------
    def checkpoint(self) -> dict:
        """Attesta numero di voci e hash dell'ultima. Va conservato FUORI dal registro (verbale, repository
        pubblico, email a terzi): solo così si rilevano troncamenti e riscritture fatte da chi ha la chiave."""
        cat = self.verifica_catena()
        if not cat["integro"]:
            raise ValueError("catena non integra: nessun checkpoint su una storia compromessa")
        if cat["voci"] == 0:
            raise ValueError("registro vuoto: niente da attestare")
        return {"formato": FORMATO_CHECKPOINT, "voci": cat["voci"], "ultimo_hash": cat["ultimo_hash"],
                "istante": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")}

    @staticmethod
    def valida_checkpoint(cp: object) -> dict:
        if not isinstance(cp, dict) or cp.get("formato") != FORMATO_CHECKPOINT:
            raise ValueError(f"checkpoint non valido: serve formato {FORMATO_CHECKPOINT}")
        n, h = cp.get("voci"), cp.get("ultimo_hash")
        if type(n) is not int or n < 1:
            raise ValueError("checkpoint non valido: 'voci' deve essere un intero >= 1")
        if not isinstance(h, str) or len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
            raise ValueError("checkpoint non valido: 'ultimo_hash' deve essere un SHA-256 esadecimale")
        return cp

    def verifica_catena(self, checkpoint: dict | None = None) -> dict:
        if checkpoint is not None:
            self.valida_checkpoint(checkpoint)
        try:
            voci = self.voci()
        except RegistroCorrotto as e:
            return {"integro": False, "voci": 0, "errori": [str(e)], "ultimo_hash": None, "checkpoint": None}
        errori = []
        prec = GENESI
        for i, v in enumerate(voci, 1):
            corpo = {k: v[k] for k in v if k not in ("hash", "firma")}
            if v.get("seq") != i:
                errori.append(f"voce {i}: numero di sequenza {v.get('seq')} inatteso")
            if v.get("hash_precedente") != prec:
                errori.append(f"voce {i}: catena interrotta (hash precedente non corrisponde)")
            if sha256(corpo) != v.get("hash"):
                errori.append(f"voce {i}: contenuto modificato (hash non corrisponde)")
            atteso = hmac.new(self._chiave(), str(v.get("hash")).encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(atteso, str(v.get("firma"))):
                errori.append(f"voce {i}: firma non valida")
            prec = v.get("hash")
        esito_cp = None
        if checkpoint is not None:
            m = checkpoint["voci"]
            if len(voci) < m:
                errori.append(f"registro troncato: {len(voci)} voci, il checkpoint del {checkpoint.get('istante')} ne attesta {m}")
            elif voci[m - 1].get("hash") != checkpoint["ultimo_hash"]:
                errori.append(f"storia riscritta: la voce {m} non ha l'hash attestato dal checkpoint del {checkpoint.get('istante')}")
            else:
                esito_cp = {"voci_attestate": m, "voci_successive": len(voci) - m}
        return {"integro": not errori, "voci": len(voci), "errori": errori, "ultimo_hash": prec, "checkpoint": esito_cp}

    # --- preregistrazione -----------------------------------------------------------
    def preregistra(self, pacchetto: dict) -> dict:
        p = piano(pacchetto)
        return self.aggiungi("PREREGISTRAZIONE", {"hash_piano": sha256(p), "piano": p})

    def ultima(self, tipo: str) -> dict | None:
        for v in reversed(self.voci()):
            if v["tipo"] == tipo:
                return v
        return None

    def deviazioni(self, pacchetto: dict) -> dict:
        pre = self.ultima("PREREGISTRAZIONE")
        if pre is None:
            return {"preregistrato": False, "deviazioni": ["nessuna preregistrazione: l'analisi è esplorativa"], "dettaglio": []}
        attuale = piano(pacchetto)
        congelato = pre["contenuto"]["piano"]
        dev, dettaglio = [], []
        for sezione in sorted(set(attuale) | set(congelato)):
            a, c = attuale.get(sezione), congelato.get(sezione)
            if sha256(a) != sha256(c):
                if isinstance(a, dict) and isinstance(c, dict):
                    chiavi = sorted(k for k in set(a) | set(c) if sha256(a.get(k)) != sha256(c.get(k)))
                    dev.append(f"{sezione}: modificati {', '.join(chiavi)}")
                else:
                    chiavi = None
                    dev.append(f"{sezione}: modificata")
                dettaglio.append({"sezione": sezione, "chiavi": chiavi, "bloccante": deviazione_bloccante(sezione, chiavi)})
        return {"preregistrato": True, "seq_preregistrazione": pre["seq"], "istante": pre["istante"],
                "hash_piano": pre["contenuto"]["hash_piano"], "deviazioni": dev, "dettaglio": dettaglio}

    # --- controlli d'uso ----------------------------------------------------------
    def controlli_uso(self, pacchetto: dict, risultato: dict, uso_richiesto: str | None = None) -> dict:
        avvisi, blocchi = [], []
        dev = self.deviazioni(pacchetto)
        if dev["preregistrato"]:
            for testo, d in zip(dev["deviazioni"], dev["dettaglio"]):
                (blocchi if d["bloccante"] else avvisi).append("deviazione dal piano preregistrato — " + testo)
        else:
            avvisi.append("analisi non preregistrata: trattarla come esplorativa")
        if risultato.get("fonte_pesi") == "forniti_dall_utente":
            if dev["preregistrato"]:
                blocchi.append("pesi inseriti a mano dopo la preregistrazione: sostituiscono quelli dell'elicitazione congelata")
            else:
                avvisi.append("pesi inseriti a mano invece che dall'elicitazione: dichiararlo nel rapporto")
        if risultato.get("fonte_pesi") == "elicitazione":
            from .elicitazione import valida_partecipanti
            problemi = valida_partecipanti(pacchetto.get("partecipanti"), risultato["criteri"])
            if problemi:
                testo = "preferenze non utilizzabili per una raccomandazione — " + "; ".join(problemi)
                (blocchi if uso_richiesto else avvisi).append(testo)
        # sentieri che si biforcano
        dopo = dev.get("seq_preregistrazione", 0)
        configurazioni = {v["contenuto"].get("hash_piano") for v in self.voci()
                          if v["tipo"] == "ANALISI" and v["seq"] > dopo}
        if len(configurazioni) > 1:
            avvisi.append(f"{len(configurazioni)} configurazioni diverse analizzate dopo la preregistrazione: riportarle tutte")
        gate = risultato["cancello_prove"]
        if uso_richiesto:
            from .evidence import cancello
            verdetto_uso = cancello(pacchetto["registro"], pacchetto["requisiti"], uso_richiesto,
                                    list(gate["livelli_parametri"]))["verdetto"]
            if verdetto_uso == "ABSTAIN":
                blocchi.append(f"uso '{uso_richiesto}' non consentito dalle prove disponibili")
        falliti = [v["holdout"] for v in risultato["validazione"] if v["esito"] != "SUPERATO"]
        if falliti:
            avvisi.append("la scelta non supera gli holdout: " + ", ".join(falliti))
        raggio = (risultato.get("stabilita_pesi") or {}).get("raggio", {})
        if raggio.get("distanza") is not None and raggio["distanza"] < 0.05:
            avvisi.append(f"scelta fragile rispetto ai pesi: basta spostare il {100 * raggio['distanza']:.1f}% del peso")
        return {"consentito": not blocchi, "blocchi": blocchi, "avvisi": avvisi, "preregistrazione": dev}
