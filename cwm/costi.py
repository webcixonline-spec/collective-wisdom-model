"""Raccolta dei costi reali per posto dagli istituti (dalla 1.2.1).

Ogni riga del CSV descrive un preventivo, una delibera o una voce di bilancio di un istituto. Il costo
per posto è ricavato in modo esplicito:

    costo_per_posto = costo_orario_personale × (1 + oneri_e_indiretti_pct/100) × ore_per_studente
                      / studenti_per_gruppo + altri_costi_per_studente

Il risultato NON viene scritto nel registro delle prove: il comando produce una PROPOSTA di fonte da
rivedere e incollare a mano in config/registro_prove.json. Chi aggiunge prove al registro deve
poterne rispondere.

Formati accettati: CSV con virgola o punto e virgola (Excel italiano), UTF-8 con o senza BOM,
decimali con punto o, se il separatore è il punto e virgola, con virgola.
"""
from __future__ import annotations

import csv
import datetime as _dt
import io
import math
import statistics
from pathlib import Path

COLONNE = ("istituto", "codice_meccanografico", "tipo_istituto", "gruppo", "formato", "ore_per_studente",
           "studenti_per_gruppo", "costo_orario_personale_eur", "oneri_e_indiretti_pct",
           "altri_costi_per_studente_eur", "documento", "data_documento", "verificato_da")
GRUPPI = {"svantaggiati": ("costo_svantaggiati",), "altri": ("costo_altri",), "entrambi": ("costo_svantaggiati", "costo_altri")}
FORMATI = ("individuale", "piccolo_gruppo")
MIN_ISTITUTI = 3  # sotto questa soglia l'intervallo non rappresenta la variabilità tra istituti


def _numero(testo: str, decimale_virgola: bool, campo: str, riga: int, minimo: float, positivo: bool) -> float:
    t = testo.strip()
    if decimale_virgola and "," in t:
        t = t.replace(".", "").replace(",", ".")  # 1.234,50 -> 1234.50
    try:
        v = float(t)
    except ValueError:
        raise ValueError(f"riga {riga}, {campo}: {testo!r} non è un numero") from None
    if not math.isfinite(v) or v < minimo or (positivo and v <= 0):
        raise ValueError(f"riga {riga}, {campo}: {testo!r} fuori dai valori ammessi")
    return v


def leggi(percorso: str | Path, oggi: _dt.date | None = None) -> list[dict]:
    testo = Path(percorso).read_text(encoding="utf-8-sig")
    prima = testo.splitlines()[0] if testo.strip() else ""
    separatore = ";" if prima.count(";") > prima.count(",") else ","
    lettore = csv.DictReader(io.StringIO(testo), delimiter=separatore)
    if tuple(c.strip() for c in lettore.fieldnames or ()) != COLONNE:
        raise ValueError(f"intestazione non valida: servono esattamente le colonne {', '.join(COLONNE)}")
    oggi = oggi or _dt.date.today()
    dv = separatore == ";"
    righe = []
    for n, r in enumerate(lettore, 2):
        r = {k.strip(): (v or "").strip() for k, v in r.items()}
        vuoti = [c for c in COLONNE if not r[c]]
        if vuoti:
            raise ValueError(f"riga {n}: campi vuoti {', '.join(vuoti)} (documento e verifica sono obbligatori)")
        if r["gruppo"] not in GRUPPI:
            raise ValueError(f"riga {n}, gruppo: {r['gruppo']!r} (ammessi: {', '.join(GRUPPI)})")
        if r["formato"] not in FORMATI:
            raise ValueError(f"riga {n}, formato: {r['formato']!r} (ammessi: {', '.join(FORMATI)})")
        try:
            data = _dt.date.fromisoformat(r["data_documento"])
        except ValueError:
            raise ValueError(f"riga {n}, data_documento: serve AAAA-MM-GG, trovato {r['data_documento']!r}") from None
        if data > oggi:
            raise ValueError(f"riga {n}: data_documento {data} nel futuro")
        ore = _numero(r["ore_per_studente"], dv, "ore_per_studente", n, 0, True)
        gruppo_n = _numero(r["studenti_per_gruppo"], dv, "studenti_per_gruppo", n, 1, True)
        if gruppo_n != int(gruppo_n):
            raise ValueError(f"riga {n}, studenti_per_gruppo: serve un intero")
        if (r["formato"] == "individuale") != (gruppo_n == 1):
            raise ValueError(f"riga {n}: formato {r['formato']} incoerente con {int(gruppo_n)} studenti per gruppo")
        orario = _numero(r["costo_orario_personale_eur"], dv, "costo_orario_personale_eur", n, 0, True)
        pct = _numero(r["oneri_e_indiretti_pct"], dv, "oneri_e_indiretti_pct", n, 0, False)
        altri = _numero(r["altri_costi_per_studente_eur"], dv, "altri_costi_per_studente_eur", n, 0, False)
        costo = orario * (1 + pct / 100) * ore / gruppo_n + altri
        righe.append({**r, "riga": n, "data_documento": data.isoformat(), "ore_per_studente": ore,
                      "studenti_per_gruppo": int(gruppo_n), "costo_orario_personale_eur": orario,
                      "oneri_e_indiretti_pct": pct, "altri_costi_per_studente_eur": altri, "costo_per_posto_eur": costo})
    if not righe:
        raise ValueError("nessuna riga di dati")
    return righe


def riepilogo(righe: list[dict]) -> dict[str, dict]:
    out = {}
    for parametro in ("costo_svantaggiati", "costo_altri"):
        rr = [r for r in righe if parametro in GRUPPI[r["gruppo"]]]
        if not rr:
            continue
        valori = [r["costo_per_posto_eur"] for r in rr]
        out[parametro] = {
            "righe": len(rr), "istituti": len({r["codice_meccanografico"] for r in rr}),
            "tipi_istituto": sorted({r["tipo_istituto"] for r in rr}),
            "minimo": min(valori), "mediana": statistics.median(valori), "massimo": max(valori),
            "ore_per_studente": [min(r["ore_per_studente"] for r in rr), max(r["ore_per_studente"] for r in rr)],
        }
    return out


def proposta_fonte(righe: list[dict], id_fonte: str) -> dict:
    """Bozza di voce per il registro delle prove: va riletta, completata e incollata a mano."""
    rie = riepilogo(righe)
    pochi = [p for p, s in rie.items() if s["istituti"] < MIN_ISTITUTI]
    istituti = sorted({r["codice_meccanografico"] for r in righe})
    return {
        "id": id_fonte,
        "citazione": f"Preventivi e documenti contabili di {len(istituti)} istituti ({', '.join(istituti)})",
        "disegno": "dato_amministrativo_verificato",
        "contesto": "; ".join(f"{p}: {s['righe']} righe da {s['istituti']} istituti ({', '.join(s['tipi_istituto'])}), "
                              f"mediana {s['mediana']:.0f} €, {s['ore_per_studente'][0]:g}-{s['ore_per_studente'][1]:g} ore per studente"
                              for p, s in rie.items()),
        "declassamenti": {"imprecisione": 1} if pochi else {},
        "motivo_declassamenti": (f"Imprecisione: meno di {MIN_ISTITUTI} istituti per {', '.join(pochi)}." if pochi else
                                 "Nessuno proposto: valutare rischio di distorsione (istituti scelti a caso o per convenienza?) "
                                 "e indirettezza (stesso formato e dosaggio del programma?)."),
        "sostiene_parametri": sorted(rie),
        "stime": {p: {"intervallo": [round(s["minimo"], 2), round(s["massimo"], 2)], "unita": "EUR per posto",
                      "derivazione": f"Minimo e massimo del costo per posto su {s['righe']} documenti di {s['istituti']} istituti "
                                     "(costo orario × (1 + oneri e indiretti) × ore / studenti per gruppo + altri costi)."}
                  for p, s in rie.items()},
        "documenti": [{"istituto": r["codice_meccanografico"], "documento": r["documento"], "data": r["data_documento"],
                       "verificato_da": r["verificato_da"], "costo_per_posto_eur": round(r["costo_per_posto_eur"], 2)} for r in righe],
        "consultato_il": _dt.date.today().isoformat(),
        "da_verificare": "PROPOSTA generata da 'python3 -m cwm costi': rivedere declassamenti e contesto prima di incollarla nel registro.",
    }
