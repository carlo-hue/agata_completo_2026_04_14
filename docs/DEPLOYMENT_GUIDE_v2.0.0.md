# AGATA Deployment Guide v2.0.0 - astrogen01 (Dev) → astrogen03 (Prod)

**Last Updated**: 2026-02-28
**Version**: v2.0.0
**Status**: Production Ready
**Based on**: Real-world deployment (Feb 28, 2026)

---

## ⚠️ CRITICAL: Understand Your Git Setup

### Repository Configuration

- **astrogen01** (Development):
  - Remote `origin` → `git@github.com:giorgio-astrogen/flask.git` (flask repo, source of truth)
  - Branch: `main`
  - Role: Sviluppo e push del codice

- **astrogen03** (Production):
  - Remote `origin` → `git@github.com-astrogen03:giorgio-astrogen/astrogen.git` (repo backup/copia)
  - Remote `dev` → `git@github.com:giorgio-astrogen/flask.git` (flask repo, source of truth)
  - Branch: `main`
  - Role: Riceve il codice dal remote `dev` (flask repo)

**KEY INSIGHT**: Il codice risiede nel repo `flask`. astrogen01 lo pusha via `origin`; astrogen03 lo fetcha via remote `dev`. Il deploy.sh gestisce questo automaticamente.

---

## Quick Deployment (TL;DR)

```bash
# On astrogen01 (development)
git status                    # Ensure clean
git log -1 --oneline          # Check latest commit
git push origin main          # Push to GitHub
git push origin v2.0.0        # Push version tag (if new version)

# Then on astrogen03 (production) - via SSH
ssh azureuser@10.1.0.6 'bash -s' << 'DEPLOY'
cd /var/www/astrogen
git fetch --all --tags --quiet
git checkout v2.0.0 --quiet       # Or latest tag
git reset --hard origin/main --quiet
pip install -r requirements.txt --upgrade --quiet
# Restart services (depends on your setup)
DEPLOY

# Verify
curl https://app-test.astrogen.it/agata/admin/
```

---

## Full Deployment Procedure (Step-by-Step)

### STEP 1: Prepare on astrogen01 (Development)

#### 1.1 Verify Git Status
```bash
cd /var/www/astrogen
git status --short           # MUST be empty (no uncommitted changes)
git log -1 --oneline         # Check latest commit
```

**Expected output**: Clean working directory

#### 1.2 Make Your Changes
```bash
# Edit code, tests, docs, etc.
vim agata/templates/admin/base.html
python agata/auth_models/user.py

# Update version if major release
vim agata/__init__.py         # Change __version__ = '2.1.0'
```

#### 1.3 Commit Changes
```bash
git add .
git commit -m "v2.1.0: description of changes"
```

#### 1.4 Create Version Tag (if new version)
```bash
git tag -a v2.1.0 -m "v2.1.0: Release description"
```

#### 1.5 Push to GitHub
```bash
git push origin main --quiet
git push origin v2.1.0 --quiet    # If creating new version
```

**Verify on GitHub**: Check `https://github.com/giorgio-astrogen/flask` - should see new commit on `main` branch

---

### STEP 2: Deploy to astrogen03 (Production)

#### 2.1 Backup Production Database (CRITICAL!)
```bash
ssh azureuser@10.1.0.6 << 'BACKUP'
cd /var/www/astrogen
DB_PASS=$(grep DATABASE_URL .env | python3 -c "import sys,urllib.parse; u=urllib.parse.urlparse(sys.stdin.read().strip().split('=',1)[1]); print(urllib.parse.unquote(u.password))")
mysqldump -u aaaat01 -p"$DB_PASS" --single-transaction catalogo | gzip > ~/backup_catalogo_$(date +%Y%m%d_%H%M%S).sql.gz
echo "✅ Backup created"
BACKUP
```

**Verify**: Check `~/backup_catalogo_*.sql.gz` exists on astrogen03

#### 2.2 Fetch Latest Code from GitHub
```bash
ssh azureuser@10.1.0.6 << 'FETCH'
cd /var/www/astrogen
git fetch --all --tags --quiet
FETCH
```

#### 2.3 Checkout Version Tag
```bash
ssh azureuser@10.1.0.6 << 'CHECKOUT'
cd /var/www/astrogen

# Option A: Checkout specific version tag
git checkout v2.1.0 --quiet

# Option B: If tag not available yet, checkout main
# git checkout main --quiet
# git reset --hard origin/main --quiet

echo "Current commit:"
git log -1 --oneline
CHECKOUT
```

**Verify**: Commit should match what you pushed from astrogen01

#### 2.4 Update Python Dependencies
```bash
ssh azureuser@10.1.0.6 << 'DEPS'
cd /var/www/astrogen
source venv/bin/activate || source flask/bin/activate || true
pip install -r requirements.txt --upgrade --quiet
DEPS
```

#### 2.5 Restart Application Services

⚠️ **This depends on your setup**. Common options:

```bash
# Option A: Systemd service
ssh azureuser@10.1.0.6 'sudo systemctl restart agata-flask && sudo systemctl restart nginx'

# Option B: Manual WSGI restart (gunicorn, uwsgi, etc.)
ssh azureuser@10.1.0.6 'pkill -f gunicorn && cd /var/www/astrogen && gunicorn -w 4 -b 0.0.0.0:5000 app:app --daemon'

# Option C: Your custom script
ssh azureuser@10.1.0.6 '/var/www/astrogen/restart_services.sh'
```

Wait 3-5 seconds for services to restart.

---

### STEP 3: Verify Deployment

#### 3.1 Check Deployed Commit
```bash
ssh azureuser@10.1.0.6 'cd /var/www/astrogen && git log -1 --oneline'
```

**Expected**: Shows your v2.1.0 commit from astrogen01

#### 3.2 Check Version in Code
```bash
ssh azureuser@10.1.0.6 'grep "__version__" /var/www/astrogen/agata/__init__.py'
```

**Expected**: `__version__ = '2.1.0'`

#### 3.3 Verify Critical Files Exist
```bash
ssh azureuser@10.1.0.6 << 'VERIFY'
# Check for v2.0.0+ features
grep -q '@app.context_processor' /var/www/astrogen/app.py && echo "✅ Context processor found"
grep -q 'v{{ app_version }}' /var/www/astrogen/agata/templates/admin/base.html && echo "✅ Admin version badge found"
grep -q 'v{{ app_version }}' /var/www/astrogen/agata/templates/variable_stars/index.html && echo "✅ Variable Stars version found"
VERIFY
```

#### 3.4 Test Health Endpoints
```bash
# Direct test on server
ssh azureuser@10.1.0.6 'curl -sf http://localhost:5000/health'

# OR from browser
# https://app-test.astrogen.it/agata/admin/
# https://app-test.astrogen.it/agata/variable-stars/
```

**Expected**: HTTP 200 and page loads without errors

---

## Common Errors & Fixes

### Error: "fatal: couldn't find remote ref v2.1.0"

**Cause**: Tag not pushed to GitHub yet

**Fix**:
```bash
# On astrogen01
git push origin v2.1.0

# Then on astrogen03
ssh azureuser@10.1.0.6 'cd /var/www/astrogen && git fetch --tags'
git checkout v2.1.0
```

### Error: "error: Your local changes to the following files would be overwritten"

**Cause**: Local changes on astrogen03 that conflict with pull

**Fix**:
```bash
# Option A: Stash local changes
ssh azureuser@10.1.0.6 'cd /var/www/astrogen && git stash'

# Option B: Force reset (⚠️ loses local changes)
ssh azureuser@10.1.0.6 'cd /var/www/astrogen && git reset --hard origin/main'
```

### Error: "fatal: not a git repository"

**Cause**: SSH doesn't cd to correct directory

**Fix**: Always use full path or explicit cd
```bash
# ❌ Wrong
ssh azureuser@10.1.0.6 'git log -1'

# ✅ Right
ssh azureuser@10.1.0.6 'cd /var/www/astrogen && git log -1'
```

### Services Don't Restart

**Check what's running**:
```bash
ssh azureuser@10.1.0.6 'ps aux | grep -E "wsgi|gunicorn|flask|nginx"'
```

**Common service names**:
- `agata-flask` (systemd service)
- `agata.service` (systemd service)
- `gunicorn` (process, kill and restart manually)
- `nginx` (web server)

---

## Rollback Procedure (If Something Goes Wrong)

### Quick Rollback
```bash
# On astrogen03
ssh azureuser@10.1.0.6 << 'ROLLBACK'
cd /var/www/astrogen

# Go back to previous version
git checkout v2.0.0    # Previous stable version
git reset --hard origin/main --quiet

# Restore database backup
DB_BACKUP=~/backup_catalogo_20260228_100342.sql.gz
gunzip < $DB_BACKUP | mysql -u aaaat01 -p catalogo

# Restart services
# (use appropriate restart command for your setup)

ROLLBACK
```

### Full Rollback Steps
1. SSH to astrogen03
2. Stop Flask service
3. Restore database: `gunzip < ~/backup_catalogo_*.sql.gz | mysql -u aaaat01 -p catalogo`
4. Checkout previous git tag: `git checkout v2.0.0`
5. Restart Flask service
6. Verify: `curl https://app-test.astrogen.it/agata/admin/`

---

## Deployment Checklist

### Before Deploying
- [ ] Git working directory clean on astrogen01
- [ ] All changes committed
- [ ] Version updated in `agata/__init__.py` (if new release)
- [ ] Version tag created (if new release)
- [ ] Pushed to GitHub: `git push origin main --tags`

### During Deployment
- [ ] Backup created on astrogen03
- [ ] Code fetched from GitHub
- [ ] Correct version checked out
- [ ] Dependencies updated
- [ ] Services restarted

### After Deployment
- [ ] Deployed commit matches astrogen01
- [ ] Version matches expected version
- [ ] Critical files present (context processor, version badges)
- [ ] Health check passed (curl endpoint)
- [ ] Opened URL in browser, verified working

---

## Performance Metrics

### Typical Deployment Time
- Database backup: 1-2 minutes
- Code fetch: 30 seconds
- Dependencies update: 1-2 minutes
- Services restart: 10-30 seconds
- **Total**: ~5 minutes

### What Changed in v2.0.0
- ✅ **Dynamic version display** (Flask context processor)
  - Shows in browser title tabs
  - Shows in sidebars (admin + variable_stars)
- ✅ **Unified deployment script** (./scripts/deploy.sh)
  - 6x faster deployment (30 min → 5 min)
  - Automatic schema diffing with skeema
  - Automatic backups

---

## Future Improvements (When Needed)

1. **CI/CD Pipeline**: GitHub Actions to auto-deploy on push
2. **Zero-Downtime Deploy**: Blue-green or rolling deployment
3. **Automated Health Checks**: More comprehensive endpoint testing
4. **Slack Notifications**: Auto-notify when deployment completes
5. **Database Migrations**: Formal migration system (Alembic)

---

## Quick Reference

```bash
# Minimal deployment script (copy & paste)
# On astrogen01:
git push origin main && git push origin v2.1.0

# On astrogen03 (via SSH):
ssh azureuser@10.1.0.6 << 'DEPLOY'
cd /var/www/astrogen
git fetch --all --tags --quiet
git checkout v2.1.0 --quiet
git reset --hard origin/main --quiet
pip install -r requirements.txt --upgrade --quiet
# Restart your services here
DEPLOY
```

---

## Notes for Next Deployment

- ✅ Both servers use same GitHub repo (`flask`)
- ✅ Always fetch `--tags` to get version tags
- ✅ Use `git checkout <tag>` for releases, not branches
- ✅ Always backup database BEFORE pulling code
- ✅ Verify deployment with curl before opening in browser
- ⚠️ Check systemd service names for your environment

---

**Last Tested**: 2026-02-28 (v2.0.0 deployment to astrogen03)
**Status**: ✅ Verified working
