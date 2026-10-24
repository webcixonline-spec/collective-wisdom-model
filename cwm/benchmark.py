"""Benchmark sul lake problem: stessi numeri di EMA Workbench, più il livello decisionale CWM.

File di riferimento in benchmarks/ (generati con EMA Workbench 3.0, script inclusi):
- lake_ema_results.tar.gz : 200 scenari LHS x 6 politiche, modello ufficiale lake_problem_intertemporal
- lake_ema_reference.json : metriche di robustezza calcolate indipendentemente con numpy/pandas
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

from . import ema_bridge as eb
from . import lake
from .robust import choose_minimax, summarize
from .voi import evppi, evpi, voi_rimpianto
from .weights import raggio_stabilita, smaa

CARTELLA = Path(__file__).resolve().parent.parent / "benchmarks"


def _max_diff(rif: dict, cwm: dict) -> float:
    d = 0.0
    for k, v in rif.items():
        if isinstance(v, dict):
            d = max(d, _max_diff(v, cwm[k]))
        elif isinstance(v, (int, float)):
            d = max(d, abs(float(v) - float(cwm[k])))
    return d


def fedelta_modello(ris: eb.RisultatiEMA, quanti: int, backend: str) -> dict:
    """Riesegue il lake model del CWM sugli stessi esperimenti e confronta con gli esiti di EMA."""
    nomi = ("max_p", "utility", "inertia", "reliability")
    diff = {n: 0.0 for n in nomi}
    rel = {n: [] for n in nomi}
    t = time.time()
    passo = max(1, len(ris.esperimenti) // quanti)
    usati = list(range(0, len(ris.esperimenti), passo))[:quanti]
    for i in usati:
        e = ris.esperimenti[i]
        out = lake.lake_problem(b=e["b"], q=e["q"], mean=e["mean"], stdev=e["stdev"], delta=e["delta"],
                                decisions=lake.decisioni_alternate(e["base"], e["ampiezza"]), backend=backend)
        for n, v in zip(nomi, out):
            ref = ris.esiti[n][i]
            diff[n] = max(diff[n], abs(v - ref))
            if abs(ref) > 1e-12:
                rel[n].append(abs(v - ref) / abs(ref))
    return {"backend": backend, "esperimenti": len(usati), "secondi": round(time.time() - t, 2),
            "differenza_massima_assoluta": diff,
            "differenza_relativa_media": {n: (sum(r) / len(r) if r else 0.0) for n, r in rel.items()}}


def esegui(campioni_smaa: int = 300, direzioni: int = 20, quanti_fedelta: int = 60) -> dict:
    ris = eb.carica_risultati(str(CARTELLA / "lake_ema_results.tar.gz"))
    rif = json.loads((CARTELLA / "lake_ema_reference.json").read_text(encoding="utf-8"))
    soglie = {k: tuple(v) for k, v in rif["soglie"].items()}
    an = eb.analizza(ris, rif["direzioni"], rif["pesi"], soglie)

    confronto = {
        "per_esito": _max_diff(rif["per_esito"], an["per_esito"]),
        "quota_soddisfacente": _max_diff(rif["quota_soddisfacente"], an["quota_soddisfacente"]),
        "composita": _max_diff(rif["composita"], an["composita"]),
        "stessa_scelta_minimax": rif["scelta_minimax"] == an["scelta_minimax"],
    }
    confronto["identico"] = (max(confronto["per_esito"], confronto["quota_soddisfacente"], confronto["composita"]) < 1e-9
                             and confronto["stessa_scelta_minimax"])

    fedelta = {}
    try:
        import numpy  # noqa: F401
        fedelta["numpy"] = fedelta_modello(ris, quanti_fedelta, "numpy")
    except ImportError:
        fedelta["numpy"] = {"nota": "numpy non installato: confronto esatto non eseguito"}
    fedelta["python"] = fedelta_modello(ris, min(quanti_fedelta, 30), "python")

    # --- ciò che EMA e Rhodium non forniscono -------------------------------------------
    utils = an["utils"]
    scen = ris.parametri_scenari()
    voi = {"evpi": evpi(utils), "per_incertezza": {}}
    for p in ris.incertezze():
        x = [s[p] for s in scen]
        voi["per_incertezza"][p] = {"evppi": evppi(utils, x), **voi_rimpianto(utils, x)}

    criteri = list(rif["direzioni"])
    norm = {}
    for e, verso in rif["direzioni"].items():
        vals = ris.esiti[e]
        lo, hi = min(vals), max(vals)
        norm[e] = {p: [((v - lo) / (hi - lo)) if verso == "max" else ((hi - v) / (hi - lo)) for v in r]
                   for p, r in ris.pivot(e).items()}
    n = len(ris.scenari())

    def scegli(w: dict[str, float]) -> str:
        s = math.fsum(w.values())
        u = {p: [math.fsum(w[e] * norm[e][p][i] for e in criteri) / s for i in range(n)] for p in ris.politiche()}
        return choose_minimax(summarize(u))

    pesi = {k: v / math.fsum(rif["pesi"].values()) for k, v in rif["pesi"].items()}
    stabilita = {"smaa_pesi_ignoti": smaa(scegli, criteri, None, campioni_smaa, 7),
                 "raggio": raggio_stabilita(scegli, criteri, pesi, direzioni, 11)}

    return {
        "ema_workbench_riferimento": rif["ema_workbench"],
        "esperimenti": len(ris.esperimenti), "scenari": n, "politiche": ris.politiche(),
        "leve": ris.leve(), "incertezze": ris.incertezze(),
        "confronto_con_ema": confronto, "fedelta_modello": fedelta,
        "robustezza": {"scelta_minimax": an["scelta_minimax"], "composita": an["composita"],
                       "quota_soddisfacente": an["quota_soddisfacente"]},
        "aggiunte_cwm": {"valore_informazione": voi, "stabilita_pesi": stabilita},
        "nota_direzioni": "inertia è minimizzata: in EMA 3.0 la funzione conta i cambi annuali > 0,02, "
                          "mentre l'esempio di ottimizzazione la dichiara MAXIMIZE.",
    }
