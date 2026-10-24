"""Valore dell'informazione (dalla 1.0).

- EVPI: valore atteso dell'informazione perfetta su tutto.
- EVPPI: informazione perfetta su UN parametro, stimata con regressione non parametrica sul
  campione di scenari (Strong, Oakley & Brennan, Med Decis Making 2014; qui con polinomio cubico).
- EVSI: informazione da uno STUDIO di dimensione n che stima un parametro con errore standard
  se(n); stimata regredendo l'utilità sulla statistica simulata dello studio
  (Strong, Oakley, Brennan & Breeze, Med Decis Making 2015).
- ENBS e soglia di convenienza: EVSI tradotto in euro SOLO tramite un valore lambda dichiarato.
- VOI-R (novità CWM): di quanto si riduce il RIMPIANTO MASSIMO della scelta minimax se si
  conoscesse in quale intervallo cade un parametro. È il valore dell'informazione per chi decide
  con criterio robusto, coerente con il criterio minimax (l'EVPI usa invece l'utilità attesa).

Tutti i valori sono in unità di utilità normalizzata, salvo dove indicato esplicitamente.
"""
from __future__ import annotations

import math
import random
from typing import Callable, Sequence

from .robust import minimax_value
from .stats import mean, polyfit_predict, quantile

Utils = dict[str, list[float]]


def evpi(utils: Utils) -> float:
    n = len(next(iter(utils.values())))
    best = [max(utils[p][i] for p in utils) for i in range(n)]
    return max(0.0, mean(best) - max(mean(v) for v in utils.values()))


def evppi(utils: Utils, x: Sequence[float], grado: int = 3) -> float:
    """EVPPI per il parametro con valori x (uno per scenario)."""
    fitted = {p: polyfit_predict(x, u, grado) for p, u in utils.items()}
    n = len(x)
    con_info = mean([max(fitted[p][i] for p in utils) for i in range(n)])
    senza = max(mean(u) for u in utils.values())
    return max(0.0, con_info - senza)


def evsi(utils: Utils, theta: Sequence[float], se: float, seme: int = 0, grado: int = 3, ripetizioni: int = 5) -> float:
    """EVSI per uno studio che osserva X = theta + N(0, se^2); media su più estrazioni del rumore."""
    vals = []
    for r in range(ripetizioni):
        rng = random.Random(seme * 1000 + r)
        x = [t + rng.gauss(0.0, se) for t in theta]
        vals.append(evppi(utils, x, grado))
    return mean(vals)


def isotonica(ys: Sequence[float]) -> list[float]:
    """Regressione isotonica crescente (pool adjacent violators)."""
    blocchi: list[list[float]] = []  # [somma, conteggio]
    for y in ys:
        blocchi.append([y, 1.0])
        while len(blocchi) > 1 and blocchi[-2][0] / blocchi[-2][1] > blocchi[-1][0] / blocchi[-1][1]:
            s, c = blocchi.pop()
            blocchi[-1][0] += s
            blocchi[-1][1] += c
    out: list[float] = []
    for s, c in blocchi:
        out.extend([s / c] * int(c))
    return out


def curva_enbs(utils: Utils, theta: Sequence[float], se_unitario: float, dimensioni: Sequence[int],
               decisioni_interessate: float, euro_per_unita_utilita: float | None,
               costo_fisso: float, costo_per_unita: float, seme: int = 0) -> list[dict]:
    """Per ogni n: EVSI, costo dello studio, soglia lambda di convenienza e (se lambda è dato) ENBS.

    Le stime grezze dell'EVSI sono rumorose: si impone che non superino l'EVPPI del parametro
    (limite teorico) e che crescano con n (regressione isotonica).
    """
    dims = sorted(dimensioni)
    tetto = evppi(utils, theta)
    grezzi = [min(tetto, evsi(utils, theta, se_unitario / math.sqrt(n), seme=seme + n)) for n in dims]
    lisci = isotonica(grezzi)
    out = []
    for n, v, g in zip(dims, lisci, grezzi):
        se = se_unitario / math.sqrt(n)
        costo = costo_fisso + costo_per_unita * n
        soglia = costo / (v * decisioni_interessate) if v > 1e-12 else math.inf
        riga = {"n": n, "errore_standard": se, "evsi": v, "evsi_grezzo": g, "evppi_tetto": tetto, "costo_studio_eur": costo,
                "lambda_minimo_eur_per_unita": soglia}
        if euro_per_unita_utilita is not None:
            riga["enbs_eur"] = v * decisioni_interessate * euro_per_unita_utilita - costo
        out.append(riga)
    return out


def voi_rimpianto(utils: Utils, x: Sequence[float], intervalli: int = 4) -> dict:
    """VOI-R: riduzione attesa del rimpianto massimo della scelta minimax sapendo l'intervallo di x."""
    n = len(x)
    scelta0, r0 = minimax_value(utils)
    tagli = [quantile(x, k / intervalli) for k in range(1, intervalli)]
    gruppi: list[list[int]] = [[] for _ in range(intervalli)]
    for i, v in enumerate(x):
        b = sum(1 for t in tagli if v > t)
        gruppi[b].append(i)
    gruppi = [g for g in gruppi if g]
    dopo = []
    scelte = []
    for g in gruppi:
        s, r = minimax_value(utils, g)
        dopo.append((len(g) / n) * r)
        scelte.append(s)
    r_dopo = math.fsum(dopo)
    return {"rimpianto_massimo_ora": r0, "rimpianto_massimo_atteso_dopo": r_dopo,
            "voi_r": max(0.0, r0 - r_dopo), "quota_ridotta": (r0 - r_dopo) / r0 if r0 > 0 else 0.0,
            "scelta_ora": scelta0, "scelte_per_intervallo": scelte,
            "la_scelta_cambierebbe": any(s != scelta0 for s in scelte)}


def analisi_completa(utils: Utils, scenari: list[dict[str, float]], parametri: Sequence[str]) -> dict:
    per_param = {}
    for p in parametri:
        x = [s[p] for s in scenari]
        per_param[p] = {"evppi": evppi(utils, x), **voi_rimpianto(utils, x)}
    classifica_evppi = sorted(parametri, key=lambda p: -per_param[p]["evppi"])
    classifica_voir = sorted(parametri, key=lambda p: -per_param[p]["voi_r"])
    return {"evpi": evpi(utils), "per_parametro": per_param,
            "priorita_ricerca_utilita_attesa": classifica_evppi,
            "priorita_ricerca_robusta": classifica_voir}


def stima_studi(utils: Utils, scenari: list[dict[str, float]], studi: list[dict],
                lambda_eur: float | None, decisioni: float, seme: int = 0) -> list[dict]:
    out = []
    for st in studi:
        theta = [s[st["parametro"]] for s in scenari]
        curva = curva_enbs(utils, theta, st["errore_standard_unitario"], st["dimensioni"], decisioni,
                           lambda_eur, st["costo_fisso_eur"], st["costo_per_unita_eur"], seme)
        if lambda_eur is not None:
            migliore = max(curva, key=lambda r: r["enbs_eur"])
            consigliata = migliore["n"] if migliore["enbs_eur"] > 0 else None
        else:
            migliore = min(curva, key=lambda r: r["lambda_minimo_eur_per_unita"])
            consigliata = migliore["n"] if math.isfinite(migliore["lambda_minimo_eur_per_unita"]) else None
        nota = ("lo studio non cambierebbe la scelta a utilità attesa: valore nullo con questo criterio"
                if consigliata is None and lambda_eur is None else "")
        out.append({"studio": st["nome"], "parametro": st["parametro"], "unita": st.get("unita", ""),
                    "curva": curva, "dimensione_consigliata": consigliata, "nota": nota})
    return out
