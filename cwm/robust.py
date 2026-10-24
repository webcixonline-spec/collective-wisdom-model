"""Metriche di robustezza generiche su una tabella utilità[politica][scenario].

Indipendenti dal dominio: usate sia dal modello educativo sia dal ponte EMA.
"""
from __future__ import annotations

from typing import Iterable, Sequence

from .stats import mean, quantile

Utils = dict[str, list[float]]


def _n(utils: Utils) -> int:
    lens = {len(v) for v in utils.values()}
    if len(lens) != 1:
        raise ValueError("tutte le politiche devono avere lo stesso numero di scenari")
    return lens.pop()


def regrets(utils: Utils, idx: Iterable[int] | None = None) -> dict[str, list[float]]:
    """Rimpianto = migliore utilità nello scenario - utilità della politica."""
    n = _n(utils)
    ids = list(range(n)) if idx is None else list(idx)
    out: dict[str, list[float]] = {p: [] for p in utils}
    for i in ids:
        best = max(utils[p][i] for p in utils)
        for p in utils:
            out[p].append(best - utils[p][i])
    return out


def summarize(utils: Utils, tol: float = 1e-12) -> dict[str, dict[str, float]]:
    n = _n(utils)
    reg = regrets(utils)
    wins = {p: 0 for p in utils}
    for i in range(n):
        best = max(utils[p][i] for p in utils)
        winners = [p for p in utils if best - utils[p][i] <= tol]
        if len(winners) == 1:
            wins[winners[0]] += 1
    return {
        p: {
            "punteggio_medio": mean(utils[p]),
            "punteggio_p10": quantile(utils[p], 0.10),
            "rimpianto_medio": mean(reg[p]),
            "rimpianto_p90": quantile(reg[p], 0.90),
            "rimpianto_massimo": max(reg[p]),
            "vittorie_uniche": wins[p],
        }
        for p in utils
    }


def choose_minimax(metrics: dict[str, dict[str, float]]) -> str:
    """Minimo rimpianto massimo; a parità, punteggio medio più alto, poi nome."""
    return min(metrics, key=lambda p: (round(metrics[p]["rimpianto_massimo"], 12), -metrics[p]["punteggio_medio"], p))


def choose_mean(metrics: dict[str, dict[str, float]]) -> str:
    return min(metrics, key=lambda p: (-round(metrics[p]["punteggio_medio"], 12), p))


def minimax_value(utils: Utils, idx: Sequence[int] | None = None) -> tuple[str, float]:
    reg = regrets(utils, idx)
    p = min(reg, key=lambda k: (round(max(reg[k]), 12), k))
    return p, max(reg[p])
