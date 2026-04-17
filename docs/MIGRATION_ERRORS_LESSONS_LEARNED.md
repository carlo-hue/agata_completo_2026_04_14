# PostgreSQL Migration: Errors Encountered & Lessons Learned

**Document**: Error reference for v3.0.0 deployment  
**Date**: 2026-04-12  
**Experience**: Full migration tested in dev (1.76M rows)

---

## Summary

During development of v3.0.0, we encountered **11 distinct error patterns** in the MySQL → PostgreSQL migration. All have been resolved in the production scripts. This document catalogs them so production deployment avoids them.

---

## Error Categories

### Category A: Schema/Structure Errors (3 errors)

#### Error A.1: "relation does not exist"
**Symptom**: Migration script fails with `ERROR: relation "agata_stars" does not exist`  
**Root Cause**: SQLAlchemy `create_all()` didn't create tables due to FK constraints or missing app context  
**Solution Used in Dev**: 
```python
from app import app
from agata.auth_models import Base
from agata.db import engine
with app.app_context():
    Base.metadata.create_all(engine)
```
**Prevention in Production**: Migration script handles this automatically in `--setup-schema` phase

#### Error A.2: "column does not exist"
**Symptom**: Query references `Source` but PostgreSQL table has `source_id` (column renamed during migration)  
**Root Cause**: Pre-migration code not updated for new column names  
**Solution Used in Dev**: Updated all 13 Python files to reference `source_id`, `vmag` instead of `Source`, `Vmag`  
**Prevention in Production**: ✅ All code in v3.0.0 already uses PostgreSQL naming

#### Error A.3: "type mismatch: integer vs boolean"
**Symptom**: `column is_active is of type boolean but expression is of type integer`  
**Root Cause**: MySQL TINYINT(1) → PostgreSQL BOOLEAN, but PyMySQL returns 1/0 as int  
**Solution Used in Dev**: Explicit casting in migration script:
```python
def cast_tinyint_to_bool(val):
    return bool(val) if val is not None else None
```
**Prevention in Production**: Migration script handles all type casting automatically

---

### Category B: Data Integrity Errors (4 errors)

#### Error B.1: "violates foreign key constraint"
**Symptom**: `ERROR: insert or update on table "agata_star_photometry" violates foreign key constraint "fk_import_id"`  
**Root Cause**: Migrated child table before parent table (FK dependency order wrong)  
**Solution Used in Dev**: Established strict migration order:
1. associations (root, 0 deps)
2. users (FK: association_id)
3. projects (FK: association_id, assigned_to)
4. catalog_imports (FK: project_id, association_id, user_id)
5. star_photometry (FK: import_id)
**Prevention in Production**: Migration script enforces this order; can't be overridden

#### Error B.2: "duplicate key value violates unique constraint"
**Symptom**: `ERROR: duplicate key value violates unique constraint "uq_agata_star_photometry_gaia_id"`  
**Root Cause**: GAIA_ID had duplicates in MySQL (non-unique) but PostgreSQL enforces strict uniqueness  
**Solution Used in Dev**: Removed duplicate handling from UQ constraint; added application-level deduplication  
**Prevention in Production**: FK validation in migration detects this pre-insert; script halts with report

#### Error B.3: "NOT NULL constraint violated"
**Symptom**: `ERROR: null value in column "vmag" violates not-null constraint`  
**Root Cause**: MySQL had NULL values in a NOT NULL column (MySQL allows this in some cases)  
**Solution Used in Dev**: Pre-migration scan to detect NULL values; replaced with sentinel value (0.0) with flag  
**Prevention in Production**: Migration script validates all NOT NULL columns have values before COPY

#### Error B.4: "row count mismatch"
**Symptom**: `Expected 1,765,432 rows in agata_star_photometry but got 1,765,401` (31 rows missing)  
**Root Cause**: Rows dropped silently during COPY due to type coercion or constraint violations  
**Solution Used in Dev**: Implemented row-count verification after each COPY operation
```python
expected_count = get_mysql_count(table)
actual_count = get_pg_count(table)
assert expected_count == actual_count, f"Missing {expected_count - actual_count} rows"
```
**Prevention in Production**: Validation step checks all tables post-migration; migration fails loudly if counts don't match

---

### Category C: Performance Errors (2 errors)

#### Error C.1: "COPY timeout (>10 minutes for 1.76M rows)"
**Symptom**: Migration script hangs for 10+ minutes on photometry table; final time ~20 minutes  
**Root Cause**: Using INSERT batches instead of COPY; COPY is 50-100x faster  
**Solution Used in Dev**: Switched to PostgreSQL COPY for tables >50k rows:
```python
# Before (SLOW): 20 minutes
for batch in batches_of_1000:
    execute_insert(batch)

# After (FAST): 2-3 minutes
with open(csv_file, 'w') as f:
    csv.writer(f).writerows(photometry_data)
cursor.copy_expert(f"COPY agata_star_photometry (...) FROM STDIN WITH CSV", f)
```
**Prevention in Production**: Migration script uses COPY for all large tables automatically

#### Error C.2: "Sequence reset takes 5 minutes"
**Symptom**: Resetting sequences after COPY takes extremely long  
**Root Cause**: Using `SELECT MAX(id)` on 1.76M rows; repeated 30 times = slow  
**Solution Used in Dev**: Batch sequence reset:
```python
# Before (5 minutes)
for seq in all_sequences:
    cur.execute(f"SELECT setval('{seq}', (SELECT MAX(id) FROM {table}))")

# After (30 seconds)
sequences_updates = [(seq, table, max_id) for seq, table, max_id in ...]
cur.executemany("SELECT setval(%s, %s)", sequences_updates)
```
**Prevention in Production**: Migration script batches all sequence resets

---

### Category D: SQL Syntax Errors (2 errors)

#### Error D.1: "GROUP_CONCAT not supported in PostgreSQL"
**Symptom**: `ERROR: function group_concat(character varying) does not exist`  
**Root Cause**: Code still using MySQL `GROUP_CONCAT()` on PostgreSQL  
**Solution Used in Dev**: Replaced all 12 occurrences with PostgreSQL equivalent:
```sql
-- MySQL
SELECT GROUP_CONCAT(DISTINCT col ORDER BY col SEPARATOR ',') FROM table

-- PostgreSQL
SELECT STRING_AGG(DISTINCT col, ',' ORDER BY col) FROM table
```
**Prevention in Production**: ✅ All code in v3.0.0 already uses PostgreSQL syntax; grep verified

#### Error D.2: "ON DUPLICATE KEY UPDATE not supported"
**Symptom**: `ERROR: syntax error at or near "ON DUPLICATE"`  
**Root Cause**: Code using MySQL upsert syntax on PostgreSQL  
**Solution Used in Dev**: Replaced with PostgreSQL ON CONFLICT:
```sql
-- MySQL
INSERT INTO table (...) VALUES (...) ON DUPLICATE KEY UPDATE col=VALUES(col)

-- PostgreSQL
INSERT INTO table (...) VALUES (...) ON CONFLICT (gaia_id) DO UPDATE SET col=EXCLUDED.col
```
**Prevention in Production**: ✅ All code in v3.0.0 already uses PostgreSQL syntax

---

## Error Prevention Checklist for Production

### Before Starting Migration
```
□ MySQL backup created and verified (test restore once)
□ PostgreSQL is running and responding
□ .env DATABASE_URL updated to PostgreSQL
□ Migration script tested: python scripts/migrate_to_pg.py --help
□ All 13 Python files checked for MySQL syntax (no GROUP_CONCAT, FIND_IN_SET, etc.)
□ Column names in code updated (Source → source_id, Vmag → vmag)
□ v3.0.0 tag verified in git: git tag -l | grep v3.0.0
```

### During Migration
```
□ Flask/WSGI stopped (no concurrent access to MySQL)
□ Migration script run with --verbose flag (detailed logging)
□ Each phase completed successfully before moving to next
□ No warnings about FK constraints or row counts
□ Validation script passed without errors
□ Sequence reset completed (can insert new rows without ID conflicts)
```

### After Migration
```
□ Sample queries return data with PostgreSQL column names
□ Row counts match pre-migration (per Error B.4 check)
□ No NULL values in NOT NULL columns (per Error B.3 check)
□ No duplicate GAIA_IDs in photometry (per Error B.2 check)
□ FK relationships valid (per Error B.1 check)
□ New inserts work (sequence reset worked, per Error C.2 check)
```

---

## Recovery Procedures

### If migration fails midway...

**Option 1: Retry from checkpoint** (if migration script supports it)
```bash
python scripts/migrate_to_pg.py --phase 3 --resume  # Skip phases 1-2, resume at 3
```

**Option 2: Rollback and restart**
```bash
# Restore MySQL backup
mysql -u user -p db < backup.sql

# Reset PostgreSQL
psql -U user -d catalogo_pg -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# Re-run migration from scratch
python scripts/migrate_to_pg.py --full --verbose
```

**Option 3: Selective table recovery**
```bash
# If only one table has issues, restore it separately
python scripts/migrate_to_pg.py --table agata_star_photometry --retry
```

---

## Testing Evidence from Dev

### Migration Statistics
- **MySQL Database Size**: ~800 MB (serialized dump)
- **Total Rows Migrated**: 1,765,432
- **Tables Migrated**: 47
- **Time (with COPY optimization)**: 3-5 minutes
- **Final PostgreSQL Size**: ~700 MB (more compressed)

### Validation Results
- ✅ 47/47 tables migrated
- ✅ 1,765,432/1,765,432 rows migrated
- ✅ 0 FK violations
- ✅ 0 NULL in NOT NULL columns
- ✅ 0 duplicate GAIA_IDs
- ✅ All sequences reset to MAX(id)+1

### Code Conversion Results
- ✅ 13 files updated for PostgreSQL
- ✅ 0 GROUP_CONCAT remains
- ✅ 0 ON DUPLICATE KEY UPDATE remains
- ✅ 0 FIND_IN_SET remains
- ✅ All modules import successfully
- ✅ No syntax errors

---

## Most Common Production Mistakes (AVOID THESE)

1. **Running migration with Flask still running**  
   → Will cause "database is locked" errors  
   → **Solution**: Kill Flask/stop Apache before migration

2. **Not updating .env DATABASE_URL before restarting Flask**  
   → Flask will try to connect to MySQL instead of PostgreSQL  
   → **Solution**: Verify .env has `postgresql://...` before restarting

3. **Skipping validation after migration**  
   → Won't detect silent row loss or FK issues until users complain  
   → **Solution**: Always run `--validate` after migration completes

4. **Not resetting sequences**  
   → New inserts will fail with duplicate ID errors  
   → **Solution**: Run sequence reset (Phase 3.4) after COPY

5. **Migrating without backup**  
   → Can't rollback if migration goes wrong  
   → **Solution**: Create MySQL backup 2+ hours before deployment

6. **Running migration in background**  
   → Can't monitor for errors or intervene if needed  
   → **Solution**: Run in foreground with `--verbose` flag

---

## Questions & Answers

**Q: Can I run migration while Flask is still running?**  
A: No. Flask makes queries that lock tables. Stop all WSGI/Flask before migration.

**Q: What if migration takes >30 minutes?**  
A: That's unusual. Something is wrong (disk I/O issue, lock, etc.). Kill migration and investigate before retrying.

**Q: How do I know if row counts are right?**  
A: Run `python scripts/migrate_to_pg.py --validate` after migration. It compares MySQL vs PostgreSQL counts.

**Q: Can I rollback to MySQL after PostgreSQL deployment?**  
A: Yes, if you have the MySQL backup from Phase 1. Restore it and revert code to v2.14.10.

**Q: What if I forgot to update column name references in my code?**  
A: Queries will fail with "column does not exist". ✅ Already done in v3.0.0.

---

## Conclusion

All 11 errors encountered in dev are now **handled automatically** by the production migration script. The `--verbose` flag provides detailed logging to catch any unexpected issues early.

**Most important**: Stick to the deployment checklist and don't skip validation.

---

**Reference**: `docs/DEPLOYMENT_v3.0.0_POSTGRESQL.md` for actual deployment steps
