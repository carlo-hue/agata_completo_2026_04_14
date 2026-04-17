#!/bin/bash
# ============================================================================
# AGATA Production Deployment Script
# ============================================================================
# Migra codice da sviluppo (astrogen01) a produzione (astrogen03)
# via GitHub come ponte (no SSH richiesto)
#
# PREREQUISITI:
# - Git configurato su astrogen03 con accesso a https://github.com/giorgio-astrogen/astrogen
# - Database MySQL attivo su astrogen03
# - Credenziali DB in /var/www/astrogen/.env
#
# USO:
#   ./deploy_to_production.sh [--dry-run] [--skip-db]
#
# ============================================================================

set -e  # Exit on error
set -u  # Exit on undefined variable

# ----------------------------------------------------------------------------
# Configurazione
# ----------------------------------------------------------------------------
PROD_SERVER="10.1.0.6"
PROD_USER="astrogen01"
PROD_PATH="/var/www/astrogen"
PROD_REPO="https://github.com/giorgio-astrogen/astrogen"
PROD_BRANCH="main"

DEV_REPO="git@github.com:giorgio-astrogen/flask.git"
DEV_BRANCH="main"

DB_NAME="catalogo"
DB_USER="aaaat01"
DB_SCHEMA_FILE="/tmp/agata_schema_latest.sql"

# Colori output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Flags
DRY_RUN=false
SKIP_DB=false

# ----------------------------------------------------------------------------
# Parse Arguments
# ----------------------------------------------------------------------------
for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            ;;
        --skip-db)
            SKIP_DB=true
            ;;
        *)
            echo "Unknown argument: $arg"
            echo "Usage: $0 [--dry-run] [--skip-db]"
            exit 1
            ;;
    esac
done

# ----------------------------------------------------------------------------
# Functions
# ----------------------------------------------------------------------------
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_git_clean() {
    if [[ -n $(git status --porcelain) ]]; then
        log_error "Working directory non pulito. Commit o stash prima di deployare."
        git status --short
        exit 1
    fi
}

export_db_schema() {
    log_info "Esporto schema database (NO dati)..."

    # Leggi password da .env
    DB_PASSWORD=$(grep DATABASE_URL .env | cut -d':' -f3 | cut -d'@' -f1)

    mysqldump -u "$DB_USER" -p"$DB_PASSWORD" --no-data --skip-triggers \
        --skip-add-drop-table \
        "$DB_NAME" > "$DB_SCHEMA_FILE" 2>/dev/null

    # Modifica per CREATE TABLE IF NOT EXISTS
    sed -i 's/CREATE TABLE `/CREATE TABLE IF NOT EXISTS `/g' "$DB_SCHEMA_FILE"

    log_info "Schema esportato: $DB_SCHEMA_FILE ($(wc -l < "$DB_SCHEMA_FILE") righe)"
}

push_to_dev_repo() {
    log_info "Push su repository sviluppo: $DEV_REPO"
    git push origin "$DEV_BRANCH" --tags
    log_info "✅ Push completato"
}

# ----------------------------------------------------------------------------
# STEP 1: Verifica Prerequisiti
# ----------------------------------------------------------------------------
log_info "============================================================"
log_info "AGATA Production Deployment Script"
log_info "============================================================"
log_info "Sviluppo: astrogen01 → Produzione: astrogen03 ($PROD_SERVER)"
log_info ""

if [[ "$DRY_RUN" == true ]]; then
    log_warn "🔍 DRY RUN MODE - nessuna modifica sarà applicata"
fi

# Verifica di essere su astrogen01
CURRENT_HOST=$(hostname)
if [[ "$CURRENT_HOST" != "AstroGen01" ]]; then
    log_error "Questo script deve essere eseguito su astrogen01 (hostname: $CURRENT_HOST)"
    exit 1
fi

# Verifica Git clean
log_info "Verifico working directory Git..."
check_git_clean
log_info "✅ Working directory pulito"

# Verifica branch main
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [[ "$CURRENT_BRANCH" != "$DEV_BRANCH" ]]; then
    log_error "Devi essere sul branch $DEV_BRANCH (attuale: $CURRENT_BRANCH)"
    exit 1
fi

# ----------------------------------------------------------------------------
# STEP 2: Esporta Schema Database
# ----------------------------------------------------------------------------
if [[ "$SKIP_DB" == false ]]; then
    export_db_schema
else
    log_warn "⏭️  Skip database schema export (--skip-db)"
fi

# ----------------------------------------------------------------------------
# STEP 3: Push su Repository Sviluppo
# ----------------------------------------------------------------------------
log_info "Ultimo commit locale:"
git log -1 --oneline

if [[ "$DRY_RUN" == false ]]; then
    push_to_dev_repo
else
    log_warn "⏭️  Skipping push (dry-run)"
fi

# ----------------------------------------------------------------------------
# STEP 4: Istruzioni Manuali per astrogen03
# ----------------------------------------------------------------------------
log_info ""
log_info "============================================================"
log_info "📋 ISTRUZIONI PER ASTROGEN03"
log_info "============================================================"
log_info ""
log_info "Esegui i seguenti comandi su astrogen03 ($PROD_SERVER):"
log_info ""

cat <<'EOF'
# ----------------------------------------------------------------------------
# 1. BACKUP CODICE ATTUALE (opzionale ma raccomandato)
# ----------------------------------------------------------------------------
cd /var/www/astrogen
git branch backup-$(date +%Y%m%d-%H%M%S)
git push origin backup-$(date +%Y%m%d-%H%M%S)

# ----------------------------------------------------------------------------
# 2. PULL NUOVO CODICE DA REPOSITORY PRODUZIONE
# ----------------------------------------------------------------------------
# Verifica remote configurato
git remote -v
# Dovrebbe mostrare: origin  https://github.com/giorgio-astrogen/astrogen

# Pull ultimi cambiamenti
git fetch origin
git checkout main
git reset --hard origin/main

# Verifica versione deployata
git log -1 --oneline
git tag

# ----------------------------------------------------------------------------
# 3. AGGIORNA DIPENDENZE PYTHON
# ----------------------------------------------------------------------------
source venv/bin/activate  # o path al tuo virtualenv
pip install -r requirements.txt --upgrade

# ----------------------------------------------------------------------------
# 4. BACKUP DATABASE (CRITICO!)
# ----------------------------------------------------------------------------
mysqldump -u aaaat01 -p catalogo > ~/backup_catalogo_$(date +%Y%m%d_%H%M%S).sql
# Verifica backup creato
ls -lh ~/backup_catalogo_*.sql

# ----------------------------------------------------------------------------
# 5. APPLICA MIGRAZIONI DATABASE SCHEMA
# ----------------------------------------------------------------------------
# OPZIONE A: Copia schema file manualmente da astrogen01
# scp astrogen01:/tmp/agata_schema_latest.sql /tmp/

# OPZIONE B: Rigeneralo localmente (se hai accesso al DB)
mysqldump -u aaaat01 -p --no-data catalogo > /tmp/agata_schema_current.sql

# Applica schema (crea nuove tabelle/colonne se mancanti)
mysql -u aaaat01 -p catalogo < /tmp/agata_schema_latest.sql

# ----------------------------------------------------------------------------
# 6. VERIFICA INTEGRITÀ DATABASE
# ----------------------------------------------------------------------------
mysql -u aaaat01 -p catalogo -e "SHOW TABLES LIKE 'agata_%';"
mysql -u aaaat01 -p catalogo -e "SELECT COUNT(*) FROM agata_projects;"
mysql -u aaaat01 -p catalogo -e "SELECT COUNT(*) FROM agata_vast_jobs;"

# ----------------------------------------------------------------------------
# 7. AGGIORNA CONFIGURAZIONI (se necessario)
# ----------------------------------------------------------------------------
# Verifica .env per API keys, database credentials
vim /var/www/astrogen/.env

# Esempio variabili critiche:
# DATABASE_URL=mysql+pymysql://aaaat01:PASSWORD@localhost:3306/catalogo
# ANTHROPIC_API_KEY=sk-...
# FLASK_SECRET_KEY=...
# SLACK_BOT_TOKEN=xoxb-...

# ----------------------------------------------------------------------------
# 8. RESTART SERVIZI
# ----------------------------------------------------------------------------
# Flask (se usa systemd service)
sudo systemctl restart agata.service
sudo systemctl status agata.service

# OPPURE (se usa gunicorn standalone)
pkill -f gunicorn
cd /var/www/astrogen
source venv/bin/activate
gunicorn -w 4 -b 0.0.0.0:5000 app:app --daemon

# Nginx
sudo systemctl restart nginx
sudo systemctl status nginx

# ----------------------------------------------------------------------------
# 9. VERIFICA DEPLOYMENT
# ----------------------------------------------------------------------------
# Test endpoint
curl http://localhost:5000/agata/admin/

# Verifica logs
tail -f /var/log/nginx/error.log
tail -f /var/www/astrogen/logs/agata.log  # se esiste

# Test login
# Apri browser: http://10.1.0.6/agata/admin/

EOF

log_info ""
log_info "============================================================"
log_info "✅ DEPLOYMENT SCRIPT COMPLETATO"
log_info "============================================================"
log_info ""
log_info "📁 File generati:"
if [[ "$SKIP_DB" == false ]]; then
    log_info "  - Schema DB: $DB_SCHEMA_FILE"
fi
log_info ""
log_info "📌 Prossimi passi:"
log_info "  1. Trasferisci schema DB su astrogen03 (scp o manualmente)"
log_info "  2. Esegui istruzioni sopra su astrogen03"
log_info "  3. Verifica deployment: http://10.1.0.6/agata/admin/"
log_info ""
