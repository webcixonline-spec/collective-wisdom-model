"""Elicitazione dei pesi con persone reali (dalla 1.2.1).

Flusso (protocollo completo in docs/elicitazione.md):
1. `python3 -m cwm elicitazione modulo --partecipanti N --out modulo.csv` genera il modulo con tutti i
   confronti a coppie (10 per 5 criteri), una riga per confronto e per partecipante.
2. Il facilitatore raccoglie i giudizi (scala di Saaty 1/9..9; si accettano "3", "1/3", "0,333").
3. `python3 -m cwm elicitazione importa modulo.csv --facilitatore ... --protocollo ... --out partecipanti.json`
   valida il modulo e, per chi supera la soglia di coerenza, indica QUALI giudizi rivedere con la persona:
   l'incoerenza si discute, non si esclude in silenzio.

Le preferenze entrano in una raccomandazione solo se il file dichiara "natura": "reale" ed è documentato
(facilitatore, protocollo, data e consenso per ogni partecipante): vedi valida_partecipanti.
"""
from __future__ import annotations

import csv
import datetime as _dt
import io
import math
from fractions import Fraction
from itertools import combinations
from pathlib import Path

from .weights import autovettore, coerenza, matrice_da_giudizi

COLONNE = ("partecipante_id", "ruolo", "data", "consenso", "criterio_a", "criterio_b", "valore")
MIN_PARTECIPANTI = 3
SI = {"si", "sì", "s", "yes", "y", "true", "1", "x"}


def modulo(criteri: tuple[str, ...] | list[str], partecipanti: int) -> str:
    if partecipanti < 1:
        raise ValueError("serve almeno un partecipante")
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(COLONNE)
    for k in range(1, partecipanti + 1):
        for a, b in combinations(criteri, 2):
            w.writerow([f"P{k:02d}", "", "", "", a, b, ""])
    return buf.getvalue()


def _valore(testo: str, riga: int) -> float:
    t = testo.strip().replace(",", ".")
    try:
        v = float(Fraction(t))
    except (ValueError, ZeroDivisionError):
        raise ValueError(f"riga {riga}, valore: {testo!r} non è un giudizio (usare 1/9..9, es. 3 oppure 1/3)") from None
    if not (1 / 9 - 1e-9 <= v <= 9 + 1e-9):
        raise ValueError(f"riga {riga}, valore: {testo!r} fuori dalla scala 1/9..9")
    return v


def importa(percorso: str | Path, criteri: tuple[str, ...] | list[str], facilitatore: str, protocollo: str,
            soglia_cr: float = 0.10, oggi: _dt.date | None = None) -> tuple[dict, dict]:
    """Restituisce (documento partecipanti, diagnosi di coerenza per partecipante)."""
    if not facilitatore.strip() or not protocollo.strip():
        raise ValueError("facilitatore e protocollo sono obbligatori")
    testo = Path(percorso).read_text(encoding="utf-8-sig")
    prima = testo.splitlines()[0] if testo.strip() else ""
    lettore = csv.DictReader(io.StringIO(testo), delimiter=";" if prima.count(";") > prima.count(",") else ",")
    if tuple(c.strip() for c in lettore.fieldnames or ()) != COLONNE:
        raise ValueError(f"intestazione non valida: servono esattamente le colonne {', '.join(COLONNE)}")
    persone: dict[str, dict] = {}
    for n, r in enumerate(lettore, 2):
        r = {k.strip(): (v or "").strip() for k, v in r.items()}
        vuoti = [c for c in COLONNE if not r[c]]
        if vuoti:
            raise ValueError(f"riga {n}: campi vuoti {', '.join(vuoti)}")
        if r["consenso"].lower() not in SI:
            raise ValueError(f"riga {n}: senza consenso registrato il partecipante {r['partecipante_id']} non può essere usato")
        p = persone.setdefault(r["partecipante_id"], {"id": r["partecipante_id"], "ruolo": r["ruolo"], "data": r["data"],
                                                      "consenso": True, "giudizi": []})
        if (p["ruolo"], p["data"]) != (r["ruolo"], r["data"]):
            raise ValueError(f"riga {n}: ruolo o data diversi dalle altre righe di {r['partecipante_id']}")
        p["giudizi"].append({"a": r["criterio_a"], "b": r["criterio_b"], "valore": _valore(r["valore"], n)})
    doc = {"natura": "reale", "facilitatore": facilitatore.strip(), "protocollo": protocollo.strip(),
           "importato_il": (oggi or _dt.date.today()).isoformat(), "criteri": list(criteri),
           "partecipanti": list(persone.values())}
    problemi = valida_partecipanti(doc, criteri, oggi)
    if problemi:
        raise ValueError("modulo non valido: " + "; ".join(problemi))
    return doc, diagnosi(doc, criteri, soglia_cr)


def diagnosi(doc: dict, criteri, soglia_cr: float = 0.10) -> dict[str, dict]:
    """Per ogni partecipante: rapporto di coerenza e, se supera la soglia, i due giudizi più lontani dai
    pesi impliciti (|log(a_ij · w_j / w_i)|), da rivedere insieme alla persona."""
    idx = {c: i for i, c in enumerate(criteri)}
    out = {}
    for p in doc["partecipanti"]:
        m = matrice_da_giudizi(criteri, p["giudizi"])
        cr = coerenza(m)
        w, _ = autovettore(m)
        scarti = sorted(((abs(math.log(g["valore"] * w[idx[g["b"]]] / w[idx[g["a"]]])), g) for g in p["giudizi"]),
                        key=lambda t: -t[0])
        out[p["id"]] = {"cr": cr, "coerente": cr <= soglia_cr, "pesi": dict(zip(criteri, w)),
                        "da_rivedere": [] if cr <= soglia_cr else
                        [{"a": g["a"], "b": g["b"], "valore": g["valore"],
                          "coerente_con_gli_altri_giudizi": w[idx[g["a"]]] / w[idx[g["b"]]]} for _, g in scarti[:2]]}
    return out


def valida_partecipanti(doc: dict | None, criteri, oggi: _dt.date | None = None) -> list[str]:
    """Problemi che impediscono di usare le preferenze per una raccomandazione (lista vuota = utilizzabili)."""
    if not isinstance(doc, dict):
        return ["nessun file di partecipanti"]
    natura = doc.get("natura")
    if natura != "reale":
        return [f"preferenze di natura {natura!r}: non raccolte da persone reali" if natura else
                "il file dei partecipanti non dichiara 'natura': trattato come non reale"]
    problemi = []
    for campo in ("facilitatore", "protocollo"):
        if not str(doc.get(campo, "")).strip():
            problemi.append(f"manca '{campo}'")
    if doc.get("criteri") is not None and list(doc["criteri"]) != list(criteri):
        problemi.append("i criteri del file non coincidono con quelli del modello")
    persone = doc.get("partecipanti", [])
    if len(persone) < MIN_PARTECIPANTI:
        problemi.append(f"{len(persone)} partecipanti: ne servono almeno {MIN_PARTECIPANTI}")
    oggi = oggi or _dt.date.today()
    for p in persone:
        pid = p.get("id", "?")
        if not str(p.get("ruolo", "")).strip():
            problemi.append(f"{pid}: manca il ruolo")
        if p.get("consenso") is not True:
            problemi.append(f"{pid}: consenso non registrato")
        try:
            if _dt.date.fromisoformat(str(p.get("data"))) > oggi:
                problemi.append(f"{pid}: data nel futuro")
        except ValueError:
            problemi.append(f"{pid}: data mancante o non in formato AAAA-MM-GG")
        try:
            matrice_da_giudizi(criteri, p.get("giudizi", []))
        except (ValueError, KeyError) as e:
            problemi.append(f"{pid}: {e}")
    return problemi
