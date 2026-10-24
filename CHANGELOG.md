# Modifiche

## 1.2.1 — 24 ottobre 2026

### Dati reali
- Registro delle prove con fonti reali e stime numeriche: Carlana & La Ferrara (TOP, Italia), meta-analisi Nickow, Oreopoulos & Quan (stime per classi 6-11), Cabezas, Cuesta & Gallego (Cile), unità di costo standard PNRR DM 170/2022, CCNL scuola Tabella 5. Ogni fonte dichiara derivazione, data di consultazione e cosa resta da verificare.
- Gli intervalli di incertezza sono ricavati dal registro (`"intervalli": {"fonte": "registro"}`); i parametri senza stime restano ipotesi dichiarate. I piani precedenti producono esattamente i risultati di prima.
- `python3 -m cwm costi`: raccolta dei costi per posto dagli istituti, con proposta di fonte da rivedere.
- `python3 -m cwm elicitazione modulo|importa`: confronti a coppie di persone reali, con indicazione dei giudizi incoerenti da rivedere. Nessuna raccomandazione si basa su preferenze sintetiche o non documentate.

### Governance e audit
- Le deviazioni dal piano preregistrato bloccano per sezione (requisiti, vincoli, partecipanti, pesi, obiettivo, validazione), non per testo.
- `verifica` riproduce anche le analisi lanciate dall'interfaccia ed esce con errore su un registro vuoto.
- Registro con lock su file, fsync, JSON canonico rigoroso (niente NaN, chiavi ripetute o righe incomplete) e versione del formato dell'hash.
- `python3 -m cwm checkpoint` e `verifica --checkpoint`: rilevano troncamenti e riscritture della storia.

### Robustezza
- Validazione di pesi, vincoli, cancello sulle prove e giudizi AHP (più di 10 criteri, confronti ripetuti o di un criterio con sé stesso).
- Server locale protetto da DNS rebinding e CSRF, con limite al corpo delle richieste ed errori 400/500 distinti.

### Pacchetto
- Licenza EUPL-1.2, `pyproject.toml` (comando `cwm`), test automatici su GitHub Actions, `CITATION.cff`, `SECURITY.md`.

## 1.2.0

Prima versione con audit a catena firmato, preregistrazione, interfaccia web locale, governance dei pesi (1.1), valore dell'informazione (1.0), ponte con EMA Workbench (0.9) e modello a 5 dimensioni con cancello sulle prove (0.8).
