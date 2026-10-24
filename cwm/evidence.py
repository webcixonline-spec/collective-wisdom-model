"""Registro delle prove e cancello decisionale graduato (dalla 0.8).

Ispirato al metodo GRADE (Guyatt et al., BMJ 2008): ogni fonte parte da un livello che dipende
dal disegno dello studio e viene declassata per rischio di distorsione, incoerenza, indirettezza,
imprecisione e distorsione di pubblicazione. Ogni parametro del modello è collegato alle fonti
che lo sostengono: il suo livello è il massimo tra le fonti. Il cancello confronta i livelli con
requisiti minimi e desiderati che dipendono dall'OBIETTIVO della decisione.

Esiti possibili: PASS, PASS_CON_RISERVA, ABSTAIN. Non sono punteggi di confidenza inventati:
sono conseguenze esplicite e verificabili del registro e dei requisiti.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

LIVELLI = {4: "alta", 3: "moderata", 2: "bassa", 1: "molto_bassa", 0: "assente"}
PARTENZA = {
    "meta_analisi_rct": 4,
    "rct": 4,
    "dato_amministrativo_verificato": 4,
    "quasi_sperimentale": 3,
    "osservazionale": 2,
    "parere_esperti": 1,
    "assunzione": 0,
    "metodologia": None,  # non è prova su un parametro
}
DOMINI_DECLASSAMENTO = ("rischio_bias", "incoerenza", "indirettezza", "imprecisione", "pubblicazione")


def carica_json(percorso: str | Path) -> dict:
    return json.loads(Path(percorso).read_text(encoding="utf-8"))


def livello_fonte(fonte: dict) -> int | None:
    disegno = fonte.get("disegno")
    if disegno not in PARTENZA:
        raise ValueError(f"fonte {fonte.get('id')}: disegno {disegno!r} sconosciuto (ammessi: {', '.join(PARTENZA)})")
    base = PARTENZA[disegno]
    if base is None:
        return None
    if base == 0:
        return 0
    declassamenti = fonte.get("declassamenti", {})
    ignoti = sorted(set(declassamenti) - set(DOMINI_DECLASSAMENTO))
    if ignoti:
        raise ValueError(f"fonte {fonte.get('id')}: domini di declassamento sconosciuti {ignoti}")
    valori = {d: int(declassamenti.get(d, 0)) for d in DOMINI_DECLASSAMENTO}
    if any(v < 0 for v in valori.values()):
        raise ValueError(f"fonte {fonte.get('id')}: i declassamenti non possono essere negativi")
    return max(1, base - sum(valori.values()))


def _valida_requisiti(obiettivo: str, req: dict, parametri: list[str]) -> None:
    par = req.get("parametri")
    if not isinstance(par, dict) or not par:
        raise ValueError(f"obiettivo '{obiettivo}': nessun parametro richiesto (un cancello vuoto darebbe sempre PASS)")
    for p, r in par.items():
        if p not in parametri:
            raise ValueError(f"obiettivo '{obiettivo}': parametro sconosciuto {p!r} (noti: {', '.join(parametri)})")
        minimo = r.get("minimo")
        desiderato = r.get("desiderato", minimo)
        if not all(isinstance(x, int) and not isinstance(x, bool) for x in (minimo, desiderato)) \
                or not 0 <= minimo <= desiderato <= max(LIVELLI):
            raise ValueError(f"obiettivo '{obiettivo}', parametro {p}: serve 0 <= minimo <= desiderato <= {max(LIVELLI)} interi")


def livelli_parametri(registro: dict, parametri: list[str]) -> dict[str, dict]:
    out = {p: {"livello": 0, "nome_livello": LIVELLI[0], "fonti": []} for p in parametri}
    for f in registro["fonti"]:
        liv = livello_fonte(f)
        if liv is None:
            continue
        for p in f.get("sostiene_parametri", []):
            if p not in out:
                continue
            out[p]["fonti"].append({"id": f["id"], "livello": liv})
            if liv > out[p]["livello"]:
                out[p]["livello"] = liv
                out[p]["nome_livello"] = LIVELLI[liv]
    return out


def cancello(registro: dict, requisiti: dict, obiettivo: str, parametri: list[str]) -> dict:
    if obiettivo not in requisiti["obiettivi"]:
        raise KeyError(f"obiettivo sconosciuto: {obiettivo}; disponibili: {sorted(requisiti['obiettivi'])}")
    req = requisiti["obiettivi"][obiettivo]
    _valida_requisiti(obiettivo, req, parametri)
    liv = livelli_parametri(registro, parametri)
    dettagli = []
    bloccanti = []
    riserve = []
    for p, r in req["parametri"].items():
        attuale = liv.get(p, {"livello": 0})["livello"]
        minimo = int(r["minimo"])
        desiderato = int(r.get("desiderato", minimo))
        if attuale < minimo:
            stato = "insufficiente"
            bloccanti.append(f"{p}: prova {LIVELLI[attuale]}, serve almeno {LIVELLI[minimo]} ({r.get('motivo', '')})".strip())
        elif attuale < desiderato:
            stato = "con_riserva"
            riserve.append(f"{p}: prova {LIVELLI[attuale]}, auspicabile {LIVELLI[desiderato]}")
        else:
            stato = "sufficiente"
        dettagli.append({"parametro": p, "livello": attuale, "nome_livello": LIVELLI[attuale],
                         "minimo": minimo, "desiderato": desiderato, "stato": stato})
    verdetto = "ABSTAIN" if bloccanti else ("PASS_CON_RISERVA" if riserve else "PASS")
    return {
        "obiettivo": obiettivo,
        "descrizione_obiettivo": req.get("descrizione", ""),
        "verdetto": verdetto,
        "motivi_astensione": bloccanti,
        "riserve": riserve,
        "dettagli": dettagli,
        "livelli_parametri": liv,
        "ambito_consentito": obiettivo if verdetto != "ABSTAIN" else None,
    }


def obiettivi_superati(registro: dict, requisiti: dict, parametri: list[str]) -> dict[str, str]:
    return {o: cancello(registro, requisiti, o, parametri)["verdetto"] for o in requisiti["obiettivi"]}


def _intervallo_valido(fonte_id: str, parametro: str, stima: object) -> tuple[float, float]:
    iv = stima.get("intervallo") if isinstance(stima, dict) else None
    if not (isinstance(iv, list) and len(iv) == 2
            and all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in iv)
            and iv[0] <= iv[1]):
        raise ValueError(f"fonte {fonte_id}, stima di {parametro}: serve 'intervallo' [minimo, massimo] di numeri finiti")
    if not str(stima.get("derivazione", "")).strip():
        raise ValueError(f"fonte {fonte_id}, stima di {parametro}: manca 'derivazione' (come è stato ricavato l'intervallo)")
    return float(iv[0]), float(iv[1])


def intervalli_da_registro(registro: dict, ipotesi: dict[str, tuple[float, float]]) -> dict[str, dict]:
    """Intervalli di incertezza ricavati dalle stime delle fonti, con la loro provenienza.

    Regola (conservativa e verificabile): per ogni parametro si considerano le fonti con livello di prova
    almeno max(1, migliore - 1) che dichiarano una stima, e si prende l'inviluppo dei loro intervalli
    (minimo dei minimi, massimo dei massimi). Le assunzioni (livello 0) non definiscono intervalli.
    Senza stime il parametro resta sull'intervallo ipotetico, dichiarato come tale.
    """
    candidati: dict[str, list[tuple[int, str, float, float]]] = {p: [] for p in ipotesi}
    for f in registro["fonti"]:
        stime = f.get("stime", {})
        for p, stima in stime.items():
            if p not in ipotesi:
                raise ValueError(f"fonte {f.get('id')}: stima di un parametro sconosciuto {p!r}")
            if p not in f.get("sostiene_parametri", []):
                raise ValueError(f"fonte {f.get('id')}: stima di {p} ma il parametro non è in 'sostiene_parametri'")
            lo, hi = _intervallo_valido(f.get("id"), p, stima)
            liv = livello_fonte(f)
            if liv is None or liv < 1:
                raise ValueError(f"fonte {f.get('id')}: una fonte di livello {LIVELLI.get(liv, liv)} non può definire intervalli")
            candidati[p].append((liv, f["id"], lo, hi))
    out = {}
    for p, (lo_i, hi_i) in ipotesi.items():
        c = candidati[p]
        if not c:
            out[p] = {"intervallo": [lo_i, hi_i], "origine": "ipotesi", "fonti": [], "fonti_escluse": []}
            continue
        soglia = max(1, max(x[0] for x in c) - 1)
        usati = [x for x in c if x[0] >= soglia]
        out[p] = {"intervallo": [min(x[2] for x in usati), max(x[3] for x in usati)], "origine": "fonti",
                  "fonti": sorted(x[1] for x in usati), "fonti_escluse": sorted(x[1] for x in c if x[0] < soglia),
                  "livello_minimo_usato": LIVELLI[soglia]}
    return out
