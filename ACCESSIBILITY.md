# Accessibilità

## Impegno

CWM vuole poter essere usato da chi prende decisioni pubbliche, che non sempre programma e non sempre usa mouse e vista. L'obiettivo per ogni interfaccia è il livello AA delle WCAG 2.1, lo stesso richiesto in Italia alle pubbliche amministrazioni dalla Legge 4/2004.

## Situazione attuale

| Parte | Stato |
|---|---|
| Riga di comando (`python3 -m cwm ...`) | Solo testo, utilizzabile con lettori di schermo e da tastiera. |
| Rapporti in `esiti/` (Markdown e CSV) | Testo e tabelle senza immagini; i CSV si aprono con qualunque foglio di calcolo. |
| Interfaccia web locale (`python3 -m cwm interfaccia`) | Prototipo: etichette sui cursori dei pesi, colori con contrasto curato, ma **non ancora verificata** con lettori di schermo né con un audit WCAG. |

## Limiti noti dell'interfaccia web

- I grafici a barre sono SVG senza un'alternativa testuale completa: gli stessi valori sono nelle tabelle accanto.
- Alcuni stati (superato / non superato, astensione) sono indicati anche dal colore; il testo dell'etichetta li riporta sempre.
- Il linguaggio è tecnico (EVPI, VOI-R, minimax): manca ancora una versione in linguaggio semplice.

## Ambienti provati

macOS con Safari e Chrome recenti. Altri sistemi e browser non sono ancora stati provati in modo sistematico.

## Segnalare una barriera

Apri una issue con il modulo *Segnalazione di errore* e indica nel titolo "Accessibilità": cosa stavi facendo, quale tecnologia assistiva usi (se ne usi una), browser e sistema. Le barriere hanno la precedenza sulle nuove funzioni.
