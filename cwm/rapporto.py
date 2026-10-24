"""Scrittura degli esiti: JSON completo, CSV e rapporto leggibile in Markdown."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .audit import pulisci


def _f(x, n=4):
    return "—" if x is None else (f"{x:.{n}f}" if isinstance(x, float) else str(x))


def scrivi(risultato: dict, controlli: dict, cartella: Path) -> list[Path]:
    cartella.mkdir(parents=True, exist_ok=True)
    scritti = []
    p = cartella / "risultati.json"
    p.write_text(json.dumps(pulisci({**risultato, "controlli_uso": controlli}), ensure_ascii=False, indent=2), encoding="utf-8")
    scritti.append(p)

    p = cartella / "politiche.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["politica", "punteggio_medio", "punteggio_p10", "rimpianto_medio", "rimpianto_p90", "rimpianto_massimo", "vittorie_uniche"])
        for pol, m in risultato["metriche_train"].items():
            w.writerow([pol] + [round(m[k], 6) for k in ("punteggio_medio", "punteggio_p10", "rimpianto_medio", "rimpianto_p90", "rimpianto_massimo")] + [m["vittorie_uniche"]])
    scritti.append(p)

    p = cartella / "validazione.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["holdout", "scenari", "scelta_train", "scelta_ottimale_holdout", "rimpianto_max_scelta_train", "rimpianto_max_ottimale", "scarto", "tolleranza", "tau_kendall", "esito"])
        for v in risultato["validazione"]:
            w.writerow([v["holdout"], v["scenari"], risultato["scelta_minimax"], v["scelta_ottimale_holdout"], round(v["rimpianto_massimo_scelta_train"], 6),
                        round(v["rimpianto_massimo_ottimale"], 6), round(v["scarto"], 6), v["tolleranza"], round(v["tau_kendall_classifiche"], 3), v["esito"]])
    scritti.append(p)

    p = cartella / "valore_informazione.csv"
    voi = risultato["valore_informazione"]
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["parametro", "evppi", "voi_r", "quota_rimpianto_ridotta", "la_scelta_cambierebbe"])
        for par, v in voi["per_parametro"].items():
            w.writerow([par, round(v["evppi"], 7), round(v["voi_r"], 7), round(v["quota_ridotta"], 4), v["la_scelta_cambierebbe"]])
    scritti.append(p)

    p = cartella / "rapporto.md"
    p.write_text(markdown(risultato, controlli), encoding="utf-8")
    scritti.append(p)
    return scritti


def markdown(r: dict, controlli: dict) -> str:
    g = r["cancello_prove"]
    L = [f"# CWM {r['versione']} — rapporto di analisi", "",
         f"**Sintesi.** {r['sintesi']}", "",
         "> Prototipo di ricerca. Tutti i parametri tranne l'effetto medio del tutoraggio sono ipotesi illustrative.", ""]
    L += ["## Controlli d'uso", ""]
    L += [f"- Uso consentito: **{'sì' if controlli['consentito'] else 'no'}**"]
    L += [f"- BLOCCO: {b}" for b in controlli["blocchi"]]
    L += [f"- Avviso: {a}" for a in controlli["avvisi"]]
    L += ["", "## Vincoli sui diritti", ""]
    for v in r["vincoli"]["definizioni"]:
        L.append(f"- **{v['id']}** ({v['tipo']}): {v['descrizione']} — {v['fondamento']}. _{v['stato_validazione']}_")
    for pol, mot in r["vincoli"]["escluse"].items():
        L.append(f"  - esclusa {pol}: {'; '.join(mot)}")
    L += ["", "## Pesi", "", f"Fonte: {r['fonte_pesi']}.", "", "| criterio | peso |", "|---|---|"]
    L += [f"| {c} | {_f(r['pesi'][c], 3)} |" for c in r["criteri"]]
    if r.get("elicitazione"):
        e = r["elicitazione"]
        L += ["", f"Partecipanti accettati: {', '.join(e['partecipanti_accettati'])}. CR di gruppo {_f(e['cr_gruppo'], 3)}."]
        L += [f"- escluso {x['id']}: {x['motivo']} (CR {_f(x['cr'], 2)})" for x in e["partecipanti_esclusi"]]
    if r.get("intervalli"):
        L += ["", "## Intervalli di incertezza e loro provenienza", "", "| parametro | intervallo | origine | fonti |", "|---|---|---|---|"]
        for p, iv in r["intervalli"].items():
            origine = "fonti" if iv["origine"] == "fonti" else "**ipotesi** (nessuna stima nel registro)"
            L.append(f"| {p} | {iv['intervallo'][0]:g} – {iv['intervallo'][1]:g} | {origine} | {', '.join(iv['fonti']) or '—'} |")
    L += ["", f"## Robustezza ({r['scenari_train']} scenari di train)", "",
          "| politica | punteggio medio | rimpianto medio | rimpianto massimo | vittorie |", "|---|---|---|---|---|"]
    for p, m in r["metriche_train"].items():
        segno = " ◀ minimax" if p == r["scelta_minimax"] else (" ◀ utilità media" if p == r["scelta_utilita_media"] else "")
        L.append(f"| {p}{segno} | {_f(m['punteggio_medio'])} | {_f(m['rimpianto_medio'])} | {_f(m['rimpianto_massimo'])} | {m['vittorie_uniche']} |")
    L += ["", "Strategie a confronto (una riga per politica, senza duplicati):", ""]
    L += [f"- {c['politica']}: {', '.join(c['strategie'])}" for c in r["confronto_strategie"]]
    L += [f"- {k}: non ammessa ({v['politica']})" for k, v in r["strategie_non_ammesse"].items()]
    L += ["", "## Validazione su holdout", "", "| holdout | scelta ottimale | scarto | tolleranza | esito |", "|---|---|---|---|---|"]
    L += [f"| {v['holdout']} ({v['descrizione']}) | {v['scelta_ottimale_holdout']} | {_f(v['scarto'])} | {v['tolleranza']} | **{v['esito']}** |" for v in r["validazione"]]
    L += ["", f"## Cancello sulle prove — obiettivo `{g['obiettivo']}`: **{g['verdetto']}**", "",
          "| parametro | livello | minimo | stato |", "|---|---|---|---|"]
    L += [f"| {d['parametro']} | {d['nome_livello']} | {d['minimo']} | {d['stato']} |" for d in g["dettagli"]]
    L += ["", "Verdetti per tutti gli obiettivi: " + ", ".join(f"{o} → {v}" for o, v in r["verdetti_per_obiettivo"].items())]
    voi = r["valore_informazione"]
    L += ["", f"## Valore dell'informazione ({voi.get('scenari', '?')} scenari)", "", f"EVPI: {_f(voi['evpi'], 5)} unità di utilità.", "",
          "| parametro | EVPPI (utilità attesa) | VOI-R (rimpianto massimo) | riduzione | la scelta cambierebbe |", "|---|---|---|---|---|"]
    for p, v in voi["per_parametro"].items():
        L.append(f"| {p} | {_f(v['evppi'], 5)} | {_f(v['voi_r'], 5)} | {100 * v['quota_ridotta']:.0f}% | {'sì' if v['la_scelta_cambierebbe'] else 'no'} |")
    L += ["", f"Priorità di ricerca per chi decide a utilità attesa: {', '.join(voi['priorita_ricerca_utilita_attesa'][:3])}.",
          f"Priorità di ricerca per chi decide in modo robusto: {', '.join(voi['priorita_ricerca_robusta'][:3])}."]
    for s in voi.get("studi", []):
        L.append(f"- **{s['studio']}**: dimensione consigliata {s['dimensione_consigliata'] or 'nessuna'} {s['unita']}. {s['nota']}")
    if r["cosa_cambierebbe_il_verdetto"]:
        L += ["", "Cosa servirebbe per superare il cancello (ordinato per VOI-R):", ""]
        L += [f"- {c['parametro']} (prova {c['livello_attuale']}; VOI-R {_f(c['voi_r'], 5)})" for c in r["cosa_cambierebbe_il_verdetto"]]
    st = r.get("stabilita_pesi")
    if st:
        L += ["", "## Stabilità rispetto ai pesi", "",
              "Accettabilità SMAA attorno ai pesi del gruppo: " + ", ".join(f"{p} {100 * v:.0f}%" for p, v in st["smaa_attorno_ai_pesi"].items()),
              "", "Accettabilità SMAA a pesi ignoti: " + ", ".join(f"{p} {100 * v:.0f}%" for p, v in st["smaa_pesi_ignoti"].items()),
              "", f"Raggio di stabilità: {st['raggio']['interpretazione']}."]
    L += ["", "## Limiti", ""] + [f"- {x}" for x in r["limiti"]]
    return "\n".join(L) + "\n"
