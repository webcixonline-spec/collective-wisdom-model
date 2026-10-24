"""Ponte con EMA Workbench (dalla 0.9).

Legge i file prodotti da `ema_workbench.save_results(...)` (tar.gz con experiments.csv,
<esito>.cls e metadata.json) SENZA richiedere EMA, numpy o pandas. Il CWM diventa così il
livello decisionale sopra al motore di esplorazione di EMA.
"""
from __future__ import annotations

import csv
import io
import json
import math
import tarfile
from dataclasses import dataclass, field
from typing import Any

from .robust import choose_minimax, regrets, summarize
from .stats import mean, quantile

_NUMERICI = {"float64", "float32", "int64", "int32", "float", "int"}


@dataclass
class RisultatiEMA:
    esperimenti: list[dict[str, Any]]
    esiti: dict[str, list[float]]
    metadata: dict = field(default_factory=dict)

    # --- struttura -------------------------------------------------------------------
    def politiche(self) -> list[str]:
        return list(dict.fromkeys(str(r["policy"]) for r in self.esperimenti))

    def scenari(self) -> list[str]:
        return list(dict.fromkeys(str(r["scenario"]) for r in self.esperimenti))

    def colonne_numeriche(self) -> list[str]:
        tipi = self.metadata.get("experiments", {})
        return [c for c, t in tipi.items() if t in _NUMERICI]

    def leve(self) -> list[str]:
        """Colonne numeriche costanti all'interno di ogni politica."""
        out = []
        for c in self.colonne_numeriche():
            per_pol: dict[str, set] = {}
            for r in self.esperimenti:
                per_pol.setdefault(str(r["policy"]), set()).add(r[c])
            if all(len(v) == 1 for v in per_pol.values()):
                out.append(c)
        return out

    def incertezze(self) -> list[str]:
        leve = set(self.leve())
        return [c for c in self.colonne_numeriche() if c not in leve]

    def _indice(self) -> dict[tuple[str, str], int]:
        return {(str(r["policy"]), str(r["scenario"])): i for i, r in enumerate(self.esperimenti)}

    def pivot(self, esito: str) -> dict[str, list[float]]:
        idx = self._indice()
        sc = self.scenari()
        return {p: [self.esiti[esito][idx[(p, s)]] for s in sc] for p in self.politiche()}

    def parametri_scenari(self) -> list[dict[str, float]]:
        primo: dict[str, dict] = {}
        for r in self.esperimenti:
            primo.setdefault(str(r["scenario"]), r)
        return [{k: primo[s][k] for k in self.incertezze()} for s in self.scenari()]


def _converti(valore: str, tipo: str) -> Any:
    if tipo in _NUMERICI:
        return float(valore)
    return valore


def carica_risultati(percorso: str) -> RisultatiEMA:
    with tarfile.open(percorso, "r:gz") as tar:
        meta = json.loads(tar.extractfile("metadata.json").read().decode("utf-8"))
        tipi = meta.get("experiments", {})
        testo = tar.extractfile("experiments.csv").read().decode("utf-8")
        righe = list(csv.DictReader(io.StringIO(testo)))
        esperimenti = [{k: _converti(v, tipi.get(k, "object")) for k, v in r.items()} for r in righe]
        esiti: dict[str, list[float]] = {}
        for classe, nome, filename in meta["outcomes"]:
            if classe != "ScalarOutcome":
                raise NotImplementedError(f"esito {nome}: solo ScalarOutcome è supportato ({classe})")
            dati = tar.extractfile(filename).read().decode("utf-8").split()
            esiti[nome] = [float(x) for x in dati]
            if len(esiti[nome]) != len(esperimenti):
                raise ValueError(f"esito {nome}: {len(esiti[nome])} valori per {len(esperimenti)} esperimenti")
    return RisultatiEMA(esperimenti, esiti, meta)


def utilita_composita(ris: RisultatiEMA, direzioni: dict[str, str], pesi: dict[str, float]) -> dict[str, list[float]]:
    """Normalizzazione min-max di ogni esito su tutti gli esperimenti (1 = meglio), somma pesata."""
    somma_pesi = math.fsum(pesi.values())
    norm: dict[str, dict[str, list[float]]] = {}
    for esito, verso in direzioni.items():
        vals = ris.esiti[esito]
        lo, hi = min(vals), max(vals)
        span = hi - lo
        tab = ris.pivot(esito)
        norm[esito] = {p: [((v - lo) / span if span else 1.0) if verso == "max" else ((hi - v) / span if span else 1.0)
                           for v in righe] for p, righe in tab.items()}
    return {p: [math.fsum(pesi[e] * norm[e][p][i] for e in direzioni) / somma_pesi
                for i in range(len(ris.scenari()))] for p in ris.politiche()}


def analizza(ris: RisultatiEMA, direzioni: dict[str, str], pesi: dict[str, float],
             soglie: dict[str, tuple[str, float]] | None = None) -> dict:
    """Metriche di robustezza per esito e per utilità composita, più quota di scenari soddisfacenti."""
    soglie = soglie or {}
    per_esito = {}
    for esito, verso in direzioni.items():
        tab = ris.pivot(esito)
        segno = 1.0 if verso == "max" else -1.0
        reg = regrets({p: [segno * v for v in r] for p, r in tab.items()})
        per_esito[esito] = {p: {"media": mean(tab[p]), "p10": quantile(tab[p], 0.1), "p90": quantile(tab[p], 0.9),
                                "rimpianto_medio": mean(reg[p]), "rimpianto_massimo": max(reg[p])} for p in tab}
    soddisf = {}
    if soglie:
        tabs = {e: ris.pivot(e) for e in soglie}
        n = len(ris.scenari())
        for p in ris.politiche():
            ok = 0
            for i in range(n):
                if all((tabs[e][p][i] >= v) if op == ">=" else (tabs[e][p][i] <= v) for e, (op, v) in soglie.items()):
                    ok += 1
            soddisf[p] = ok / n
    utils = utilita_composita(ris, direzioni, pesi)
    metr = summarize(utils)
    return {"per_esito": per_esito, "quota_soddisfacente": soddisf, "composita": metr,
            "scelta_minimax": choose_minimax(metr), "utils": utils}
