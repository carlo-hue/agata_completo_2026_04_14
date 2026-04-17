# v3.0.0 Deployment: Quick Reference Card

**For**: astrogen03 production team  
**Time**: ~1 hour total (30 min prep, 30 min execution)  
**Difficulty**: Medium (follow checklist exactly)

---

## 🚨 STOP BEFORE YOU START

- [ ] Do you have the MySQL **backup file**? (`catalogo_YYYYMMDD_HHMMSS.sql`)
- [ ] Is PostgreSQL **running**? (`sudo systemctl status postgresql`)
- [ ] Is Flask **NOT running**? (check: `ps aux | grep python | grep -v grep` = empty)
- [ ] Have you **read** `DEPLOYMENT_v3.0.0_POSTGRESQL.md`?

If you answered NO to any of these, **STOP** and read Phase 1 in the full deployment guide.

---

## ⚡ The 3-Step Deployment

### STEP 1: Backup (run 2+ hours before deployment)
```bash
cd /var/www/astrogen
mysqldump -u catalogo_user -p catalogo > backups/catalogo_$(date +%Y%m%d_%H%M%S).sql
# Enter MySQL password when prompted
```
✅ **Done?** Continue to Step 2 only after backup is > 500MB

---

### STEP 2: Deploy Code & Migrate DB (execute in this exact order)

```bash
cd /var/www/astrogen

# 2a. Stop Flask
sudo systemctl stop apache2

# 2b. Deploy code
./scripts/deploy.sh --yes --skip-db --tag v3.0.0

# 2c. Verify version updated
python -c "from agata import __version__; print(__version__)"
# Should print: 3.0.0

# 2d. Run migration (this takes 10-15 minutes, watch the output)
python scripts/migrate_to_pg.py --full --verbose

# 2e. Validate migration (this should show all green checks)
python scripts/migrate_to_pg.py --validate

# 2f. Start Flask
sudo systemctl start apache2
sleep 10

# 2g. Verify Flask is up
curl -I http://localhost:5000/
# Should show: 200 OK or 302 (redirect)
```

✅ **Done?** Continue to Step 3 only if you see "✅ Migration complete" and no red errors

---

### STEP 3: Smoke Test (5 minutes)

Open browser and test these **in order**:

1. **Login**: https://astrogen.it/agata/
   - Click "Login with Google"
   - Should see dashboard
   - ❌ If stuck on login: migration failed, check `/var/log/astrogen/astrogen.log`

2. **Load Variable Stars**: Click a project
   - Should see star list
   - ❌ If blank: database connectivity issue

3. **Check a Star**: Click a star row
   - Should show photometry chart
   - ❌ If chart empty: column name issue (Source vs source_id)

4. **Try Catalog Import**: Edit star → Import Cataloghi → Gaia
   - Should search successfully
   - ❌ If fails: SQL syntax issue

5. **Admin Panel**: Go to `/agata/admin/`
   - Check "Progetti" count matches pre-migration
   - Check "Stelle Catalogo" count matches pre-migration
   - ❌ If counts wrong: rows weren't migrated

✅ **All tests pass?** Deployment complete! Document the time and version in your wiki.

---

## 🔧 Emergency Commands

### If Flask won't start:
```bash
sudo systemctl stop apache2
tail -100 /var/log/astrogen/astrogen.log  # See what's wrong
# Fix issue, then:
sudo systemctl start apache2
```

### If migration failed:
```bash
# Restore MySQL backup (choose file from Step 1)
mysql -u catalogo_user -p catalogo < backups/catalogo_YYYYMMDD_HHMMSS.sql

# Revert code
git reset --hard v2.14.10

# Restart Flask
sudo systemctl start apache2

# Contact your admin
```

### If row counts are wrong:
```bash
# Check what happened
python scripts/migrate_to_pg.py --validate

# If errors listed: run migration again from beginning
python scripts/migrate_to_pg.py --full --verbose --force
```

### If you need to see what table is broken:
```bash
psql -U agata_user -d catalogo_pg << 'EOF'
SELECT 'associations', COUNT(*) FROM agata_associations
UNION ALL SELECT 'users', COUNT(*) FROM agata_users
UNION ALL SELECT 'projects', COUNT(*) FROM agata_projects
UNION ALL SELECT 'photometry', COUNT(*) FROM agata_star_photometry;
EOF
```

---

## 📊 What to Expect (Normal Output)

### During migration:
```
✅ Phase 1: associations, users (1 sec)
✅ Phase 2: projects, assignments (2 sec)
✅ Phase 3: catalog imports (5 sec)
✅ Phase 4: photometry (3-5 minutes) ← this one takes longest
✅ Resetting sequences (30 sec)
✅ FK validation (30 sec)
✅ Migration complete
```

⏱️ **Total time**: 10-15 minutes (not including 30 min wait for Flask to restart)

### During validation:
```
✅ Table row counts match
✅ FK constraints valid
✅ Sequences reset correctly
✅ All checks passed
```

---

## ❌ Stop Immediately If You See:

| Message | Problem | Action |
|---------|---------|--------|
| `violates foreign key` | DB corruption | Restore backup, retry |
| `row count mismatch` | Data lost | Restore backup, retry |
| `relation does not exist` | Schema not created | Restore backup, retry |
| `type mismatch` | Column type issue | Restore backup, retry |
| `timeout` (>20 minutes) | Something stuck | Kill process, check logs |

**For ANY error**: Kill migration, restore backup, investigate, retry.

---

## 📝 Deployment Checklist

### Before Deployment
- [ ] Backup created (size > 500 MB)
- [ ] PostgreSQL running
- [ ] Flask stopped
- [ ] .env DATABASE_URL has `postgresql://`
- [ ] Commit hash shows v3.0.0 message

### During Deployment
- [ ] deploy.sh completed without errors
- [ ] Migration script ran to completion
- [ ] Validation passed (all checks green)
- [ ] Flask started successfully
- [ ] curl test shows 200/302 response

### After Deployment
- [ ] Can login via Google OAuth
- [ ] Variable stars load
- [ ] Charts display
- [ ] Catalog import works
- [ ] Admin counts match pre-migration
- [ ] Logs show no errors

---

## 🎯 Success Criteria

✅ **You're done if:**
- Migration script output ends with "✅ Migration complete"
- Validation script output shows "✅ All checks passed"
- Can login and see dashboard
- Variable stars project loads with chart
- Row counts match expectations
- No errors in logs after 5 minutes

❌ **Rollback if:**
- Any step fails/hangs
- Row counts don't match
- Can't login after 10 minutes
- Charts don't display
- Catalog import fails
- Logs full of "ERROR" messages

---

## 📞 If You're Stuck

1. **Check logs first**:
   ```bash
   tail -100 /var/log/astrogen/astrogen.log
   ```

2. **Check database connection**:
   ```bash
   psql -U agata_user -d catalogo_pg -c "SELECT 1"
   ```

3. **Check Flask can import**:
   ```bash
   python -c "from app import app; print('OK')"
   ```

4. **When in doubt, restore backup**:
   ```bash
   mysql -u catalogo_user -p catalogo < backups/catalogo_latest.sql
   git reset --hard v2.14.10
   sudo systemctl start apache2
   ```

5. **Then contact your admin** with:
   - Error message
   - Timestamp it occurred
   - Which step failed
   - Contents of `/var/log/strogen/astrogen.log`

---

## 🎓 Key Concepts (Read This First If You're New)

### What's Changing?
- **Database**: MySQL → PostgreSQL (different system, better performance)
- **Code**: All SQL queries updated to PostgreSQL syntax
- **Column names**: `Source` becomes `source_id`, `Vmag` becomes `vmag`
- **Users**: No change, same login

### Why?
- PostgreSQL is more reliable and faster
- Better type safety
- Fewer MySQL-specific quirks
- Same functionality for end users

### What could go wrong?
- Migration script fails to copy data (rare, handled by validation)
- Flask can't connect to PostgreSQL (fixable, check .env)
- Old column names in code (won't happen, all updated)
- FK constraints violated (won't happen, migration validates)

### Recovery?
- If anything goes wrong: restore MySQL backup and revert to v2.14.10
- Migration is **reversible** as long as you have the backup

---

## 📚 Full Documentation

- **Full guide**: `docs/DEPLOYMENT_v3.0.0_POSTGRESQL.md`
- **Errors & fixes**: `docs/MIGRATION_ERRORS_LESSONS_LEARNED.md`
- **Technical details**: `docs/MIGRATION_COMPLETE_SUMMARY.md`
- **Code changes**: `git log v2.14.10..v3.0.0`

---

**Version**: v3.0.0  
**Tested**: Development (1.76M rows, 2+ hours)  
**Last Updated**: 2026-04-12  
**Ready For**: Production
