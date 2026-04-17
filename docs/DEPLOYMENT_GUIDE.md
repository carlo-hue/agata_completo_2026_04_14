# AGATA Deployment Guide - astrogen01 (Dev) → astrogen03 (Prod)

**Last Updated**: 2026-02-16
**Version**: v1.19.0-production
**Status**: Production Ready

---

## Overview

Questa guida descrive il processo completo di deployment del codice AGATA da:
- **Server di sviluppo**: astrogen01 (IP interno, GitHub: `giorgio-astrogen/flask`)
- **Server di produzione**: astrogen03 (IP: 10.1.0.6, GitHub: `giorgio-astrogen/astrogen`)

**Strategia**: Git-based deployment via GitHub come ponte (NO SSH diretto richiesto).

---

## Prerequisiti

### Su astrogen01 (Sviluppo)
- [x] Git configurato con accesso SSH a `git@github.com:giorgio-astrogen/flask.git`
- [x] Database MySQL `catalogo` accessibile (user: `aaaat01`)
- [x] File `.env` con credenziali corrette
- [x] Script `deploy_to_production.sh` eseguibile

### Su astrogen03 (Produzione)
- [ ] Git configurato con accesso HTTPS a `https://github.com/giorgio-astrogen/astrogen`
- [ ] Database MySQL `catalogo` accessibile (user: `aaaat01`)
- [ ] Python virtualenv attivo
- [ ] Nginx + Flask service configurati
- [ ] File `.env` con credenziali di produzione

---

## Configurazione Slack per Ambienti Duali (astrogen01 Dev + astrogen03 Prod)

Se astrogen01 (dev) e astrogen03 (prod) condividono lo stesso workspace Slack (non c'è Slack dev/staging):

**PROBLEMA**: Entrambi i server usano lo stesso `SLACK_BOT_TOKEN`, causando notifiche duplicate quando gli utenti:
- Creano progetti su uno dei due server
- Assegnano progetti
- Esportano analisi su Slack

**SOLUZIONE**: Disabilitare l'integrazione Slack su astrogen01 impostando una variabile d'ambiente.

### Configurazione su astrogen01 (Development)

**File**: `/var/www/astrogen/.env`

```bash
# ============================================================================
# Slack Integration Control (ENVIRONMENT-SPECIFIC)
# ============================================================================
# Set to 'false' to disable Slack integration entirely (dev environments)
SLACK_INTEGRATION_ENABLED=false

# Slack OAuth (configurato ma non usato se SLACK_INTEGRATION_ENABLED=false)
SLACK_CLIENT_ID=...
SLACK_CLIENT_SECRET=...
SLACK_BOT_TOKEN=...
```

**Effetto**:
- ✅ Progetti creati su astrogen01 NON generano messaggi Slack
- ✅ Assegnazioni su astrogen01 NON generano notifiche Slack
- ❌ Click "Send to Slack" su astrogen01 restituisce HTTP 500 con messaggio: "Slack integration is disabled globally"
- ✅ Admin > Slack Overview visualizza i canali (lettura DB), ma Test Connection restituisce HTTP 503

### Configurazione su astrogen03 (Production)

**File**: `/var/www/astrogen/.env`

```bash
# Slack Integration Control
# PRODUCTION: Slack integration enabled
SLACK_INTEGRATION_ENABLED=true

# Slack OAuth (PRODUCTION)
SLACK_CLIENT_ID=...
SLACK_CLIENT_SECRET=...
SLACK_BOT_TOKEN=...
```

**Effetto**:
- ✅ Progetti creati su astrogen03 generano messaggi Slack in `#ag-*-lavori`
- ✅ Assegnazioni su astrogen03 generano notifiche Slack nel thread del progetto
- ✅ Export analisi funzionano normalmente
- ✅ Admin > Slack Overview funziona completamente

### Verifica Post-Deployment

```bash
# Su astrogen01 - Verifica disabilitazione
grep SLACK_INTEGRATION_ENABLED /var/www/astrogen/.env
# Atteso: SLACK_INTEGRATION_ENABLED=false

# Su astrogen03 - Verifica abilitazione
grep SLACK_INTEGRATION_ENABLED /var/www/astrogen/.env
# Atteso: SLACK_INTEGRATION_ENABLED=true (o assente = default true)

# Restart Flask su entrambi
sudo systemctl restart agata-flask
```

---

## Procedura Deployment

### Fase 1: Su astrogen01 (Sviluppo)

#### 1.1 Prepara Codice
Assicurati che tutto il codice sia committato e il branch `main` sia aggiornato:

```bash
cd /var/www/astrogen
git status  # Verifica working directory pulito
git log -5 --oneline  # Verifica ultimi commit
```

#### 1.2 Esegui Script di Deployment
Usa lo script automatico per generare schema DB e pushare su GitHub:

```bash
# Test in dry-run (raccomandato prima volta)
./deploy_to_production.sh --dry-run

# Esecuzione reale
./deploy_to_production.sh
```

**Output atteso**:
- ✅ Schema DB esportato in `/tmp/agata_schema_latest.sql` (1796 righe)
- ✅ Push completato su GitHub
- 📋 Istruzioni stampate a console per astrogen03

#### 1.3 Verifica File Generati
```bash
ls -lh /tmp/agata_schema_latest.sql
# Atteso: ~85KB, 1796 righe

git log -1 --oneline
# Atteso: commit deployment script presente
```

---

### Fase 2: Su astrogen03 (Produzione)

⚠️ **ATTENZIONE**: Esegui questi comandi direttamente su astrogen03 (via console/SSH locale, NON da astrogen01).

#### 2.1 Backup Codice Attuale
Crea branch di backup prima di sovrascrivere:

```bash
ssh astrogen01@10.1.0.6
cd /var/www/astrogen

git branch backup-$(date +%Y%m%d-%H%M%S)
git push origin backup-$(date +%Y%m%d-%H%M%S)
```

#### 2.2 Configura Git Remote (prima volta)
Verifica che il remote punti al repository di produzione:

```bash
git remote -v
# Dovrebbe mostrare: origin  https://github.com/giorgio-astrogen/astrogen

# Se sbagliato, correggi:
git remote set-url origin https://github.com/giorgio-astrogen/astrogen
```

#### 2.3 Pull Nuovo Codice
Scarica l'ultimo codice da GitHub:

```bash
git fetch origin
git checkout main
git reset --hard origin/main

# Verifica commit deployato
git log -1 --oneline
# Atteso: e43af28 Add deployment script for astrogen03 migration (o più recente)

git tag
# Atteso: v1.19.0-production presente
```

#### 2.4 Aggiorna Dipendenze Python
```bash
source venv/bin/activate  # o path virtualenv (es: /var/www/astrogen/venv)
pip install -r requirements.txt --upgrade
```

#### 2.5 Backup Database (CRITICO!)
⚠️ **NON SALTARE QUESTO STEP**

```bash
mysqldump -u aaaat01 -p catalogo > ~/backup_catalogo_$(date +%Y%m%d_%H%M%S).sql

# Verifica backup creato
ls -lh ~/backup_catalogo_*.sql
```

#### 2.6 Trasferimento Schema Database

**Opzione A - Manuale** (se astrogen03 non accessibile via SSH da astrogen01):
1. Su astrogen01: `cat /tmp/agata_schema_latest.sql`
2. Copia contenuto
3. Su astrogen03: `vim /tmp/agata_schema_latest.sql` e incolla

**Opzione B - SCP** (se SSH configurato):
```bash
# Da astrogen01
scp /tmp/agata_schema_latest.sql astrogen01@10.1.0.6:/tmp/
```

**Opzione C - Rigenera localmente** (se hai accesso DB):
```bash
# Su astrogen03
mysqldump -u aaaat01 -p --no-data catalogo > /tmp/agata_schema_latest.sql
sed -i 's/CREATE TABLE `/CREATE TABLE IF NOT EXISTS `/g' /tmp/agata_schema_latest.sql
```

#### 2.7 Applica Migrazioni Database
```bash
mysql -u aaaat01 -p catalogo < /tmp/agata_schema_latest.sql
```

**Verifica tabelle create**:
```bash
mysql -u aaaat01 -p catalogo -e "SHOW TABLES LIKE 'agata_%';" | wc -l
# Atteso: ~50+ tabelle
```

**Verifica dati preservati**:
```bash
mysql -u aaaat01 -p catalogo -e "SELECT COUNT(*) FROM agata_projects;"
mysql -u aaaat01 -p catalogo -e "SELECT COUNT(*) FROM agata_users;"
# Atteso: dati esistenti preservati (COUNT > 0 se dati presenti)
```

#### 2.8 Verifica Configurazioni
Controlla file `.env` per credenziali di produzione:

```bash
vim /var/www/astrogen/.env
```

**Variabili critiche da verificare**:
```env
# Database
DATABASE_URL=mysql+pymysql://aaaat01:PASSWORD@localhost:3306/catalogo

# API Keys
ANTHROPIC_API_KEY=sk-ant-...
FLASK_SECRET_KEY=...

# OAuth
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
```

#### 2.9 Restart Servizi

**Opzione A - Systemd Service** (raccomandato):
```bash
sudo systemctl restart agata.service
sudo systemctl status agata.service

sudo systemctl restart nginx
sudo systemctl status nginx
```

**Opzione B - Gunicorn Standalone**:
```bash
pkill -f gunicorn
cd /var/www/astrogen
source venv/bin/activate
gunicorn -w 4 -b 0.0.0.0:5000 app:app --daemon

sudo systemctl restart nginx
```

#### 2.10 Verifica Deployment

**Test locale**:
```bash
curl http://localhost:5000/agata/admin/
# Atteso: HTML response (status 200 o 302 redirect)
```

**Test da browser**:
- URL: `http://10.1.0.6/agata/admin/`
- Verifica: Login Google OAuth funzionante
- Verifica: Dashboard admin caricato

**Verifica logs**:
```bash
tail -100 /var/log/nginx/error.log
tail -100 /var/www/astrogen/logs/app.log  # se esiste
```

---

## Checklist Pre-Deployment

Su **astrogen01**:
- [ ] Branch `main` aggiornato con ultimi commit
- [ ] Working directory pulito (`git status`)
- [ ] Tag di release creato (`v1.19.0-production`)
- [ ] Schema database esportato (`/tmp/agata_schema_latest.sql`)
- [ ] Script `deploy_to_production.sh` testato in dry-run
- [ ] Push completato su GitHub

Su **astrogen03**:
- [ ] Accesso al server verificato (console/SSH)
- [ ] Backup database creato
- [ ] File `.env` pronto con credenziali produzione

---

## Checklist Post-Deployment

- [ ] Git log mostra commit corretto (`e43af28` o più recente)
- [ ] Database schema applicato (50+ tabelle AGATA)
- [ ] Dati esistenti preservati (COUNT(*) invariato)
- [ ] Servizi Flask/Nginx riavviati
- [ ] Login Google OAuth funzionante
- [ ] Dashboard admin accessibile
- [ ] VAST automation disponibile (`/agata/admin/vast/jobs`)
- [ ] Catalog integration attivo (`/agata/catalog/`)
- [ ] Field Star Map caricato (`/agata/field-star-map/`)
- [ ] Logs non mostrano errori critici

---

## Rollback Procedure

Se il deployment fallisce su astrogen03:

### 1. Rollback Codice
```bash
cd /var/www/astrogen
git checkout backup-YYYYMMDD-HHMMSS  # branch backup creato in Fase 2.1
git reset --hard
```

### 2. Rollback Database
```bash
mysql -u aaaat01 -p catalogo < ~/backup_catalogo_YYYYMMDD_HHMMSS.sql
```

### 3. Restart Servizi
```bash
sudo systemctl restart agata.service
sudo systemctl restart nginx
```

### 4. Verifica Rollback
```bash
curl http://localhost:5000/agata/admin/
git log -1 --oneline
```

---

## Troubleshooting

### Problema: Git Remote Sbagliato
**Sintomo**: `git fetch origin` scarica codice sbagliato

**Soluzione**:
```bash
git remote -v
git remote set-url origin https://github.com/giorgio-astrogen/astrogen
git fetch origin
```

### Problema: Schema DB Incompatibile
**Sintomo**: Errore `ALTER TABLE` durante migrazioni

**Soluzione**:
```bash
# Ripristina backup DB
mysql -u aaaat01 -p catalogo < ~/backup_catalogo_LATEST.sql

# Verifica schema
mysql -u aaaat01 -p catalogo -e "SHOW TABLES;"
mysql -u aaaat01 -p catalogo -e "DESCRIBE agata_users;"
```

### Problema: Servizi Non Riavviano
**Sintomo**: `systemctl restart agata.service` fallisce

**Soluzione**:
```bash
# Verifica logs servizio
sudo journalctl -u agata.service -n 50

# Verifica .env
cat /var/www/astrogen/.env | grep -E "DATABASE_URL|FLASK_SECRET"

# Test manuale Flask
cd /var/www/astrogen
source venv/bin/activate
python -m flask run
```

### Problema: OAuth Login Fallisce
**Sintomo**: Errore "invalid_client" o redirect loop

**Soluzione**:
```bash
# Verifica credenziali Google OAuth in .env
cat /var/www/astrogen/.env | grep GOOGLE_CLIENT

# Verifica Authorized redirect URIs in Google Cloud Console:
# - http://10.1.0.6/auth/callback
# - http://10.1.0.6/auth/google/callback
```

### Problema: Database Connection Failed
**Sintomo**: Errore "Can't connect to MySQL server"

**Soluzione**:
```bash
# Test connessione DB
mysql -u aaaat01 -p catalogo -e "SELECT 1;"

# Verifica DATABASE_URL in .env
cat /var/www/astrogen/.env | grep DATABASE_URL

# Verifica servizio MySQL
sudo systemctl status mysql
```

---

## File Importanti

| File/Directory | Descrizione | Location |
|----------------|-------------|----------|
| `deploy_to_production.sh` | Script deployment automatico | `/var/www/astrogen/` |
| `agata_schema_latest.sql` | Schema DB (generato) | `/tmp/` |
| `.env` | Configurazioni ambiente | `/var/www/astrogen/` |
| `requirements.txt` | Dipendenze Python | `/var/www/astrogen/` |
| `backup_catalogo_*.sql` | Backup database | `~/` |
| `agata.service` | Systemd service file | `/etc/systemd/system/` (se presente) |

---

## Future Improvements

1. **CI/CD Automatico**: GitHub Actions che deploya su astrogen03 al push su `main`
2. **Database Migrations**: Alembic per gestire migrazioni versionali
3. **Health Checks**: Endpoint `/health` per monitoraggio
4. **Blue-Green Deployment**: Due istanze parallele per zero-downtime
5. **Automated Backups**: Backup database automatici pre-deployment
6. **SSH Setup**: Configurare chiavi SSH tra astrogen01 e astrogen03 per SCP diretto

---

## Stima Tempo

- **Prima migrazione**: ~1.5 ore (include setup, backup, verifica)
- **Migrazioni successive**: ~30 minuti (processo rodato)

---

## Contatti

In caso di problemi:
- Verifica logs: `/var/log/nginx/error.log`, `/var/www/astrogen/logs/`
- Consulta documentazione: `/var/www/astrogen/docs/`
- Rollback: Segui procedura sopra

---

**Last tested**: 2026-02-16
**Deployment script version**: v1.0
**AGATA version**: v1.19.0-production
