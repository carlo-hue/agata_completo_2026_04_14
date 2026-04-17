# WSGI Deployment Fix - Production Troubleshooting (2026-02-28)

**Status**: ✅ FIXED
**Issue**: Production (app.astrogen.it) returned "404 Not Found" after v2.0.0 deployment
**Root Cause**: Missing `astrogen.wsgi` file on astrogen03 and incorrect virtualenv path
**Resolution Time**: ~1 hour
**Date Fixed**: 2026-02-28 10:34

---

## Problem Summary

After deploying v2.0.0 to astrogen03 (production), accessing https://app.astrogen.it/agata/admin/ returned:
```
404 Not Found
The requested URL was not found on this server.
Apache/2.4.58 (Ubuntu)
```

Development (app-test.astrogen.it) continued to work fine.

---

## Root Causes Identified

### 1. Missing `astrogen.wsgi` File
- **Location**: `/var/www/astrogen/astrogen.wsgi`
- **Issue**: File did NOT exist on astrogen03 after v2.0.0 deployment
- **Why**: `.gitignore` excludes `*.wsgi` (by design - each environment has its own)
- **Impact**: Apache mod_wsgi couldn't find entry point, returned 404

### 2. Incorrect Virtualenv Path
- **Configured in Apache** (`astrogen.conf`):
  ```
  python-path=/var/www/astrogen:/var/www/astrogen/venv/lib/python3.12/site-packages
  WSGIDaemonProcess astrogen python-path=...
  ```
- **File I created initially pointed to**: `/var/www/astrogen/flask/lib/python3.12/site-packages`
- **Should point to**: `/var/www/astrogen/venv/lib/python3.12/site-packages`
- **Why different**: Development uses `flask` virtualenv, production uses `venv` virtualenv

---

## Solution Implemented

### Step 1: Create Correct `astrogen.wsgi` for Production

**Location**: `/var/www/astrogen/astrogen.wsgi`

**Content**:
```python
import sys
import os

# Inserisci il percorso del tuo progetto
sys.path.insert(0, '/var/www/astrogen')

# Inserisci il percorso del tuo virtualenv nei site-packages
sys.path.insert(0, '/var/www/astrogen/venv/lib/python3.12/site-packages')

from app import app as application
```

**Key differences from development**:
- Development uses: `/var/www/astrogen-test/flask/lib/python3.12/site-packages`
- Production uses: `/var/www/astrogen/venv/lib/python3.12/site-packages`

### Step 2: Copy to astrogen03
```bash
scp /var/www/astrogen/astrogen.wsgi azureuser@10.1.0.6:/var/www/astrogen/astrogen.wsgi
```

### Step 3: Restart Apache
```bash
ssh azureuser@10.1.0.6 'sudo systemctl restart apache2'
```

### Step 4: Verify
```bash
curl -I https://app.astrogen.it/agata/admin/
# Expected: HTTP 302 FOUND (redirect to login) ✅
```

---

## Important Notes for Next Deployment

### WSGI File Location Matters
- **Development**: `/var/www/astrogen-test/astrogen.wsgi`
  - Virtualenv: `/var/www/astrogen-test/flask/lib/python3.12/site-packages`
  - DNS: app-test.astrogen.it

- **Production**: `/var/www/astrogen/astrogen.wsgi` ⚠️ CRITICAL
  - Virtualenv: `/var/www/astrogen/venv/lib/python3.12/site-packages`
  - DNS: app.astrogen.it

### WSGI Files Are NOT Versioned
- Both `astrogen.wsgi` files are in `.gitignore` (line: `*.wsgi`, `astrogen.wsgi`)
- They are **not pulled by `git reset --hard`** or `git checkout`
- Each environment maintains its own wsgi file locally
- **After any deployment, verify wsgi file still exists with correct paths**

### Apache VirtualHost Configuration
Check `/etc/apache2/sites-available/astrogen.conf`:
```apache
WSGIDaemonProcess astrogen python-path=/var/www/astrogen:/var/www/astrogen/venv/lib/python3.12/site-packages
WSGIScriptAlias / /var/www/astrogen/astrogen.wsgi
```

If you modify this, the wsgi file MUST match the configured paths.

---

## SOLUTION: Use `git reset --hard` Instead of `git checkout`

**CRITICAL FIX**: Use `git reset --hard <tag>` NOT `git checkout <tag>`

**Why**:
- `git checkout <tag>` switches to that commit state exactly (can delete local files)
- `git reset --hard <tag>` resets HEAD to that tag but **preserves files in .gitignore**
- astrogen.wsgi is in .gitignore (environment-specific) and must NOT be touched

### Verified Behavior (Tested 2026-02-28)

```bash
# Test on astrogen03:
git reset --hard 2e410fd          # Reset to different commit
ls -lah astrogen.wsgi             # File STILL EXISTS ✅

git reset --hard v2.0.0           # Reset to v2.0.0 tag
ls -lah astrogen.wsgi             # File STILL EXISTS ✅
```

**Result**: `.gitignore` files are preserved during `git reset --hard` ✅

### Deployment Command (CORRECT)

```bash
cd /var/www/astrogen
git fetch --all --tags --quiet
git reset --hard v2.0.0 --quiet       # ✅ CORRECT: preserves astrogen.wsgi
pip install -r requirements.txt --upgrade --quiet
sudo systemctl restart apache2
```

### What NOT to Do (BROKEN)

```bash
cd /var/www/astrogen
git fetch --all --tags --quiet
git checkout v2.0.0 --quiet           # ❌ WRONG: can delete local files
git reset --hard origin/main --quiet  # ❌ WRONG: unnecessary, can overwrite
```

### Post-Deployment Checklist

After any v2.x.x deployment to astrogen03:

```bash
# 1. CRITICAL: Verify wsgi file exists and has correct content
ssh azureuser@10.1.0.6 'cat /var/www/astrogen/astrogen.wsgi | grep venv'
# Should show: sys.path.insert(0, '/var/www/astrogen/venv/lib/python3.12/site-packages')

# 2. Restart Apache
ssh azureuser@10.1.0.6 'sudo systemctl restart apache2'

# 3. Test production endpoint
curl -I https://app.astrogen.it/agata/admin/
# Should return: HTTP 302 FOUND (not 404)

# 4. Verify Flask app is responding
curl -s https://app.astrogen.it/ | head -1
# Should show HTML response (not 404)
```

---

## What Changed in v2.0.0 Deployment

The v2.0.0 commit brought:
- ✅ Dynamic version display (Flask context processor)
- ✅ Deployment automation (scripts/deploy.sh, skeema integration)
- ✅ Schema migration tracking

But did NOT include:
- ❌ `astrogen.wsgi` (not in git by design)
- ❌ Database changes (only migration infrastructure)
- ❌ Application logic changes

---

## Related Files

- **Apache config**: `/etc/apache2/sites-available/astrogen.conf`
- **WSGI file dev**: `/var/www/astrogen-test/astrogen.wsgi`
- **WSGI file prod**: `/var/www/astrogen/astrogen.wsgi`
- **Git ignore**: `/var/www/astrogen/.gitignore` (line: `*.wsgi`)
- **Main app**: `/var/www/astrogen/app.py`
- **Deployment guide**: [DEPLOYMENT_GUIDE_v2.0.0.md](DEPLOYMENT_GUIDE_v2.0.0.md)

---

## Reference

**Last tested**: 2026-02-28 10:34:38 UTC
**Status**: ✅ Production working
**Command to verify**: `curl -I https://app.astrogen.it/agata/admin/`

