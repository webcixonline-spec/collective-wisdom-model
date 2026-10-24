"""Modello educativo CWM (dalla 0.8): allocazione di 60 posti di tutoraggio.

Novità rispetto alla 0.7:
- cinque dimensioni (apprendimento, equità, accesso, lungo periodo, sostenibilità);
- rendimenti decrescenti (saturazione) ed effetti soglia (equità logistica, struttura "soglia");
- costi per posto incerti e diversi per gruppo, con vincolo di bilancio;
- griglia di 13 politiche (passo 5 posti) al posto di 3, filtrata da vincoli sui diritti.

TUTTI i valori numerici sono ipotesi illustrative salvo quanto tracciato nel registro delle prove.
"""
from __future__ import annotations

import math

from .stats import lhs

CRITERI = ("apprendimento", "equita", "accesso", "lungo_periodo", "sostenibilita")
POSTI_TOTALI = 60
BILANCIO_EUR = 36000.0

# Intervalli IPOTETICI. Con "intervalli": {"fonte": "registro"} nel piano di analisi valgono solo per i
# parametri senza stime nel registro delle prove; gli altri vengono da evidence.intervalli_da_registro.
INTERVALLI_TRAIN: dict[str, tuple[float, float]] = {
    "effetto": (0.10, 0.30),             # SD per studente; contesto: Carlana & La Ferrara 2025
    "moltiplicatore": (0.60, 1.30),      # efficacia relativa sugli svantaggiati (ipotesi)
    "saturazione": (0.00, 0.60),         # perdita di efficacia quando un gruppo occupa tutti i posti (ipotesi)
    "conversione_lp": (0.02, 0.10),      # riduzione abbandono per SD di apprendimento (ipotesi)
    "costo_svantaggiati": (600.0, 1100.0),  # EUR per posto (ipotesi, non verificata)
    "costo_altri": (400.0, 700.0),       # EUR per posto (ipotesi, non verificata)
}

# Limiti fisici per l'estrapolazione (holdout fuori intervallo).
LIMITI_ESTRAPOLAZIONE: dict[str, tuple[float, float]] = {
    "effetto": (0.02, 0.40),
    "moltiplicatore": (0.40, 1.60),
    "saturazione": (0.00, 0.85),
    "conversione_lp": (0.00, 0.14),
    "costo_svantaggiati": (450.0, 1350.0),
    "costo_altri": (300.0, 850.0),
}

# Costanti di normalizzazione fisse (non dipendono dai dati), dimensionate sul caso peggiore estrapolato.
_NORM_APPR = POSTI_TOTALI * 0.40 * 1.60
_NORM_LP = _NORM_APPR * 0.14
STRUTTURE = ("saturazione", "soglia")


def politiche(passo: int = 5) -> dict[str, dict[str, int]]:
    return {f"{d}/{POSTI_TOTALI - d}": {"svantaggiati": d, "altri": POSTI_TOTALI - d}
            for d in range(0, POSTI_TOTALI + 1, passo)}


def _fattore(n: int, sat: float, struttura: str) -> float:
    if struttura == "saturazione":
        # rendimenti decrescenti lineari nella dimensione del gruppo
        return 1.0 - sat * n / POSTI_TOTALI
    if struttura == "soglia":
        # efficacia piena fino a 20 studenti per gruppo, poi ridotta di (1 - sat) per i posti in eccesso
        if n <= 20:
            return 1.0
        return (20 + (n - 20) * (1.0 - sat)) / n
    raise ValueError(f"struttura sconosciuta: {struttura}")


def valuta(politica: dict[str, int], s: dict[str, float], struttura: str = "saturazione") -> dict[str, float]:
    d = politica["svantaggiati"]
    o = politica["altri"]
    e, m, sat = s["effetto"], s["moltiplicatore"], s["saturazione"]
    gain_d = d * e * m * _fattore(d, sat, struttura)
    gain_o = o * e * _fattore(o, sat, struttura)
    tot = gain_d + gain_o
    share_d = gain_d / tot if tot > 0 else 0.0
    costo = d * s["costo_svantaggiati"] + o * s["costo_altri"]
    sforamento = max(0.0, costo - BILANCIO_EUR) / BILANCIO_EUR
    return {
        "apprendimento": min(1.0, tot / _NORM_APPR),
        # effetto soglia (logistica): l'equità cresce rapidamente quando più di metà del guadagno va agli svantaggiati
        "equita": 1.0 / (1.0 + math.exp(-6.0 * (share_d - 0.5))),
        # ampiezza dell'accesso per chi non è nel gruppo prioritario, rendimenti decrescenti
        "accesso": math.sqrt(o / POSTI_TOTALI),
        "lungo_periodo": min(1.0, (gain_d * s["conversione_lp"] + gain_o * s["conversione_lp"] / 3.0) / _NORM_LP),
        "sostenibilita": max(0.0, 1.0 - 3.0 * sforamento),
    }


def utilita(dim: dict[str, float], pesi: dict[str, float]) -> float:
    return math.fsum(pesi[c] * dim[c] for c in CRITERI)


# Limiti fisici dei parametri: l'estrapolazione non può uscirne.
LIMITI_FISICI: dict[str, tuple[float, float]] = {
    "effetto": (0.0, math.inf),
    "moltiplicatore": (0.0, math.inf),
    "saturazione": (0.0, 0.95),
    "conversione_lp": (0.0, math.inf),
    "costo_svantaggiati": (0.0, math.inf),
    "costo_altri": (0.0, math.inf),
}


def limiti_estrapolazione(intervalli: dict[str, dict]) -> dict[str, tuple[float, float]]:
    """Per i parametri con intervallo ipotetico usa i limiti fissi; per quelli ricavati dalle fonti allarga
    l'intervallo di metà della sua ampiezza per lato (almeno il 25% del valore se l'ampiezza è nulla),
    entro i limiti fisici. Così l'holdout esce sempre dall'intervallo di train, qualunque sia la fonte."""
    out = {}
    for p, info in intervalli.items():
        lo, hi = info["intervallo"]
        if info["origine"] == "ipotesi":
            lim_lo, lim_hi = LIMITI_ESTRAPOLAZIONE[p]
            out[p] = (min(lim_lo, lo), max(lim_hi, hi))
            continue
        margine = (hi - lo) / 2 or 0.25 * max(abs(lo), abs(hi))
        f_lo, f_hi = LIMITI_FISICI[p]
        out[p] = (max(f_lo, lo - margine), min(f_hi, hi + margine))
    return out


def _tuple(intervalli: dict[str, dict] | None) -> dict[str, tuple[float, float]]:
    if intervalli is None:
        return INTERVALLI_TRAIN
    return {p: tuple(info["intervallo"]) for p, info in intervalli.items()}


def scenari_train(n: int, seme: int, intervalli: dict[str, dict] | None = None) -> list[dict[str, float]]:
    return lhs(_tuple(intervalli), n, seme)


def scenari_estrapolazione(n: int, seme: int, intervalli: dict[str, dict] | None = None) -> list[dict[str, float]]:
    """Scenari con almeno un parametro FUORI dagli intervalli di train (campionamento con rifiuto)."""
    train = _tuple(intervalli)
    limiti = LIMITI_ESTRAPOLAZIONE if intervalli is None else limiti_estrapolazione(intervalli)
    out: list[dict[str, float]] = []
    tentativo = 0
    while len(out) < n:
        for s in lhs(limiti, 4 * n, seme + 7919 * tentativo):
            fuori = any(not (train[k][0] <= v <= train[k][1]) for k, v in s.items())
            if fuori:
                out.append(s)
                if len(out) == n:
                    break
        tentativo += 1
    return out


def tabella_dimensioni(pol: dict[str, dict[str, int]], scen: list[dict[str, float]],
                       struttura: str = "saturazione") -> dict[str, list[dict[str, float]]]:
    return {p: [valuta(v, s, struttura) for s in scen] for p, v in pol.items()}


def tabella_utilita(dims: dict[str, list[dict[str, float]]], pesi: dict[str, float]) -> dict[str, list[float]]:
    return {p: [utilita(d, pesi) for d in righe] for p, righe in dims.items()}
