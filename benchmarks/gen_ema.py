"""Genera i risultati di riferimento con EMA Workbench 3.0 (modello ufficiale lake_problem_intertemporal)."""
import json, sys, numpy as np, pandas as pd
sys.path.insert(0, sys.argv[1])  # cartella examples di EMA
from lake_models import lake_problem_intertemporal
from ema_workbench import Model, RealParameter, ScalarOutcome, Sample, SequentialEvaluator, save_results, __version__
from ema_workbench.em_framework.evaluators import Samplers

def lake_policy(b=0.42, q=2.0, mean=0.02, stdev=0.001, delta=0.98, base=0.03, ampiezza=0.0):
    dec = [min(0.1, max(0.0, base + (ampiezza if t % 2 else -ampiezza))) for t in range(100)]
    return lake_problem_intertemporal(b=b, q=q, mean=mean, stdev=stdev, delta=delta, decisions=dec)

m = Model("lake", function=lake_policy)
m.uncertainties = [RealParameter("b", 0.1, 0.45), RealParameter("q", 2.0, 4.5), RealParameter("mean", 0.01, 0.05),
                   RealParameter("stdev", 0.001, 0.005), RealParameter("delta", 0.93, 0.99)]
m.levers = [RealParameter("base", 0.0, 0.1), RealParameter("ampiezza", 0.0, 0.05)]
m.outcomes = [ScalarOutcome("max_p"), ScalarOutcome("utility"), ScalarOutcome("inertia"), ScalarOutcome("reliability")]
pols = [Sample("prudente", base=0.01, ampiezza=0.0), Sample("moderata", base=0.03, ampiezza=0.0),
        Sample("intensiva", base=0.05, ampiezza=0.0), Sample("molto_intensiva", base=0.08, ampiezza=0.0),
        Sample("alternata_bassa", base=0.02, ampiezza=0.015), Sample("alternata_media", base=0.04, ampiezza=0.015)]
with SequentialEvaluator(m) as ev:
    res = ev.perform_experiments(200, pols, uncertainty_sampling=Samplers.LHS, uncertainty_sampling_kwargs={"rng": 42})
save_results(res, sys.argv[2])
exp, out = res
print(exp.columns.tolist()); print(exp.head(3)); print({k: v[:3] for k, v in out.items()})
