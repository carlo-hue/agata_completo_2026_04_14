# Galassie Nane (Modulo AGATA)

Modulo AGATA per analisi di campi Gaia finalizzata alla ricerca/valutazione di candidati (galassie nane), con:

- analisi singola (`single-run`)
- provider Gaia centralizzato (`mock` / `real`)
- visualizzazione risultati in UI (KPI, heatmap, preview sorgenti)
- salvataggio e riapertura run locali

## Struttura del modulo (backend)

- `2026_02_15-agata/galassie_nane/__init__.py`
  - blueprint Flask
  - controllo accesso / bypass locale
- `2026_02_15-agata/galassie_nane/routes.py`
  - route UI
  - API `single-run`, `save-run`, `saved-runs`
- `2026_02_15-agata/galassie_nane/services/density.py`
  - mappe densita e Z-map
- `2026_02_15-agata/galassie_nane/services/scoring.py`
  - metriche e tile score
- `2026_02_15-agata/galassie_nane/services/single_run.py`
  - orchestrazione analisi singola (query -> density -> score -> payload UI)
- `2026_02_15-agata/galassie_nane/services/gaia_client.py`
  - unico punto per interrogazione Gaia
  - supporta `mock` e `real`
  - tabella Gaia centralizzata (`gaia_source_table_name()`)
- `2026_02_15-agata/galassie_nane/services/saved_runs.py`
  - salvataggio locale JSON
  - lista run salvate
  - caricamento run salvata

## Frontend collegato

- `2026_02_15-agata/templates/galassie_nane/index.html`
  - pagina principale modulo
- `2026_02_15-agata/templates/galassie_nane/descrizione.html`
  - pagina descrittiva (abbozzo)
- `2026_02_15-agata/static/css/galassie_nane.css`
  - stili UI modulo
- `2026_02_15-agata/static/js/galassie_nane/main.js`
  - logica UI: esecuzione, rendering risultati, salvataggio, riapertura run

## Endpoint

UI:

- `GET /agata/galassie-nane/`
- `GET /agata/galassie-nane/descrizione`

API:

- `POST /agata/galassie-nane/api/single-run`
- `POST /agata/galassie-nane/api/save-run`
- `GET /agata/galassie-nane/api/saved-runs`
- `GET /agata/galassie-nane/api/saved-runs/<run_id>`

## Provider Gaia (punto unico)

Il file da modificare quando si cambia strategia di interrogazione Gaia e:

- `2026_02_15-agata/galassie_nane/services/gaia_client.py`

Responsabilita centralizzate:

- ADQL
- selezione tabella Gaia
- retry/fallback sync
- normalizzazione risultati
- mock provider

## Storage run salvate

Default:

- `2026_02_15-agata/_runtime_data/galassie_nane_runs/`

Configurabile via env:

- `GALASSIE_NANE_RUNS_DIR`

## Nota runtime locale

Nel setup locale corrente, `app_local.py` carica AGATA dalla cartella:

- `agata_mappa_stelle/2026_02_15-agata`

Quindi questa e la sorgente attiva da modificare per vedere gli effetti nella UI locale.
