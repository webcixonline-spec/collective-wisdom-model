# Contribuire a CWM

Grazie dell'interesse. CWM è un prototipo di ricerca per decisioni pubbliche: ogni contributo deve mantenere tre garanzie, cioè che i numeri siano tracciabili alle fonti, che l'algoritmo si astenga quando le prove non bastano, e che ogni analisi resti riproducibile dal registro di audit.

Partecipando accetti il [codice di comportamento](CODE_OF_CONDUCT.md).

## Tipi di contributo

- **Prove nuove o correzioni al registro** (`config/registro_prove.json`): apri una issue con il modulo *Nuova fonte o correzione*. Servono citazione completa, link, valori con la pagina o tabella da cui vengono, e come sono stati ricavati gli intervalli. Una fonte entra nel registro solo dopo che una seconda persona l'ha controllata.
- **Errori nel codice**: modulo *Segnalazione di errore*, con il comando eseguito, l'uscita e la versione (`python3 -m cwm --help` e `git rev-parse --short HEAD`).
- **Proposte di metodo o funzioni**: modulo *Proposta*, prima di scrivere codice, così si discute l'impatto su prove, astensione e audit.
- **Vulnerabilità**: mai in una issue pubblica. Vedi [SECURITY.md](SECURITY.md).

## Preparare l'ambiente

```bash
git clone https://github.com/webcixonline-spec/collective-wisdom-model.git
cd collective-wisdom-model
python3 -m unittest discover -s tests -v
```

Serve Python 3.10 o successivo, senza librerie esterne. numpy è facoltativo e serve solo al benchmark bit per bit con EMA Workbench.

## Regole per le modifiche al codice

1. **Test prima di tutto.** Ogni correzione aggiunge un test che fallirebbe senza la correzione. La CI esegue i test su Python 3.10–3.13.
2. **Nessun default silenzioso.** Un input non valido deve produrre un errore chiaro, non un valore plausibile. NaN, chiavi mancanti e parametri sconosciuti sono errori.
3. **Riproducibilità.** Le analisi registrate con versioni precedenti devono continuare a dare lo stesso hash: se un cambiamento modifica la forma dei risultati, va reso condizionato a una nuova chiave del piano (vedi come è fatto `intervalli` in `cwm/analysis.py`) e accompagnato da un test di compatibilità.
4. **Governance.** Non indebolire il cancello sulle prove, i blocchi sulle deviazioni dal piano preregistrato o i controlli sulle preferenze reali senza una discussione esplicita in una issue.
5. **Stile.** Libreria standard di Python, nomi e messaggi in italiano come nel resto del codice, commenti solo dove spiegano un perché.

## Pull request

- Una PR per un argomento.
- Descrivi cosa cambia, perché, e come l'hai verificato (il modello di PR lo chiede).
- Aggiorna `CHANGELOG.md` e, se cambia l'uso, il README.

## Licenza dei contributi

Il progetto è distribuito con licenza [EUPL-1.2](LICENSE). Inviando un contributo accetti che sia distribuito con la stessa licenza.
