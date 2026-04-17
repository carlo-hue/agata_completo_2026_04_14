# DEPLOYMENT v3.0.0 → PostgreSQL (Production)

**Release Date**: 2026-04-12  
**Target Environment**: astrogen03 (production)  
**Estimated Downtime**: 15-30 minutes  
**Backup Required**: YES (full MySQL dump)

---

## Overview

AGATA v3.0.0 is a **major release** that migrates the database from **MySQL/MariaDB to PostgreSQL**.

### Breaking Changes
- ✅ All SQL syntax is now PostgreSQL-only (MySQL queries removed)
- ✅ Column names in `agata_star_photometry` are now snake_case: `Source` → `source_id`, `Vmag` → `vmag`
- ✅ TINYINT(1) → BOOLEAN (True/False instead of 1/0)
- ⚠️ **Rollback to v2.14.10 requires MySQL restoration from backup**

---

## Phase 1: Pre-Deployment Checklist (2-4 hours before)

### 1.1 Database Backup
```bash
# SSH to astrogen03
ssh astrogen@10.1.0.6

# Create full MySQL backup (this takes ~10-15 minutes for 1.76M rows)
cd /var/www/astrogen
mysqldump -u catalogo_user -p catalogo > backups/catalogo_$(date +%Y%m%d_%H%M%S).sql
# Password: (ask your admin for MySQL password)

# Verify backup
ls -lh backups/catalogo_*.sql
# Should be ~500-800 MB for full dump
```

### 1.2 PostgreSQL Verification
```bash
# Verify PostgreSQL is running
sudo systemctl status postgresql

# Test connection
psql -U agata_user -d catalogo_pg -c "SELECT 1"
# Expected output: 1 (single row with value 1)

# Verify schema is EMPTY (pre-populated for migration)
psql -U agata_user -d catalogo_pg -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'"
# Expected output: ~40-50 tables (from SQLAlchemy create_all)
```

### 1.3 Environment Variables
```bash
# Verify .env has PostgreSQL DATABASE_URL
cat /var/www/astrogen/.env | grep DATABASE_URL
# Should be: postgresql+psycopg://agata_user:password@localhost/catalogo_pg
# NOT: mysql+pymysql://...
```

### 1.4 Code Verification
```bash
# Verify v3.0.0 code is ready
cd /var/www/astrogen
git log --oneline -1
# Should show commit hash starting with v3.0.0 message

# Verify migration script exists
python scripts/migrate_to_pg.py --help
# Should show usage without errors
```

---

## Phase 2: Code Deployment (5 minutes)

### 2.1 Deploy Code Only (Skip DB)
```bash
cd /var/www/astrogen

# Deploy v3.0.0 code (using existing deploy.sh script)
./scripts/deploy.sh --yes --skip-db --tag v3.0.0

# Expected output:
# ✅ Git clean check passed
# ✅ Switched to v3.0.0 tag
# ✅ pip install completed
# ✅ Apache restarted
# ✅ Health check passed
```

### 2.2 Verify Code is Ready
```bash
# Check Flask app loads
python -c "from app import app; print(f'Flask app loaded: {app.name}')"
# Expected: Flask app loaded: app

# Check version
python -c "from agata import __version__; print(__version__)"
# Expected: 3.0.0
```

---

## Phase 3: Database Migration (10-15 minutes)

### 3.1 Stop Flask/WSGI
```bash
# Stop Apache (which runs WSGI)
sudo systemctl stop apache2
# OR if using standalone Flask dev server:
# killall python3

# Wait for connections to drain
sleep 5

# Verify no Flask processes running
ps aux | grep python | grep -v grep
# Should have NO results
```

### 3.2 Run Migration Script
```bash
cd /var/www/astrogen

# Option A: Migrate everything at once (safest for production)
python scripts/migrate_to_pg.py --full --verbose

# Expected output:
# ✅ Phase 1: associations, users (2-3 rows expected)
# ✅ Phase 2: projects, assignments (should complete quickly)
# ✅ Phase 3: catalog imports and details (large volume)
# ✅ Phase 4: photometry (1.76M rows - this takes 3-5 minutes)
# ✅ Sequences reset
# ✅ FK validation complete

# Option B: Migrate phase-by-phase (if you want more control)
python scripts/migrate_to_pg.py --phase 1 --verbose
# [verify success]
python scripts/migrate_to_pg.py --phase 2 --verbose
# [verify success]
python scripts/migrate_to_pg.py --phase 3-4 --verbose
# [verify success]
python scripts/migrate_to_pg.py --validate
```

### 3.3 Validate Migration
```bash
# Run validation checks
python scripts/migrate_to_pg.py --validate

# Expected output:
# ✅ Table row counts match MySQL
# ✅ No NULL foreign keys detected
# ✅ Sequences reset correctly
# ✅ Sample data verification passed
```

### 3.4 Post-Migration Cleanup
```bash
# Reset any sequences that might be off
psql -U agata_user -d catalogo_pg << 'EOF'
-- Resets all sequences to MAX(id) + 1
SELECT setval('agata_associations_id_seq', (SELECT MAX(id) + 1 FROM agata_associations), false);
SELECT setval('agata_users_id_seq', (SELECT MAX(id) + 1 FROM agata_users), false);
SELECT setval('agata_projects_id_seq', (SELECT MAX(id) + 1 FROM agata_projects), false);
SELECT setval('agata_star_photometry_id_seq', (SELECT MAX(id) + 1 FROM agata_star_photometry), false);
EOF
```

---

## Phase 4: Application Restart & Verification (5 minutes)

### 4.1 Restart Flask/WSGI
```bash
# Restart Apache
sudo systemctl start apache2

# Wait for app to come up
sleep 10

# Check app is responding
curl -I http://localhost:5000/
# Expected: 200 OK or 302 (redirect to login)
```

### 4.2 Verify Application Functionality

#### OAuth Login
1. Open browser: `https://astrogen.it/agata/`
2. Click "Login with Google"
3. Authenticate with a test account
4. Verify login successful (should see dashboard)

#### Load Variable Stars Project
1. From dashboard, click a variable star project
2. Verify star list loads (check row count matches pre-migration)
3. Click a star, verify photometry chart displays
4. Verify columns: `vmag` (not `Vmag`), proper source display

#### Test Catalog Import (Gaia)
1. Edit a variable star
2. Click "Import Cataloghi"
3. Select "Gaia DR3"
4. Enter a magnitude range
5. Click "Search"
6. Verify results load and show "Already imported" if applicable

#### Check Admin Panel
1. Login as admin
2. Go to `/agata/admin/`
3. Check "Progetti" tab: verify all projects visible
4. Check "Stelle Catalogo" tab: verify star counts match pre-migration
5. Check "VAST Jobs", "ZTF Survey", "TESS Jobs": verify any job status displays

### 4.3 Monitor Logs
```bash
# Watch Flask logs for errors
tail -f /var/log/astrogen/astrogen.log
# [should show no critical errors, maybe some INFO level messages]

# Watch Apache logs
tail -f /var/log/apache2/error.log
# [should be clean]

# Check PostgreSQL logs for errors
sudo tail -f /var/log/postgresql/postgresql.log
# [should show no connection errors]
```

---

## Phase 5: Final Checks (10 minutes)

### 5.1 Data Integrity Spot Checks
```bash
# Count rows in critical tables (should match pre-migration)
psql -U agata_user -d catalogo_pg << 'EOF'
SELECT 'associations' as table_name, COUNT(*) as row_count FROM agata_associations
UNION ALL
SELECT 'users', COUNT(*) FROM agata_users
UNION ALL
SELECT 'projects', COUNT(*) FROM agata_projects
UNION ALL
SELECT 'star_photometry', COUNT(*) FROM agata_star_photometry
UNION ALL
SELECT 'catalog_imports', COUNT(*) FROM agata_catalog_imports;
EOF
```

### 5.2 Sample Data Query
```bash
# Verify photometry data is accessible
psql -U agata_user -d catalogo_pg << 'EOF'
SELECT source_id, vmag, g_mag, import_id
FROM agata_star_photometry
LIMIT 5;
EOF
# Should return 5 rows with non-NULL vmag and source_id (new column names)
```

### 5.3 User Session Check
```bash
# Verify at least one user can authenticate
# (manual step: have someone log in via OAuth)
# Check database has login record
psql -U agata_user -d catalogo_pg -c "SELECT COUNT(*) FROM agata_users;"
# Should match pre-migration count
```

---

## Rollback Procedure (If Needed)

**If anything goes wrong during migration:**

### Rollback Step 1: Restore MySQL Backup
```bash
# Stop Flask/WSGI
sudo systemctl stop apache2

# Restore MySQL backup (choose the backup from Phase 1)
mysql -u catalogo_user -p catalogo < backups/catalogo_YYYYMMDD_HHMMSS.sql
# Password: (MySQL password)

# Verify MySQL is restored
mysql -u catalogo_user -p catalogo -c "SELECT COUNT(*) FROM agata_star_photometry;"
# Should match pre-migration count
```

### Rollback Step 2: Revert Code
```bash
cd /var/www/astrogen

# Revert to v2.14.10 (last MySQL version)
git reset --hard v2.14.10

# Verify .env points to MySQL
cat .env | grep DATABASE_URL
# Should be: mysql+pymysql://...
```

### Rollback Step 3: Restart Application
```bash
# Restart Apache
sudo systemctl start apache2

# Wait and verify
sleep 10
curl -I http://localhost:5000/
# Should respond with 200 or 302
```

---

## Known Issues & Mitigations

### Issue 1: "relation does not exist" errors
**Cause**: Migration script didn't create PostgreSQL schema  
**Mitigation**: Run `python scripts/migrate_to_pg.py --setup-schema` before migration  
**Prevention**: This is handled automatically by the script

### Issue 2: "column 'Source' does not exist"
**Cause**: Old code still references MySQL column names  
**Prevention**: All code updated in v3.0.0; if error occurs, rollback to v2.14.10

### Issue 3: "violates foreign key constraint"
**Cause**: Migration order wrong (child inserted before parent)  
**Prevention**: Migration script uses correct FK ordering; if error, check Phase 3 output

### Issue 4: High row insert times (>30 minutes)
**Cause**: COPY performance degradation  
**Mitigation**: Can pause migration, investigate, and resume by running just remaining phases  
**Prevention**: PostgreSQL should migrate 1.76M rows in 3-5 minutes

### Issue 5: Sequences not reset (NEW records get duplicate IDs)
**Cause**: PostgreSQL sequences weren't reset after COPY  
**Mitigation**: Run Phase 3.4 post-migration cleanup script  
**Prevention**: Automatic in `--full` mode; manual otherwise

---

## Support & Documentation

### Migration Logs
- Migration script logs all actions to `/var/www/astrogen/migration_$(date +%Y%m%d_%H%M%S).log`
- Review if any issues occur: `cat migration_*.log | tail -100`

### Reference Documents
- `docs/MIGRATION_COMPLETE_SUMMARY.md` - Overview of migration strategy
- `scripts/migrate_to_pg.py --help` - Detailed script options
- `docs/DATABASE_SCHEMA.md` - Updated schema (now PostgreSQL)

### Contacts
- If migration fails: contact your database admin
- If code fails to deploy: check `git log --oneline -5`
- If data integrity issues: restore MySQL backup and investigate

---

## Deployment Checklist Template

```
PRE-DEPLOYMENT
□ MySQL backup created (size > 500 MB)
□ PostgreSQL verified running
□ .env DATABASE_URL points to PostgreSQL
□ v3.0.0 code verified in git

DEPLOYMENT
□ Apache stopped (no Flask processes)
□ Code deployed via ./scripts/deploy.sh --skip-db --tag v3.0.0
□ Migration script ran successfully (--full --verbose)
□ Validation passed (--validate)
□ Sequences reset (Phase 3.4)

VERIFICATION
□ Apache started successfully
□ OAuth login works
□ Variable stars project loads
□ Catalog import works
□ Admin panel accessible
□ No error logs
□ Row counts match pre-migration

POST-DEPLOYMENT
□ Data integrity checks passed
□ Sample queries return PostgreSQL column names (source_id, vmag)
□ Users can authenticate
□ Document deployment in wiki with date/time
```

---

## Timeline

| Phase | Task | Duration | Status |
|-------|------|----------|--------|
| 1 | Pre-deployment checks | 30 min | Before deployment |
| 2 | Code deployment | 5 min | During deployment window |
| 3 | DB migration | 10-15 min | During deployment window |
| 4 | App restart + verify | 5 min | During deployment window |
| 5 | Final checks | 10 min | After deployment |
| **TOTAL** | **Full deployment** | **~1 hour** | |

---

## Success Criteria

✅ **Deployment is successful if:**
1. All pre-deployment checks passed
2. Migration script ran with no errors
3. Validation passed
4. OAuth login works
5. Variable stars load with correct photometry
6. Row counts match pre-migration
7. No critical error logs
8. Database is PostgreSQL (not MySQL)

❌ **Rollback if:**
1. Migration script fails (won't complete)
2. Validation detects missing rows or FK violations
3. OAuth login fails (user lookup broken)
4. Variable stars don't load (DB connectivity issue)
5. Any critical errors in logs after 30 minutes

---

**Last Updated**: 2026-04-12  
**Tested In**: Development (1.76M rows, 2 hours)  
**Ready For**: Production deployment
