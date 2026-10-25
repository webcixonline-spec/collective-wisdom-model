# Collective Wisdom Model 1.2

[![test](../../actions/workflows/test.yml/badge.svg)](../../actions/workflows/test.yml)
Licenza: [EUPL-1.2](LICENSE) · Versione 1.2.1 · [Modifiche](CHANGELOG.md)

**Stato:** prototipo di ricerca. Non è uno strumento validato per allocare risorse pubbliche. Effetto, efficacia relativa tra gruppi e costi hanno fonti reali (vedi `config/registro_prove.json`); saturazione e benefici di lungo periodo restano ipotesi illustrative, e i partecipanti dell'esempio di elicitazione sono inventati.

CWM non è un altro motore di esplorazione degli scenari: è il **livello decisionale e di governance** che manca a EMA Workbench e Rhodium. Può usare EMA come motore (legge direttamente i suoi file) e aggiunge cinque cose: prove, valore dell'informazione, legittimità dei pesi, astensione e audit.

Requisiti: Python ≥ 3.10, **nessuna libreria esterna**. Se numpy è installato, il lake problem riproduce EMA bit per bit.

## When should a decision model refuse to recommend?

**CWM is a Python research prototype for public decisions under uncertainty: evidence checks, value of information, stakeholder weights, explicit abstention, and a verifiable audit trail.**

It connects model parameters to their evidence sources, explores which missing information is worth collecting, and checks whether a recommendation is permitted for its intended use. It can read EMA Workbench results and provides a local web interface.

**Research status:** not validated for allocating public resources. The included example combines sourced estimates with illustrative assumptions and synthetic stakeholder preferences. It withholds recommendations while those preferences remain synthetic. See the detailed limitations below.

### Try the local interface

Requires Git and Python 3.10 or newer. Run these commands in your terminal:

```bash
git clone https://github.com/webcixonline-spec/collective-wisdom-model.git
cd collective-wisdom-model
python3 -m cwm interfaccia
```

Open <http://127.0.0.1:8765> in your browser. The core uses the Python standard library; no package installation is needed for this quick start.

### Help test the idea

Can you find a case where CWM should abstain but does not? Or evidence that would change a decision? [Open an issue](https://github.com/webcixonline-spec/collective-wisdom-model/issues) with the command, configuration, expected result, and actual result. Remove private data and audit keys before sharing.

Contributions are welcome on evidence quality, reproducibility, stakeholder elicitation, and English documentation. Read [CONTRIBUTING.md](CONTRIBUTING.md) to get started. If this research is useful, star the repository to find it again or share it with someone working on decision analysis.

---

## Documentazione italiana

## Installazione

```bash
git clone https://github.com/webcixonline-spec/collective-wisdom-model.git cwm
cd cwm
python3 -m unittest discover -s tests       # 80 test, circa 15 secondi
python3 -m pip install -e .                 # facoltativo: aggiunge il comando `cwm`
```

I comandi vanno lanciati dalla cartella del repository: `config/` e `registro_audit/` vengono cercati lì. Su macOS e Linux usare `python3` (spesso `python` non esiste).

## Uso

```bash
python3 -m cwm preregistra          # congela il piano di analisi PRIMA dei risultati
python3 -m cwm analizza             # analisi completa -> esiti/ + voce nel registro di audit
python3 -m cwm verifica             # integrità della catena + riesecuzione dell'ultima analisi
python3 -m cwm checkpoint --out ~/altrove/cwm-checkpoint.json   # attesta la testa del registro: conservarlo FUORI da qui
python3 -m cwm verifica --checkpoint ~/altrove/cwm-checkpoint.json   # rileva anche troncamenti e riscritture
python3 -m cwm raccomanda --uso raccomandazione_nazionale   # rifiutata se le prove non bastano
python3 -m cwm raccomanda --uso pilota_valutato
python3 -m cwm benchmark            # lake problem: confronto con EMA Workbench 3.0
python3 -m cwm ema risultati.tar.gz --direzioni max_p=min,utility=max   # qualsiasi file save_results di EMA
python3 -m cwm interfaccia          # interfaccia web su http://127.0.0.1:8765
python3 -m cwm costi costi.csv --out proposta.json        # costi degli istituti -> proposta di fonte
python3 -m cwm elicitazione modulo --partecipanti 12 --out modulo.csv
python3 -m cwm elicitazione importa modulo.csv --facilitatore "..." --protocollo "docs/elicitazione.md v1" --out config/partecipanti_reali.json
python3 -m unittest discover -s tests -v
```

La configurazione è in `config/`: piano di analisi, registro delle prove, requisiti per obiettivo, vincoli sui diritti, partecipanti.

## Cosa contiene, fase per fase

| Fase | Moduli | Contenuto |
|---|---|---|
| 0.8 Basi solide | `education.py`, `evidence.py`, `analysis.py` | Modello a 5 dimensioni con rendimenti decrescenti, effetti soglia, costi incerti e vincolo di bilancio; 13 politiche al posto di 3; campionamento Latin Hypercube; holdout **che possono fallire** (estrapolazione fuori intervallo, struttura del modello diversa); cancello sulle prove graduato in stile GRADE (PASS / PASS_CON_RISERVA / ABSTAIN) per obiettivo; confronto con le baseline senza righe duplicate |
| 0.9 Ponte con EMA | `ema_bridge.py`, `lake.py`, `benchmark.py` | Lettura dei file `save_results` di EMA senza dipendenze; lake problem identico a quello di EMA 3.0; benchmark verificato |
| 1.0 Valore dell'informazione | `voi.py` | EVPI, EVPPI per parametro (regressione), EVSI per studi di dimensione n con costo e soglia di convenienza, **VOI-R**: valore dell'informazione per chi decide con minimax regret |
| 1.1 Governance dei pesi | `weights.py` | Confronti a coppie (AHP) con controllo di coerenza ed esclusione dei giudizi incoerenti, aggregazione per media geometrica, vincoli sui diritti non compensabili, accettabilità SMAA e raggio di stabilità |
| 1.2 Audit e interfaccia | `audit.py`, `server.py`, `ui.html`, `__main__.py` | Registro a catena firmato (HMAC-SHA256), preregistrazione con rilevamento delle deviazioni, riproducibilità verificata, blocco degli usi non consentiti, conteggio delle analisi ripetute; interfaccia web locale |

## Benchmark contro EMA Workbench

`benchmarks/` contiene 1.200 esperimenti (200 scenari LHS × 6 politiche) prodotti da **EMA Workbench 3.0.0** con il suo modello ufficiale `lake_problem_intertemporal`, più le metriche di robustezza calcolate in modo indipendente con numpy/pandas. Gli script per rigenerarli sono inclusi (`gen_ema.py`, `ref_numpy.py`; richiedono Python ≥ 3.12 ed EMA).

Risultati:
- metriche di robustezza (medie, percentili, rimpianti, quote soddisfacenti, utilità composita): **identiche**, scarto massimo 2,2·10⁻¹⁶, stessa scelta minimax;
- modello lake del CWM con numpy: **stessi numeri** (scarto 0 sulla stessa macchina, ≤ 10⁻¹⁵ su processori diversi per arrotondamenti di libm); con il solo Python, esiti deterministici identici e stocastici equivalenti;
- **in più**: VOI-R per incertezza (il fattore di sconto `delta` conta più di tutti per una scelta robusta) e raggio di stabilità rispetto ai pesi degli obiettivi.

Nota: in EMA 3.0 la funzione conta come `inertia` i cambi annuali **superiori** a 0,02, mentre l'esempio di ottimizzazione la dichiara da massimizzare. Il CWM la minimizza, in coerenza con la funzione.

## Cosa CWM fa e EMA/Rhodium no (e viceversa)

| | EMA Workbench / Rhodium | CWM 1.2 |
|---|---|---|
| Esplorazione di modelli complessi, connettori (Vensim, NetLogo, Excel), calcolo parallelo, ottimizzazione multiobiettivo, scenario discovery (PRIM/CART) | **sì** | no: usa EMA come motore |
| Metriche di robustezza | sì | sì, con stessi numeri |
| Collegamento parametro → fonte → livello di prova | no | sì |
| Astensione esplicita e ambito d'uso consentito | no | sì |
| EVPI / EVPPI / EVSI e soglia di convenienza di uno studio | no | sì |
| Valore dell'informazione coerente con il minimax regret (VOI-R) | no | sì |
| Pesi da partecipanti con controllo di coerenza | no | sì |
| Vincoli sui diritti separati dalle preferenze | no | sì |
| Stabilità della scelta rispetto ai pesi (SMAA, raggio) | no | sì |
| Preregistrazione, registro firmato, riproduzione verificata, blocco degli usi impropri | no | sì |
| Interfaccia per chi non programma | no (notebook) | sì |

## Esiti nell'esempio sintetico

Dalla 1.2.1 gli intervalli di incertezza vengono dal registro delle prove dove esistono stime (`"intervalli": {"fonte": "registro"}` in `config/analisi.json`):

| parametro | intervallo | origine |
|---|---|---|
| effetto | 0,12 – 0,26 DS | Carlana & La Ferrara (TOP, Italia, 0,20-0,26); meta-analisi Nickow, Oreopoulos & Quan per le classi 6-11 e gli studi grandi (0,12-0,25). L'aggregato 0,37 della meta-analisi non è usato: è dominato da infanzia e primaria |
| moltiplicatore | 0,85 – 1,32 | Cabezas, Cuesta & Gallego (Cile): rapporto tra effetti a breve termine per studenti a rischio alto e basso |
| costo per posto (entrambi i gruppi) | 525 – 1.000 € | UCS PNRR DM 170/2022 (mentoring 42 €/h); CCNL scuola Tabella 5 (35-50 €/h); 15-20 ore individuali |
| saturazione, conversione_lp | come prima | **ipotesi**. Per la conversione lo studio cileno mostra un effetto sull'abbandono (-3,7 p.p. per i più a rischio) quasi senza effetto sull'apprendimento: la struttura del modello (beneficio di lungo periodo proporzionale all'apprendimento) andrebbe rivista |

Con questi intervalli:
- **il bilancio di 36.000 € non basta**: 60 posti costano tra circa 33.000 e 59.000 € (mediana circa 46.000) e il bilancio è rispettato solo nel 4-7% degli scenari;
- le fonti non indicano costi diversi tra i due gruppi (prima era un'ipotesi): la scelta minimax e quella di massima utilità media coincidono, **45/15**, ed è più stabile (serve spostare il 3,8% del peso per passare a 40/20; accettabilità SMAA 71%);
- la scelta **non supera l'holdout di estrapolazione** (scarto 0,038 contro una tolleranza di 0,02): il CWM lo dichiara;
- il cancello consente il **pilota valutato** senza riserve e si astiene per il programma locale (servono preventivi degli istituti e prove sull'efficacia relativa tra gruppi) e per la raccomandazione nazionale;
- **nessuna raccomandazione viene emessa** finché i pesi vengono dai partecipanti sintetici dell'esempio: servono persone reali (vedi sotto);
- valore dell'informazione: per chi decide in modo robusto contano soprattutto i **costi** (conoscerli ridurrebbe il rimpianto massimo del 63-79%) e la **saturazione** (40%).

## Raccogliere dati reali

- **Costi degli istituti**: compilare `config/raccolta_costi_modello.csv` (istruzioni in [docs/raccolta_costi.md](docs/raccolta_costi.md)) e lanciare `python3 -m cwm costi FILE --out proposta.json`. Il comando propone una fonte per il registro; non lo modifica da solo.
- **Preferenze**: seguire [docs/elicitazione.md](docs/elicitazione.md); `python3 -m cwm elicitazione modulo` genera il modulo dei confronti a coppie e `python3 -m cwm elicitazione importa` lo valida e indica, per chi è incoerente, quali giudizi rivedere con la persona.
- **Prove ancora mancanti** (campo `da_verificare` nel registro): testi ufficiali delle UCS PNRR e del CCNL vigente; errori standard e sottogruppi di Carlana & La Ferrara; versione successiva della meta-analisi di Nickow et al.; qualunque fonte sulla saturazione; prove italiane sull'abbandono.

## Limiti dichiarati

1. Effetto e costi hanno fonti reali, lette in parte da sintesi e articoli (vedi `da_verificare` nel registro); moltiplicatore, saturazione e conversione nel lungo periodo restano ipotesi, e le preferenze dell'esempio sono inventate. Gli intervalli ricavati dalle fonti sono intervalli di stime puntuali, non intervalli di confidenza.
2. Gli holdout sono sintetici: verificano la robustezza a estrapolazione e struttura, non sostituiscono dati reali né una valutazione preregistrata sul campo.
3. EVPPI ed EVSI sono stimati per regressione polinomiale su campioni finiti: le stime hanno rumore e l'EVSI viene vincolato a non superare l'EVPPI e a crescere con n.
4. Il valore in euro dell'informazione richiede un parametro λ che spetta al decisore; senza λ il CWM riporta solo la soglia di convenienza.
5. La firma HMAC prova l'integrità a chi possiede la chiave (`registro_audit/.chiave`, da non condividere), ma chi ha la chiave può riscrivere l'intera catena. Troncamenti e riscritture si rilevano solo con un checkpoint (`python3 -m cwm checkpoint`) conservato fuori dalla cartella del registro e verificato con `verifica --checkpoint`. Le scritture usano un lock su file e `fsync`; un registro con righe incomplete, chiavi JSON ripetute o NaN viene dichiarato compromesso, non interpretato.
6. I vincoli R1/R2 sono interpretazioni degli autori, da validare con un giurista.

## Riferimenti metodologici

Carlana & La Ferrara (2025, American Economic Review 115(10)); Nickow, Oreopoulos & Quan (2020, NBER WP 27476); Cabezas, Cuesta & Gallego (2021, IE-PUC DT 565); Rothery et al. (2020, Value in Health); Strong, Oakley & Brennan (2014) e Strong et al. (2015, Medical Decision Making); Guyatt et al. (2008, BMJ, GRADE); Lempert et al. (2006, Management Science); Lahdelma, Hokkanen & Salminen (1998, EJOR); Forman & Peniwati (1998, EJOR); Kwakkel (2017, Environmental Modelling & Software). Dettagli in `config/registro_prove.json`.

## Come citare

GitHub mostra la citazione nel pulsante *Cite this repository* (file [CITATION.cff](CITATION.cff)).

## Sicurezza

Per segnalare una vulnerabilità vedi [SECURITY.md](SECURITY.md). La chiave del registro di audit (`registro_audit/.chiave`) è locale ed esclusa dal repository.

## Licenza

Copyright © 2026 Cristian Magrini.

Licensed under the EUPL. Il testo completo della European Union Public Licence v. 1.2 è in [LICENSE](LICENSE); la licenza è disponibile in tutte le lingue ufficiali dell'Unione europea, italiano compreso, sul sito della Commissione europea.

Il file `benchmarks/lake_ema_results.tar.gz` contiene esperimenti generati con EMA Workbench 3.0.0 (licenza BSD) e il suo modello `lake_problem_intertemporal`; gli script che li rigenerano sono in `benchmarks/`.
