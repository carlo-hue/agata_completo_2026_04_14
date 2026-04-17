# CLAUDE.md - Astrogen / AGATA

**Version**: 2.9.9 | Flask + MySQL/MariaDB | Python 3.12

---

## Cos'e Astrogen

Applicazione web per analisi astronomica: stelle variabili, esopianeti, galassie nane, mappe stellari di campo. Flask backend con MySQL/MariaDB, architettura multi-tenant con RBAC (Role-Based Access Control), autenticazione OAuth 2.0 Google. AI Advisor (Claude/Cerebras) per raccomandazioni intelligenti. Integrazione cataloghi esterni (Gaia DR3, VSX, TESS, ZTF, ASAS-SN, OGLE, Vizier). Knowledge Base con ricerca semantica. VAST automation per fotometria automatizzata da immagini FITS.

---

## Architettura Modulare

Ogni funzionalita e un modulo autonomo sotto `agata/moduli/`. Il modulo `field_star_map` e il **gold standard** da seguire per ogni nuovo sviluppo.

### Directory del Progetto

```
/var/www/astrogen/
  app.py                        # Flask init, registrazione blueprint
  agata/
    __init__.py                 # __version__ (single source of truth)
    auth/                       # OAuth 2.0 Google
    auth_models/                # SQLAlchemy ORM (TUTTI i modelli, condivisi)
    catalog/                    # Query Vizier (blueprint legacy)
    kb/                         # Knowledge Base (blueprint legacy)
    core/db/                    # SessionLocal (connessione DB)
    moduli/                     # === PATTERN MODULARE ===
      field_star_map/           # GOLD STANDARD - riferimento per nuovi moduli
      variable_stars/           # Analisi stelle variabili (routes/ multipli)
      exoplanets/               # Transiti esopianeti
      admin/                    # Gestione RBAC, progetti, VAST, ZTF (routes/ multipli)
      galassie_nane/            # Ricerca galassie nane
      lightcurve/               # Fotometria curve di luce
  docs/
    ARCHITECTURE.md             # Documento architettura normativo
    DATABASE_SCHEMA.md          # Schema DB (autoritativo - consultare SEMPRE)
    migrations/                 # SQL numerati (000-006+)
    features/                   # Doc per feature
  scripts/
    deploy.sh                   # Deploy automatico (codice + DB + requirements)
```

### Struttura Gold Standard (field_star_map)

```
agata/moduli/<nome_modulo>/
  __init__.py              # Blueprint: name, url_prefix, template_folder, static_folder
  routes.py                # Endpoint HTTP, importa da ./services/
  services/
    __init__.py
    <servizio>.py          # Logica pura Python, dataclass per I/O, NO Flask request
  templates/
    <blueprint_name>/      # Jinja2 templates (sottocartella = nome blueprint)
  static/
    <blueprint_name>/
      css/
      js/
```

### Regole Architetturali

1. **Modulo autonomo**: ogni modulo ha blueprint, routes, services, templates, static propri
2. **Services puri**: niente `from flask import request` nei services. Usare dataclass/namedtuple per input/output. Funzioni pure, testabili senza Flask
3. **Cross-module**: si possono importare **services** da altri moduli, MAI routes
4. **Models condivisi**: tutti in `agata/auth_models/` (non dentro i moduli)
5. **Moduli grandi** (admin, variable_stars): directory `routes/` con file multipli per dominio
6. **Registrazione**: ogni blueprint si registra in `app.py` con `app.register_blueprint()`
7. **Protezione RBAC**: `@before_request` nel `__init__.py` del modulo (vedi `galassie_nane/__init__.py`)

---

## Creare un Nuovo Modulo

1. Creare `agata/moduli/<nome>/` con la struttura gold standard
2. `__init__.py`: definire Blueprint con `url_prefix="/agata/<nome>"`, `template_folder="templates"`, `static_folder="static"`. Import routes **dopo** la definizione del blueprint
3. `routes.py`: endpoint HTTP, importa logica da `./services/`
4. `services/`: Python puro. Dataclass per parametri e risultati. Timeout espliciti per API esterne. Retry logic configurabile via env vars
5. Se serve DB:
   - Modello SQLAlchemy in `agata/auth_models/<nome>.py`
   - Export in `agata/auth_models/__init__.py`
   - Migration SQL in `docs/migrations/NNN_<modulo>_<descrizione>.sql`
   - Aggiornare `docs/DATABASE_SCHEMA.md`
6. Registrare blueprint in `app.py`
7. Protezione RBAC: `@before_request` nel `__init__.py` (copiare pattern da `galassie_nane`)
8. Documentazione: creare doc in `docs/features/` se feature non triviale

**Riferimento completo**: `agata/moduli/field_star_map/` - leggere tutti i file prima di creare un nuovo modulo.

---

## Database

- **DBMS**: MySQL/MariaDB via PyMySQL + SQLAlchemy ORM
- **Modelli**: `agata/auth_models/` (un file per entita)
- **Schema**: `docs/DATABASE_SCHEMA.md` - **SEMPRE consultare prima di toccare il DB**
- **Migrazioni**: SQL numerati in `docs/migrations/` (no Alembic, no skeema)
- **Multi-tenant**: ogni query filtra per `association_id`
- **Convenzione migrazioni**: `NNN_<modulo>_<descrizione>.sql` (es. `004_create_tess_bulk_import_tables.sql`)

### Aggiungere una Tabella

1. Scrivere modello SQLAlchemy in `agata/auth_models/<nome>.py`
2. Esportare da `agata/auth_models/__init__.py`
3. Scrivere migration SQL in `docs/migrations/NNN_<modulo>_<desc>.sql` (idempotente: `CREATE TABLE IF NOT EXISTS`)
4. Aggiornare `docs/DATABASE_SCHEMA.md`
5. Applicare su dev, poi deploy su prod con `scripts/deploy.sh`

---

## Deploy in Produzione

**Procedura:** deploy codice + SQL migrations separate (script automatico via SSH).

### Deploy Codice

```bash
# Step 1: Deploy codice (main branch)
./scripts/deploy.sh --yes

# Step 2: Deploy tag specifico
./scripts/deploy.sh --yes --tag v3.0.3

# Step 3: (SOLO per preview) controllare senza applicare
./scripts/deploy.sh --dry-run
```

### SQL Migrations (Automatico via SSH)

Esegui migrazioni pendenti su produzione con credenziali da `.env`:

```bash
# Legge DATABASE_URL da .env, connette a produzione, applica migration
./scripts/migrate-prod.sh docs/migrations/013_drop_tess_curl_entries.sql

# Oppure per migrazioni multiple
./scripts/migrate-prod.sh docs/migrations/013_*.sql
```

**Script migrate-prod.sh** (crea se non esiste):
```bash
#!/bin/bash
# Deploy SQL migrations to production via SSH
# Usage: ./scripts/migrate-prod.sh <migration_file_or_glob>

set -e

PROD_SERVER="10.1.0.6"
PROD_USER="azureuser"
PROD_PATH="/var/www/astrogen"

if [ $# -eq 0 ]; then
    echo "Usage: $0 <migration_file_or_glob>"
    echo "Example: $0 docs/migrations/013_drop_tess_curl_entries.sql"
    exit 1
fi

# Extract password from DATABASE_URL in .env
DB_PASSWORD=$(grep "^DATABASE_URL=" .env | python3 -c "
import sys, urllib.parse
url = sys.stdin.read().split('=')[1].strip()
parsed = urllib.parse.urlparse(url)
print(parsed.password or '')
")

DB_USER="aaaat01"
DB_NAME="catalogo"

# Get migration files
MIGRATIONS=$(ls $1 2>/dev/null)
if [ -z "$MIGRATIONS" ]; then
    echo "No migration files found: $1"
    exit 1
fi

echo "📋 Migrations to apply:"
echo "$MIGRATIONS"
echo ""

for MIGRATION_FILE in $MIGRATIONS; do
    if [ ! -f "$MIGRATION_FILE" ]; then
        echo "❌ File not found: $MIGRATION_FILE"
        continue
    fi

    FILENAME=$(basename "$MIGRATION_FILE")
    echo "🚀 Applying $FILENAME..."

    # Execute migration on production via SSH
    ssh "$PROD_USER@$PROD_SERVER" <<EOSSH
cd $PROD_PATH
mysql -u $DB_USER -p"$DB_PASSWORD" $DB_NAME < <(cat <<'EOSQL'
$(cat "$MIGRATION_FILE")
EOSQL
)
EOSSH

    if [ $? -eq 0 ]; then
        echo "✅ $FILENAME applied successfully"
    else
        echo "❌ Failed to apply $FILENAME"
        exit 1
    fi
done

echo "✅ All migrations applied!"
```

**Prima di un tag/release**: aggiornare `__version__` in `agata/__init__.py`.

**Ambienti**: dev = astrogen01 (localhost), prod = astrogen03 (10.1.0.6).

---

## Autenticazione e RBAC

- **OAuth 2.0** con Google (`agata/auth/`)
- **Ruoli**: `superuser` (globale) > `admin` (associazione) > `reviewer` > `analyst` > `viewer` (solo lettura)
- **Protezione modulo**: `@before_request` nel blueprint `__init__.py`
- **Protezione route**: `@admin_required(min_role)`, `@superuser_required`, `@audit_action` (da `agata/moduli/admin/decorators.py`)
- **Multi-tenant**: tutti i dati filtrati per `association_id`
- **Ref**: `docs/auth/AGATA_AUTH_IMPLEMENTATION_SUMMARY.md`

---

## Standard Scientifici

L'accuratezza scientifica e prioritaria. Nessun compromesso per semplicita di codice.

- **astropy obbligatorio** per coordinate, unita, tempo, conversioni. Mai reimplementare calcoli astronomici
- **Coordinate**: J2000 con correzione moto proprio (proper motion)
- **Gaia cross-match**: raggio primario configurabile (tipicamente 2-10") + fallback a raggio piu ampio con flag `is_ambiguous`
- **Magnitudini**: documentare SEMPRE sistema fotometrico (Vega/AB) e filtro/banda passante
- **Analisi periodica**: Lomb-Scargle (astropy.timeseries). Pre-whitening Fourier per segnali multi-periodici
- **Phase folding**: modulo 1.0, epoca di riferimento documentata esplicitamente
- **Propagazione errori**: trasportare incertezze attraverso TUTTE le trasformazioni
- **API esterne**: timeout espliciti sempre (pattern `GAIA_TIMEOUT_SECONDS` in env vars). Retry con backoff

---

## Standard Documentazione

- **Ogni feature non triviale**: doc in `docs/features/<nome>.md`
- **Modifiche DB**: aggiornare `docs/DATABASE_SCHEMA.md` **immediatamente**
- **Migrazioni**: SQL numerati in `docs/migrations/`
- **CLAUDE.md**: sotto 250 righe, niente storico sessioni o bug fix
- **docs/INDEX.md**: guida navigazione master per tutta la documentazione
- **Codice**: docstring su services e route handler non banali. Commenti solo dove la logica non e auto-evidente
- **REGOLA**: nessun file `.md` nella root del progetto (eccetto `CLAUDE.md`). Usare `/agata-docs` per creare doc nel percorso corretto

---

## Linee Guida Sviluppo

- **Pattern esistenti**: seguire i pattern del modulo su cui si lavora
- **No sovraingegneria**: funzioni pure, niente astrazioni premature. Tre righe simili > un'astrazione prematura
- **Secrets**: solo via `.env`, mai hardcoded
- **Logging**: `logging.getLogger(__name__)` a livello di modulo
- **Errori**: log con contesto (file, funzione, parametri), HTTP status code semanticamente corretti (422 validazione, 502 servizio esterno, 500 errore interno)
- **JavaScript**: ES6 modules (vedi `agata/moduli/variable_stars/static/js/`)
- **Configurazione**: variabili d'ambiente per tutto cio che e deployment-specific

---

## Slash Commands Disponibili

Usa questi comandi per guidare lo sviluppo coerentemente con l'architettura AGATA.

| Comando | Argomenti | Quando usarlo |
|---------|-----------|---------------|
| `/agata-new-module` | `<nome> "<desc>" <ruolo>` | Creare un nuovo modulo completo (Blueprint, routes, services, templates, RBAC) |
| `/agata-new-catalog` | `<nome> "<url>" "<desc>"` | Integrare un catalogo esterno (Gaia, TESS, ZTF, etc.) |
| `/agata-new-service` | `<modulo> <file> "<desc>"` | Aggiungere una funzione service pura (no Flask, Python scientifico) |
| `/agata-new-route` | `<modulo> <file> "<METHOD /path>" "<desc>"` | Aggiungere un endpoint HTTP in modulo esistente |
| `/agata-new-model` | `<NomeEntita> "<desc>"` | Creare tabella DB: model SQLAlchemy + migration SQL + DATABASE_SCHEMA.md |
| `/agata-new-pipeline` | `<nome> "<stati>" "<desc>"` | Implementare background job (state machine, ThreadPoolExecutor, polling) |
| `/agata-new-js-feature` | `<modulo> <file> "<desc>"` | Aggiungere feature JavaScript (ES6 modules, no calcoli scientifici) |
| `/agata-fix-bug` | `<descrizione>` | Correggere bug targeted (fix minimo, no refactor non richiesto) |
| `/agata-refactor` | `<file> "<motivo>"` | Refactor behavior-preserving (API invariata) |
| `/agata-rbac` | `<tipo> <file> "<desc>"` | Aggiungere RBAC protection, audit logging, scope filtering |
| `/agata-docs` | `"<desc>"` | Creare documentazione nel percorso corretto (`docs/`) |

**Exemplo uso:**
```
/agata-new-module spectroscopy "Analisi spettri stellari" analyst
/agata-new-service variable_stars lomb_scargle "Periodogramma Lomb-Scargle con pre-whitening"
/agata-fix-bug "KeyError 'g_mag' in routes.py:103 quando stella non ha fotometria Gaia"
```

---

## Riferimenti Rapidi

| Serve... | Leggere... |
|----------|------------|
| Confini architetturali | `docs/ARCHITECTURE.md` |
| Schema DB (tabelle, relazioni) | `docs/DATABASE_SCHEMA.md` |
| Pattern nuovo modulo | `agata/moduli/field_star_map/` (tutti i file) |
| RBAC e protezione | `agata/moduli/galassie_nane/__init__.py` (pattern @before_request) |
| Admin module | `agata/moduli/admin/README.md` |
| Deploy | `scripts/deploy.sh` (self-documented) |
| Auth setup | `docs/auth/AGATA_AUTH_SETUP_GUIDE.md` |
| Tutta la documentazione | `docs/INDEX.md` |
| VAST automation | `docs/features/vast/VAST_SETUP_GUIDE.md` |
| Cataloghi Vizier | `docs/features/CATALOG_INTEGRATION.md` |
