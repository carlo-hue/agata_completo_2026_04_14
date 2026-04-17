# TODO Galassie Nane

Stato operativo del modulo `Galassie Nane` in AGATA.

## Gia fatto (base funzionante)

- modulo Flask `galassie_nane` con route UI e API
- UI analisi singola con KPI, heatmap, preview sorgenti
- provider Gaia centralizzato in `services/gaia_client.py`
- supporto `mock` e `Gaia reale` (toggle FE)
- salvataggio run con nome (JSON locale)
- lista run salvate e riapertura run
- tempi di esecuzione (`Tempo Totale`)
- metadati risultati (`tabella Gaia`, filtro extragal, nome run visualizzata)

## Mancante (priorita alta)

1. Rifattorizzare/integrare il codice scientifico originale nel nuovo schema `services/*`
2. Validazione input robusta (range RA/Dec/radius/gmax/ruwe/cell)
3. Gestione errori Gaia piu specifica in UI (timeout, astroquery mancante, TAP error)
4. Test backend minimi (`single-run`, `save-run`, `saved-runs`)
5. Commit e push delle ultime modifiche

## Mancante (priorita media)

1. Batch/griglia (`preview tiles`, esecuzione batch, summary)
2. CMD core/control e altri output scientifici del codice originale
3. Export risultati (CSV/JSON scaricabile da UI)
4. Ricerca/filtro lista run salvate (nome/data/provider)
5. Migliorare formattazione date UTC in UI

## Mancante (prestazioni / Gaia)

1. Caching interrogazioni Gaia
2. Strategia "query estesa una volta, tuning locale parametri"
3. Parametri retry/timeout configurabili da UI avanzata o config
4. Logging job Gaia (`jobid`, `remote_location`) per debug/audit

## Mancante (documentazione)

1. `TREE.md` aggiornato quando la struttura cambia
2. Documentare workflow di test locale (mock vs reale)
3. Documentare convenzioni storage run salvate

## Note di progetto

- Il punto unico per Gaia resta `services/gaia_client.py`
- Evitare di duplicare logica Gaia in altri servizi/route
- Il caching Gaia va progettato a livello servizio, non in UI
