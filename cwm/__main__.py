"""Interfaccia a riga di comando: python -m cwm <comando>."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import analysis
from .audit import FORMATO_HASH_ESITI, Registro, carica_json_rigoroso, hash_esiti, pulisci, sha256, piano
from .rapporto import scrivi

BASE = Path(__file__).resolve().parent.parent


def _analizza(args) -> int:
    pac = analysis.carica_pacchetto(args.config)
    reg = Registro(args.audit)
    opzioni = analysis.opzioni_esecuzione(args.obiettivo, None, con_studi=not args.rapido, con_stabilita=not args.rapido)
    ris = analysis.riesegui(pac, opzioni)
    controlli = reg.controlli_uso(pac, ris)
    voce = reg.aggiungi("ANALISI", {"hash_piano": sha256(piano(pac)), "input": pac, "opzioni": opzioni,
                                    "hash_esiti": hash_esiti(ris), "formato_hash_esiti": FORMATO_HASH_ESITI,
                                    "sintesi": ris["sintesi"], "controlli": controlli})
    file = scrivi(ris, controlli, Path(args.uscita))
    print(ris["sintesi"])
    for b in controlli["blocchi"]:
        print("BLOCCO:", b)
    for a in controlli["avvisi"]:
        print("Avviso:", a)
    print(f"Registro di audit: voce {voce['seq']} ({voce['hash'][:12]}…)")
    print("File:", ", ".join(str(f) for f in file))
    return 0


def _preregistra(args) -> int:
    pac = analysis.carica_pacchetto(args.config)
    v = Registro(args.audit).preregistra(pac)
    print(f"Piano congelato: hash {v['contenuto']['hash_piano'][:16]}… (voce {v['seq']}, {v['istante']})")
    return 0


def _verifica(args) -> int:
    reg = Registro(args.audit)
    cp = None
    if args.checkpoint:
        cp = Registro.valida_checkpoint(carica_json_rigoroso(Path(args.checkpoint).read_text(encoding="utf-8")))
    cat = reg.verifica_catena(cp)
    print(f"Catena: {'INTEGRA' if cat['integro'] else 'COMPROMESSA'} ({cat['voci']} voci)")
    for e in cat["errori"]:
        print("  -", e)
    if cat["checkpoint"]:
        print(f"Checkpoint: le prime {cat['checkpoint']['voci_attestate']} voci corrispondono; "
              f"{cat['checkpoint']['voci_successive']} aggiunte dopo")
    elif cp is None and cat["integro"]:
        print("Nessun checkpoint esterno fornito: troncamenti e riscritture con la chiave non sono rilevabili (--checkpoint).")
    if not cat["integro"]:
        return 1
    if cat["voci"] == 0:
        print("Registro vuoto: nulla da verificare.")
        return 1
    ultima = reg.ultima("ANALISI")
    ok_rip = True
    if ultima:
        c = ultima["contenuto"]
        ris = analysis.riesegui(c["input"], c["opzioni"])
        ok_rip = hash_esiti(ris, c.get("formato_hash_esiti", 1)) == c["hash_esiti"]
        print(f"Riproducibilità dell'analisi {ultima['seq']}: {'RIPRODOTTA' if ok_rip else 'NON RIPRODOTTA'}")
    else:
        print("Nessuna analisi registrata: verificata solo la catena.")
    return 0 if cat["integro"] and ok_rip else 1


def _checkpoint(args) -> int:
    out = Path(args.out)
    if out.exists():
        print(f"{out} esiste già: un checkpoint non si sovrascrive.", file=sys.stderr)
        return 1
    cp = Registro(args.audit).checkpoint()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as f:
        f.write(json.dumps(cp, ensure_ascii=False, indent=2) + "\n")
    print(f"Checkpoint: {cp['voci']} voci, ultimo hash {cp['ultimo_hash']}")
    print(f"  -> {out}")
    print("Conservarlo FUORI da questa cartella (verbale, repository pubblico, email a terzi) e verificare con:")
    print(f"  python3 -m cwm verifica --checkpoint {out}")
    return 0


def _scrivi_nuovo(percorso: str, testo: str) -> Path | None:
    out = Path(percorso)
    if out.exists():
        print(f"{out} esiste già: non lo sovrascrivo.", file=sys.stderr)
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as f:
        f.write(testo)
    return out


def _costi(args) -> int:
    from . import costi
    righe = costi.leggi(args.file)
    for p, s in costi.riepilogo(righe).items():
        print(f"{p}: {s['righe']} documenti da {s['istituti']} istituti — minimo {s['minimo']:.0f} €, "
              f"mediana {s['mediana']:.0f} €, massimo {s['massimo']:.0f} € per posto")
        if s["istituti"] < costi.MIN_ISTITUTI:
            print(f"  Avviso: meno di {costi.MIN_ISTITUTI} istituti, l'intervallo non rappresenta la variabilità tra istituti.")
    if args.out:
        prop = costi.proposta_fonte(righe, args.id)
        out = _scrivi_nuovo(args.out, json.dumps(prop, ensure_ascii=False, indent=2) + "\n")
        if out is None:
            return 1
        print(f"Proposta di fonte -> {out}")
        print("Rileggerla e incollarla in config/registro_prove.json: il registro non viene modificato in automatico.")
    return 0


def _elicitazione(args) -> int:
    from . import education as edu
    from . import elicitazione as el
    if args.azione == "modulo":
        out = _scrivi_nuovo(args.out, el.modulo(edu.CRITERI, args.partecipanti))
        if out is None:
            return 1
        print(f"Modulo con {args.partecipanti} partecipanti × {len(edu.CRITERI) * (len(edu.CRITERI) - 1) // 2} confronti -> {out}")
        print("Leggere docs/elicitazione.md prima della sessione.")
        return 0
    doc, dia = el.importa(args.file, edu.CRITERI, args.facilitatore, args.protocollo, args.soglia)
    da_rivedere = 0
    for pid, d in dia.items():
        stato = "coerente" if d["coerente"] else "DA RIVEDERE"
        print(f"{pid}: CR {d['cr']:.3f} — {stato}")
        for g in d["da_rivedere"]:
            print(f"    {g['a']} vs {g['b']}: ha indicato {g['valore']:.3g}, gli altri suoi giudizi implicano circa "
                  f"{g['coerente_con_gli_altri_giudizi']:.2g}")
        da_rivedere += not d["coerente"]
    if da_rivedere:
        print(f"{da_rivedere} partecipanti da ricontattare: rivedere con loro i giudizi indicati, poi reimportare. "
              "Chi resta incoerente sarà escluso dall'aggregazione e il rapporto lo dichiarerà.")
    out = _scrivi_nuovo(args.out, json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    if out is None:
        return 1
    print(f"Partecipanti reali -> {out}")
    print('Per usarli: in config/analisi.json impostare "pesi": {"fonte": "elicitazione", "file": "<nome del file>"} '
          "e ripetere la preregistrazione.")
    return 0


def _raccomanda(args) -> int:
    pac = analysis.carica_pacchetto(args.config)
    reg = Registro(args.audit)
    ris = analysis.esegui(pac, obiettivo=args.uso, con_studi=False, con_stabilita=True)
    controlli = reg.controlli_uso(pac, ris, uso_richiesto=args.uso)
    if not controlli["consentito"]:
        reg.aggiungi("RACCOMANDAZIONE_RIFIUTATA", {"uso": args.uso, "blocchi": controlli["blocchi"]})
        print("Raccomandazione NON emessa:")
        for b in controlli["blocchi"]:
            print("  -", b)
        return 2
    doc = {"uso": args.uso, "politica": ris["scelta_minimax"], "verdetto_prove": ris["cancello_prove"]["verdetto"],
           "riserve": ris["cancello_prove"]["riserve"], "avvisi": controlli["avvisi"], "sintesi": ris["sintesi"]}
    v = reg.aggiungi("RACCOMANDAZIONE", doc)
    out = Path(args.uscita) / f"raccomandazione_{args.uso}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(pulisci({**doc, "voce_audit": v["seq"], "hash_audit": v["hash"]}), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Raccomandazione per '{args.uso}': {doc['politica']} ({doc['verdetto_prove']}) -> {out}")
    return 0


def _benchmark(args) -> int:
    from . import benchmark
    r = benchmark.esegui()
    c = r["confronto_con_ema"]
    print(f"Lake problem: {r['esperimenti']} esperimenti di EMA Workbench {r['ema_workbench_riferimento']}")
    print(f"  Metriche di robustezza identiche a EMA+numpy: {'SÌ' if c['identico'] else 'NO'} "
          f"(scarto massimo {max(c['per_esito'], c['composita'], c['quota_soddisfacente']):.2e}); scelta minimax {r['robustezza']['scelta_minimax']}")
    for b, f in r["fedelta_modello"].items():
        if "differenza_massima_assoluta" in f:
            print(f"  Modello lake CWM ({b}): differenza massima {max(f['differenza_massima_assoluta'].values()):.2e} su {f['esperimenti']} esperimenti")
    voi = r["aggiunte_cwm"]["valore_informazione"]
    top = sorted(voi["per_incertezza"].items(), key=lambda kv: -kv[1]["voi_r"])[:3]
    print("  In più del CWM — incertezze che contano di più per una scelta robusta (VOI-R):",
          ", ".join(f"{k} {v['voi_r']:.4f}" for k, v in top))
    print("  Stabilità rispetto ai pesi:", r["aggiunte_cwm"]["stabilita_pesi"]["raggio"]["interpretazione"])
    out = Path(args.uscita) / "benchmark_lake.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(pulisci(r), ensure_ascii=False, indent=2), encoding="utf-8")
    Registro(args.audit).aggiungi("BENCHMARK", {"identico_a_ema": c["identico"], "file": out.name})
    print("  ->", out)
    return 0 if c["identico"] else 1


def _ema(args) -> int:
    from . import ema_bridge as eb
    ris = eb.carica_risultati(args.file)
    direzioni = dict(x.split("=") for x in args.direzioni.split(","))
    pesi = {k: float(v) for k, v in (x.split("=") for x in args.pesi.split(","))} if args.pesi else {k: 1.0 for k in direzioni}
    an = eb.analizza(ris, direzioni, pesi)
    print(f"{len(ris.esperimenti)} esperimenti, politiche {ris.politiche()}, incertezze {ris.incertezze()}")
    for p, m in an["composita"].items():
        print(f"  {p:20s} punteggio medio {m['punteggio_medio']:.4f}  rimpianto massimo {m['rimpianto_massimo']:.4f}")
    print("Scelta minimax:", an["scelta_minimax"])
    return 0


def _interfaccia(args) -> int:
    from .server import avvia
    avvia(args.porta, args.config, args.audit)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m cwm", description="Collective Wisdom Model 1.2")
    ap.add_argument("--config", default=str(BASE / "config"))
    ap.add_argument("--audit", default=str(BASE / "registro_audit"))
    ap.add_argument("--uscita", default=str(BASE / "esiti"))
    sub = ap.add_subparsers(dest="comando", required=True)
    s = sub.add_parser("analizza", help="analisi completa, scrive esiti/ e una voce di audit")
    s.add_argument("--obiettivo", default=None)
    s.add_argument("--rapido", action="store_true", help="salta studi EVSI e stabilità")
    s.set_defaults(f=_analizza)
    sub.add_parser("preregistra", help="congela il piano di analisi").set_defaults(f=_preregistra)
    s = sub.add_parser("verifica", help="verifica la catena di audit e riproduce l'ultima analisi")
    s.add_argument("--checkpoint", default=None, help="checkpoint conservato altrove: rileva troncamenti e riscritture")
    s.set_defaults(f=_verifica)
    s = sub.add_parser("checkpoint", help="attesta la testa del registro in un file da conservare altrove")
    s.add_argument("--out", required=True)
    s.set_defaults(f=_checkpoint)
    s = sub.add_parser("costi", help="legge i costi degli istituti e propone una fonte per il registro delle prove")
    s.add_argument("file", help="CSV come config/raccolta_costi_modello.csv")
    s.add_argument("--out", default=None, help="file nuovo in cui scrivere la proposta di fonte")
    s.add_argument("--id", default="preventivi_istituti", help="id della fonte proposta")
    s.set_defaults(f=_costi)
    s = sub.add_parser("elicitazione", help="modulo e importazione dei confronti a coppie di persone reali")
    el = s.add_subparsers(dest="azione", required=True)
    m = el.add_parser("modulo", help="genera il modulo dei confronti a coppie")
    m.add_argument("--partecipanti", type=int, required=True)
    m.add_argument("--out", required=True)
    i = el.add_parser("importa", help="valida un modulo compilato e indica i giudizi incoerenti da rivedere")
    i.add_argument("file")
    i.add_argument("--facilitatore", required=True)
    i.add_argument("--protocollo", required=True, help="riferimento al protocollo seguito, es. 'docs/elicitazione.md v1'")
    i.add_argument("--soglia", type=float, default=0.10, help="soglia del rapporto di coerenza (Saaty: 0,10)")
    i.add_argument("--out", required=True)
    s.set_defaults(f=_elicitazione)
    s = sub.add_parser("raccomanda", help="emette una raccomandazione solo se le prove lo consentono")
    s.add_argument("--uso", required=True)
    s.set_defaults(f=_raccomanda)
    sub.add_parser("benchmark", help="lake problem: confronto con EMA Workbench").set_defaults(f=_benchmark)
    s = sub.add_parser("ema", help="analizza un file save_results di EMA Workbench")
    s.add_argument("file")
    s.add_argument("--direzioni", required=True, help="es. max_p=min,utility=max")
    s.add_argument("--pesi", default=None, help="es. max_p=0.3,utility=0.7")
    s.set_defaults(f=_ema)
    s = sub.add_parser("interfaccia", help="interfaccia web locale")
    s.add_argument("--porta", type=int, default=8765)
    s.set_defaults(f=_interfaccia)
    args = ap.parse_args(argv)
    return args.f(args)


if __name__ == "__main__":
    sys.exit(main())
