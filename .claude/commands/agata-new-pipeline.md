# AGATA – Nuova Background Pipeline (State Machine)

**Argomenti:** `$ARGUMENTS` = `<nome_pipeline> "<stati_csv>" "<descrizione>"`

Esempio: `/agata-new-pipeline photometry_import "pending,downloading,processing,completed,failed" "Import fotometria da sorgente esterna"`

---

## Contesto Progetto

**Sistema:** AGATA | Background jobs con ThreadPoolExecutor, state machine in DB

**Pattern obbligatorio:** leggi `agata/moduli/admin/services/ztf_survey_service.py` (intero file)

**Pattern route:** leggi `agata/moduli/admin/routes/ztf_survey.py`

**Pattern modello:** leggi `agata/auth_models/ztf_survey_job.py`

**Pattern migration:** leggi `docs/migrations/002_create_ztf_survey_tables.sql`

---

## Componenti da Creare

### 1. Modello DB: `agata/auth_models/<nome>_job.py`

State machine tramite `SQLEnum` con gli stati da `$ARGUMENTS`.

Campi obbligatori su ogni job model:
- `id`, `job_code` (univoco, es. `PREFIX-YYYY-00001`), `association_id`
- `state` (SQLEnum), `progress_pct` (0-100), `current_step` (VARCHAR 255)
- `error_message` (Text), `retry_count`
- `requested_by` / `created_by` (FK a `agata_users`)
- `created_at`, `started_at`, `completed_at`
- Indici: `(association_id, state)`, `created_at`, `created_by`

### 2. Service: `agata/moduli/admin/services/<nome>_service.py`

Struttura obbligatoria:

```python
# Worker function FUORI dalla classe (obbligatorio per ThreadPoolExecutor pickling)
def _<nome>_worker(params: tuple):
    """Top-level per compatibilità pickling con ThreadPoolExecutor."""
    ...

class <NomePipeline>Service:
    def start_job(self, job_id: int) -> None:
        """Lancia il job in background thread."""
        thread = threading.Thread(target=self._run_pipeline, args=(job_id,), daemon=True)
        thread.start()

    def _run_pipeline(self, job_id: int) -> None:
        """Orchestratore pipeline. Aggiorna stato DB a ogni fase."""
        db = SessionLocal()
        try:
            self._update_state(db, job_id, 'downloading', 'Avvio download...')
            # fase 1...
            self._update_state(db, job_id, 'processing', 'Elaborazione...')
            # fase 2...
            self._update_state(db, job_id, 'completed', 'Completato')
        except Exception as e:
            self._update_state(db, job_id, 'failed', str(e))
            logger.exception(f"Pipeline {job_id} failed")
        finally:
            db.close()

    def _update_state(self, db, job_id, state, step, progress=None):
        """Aggiorna stato job nel DB."""
        ...
```

Regole per worker functions:
- Se usa `ThreadPoolExecutor` per parallelismo: funzioni worker **obbligatoriamente** top-level (non metodi di classe) per compatibilità con pickling
- Ogni fase aggiorna `state`, `progress_pct`, `current_step` nel DB
- Timeout espliciti per ogni chiamata API/rete esterna
- Errori non fatali: log + continua. Errori fatali: set `state='failed'`, solleva eccezione

### 3. Route: `agata/moduli/admin/routes/<nome>.py`

Endpoint obbligatori:
- `GET /<nome>/jobs` — pagina lista job (HTML)
- `GET /<nome>/jobs/<job_id>` — dettaglio job (HTML)
- `POST /api/<nome>/jobs` — crea e avvia job (JSON)
- `GET /api/<nome>/jobs/<job_id>/status` — polling status (JSON, usato da UI per progress bar)
- `DELETE /api/<nome>/jobs/<job_id>` — cancella job pending (JSON)

### 4. Template: `agata/moduli/admin/templates/admin/<nome>/jobs.html` e `job_detail.html`

La pagina `job_detail.html` deve includere polling JS con `setInterval` su `/api/.../status`.

### 5. Modifica `agata/moduli/admin/__init__.py`:

```python
from agata.moduli.admin.routes import <nome>
```

---

## Regole Non Negoziabili

- Worker functions top-level per ThreadPoolExecutor (mai metodi di classe)
- Ogni transizione di stato è una singola DB commit atomica
- Progress polling: endpoint `/api/.../status` ritorna `{state, progress_pct, current_step, error_message}`
- Thread daemon=True per evitare blocco shutdown
- Job scoping: admin vede solo `association_id` proprio; superuser vede tutti
- `created_by` / `requested_by` sempre popolato con `current_user.id`

---

## Output Atteso

1. Modello SQLAlchemy con state machine
2. Service class con orchestratore e worker functions
3. Routes con tutti gli endpoint
4. Migration SQL idempotente
5. Template HTML base con polling JS
6. Modifica a `admin/__init__.py`
7. Checklist:
   - [ ] Worker functions top-level (non metodi)
   - [ ] Ogni fase aggiorna DB
   - [ ] Endpoint `/status` per polling
   - [ ] Thread daemon=True
   - [ ] Scoping superuser vs admin
   - [ ] `created_by` sempre presente
