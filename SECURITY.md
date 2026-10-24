# Sicurezza

CWM è un prototipo di ricerca. L'interfaccia web (`python3 -m cwm interfaccia`) ascolta solo su `127.0.0.1` e non va esposta in rete.

## Segnalare una vulnerabilità

Non aprire una issue pubblica. Usa la funzione **Report a vulnerability** nella scheda *Security* del repository (segnalazione privata di GitHub). Indica versione, passi per riprodurre e impatto.

Sono particolarmente utili le segnalazioni su:
- integrità del registro di audit (`cwm/audit.py`): modifiche, troncamenti o riscritture non rilevate, anche con il checkpoint;
- controlli d'uso aggirabili (raccomandazioni emesse quando il cancello sulle prove o la preregistrazione dovrebbero bloccarle);
- lettura di file EMA (`cwm/ema_bridge.py`) e del server locale (`cwm/server.py`).

## Chiave del registro

`registro_audit/.chiave` è creata in locale ed è esclusa dal repository. Non va mai pubblicata: chi la possiede può rifirmare il registro. Contro questa minaccia serve un checkpoint conservato altrove (`python3 -m cwm checkpoint`).
