"""Lake problem (Carpenter et al. 1999; Quinn et al. 2017), problema di riferimento di EMA Workbench e Rhodium.

Riproduce `lake_problem_intertemporal` di EMA Workbench 3.0 (examples/lake_models.py):
- backend "numpy": stesso generatore (default_rng(rng)) e stesse operazioni -> stessi numeri di EMA (a meno di 1e-15 tra CPU diverse);
- backend "python": solo libreria standard -> stessi esiti deterministici (utility, inertia),
  esiti stocastici (max_p, reliability) statisticamente equivalenti.
"""
from __future__ import annotations

import math
import random

INCERTEZZE = {"b": (0.1, 0.45), "q": (2.0, 4.5), "mean": (0.01, 0.05), "stdev": (0.001, 0.005), "delta": (0.93, 0.99)}

# Direzioni coerenti con la funzione di EMA 3.0: "inertia" conta i cambi annuali > 0.02, quindi va MINIMIZZATA.
# (Nota: examples/optimization_lake_model_intertemporal.py di EMA 3.0 la dichiara MAXIMIZE: incoerenza dell'esempio.)
DIREZIONI = {"max_p": "min", "utility": "max", "inertia": "min", "reliability": "max"}


def decisioni_alternate(base: float, ampiezza: float, anni: int = 100) -> list[float]:
    return [min(0.1, max(0.0, base + (ampiezza if t % 2 else -ampiezza))) for t in range(anni)]


def p_critico(b: float, q: float) -> float:
    f = lambda x: x ** q / (1 + x ** q) - b * x  # noqa: E731
    lo, hi = 0.01, 1.5
    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:
        raise ValueError("nessun cambio di segno per P critico")
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if flo * fm <= 0:
            hi = mid
        else:
            lo, flo = mid, fm
        if hi - lo < 1e-15:
            break
    return 0.5 * (lo + hi)


def lake_problem(b=0.42, q=2.0, mean=0.02, stdev=0.001, delta=0.98, alpha=0.4, n_samples=100,
                 rng: int | None = 42, decisions=None, backend: str = "auto"):
    if decisions is None:
        decisions = [0.0] * 100
    if backend == "auto":
        try:
            import numpy  # noqa: F401
            backend = "numpy"
        except ImportError:
            backend = "python"
    if backend == "numpy":
        return _lake_numpy(b, q, mean, stdev, delta, alpha, n_samples, rng, decisions)
    return _lake_python(b, q, mean, stdev, delta, alpha, n_samples, rng, decisions)


def _deterministici(decisions, alpha, delta):
    n = len(decisions)
    utility = math.fsum(alpha * d * delta ** t for t, d in enumerate(decisions))
    inertia = sum(1 for t in range(1, n) if abs(decisions[t] - decisions[t - 1]) > 0.02) / float(n - 1)
    return utility, inertia


def _lake_python(b, q, mean, stdev, delta, alpha, n_samples, rng, decisions):
    r = random.Random(rng)
    n = len(decisions)
    pcrit = p_critico(b, q)
    mu = math.log(mean ** 2 / math.sqrt(stdev ** 2 + mean ** 2))
    sigma = math.sqrt(math.log(1.0 + stdev ** 2 / mean ** 2))
    somma = [0.0] * n
    sotto = 0
    for _ in range(n_samples):
        x = 0.0
        sotto += 1 if pcrit > x else 0
        inflows = [r.lognormvariate(mu, sigma) for _ in range(n)]
        for t in range(1, n):
            xq = x ** q
            x = (1 - b) * x + xq / (1 + xq) + decisions[t - 1] + inflows[t - 1]
            somma[t] += x
            if pcrit > x:
                sotto += 1
    max_p = max(s / n_samples for s in somma)
    reliability = sotto / float(n_samples * n)
    utility, inertia = _deterministici(decisions, alpha, delta)
    return max_p, utility, inertia, reliability


def _lake_numpy(b, q, mean, stdev, delta, alpha, n_samples, rng, decisions):
    import numpy as np
    g = np.random.default_rng(rng)
    nvars = len(decisions)
    dec = np.array(decisions)
    pcrit = p_critico(b, q)
    inflows = g.lognormal(mean=math.log(mean ** 2 / math.sqrt(stdev ** 2 + mean ** 2)),
                          sigma=math.sqrt(math.log(1.0 + stdev ** 2 / mean ** 2)), size=(n_samples, nvars))
    X = np.zeros((n_samples, nvars))
    for t in range(1, nvars):
        X[:, t] = (1 - b) * X[:, t - 1] + (X[:, t - 1] ** q / (1 + X[:, t - 1] ** q)) + dec[t - 1] + inflows[:, t - 1]
    max_p = float(np.max(np.mean(X, axis=0)))
    reliability = float(np.sum(pcrit > X) / float(n_samples * nvars))
    utility = float(np.sum(alpha * dec * np.power(delta, np.arange(nvars))))
    inertia = float(np.sum(np.abs(np.diff(dec)) > 0.02) / float(nvars - 1))
    return max_p, utility, inertia, reliability
