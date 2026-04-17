#!/bin/bash
# ============================================================================
# Deploy SQL migrations to production via SSH
# ============================================================================
# Applies SQL migration files to production database (astrogen03)
# Reads database credentials from .env DATABASE_URL
#
# USAGE:
#   ./scripts/migrate-prod.sh <migration_file_or_glob>
#
# EXAMPLES:
#   ./scripts/migrate-prod.sh docs/migrations/013_drop_tess_curl_entries.sql
#   ./scripts/migrate-prod.sh docs/migrations/013_*.sql
#   ./scripts/migrate-prod.sh docs/migrations/01[23]_*.sql
# ============================================================================

set -e

# ============================================================================
# Configuration
# ============================================================================

PROD_SERVER="10.1.0.6"
PROD_USER="azureuser"
PROD_PATH="/var/www/astrogen"

DB_USER="aaaat01"
DB_NAME="catalogo"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ============================================================================
# Functions
# ============================================================================

log_info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_section() { echo -e "\n${BLUE}$1${NC}\n"; }

# Extract password from DATABASE_URL in remote .env via SSH
# Reads MYSQL_DATABASE_URL or DATABASE_URL from production .env
get_db_password_remote() {
    ssh "$PROD_USER@$PROD_SERVER" python3 << 'PYTHON_EOF'
import os, urllib.parse

env_file = '/var/www/astrogen/.env'
if not os.path.exists(env_file):
    print("")
    exit(0)

with open(env_file, 'r') as f:
    lines = f.readlines()

# Prefer MYSQL_DATABASE_URL, fallback to DATABASE_URL
for url_key in ['MYSQL_DATABASE_URL', 'DATABASE_URL']:
    for line in lines:
        if line.startswith(url_key + '='):
            url = line.split('=', 1)[1].strip()
            parsed = urllib.parse.urlparse(url)
            password = parsed.password or ''
            print(password)
            exit(0)

print("")
PYTHON_EOF
}

# ============================================================================
# Main
# ============================================================================

# Validate arguments
if [ $# -eq 0 ]; then
    echo "Usage: $0 <migration_file_or_glob>"
    echo "Examples:"
    echo "  $0 docs/migrations/013_drop_tess_curl_entries.sql"
    echo "  $0 docs/migrations/013_*.sql"
    exit 1
fi

log_section "🚀 AGATA SQL Migration Deployer"

log_info "Reading database credentials from production .env..."
DB_PASSWORD=$(get_db_password_remote)

if [ -z "$DB_PASSWORD" ]; then
    log_error "Could not extract password from DATABASE_URL"
    exit 1
fi

log_info "Target: $PROD_USER@$PROD_SERVER"
log_info "Database: $DB_NAME"

# Get migration files (handle glob patterns)
MIGRATION_PATTERN="$1"
MIGRATIONS=$(ls $MIGRATION_PATTERN 2>/dev/null | sort) || true

if [ -z "$MIGRATIONS" ]; then
    log_error "No migration files found matching: $MIGRATION_PATTERN"
    exit 1
fi

echo ""
log_info "Migrations to apply:"
echo "$MIGRATIONS" | sed 's/^/  /'
echo ""

read -p "Proceed with migration? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Cancelled"
    exit 0
fi

# Apply each migration
FAILED=0
APPLIED=0

for MIGRATION_FILE in $MIGRATIONS; do
    if [ ! -f "$MIGRATION_FILE" ]; then
        log_error "File not found: $MIGRATION_FILE"
        FAILED=$((FAILED + 1))
        continue
    fi

    FILENAME=$(basename "$MIGRATION_FILE")
    log_section "Applying: $FILENAME"

    # Read migration content
    MIGRATION_SQL=$(cat "$MIGRATION_FILE")

    # Execute via SSH with password from stdin
    if ssh "$PROD_USER@$PROD_SERVER" << EOSSH
cd "$PROD_PATH"
mysql -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" << 'EOSQL'
$MIGRATION_SQL
EOSQL
EOSSH
    then
        log_success "$FILENAME applied successfully"
        APPLIED=$((APPLIED + 1))
    else
        log_error "Failed to apply $FILENAME"
        FAILED=$((FAILED + 1))
    fi
done

echo ""
log_section "Migration Summary"
log_info "Applied: $APPLIED"
log_info "Failed: $FAILED"

if [ $FAILED -gt 0 ]; then
    log_error "Some migrations failed!"
    exit 1
else
    log_success "All migrations applied!"
    exit 0
fi
