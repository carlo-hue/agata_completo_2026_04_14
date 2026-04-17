# Import Pipeline Audit - VAST, TESS, ZTF

**Date**: 2026-04-12  
**Status**: Complete audit of 3 import pipelines

---

## Architettura Comune (Tutti e 3)

```
┌─────────────┐
│   User      │ [Route] POST /api/.../create-job
│ Submit Job  │         → Create DB record (state='pending')
│   (UI)      │         → Start background thread
└──────┬──────┘
       │
       ▼
┌──────────────────────────┐
│ Background Thread        │ [Service] execute_job(job_id)
│ execute_job()            │ - Download / Parse / Analyze
│ • Download               │ - Generate results → agata_*_results table
│ • Parse/Analyze          │ - Update job.state = 'completed'
│ • Generate results       │ - db.commit() ← JOB FINISH POINT
│ • Save to DB             │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│ DB Commit (Final)        │ job.state = 'completed'
│ ALL RESULTS SAVED        │ job.completed_at = utcnow()
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│ User Polls Job Status    │ [Route] GET /api/.../jobs/{id}
│ (Every 5 seconds)        │ → Read job.state, progress_pct
│ → Sees "completed"       │ → Read results count (candidates, vars)
│ → Loads Results Table    │ → Direct SQL SELECT on *_results
└──────────────────────────┘
```

---

## VAST Pipeline

### Struttura
- **Service**: `agata/moduli/admin/services/vast_service.py`
- **Executor**: `execute_job(job_id: int)`
- **Launch**: `threading.Thread(target=vast_service.execute_job, args=(job.id,))`
- **Results Table**: `agata_vast_results` (insert durante pipeline)

### Timeline Esecuzione

```
T=0:   POST /api/vast-automation/jobs/create
       → VastJob created (state='pending')
       → Thread started: execute_job()

T=0-N: Background thread processing
       - job.state = 'downloading' (files da Google Drive)
       - job.state = 'validating' (header FITS)
       - job.state = 'vast_analysis' (VAST solver, x-match)
       - INSERT INTO agata_vast_results (... 1000 righe ...)
       
T=N:   job.state = 'uploading'
       
T=N+1: job.state = 'completed'
       job.completed_at = utcnow()
       db.commit()  ← ⭐ TUTTE LE RIGHE VISIBILI DA QUI
       
T=N+5: User polls: GET /api/vast-automation/jobs/{id}
       Response: state='completed', candidates_found=150
       
T=N+10: User wants metriche: SELECT COUNT(*) FROM agata_vast_results 
        WHERE job_id={id}
        → Query runs su dati FRESH (appena salvati)
```

### Code Reference
- **Job completion** ([vast_service.py:688-692](agata/moduli/admin/services/vast_service.py#L688-L692))
- **Results insert** ([vast_service.py:450-700 range](agata/moduli/admin/services/vast_service.py#L450-L700))
- **Route poll** ([vast_automation.py route GET /api/jobs/{id}](agata/moduli/admin/routes/vast_automation.py))

---

## TESS Pipeline

### Struttura
- **Service**: `agata/moduli/admin/services/tess_bulk_import_service.py`
- **Executor**: `execute_job(job_id: int)` → 3 entry points (direct, library, resume)
- **Launch**: `threading.Thread(target=svc.execute_job, args=(job.id,))`
- **Results Table**: `agata_tess_import_results` (insert batch durante pipeline)

### Timeline Esecuzione

```
T=0:   POST /api/tess-bulk-import/jobs/create
       → TessImportJob created (state='pending')
       → Thread started: execute_job()

T=0-N: Background thread
       - job.state = 'downloading' (MAST query)
       - INSERT INTO agata_tess_import_results (file_1)
       - INSERT INTO agata_tess_import_results (file_2)
       - ... batch di 100-1000 file ...
       - job.state = 'analyzing' (variability metrics)
       - job.state = 'crossmatching' (Gaia/VSX)
       
T=N:   UPDATE agata_tess_import_results SET gaia_source_id, vsx_match
       
T=N+1: job.candidates_found = COUNT(*) WHERE is_candidate=True
       job.known_variables_found = COUNT(*) WHERE is_known_variable=True
       job.state = 'completed'
       job.completed_at = utcnow()
       db.commit()  ← ⭐ TUTTE LE RIGHE VISIBILI
       
T=N+5: User polls: GET /api/tess-bulk-import/jobs/{id}
       Response: state='completed', 
                 candidates_found=342,
                 known_variables_found=78
       
T=N+10: User views dashboard (candidates grid):
        SELECT * FROM agata_tess_import_results 
        WHERE job_id={id} AND is_candidate=True
        → Query runs su dati FRESH
```

### Code Reference
- **Job completion** ([tess_bulk_import_service.py:578-582](agata/moduli/admin/services/tess_bulk_import_service.py#L578-L582))
- **Results insert/update** (scattered throughout [tess_bulk_import_service.py](agata/moduli/admin/services/tess_bulk_import_service.py))
- **Route poll** ([tess_bulk_import.py:422-456](agata/moduli/admin/routes/tess_bulk_import.py#L422-L456))

### Batch Insertions Pattern
```python
# Durante download/analyze, salvataggio è iterativo:
for file in files:
    results = analyze_file(file)
    db.add_all([TessImportResult(...) for r in results])
    db.commit()  # ← Commit incrementale
    job.total_processed += len(results)
    db.commit()

# Finale
job.state = 'completed'
db.commit()  # ← Last commit, tutto è salvato
```

---

## ZTF Pipeline

### Struttura
- **Service**: `agata/moduli/admin/services/ztf_survey_service.py`
- **Executor**: `execute_job(job_id: int)`
- **Launch**: `threading.Thread(target=svc.execute_job, args=(job_id,))`
- **Results Table**: `agata_ztf_survey_results` (insert durante pipeline)

### Timeline Esecuzione

```
T=0:   POST /api/ztf-survey/jobs/create
       → ZtfSurveyJob created (state='pending')
       → Thread started: execute_job()

T=0-N: Background thread
       - job.state = 'downloading' (IRSA API queries)
       - job.state = 'analyzing' (variability metrics)
       - INSERT INTO agata_ztf_survey_results (... 500-1000 stelle ...)
       - job.state = 'crossmatching' (Gaia/VSX)
       
T=N:   UPDATE agata_ztf_survey_results SET gaia_source_id, vsx_match
       
T=N+1: job.state = 'completed'
       job.completed_at = utcnow()
       db.commit()  ← ⭐ TUTTE LE RIGHE VISIBILI
       
T=N+5: User polls: GET /api/ztf-survey/jobs/{id}
       Response: state='completed', candidates_found=150, known_vars=45
       
T=N+10: User wants vedere results:
        SELECT * FROM agata_ztf_survey_results 
        WHERE job_id={id} AND is_candidate=True
        → Query runs su dati FRESH
```

### Code Reference
- **Job completion** ([ztf_survey_service.py:424-428](agata/moduli/admin/services/ztf_survey_service.py#L424-L428))
- **Results insert** ([ztf_survey_service.py:300-430 range](agata/moduli/admin/services/ztf_survey_service.py#L300-L430))
- **Route poll** ([ztf_survey.py route GET /api/jobs/{id}](agata/moduli/admin/routes/ztf_survey.py))

---

## Pattern Comune: "Job Polling"

Tutte e 3 i pipeline seguono lo stesso pattern:

### UI → Backend
```javascript
// UI: every 5 seconds while job.state !== 'completed'
fetch('/api/tess-bulk-import/jobs/' + jobId)
  .then(r => r.json())
  .then(data => {
    console.log('State:', data.state);
    console.log('Progress:', data.progress_pct);
    console.log('Candidates:', data.candidates_found);  // ← LETTO DALLA JOB ROW
    
    if (data.state === 'completed') {
      // Stop polling, show results
      loadResultsTable(jobId);
    }
  })
```

### Backend Route Pattern
```python
# All 3 routes (VAST, TESS, ZTF) sono identiche:
@route('/api/{service}/jobs/<int:job_id>', methods=['GET'])
def get_job_status(job_id):
    job = db.query(JobModel).get(job_id)
    return {
        'state': job.state,
        'progress_pct': job.progress_pct,
        'candidates_found': job.candidates_found,  # ← COMPUTED FIELD
        'known_variables_found': job.known_variables_found,  # ← COMPUTED FIELD
    }
```

### Results Table Pattern
```python
# Quando user vede i risultati (dopo state='completed'):
results = db.query(ResultsTable).filter_by(job_id=job_id).all()
# → SELECT * FROM agata_*_results WHERE job_id={id}
# → Scansione full table
```

---

## Insight Chiave: Come Usare il CAGG

### 1. **I campi candidates_found e known_variables_found sono COMPUTED durante la pipeline**

Nel codice:
```python
# TESS (line 576-577)
job.candidates_found = sum(1 for r in results_list if r.get('is_candidate', False))
job.known_variables_found = sum(1 for r in results_list if r.get('is_known_variable', False))
db.commit()
```

**Attualmente**: Ogni volta che user ricarica il job status, reads `job.candidates_found` (1 row query, 1ms).

### 2. **I dati risultati sono SALVATI INCREMENTALMENTE durante la pipeline**

Nel codice:
```python
# TESS
for file in files:
    results = analyze_file(file)
    db.add_all([TessImportResult(...)])
    db.commit()  # ← Commit per ogni batch
```

**Problema**: Se user apre "Results Dashboard" MENTRE la pipeline è ancora in esecuzione:
- T=5 min: Pipeline ha salvato 50K righe
- User query: `SELECT COUNT(*) FROM agata_tess_import_results WHERE job_id={id}`
- → Risultato: 50K (dati parziali!)
- → Ma job.candidates_found=0 (perché crossmatch non finito)

### 3. **QUANDO arrivano i dati "fresh" alla UI**

```
┌─ Job completes (state='completed') ─┐
│  db.commit() saves last batch       │
│ (ALL rows visible to SELECT)         │
└──────────────────────────────────────┘
                │
         T = 2-3 seconds
                │
┌─ User's next poll (GET /api/jobs) ─┐
│  Reads job.candidates_found         │
│  Sees state='completed'              │
│ Loads Results Table (SELECT * ...)   │
└──────────────────────────────────────┘
```

---

## Come Usare il CAGG Correttamente ✅

### Strategia: **Materialized View con On-Demand Refresh**

```sql
-- 1. Creare cagg (dati precomputed)
CREATE MATERIALIZED VIEW tess_job_summary AS
SELECT 
    job_id,
    COUNT(*) AS n_total,
    COUNT(CASE WHEN is_candidate THEN 1 END) AS n_candidates,
    COUNT(CASE WHEN is_known_variable THEN 1 END) AS n_known_vars,
    AVG(stetson_j) AS mean_stetson_j,
    AVG(chi_squared) AS mean_chi_squared
FROM agata_tess_import_results
GROUP BY job_id;

-- 2. Schedule lento (backup)
SELECT add_continuous_aggregate_policy(
    'tess_job_summary',
    schedule_interval => INTERVAL '6 hours'  -- ← Refresh ogni 6 ore
);
```

### Nel Python Service (execute_job):

```python
# File: agata/moduli/admin/services/tess_bulk_import_service.py

def execute_job(self, job_id: int):
    try:
        # ... pipeline processing ...
        
        # Step finale: job.state = 'completed'
        job.state = 'completed'
        job.progress_pct = 100
        job.completed_at = datetime.utcnow()
        db.commit()
        
        # ⭐ NEW: Force refresh cagg subito
        self._refresh_cagg_metrics(db, job_id)
        
        logger.info(f"Job {job.job_code} completed")
        
    except Exception as e:
        # ... error handling ...

def _refresh_cagg_metrics(self, db, job_id: int):
    """Refresh materialized views dopo job completion."""
    try:
        # Option 1: Refresh just this job's data window
        db.session.execute(text("""
            CALL refresh_continuous_aggregate(
                'tess_job_summary',
                CURRENT_TIMESTAMP - INTERVAL '1 day',
                CURRENT_TIMESTAMP
            )
        """))
        db.session.commit()
        logger.info(f"Refreshed tess_job_summary for job {job_id}")
        
    except Exception as e:
        logger.warning(f"Could not refresh cagg: {e}")
        # Non fallisce il job se cagg refresh fallisce
```

### Route di Polling (rimane uguale):

```python
# File: agata/moduli/admin/routes/tess_bulk_import.py

@admin_bp.route('/api/tess-bulk-import/jobs/<int:job_id>', methods=['GET'])
@login_required
def api_get_tess_bulk_import_job(job_id):
    """Stato job per polling UI."""
    job = db.query(TessImportJob).get(job_id)
    
    # Se job è completed, leggi metriche da cagg (istantaneo, cached)
    if job.state == 'completed':
        # OPZIONE 1: Leggi da cagg (fast)
        metrics = db.session.execute(text("""
            SELECT n_candidates, n_known_vars, mean_stetson_j, mean_chi_squared
            FROM tess_job_summary
            WHERE job_id = :job_id
        """), {'job_id': job_id}).first()
        
        if metrics:
            return {
                'state': 'completed',
                'candidates_found': metrics[0],
                'known_variables_found': metrics[1],
                'mean_stetson_j': metrics[2],
                'mean_chi_squared': metrics[3],
            }
    
    # Se job in esecuzione, leggi da job row (sempre 1ms)
    return {
        'state': job.state,
        'progress_pct': job.progress_pct,
        'candidates_found': job.candidates_found,  # Computed field
        'known_variables_found': job.known_variables_found,
    }
```

---

## Benefici di Questo Approccio

### **Dati Sempre Fresh** ✅
- Dopo `db.commit()` al job completion → cagg refresh immediately
- User NON vede dati stale (no 1-3 hour delay)

### **Zero Downtime** ✅
- Cagg refresh è non-blocking (bg operation)
- Query SELECT non si bloccano

### **Scalabilità** ✅
- 5M TESS rows: CAGG è 1 riga per job (instant queries)
- Senza cagg: GROUP BY su 5M rows = 1-2s

### **Fallback Sicuro** ✅
- Se `_refresh_cagg_metrics()` fallisce → job è comunque completato
- Schedule ogni 6 ore aggiusta il cagg se refresh on-demand fallì

---

## Implementation Checklist

### Fase 1: Create Caggs (SQL)
- [ ] `CREATE MATERIALIZED VIEW tess_job_summary` + policy
- [ ] `CREATE MATERIALIZED VIEW vast_job_summary` + policy
- [ ] `CREATE MATERIALIZED VIEW ztf_job_summary` + policy

### Fase 2: Add Refresh Logic (Python)
- [ ] Add `_refresh_cagg_metrics()` method to TessService
- [ ] Add `_refresh_cagg_metrics()` method to VastService
- [ ] Add `_refresh_cagg_metrics()` method to ZtfService
- [ ] Call in execute_job() before final commit

### Fase 3: Update Routes (Poll)
- [ ] Update TESS poll route to read from cagg if completed
- [ ] Update VAST poll route to read from cagg if completed
- [ ] Update ZTF poll route to read from cagg if completed

### Fase 4: Test
- [ ] Create small job, verify cagg refreshes
- [ ] Create large job (1M rows), verify still fresh
- [ ] Disconnect DB during refresh, verify graceful fallback
- [ ] Monitor cagg staleness (continuous_aggs_materialization_invalidation_log)

---

## Summary: Il CAGG Funziona Bene Qui Perché...

1. **Dati sono salvati in batch**, non row-by-row
2. **Job completion è un punto singolo** (state='completed' + db.commit)
3. **Refresh on-demand è semplice** (CALL refresh dopo commit)
4. **User aspetta comunque** il polling refresh (5s), 100ms in più per cagg = invisibile
5. **Scale with time**: Domani 5M rows → cagg è 1 riga (3 bytes) vs full GROUP BY (1-2s)

Non sei "bloccato" dagli aggregati. Sei solo **massimizzando il valore** con refresh on-demand.

