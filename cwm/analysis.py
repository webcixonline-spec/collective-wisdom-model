"""Pipeline completa CWM 1.2: diritti -> pesi -> robustezza -> validazione -> prove -> VOI -> stabilità."""
from __future__ import annotations

import math
from pathlib import Path

from . import education as edu
from .evidence import cancello, carica_json, intervalli_da_registro, obiettivi_superati
from .robust import choose_mean, choose_minimax, summarize
from .stats import kendall_tau
from .voi import analisi_completa, stima_studi
from .weights import aggrega, applica_vincoli, raggio_stabilita, smaa

BASE = Path(__file__).resolve().parent.parent
CONFIG = BASE / "config"


def carica_pacchetto(cartella: Path | str = CONFIG) -> dict:
    c = Path(cartella)
    cfg = carica_json(c / "analisi.json")
    pac = {
        "analisi": cfg,
        "registro": carica_json(c / "registro_prove.json"),
        "requisiti": carica_json(c / "requisiti_prove.json"),
        "vincoli": carica_json(c / "vincoli_diritti.json"),
    }
    if cfg["pesi"]["fonte"] == "elicitazione":
        pac["partecipanti"] = carica_json(c / cfg["pesi"]["file"])
    return pac


def normalizza_pesi(pesi: object) -> dict[str, float]:
    """Valida e normalizza i pesi: esattamente i criteri del modello, numeri finiti, non negativi, somma positiva."""
    if not isinstance(pesi, dict):
        raise ValueError("i pesi devono essere un oggetto {criterio: valore}")
    attesi = set(edu.CRITERI)
    if set(pesi) != attesi:
        mancanti, extra = sorted(attesi - set(pesi)), sorted(set(pesi) - attesi)
        raise ValueError(f"pesi non validi: mancano {mancanti or 'nessuno'}, sconosciuti {extra or 'nessuno'}")
    w = {}
    for c in edu.CRITERI:
        v = pesi[c]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            raise ValueError(f"peso di '{c}' non valido: {v!r} (serve un numero finito >= 0)")
        w[c] = float(v)
    s = math.fsum(w.values())
    if s <= 0:
        raise ValueError("la somma dei pesi deve essere positiva")
    return {c: v / s for c, v in w.items()}


def pesi_da_pacchetto(pac: dict) -> tuple[dict[str, float], dict | None]:
    cfg = pac["analisi"]["pesi"]
    if cfg["fonte"] == "espliciti":
        return normalizza_pesi(cfg["valori"]), None
    if cfg["fonte"] != "elicitazione":
        raise ValueError(f"fonte dei pesi sconosciuta: {cfg['fonte']!r} (ammesse: espliciti, elicitazione)")
    agg = aggrega(edu.CRITERI, pac["partecipanti"]["partecipanti"], cfg.get("soglia_coerenza", 0.10))
    return agg["pesi_gruppo"], agg


def intervalli_effettivi(pac: dict) -> dict[str, dict]:
    """Intervalli di incertezza dell'analisi, con provenienza. Le analisi registrate prima della 1.2.1 non hanno
    la chiave 'intervalli' e usavano solo le ipotesi: per riprodurle, l'assenza vale 'ipotesi'."""
    fonte = pac["analisi"].get("intervalli", {"fonte": "ipotesi"})["fonte"]
    ipotesi = edu.INTERVALLI_TRAIN
    if fonte == "registro":
        return intervalli_da_registro(pac["registro"], ipotesi)
    if fonte == "ipotesi":
        return {p: {"intervallo": list(iv), "origine": "ipotesi", "fonti": [], "fonti_escluse": []} for p, iv in ipotesi.items()}
    raise ValueError(f"fonte degli intervalli sconosciuta: {fonte!r} (ammesse: registro, ipotesi)")


class Valutatore:
    """Tiene in memoria le dimensioni per scenario e calcola rapidamente scelte al variare dei pesi."""

    def __init__(self, politiche: dict[str, dict], scenari: list[dict], struttura: str = "saturazione"):
        self.politiche = politiche
        self.scenari = scenari
        self.dims = edu.tabella_dimensioni(politiche, scenari, struttura)
        self._vett = {p: [[d[c] for c in edu.CRITERI] for d in righe] for p, righe in self.dims.items()}

    def utils(self, pesi: dict[str, float]) -> dict[str, list[float]]:
        w = [pesi[c] for c in edu.CRITERI]
        return {p: [math.fsum(a * b for a, b in zip(w, v)) for v in righe] for p, righe in self._vett.items()}

    def scelta(self, pesi: dict[str, float]) -> str:
        return choose_minimax(summarize(self.utils(pesi)))


def _validazione(nome: str, descr: str, val: Valutatore, pesi: dict, scelta_train: str, metr_train: dict, tol: float) -> dict:
    m = summarize(val.utils(pesi))
    oracolo = choose_minimax(m)
    gap = m[scelta_train]["rimpianto_massimo"] - m[oracolo]["rimpianto_massimo"]
    ordine = sorted(m, key=lambda p: (m[p]["rimpianto_massimo"], p))
    pol = sorted(m)
    tau = kendall_tau([metr_train[p]["rimpianto_massimo"] for p in pol], [m[p]["rimpianto_massimo"] for p in pol])
    return {"holdout": nome, "descrizione": descr, "scenari": len(val.scenari), "scelta_ottimale_holdout": oracolo,
            "rimpianto_massimo_scelta_train": m[scelta_train]["rimpianto_massimo"],
            "rimpianto_massimo_ottimale": m[oracolo]["rimpianto_massimo"], "scarto": gap,
            "posizione_scelta_train": ordine.index(scelta_train) + 1, "politiche": len(m),
            "tau_kendall_classifiche": tau, "tolleranza": tol,
            "esito": "SUPERATO" if gap <= tol + 1e-12 else "NON_SUPERATO", "metriche": m}


def esegui(pac: dict, pesi: dict[str, float] | None = None, obiettivo: str | None = None,
           con_studi: bool = True, con_stabilita: bool = True) -> dict:
    cfg = pac["analisi"]
    semi, ns = cfg["semi"], cfg["scenari"]
    obiettivo = obiettivo or cfg["obiettivo"]

    # 1. diritti
    tutte = edu.politiche(cfg.get("passo_politiche", 5))
    ammesse, escluse = applica_vincoli(tutte, pac["vincoli"]["vincoli"])

    # 2. pesi (fatti e valori separati: i pesi non sono uno scenario di incertezza)
    elicitazione = None
    if pesi is None:
        pesi, elicitazione = pesi_da_pacchetto(pac)
        fonte_pesi = cfg["pesi"]["fonte"]
    else:
        pesi = normalizza_pesi(pesi)
        fonte_pesi = "forniti_dall_utente"

    # 3. robustezza sul train, con intervalli ricavati dalle fonti dove esistono
    intervalli = intervalli_effettivi(pac)
    train = Valutatore(ammesse, edu.scenari_train(ns["train"], semi["train"], intervalli))
    u_train = train.utils(pesi)
    metr = summarize(u_train)
    scelta = choose_minimax(metr)
    scelta_media = choose_mean(metr)

    # 4. confronti con le baseline, senza righe duplicate
    strategie = {"CWM minimax regret": scelta, "Massima utilità media": scelta_media,
                 "Ripartizione paritaria": "30/30", "Priorità forte": "45/15", "Tutto agli svantaggiati": "60/0"}
    per_pol: dict[str, list[str]] = {}
    non_ammesse = {}
    for etichetta, p in strategie.items():
        if p in ammesse:
            per_pol.setdefault(p, []).append(etichetta)
        else:
            non_ammesse[etichetta] = {"politica": p, "motivi": escluse.get(p, ["non nella griglia"])}
    confronto = [{"politica": p, "strategie": et, **{k: metr[p][k] for k in ("punteggio_medio", "rimpianto_medio", "rimpianto_massimo")}}
                 for p, et in per_pol.items()]

    # 5. validazione su holdout che possono fallire
    tol = cfg["validazione"]["tolleranza_trasferimento"]
    hold_e = Valutatore(ammesse, edu.scenari_estrapolazione(ns["estrapolazione"], semi["estrapolazione"], intervalli))
    hold_s = Valutatore(ammesse, edu.scenari_train(ns["strutturale"], semi["strutturale"], intervalli), struttura="soglia")
    validazione = [
        _validazione("estrapolazione", "almeno un parametro fuori dagli intervalli di train", hold_e, pesi, scelta, metr, tol),
        _validazione("strutturale", "struttura del modello diversa (soglia per dimensione del gruppo)", hold_s, pesi, scelta, metr, tol),
    ]

    # 6. cancello sulle prove
    parametri = sorted(edu.INTERVALLI_TRAIN)
    gate = cancello(pac["registro"], pac["requisiti"], obiettivo, parametri)
    per_obiettivo = obiettivi_superati(pac["registro"], pac["requisiti"], parametri)

    # 7. valore dell'informazione, su un campione più ampio dedicato (riduce la distorsione delle regressioni)
    campione_voi = Valutatore(ammesse, edu.scenari_train(ns["voi"], semi["voi"], intervalli))
    u_voi = campione_voi.utils(pesi)
    voi = analisi_completa(u_voi, campione_voi.scenari, parametri)
    voi["scenari"] = len(campione_voi.scenari)
    vcfg = cfg["valore_informazione"]
    if con_studi:
        voi["studi"] = stima_studi(u_voi, campione_voi.scenari, vcfg["studi"], vcfg.get("euro_per_unita_utilita"),
                                   vcfg["decisioni_interessate"], semi["voi"])
    mancanti = [d["parametro"] for d in gate["dettagli"] if d["stato"] != "sufficiente"]
    cosa_cambierebbe = [{"parametro": p, "livello_attuale": gate["livelli_parametri"][p]["nome_livello"],
                         "evppi": voi["per_parametro"][p]["evppi"], "voi_r": voi["per_parametro"][p]["voi_r"],
                         "la_scelta_cambierebbe": voi["per_parametro"][p]["la_scelta_cambierebbe"]}
                        for p in sorted(mancanti, key=lambda q: -voi["per_parametro"][q]["voi_r"])]

    # 8. stabilità rispetto ai pesi
    stabilita = None
    if con_stabilita:
        scfg = cfg["stabilita"]
        stabilita = {
            "smaa_attorno_ai_pesi": smaa(train.scelta, edu.CRITERI, pesi, scfg["campioni_smaa"], semi["stabilita"], scfg["concentrazione"]),
            "smaa_pesi_ignoti": smaa(train.scelta, edu.CRITERI, None, scfg["campioni_smaa"], semi["stabilita"] + 1),
            "raggio": raggio_stabilita(train.scelta, edu.CRITERI, pesi, scfg["direzioni_raggio"], semi["stabilita"] + 2),
        }

    # 9. sintesi
    if gate["verdetto"] == "ABSTAIN":
        sintesi = (f"ASTENSIONE per l'obiettivo '{obiettivo}'. La scelta robusta nel modello sarebbe {scelta}, "
                   f"ma le prove non bastano. Obiettivi oggi consentiti: "
                   f"{', '.join(o for o, v in per_obiettivo.items() if v != 'ABSTAIN') or 'nessuno'}.")
    else:
        riserva = " (con riserva)" if gate["verdetto"] == "PASS_CON_RISERVA" else ""
        sintesi = f"Scelta robusta {scelta} consentita{riserva} SOLO per l'obiettivo '{obiettivo}'."
    falliti = [v["holdout"] for v in validazione if v["esito"] != "SUPERATO"]
    if falliti:
        sintesi += f" Attenzione: la scelta non supera gli holdout: {', '.join(falliti)}."

    risultato = {
        "versione": "1.2",
        "sintesi": sintesi,
        "obiettivo": obiettivo,
        "criteri": list(edu.CRITERI),
        "pesi": pesi, "fonte_pesi": fonte_pesi, "elicitazione": elicitazione,
        "vincoli": {"ammesse": list(ammesse), "escluse": escluse, "definizioni": pac["vincoli"]["vincoli"]},
        "scenari_train": len(train.scenari),
        "metriche_train": metr,
        "scelta_minimax": scelta, "scelta_utilita_media": scelta_media,
        "confronto_strategie": confronto, "strategie_non_ammesse": non_ammesse,
        "validazione": validazione,
        "cancello_prove": gate, "verdetti_per_obiettivo": per_obiettivo,
        "valore_informazione": voi, "cosa_cambierebbe_il_verdetto": cosa_cambierebbe,
        "stabilita_pesi": stabilita,
        "limiti": [
            "Tutti i parametri tranne l'effetto medio sono ipotesi illustrative (vedi registro delle prove).",
            "I partecipanti dell'esempio di elicitazione sono inventati.",
            "Gli holdout sono sintetici: verificano robustezza a estrapolazione e struttura, non sostituiscono dati reali.",
            "Il valore in euro dell'informazione dipende da lambda, che è una scelta del decisore.",
        ],
    }
    if "intervalli" in cfg:  # i piani precedenti alla 1.2.1 non la producevano: senza, i loro hash restano riproducibili
        risultato["intervalli"] = intervalli
        ipotetici = [p for p, iv in intervalli.items() if iv["origine"] == "ipotesi"]
        risultato["limiti"][0] = (f"Intervalli ricavati dalle fonti per {', '.join(p for p in intervalli if p not in ipotetici)}; "
                                  f"ancora ipotetici per {', '.join(ipotetici) or 'nessuno'} (vedi registro delle prove).")
        if elicitazione is not None and (pac.get("partecipanti") or {}).get("natura") == "reale":
            risultato["limiti"][1] = "Preferenze raccolte da persone reali: rappresentatività e protocollo nel file dei partecipanti."
    return risultato


def opzioni_esecuzione(obiettivo: str, pesi: dict[str, float] | None, con_studi: bool, con_stabilita: bool) -> dict:
    """Tutti gli argomenti di `esegui` oltre al pacchetto: vanno salvati nel registro per poter riprodurre l'analisi."""
    return {"obiettivo": obiettivo, "pesi": pesi, "con_studi": con_studi, "con_stabilita": con_stabilita}


def riesegui(pac: dict, opzioni: dict) -> dict:
    """Riesegue un'analisi registrata. Le voci precedenti salvavano solo `rapido` (studi e stabilità insieme)."""
    rapido = bool(opzioni.get("rapido", False))
    return esegui(pac, pesi=opzioni.get("pesi"), obiettivo=opzioni.get("obiettivo"),
                  con_studi=opzioni.get("con_studi", not rapido), con_stabilita=opzioni.get("con_stabilita", not rapido))
