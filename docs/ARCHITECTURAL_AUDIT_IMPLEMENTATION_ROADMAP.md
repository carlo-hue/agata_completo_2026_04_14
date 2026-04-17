# AGATA Architettura — Roadmap Implementazione

**Documento**: Guida pratica per risolvere i tre problemi critici dell'audit architetturale.
**Data**: 2026-03-06
**Versione**: 1.0

---

## Sommario Esecutivo

L'audit ha identificato **3 problemi critici** che bloccheranno la crescita della piattaforma:

1. **Database session lifecycle è manuale e fragile** (124 `SessionLocal()` sparsi senza `finally` garantiti)
2. **Background jobs non hanno persistenza** (thread daemon che muoiono al restart)
3. **Inversione di dipendenze** (servizi importano da route)

Questo documento fornisce una roadmap implementativa per risolverli in ordine di priorità.

---

## FASE 1: Fix Immediati (1-2 settimane)

Questi fix richiedono poco sforzo e risolvono rischi immediati.

### 1.1 Context Manager per DB Sessions

**Problema**: `SessionLocal()` discariche senza `finally` causano connection leak.

**Soluzione**:

```python
# agata/db.py — aggiungere questo
from contextlib import contextmanager

@contextmanager
def get_db():
    """Context manager per SQLAlchemy sessions.

    Garantisce che la sessione sia sempre chiusa, anche in caso di eccezione.

    Usage:
        with get_db() as db:
            project = db.query(Project).filter_by(id=1).first()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Impatto**: Elimina connection leaks. Con MySQL che ha default 10-100 connessioni, questo previene `OperationalError: too many connections` sotto carico.

**Checklist di implementazione**:
- [x] Aggiungere `get_db()` a `agata/db.py` ✅ 2026-03-06
- [x] Verificare tutti i `db.close()` nel codebase — analisi AST automatica conferma solo 1 bug reale ✅ 2026-03-06
- [x] Corretto bug reale in `ztf_survey.py:api_delete_ztf_survey_job` (db.close() nel try invece del finally) ✅ 2026-03-06
- [ ] Test: caricare 50 stelle contemporaneamente, verificare connection count non cresce indefinitamente

**Note post-implementazione**: La codebase era più solida del previsto. La maggior parte dei file usava già `try/finally` correttamente. Il `get_db()` è ora disponibile per tutti i nuovi file.

**Tempo stimato**: 2 ore

---

### 1.2 Muovi `_upsert_star_photometry` dalla Route al Service

**Problema**: `vast_service.py` e `ztf_survey_service.py` importano da `routes/stars_catalog.py`.
Questo viola la layering (service → route è invertito).

**Soluzione**:

```python
# agata/admin/services/star_service.py — NUOVO FILE
"""
Service per operazioni su stelle nel catalogo locale.
"""
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def upsert_star_photometry(db: Session, gaia_id: str) -> None:
    """
    Recalcola e UPSERT agata_star dalla fotometria live.

    Chiamato dopo ogni import fotometrico per aggiornare la cache di riepilogo.
    Non solleva eccezioni — wrappato in try/except per proteggere il caller.

    Args:
        db: SQLAlchemy session
        gaia_id: Gaia DR3 source ID (stringa o int)
    """
    try:
        gaia_id = str(gaia_id).strip()
        gaia_id_int = int(gaia_id)

        # Query di riepilogo dalla fotometria importata
        row = db.execute(text("""
            SELECT
                COUNT(*) as total_points,
                COUNT(DISTINCT catalogo) as num_catalogs,
                GROUP_CONCAT(DISTINCT catalogo ORDER BY catalogo SEPARATOR ',') as catalogs,
                MIN(hjd) as min_hjd,
                MAX(hjd) as max_hjd,
                MIN(Vmag) as min_mag,
                MAX(Vmag) as max_mag,
                MAX(catalog_import_id) as latest_import_id
            FROM agata_star_photometry
            WHERE Source = :gaia_id_int
            GROUP BY Source
        """), {'gaia_id_int': gaia_id_int}).fetchone()

        if not row or not row.total_points:
            return

        # [resto della logica da stars_catalog.py:38-80]
        imported_at = None
        if row.latest_import_id:
            imp = db.execute(text(
                "SELECT created_at FROM agata_catalog_imports WHERE id = :iid"
            ), {'iid': row.latest_import_id}).fetchone()
            if imp:
                imported_at = imp.created_at

        db.execute(text("""
            INSERT INTO agata_star
                (gaia_id, total_points, num_catalogs, catalogs,
                 min_hjd, max_hjd, min_mag, max_mag,
                 latest_import_id, last_imported_at,
                 created_at, updated_at)
            VALUES (...)
            ON DUPLICATE KEY UPDATE ...
        """), {...})

        db.commit()
        logger.info(f"Star {gaia_id} photometry updated: {row.total_points} points from {row.num_catalogs} catalogs")

    except Exception as e:
        logger.error(f"Failed to upsert star photometry for {gaia_id}: {e}")
        # Non propagare — questo non è un errore critico
```

Poi nei service che lo usano:

```python
# agata/admin/services/vast_service.py (line 33 attuale)
# PRIMA: from agata.admin.routes.stars_catalog import _upsert_star_photometry
# DOPO:
from agata.admin.services.star_service import upsert_star_photometry

# Cambio nel codice:
# _upsert_star_photometry(db, gaia_id) → upsert_star_photometry(db, gaia_id)
```

**Impatto**: Separa business logic da HTTP layer, rende il codice testabile.

**Checklist**:
- [x] Creare `agata/admin/services/star_service.py` ✅ 2026-03-06
- [x] Copiare `upsert_star_photometry` da `stars_catalog.py` ✅ 2026-03-06
- [x] Aggiornare import in `vast_service.py` ✅ 2026-03-06
- [x] Aggiornare import in `ztf_survey_service.py` ✅ 2026-03-06
- [x] Rimosso corpo funzione da `stars_catalog.py` (rimane alias `_upsert_star_photometry` → service) ✅ 2026-03-06
- [ ] Test: run VAST import, verificare agata_star sia aggiornata

**Tempo stimato**: 1 ora

---

### 1.3 Cache Git Info al Startup

**Problema**: Il context processor `inject_app_info()` esegue due `subprocess.check_output(['git', ...])` su ogni request.
Questo aggiunge 50-100ms per pagina e spawna due processi a request.

**Soluzione**:

```python
# app.py — sostituisci le righe 223-249

import subprocess
import logging

logger = logging.getLogger(__name__)

# Computa una volta al startup
_GIT_COMMIT = "unknown"
_GIT_TAG = "unknown"

try:
    _GIT_COMMIT = subprocess.check_output(
        ['git', 'rev-parse', '--short', 'HEAD'],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        stderr=subprocess.DEVNULL
    ).decode().strip()
except Exception as e:
    logger.warning(f"Could not get git commit: {e}")

try:
    _GIT_TAG = subprocess.check_output(
        ['git', 'describe', '--tags'],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        stderr=subprocess.DEVNULL
    ).decode().strip()
except Exception as e:
    logger.warning(f"Could not get git tag: {e}")

@app.context_processor
def inject_app_info():
    """Inject app version and git info into all templates."""
    from agata import __version__
    return dict(
        app_version=__version__,
        git_commit=_GIT_COMMIT,
        git_tag=_GIT_TAG
    )
```

**Impatto**: Riduce latenza pagina di 50-100ms, elimina 2 processi a request.

**Checklist**:
- [x] Spostato calcolo git in `_get_git_info()` a livello modulo, eseguito una volta al startup ✅ 2026-03-06
- [x] `inject_app_info()` ridotto a 4 righe, legge `_GIT_COMMIT`/`_GIT_TAG` già calcolati ✅ 2026-03-06
- [ ] Test: caricare pagina, misurare latenza (deve diminuire)

**Tempo stimato**: 30 minuti

---

### 1.4 Aggiungi Indici SQLAlchemy ai Modelli

**Problema**: Le query critiche non hanno indici dichiarati in codice.
Una tabella creata da zero skipperebbe gli indici; schema migrations non sanno cosa creare.

**Soluzione**:

```python
# agata/auth_models/project.py
from sqlalchemy import Index

class Project(Base):
    __tablename__ = "agata_projects"

    # ... campi ...

    __table_args__ = (
        Index('idx_projects_assoc_state', 'association_id', 'state'),
        Index('idx_projects_gaia_id', 'gaia_id'),
        Index('idx_projects_assigned_to', 'assigned_to'),
    )
```

```python
# agata/auth_models/vast_job.py
class VastJob(Base):
    __tablename__ = "agata_vast_jobs"

    # ... campi ...

    __table_args__ = (
        Index('idx_vast_jobs_assoc_state', 'association_id', 'state'),
        Index('idx_vast_jobs_created', 'created_at'),
    )

class VastResult(Base):
    __tablename__ = "agata_vast_results"

    # ... campi ...

    __table_args__ = (
        Index('idx_vast_results_job_id', 'job_id'),
        Index('idx_vast_results_gaia', 'gaia_source_id'),
    )
```

```python
# agata/auth_models/ztf_survey_job.py
class ZtfSurveyJob(Base):
    __tablename__ = "agata_ztf_survey_jobs"

    # ... campi ...

    __table_args__ = (
        Index('idx_ztf_survey_assoc', 'association_id'),
        Index('idx_ztf_survey_state', 'state'),
    )

class ZtfSurveyResult(Base):
    __tablename__ = "agata_ztf_survey_results"

    # ... campi ...

    __table_args__ = (
        Index('idx_ztf_results_job_id', 'job_id'),
        Index('idx_ztf_results_gaia', 'gaia_source_id'),
    )
```

**Applica gli indici al database**:

```bash
# Nel database, se non esistono già:
mysql> CREATE INDEX idx_projects_assoc_state ON agata_projects(association_id, state);
mysql> CREATE INDEX idx_projects_gaia_id ON agata_projects(gaia_id);
# etc...
```

**Checklist**:
- [x] Aggiungere `__table_args__` a Project, VastJob, VastResult, ZtfSurveyJob, ZtfSurveyResult ✅ 2026-03-06
- [x] Creato `docs/migrations/003_add_model_indexes.sql` con tutti gli indici (16 indici su 5 tabelle) ✅ 2026-03-06
- [ ] Applicare la migration al database: `mysql -u <user> -p <db> < docs/migrations/003_add_model_indexes.sql`
- [ ] Verificare con `SHOW INDEX FROM agata_projects` che gli indici siano presenti
- [ ] Test: `EXPLAIN SELECT * FROM agata_projects WHERE association_id=1 AND state='assigned'` deve usare idx_projects_association_state

**Indici aggiunti**:
| Tabella | Indice | Colonne |
|---------|--------|---------|
| agata_projects | idx_projects_association_state | association_id, state |
| agata_projects | idx_projects_gaia_id | gaia_id |
| agata_projects | idx_projects_assigned_to | assigned_to |
| agata_projects | idx_projects_created_at | created_at |
| agata_vast_jobs | idx_vast_jobs_state | state |
| agata_vast_jobs | idx_vast_jobs_requested_by | requested_by |
| agata_vast_jobs | idx_vast_jobs_created_at | created_at |
| agata_vast_results | idx_vast_results_job_id | job_id |
| agata_vast_results | idx_vast_results_gaia_source_id | gaia_source_id |
| agata_vast_results | idx_vast_results_flags | job_id, is_valid, is_candidate |
| agata_ztf_survey_jobs | idx_ztf_jobs_association_state | association_id, state |
| agata_ztf_survey_jobs | idx_ztf_jobs_created_by | created_by |
| agata_ztf_survey_jobs | idx_ztf_jobs_created_at | created_at |
| agata_ztf_survey_results | idx_ztf_results_job_id | job_id |
| agata_ztf_survey_results | idx_ztf_results_gaia_source_id | gaia_source_id |
| agata_ztf_survey_results | idx_ztf_results_flags | job_id, is_candidate, is_valid |

**Tempo stimato**: 2 ore (1 ora codice, 1 ora testing e verifica)

---

## FASE 2: Refactoring Architetturale (2-4 settimane)

### 2.1 Integra Celery per Background Jobs

**Problema**: VAST e ZTF job lanciano thread daemon che muoiono al restart del server.
Non c'è recovery — il job rimane stuck a `downloading`.

**Soluzione**: Usa Celery + Redis (Redis è già deployed).

#### 2.1.1 Setup Celery

```python
# agata/celery_app.py — NUOVO FILE
"""
Celery app per task asincroni (VAST, ZTF, etc).
"""
import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

app = Celery(__name__)
app.conf.update(
    broker_url=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    result_backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 min hard timeout
    task_soft_time_limit=25 * 60,  # 25 min soft timeout
)
```

```python
# agata/admin/services/vast_task.py — NUOVO FILE
"""
Celery task per VAST pipeline.
"""
from celery import shared_task
from agata.celery_app import app
from agata.db import SessionLocal
from agata.auth_models import VastJob
from agata.admin.services.vast_service import VastService
import logging

logger = logging.getLogger(__name__)

@app.task(bind=True)
def run_vast_pipeline(self, job_id: int):
    """
    Celery task per eseguire pipeline VAST.

    self.update_state() permette di aggiornare stato in Redis in real-time.
    """
    db = SessionLocal()
    try:
        job = db.query(VastJob).filter_by(id=job_id).first()
        if not job:
            logger.error(f"VastJob {job_id} not found")
            return {'success': False, 'error': 'Job not found'}

        service = VastService()
        result = service.run_pipeline(job_id=job_id)

        return {
            'success': True,
            'job_id': job_id,
            'results': result
        }
    except Exception as e:
        logger.exception(f"VAST pipeline failed for job {job_id}")
        return {
            'success': False,
            'job_id': job_id,
            'error': str(e)
        }
    finally:
        db.close()
```

#### 2.1.2 Aggiorna Route per Lanciare Task

```python
# agata/admin/routes/vast_automation.py — sostituisci line 79-81
@admin_bp.route('/api/vast/jobs', methods=['POST'])
@login_required
@superuser_required
@audit_action('vast_job_created', 'vast_job')
def api_create_vast_job():
    """Crea e lancia un nuovo job VAST."""
    # ... validazione ...

    # PRIMA: thread = threading.Thread(...) ; thread.start()
    # DOPO:
    from agata.admin.services.vast_task import run_vast_pipeline

    task = run_vast_pipeline.delay(job.id)  # Non-blocking, torna subito

    return jsonify({
        'success': True,
        'job_id': job.id,
        'task_id': task.id,  # Per tracciare progress
        'message': f"Job {job.job_code} queued for processing"
    }), 201
```

#### 2.1.3 UI per Monitorare Progress

La UI può fare polling su `/api/vast/jobs/{job_id}/status` che legge `job.state`, `job.progress_pct`, `job.current_step` dal DB aggiornati dal task.

**Impatto**: Job survives server restart, può essere ripreso se fallisce, stato è persistente.

**Checklist**:
- [ ] Installare Celery: `pip install celery`
- [ ] Creare `agata/celery_app.py`
- [ ] Creare `agata/admin/services/vast_task.py` e `ztf_task.py`
- [ ] Aggiornare route per lanciare task invece di thread
- [ ] Testare: creare job, restart gunicorn, verificare job non scompaia
- [ ] Lanciare worker: `celery -A agata.celery_app worker --loglevel=info`

**Tempo stimato**: 3-5 giorni

---

### 2.2 Centralizza Association Scoping

**Problema**: La logica `if not is_superuser: query = query.filter(association_id == ...)` è copy-pasted in 40+ route file con varianti diverse.

**Analisi reale (2026-03-06)**: Un decorator generico che modifica le query non è fattibile perché le 40+ occorrenze hanno pattern diversi:
1. `if role != 'superuser': query.filter(X.association_id == user.association_id)` — lista
2. `if role != 'superuser' and record.requested_by != user.id` — ownership individuale
3. `auto_create_project = role != 'superuser'` — flag di comportamento
4. Filtri su colonne diverse (`association_id` vs `requested_by`)

Un decorator che cerca di coprire tutti i casi diventa più complesso della logica che sostituisce.

**Soluzione adottata**: Due helper functions in `decorators.py` che centralizzano la logica senza toccare le route:

```python
# agata/admin/decorators.py — AGGIUNTO

def get_scoped_association_id() -> int | None:
    """
    Ritorna l'association_id per filtrare le query.
    - Superuser: None (vede tutto)
    - Altri: current_user.association_id
    """
    if current_user.role == 'superuser':
        return None
    return current_user.association_id


def is_own_association(association_id: int) -> bool:
    """
    True se l'utente può accedere a questa associazione.
    - Superuser: sempre True
    - Altri: True solo se coincide con la propria
    """
    if current_user.role == 'superuser':
        return True
    return current_user.association_id == association_id
```

Uso nelle route (quando si refactora):

```python
from agata.admin.decorators import get_scoped_association_id, is_own_association

# Lista (filtra automaticamente per associazione)
association_id = get_scoped_association_id()
query = db.query(ZtfSurveyJob)
if association_id is not None:
    query = query.filter(ZtfSurveyJob.association_id == association_id)

# Dettaglio (verifica accesso)
if not is_own_association(job.association_id):
    return jsonify({'error': 'Accesso negato'}), 403
```

**Impatto**: La logica vive in un posto, è testabile, le route restano invariate finché non vengono refactorate individualmente.

**Checklist**:
- [x] Aggiunto `get_scoped_association_id()` a `decorators.py` ✅ 2026-03-06
- [x] Aggiunto `is_own_association()` a `decorators.py` ✅ 2026-03-06
- [ ] Refactorare route progressivamente quando si tocca un file per altri motivi
- [ ] Test: admin accede a 2 associazioni diverse, vede solo la propria
- [ ] Test: superuser accede a tutto

**Nota**: Non riscrivere tutte le 40 route in un colpo solo — rischio troppo alto. Adottare le due helper functions gradualmente file per file.

**Tempo stimato**: implementazione base 30 min (fatto) + adozione graduale nelle route

---

### 2.3 Unifica Decorator Admin e Auth

**Problema**: Due implementazioni di `admin_required` e `superuser_required`:
- `agata/auth/decorators.py` — flat list check
- `agata/admin/decorators.py` — numeric hierarchy

**Soluzione**: Mantieni la versione admin (è più corretta), rimuovi la versione auth:

```python
# agata/auth/decorators.py — rimuovi admin_required e superuser_required

# Sostituisci con import da admin:
from agata.admin.decorators import admin_required, superuser_required

__all__ = ['login_required', 'require_role', 'require_permission', 'admin_required', 'superuser_required']
```

**Impatto**: Un'unica fonte di verità per RBAC.

**Checklist**:
- [ ] Rimuovere le definizioni duplicate da `auth/decorators.py`
- [ ] Importare da `admin/decorators.py`
- [ ] Verificare che tutti i decorator abbiano il comportamento atteso
- [ ] Test: verificare che `@admin_required('analyst')` funzioni in tutti i contesti

**Tempo stimato**: 2 ore

---

## FASE 3: Evoluzioni Architetturale (3-6 mesi)

Questi step richiedono significative riscritture e dovrebbero essere schedulati per il futuro.

### 3.1 Adotta Flask-SQLAlchemy

Sostituire manuale `SessionLocal()` con una integrazione Flask nativa.

```python
# app.py
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy(app)
```

Poi nei route:

```python
from agata import db

@route('/projects')
def list_projects():
    projects = db.session.query(Project)...
    # db.session è auto-gestito per la request
```

**Benefici**:
- Session lifecycle gestito automaticamente per HTTP request
- Integrazione con Flask testing
- Meno boilerplate

**Tempo stimato**: 5-10 giorni

---

### 3.2 Aggiungi Alembic per Schema Migrations

Attualmente i cambi schema sono manuali. Alembic rende le migrazioni versionabili.

```bash
pip install alembic
alembic init migrations
```

Poi:

```bash
# Dopo ogni modifica al modello SQLAlchemy:
alembic revision --autogenerate -m "add index to projects"
alembic upgrade head
```

**Benefici**:
- Reproducible schema across environments
- Easy rollback
- Version control per schema changes

**Tempo stimato**: 3-5 giorni

---

### 3.3 Refactoring Physical Data in Project

Separate `ProjectPhysics` table:

```python
class ProjectPhysics(Base):
    __tablename__ = "agata_project_physics"

    project_id = ForeignKey("agata_projects.id")

    # Stored as FLOAT, not String
    teff_k: Optional[float]
    distance_pc: Optional[float]
    radius_solar: Optional[float]

    # Provenance tracking
    teff_source: Optional[str]  # "Gaia DR3", "VSX", etc.
    distance_source: Optional[str]
    # ... etc

    last_updated: datetime
```

**Benefici**:
- Queryable numerically
- Proper provenance tracking
- Separation of concerns

---

### 3.4 Refactor `dati_stelle` → `agata_star_photometry`

Migrate legacy table:

```sql
-- Creare mapping tra vecchia e nuova schema
INSERT INTO agata_star_photometry
  (Source, catalogo, hjd, Vmag, catalog_import_id)
SELECT
  CAST(GAIAID AS BIGINT),
  'LEGACY_dati_stelle',
  JDT,
  mag,
  NULL  -- No import_id for legacy data
FROM dati_stelle
WHERE GAIAID NOT IN (SELECT DISTINCT Source FROM agata_star_photometry);
```

Poi rimuovere UNION in `db_loader.py`.

---

## Tracking e Metriche

Per monitorare progresso:

| Task | Status | ETA | Owner |
|------|--------|-----|-------|
| Context manager DB | ⬜ | Settimana 1 | |
| Star service | ⬜ | Settimana 1 | |
| Git cache | ⬜ | Settimana 1 | |
| Indici SQLAlchemy | ⬜ | Settimana 1 | |
| Celery integration | ⬜ | Settimana 2-4 | |
| Association scope | ⬜ | Settimana 2 | |
| Decorator unify | ⬜ | Settimana 2 | |

---

## Risorse Addizionali

- Audit completo: [AUDIT_ARCHITECTURE_DETAILED.md](./AUDIT_ARCHITECTURE_DETAILED.md)
- Celery docs: https://docs.celeryproject.org/
- SQLAlchemy best practices: https://docs.sqlalchemy.org/
- Flask-SQLAlchemy: https://flask-sqlalchemy.palletsprojects.com/

---

**Prossimo step**: Schedulare Fase 1 (fix immediati) per questa settimana. Richiede ~5-6 ore di sviluppo.
