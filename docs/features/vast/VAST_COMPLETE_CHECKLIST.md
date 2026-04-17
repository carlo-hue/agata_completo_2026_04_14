# VAST-Automation Implementation - Complete Checklist

**Status**: ✅ Phase 3/5 Complete (Implementation Done)

---

## 📋 Implementation Summary

### Components Implemented
- ✅ Database models (VastJob, VastResult)
- ✅ Service layer (VastExecutor, GoogleDriveService, VastService)
- ✅ Web routes and UI (/agata/admin/vast)
- ✅ OAuth 2.0 authentication (no hardcoded credentials)
- ✅ Background job processing (daemon threads)
- ✅ Error handling and cleanup

### Files Created (11 new files)

```
agata/auth_models/vast_job.py                              ← Database models
agata/admin/services/vast_executor.py                      ← VAST wrapper
agata/admin/services/google_drive_service.py               ← Google Drive (OAuth)
agata/admin/services/vast_service.py                       ← Main orchestrator
agata/admin/routes/vast_automation.py                      ← Web routes
agata/templates/admin/vast/jobs.html                       ← Job list UI
agata/templates/admin/vast/job_detail.html                 ← Job detail UI
docs/migrations/001_create_vast_tables.sql                 ← Database schema
config/google_client_secret.example.json                   ← OAuth template
config/.gitignore                                          ← Protect secrets
config/README.md                                           ← Config docs
scripts/verify_oauth_credentials.py                        ← Verification script
```

### Files Modified (4 files)

```
agata/auth_models/__init__.py                              ← Added VastJob exports
agata/admin/__init__.py                                    ← Registered routes
requirements.txt                                           ← OAuth dependencies
.env                                                       ← VAST configuration
```

### Documentation Created (4 files)

```
VAST_SETUP_GUIDE.md                                        ← Setup instructions
VAST_IMPLEMENTATION_SUMMARY.md                             ← Architecture overview
VAST_OAUTH_SETUP.md                                        ← OAuth guide
VAST_OAUTH_DOWNLOAD.md                                     ← Download credentials
VAST_COMPLETE_CHECKLIST.md                                 ← This file
```

---

## 🚀 Quick Start (5 Minutes)

### Step 1: Get Google Credentials ⏱️ 2 min

```bash
# Go to: https://console.cloud.google.com/apis/credentials
#
# Find existing "VAST-Automation" OAuth credential or create new:
# - Type: Desktop application
# - Download JSON file
```

### Step 2: Copy Credentials File ⏱️ 30 sec

```bash
cd /var/www/astrogen
cp ~/Downloads/client_secret.json ./config/google_client_secret.json
```

### Step 3: Verify Configuration ⏱️ 1 min

```bash
python scripts/verify_oauth_credentials.py

# Expected output:
# ✅ File exists
# ✅ Valid JSON
# ✅ All required fields
# ✅ All checks PASSED!
```

### Step 4: Install Dependencies ⏱️ 1 min

```bash
pip install -r requirements.txt

# Already installed (check):
# ✅ google-auth-oauthlib==1.2.0
# ✅ google-auth-httplib2==0.2.0
# ✅ google-api-python-client==2.105.0
```

### Step 5: Setup Database ⏱️ 1 min

```bash
mysql -u aaaat01 -p catalogo < docs/migrations/001_create_vast_tables.sql

# Verify:
mysql -u aaaat01 -p catalogo -e "SHOW TABLES LIKE 'agata_vast%';"
```

---

## 🔧 Pre-Deployment Checklist

### Configuration
- [ ] Google credentials file downloaded from GCP Console
- [ ] File copied to `./config/google_client_secret.json`
- [ ] Verification script passes: `python scripts/verify_oauth_credentials.py`
- [ ] `.env` has `GOOGLE_CLIENT_SECRET_FILE=./config/google_client_secret.json`
- [ ] `.env` has `VAST_BINARY_PATH` pointing to VAST binary

### Dependencies
- [ ] `pip install -r requirements.txt` completes successfully
- [ ] No import errors when starting Flask
- [ ] OAuth libraries available: `python -c "from google_auth_oauthlib.flow import InstalledAppFlow"`

### Database
- [ ] Migration SQL runs without errors
- [ ] Tables created: `agata_vast_jobs` and `agata_vast_results`
- [ ] Foreign keys valid (no constraint errors)
- [ ] Indices present for performance

### Application
- [ ] Flask starts: `python -m flask run`
- [ ] No import errors in logs
- [ ] Superuser can access `/agata/admin/vast`
- [ ] Admin sidebar shows "VAST Automation" (may need template update)

### Security
- [ ] `./config/.gitignore` protects credentials
- [ ] No `google_client_secret.json` in git history: `git log --all -- config/google_client_secret.json`
- [ ] File permissions are restrictive: `ls -l ./config/google_client_secret.json`
- [ ] No credentials in `.env` (only path to file)

---

## 📊 Workflow States

Job lifecycle (9 states):

```
pending
    ↓
downloading (get images from Drive/local)
    ↓
validating (WCS check with Astropy)
    ↓
vast_analysis (run VAST photometry)
    ↓
uploading (save to database)
    ↓
completed ✅

OR

failed ❌ (error occurred, see error_message)
```

Progress updates every 10% approximately.

---

## 🧪 Testing Checklist

### Basic Functionality
- [ ] Visit `/agata/admin/vast` (superuser login required)
- [ ] Job list page loads
- [ ] "New Job" button appears
- [ ] Modal form opens

### Job Creation
- [ ] Create job with local path (test data)
- [ ] Form validation works (required fields)
- [ ] Job appears in list with "pending" state

### Job Execution
- [ ] Job transitions to "downloading" → "validating" → "vast_analysis" → "uploading" → "completed"
- [ ] Progress bar updates (0% → 100%)
- [ ] Current step shows what's happening

### Database
- [ ] VastJob record created in database
- [ ] VastResult records created for candidates
- [ ] Audit log entry for job creation
- [ ] No orphaned records after completion

### Error Handling
- [ ] Invalid folder ID shows error
- [ ] Disk space error handled gracefully
- [ ] Job state set to "failed" on error
- [ ] Error message visible in UI

### OAuth
- [ ] First run: browser opens for authorization
- [ ] Subsequent runs: token reused (no browser)
- [ ] Token saved to `~/.agata/google_drive_token.json`
- [ ] Token auto-refreshes when expired

---

## 📦 Dependencies

### Old (Removed)
```
pydrive2==1.15.3        ❌ Replaced
gspread==5.12.0         ❌ Replaced
oauth2client==4.1.3     ❌ Replaced
```

### New (Added)
```
google-auth-oauthlib==1.2.0         ✅ OAuth 2.0
google-auth-httplib2==0.2.0         ✅ HTTP adapter
google-api-python-client==2.105.0   ✅ Google APIs
```

### Already Present (Reused)
```
astropy==7.2.0          ✅ WCS validation
pandas==2.3.1           ✅ Data parsing
numpy==2.3.2            ✅ Numerical ops
Flask==3.1.2            ✅ Web framework
SQLAlchemy==2.0.45      ✅ Database ORM
```

---

## 🔒 Security

### Credentials Protection
- ✅ OAuth 2.0 (no service account keys)
- ✅ Credentials in `.gitignore`
- ✅ Token per-machine (~/.agata/)
- ✅ Auto-refresh when expired
- ✅ Revocable via Google account

### Code Security
- ✅ No shell=True in subprocess
- ✅ SQLAlchemy ORM (no SQL injection)
- ✅ Input validation before processing
- ✅ RBAC via @superuser_required decorator
- ✅ All ops logged to audit trail

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| VAST_SETUP_GUIDE.md | Full setup with troubleshooting |
| VAST_IMPLEMENTATION_SUMMARY.md | Architecture and decisions |
| VAST_OAUTH_SETUP.md | OAuth workflow details |
| VAST_OAUTH_DOWNLOAD.md | Credentials download steps |
| config/README.md | Configuration explanation |
| scripts/verify_oauth_credentials.py | Automated verification |

---

## 🎯 Next Phase: Testing (Phase 4)

**When ready:**

1. **Run pre-deployment checks** (above)
2. **Database setup**: Run migration SQL
3. **Dependencies**: `pip install -r requirements.txt`
4. **Verify OAuth**: `python scripts/verify_oauth_credentials.py`
5. **Start Flask**: `python -m flask run`
6. **Test UI**: Visit `/agata/admin/vast`
7. **Create test job**: Use local path with test FITS files
8. **Monitor execution**: Watch state transitions and progress
9. **Verify results**: Check database records
10. **Test error handling**: Verify error states and cleanup

---

## 🚢 Deployment

Once tested and approved:

```bash
# 1. Merge to main
git merge senza-layer main

# 2. Deploy database schema
mysql -u aaaat01 -p catalogo < docs/migrations/001_create_vast_tables.sql

# 3. Install/update dependencies
pip install -r requirements.txt

# 4. Restart Flask
systemctl restart agata-flask
# or
python -m flask run

# 5. Verify
curl https://app-test.astrogen.it/agata/admin/vast
```

---

## 📝 Notes

### Why OAuth 2.0?
- More secure than service account keys
- User-approved, not automated service
- Revocable anytime
- Auto-refresh, no manual token management
- Better for production environments

### Why Credentials in Project?
- Not tied to external `/dati/` filesystem
- Always available when cloning repo
- Easy to backup and migrate
- Protected by `.gitignore`
- Docker-friendly

### Why Async/Background Jobs?
- Non-blocking UI (Flask stays responsive)
- Long-running VAST analysis doesn't timeout
- User can check status later
- Multiple jobs can run concurrently
- Daemon threads are lightweight

### Performance Targets
- **Download**: ~1-10 GB/hr from Drive
- **WCS validation**: ~1-10 sec/image
- **VAST analysis**: Highly variable (5 min - 2 hours)
- **Upload**: 100-1000 candidates/sec to MySQL

---

## ✅ Final Status

**Implementation**: ✅ COMPLETE (1,500+ lines of code)
**Testing**: ⏳ PENDING (Phase 4)
**Documentation**: ✅ COMPLETE
**Security**: ✅ COMPLETE
**Dependencies**: ✅ INSTALLED

**Status**: Ready for Phase 4 Testing & Verification

---

**Last Updated**: 2026-02-06
**Version**: 1.0 Implementation Complete
