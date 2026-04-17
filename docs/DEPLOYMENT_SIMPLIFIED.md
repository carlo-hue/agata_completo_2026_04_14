# AGATA Simplified Deployment Guide (2026-02-28)

**Version**: 2.0 - Unified Script with skeema Schema Diffing
**Status**: Ready for Production
**Last Updated**: 2026-02-28

---

## ⚡ Quick Start (TL;DR)

You're on astrogen01 with clean git and you want to deploy to astrogen03?

```bash
# One-time setup (first deploy only)
./scripts/install_skeema.sh
./scripts/setup_ssh_deployment.sh --setup-ssh

# Then for EVERY deploy:
./scripts/deploy.sh                  # Interactive (shows preview, asks confirmation)
./scripts/deploy.sh --yes            # Automatic (auto-approves, no prompts)
./scripts/deploy.sh --dry-run        # Preview only (no changes applied)
./scripts/deploy.sh --yes --dry-run  # Safe preview
```

Done! ✅

---

## What `./scripts/deploy.sh` Does

A single command automates **10 steps**:

1. **Verify prerequisites** - Git clean, SSH working, skeema installed
2. **Generate schema diff** - Compare DB schemas (astrogen01 vs astrogen03) using skeema
3. **Show preview** - Display exactly what will change in the database
4. **Confirm changes** - Wait for user approval (skip with `--yes`)
5. **Backup production DB** - Automatic gzipped backup saved to `~/backups_agata/`
6. **Push code to GitHub** - Via `git push origin main`
7. **Pull code on production** - SSH: `git reset --hard origin/main`
8. **Update Python dependencies** - SSH: `pip install -r requirements.txt --upgrade`
9. **Apply schema changes** - SSH: Apply database DDL changes
10. **Restart services & health check** - SSH: Restart Flask/Nginx, verify endpoint responds

---

## Options

| Option | Effect | Example |
|--------|--------|---------|
| `--dry-run` | Show everything but apply nothing | `./scripts/deploy.sh --dry-run` |
| `--yes` | Skip confirmation prompts (auto-approve) | `./scripts/deploy.sh --yes` |
| `--skip-db` | Skip database schema changes | `./scripts/deploy.sh --skip-db` |
| `--skip-restart` | Don't restart Flask/Nginx services | `./scripts/deploy.sh --skip-restart` (testing) |
| `--help` | Show full help | `./scripts/deploy.sh --help` |

**Combining options**:
```bash
./scripts/deploy.sh --dry-run --yes          # Preview + auto-approve (show only)
./scripts/deploy.sh --yes --skip-db          # Deploy code only, skip DB changes
```

---

## Setup Instructions (One-Time)

### Step 1: Install skeema

On astrogen01:
```bash
cd /var/www/astrogen
./scripts/install_skeema.sh
skeema --version  # Verify installation
```

### Step 2: Configure SSH

Still on astrogen01:
```bash
./scripts/setup_ssh_deployment.sh --setup-ssh
```

This will:
1. Generate SSH key (if not exists)
2. Print commands to run on astrogen03
3. Ask you to execute those commands
4. Verify SSH works

### Step 3: Verify Everything

```bash
./scripts/setup_ssh_deployment.sh --test-ssh  # Quick SSH test
./scripts/deploy.sh --dry-run                 # Preview a potential deploy
```

---

## Workflow for Developers

### When You Modify the Database Schema

Example: You want to add a new column to `agata_projects`

```bash
# 1. Make change on astrogen01 development database
mysql -u aaaat01 -p catalogo
ALTER TABLE agata_projects ADD COLUMN new_column VARCHAR(100);

# 2. Update Python model if needed
vim agata/auth_models/project.py

# 3. Commit as normal
git add agata/auth_models/project.py
git commit -m "feat: add new_column to agata_projects"

# 4. Deploy (skeema detects the change automatically)
./scripts/deploy.sh
# → skeema will show: ALTER TABLE agata_projects ADD COLUMN new_column VARCHAR(100);
# → Review the preview
# → Press 'y' to confirm
# → Done!
```

**No migration files needed!** skeema compares the databases and generates the correct DDL.

---

## How Schema Diffing Works (skeema)

`skeema` is a tool that compares two MySQL/MariaDB databases and generates correct DDL statements.

**Example**:

You add index on astrogen01:
```sql
CREATE INDEX idx_state ON agata_projects(state);
```

When you run `./scripts/deploy.sh`:
```
skeema compares:
  ✅ localhost (astrogen01) has: CREATE INDEX idx_state ON agata_projects(state);
  ❌ 10.1.0.6 (astrogen03) doesn't have it

Generated DDL:
  CREATE INDEX idx_state ON agata_projects(state);

Preview shows the change to user → user approves → change is applied
```

Works for:
- ✅ ALTER TABLE (add/drop/modify columns)
- ✅ CREATE INDEX / DROP INDEX
- ✅ CREATE VIEW / ALTER VIEW
- ✅ CREATE FUNCTION / DROP FUNCTION
- ✅ All DDL operations

---

## Backup & Rollback

Every deploy creates an automatic backup:

```bash
# Backups stored in:
ls -lh ~/backups_agata/

# Example output:
# -rw-r--r-- 1 astrogen01 astrogen01 45M Feb 28 10:45 catalogo_20260228_104523.sql.gz

# To restore (if something goes wrong):
gunzip < ~/backups_agata/catalogo_20260228_104523.sql.gz | \
  mysql -u aaaat01 -p catalogo
```

---

## Troubleshooting

### Error: "skeema not found"
```bash
./scripts/install_skeema.sh
```

### Error: "SSH connection failed"
```bash
./scripts/setup_ssh_deployment.sh --setup-ssh
# Follow the instructions
```

### Error: "Working directory not clean"
```bash
git status
# Commit or stash your changes first
git add .
git commit -m "Work in progress"
```

### Error: "Not on branch main"
```bash
git checkout main
git pull origin main
```

### Services didn't restart after deploy
```bash
# SSH to astrogen03
ssh azureuser@10.1.0.6

# Check status
sudo systemctl status agata-flask
sudo systemctl status nginx

# Restart manually
sudo systemctl restart agata-flask
sudo systemctl restart nginx
```

### Health check failed
```bash
# Test Flask endpoint manually
ssh azureuser@10.1.0.6 "curl -v http://localhost:5000/agata/admin/"

# Check logs
ssh azureuser@10.1.0.6 "sudo journalctl -u agata-flask -n 50"
```

---

## Database Migration Tracking

A table `agata_schema_migrations` tracks all deployments:

```sql
SELECT * FROM agata_schema_migrations ORDER BY deployed_at DESC LIMIT 5;
```

Schema:
- `deploy_id` - Git commit hash
- `deployed_at` - When it was deployed
- `deployed_by` - Username that deployed
- `objects_changed` - List of DDL changes (JSON)
- `status` - success / failed

This gives you a complete audit trail of all DB changes.

---

## Configuration Files

### `.skeema` (Project Root)

Configures skeema to connect to production database:

```ini
[production]
host=10.1.0.6
port=3306
user=aaaat01
schema=catalogo
```

skeema reads this file to know where to compare against.

### `.env` (Credentials - Git-ignored)

Must contain:
```bash
DATABASE_URL=mysql+pymysql://aaaat01:PASSWORD@localhost:3306/catalogo
```

The deploy script extracts the password securely (never hardcoded in shell scripts).

---

## Security Notes

✅ **What's Safe**:
- Credentials read from `.env` at runtime (never in script)
- Automatic backups before every change
- Preview shows exactly what will change before confirmation
- SSH key-based authentication (no password in commands)
- Health checks verify service is running

❌ **What Changed from Old Script**:
- ✅ Removed hardcoded DB password (`-pdwedfAA1saa14` removed!)
- ✅ Removed manual steps (now fully automated)
- ✅ Added schema diffing (safer than full dump)
- ✅ Added migration tracking table

---

## Old Scripts (Deprecated)

The old deployment scripts are still present but deprecated:

- `scripts/deploy_to_production.sh` - Old method (full schema dump)
- `scripts/setup_ssh_deployment.sh` - Partially integrated into new script

New deployments should use: **`./scripts/deploy.sh`**

---

## Examples

### Example 1: Safe Preview Before Deploying

```bash
# See what would happen without applying changes
./scripts/deploy.sh --dry-run
# Output shows schema diff preview
# No confirmation needed (dry-run)
# No changes applied
```

### Example 2: Automated Deployment (CI/CD ready)

```bash
# Deploy automatically without prompts
./scripts/deploy.sh --yes
# ✅ Shows preview
# ✅ Auto-approves
# ✅ Applies all changes
# ✅ Health checks
# ✅ Reports result
```

### Example 3: Deploy Code Only (Database Frozen)

```bash
# Update code and dependencies, skip DB changes
./scripts/deploy.sh --yes --skip-db
# ✅ Pulls code
# ✅ Updates pip packages
# ✅ Restarts services
# ❌ Skips database schema changes
```

---

## Questions?

See the main deployment guide: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

Or check individual component docs:
- SSH setup: [scripts/setup_ssh_deployment.sh](../scripts/setup_ssh_deployment.sh)
- Skeema installation: [scripts/install_skeema.sh](../scripts/install_skeema.sh)
- Main deploy script: [scripts/deploy.sh](../scripts/deploy.sh)
- Skeema docs: https://www.skeema.io/docs/

---

**Last tested**: 2026-02-28
**Script version**: 2.0
**AGATA version**: v1.23.5+
