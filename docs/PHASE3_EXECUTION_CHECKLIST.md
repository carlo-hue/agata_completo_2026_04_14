# PHASE 3 Execution Checklist - Quick Reference

**Estimated Total Time**: 12-14 hours  
**Break it into**:
- SQL (1-2h) → Test on staging
- Code changes (6-8h) → Python + routes
- Testing (2-3h) → All entry points
- Deployment (1h) → Prod + monitoring

---

## ✅ PART 1: Database Migration (1-2 hours)

### [ ] 1.1 Create Migration File

```bash
# Create new file
cat > /var/www/astrogen/docs/migrations/pg/pg_013_hypertable_optimization_phase3.sql << 'EOF'
-- [Copy entire SQL from PHASE3_IMPLEMENTATION_PLAN.md "Step 1"]
EOF
```

### [ ] 1.2 Test on Staging (if available)

```bash
# SSH to staging DB
psql -h <staging-host> -U <user> -d catalogo < docs/migrations/pg/pg_013_hypertable_optimization_phase3.sql

# Verify (should see 4 hypertables + 7 cagg views)
psql -h <staging-host> -U <user> -d catalogo -c "
SELECT * FROM timescaledb_information.hypertables WHERE hypertable_name LIKE 'agata_%';
SELECT * FROM timescaledb_information.continuous_aggregates;
"
```

### [ ] 1.3 Dry Run: Test with small dataset

```bash
# In staging: Create small job (100 results) and verify cagg refreshes
psql -c "
SELECT * FROM tess_job_summary WHERE job_id = (SELECT id FROM agata_tess_import_jobs ORDER BY id DESC LIMIT 1);
"
# Should see 1 row with metrics (if job completed)
```

---

## ✅ PART 2: Python Code Changes (6-8 hours)

### [ ] 2.1 Create CaggRefreshMixin

**File**: `/var/www/astrogen/agata/moduli/admin/services/cagg_refresh_helper.py` (NEW)

```bash
# Copy entire code from PHASE3_IMPLEMENTATION_PLAN.md "Step 2"
```

### [ ] 2.2 Update VAST Service

**File**: `/var/www/astrogen/agata/moduli/admin/services/vast_service.py`

```python
# 1. Add import at top (after existing imports)
from agata.moduli.admin.services.cagg_refresh_helper import CaggRefreshMixin

# 2. Update class declaration (around line 100)
class VastOrchestrator(CaggRefreshMixin):  # ← Add mixin

# 3. Add refresh call in execute_job() (around line 692, after db.commit())
# Find: job.state = 'completed' ... db.commit()
# Add after:   self.refresh_cagg_for_table(db, 'agata_vast_results', 'vast_job_summary')
```

**Quick edit command**:
```bash
# Find exact line
grep -n "job.state = 'completed'" /var/www/astrogen/agata/moduli/admin/services/vast_service.py | grep 688

# Then manually edit OR use sed:
sed -i '692 a\            # Force refresh cagg immediately\n            self.refresh_cagg_for_table(db, '\''agata_vast_results'\'', '\''vast_job_summary'\'')' /var/www/astrogen/agata/moduli/admin/services/vast_service.py
```

### [ ] 2.3 Update TESS Service

**File**: `/var/www/astrogen/agata/moduli/admin/services/tess_bulk_import_service.py`

```python
# 1. Add import at top
from agata.moduli.admin.services.cagg_refresh_helper import CaggRefreshMixin

# 2. Update class declaration (around line 50)
class TessImportService(CaggRefreshMixin):  # ← Add mixin

# 3. Add refresh call in execute_job() (around line 582, after db.commit())
# Find: job.state = 'completed' ... db.commit()
# Add after:   self.refresh_cagg_for_table(db, 'agata_tess_import_results', 'tess_job_summary')
```

### [ ] 2.4 Update ZTF Service

**File**: `/var/www/astrogen/agata/moduli/admin/services/ztf_survey_service.py`

```python
# 1. Add import at top
from agata.moduli.admin.services.cagg_refresh_helper import CaggRefreshMixin

# 2. Update class declaration
class ZtfSurveyService(CaggRefreshMixin):  # ← Add mixin

# 3. Add refresh call in execute_job() (around line 428, after db.commit())
# Add after:   self.refresh_cagg_for_table(db, 'agata_ztf_survey_results', 'ztf_job_summary')
```

### [ ] 2.5 Update Catalog Import Service (Editor)

**File**: `/var/www/astrogen/agata/moduli/admin/services/catalog_import_service.py`

```python
# 1. Add import at top
from agata.moduli.admin.services.cagg_refresh_helper import CaggRefreshMixin

# 2. In import_selected_data() function, find line ~350 (after final db.commit())
# Add:
"""
# Refresh star_photometry cagg after import
try:
    CaggRefreshMixin.refresh_star_photometry_cagg(db)
except Exception as e:
    logger.warning(f"Could not refresh photometry cagg: {e}")
"""
```

---

## ✅ PART 3: Route Updates (2 hours) - OPTIONAL but Recommended

### [ ] 3.1 Update TESS Poll Route

**File**: `/var/www/astrogen/agata/moduli/admin/routes/tess_bulk_import.py`

Find function `api_get_tess_bulk_import_job` (around line 422)

Replace the response building section with code from PHASE3_IMPLEMENTATION_PLAN.md "Step 7"

### [ ] 3.2 Update VAST Poll Route

**File**: `/var/www/astrogen/agata/moduli/admin/routes/vast_automation.py`

Same pattern, find `api_get_vast_job` endpoint

### [ ] 3.3 Update ZTF Poll Route

**File**: `/var/www/astrogen/agata/moduli/admin/routes/ztf_survey.py`

Same pattern, find `api_get_ztf_job` endpoint

---

## ✅ PART 4: Testing (2-3 hours)

### [ ] 4.1 Syntax Check

```bash
cd /var/www/astrogen

# Check Python syntax
python -m py_compile agata/moduli/admin/services/cagg_refresh_helper.py
python -m py_compile agata/moduli/admin/services/vast_service.py
python -m py_compile agata/moduli/admin/services/tess_bulk_import_service.py
python -m py_compile agata/moduli/admin/services/ztf_survey_service.py
python -m py_compile agata/moduli/admin/services/catalog_import_service.py

# All should complete silently (no output = no errors)
```

### [ ] 4.2 Unit Tests

```bash
# If you have tests for these services:
pytest agata/moduli/admin/services/test_vast_service.py
pytest agata/moduli/admin/services/test_tess_service.py
pytest agata/moduli/admin/services/test_ztf_service.py
```

### [ ] 4.3 Manual Integration Test - TESS Import

1. SSH to dev server
2. Create small TESS import job (50-100 files)
3. Monitor logs:
   ```bash
   tail -f /var/log/astrogen/app.log | grep -i "tess\|cagg\|refresh"
   ```
4. Expected in logs:
   ```
   [TessImportService] Pipeline completata
   [CaggRefreshMixin] Refreshed cagg 'tess_job_summary'
   ```
5. Check DB directly:
   ```bash
   psql -c "SELECT * FROM tess_job_summary WHERE job_id = <job_id>;"
   # Should see 1 row with metrics
   ```

### [ ] 4.4 Manual Integration Test - VAST

1. Create small VAST job (10-20 images)
2. Monitor logs for cagg refresh
3. Check: `SELECT * FROM vast_job_summary WHERE job_id = <job_id>;`

### [ ] 4.5 Manual Integration Test - ZTF

1. Create small ZTF survey job
2. Monitor logs
3. Check: `SELECT * FROM ztf_job_summary WHERE job_id = <job_id>;`

### [ ] 4.6 Manual Integration Test - Editor Cataloghi Import

1. Open variable_stars editor
2. Go to "📥 Import Cataloghi" tab
3. Search for a star (e.g., Betelgeuse)
4. Import 2-3 catalogs (TESS QLp, ZTF, Gaia)
5. Monitor logs for photometry cagg refresh
6. Check DB:
   ```bash
   psql -c "SELECT COUNT(*) FROM agata_star_photometry WHERE source_id = <gaia_id>;"
   # Should see increasing count as import progresses
   ```

### [ ] 4.7 Cagg Staleness Monitor

```bash
# Check if cagg is getting stale
psql -c "
SELECT 
    view_name,
    materialization_hypertable_name,
    last_time_bucket
FROM timescaledb_information.continuous_aggregates;
"

# All last_time_bucket should be recent (within last hour)
```

### [ ] 4.8 Performance Baseline

Before deploying to prod, capture baseline:

```bash
# Create script to measure
cat > measure_perf.sh << 'EOF'
#!/bin/bash
echo "=== Cagg Query Performance ==="
time psql -c "SELECT * FROM tess_job_summary WHERE job_id = 999;" > /dev/null
time psql -c "SELECT * FROM vast_job_summary WHERE job_id = 888;" > /dev/null
time psql -c "SELECT * FROM ztf_job_summary WHERE job_id = 777;" > /dev/null

echo "=== Photometry Multi-Level Cagg ==="
time psql -c "SELECT * FROM phot_daily_summary WHERE source_id = 5354257804967066624 LIMIT 10;" > /dev/null
time psql -c "SELECT * FROM phot_monthly_summary WHERE source_id = 5354257804967066624;" > /dev/null
EOF

chmod +x measure_perf.sh
./measure_perf.sh
# All queries should complete in < 100ms
```

---

## ✅ PART 5: Production Deployment (1 hour)

### [ ] 5.1 Backup Database

```bash
# On production (astrogen03)
ssh astrogen@10.1.0.6
pg_dump -h <db-host> -U <user> catalogo | gzip > /backups/catalogo_pre_phase3_$(date +%Y%m%d_%H%M%S).sql.gz
# Verify size: ls -lh /backups/catalogo_pre_phase3_*.sql.gz
```

### [ ] 5.2 Apply Migration

```bash
# SSH to production and run migration
psql -h <db-host> -U <user> -d catalogo < /var/www/astrogen/docs/migrations/pg/pg_013_hypertable_optimization_phase3.sql

# Expected output: (no errors, multiple CREATE MATERIALIZED VIEW IF NOT EXISTS ... notices)
```

### [ ] 5.3 Verify Hypertables + CAGG Created

```bash
psql -h <db-host> -U <user> -d catalogo << EOF
SELECT hypertable_name, chunk_interval FROM timescaledb_information.hypertables 
WHERE hypertable_name IN ('agata_vast_results', 'agata_ztf_survey_results', 'agata_tess_import_results', 'agata_star_photometry')
ORDER BY hypertable_name;

SELECT view_name FROM timescaledb_information.continuous_aggregates 
WHERE view_name IN ('vast_job_summary', 'ztf_job_summary', 'tess_job_summary', 'phot_hourly_summary', 'phot_daily_summary', 'phot_monthly_summary')
ORDER BY view_name;
EOF
```

### [ ] 5.4 Deploy Code

```bash
cd /var/www/astrogen
git add -A
git commit -m "Phase 3: Hypertable optimization + continuous aggregates + on-demand refresh"
git push origin main

# Tag release
git tag -a v3.1.0 -m "Phase 3 TimescaleDB optimization"
git push origin v3.1.0

# Or use deploy script:
./scripts/deploy.sh --yes --tag v3.1.0
```

### [ ] 5.5 Restart Application

```bash
# Restart Apache/Flask
sudo systemctl restart apache2
# or
sudo systemctl restart astrogen-wsgi

# Verify logs
tail -f /var/log/apache2/error.log  # or appropriate log path
# Should see no import-related errors
```

### [ ] 5.6 Health Check - Create Test Job

```bash
# Via UI or API:
curl -X POST https://app.astrogen.it/agata/admin/api/tess-bulk-import/jobs \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"files_selected": 10, ...'

# Monitor for 5-10 minutes:
# - Job should complete normally
# - Logs should show cagg refresh
# - Dashboard should load quickly
```

### [ ] 5.7 Monitor 24 Hours

```bash
# Set up alerts for:
# - Cagg refresh errors (grep logs for "Could not refresh cagg")
# - Query latency spike (check slow query log)
# - Disk usage growth (should be stable or decrease)

# Manual checks:
# Every 4 hours:
psql -c "
SELECT hypertable_name, total_bytes FROM timescaledb_information.hypertable_approximate_row_count 
WHERE hypertable_name LIKE 'agata_%' ORDER BY hypertable_name;
"

# Should see stable or decreasing sizes as compression kicks in
```

---

## Rollback (If Issues)

```bash
# If something breaks and you need to rollback:

# Option 1: Disable cagg refresh (keep cagg, but stop querying it)
psql -c "
SELECT remove_continuous_aggregate_policy('tess_job_summary');
SELECT remove_continuous_aggregate_policy('vast_job_summary');
SELECT remove_continuous_aggregate_policy('ztf_job_summary');
"

# Option 2: Drop caggs entirely (data still safe in tables)
psql -c "
DROP MATERIALIZED VIEW IF EXISTS tess_job_summary CASCADE;
DROP MATERIALIZED VIEW IF EXISTS vast_job_summary CASCADE;
DROP MATERIALIZED VIEW IF EXISTS ztf_job_summary CASCADE;
DROP MATERIALIZED VIEW IF EXISTS phot_hourly_summary CASCADE;
DROP MATERIALIZED VIEW IF EXISTS phot_daily_summary CASCADE;
DROP MATERIALIZED VIEW IF EXISTS phot_monthly_summary CASCADE;
"

# Revert code:
git revert <commit-hash>
git push origin main
systemctl restart apache2

# Tables still hypertable (compressed, chunked) = still get some benefit
```

---

## Success Criteria ✅

After Phase 3 complete, verify:

- [ ] All 4 tables are hypertable (verify in `timescaledb_information.hypertables`)
- [ ] All 7 cagg views exist (verify in `timescaledb_information.continuous_aggregates`)
- [ ] VAST job completion < 2 sec, dashboard load < 100ms
- [ ] TESS job completion < 5 sec, dashboard load < 80ms
- [ ] ZTF job completion < 2 sec, dashboard load < 50ms
- [ ] Editor catalog import completes without errors
- [ ] Cagg refresh appears in logs after each job completion
- [ ] No cagg-related errors in logs over 24 hours
- [ ] Disk usage stable or decreasing (compression working)

---

## Expected Outcome

| Metric | Before | After |
|--------|--------|-------|
| VAST dashboard load | 2-3s | 100ms |
| TESS dashboard load | 1.8s | 80ms |
| ZTF dashboard load | 1.5s | 50ms |
| Photometry query (30d) | 2s | 50ms |
| Disk (VAST/ZTF/TESS) | 1.5GB | 900MB |
| Disk (photometry) | 800MB | 250MB |

