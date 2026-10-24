# Raccolta dei costi per posto negli istituti

Le fonti pubbliche oggi nel registro (unità di costo standard PNRR e compensi del CCNL) bastano per un **pilota**. Per un **programma locale** il cancello chiede costi di livello "moderata": preventivi o documenti contabili degli istituti che lo adotteranno.

## Cosa raccogliere

Una riga per ogni documento. Il modello è in `config/raccolta_costi_modello.csv`: si può compilare con Excel e salvare come CSV, con virgola o punto e virgola.

| colonna | contenuto |
|---|---|
| `istituto` | nome dell'istituto |
| `codice_meccanografico` | codice MIM (es. `MIIC812345`), per contare gli istituti distinti |
| `tipo_istituto` | es. `istituto_comprensivo`, `secondaria_primo_grado`, `istituto_tecnico` |
| `gruppo` | `svantaggiati`, `altri` oppure `entrambi` se il costo non dipende dal gruppo |
| `formato` | `individuale` (1 studente) oppure `piccolo_gruppo` |
| `ore_per_studente` | ore di tutoraggio previste per ciascuno studente |
| `studenti_per_gruppo` | 1 per il formato individuale |
| `costo_orario_personale_eur` | costo orario del tutor o docente |
| `oneri_e_indiretti_pct` | oneri a carico dell'amministrazione e costi organizzativi, in percentuale del costo orario (0 se già inclusi) |
| `altri_costi_per_studente_eur` | materiali, mensa, trasporto per studente (0 se assenti) |
| `documento` | riferimento verificabile: protocollo del preventivo, delibera, voce di bilancio |
| `data_documento` | `AAAA-MM-GG` |
| `verificato_da` | chi ha controllato il documento (ruolo o iniziali) |

Tutti i campi sono obbligatori: una riga senza documento o senza verifica viene rifiutata.

Costo per posto = costo orario × (1 + oneri e indiretti / 100) × ore per studente / studenti per gruppo + altri costi.

## Quanti istituti

Almeno **3 istituti distinti** per gruppo, possibilmente scelti in modo da rappresentare i tipi di istituto interessati (non solo quelli che rispondono per primi). Con meno di 3 la proposta di fonte viene declassata per imprecisione.

Il dosaggio (ore per studente) deve essere quello del programma che si vuole valutare: l'effetto nel registro viene da programmi di circa 15 ore individuali (TOP) o fino a 20 ore (mentoring PNRR).

## Dal file al registro delle prove

```bash
python3 -m cwm costi costi_raccolti.csv --out proposta_costi.json --id preventivi_2026
```

Il comando stampa minimo, mediana e massimo per posto e scrive una **proposta** di fonte. Il registro non viene modificato in automatico: rileggere la proposta, completare i declassamenti (rischio di distorsione: come sono stati scelti gli istituti? indirettezza: stesso formato e dosaggio?) e incollarla in `config/registro_prove.json`. Da quel momento gli intervalli di costo del modello includeranno i preventivi, e l'analisi successiva registrerà la deviazione dal piano preregistrato.
