# Prod Light Curve Context

Questo file raccoglie il contesto operativo utile per lavorare sul modulo `prod_light_curve` dentro AGATA.

## Scopo Del Modulo

`prod_light_curve` implementa un flusso AGATA "classico" per fotometria ground-based su sequenze di immagini FITS:

- i FITS restano sul server
- la logica scientifica sta nel backend
- il frontend usa solo preview leggere della reference image
- l'utente definisce target, comparison stars, frame inclusi e parametri fotometrici
- la fotometria viene eseguita lato server su tutta la sequenza

Il modulo prende come riferimento architetturale `moduli/tpf`, ma non ne riusa la logica scientifica TPF-specifica.

## Struttura Del Modulo

Percorso:

- `agata/moduli/prod_light_curve`

File principali:

- `__init__.py`: blueprint e controllo accesso coerente con gli altri moduli AGATA
- `routes.py`: endpoint UI/API sottili
- `config.py`: impostazioni locali del modulo
- `services/`: logica backend
- `templates/prod_light_curve/index.html`: pagina del modulo
- `static/js/prod_light_curve/main.js`: interazione frontend
- `static/css/prod_light_curve.css`: stile del viewer e dei pannelli

## Flusso Architetturale

Pattern adottato:

- route sottili
- orchestrazione nel service layer
- payload JSON tecnico verso il frontend
- sessione tecnica persistita localmente
- niente download massivo dei FITS lato client

Flusso utente attuale:

1. l'utente inserisce `dataset_path`
2. `Ispeziona dataset` costruisce dataset summary, reference image, auto-target locale e frame quality
3. `Cerca target noti` lancia la query catalografica solo su richiesta
4. `Suggerisci comparison stars` calcola il ranking automatico solo su richiesta
5. l'utente puo' rifinire target e comparison sull'immagine
6. `Esegui fotometria` lancia la pipeline server-side
7. `Salva sessione` salva lo stato tecnico del lavoro

## Servizi Backend

Responsabilita' principali:

- `dataset_service.py`
  - scansione cartelle FITS
  - caricamento frame
  - scelta reference frame

- `reference_service.py`
  - costruzione del payload reference
  - preview PNG leggera
  - metadati centro FITS

- `selection_service.py`
  - detection locale sorgenti sulla reference
  - auto-target locale
  - ranking comparison stars

- `catalog_service.py`
  - target candidati da cataloghi, in modo modulare

- `frame_quality_service.py`
  - metriche di qualita' frame
  - flag automatici

- `photometry_service.py`
  - aperture photometry
  - centroid refinement
  - curva di luce differential

- `pipeline_service.py`
  - orchestrazione del flusso

- `save_service.py`
  - sessioni tecniche file-based

## Stato UI Attuale

Viewer reference image:

- zoom e pan
- `click.target`
- `click.comp`
- `vis.centro` per mostrare/nascondere il crosshair del centro FITS
- overlay SVG per:
  - crosshair centrale
  - anelli fotometrici del target
  - anelli fotometrici delle comparison stars
  - etichette numeriche delle comparison stars

Note UI importanti:

- il target usa tre circonferenze fotometriche
- anche le comparison usano la stessa geometria, con colore diverso
- la tabella `Comparison stars` compare anche per selezioni fatte solo da immagine
- target query e comparison suggestion non partono automaticamente durante `inspect`

## Endpoint Principali

Endpoint del modulo:

- `/agata/prod-light-curve/`
- `/agata/prod-light-curve/health`
- `/agata/prod-light-curve/api/inspect`
- `/agata/prod-light-curve/api/query-targets`
- `/agata/prod-light-curve/api/suggest-comparisons`
- `/agata/prod-light-curve/api/run`
- `/agata/prod-light-curve/api/save`
- `/agata/prod-light-curve/api/sessions`
- `/agata/prod-light-curve/api/restore`
- `/agata/prod-light-curve/api/delete`

Il blueprint e' registrato in:

- `C:\Users\CarloMarino\dev\flask\app.py`

## Come Lanciare Il Backend

Root del progetto:

- `C:\Users\CarloMarino\dev\flask`

Virtual environment corretto:

- `C:\Users\CarloMarino\dev\flask\.venv`

Comando consigliato su Windows PowerShell:

```powershell
cd C:\Users\CarloMarino\dev\flask
$env:DEV_AUTH_BYPASS="true"
$env:FLASK_ENV="development"
.\.venv\Scripts\python.exe .\app.py
```

Questo comando e' stato verificato come forma corretta da usare, evitando problemi di activation policy di PowerShell.

URL utili:

- `http://127.0.0.1:5000/health`
- `http://127.0.0.1:5000/agata/prod-light-curve/`

Frontend del modulo:

- dopo l'avvio del backend, il frontend si invoca direttamente aprendo:
  - `http://127.0.0.1:5000/agata/prod-light-curve/`

## Note Su Ambiente E Dipendenze

- il plain `python .\app.py` puo' fallire se non punta al venv giusto
- l'errore visto in locale e' stato `ModuleNotFoundError: No module named 'flask_login'`
- per questo e' importante usare `.\.venv\Scripts\python.exe`

## Nota Prestazioni

Osservazione importante emersa durante il debugging:

- la fotometria puo' essere lenta non solo per i calcoli, ma anche perche' il backend rilegge l'intera sequenza FITS piu' volte nello stesso run
- il punto principale da ottimizzare e' il riuso di `dataset_summary` dentro `pipeline_service.py`

Questa nota e' utile se si lavora sulle performance del modulo.

## Convenzioni Da Mantenere

- mantenere la logica scientifica nel backend
- mantenere il frontend leggero
- evitare strutture parallele a quelle AGATA se esiste gia' un pattern riusabile
- preferire estensioni modulari a scelte troppo rigide su soglie, ranking e cataloghi
- mantenere compatibilita' con il pattern usato nel modulo `tpf`
