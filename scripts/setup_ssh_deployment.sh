#!/bin/bash
# ============================================================================
# SSH Setup + Deployment Automation
# ============================================================================
# Configura SSH tra astrogen01 e astrogen03, poi automatizza deployment
#
# USO:
#   ./setup_ssh_deployment.sh --setup-ssh
#   ./setup_ssh_deployment.sh --test-ssh
#   ./setup_ssh_deployment.sh --deploy-with-ssh
#
# ============================================================================

set -e
set -u

# Configurazione
PROD_SERVER="10.1.0.6"
PROD_USER="azureuser"
PROD_PATH="/var/www/astrogen"
DB_SCHEMA_FILE="/tmp/agata_schema_latest.sql"

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Funzioni
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_section() { echo -e "\n${BLUE}═══════════════════════════════════════════════════════${NC}"; echo -e "${BLUE}$1${NC}"; echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}\n"; }

# Parse argomenti
if [[ $# -eq 0 ]]; then
    echo "USO: $0 [--setup-ssh|--test-ssh|--deploy-with-ssh|--help]"
    exit 0
fi

COMMAND=$1

case "$COMMAND" in
    --setup-ssh)
        log_section "🔐 SETUP SSH astrogen01 → astrogen03"

        log_info "Verifico SSH key locale..."
        if [[ ! -f ~/.ssh/id_ed25519 ]]; then
            log_error "Chiave SSH non trovata in ~/.ssh/id_ed25519"
            log_info "Genero nuova chiave..."
            ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N "" -C "$(whoami)@astrogen01"
        fi

        PUB_KEY=$(cat ~/.ssh/id_ed25519.pub)
        log_info "Chiave pubblica: $PUB_KEY"

        log_warn ""
        log_warn "⚠️  AZIONE MANUALE RICHIESTA su astrogen03!"
        log_warn ""
        log_warn "Esegui questi comandi su astrogen03 (10.1.0.6):"
        log_warn ""
        cat << 'EOF'
mkdir -p ~/.ssh && chmod 700 ~/.ssh
cat >> ~/.ssh/authorized_keys << 'KEYADD'
EOF
        echo "$PUB_KEY"
        cat << 'EOF'
KEYADD
chmod 600 ~/.ssh/authorized_keys
sudo systemctl status ssh || sudo systemctl start ssh
EOF

        log_info ""
        log_info "Dopo aver eseguito i comandi sopra su astrogen03, premi Invio per verificare..."
        read -r

        # Test SSH
        if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new "$PROD_USER@$PROD_SERVER" "echo 'SSH test OK'" 2>/dev/null; then
            log_info "✅ SSH Funzionante!"
        else
            log_error "SSH non funzionante. Verifica comandi sopra."
            exit 1
        fi

        log_section "✅ SSH Setup Completo"
        log_info "Puoi ora usare: $0 --deploy-with-ssh"
        ;;

    --test-ssh)
        log_section "🔍 Test SSH Connection"

        if ssh -o ConnectTimeout=5 "$PROD_USER@$PROD_SERVER" "echo 'Connected!' && hostname && pwd" 2>/dev/null; then
            log_info "✅ SSH Funzionante!"
        else
            log_error "SSH non funzionante."
            log_info "Esegui prima: $0 --setup-ssh"
            exit 1
        fi
        ;;

    --deploy-with-ssh)
        log_section "🚀 Deployment con SSH Automatico"

        # Verifica SSH
        log_info "Verifico SSH connection..."
        if ! ssh -o ConnectTimeout=5 "$PROD_USER@$PROD_SERVER" "true" 2>/dev/null; then
            log_error "SSH non funzionante!"
            log_info "Esegui prima: $0 --setup-ssh"
            exit 1
        fi
        log_info "✅ SSH OK"

        # Verifica schema DB
        log_info "Verifico schema database..."
        if [[ ! -f "$DB_SCHEMA_FILE" ]]; then
            log_error "Schema database non trovato in $DB_SCHEMA_FILE"
            log_info "Esegui prima: ./deploy_to_production.sh"
            exit 1
        fi
        log_info "✅ Schema trovato ($(wc -l < "$DB_SCHEMA_FILE") righe)"

        # Backup su astrogen03
        log_info "Faccio backup database su astrogen03..."
        BACKUP_FILE="backup_catalogo_$(date +%Y%m%d_%H%M%S).sql"
        ssh "$PROD_USER@$PROD_SERVER" "mysqldump -u aaaat01 -pdwedfAA1saa14 catalogo > ~/$BACKUP_FILE" 2>/dev/null || log_warn "Backup potrebbe aver fallito"
        log_info "✅ Backup: ~/$BACKUP_FILE"

        # Copia schema DB via SCP
        log_info "Trasferisco schema database via SCP..."
        scp -q "$DB_SCHEMA_FILE" "$PROD_USER@$PROD_SERVER:/tmp/" 2>/dev/null || {
            log_error "SCP fallito!"
            exit 1
        }
        log_info "✅ Schema trasferito"

        # Backup codice
        log_info "Faccio backup codice su astrogen03..."
        ssh "$PROD_USER@$PROD_SERVER" "cd $PROD_PATH && git branch backup-$(date +%Y%m%d-%H%M%S)" 2>/dev/null || log_warn "Backup branch potrebbe non funzionare"

        # Pull codice
        log_info "Effettuo pull nuovo codice..."
        ssh "$PROD_USER@$PROD_SERVER" "cd $PROD_PATH && git fetch origin && git checkout main && git reset --hard origin/main" 2>/dev/null || {
            log_error "Git pull fallito!"
            exit 1
        }
        log_info "✅ Codice aggiornato"

        # Applica schema DB
        log_info "Applico migrazioni database..."
        ssh "$PROD_USER@$PROD_SERVER" "mysql -u aaaat01 -pdwedfAA1saa14 catalogo < /tmp/agata_schema_latest.sql" 2>/dev/null || {
            log_error "Migrazioni database fallite!"
            exit 1
        }
        log_info "✅ Schema applicato"

        # Verifica
        log_info "Verifico deployment..."
        TABLES=$(ssh "$PROD_USER@$PROD_SERVER" "mysql -u aaaat01 -pdwedfAA1saa14 catalogo -e \"SHOW TABLES LIKE 'agata_%';\" | wc -l" 2>/dev/null)
        log_info "Tabelle AGATA trovate: $TABLES"

        log_section "✅ Deployment Completato!"
        log_info "Prossimi step su astrogen03:"
        log_info "  1. pip install -r requirements.txt --upgrade"
        log_info "  2. sudo systemctl restart agata.service"
        log_info "  3. sudo systemctl restart nginx"
        log_info ""
        log_info "Esegui: ssh $PROD_USER@$PROD_SERVER"
        ;;

    --help)
        cat << 'EOF'
SSH Setup & Deployment Script

COMANDI:
  --setup-ssh         Configura SSH tra astrogen01 e astrogen03
  --test-ssh          Test SSH connection
  --deploy-with-ssh   Esegui deployment completo con SSH
  --help              Mostra questo aiuto

ESEMPIO:
  ./setup_ssh_deployment.sh --setup-ssh
  ./setup_ssh_deployment.sh --test-ssh
  ./setup_ssh_deployment.sh --deploy-with-ssh

EOF
        ;;

    *)
        log_error "Comando sconosciuto: $COMMAND"
        echo "USO: $0 [--setup-ssh|--test-ssh|--deploy-with-ssh|--help]"
        exit 1
        ;;
esac
