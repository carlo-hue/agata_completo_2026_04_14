#!/bin/bash
# ============================================================================
# AGATA Deployment Script - astrogen01 → astrogen03
# ============================================================================
# Deploys code from development (astrogen01) to production (astrogen03)
# via GitHub. SQL migrations applied manually via --db-migrate.
#
# USAGE:
#   ./scripts/deploy.sh [OPTIONS]
#
# OPTIONS:
#   --tag <ref>            Deploy a specific git tag or commit (default: main HEAD)
#   --dry-run              Show what would happen without applying changes
#   --yes                  Skip interactive confirmation prompts
#   --db-migrate           Apply pending SQL migrations from docs/migrations/
#   --skip-restart         Skip Apache restart (for testing)
#   --help                 Show this help
#
# EXAMPLES:
#   ./scripts/deploy.sh --yes                      # Deploy main HEAD
#   ./scripts/deploy.sh --yes --tag v2.14.1        # Deploy specific tag
#   ./scripts/deploy.sh --yes --db-migrate         # Deploy + apply SQL migrations
#   ./scripts/deploy.sh --dry-run                  # Preview only
# ============================================================================

set -e
set -u
set -o pipefail

# ============================================================================
# CONFIGURATION
# ============================================================================

PROD_SERVER="10.1.0.6"
PROD_USER="azureuser"
PROD_PATH="/var/www/astrogen"
PROD_BRANCH="main"

DB_NAME="catalogo"
DB_USER="aaaat01"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$HOME/backups_agata"

# Flags
DRY_RUN=false
SKIP_CONFIRM=false
DB_MIGRATE=false
SKIP_RESTART=false
DEPLOY_REF="dev/main"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ============================================================================
# FUNCTIONS
# ============================================================================

log_info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }

log_section() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}\n"
}

# Estrae password dalla stringa DATABASE_URL nel .env
# Formato: mysql+pymysql://user:password@host:port/db
get_db_password() {
    local url
    url=$(grep "^DATABASE_URL=" .env | cut -d'=' -f2-)
    python3 << PYTHON_EOF
import urllib.parse, sys
try:
    parsed = urllib.parse.urlparse("$url")
    if parsed.password:
        print(urllib.parse.unquote(parsed.password))
    else:
        sys.exit(1)
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
PYTHON_EOF
}

confirm() {
    local prompt="$1"
    if [[ "$SKIP_CONFIRM" == true ]]; then
        log_info "$prompt ... auto-confirmed (--yes)"
        return 0
    fi
    echo -n -e "${YELLOW}$prompt (y/n)?${NC} "
    read -r response
    [[ "$response" == "y" || "$response" == "Y" ]]
}

check_ssh() {
    log_info "Testing SSH connection to $PROD_USER@$PROD_SERVER..."
    if ssh -o ConnectTimeout=5 -o BatchMode=yes "$PROD_USER@$PROD_SERVER" "true" 2>/dev/null; then
        log_success "SSH connection OK"
    else
        log_error "SSH connection failed!"
        return 1
    fi
}

check_git_clean() {
    if [[ -n $(git status --porcelain) ]]; then
        log_error "Working directory not clean!"
        git status --short
        log_error "Commit or stash changes before deploying"
        return 1
    fi
    log_success "Git working directory clean"
}

get_commit_hash()      { git rev-parse --short HEAD; }
get_commit_hash_long() { git rev-parse HEAD; }

# ============================================================================
# PARSE ARGUMENTS
# ============================================================================

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tag)         DEPLOY_REF="$2"; shift ;;
        --dry-run)     DRY_RUN=true ;;
        --yes)         SKIP_CONFIRM=true ;;
        --db-migrate)  DB_MIGRATE=true ;;
        --skip-restart) SKIP_RESTART=true ;;
        --help)
            sed -n '3,20p' "$0"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
    shift
done

# ============================================================================
# STEP 0: STARTUP
# ============================================================================

log_section "🚀 AGATA Deployment Script"
log_info "Source: astrogen01 (localhost)"
log_info "Target: astrogen03 ($PROD_SERVER)"
log_info ""

[[ "$DRY_RUN" == true ]]     && log_warn "🔍 DRY RUN MODE - No changes will be applied"
[[ "$SKIP_CONFIRM" == true ]] && log_warn "⚡ Auto-confirm mode enabled (--yes)"

# ============================================================================
# STEP 1: VERIFY PREREQUISITES
# ============================================================================

log_section "Step 1/8: Verifying Prerequisites"

[[ ! -f .env ]] && { log_error ".env not found!"; exit 1; }
log_success ".env found"

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
[[ "$CURRENT_BRANCH" != "$PROD_BRANCH" ]] && { log_error "Not on branch $PROD_BRANCH (current: $CURRENT_BRANCH)"; exit 1; }
log_success "On branch $PROD_BRANCH"

check_git_clean || exit 1
check_ssh       || exit 1

log_success "All prerequisites verified"

# ============================================================================
# STEP 2: GET CREDENTIALS
# ============================================================================

log_info "Reading database credentials from .env..."
if ! DB_PASS=$(get_db_password); then
    log_error "Failed to extract DB password from DATABASE_URL"
    exit 1
fi
log_success "Credentials loaded"

# ============================================================================
# STEP 3: CONFIRM DEPLOY
# ============================================================================

log_section "Step 2/8: Confirm Deploy"

COMMIT_SHORT=$(get_commit_hash)
COMMIT_MSG=$(git log -1 --format='%s')
log_info "Deploy ref:    $DEPLOY_REF"
log_info "Local commit:  $COMMIT_SHORT - $COMMIT_MSG"
[[ "$DB_MIGRATE" == true ]] && log_info "DB migrations: ENABLED (--db-migrate)"

confirm "Proceed with deployment?" || { log_warn "Deployment cancelled"; exit 0; }

# ============================================================================
# STEP 4: BACKUP PRODUCTION DATABASE
# ============================================================================

if [[ "$DRY_RUN" == false ]]; then
    log_section "Step 3/8: Backing Up Production Database"

    mkdir -p "$BACKUP_DIR"
    BACKUP_FILE="$BACKUP_DIR/catalogo_${TIMESTAMP}.sql.gz"

    log_info "Backing up to $BACKUP_FILE..."
    if ! ssh "$PROD_USER@$PROD_SERVER" "mysqldump -u $DB_USER -p\"$DB_PASS\" --single-transaction $DB_NAME | gzip" > "$BACKUP_FILE" 2>/dev/null; then
        log_error "Backup failed!"
        exit 1
    fi

    BACKUP_SIZE=$(du -sh "$BACKUP_FILE" | awk '{print $1}')
    log_success "Backup created: $BACKUP_FILE ($BACKUP_SIZE)"
else
    log_section "Step 3/8: Skipping Backup (--dry-run)"
fi

# ============================================================================
# STEP 5: PUSH CODE TO GITHUB
# ============================================================================

if [[ "$DRY_RUN" == false ]]; then
    log_section "Step 4/8: Pushing Code to GitHub"

    log_info "Pushing to origin/$PROD_BRANCH..."
    git push origin "$PROD_BRANCH" --quiet 2>/dev/null || { log_error "Git push failed!"; exit 1; }
    log_success "Code pushed to GitHub"
else
    log_section "Step 4/8: Skipping Git Push (--dry-run)"
fi

# ============================================================================
# STEP 6: PULL CODE ON PRODUCTION
# ============================================================================

if [[ "$DRY_RUN" == false ]]; then
    log_section "Step 5/8: Pulling Code on Production"

    log_info "SSH: Updating code on astrogen03 to: $DEPLOY_REF..."
    ssh "$PROD_USER@$PROD_SERVER" bash << SSH_PULL
        set -e
        cd $PROD_PATH
        git fetch dev --tags --force --quiet
        git reset --hard $DEPLOY_REF || { echo "RESET FAILED: $DEPLOY_REF not found"; exit 1; }
        echo "Commit: \$(git log -1 --oneline)"
SSH_PULL

    log_success "Code pulled on production"
else
    log_section "Step 5/8: Skipping Code Pull (--dry-run)"
fi

# ============================================================================
# STEP 7: APPLY SQL MIGRATIONS (optional, --db-migrate)
# ============================================================================

if [[ "$DB_MIGRATE" == true && "$DRY_RUN" == false ]]; then
    log_section "Step 6/8: Applying SQL Migrations"

    MIGRATION_DIR="$PROD_PATH/docs/migrations"
    log_info "SSH: Applying SQL files from $MIGRATION_DIR..."

    ssh "$PROD_USER@$PROD_SERVER" bash << SSH_MIGRATE
        set -e
        cd $PROD_PATH
        for sql_file in \$(ls docs/migrations/*.sql 2>/dev/null | sort); do
            echo "  → Applying: \$sql_file"
            mysql -u $DB_USER -p"$DB_PASS" $DB_NAME < "\$sql_file"
        done
        echo "Migrations applied"
SSH_MIGRATE

    log_success "SQL migrations applied"
elif [[ "$DB_MIGRATE" == true && "$DRY_RUN" == true ]]; then
    log_section "Step 6/8: Skipping Migrations (--dry-run)"
    log_info "Would apply: $(ls docs/migrations/*.sql 2>/dev/null | sort | xargs -I{} basename {} | tr '\n' ' ')"
else
    log_section "Step 6/8: Skipping Migrations (use --db-migrate to apply)"
fi

# ============================================================================
# STEP 8: UPDATE PYTHON DEPENDENCIES
# ============================================================================

if [[ "$DRY_RUN" == false ]]; then
    log_section "Step 7/8: Updating Python Dependencies"

    log_info "SSH: Installing Python packages..."
    ssh "$PROD_USER@$PROD_SERVER" bash << 'SSH_PIP'
        set -e
        cd /var/www/astrogen
        source venv/bin/activate 2>/dev/null || source flask/bin/activate 2>/dev/null || {
            echo "ERROR: virtualenv not found"
            exit 1
        }
        pip install -r requirements.txt --upgrade --quiet
        echo "Done: $(pip --version)"
SSH_PIP

    log_success "Dependencies updated"
else
    log_section "Step 7/8: Skipping Dependency Update (--dry-run)"
fi

# ============================================================================
# STEP 9: RESTART SERVICES
# ============================================================================

if [[ "$SKIP_RESTART" == false && "$DRY_RUN" == false ]]; then
    log_section "Step 8/8: Restarting Services"

    log_info "SSH: Restarting Apache2..."
    ssh "$PROD_USER@$PROD_SERVER" bash << 'SSH_RESTART'
        set -e
        sudo systemctl restart apache2
        sleep 2
        echo "Apache2 restarted"
SSH_RESTART

    log_success "Services restarted"

    log_info "Testing Flask endpoint..."
    if ssh "$PROD_USER@$PROD_SERVER" "curl -sf http://localhost/agata/admin/ > /dev/null" 2>/dev/null; then
        log_success "Health check passed"
    else
        log_warn "Health check failed - verify manually: curl http://$PROD_SERVER/agata/admin/"
    fi
else
    log_section "Step 8/8: Skipping Restart"
    [[ "$DRY_RUN" == true ]] && log_info "(--dry-run mode)" || log_info "(--skip-restart mode)"
fi

# ============================================================================
# FINAL REPORT
# ============================================================================

log_section "✅ Deployment Summary"

log_info "Status:  SUCCESS ✅"
log_info "Commit:  $(get_commit_hash_long)"
log_info "Message: $(git log -1 --format='%s')"
log_info "Target:  $PROD_USER@$PROD_SERVER"
log_info "Time:    $TIMESTAMP"

if [[ "$DRY_RUN" == true ]]; then
    log_info ""
    log_info "This was a DRY RUN - no changes were applied"
fi

if [[ "$DRY_RUN" == false && -f "${BACKUP_FILE:-}" ]]; then
    log_info ""
    log_info "🔄 Backup (rollback):"
    log_info "  Location: $BACKUP_FILE"
    log_info "  Restore:  gunzip < $BACKUP_FILE | mysql -u $DB_USER -p $DB_NAME"
fi

log_info ""
log_success "All done! 🎉"
