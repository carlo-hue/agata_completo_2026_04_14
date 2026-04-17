# AGATA OAuth Authentication - Setup Guide

Guida completa per configurare l'autenticazione OAuth 2.0 in AGATA.

---

## 📦 1. Installazione Dipendenze

```bash
cd /var/www/astrogen

# Attiva virtual environment (se presente)
source flask/bin/activate

# Installa dipendenze auth
pip install -r requirements-auth.txt
```

**Dipendenze installate**:
- Flask 3.0.0
- Flask-Login 0.6.3 (session management)
- Authlib 1.3.0 (OAuth client)
- PyMySQL 1.1.0 (MySQL connector)
- slack-sdk 3.26.0 (Slack integration)
- python-dotenv 1.0.0 (env variables)

---

## 🔐 2. Configurazione Environment Variables

```bash
# Copia template
cp .env.agata.example .env

# Genera secret key sicura
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))" >> .env

# Edita .env con le tue credenziali OAuth
nano .env
```

### Valori da configurare in `.env`:

```bash
SECRET_KEY=<generato-sopra>
DATABASE_URL=mysql+pymysql://aaaat01:dwedfAA1saa14@localhost:3306/catalogo
GOOGLE_CLIENT_ID=<da-google-console>
GOOGLE_CLIENT_SECRET=<da-google-console>
SLACK_CLIENT_ID=<da-slack-app>
SLACK_CLIENT_SECRET=<da-slack-app>
SLACK_SIGNING_SECRET=<da-slack-app>
BASE_URL=https://app-test.astrogen.it
```

---

## 🔧 3. Setup Google OAuth

### 3.1 Crea Progetto Google Cloud

1. Vai a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea nuovo progetto "AGATA" (o usa esistente)
3. Seleziona il progetto

### 3.2 Abilita Google+ API

1. Menu → **APIs & Services** → **Library**
2. Cerca "Google+ API"
3. Click **Enable**

### 3.3 Configura OAuth Consent Screen

1. Menu → **APIs & Services** → **OAuth consent screen**
2. Seleziona **Internal** (se hai Google Workspace) o **External**
3. Compila form:
   - App name: `AGATA`
   - User support email: `info@astrogen.it`
   - Developer contact: `info@astrogen.it`
4. **Save and Continue**
5. Scopes: aggiungi `.../auth/userinfo.email`, `.../auth/userinfo.profile`
6. **Save and Continue**

### 3.4 Crea Credenziali OAuth 2.0

1. Menu → **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. Application type: **Web application**
4. Name: `AGATA Web Client`
5. **Authorized redirect URIs**: aggiungi
   ```
   https://app-test.astrogen.it/auth/callback/google
   http://localhost:5000/auth/callback/google  (per dev)
   ```
6. Click **Create**
7. **Copia Client ID e Client Secret** → incolla in `.env`

### 3.5 Test

```bash
# In browser, vai a:
https://app-test.astrogen.it/auth/login/google

# Dovresti vedere la schermata di consenso Google
```

---

## 💬 4. Setup Slack App

### 4.1 Crea Slack App

1. Vai a [Slack API](https://api.slack.com/apps)
2. Click **Create New App**
3. Seleziona **From scratch**
4. App Name: `AGATA Bot`
5. Workspace: seleziona il tuo workspace AstroGen
6. Click **Create App**

### 4.2 Configura OAuth & Permissions

1. Menu laterale → **OAuth & Permissions**

2. **Redirect URLs**: aggiungi
   ```
   https://app-test.astrogen.it/auth/callback/slack
   http://localhost:5000/auth/callback/slack  (per dev)
   ```

3. **Bot Token Scopes** (sezione Scopes):
   - `channels:read` - Leggere info canali pubblici
   - `channels:manage` - Gestire canali (rinomina, archivia)
   - `chat:write` - Inviare messaggi come bot
   - `commands` - Gestire slash commands
   - `users:read` - Leggere info utenti workspace
   - `users:read.email` - Leggere email utenti

4. **User Token Scopes** (per login):
   - `identity.basic` - Info profilo base
   - `identity.email` - Email utente
   - `identity.avatar` - Avatar utente

5. **Save Changes**

### 4.3 Installa App al Workspace

1. Scroll up → Click **Install to Workspace**
2. Autorizza l'app
3. **Copia Bot User OAuth Token** (`xoxb-...`) → salva in `.env` come `SLACK_BOT_TOKEN`

### 4.4 Configura App Credentials

1. Menu laterale → **Basic Information**
2. Sezione **App Credentials**:
   - **Client ID** → copia in `.env` come `SLACK_CLIENT_ID`
   - **Client Secret** → copia in `.env` come `SLACK_CLIENT_SECRET`
   - **Signing Secret** → copia in `.env` come `SLACK_SIGNING_SECRET`

### 4.5 Configura Slash Commands (opzionale)

1. Menu laterale → **Slash Commands**
2. Click **Create New Command**
3. Command: `/agata`
4. Request URL: `https://app-test.astrogen.it/api/slack/commands/agata`
5. Short Description: `Interagisci con AGATA`
6. Usage Hint: `[analyze|status|help] [args]`
7. **Save**

### 4.6 Configura Event Subscriptions (opzionale)

1. Menu laterale → **Event Subscriptions**
2. **Enable Events**: ON
3. Request URL: `https://app-test.astrogen.it/api/slack/events`
   (Slack invierà challenge request - endpoint deve rispondere)
4. **Subscribe to bot events**:
   - `message.channels` - Messaggi nei canali dove il bot è membro
   - `channel_created` - Nuovo canale creato
5. **Save Changes**

### 4.7 Test

```bash
# In browser, vai a:
https://app-test.astrogen.it/auth/login/slack

# Dovresti vedere la schermata di autorizzazione Slack
```

---

## 🚀 5. Avvio Applicazione

### 5.1 Development Mode

```bash
cd /var/www/astrogen

# Assicurati che .env sia configurato
export FLASK_ENV=development
export FLASK_APP=app_agata.py

# Avvia Flask development server
python3 app_agata.py

# Oppure usa Flask CLI
flask run --host=0.0.0.0 --port=5000
```

Applicazione disponibile su: `http://localhost:5000`

### 5.2 Production Mode (gunicorn)

```bash
# Installa gunicorn
pip install gunicorn

# Avvia con gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app_agata:app

# Con reload automatico (dev)
gunicorn -w 4 -b 0.0.0.0:5000 --reload app_agata:app
```

### 5.3 Systemd Service (per avvio automatico)

Crea file `/etc/systemd/system/agata.service`:

```ini
[Unit]
Description=AGATA Flask Application
After=network.target mysql.service

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/var/www/astrogen
Environment="PATH=/var/www/astrogen/flask/bin"
ExecStart=/var/www/astrogen/flask/bin/gunicorn -w 4 -b 127.0.0.1:5000 app_agata:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Abilita e avvia:
```bash
sudo systemctl daemon-reload
sudo systemctl enable agata
sudo systemctl start agata
sudo systemctl status agata
```

---

## 🧪 6. Testing

### 6.1 Test Manuale

1. **Homepage**
   ```
   https://app-test.astrogen.it/
   ```
   Dovresti vedere pulsanti "Login with Google" e "Login with Slack"

2. **Login con Google**
   ```
   https://app-test.astrogen.it/auth/login/google
   ```
   - Redirect a Google
   - Scegli account Google
   - Autorizza app
   - Redirect a AGATA dashboard

3. **API Info Utente**
   ```bash
   curl -X GET https://app-test.astrogen.it/auth/me \
     -H "Cookie: session=<your-session-cookie>"
   ```

4. **Logout**
   ```
   https://app-test.astrogen.it/auth/logout
   ```

### 6.2 Test Database

```bash
# Verifica utenti creati
mysql -u aaaat01 -p'dwedfAA1saa14' -D catalogo -e "
SELECT id, email, name, role, provider, is_internal, last_login
FROM agata_users
ORDER BY created_at DESC
LIMIT 10;
"

# Verifica token OAuth salvati
mysql -u aaaat01 -p'dwedfAA1saa14' -D catalogo -e "
SELECT user_id, provider, token_type, expires_at
FROM agata_oauth_tokens;
"

# Verifica audit log
mysql -u aaaat01 -p'dwedfAA1saa14' -D catalogo -e "
SELECT created_at, user_email, action, description
FROM agata_audit_log
ORDER BY created_at DESC
LIMIT 20;
"
```

### 6.3 Test Permessi

Python shell test:

```python
from agata.db import SessionLocal
from agata.auth_models import User

db = SessionLocal()

# Ottieni utente
user = db.query(User).filter_by(email='tua@email.com').first()

# Test permessi
print(f"Role: {user.role}")
print(f"Is analyst: {user.is_analyst}")
print(f"Has 'analyze' permission: {user.has_permission('analyze')}")
print(f"Has 'admin' permission: {user.has_permission('admin')}")

db.close()
```

---

## 🔒 7. Protezione Route

### 7.1 Esempio: Proteggere endpoint esistenti

Modifica file route esistenti (es. `agata/variable_stars/routes/data_routes.py`):

```python
# Aggiungi import
from agata.auth.decorators import login_required, require_permission

# Proteggi route
@variable_stars_bp.post("/api/periodogram.arrow")
@login_required  # Richiede utente autenticato
@require_permission('analyze')  # Richiede permesso 'analyze'
def api_periodogram_arrow():
    # ... existing code ...
    pass
```

### 7.2 Protezione per ruolo

```python
from agata.auth.decorators import require_role

@admin_bp.get("/users")
@login_required
@require_role('admin', 'superuser')  # Solo admin e superuser
def list_users():
    # ... code ...
    pass
```

### 7.3 Accesso utente corrente

```python
from flask_login import current_user

@app.route("/my-projects")
@login_required
def my_projects():
    user_id = current_user.id
    user_email = current_user.email
    user_role = current_user.role

    # Query progetti assegnati
    projects = db.query(Project).filter_by(
        assigned_to=user_id
    ).all()

    return render_template('projects.html', projects=projects)
```

---

## 📊 8. Amministrazione

### 8.1 Creare Superuser

```bash
# Connessione MySQL
mysql -u aaaat01 -p'dwedfAA1saa14' -D catalogo

# Promuovi utente esistente a superuser
UPDATE agata_users
SET role = 'superuser', association_id = NULL
WHERE email = 'admin@astrogen.it';

# Oppure crea nuovo superuser manualmente
INSERT INTO agata_users (
    id, email, name, role, is_internal, is_active, email_verified
) VALUES (
    UUID(),
    'superadmin@astrogen.it',
    'Super Admin',
    'superuser',
    TRUE,
    TRUE,
    TRUE
);
```

### 8.2 Creare Nuova Associazione

```sql
-- Crea associazione
INSERT INTO agata_associations (name, slug, type, slack_namespace, is_active)
VALUES ('Gruppo Variabili Toscane', 'gvt', 'partner', 'gvt', TRUE);

-- Assegna utente all'associazione
UPDATE agata_users
SET association_id = (SELECT id FROM agata_associations WHERE slug = 'gvt'),
    role = 'analyst'
WHERE email = 'utente@gvt.it';
```

### 8.3 Gestione Ruoli

```sql
-- Promuovi analyst a admin
UPDATE agata_users
SET role = 'admin'
WHERE email = 'responsabile@associazione.it';

-- Aggiungi reviewer
UPDATE agata_users
SET role = 'reviewer'
WHERE email = 'reviewer@associazione.it';
```

---

## 🐛 9. Troubleshooting

### Errore: "Provider non configurato"

**Causa**: Variabili `.env` non caricate o mancanti

**Soluzione**:
```bash
# Verifica .env esista
ls -la .env

# Controlla valori caricati
python3 -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('GOOGLE_CLIENT_ID'))"
```

### Errore: "Invalid redirect_uri"

**Causa**: URL callback non autorizzato in Google/Slack console

**Soluzione**:
- Google Console → Credentials → OAuth 2.0 Client → Authorized redirect URIs
- Slack App → OAuth & Permissions → Redirect URLs
- Verifica URL esatto (incluso `/auth/callback/<provider>`)

### Errore: "No verified email found"

**Causa**: Account GitHub senza email verificata

**Soluzione**:
- GitHub Settings → Emails → Verify your email
- Oppure rendi pubblica l'email: Settings → Profile → Public email

### Database: "Table doesn't exist"

**Causa**: Schema AGATA non installato

**Soluzione**:
```bash
mysql -u aaaat01 -p'dwedfAA1saa14' -D catalogo < AGATA_AUTH_SCHEMA_CLEAN.sql
```

### Session non persiste tra richieste

**Causa**: SECRET_KEY non configurato o cambia ad ogni restart

**Soluzione**:
```bash
# Genera secret key stabile
python3 -c "import secrets; print(secrets.token_hex(32))" > .secret_key

# Usa in .env
SECRET_KEY=$(cat .secret_key)
```

---

## 📚 10. Risorse

- [Google OAuth Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Slack OAuth Documentation](https://api.slack.com/authentication/oauth-v2)
- [Flask-Login Documentation](https://flask-login.readthedocs.io/)
- [Authlib Documentation](https://docs.authlib.org/)

---

## ✅ Checklist Completa

- [ ] Dipendenze installate (`pip install -r requirements-auth.txt`)
- [ ] Database schema creato (`AGATA_AUTH_SCHEMA_CLEAN.sql`)
- [ ] File `.env` configurato
- [ ] Google OAuth app creata e configurata
- [ ] Slack app creata e configurata
- [ ] Applicazione avviata (`python3 app_agata.py`)
- [ ] Test login Google funzionante
- [ ] Test login Slack funzionante
- [ ] Superuser creato
- [ ] Associazione AstroGen verificata
- [ ] Route protette con decorators
- [ ] Systemd service configurato (production)

---

**Setup completato!** 🎉

Per domande o problemi: controllare i log in `/var/log/mysql/error.log` e audit_log nel database.
