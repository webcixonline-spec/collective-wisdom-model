# CWM — sistema di diffusione e contributi

Analisi del 5 novembre 2026. Base esaminata: commit bbaea35. Budget proposto:
zero pubblicità, circa 5 ore settimanali del maintainer, più preparazione iniziale.
È un esperimento di crescita, non una previsione di viralità.

## Diagnosi specifica

La repository ha già licenza EUPL, citazione, codice di condotta, contributi,
issue template, CI, 80 test e un benchmark EMA. Non serve inventare questi elementi.
Il README aveva già un'introduzione inglese e una richiesta di controesempi:
il sistema sviluppato rende quella richiesta eseguibile e misurabile.

Gli ostacoli osservati sono il percorso bilingue frammentato, l'interfaccia italiana,
l'assenza di una demo breve dedicata al rifiuto e la sproporzione tra ampiezza delle
promesse e semplicità del primo esperimento. Le affermazioni assolute sulla mancanza
di funzionalità in EMA/Rhodium richiedono una verifica per versione prima di usarle
nella comunicazione. Non basare il lancio su presunte superiorità scientifiche.

Non sono stati acquisiti traffico privato, download, tasso di attivazione o baseline
di stelle. Non dedurre scarso interesse da metriche non disponibili. Non è stata
verificata la configurazione live di topics, Discussions, social preview o release.

## Posizionamento

Messaggio principale: **When should a decision model refuse to recommend?**

Descrizione proposta per About: “Python research prototype for decisions under
uncertainty: evidence checks, explicit abstention, stakeholder weights and audit.”

Tre pubblici, in ordine: sviluppatori scientifici Python; ricercatori di decision
analysis e robust decision making; persone che studiano governance e valutazione
delle politiche. Il pubblico generalista arriva dopo un caso comprensibile.
Evitare “IA che decide per l'umanità”: CWM non è un LLM e non è validato sul campo.

## Il ciclo di crescita

1. Un contenuto mostra un rifiuto reale e spiega una ragione concreta.
2. Il lettore esegue `python3 tools/demo_abstention.py` dal checkout.
3. Il risultato porta a una sola richiesta: trovare un controesempio riproducibile.
4. Il maintainer riproduce la segnalazione, risponde e aggiunge una correzione/test quando necessario.
5. Un breve resoconto mostra cosa è cambiato, collegando issue e commit.
6. Chi ha contribuito può condividere il proprio risultato: nasce un nuovo punto d'ingresso.

Il motore di diffusione è il risultato del partecipante. Stelle e visualizzazioni
sono indicatori secondari. Non usare bot, acquisto di stelle, commenti automatici,
messaggi in massa o richieste di voti coordinate.

## Calendario operativo

| Giorni | Attività e responsabile | Condizione di uscita |
|---|---|---|
| 1–3 | Maintainer: integrare questo kit, eseguire demo/test, rivedere affermazioni comparative; acquisire baseline | Un utente esterno riesce a eseguire la demo seguendo solo la guida |
| 4–7 | Maintainer: proporre a 5 tester pertinenti una prova volontaria; registrare attriti e correggere istruzioni | Almeno 3 esecuzioni confermate, nessun blocco di onboarding irrisolto |
| 8–10 | Maintainer: registrare video di 45–60 secondi e pubblicare un post LinkedIn dal proprio profilo | Link a codice e istruzioni, dichiarazione dei limiti visibile |
| 11–14 | Maintainer: Show HN se il progetto è proponibile e non è una semplice ripetizione di un lancio precedente | Presenza per rispondere nelle prime ore; demo funzionante |
| 15–21 | Maintainer: un articolo tecnico su un limite emerso; una discussione pertinente in una comunità con regole verificate | Feedback riproducibile, non cross-post identici |
| 22–30 | Maintainer: integrare contributi, pubblicare resoconto e valutare il prossimo ciclo | Decisione documentata su messaggio e canale da mantenere |

Prima del lancio verificare eventuali precedenti Show HN. Le linee guida richiedono
qualcosa provabile, scoraggiano semplici aggiornamenti e vietano richieste di upvote.
Su Reddit o forum scegliere prima una comunità pertinente, leggere le sue regole
attuali e chiedere ai moderatori solo quando previsto. Nessun invio è automatizzato.

## Contenuti pronti per revisione

### Show HN — titolo

Show HN: CWM, a Python decision prototype that can refuse to recommend

### Primo commento dell'autore

I’m building CWM to explore a question: when should a decision model refuse to
recommend? The prototype connects model parameters to evidence, checks stakeholder
preferences, and records an audit trail. The bundled example withholds recommendations
while stakeholder preferences remain synthetic, even for a pilot whose evidence gate
passes. You can run the actual checks with Python 3.10+ and no external packages:
`python3 tools/demo_abstention.py` after cloning the repository.

This is a research prototype, not a validated public-policy tool. The interface and
engine messages are currently in Italian; the English guide explains the demo.
I’m looking for reproducible counterexamples, especially cases where it should
abstain but does not. The repository includes the limitations and an issue form.

Link: https://github.com/webcixonline-spec/collective-wisdom-model

### LinkedIn — italiano

Quando un modello decisionale dovrebbe dire: “Non posso raccomandare questa scelta”?

Sto sviluppando Collective Wisdom Model per rendere questa domanda verificabile.
Nell'esempio incluso, anche quando le prove permettono di considerare un pilota,
le preferenze sintetiche dei partecipanti impediscono di emettere la raccomandazione.

Ho preparato una demo che esegue questi controlli sul motore reale. È un prototipo
di ricerca, non uno strumento validato per decidere l'allocazione di risorse pubbliche.

Cerco persone che lavorano con Python, analisi decisionale o valutazione delle
politiche: riuscite a trovare un caso riproducibile in cui dovrebbe fermarsi e non lo fa?

Codice e istruzioni: https://github.com/webcixonline-spec/collective-wisdom-model

### Video da produrre — scaletta

0–8 s: domanda “Would you trust a model that always gives an answer?”
8–18 s: mostrare comando, commit e avviso “research prototype / synthetic preferences”.
18–38 s: mostrare output reale del pilota e del caso nazionale, senza inventare numeri.
38–48 s: spiegare differenza fra prova sufficiente per esplorare e permesso di raccomandare.
48–60 s: invitare a riprodurre o trovare un controesempio; mostrare URL.
Se l'esecuzione è più lunga, indicare esplicitamente i tagli o l'accelerazione.

## Misurazione

Eseguire localmente, con GitHub CLI autenticata:

```bash
python3 tools/growth_snapshot.py --out esiti/growth/day01.json
# Se l'account dispone dei permessi per il traffico:
python3 tools/growth_snapshot.py --traffic --out esiti/growth/day01-traffic.json
```

Ripetere una volta a settimana con un nome nuovo. Lo script legge aggregati e non
pubblica nulla. Senza accesso, la metrica è indisponibile, mai zero. La CLI `gh`
è una dipendenza solo di questo strumento, non del modello o della demo.
Il traffico GitHub copre gli ultimi 14 giorni: conservare snapshot e deduplicare
le righe per giorno; non sommare finestre sovrapposte. I visitatori unici giornalieri
non sono persone uniche mensili. `open_issues_count` comprende anche le pull request.

| Indicatore | Raccolta | Uso |
|---|---|---|
| Esecuzioni confermate | Feedback volontario dei tester e issue | Obiettivo di attivazione: non equiparare clone a esecuzione |
| Controesempi riproducibili | Triage manuale delle issue | Indicatore principale di valore |
| Contributori esterni attivi | Autori di contributi sostanziali, escluso maintainer/bot | Segnale di comunità |
| Stelle e fork | Differenza fra snapshot | Interesse secondario, non validazione |
| Visite, clone, referrer | Snapshot con permessi | Diagnosi della distribuzione, attribuzione incompleta |
| Tempo di prima risposta | Registro manuale | Obiettivo operativo: entro 48 ore |

Registro manuale settimanale: data, canale, URL del contenuto, ore impiegate,
esecuzioni confermate, issue riproducibili, contributori, attriti, azione successiva.
La domanda facoltativa nella issue aiuta l'attribuzione. Non esiste telemetria nella
demo; non attribuire una stella a un post con certezza usando solo coincidenza temporale.

Soglie proposte, non benchmark di mercato: entro 30 giorni 10 esecuzioni confermate,
3 segnalazioni sostanziali riproducibili e 2 contributori esterni. Zero promesse di stelle.
Con meno di 10 feedback non dichiarare un messaggio vincente. Se arrivano visite ma
nessuna esecuzione, migliorare onboarding; esecuzioni senza contributi richiedono
task più piccoli; interesse basso richiede revisione del messaggio e del pubblico.

## Backlog successivo e condizioni

P0: rivedere README comparativo, completare onboarding inglese, integrare kit.
P1: tradurre interfaccia, produrre video reale, curare tre task iniziali (traduzione,
verifica di una fonte, test di un controesempio). Non assegnare “good first issue” a
cambiamenti metodologici che richiedono competenze avanzate.
P2: una demo pubblica senza installazione solo dopo revisione di hosting, isolamento
e trattamento dati. Non esporre il server locale di ricerca direttamente a Internet.
Topics proposti da verificare: decision-analysis, uncertainty-quantification,
robust-decision-making, value-of-information, reproducible-research, python.

Il kit è stato preparato e testato localmente per l'integrazione nella repository.
Post promozionali, video e reclutamento dei tester restano attività di lancio.
Verifica live del 5 novembre: descrizione About e 10 topics già presenti; baseline
pubblica di 0 stelle e 0 fork. Questi conteggi non misurano le esecuzioni del modello.

## Fonti e confini delle conclusioni

- Codice e documentazione CWM, commit bbaea35: https://github.com/webcixonline-spec/collective-wisdom-model
- Show HN: https://news.ycombinator.com/showhn.html
- Metriche e permessi GitHub: https://docs.github.com/en/rest/metrics/traffic
- Topics: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics

Le fonti supportano caratteristiche e vincoli delle piattaforme. Messaggio,
sequenza, soglie e pubblici sono ipotesi strategiche da testare.
