"""Valori di riferimento calcolati in modo indipendente con EMA load_results + numpy/pandas."""
import json, sys, numpy as np, pandas as pd
from ema_workbench import load_results, __version__
exp, out = load_results(sys.argv[1])
DIR = {"max_p": "min", "utility": "max", "inertia": "min", "reliability": "max"}
PESI = {"max_p": 0.3, "utility": 0.3, "inertia": 0.1, "reliability": 0.3}
SOGLIE = {"reliability": [">=", 0.95], "utility": [">=", 0.1]}
df = exp[["scenario", "policy"]].copy().astype(str)
for k, v in out.items(): df[k] = v
pols = list(dict.fromkeys(df.policy)); scen = list(dict.fromkeys(df.scenario))
piv = {k: df.pivot(index="scenario", columns="policy", values=k).loc[scen, pols] for k in DIR}
ref = {"ema_workbench": __version__, "numpy": np.__version__, "direzioni": DIR, "pesi": PESI, "soglie": SOGLIE, "per_esito": {}}
for k, verso in DIR.items():
    t = piv[k]; s = t if verso == "max" else -t
    reg = s.max(axis=1).values[:, None] - s.values
    ref["per_esito"][k] = {p: {"media": float(t[p].mean()), "p10": float(np.quantile(t[p], .1)), "p90": float(np.quantile(t[p], .9)),
                               "rimpianto_medio": float(reg[:, j].mean()), "rimpianto_massimo": float(reg[:, j].max())} for j, p in enumerate(pols)}
ok = np.ones((len(scen), len(pols)), bool)
for k, (op, v) in SOGLIE.items(): ok &= (piv[k].values >= v) if op == ">=" else (piv[k].values <= v)
ref["quota_soddisfacente"] = {p: float(ok[:, j].mean()) for j, p in enumerate(pols)}
U = np.zeros((len(scen), len(pols)))
for k, verso in DIR.items():
    lo, hi = df[k].min(), df[k].max(); t = piv[k].values
    U += PESI[k] * (((t - lo) / (hi - lo)) if verso == "max" else ((hi - t) / (hi - lo))) if hi > lo else PESI[k]
U /= sum(PESI.values())
reg = U.max(axis=1)[:, None] - U
ref["composita"] = {p: {"punteggio_medio": float(U[:, j].mean()), "rimpianto_medio": float(reg[:, j].mean()),
                        "rimpianto_p90": float(np.quantile(reg[:, j], .9)), "rimpianto_massimo": float(reg[:, j].max())} for j, p in enumerate(pols)}
ref["scelta_minimax"] = pols[int(np.argmin(reg.max(axis=0)))]
json.dump(ref, open(sys.argv[2], "w"), indent=2)
print(ref["scelta_minimax"], {p: round(v["rimpianto_massimo"], 4) for p, v in ref["composita"].items()}, ref["quota_soddisfacente"])
