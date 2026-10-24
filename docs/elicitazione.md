# Protocollo di elicitazione dei pesi (v1)

I pesi dei cinque criteri devono venire da persone reali, con un processo documentato. Il CWM rifiuta una raccomandazione basata su preferenze dichiarate `sintetica`, senza `natura`, senza facilitatore, protocollo, data o consenso, o con meno di 3 partecipanti.

## 1. Chi partecipa

- Decidere **prima** quali gruppi devono essere rappresentati (es. docenti, dirigenti, famiglie, studenti delle superiori, servizi sociali, amministrazione) e quante persone per gruppo.
- Annotare come sono state scelte le persone (sorteggio da un elenco, candidatura, designazione). Una selezione per convenienza va dichiarata nel rapporto.
- Usare **identificativi pseudonimi** (`P01`, `P02`…) nel modulo: nomi e contatti restano in un elenco separato custodito dal facilitatore.

## 2. Consenso

Prima della sessione ogni partecipante riceve un'informativa: scopo, uso dei giudizi, conservazione, possibilità di ritirarsi. Il consenso si registra nella colonna `consenso` (`sì`). Per minorenni serve il consenso di chi esercita la responsabilità genitoriale.

## 3. La sessione

1. Spiegare i cinque criteri con le stesse parole per tutti:
   - **apprendimento**: quanto migliorano gli esiti scolastici complessivi;
   - **equità**: quanta parte del beneficio va agli studenti svantaggiati;
   - **accesso**: quanti studenti non svantaggiati possono comunque partecipare;
   - **lungo_periodo**: riduzione dell'abbandono scolastico negli anni successivi;
   - **sostenibilità**: rispetto del bilancio disponibile.
2. Spiegare la scala: per ogni coppia (A, B) si indica quanto A è più importante di B. 1 = uguale, 3 = moderatamente, 5 = fortemente, 7 = molto fortemente, 9 = in modo estremo; se è B più importante si usa l'inverso (1/3, 1/5, …).
3. Ognuno compila i 10 confronti **da solo**, prima di qualsiasi discussione di gruppo, per evitare che la prima opinione espressa orienti le altre.
4. Generare il modulo:

   ```bash
   python3 -m cwm elicitazione modulo --partecipanti 12 --out modulo.csv
   ```

## 4. Coerenza: si discute, non si esclude in silenzio

```bash
python3 -m cwm elicitazione importa modulo.csv --facilitatore "Nome del facilitatore" \
  --protocollo "docs/elicitazione.md v1" --out config/partecipanti_reali.json
```

Per ogni partecipante il comando calcola il rapporto di coerenza (CR). Se supera 0,10 indica i due giudizi più lontani da quelli che la persona ha dato sulle altre coppie. Il facilitatore li rivede **con la persona**, che può confermarli o cambiarli; poi si reimporta. Chi resta incoerente viene escluso dall'aggregazione e il rapporto lo dichiara con il suo CR.

## 5. Dissenso

Annotare nel verbale della sessione i disaccordi espressi e le ragioni. Il CWM mostra la dispersione dei pesi individuali e, con l'analisi di stabilità, quanto peso basta spostare per cambiare la scelta: questi numeri vanno discussi con i partecipanti prima della decisione.

## 6. Uso nell'analisi

In `config/analisi.json` impostare `"pesi": {"fonte": "elicitazione", "file": "partecipanti_reali.json", "soglia_coerenza": 0.10}` e **ripetere la preregistrazione** prima di guardare i risultati.
