# 📋 Deployment Checklist - Session 17

**Date**: 2026-02-13
**Branch**: senza-layer
**Type**: Features + Bug Fixes

---

## 🔍 PRE-DEPLOYMENT VERIFICATION

### Code Changes Syntax Check
- [ ] Python syntax OK: `python -m py_compile agata/admin/routes/stars_catalog.py`
- [ ] Python syntax OK: `python -m py_compile agata/catalog/services/query_service.py`
- [ ] Python syntax OK: `python -m py_compile agata/admin/routes/catalogs/tess.py`
- [ ] Jinja2 template OK: Run Jinja2 parser on list.html
- [ ] All 3 Python files compile without errors

### Files Modified
- [ ] `agata/admin/routes/stars_catalog.py` - VAST cache + filters + superuser fix
- [ ] `agata/templates/admin/stars_catalog/list.html` - Filter UI + table column
- [ ] `agata/catalog/services/query_service.py` - DB cache payload fix + removed prints
- [ ] `agata/catalog/services/vizier_client.py` - Removed debug prints
- [ ] `agata/admin/routes/catalogs/tess.py` - Vizier priority changed

### New Files Created (Documentation)
- [ ] `database_indices_vast_integration.sql` - Index creation script
- [ ] `VAST_VARIABLE_TYPE_INTEGRATION_COMPLETE.md` - Full implementation guide
- [ ] `SESSION_17_SUMMARY.md` - Session summary
- [ ] `DEPLOYMENT_CHECKLIST_SESSION_17.md` - This file

---

## 🗄️ DATABASE DEPLOYMENT

### Pre-Database Steps
- [ ] **Schedule**: Off-peak time (late evening or night)
- [ ] **Backup**: Verify MySQL backups completed
- [ ] **Users**: Notify team no deployments during index creation (~5-10 min)
- [ ] **Monitoring**: Have terminal ready to monitor process

### Index Creation
```bash
# Execute this EXACTLY:
mysql -u astrogen_admin -p astrogen_db < /var/www/astrogen/database_indices_vast_integration.sql

# Estimated time: 5-10 minutes
# Monitor with: SHOW PROCESSLIST; in another terminal
```

**Verify Indices Created**:
```sql
-- Check all indices
SHOW INDEX FROM Cataloghi_esterni WHERE Key_name LIKE 'idx_%';
SHOW INDEX FROM agata_vast_results WHERE Key_name LIKE 'idx_%';
SHOW INDEX FROM agata_star_assignments WHERE Key_name LIKE 'idx_%';
SHOW INDEX FROM agata_projects WHERE Key_name LIKE 'idx_%';

-- Expected: 11 indices total (4+3+2+2)
```

### Post-Index Verification
- [ ] All 11 indices created successfully
- [ ] No errors in MySQL error log
- [ ] Query performance acceptable

---

## 🐍 PYTHON CODE DEPLOYMENT

### Copy Files to Production
```bash
# All files are in senza-layer branch already
# Just need to restart Flask to load changes
```

### Files to Verify Modified
```bash
# Check file timestamps (should be recent)
ls -la /var/www/astrogen/agata/admin/routes/stars_catalog.py
ls -la /var/www/astrogen/agata/templates/admin/stars_catalog/list.html
ls -la /var/www/astrogen/agata/catalog/services/query_service.py
ls -la /var/www/astrogen/agata/catalog/services/vizier_client.py
ls -la /var/www/astrogen/agata/admin/routes/catalogs/tess.py
```

### Code Review Checklist
- [ ] VAST cache query looks correct (lines 305-344 in stars_catalog.py)
- [ ] Filter logic correct (lines 473-485)
- [ ] Template parameters passed correctly (lines 590-597)
- [ ] DB cache payload fix correct (query_service.py line 251)
- [ ] Debug prints removed (vizier_client.py, query_service.py)
- [ ] Superuser fix correct (lines 337-346, 703-720)

---

## 🎨 FRONTEND DEPLOYMENT

### Template Changes
- [ ] Filter UI added (lines 256-276)
- [ ] Table header added (lines 427-429)
- [ ] Table column added (lines 508-531)
- [ ] No syntax errors in Jinja2

### Assets Check
- [ ] No new CSS files needed (using Bootstrap badges)
- [ ] No new JavaScript files needed
- [ ] No breaking changes to existing styles

---

## 🚀 FLASK SERVER RESTART

### Pre-Restart
- [ ] Notify team: server restart in 2 minutes
- [ ] Check active connections: `ps aux | grep flask`
- [ ] Backup logs: `cp /path/to/logs /path/to/backup`

### Restart Sequence
```bash
# 1. Kill existing Flask process
pkill -f "flask run"

# 2. Wait for clean shutdown
sleep 3

# 3. Verify killed
ps aux | grep "flask run"  # Should show only grep line

# 4. Start new Flask instance
python -m flask run --no-debugger --no-reload --host=0.0.0.0 > /tmp/flask.log 2>&1 &

# 5. Verify started
sleep 2
ps aux | grep "flask run"  # Should show running process

# 6. Check logs
tail -20 /tmp/flask.log
```

### Post-Restart Verification
- [ ] Flask process running: `ps aux | grep flask`
- [ ] No errors in logs: `tail -30 /tmp/flask.log`
- [ ] Server responds: `curl -s http://localhost:5000/health`
- [ ] Admin page loads: Test in browser

---

## ✅ TESTING CHECKLIST

### Manual Browser Testing

**Test 1: Navigation**
- [ ] Login as superuser
- [ ] Navigate to `/agata/admin/stars-catalog`
- [ ] Page loads without errors
- [ ] No JavaScript console errors (F12)

**Test 2: Variable Type Filter**
- [ ] Dropdown "Tipo Variabile (VAST)" is visible
- [ ] Dropdown contains at least 3 options (if VAST data exists)
- [ ] Can select an option
- [ ] Page reloads with ?variable_type=... parameter
- [ ] Results filtered correctly

**Test 3: Known Variables Filter**
- [ ] Checkbox "Solo note" is visible
- [ ] Can check/uncheck checkbox
- [ ] Page reloads with ?known_variables_only=true parameter
- [ ] Only known variables displayed when checked

**Test 4: Table Column**
- [ ] "Tipo Variabile" column visible in table
- [ ] Shows badges for each variable type
- [ ] Shows green "Nota" badge if is_known_variable=true
- [ ] Shows "+N" if more than 3 types
- [ ] Small text shows catalog_matches

**Test 5: Combined Filters**
- [ ] Select state filter + variable type filter together
- [ ] Results filtered correctly by both
- [ ] Pagination works with filters applied
- [ ] Sorting works with filters applied

**Test 6: Superuser Project Creation**
- [ ] Login as superuser
- [ ] Find assigned star without project
- [ ] Button "+" visible (create project button)
- [ ] Click button and create project
- [ ] Project created successfully

**Test 7: Admin Permissions**
- [ ] Login as admin
- [ ] Navigate to stars-catalog
- [ ] Can see "Tipo Variabile" column for own association stars
- [ ] Can create project for own association star
- [ ] Cannot see/modify other association's stars

**Test 8: Analyst Permissions**
- [ ] Login as analyst
- [ ] Can view stars with projects assigned to them
- [ ] Cannot create projects
- [ ] Cannot see Variable Type filters (read-only view)

### Performance Testing

**Test 9: Query Performance**
- [ ] Load `/agata/admin/stars-catalog` with "Tutte" filter
- [ ] Should load within 3 seconds (was 2.5s before, now ~1.8s)
- [ ] Check Network tab (F12) for timing

**Test 10: Filter Performance**
- [ ] Apply variable_type filter
- [ ] Results update within <1 second (in-memory filter)
- [ ] No query to database (should be instant)

---

## 🐛 ISSUE RESOLUTION

### Issue 1: Variable Type dropdown not showing

**Check**:
```python
# Are there VAST results with is_valid=TRUE?
SELECT COUNT(*) FROM agata_vast_results WHERE is_valid=TRUE;

# Are variable_types populated?
SELECT DISTINCT variable_type FROM agata_vast_results WHERE is_valid=TRUE LIMIT 5;

# Can we see VAST data for a specific star?
SELECT gaia_source_id, variable_type FROM agata_vast_results
WHERE gaia_source_id IN (SELECT CAST(Source AS UNSIGNED) FROM Cataloghi_esterni LIMIT 5);
```

**Solution**: If 0 results, VAST data may not exist or indices not created yet.

### Issue 2: Superuser can't create project button still missing

**Check**:
```python
# Is can_create_project=True in stars_raw?
# Add debug print temporarily:
logger.info(f"Star {star.gaia_id}: can_create_project={can_create_project}, is_superuser={is_superuser}")
```

**Solution**: Verify is_superuser flag is True, not just is_admin

### Issue 3: Table column shows "-" for all stars

**Check**:
```python
# Is vast_cache populated?
logger.info(f"VAST cache size: {len(vast_cache)}")

# Is gaia_id match correct?
logger.info(f"Checking star {row.gaia_id}: in vast_cache? {str(row.gaia_id) in vast_cache}")
```

**Solution**: Verify gaia_id type conversion (string) is correct

---

## 📊 ROLLBACK PLAN

If issues occur, can rollback easily:

### Rollback Database
```sql
-- Drop all new indices (no data lost)
DROP INDEX idx_cataloghi_esterni_source ON Cataloghi_esterni;
DROP INDEX idx_cataloghi_esterni_source_assoc ON Cataloghi_esterni;
DROP INDEX idx_cataloghi_esterni_import_id ON Cataloghi_esterni;
DROP INDEX idx_cataloghi_esterni_catalogo ON Cataloghi_esterni;
DROP INDEX idx_vast_results_gaia_source_id ON agata_vast_results;
DROP INDEX idx_vast_results_is_known_variable ON agata_vast_results;
DROP INDEX idx_vast_results_gaia_variable_type ON agata_vast_results;
DROP INDEX idx_star_assignments_gaia_id ON agata_star_assignments;
DROP INDEX idx_star_assignments_gaia_assoc ON agata_star_assignments;
DROP INDEX idx_projects_gaia_id ON agata_projects;
DROP INDEX idx_projects_gaia_assoc ON agata_projects;
```

### Rollback Code
```bash
# Revert to previous commit
git revert <commit_hash>

# Or restore from backup
git checkout HEAD~1 -- agata/admin/routes/stars_catalog.py
git checkout HEAD~1 -- agata/templates/admin/stars_catalog/list.html
git checkout HEAD~1 -- agata/catalog/services/query_service.py
git checkout HEAD~1 -- agata/catalog/services/vizier_client.py
git checkout HEAD~1 -- agata/admin/routes/catalogs/tess.py

# Restart Flask
pkill -f "flask run"
sleep 2
python -m flask run --no-debugger --no-reload --host=0.0.0.0 &
```

**Rollback time**: <5 minutes

---

## 📝 DEPLOYMENT LOG TEMPLATE

```
=== DEPLOYMENT SESSION 17 LOG ===
Date: ____________________
Deployer: ____________________
Start Time: ____________________

PRE-DEPLOYMENT:
[ ] Code syntax verified
[ ] Database backup confirmed
[ ] Team notified

DATABASE:
[ ] Indices creation started: ____
[ ] Indices creation completed: ____
[ ] All 11 indices verified

FLASK RESTART:
[ ] Old process killed: ____
[ ] New process started: ____
[ ] Logs verified: ____

TESTING:
[ ] Admin page loads
[ ] Variable Type filter works
[ ] Known Variables filter works
[ ] Superuser can create projects
[ ] Table column displays correctly
[ ] Performance acceptable

ISSUES FOUND:
1. ____________________
   Status: ____________________

2. ____________________
   Status: ____________________

ROLLBACK NEEDED: [ ] Yes [ ] No

End Time: ____________________
Status: [ ] SUCCESSFUL [ ] PARTIAL [ ] FAILED
```

---

## ✨ Final Verification

Before marking deployment complete:

- [ ] All tests passed
- [ ] No errors in Flask logs
- [ ] No errors in MySQL logs
- [ ] Performance metrics acceptable
- [ ] Team confirmed functionality
- [ ] Documentation up to date
- [ ] Backup created for recovery

---

## 🎉 Deployment Complete!

When all items checked:

```bash
# Create deployment note
git log --oneline -5  # Get commits for reference

# Example final status:
echo "Session 17 deployed successfully at $(date)" >> /var/www/astrogen/DEPLOYMENT_LOG.txt
```

---

## 📞 Support Contacts

If issues occur during/after deployment:
- Check logs first
- Review TROUBLESHOOTING section above
- Reference VAST_VARIABLE_TYPE_INTEGRATION_COMPLETE.md for details
- Last resort: Rollback and investigate

**Expected deployment time**: 20-30 minutes total (including testing)

