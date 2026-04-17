# VAST-Automation Setup & Verification Guide

## Overview

This guide walks through setting up the VAST-Automation feature integrated into AGATA.

## Prerequisites

- VAST binary installed at `/home/azureuser/Documents/vast-1.0rc87/vast`
- Google Drive service account JSON at `/dati/codice/pythonvast/googlesheet.json`
- MySQL database with AGATA tables
- Python 3.10+

## Step 1: Install Dependencies

```bash
cd /var/www/astrogen
pip install -r requirements.txt
```

Should install:
- pydrive2==1.15.3
- gspread==5.12.0
- oauth2client==4.1.3

Verify installation:
```bash
python -c "from pydrive2.auth import GoogleAuth; from agata.admin.services.vast_executor import VastExecutor; print('✓ Dependencies OK')"
```

## Step 2: Create Database Tables

```bash
mysql -u aaaat01 -p catalogo < docs/migrations/001_create_vast_tables.sql
```

Verify tables created:
```bash
mysql -u aaaat01 -p catalogo -e "SHOW TABLES LIKE 'agata_vast%';"
```

Expected output:
```
agata_vast_jobs
agata_vast_results
```

## Step 3: Verify Configuration

Check `.env` file has:
```bash
VAST_BINARY_PATH=/home/azureuser/Documents/vast-1.0rc87/vast
GOOGLE_SERVICE_ACCOUNT_PATH=/dati/codice/pythonvast/googlesheet.json
```

Verify files exist:
```bash
ls -l /home/azureuser/Documents/vast-1.0rc87/vast
ls -l /dati/codice/pythonvast/googlesheet.json
```

## Step 4: Start Flask App

```bash
cd /var/www/astrogen
python -m flask run
```

Or with Gunicorn:
```bash
gunicorn -b 127.0.0.1:5000 "agata.app:app"
```

## Step 5: Access VAST Interface

1. Go to: https://app-test.astrogen.it/agata/admin/vast
2. Login with superuser account
3. Should see "VAST Automation" page with "New Job" button

## Step 6: Create Test Job

### Option A: Local Path (Easiest)

```bash
# Prepare test data
mkdir -p /tmp/test_fits
cp /path/to/sample/*.fits /tmp/test_fits/
```

In web UI:
1. Click "New Job"
2. Fill:
   - Target Name: `Test Target`
   - Source Type: `Local Path`
   - Source Location: `/tmp/test_fits`
3. Click "Start Processing"

### Option B: Google Drive Folder

1. Get Google Drive folder ID from URL: `https://drive.google.com/drive/folders/{FOLDER_ID}`
2. Click "New Job"
3. Fill:
   - Target Name: `Test Target`
   - Source Type: `Google Drive Folder`
   - Source Location: `{FOLDER_ID}`
4. Click "Start Processing"

## Step 7: Monitor Job Execution

### In Web UI

1. Click job code to open detail page
2. Status updates every 5 seconds (auto-refresh)
3. Watch progress from 0% → 100%

### In Terminal

Watch logs:
```bash
tail -f logs/agata.log | grep VAST
```

Or check database:
```bash
mysql -u aaaat01 -p catalogo -e "SELECT id, job_code, state, progress_pct FROM agata_vast_jobs ORDER BY created_at DESC LIMIT 5;"
```

### Expected Workflow

```
pending → downloading → validating → vast_analysis → uploading → completed
```

Each step takes time depending on image count and VAST complexity.

## Step 8: Verify Results

After job completes (state = `completed`):

1. **Check database records:**
```bash
mysql -u aaaat01 -p catalogo -e "
  SELECT id, job_code, state, candidates_found, stars_uploaded
  FROM agata_vast_jobs
  WHERE job_code = 'VAST-2026-0001';
"
```

2. **Check results table:**
```bash
mysql -u aaaat01 -p catalogo -e "
  SELECT id, vast_id, ra, decl, mean_mag, variability_index
  FROM agata_vast_results
  LIMIT 10;
"
```

3. **Check audit log:**
```bash
mysql -u aaaat01 -p catalogo -e "
  SELECT user_email, action, entity_id, description, created_at
  FROM agata_audit_logs
  WHERE action LIKE 'vast%'
  ORDER BY created_at DESC
  LIMIT 10;
"
```

## Troubleshooting

### Issue: "VAST binary not found"

```
FileNotFoundError: VAST binary not found: /home/azureuser/Documents/vast-1.0rc87/vast
```

**Fix:**
- Verify VAST_BINARY_PATH in .env
- Check file exists: `ls -l /home/azureuser/Documents/vast-1.0rc87/vast`
- If path wrong, update .env and restart app

### Issue: "Google service account JSON not found"

```
FileNotFoundError: Google service account JSON not found: /dati/codice/pythonvast/googlesheet.json
```

**Fix:**
- Verify GOOGLE_SERVICE_ACCOUNT_PATH in .env
- Check file exists: `ls -l /dati/codice/pythonvast/googlesheet.json`
- Ensure JSON is valid: `python -m json.tool < /dati/codice/pythonvast/googlesheet.json`

### Issue: "Insufficient disk space"

```
RuntimeError: Insufficient disk space: need 50.00 GB, have 25.00 GB
```

**Fix:**
- Free up disk space
- Use smaller test images
- Or use local path (no download overhead)

### Issue: Job stuck in "downloading" state

**Check logs:**
```bash
tail -f logs/agata.log | grep -i "download\|error"
```

**Possible causes:**
- Network issue with Google Drive
- Invalid folder ID
- Insufficient permissions on service account

**Fix:**
- Check Google Drive folder ID is correct
- Verify service account has read permissions
- Restart job

### Issue: VAST analysis fails

**Check database:**
```bash
mysql -u aatat01 -p catalogo -e "
  SELECT job_code, state, error_message
  FROM agata_vast_jobs
  WHERE state = 'failed';
"
```

**Possible causes:**
- FITS files are corrupted
- VAST binary crashed
- Wrong VAST parameters

**Fix:**
- Check FITS files: `file /tmp/*.fits`
- Try with different images
- Check VAST logs in VAST installation directory

## Performance Tips

1. **Batch jobs**: Create multiple jobs simultaneously (background threads scale well)
2. **Monitor disk**: Check `df -h /` regularly
3. **Test locally first**: Use local path before Google Drive
4. **Small datasets**: Start with 5-10 FITS images for testing

## Security Checklist

- [ ] VAST binary owned by www-data (or app user)
- [ ] Google service account key not committed to Git
- [ ] .env file not world-readable: `chmod 600 .env`
- [ ] Database user has limited permissions (read/write to agata* tables only)
- [ ] Superuser access restricted to authorized users
- [ ] Audit logs enabled for all VAST operations

## Rollback Instructions

If something breaks, revert these changes:

```bash
# Remove files
rm -rf agata/admin/services/vast_executor.py
rm -rf agata/admin/services/google_drive_service.py
rm -rf agata/admin/services/vast_service.py
rm -rf agata/admin/routes/vast_automation.py
rm -rf agata/templates/admin/vast/

# Remove models
rm -rf agata/auth_models/vast_job.py

# Drop tables (careful!)
mysql -u aaaat01 -p catalogo -e "DROP TABLE agata_vast_results; DROP TABLE agata_vast_jobs;"

# Revert dependencies
pip uninstall -y pydrive2 gspread oauth2client
```

## References

- [VAST Documentation](https://www.vast.ac.uk/wiki/bin/view/Vast/)
- [Google Drive API](https://developers.google.com/drive/api)
- [AGATA Architecture](docs/ARCHITECTURE.md)
- [Database Schema](docs/DATABASE_SCHEMA.md)

## Support

For issues, check:
1. Logs: `logs/agata.log`
2. Database: `SELECT * FROM agata_vast_jobs WHERE id = <job_id>`
3. Audit trail: `SELECT * FROM agata_audit_logs WHERE entity_id = '<job_id>'`

## Next Steps

After verification:

1. Test with real astronomical data
2. Implement catalog cross-matching (Gaia, VSX)
3. Add automatic project creation from results
4. Set up email notifications
5. Consider Celery for production job queue

---

**Last Updated**: 2026-02-06
**Status**: Phase 3 Complete
**Phase 4**: Pending Testing & Verification
