"""Strumenti numerici in puro Python (nessuna dipendenza esterna).

Campionamento Latin Hypercube, regressione polinomiale ai minimi quadrati,
campionamento di Dirichlet e statistiche di base. Tutto deterministico dato il seme.
"""
from __future__ import annotations

import math
import random
from typing import Sequence


def mean(xs: Sequence[float]) -> float:
    if not xs:
        raise ValueError("media di una sequenza vuota")
    return math.fsum(xs) / len(xs)


def stdev(xs: Sequence[float]) -> float:
    m = mean(xs)
    if len(xs) < 2:
        return 0.0
    return math.sqrt(math.fsum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def quantile(xs: Sequence[float], q: float) -> float:
    """Quantile con interpolazione lineare (stessa convenzione di numpy 'linear')."""
    s = sorted(xs)
    if not s:
        raise ValueError("quantile di una sequenza vuota")
    pos = (len(s) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def lhs(ranges: dict[str, tuple[float, float]], n: int, seed: int) -> list[dict[str, float]]:
    """Latin Hypercube Sampling: n punti, uno per strato in ogni dimensione."""
    rng = random.Random(seed)
    cols: dict[str, list[float]] = {}
    for name in sorted(ranges):
        lo, hi = ranges[name]
        strata = [(i + rng.random()) / n for i in range(n)]
        rng.shuffle(strata)
        cols[name] = [lo + u * (hi - lo) for u in strata]
    return [{k: cols[k][i] for k in sorted(ranges)} for i in range(n)]


def solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Eliminazione di Gauss con pivot parziale."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-300:
            raise ValueError("sistema singolare")
        m[col], m[piv] = m[piv], m[col]
        for r in range(col + 1, n):
            f = m[r][col] / m[col][col]
            if f:
                for c in range(col, n + 1):
                    m[r][c] -= f * m[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (m[r][n] - math.fsum(m[r][c] * x[c] for c in range(r + 1, n))) / m[r][r]
    return x


def polyfit_predict(x: Sequence[float], y: Sequence[float], degree: int = 3) -> list[float]:
    """Valori stimati di una regressione polinomiale y ~ x (x standardizzata, ridge minima)."""
    n = len(x)
    if n != len(y):
        raise ValueError("lunghezze diverse")
    mx = mean(x)
    sx = stdev(x) or 1.0
    z = [(v - mx) / sx for v in x]
    deg = max(0, min(degree, n - 2))
    k = deg + 1
    xtx = [[0.0] * k for _ in range(k)]
    xty = [0.0] * k
    for zi, yi in zip(z, y):
        powers = [zi ** p for p in range(k)]
        for r in range(k):
            xty[r] += powers[r] * yi
            for c in range(k):
                xtx[r][c] += powers[r] * powers[c]
    for r in range(k):
        xtx[r][r] += 1e-9 * n
    beta = solve(xtx, xty)
    return [math.fsum(beta[p] * zi ** p for p in range(k)) for zi in z]


def dirichlet(alpha: Sequence[float], rng: random.Random) -> list[float]:
    g = [rng.gammavariate(a, 1.0) for a in alpha]
    s = math.fsum(g)
    return [v / s for v in g]


def kendall_tau(a: Sequence[float], b: Sequence[float]) -> float:
    """Tau-b di Kendall tra due vettori (per confrontare classifiche)."""
    n = len(a)
    conc = disc = ties_a = ties_b = 0
    for i in range(n):
        for j in range(i + 1, n):
            da = a[i] - a[j]
            db = b[i] - b[j]
            if da == 0 and db == 0:
                continue
            if da == 0:
                ties_a += 1
            elif db == 0:
                ties_b += 1
            elif da * db > 0:
                conc += 1
            else:
                disc += 1
    denom = math.sqrt((conc + disc + ties_a) * (conc + disc + ties_b))
    return (conc - disc) / denom if denom else 1.0
