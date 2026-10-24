"""Governance dei pesi e vincoli sui diritti (dalla 1.1).

Separazione esplicita tra tre livelli normativi:
1. VINCOLI SUI DIRITTI: escludono politiche prima di ogni calcolo; nessun peso li può compensare.
2. PREFERENZE: pesi raccolti da partecipanti con confronti a coppie (AHP, Saaty), controllo di
   coerenza (CR <= 0,10) e aggregazione per media geometrica dei giudizi (AIJ, Forman & Peniwati 1998).
3. STABILITÀ: quanto la scelta dipende dai pesi — indici di accettabilità SMAA
   (Lahdelma, Hokkanen & Salminen 1998) e raggio di stabilità (minima variazione dei pesi che
   cambia la scelta, in distanza di variazione totale).
"""
from __future__ import annotations

import math
import operator
import random
from typing import Callable, Sequence

from .stats import dirichlet

# Indici di coerenza casuale di Saaty
RI = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}


# ----------------------------------------------------------------- vincoli sui diritti
OPERATORI = {">=": operator.ge, "<=": operator.le, "==": operator.eq}


def applica_vincoli(politiche: dict[str, dict], vincoli: list[dict]) -> tuple[dict[str, dict], dict[str, list[str]]]:
    for v in vincoli:
        if v.get("operatore") not in OPERATORI:
            raise ValueError(f"vincolo {v.get('id')}: operatore {v.get('operatore')!r} sconosciuto (ammessi: {', '.join(OPERATORI)})")
        if any(v.get("attributo") not in attr for attr in politiche.values()):
            raise ValueError(f"vincolo {v.get('id')}: attributo {v.get('attributo')!r} assente nelle politiche")
    ammesse, escluse = {}, {}
    for nome, attr in politiche.items():
        motivi = []
        for v in vincoli:
            ok = OPERATORI[v["operatore"]](attr[v["attributo"]], v["valore"])
            if not ok:
                motivi.append(f"{v['id']} ({v['tipo']}): {v['descrizione']}")
        if motivi:
            escluse[nome] = motivi
        else:
            ammesse[nome] = attr
    if not ammesse:
        raise ValueError("i vincoli escludono tutte le politiche")
    return ammesse, escluse


# ----------------------------------------------------------------- AHP
def matrice_da_giudizi(criteri: Sequence[str], giudizi: list[dict]) -> list[list[float]]:
    """giudizi: [{"a": criterio, "b": criterio, "valore": v}] con v>1 se a è più importante di b (scala 1/9..9)."""
    idx = {c: i for i, c in enumerate(criteri)}
    n = len(criteri)
    m = [[1.0] * n for _ in range(n)]
    visti = set()
    for g in giudizi:
        sconosciuti = [g.get(k) for k in ("a", "b") if g.get(k) not in idx]
        if sconosciuti:
            raise ValueError(f"giudizio su criteri sconosciuti {sconosciuti}: {g}")
        i, j, v = idx[g["a"]], idx[g["b"]], float(g["valore"])
        if i == j:
            raise ValueError(f"giudizio di un criterio con se stesso: {g}")
        if not (1 / 9 - 1e-9 <= v <= 9 + 1e-9):
            raise ValueError(f"giudizio fuori scala 1/9..9: {g}")
        coppia = frozenset((i, j))
        if coppia in visti:
            raise ValueError(f"confronto ripetuto tra {g['a']} e {g['b']}")
        m[i][j], m[j][i] = v, 1.0 / v
        visti.add(coppia)
    mancanti = n * (n - 1) // 2 - len(visti)
    if mancanti:
        raise ValueError(f"mancano {mancanti} confronti a coppie")
    return m


def autovettore(m: list[list[float]], iterazioni: int = 500) -> tuple[list[float], float]:
    n = len(m)
    w = [1.0 / n] * n
    lam = float(n)
    for _ in range(iterazioni):
        nw = [math.fsum(m[i][j] * w[j] for j in range(n)) for i in range(n)]
        s = math.fsum(nw)
        nw = [v / s for v in nw]
        if max(abs(a - b) for a, b in zip(nw, w)) < 1e-14:
            w = nw
            break
        w = nw
    mw = [math.fsum(m[i][j] * w[j] for j in range(n)) for i in range(n)]
    lam = math.fsum(mw[i] / w[i] for i in range(n)) / n
    return w, lam


def coerenza(m: list[list[float]]) -> float:
    n = len(m)
    if n not in RI:
        raise ValueError(f"indice di coerenza casuale non disponibile per {n} criteri (tabella di Saaty: 1..{max(RI)})")
    if n <= 2:
        return 0.0  # con due criteri una matrice reciproca è sempre coerente
    _, lam = autovettore(m)
    return (lam - n) / (n - 1) / RI[n]


def aggrega(criteri: Sequence[str], partecipanti: list[dict], soglia_cr: float = 0.10) -> dict:
    accettati, esclusi, individuali = [], [], {}
    ids = [p["id"] for p in partecipanti]
    doppi = sorted({i for i in ids if ids.count(i) > 1})
    if doppi:
        raise ValueError(f"identificativi di partecipanti ripetuti: {doppi}")
    for p in partecipanti:
        m = matrice_da_giudizi(criteri, p["giudizi"])
        cr = coerenza(m)
        w, _ = autovettore(m)
        individuali[p["id"]] = {"pesi": dict(zip(criteri, w)), "cr": cr, "coerente": cr <= soglia_cr}
        (accettati if cr <= soglia_cr else esclusi).append((p, m))
    if not accettati:
        raise ValueError("nessun partecipante con giudizi coerenti (CR <= soglia)")
    n = len(criteri)
    g = [[math.exp(math.fsum(math.log(m[i][j]) for _, m in accettati) / len(accettati)) for j in range(n)] for i in range(n)]
    w, _ = autovettore(g)
    pesi = dict(zip(criteri, w))
    dispersione = {c: {"min": min(individuali[p["id"]]["pesi"][c] for p, _ in accettati),
                       "max": max(individuali[p["id"]]["pesi"][c] for p, _ in accettati)} for c in criteri}
    return {"pesi_gruppo": pesi, "cr_gruppo": coerenza(g), "partecipanti_accettati": [p["id"] for p, _ in accettati],
            "partecipanti_esclusi": [{"id": p["id"], "cr": individuali[p["id"]]["cr"],
                                      "motivo": f"giudizi incoerenti (CR > {soglia_cr:.2f})"} for p, _ in esclusi],
            "individuali": individuali, "dispersione": dispersione}


# ----------------------------------------------------------------- stabilità
Scelta = Callable[[dict[str, float]], str]


def smaa(scegli: Scelta, criteri: Sequence[str], centro: dict[str, float] | None, campioni: int,
         seme: int, concentrazione: float = 20.0) -> dict:
    """Indici di accettabilità: frequenza con cui ogni politica è scelta al variare dei pesi.

    centro=None -> pesi uniformi sul simplesso (nessuna informazione sulle preferenze);
    altrimenti Dirichlet centrata sui pesi del gruppo con la concentrazione indicata.
    """
    rng = random.Random(seme)
    alpha = [1.0] * len(criteri) if centro is None else [max(1e-3, concentrazione * centro[c]) for c in criteri]
    conteggi: dict[str, int] = {}
    for _ in range(campioni):
        w = dict(zip(criteri, dirichlet(alpha, rng)))
        s = scegli(w)
        conteggi[s] = conteggi.get(s, 0) + 1
    return {p: c / campioni for p, c in sorted(conteggi.items(), key=lambda kv: -kv[1])}


def raggio_stabilita(scegli: Scelta, criteri: Sequence[str], pesi: dict[str, float], direzioni: int,
                     seme: int, passi: int = 10, bisezioni: int = 12) -> dict:
    """Minima distanza (variazione totale = ½·L1) dai pesi attuali a pesi che cambiano la scelta."""
    rng = random.Random(seme)
    base = scegli(pesi)
    w0 = [pesi[c] for c in criteri]
    migliore = {"distanza": math.inf, "pesi": None, "nuova_scelta": None}
    bersagli = [dirichlet([1.0] * len(criteri), rng) for _ in range(direzioni)]
    # aggiunge i vertici del simplesso: la direzione "tutto su un criterio"
    for k in range(len(criteri)):
        bersagli.append([1.0 if j == k else 0.0 for j in range(len(criteri))])
    for wt in bersagli:
        def punto(t: float) -> dict[str, float]:
            return {c: (1 - t) * a + t * b for c, a, b in zip(criteri, w0, wt)}
        t_prima = None
        for k in range(1, passi + 1):
            t = k / passi
            if scegli(punto(t)) != base:
                t_prima = t
                break
        if t_prima is None:
            continue
        lo, hi = t_prima - 1.0 / passi, t_prima
        for _ in range(bisezioni):
            mid = 0.5 * (lo + hi)
            if scegli(punto(mid)) != base:
                hi = mid
            else:
                lo = mid
        wp = punto(hi)
        dist = 0.5 * math.fsum(abs(wp[c] - pesi[c]) for c in criteri)
        if dist < migliore["distanza"]:
            migliore = {"distanza": dist, "pesi": wp, "nuova_scelta": scegli(wp)}
    migliore["scelta_attuale"] = base
    migliore["interpretazione"] = (
        "nessun cambio di scelta trovato nelle direzioni esplorate" if migliore["pesi"] is None else
        f"spostando il {100 * migliore['distanza']:.1f}% del peso totale la scelta passa a {migliore['nuova_scelta']}")
    return migliore
