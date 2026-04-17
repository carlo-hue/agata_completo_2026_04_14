# 🧪 Test Login Google - AGATA

## ✅ Stato Sistema

- [x] Database configurato
- [x] Modelli SQLAlchemy OK
- [x] OAuth routes registrate
- [x] Google OAuth configurato in .env
- [x] app.py aggiornato (Microsoft Auth rimosso)
- [x] db.py legge da .env

**Tutto pronto per il test!**

---

## 🚀 Come Avviare l'App

### Opzione 1: Da VSCode (Debug Mode)

1. Apri VSCode
2. Vai su "Run and Debug" (Ctrl+Shift+D)
3. Seleziona "Python Debugger: Flask"
4. Click ▶️ Start Debugging (F5)

Server disponibile su:
- http://localhost:5000
- http://10.1.0.4:5000 (IP LAN)

### Opzione 2: Da Terminale

```bash
cd /var/www/astrogen
source flask/bin/activate

# Imposta variabili Flask
export FLASK_APP=app.py
export FLASK_ENV=development

# Avvia server
python3 app.py

# Oppure con Flask CLI
flask run --host=0.0.0.0 --port=5000
```

---

## 🧪 Test Login Google

### Step 1: Apri Homepage

Browser: **http://localhost:5000**

Dovresti vedere:
```
AGATA - Benvenuto
Sistema di analisi astronomica per AstroGen APS

Login
[Login with Google]
[Login with Slack]
```

### Step 2: Click "Login with Google"

Redirect automatico a: `http://localhost:5000/auth/login/google`

Poi redirect a Google OAuth con URL tipo:
```
https://accounts.google.com/o/oauth2/v2/auth?
  client_id=411756582657-0qcvjt2mchundjnnv09lc1eoc65ntpap.apps.googleusercontent.com
  &redirect_uri=http://localhost:5000/auth/callback/google
  &scope=openid+email+profile
  &response_type=code
  ...
```

### Step 3: Autorizza su Google

1. Scegli account Google
2. Autorizza l'app "AGATA"
3. Google ti redirect a: `http://localhost:5000/auth/callback/google?code=...`

### Step 4: Verifica Login Riuscito

Dopo autorizzazione, dovresti vedere dashboard:
```
Benvenuto su AGATA
Ciao, [Tuo Nome]!
Email: [tua@email.com]
Ruolo: analyst (o viewer)
Associazione: AstroGen APS (o Nessuna)

[AAAAT - Stelle Variabili]
[Esopianeti]
[Info Utente (API)]
[Logout]
```

---

## 🔍 Verifica Database

Dopo il primo login, verifica che l'utente sia stato creato:

```bash
mysql -u aaaat01 -p'dwedfAA1saa14' -D catalogo -e "
SELECT
    email,
    name,
    role,
    provider,
    is_internal,
    association_id,
    last_login
FROM agata_users
WHERE provider = 'google'
ORDER BY created_at DESC
LIMIT 5;
"
```

Output atteso:
```
email             | name       | role     | provider | is_internal | association_id | last_login
tua@email.com     | Tuo Nome   | analyst  | google   | 0           | 1              | 2026-01-13 ...
```

Verifica audit log:
```bash
mysql -u aaaat01 -p'dwedfAA1saa14' -D catalogo -e "
SELECT
    created_at,
    user_email,
    action,
    description
FROM agata_audit_log
ORDER BY created_at DESC
LIMIT 10;
"
```

---

## 🧪 Test API Endpoint

Con sessione attiva:

```bash
# Ottieni info utente corrente
curl http://localhost:5000/auth/me

# Output atteso (JSON):
{
  "id": "uuid-here",
  "email": "tua@email.com",
  "name": "Tuo",
  "surname": "Nome",
  "full_name": "Tuo Nome",
  "role": "analyst",
  "is_internal": false,
  "association_id": 1,
  "association": {
    "id": 1,
    "name": "AstroGen APS",
    "slug": "astrogen",
    "type": "internal"
  }
}
```

---

## 🐛 Troubleshooting

### Errore: "redirect_uri_mismatch"

**Causa**: URL callback non autorizzato in Google Console

**Soluzione**:
1. Vai su https://console.cloud.google.com/
2. APIs & Services → Credentials
3. Click su OAuth 2.0 Client ID
4. Verifica "Authorized redirect URIs" contenga ESATTAMENTE:
   ```
   http://localhost:5000/auth/callback/google
   ```

### Errore: "This app is blocked"

**Causa**: App in modalità Testing con utente non autorizzato

**Soluzione**:
1. Google Console → OAuth consent screen
2. Se "User Type" = External:
   - Scroll → Test users
   - Add Users → Aggiungi tua email
3. Oppure cambia a "Internal" (richiede Google Workspace)

### Errore: "ImportError: cannot import name 'oauth'"

**Causa**: File `agata/auth/__init__.py` mancante o errato

**Soluzione**:
```bash
# Verifica file esista
ls -la agata/auth/__init__.py

# Rigenera cache Python
find agata/auth -name "*.pyc" -delete
find agata/auth -name "__pycache__" -type d -exec rm -rf {} +
```

### L'app non parte da VSCode

**Verifica**:
1. `.vscode/launch.json` contiene:
   ```json
   "env": {
       "FLASK_APP": "app.py",
       "FLASK_DEBUG": "1"
   }
   ```
2. Virtual environment: `flask/bin/python`
3. In VSCode status bar (in basso) seleziona interpreter: `./flask/bin/python`

---

## 🎯 Cosa Fare Dopo il Login

### 1. Promuovi il tuo utente ad Admin

```sql
UPDATE agata_users
SET role = 'admin'
WHERE email = 'tua@email.com';
```

### 2. Oppure a Superuser (accesso globale)

```sql
UPDATE agata_users
SET role = 'superuser', association_id = NULL
WHERE email = 'tua@email.com';
```

### 3. Testa protezione route

Prova ad accedere a:
- `/agata/variable-stars` (dovrebbe funzionare se autenticato)
- `/auth/me` (JSON con info utente)
- `/auth/logout` (logout e redirect homepage)

---

## 📊 Log di Debug

### Vedere log Flask in tempo reale

```bash
# Terminal dove gira Flask mostrerà:
127.0.0.1 - - [13/Jan/2026 12:00:00] "GET /auth/login/google HTTP/1.1" 302 -
127.0.0.1 - - [13/Jan/2026 12:00:05] "GET /auth/callback/google?code=... HTTP/1.1" 302 -
127.0.0.1 - - [13/Jan/2026 12:00:06] "GET / HTTP/1.1" 200 -
```

### Vedere errori Python

Se c'è un errore, Flask mostrerà traceback completo nel terminal.

---

## ✅ Checklist Test

- [ ] Server Flask parte correttamente
- [ ] Homepage mostra pulsanti login
- [ ] Click "Login with Google" redirect a Google
- [ ] Autorizzazione Google funziona
- [ ] Redirect callback a localhost funziona
- [ ] Dashboard mostra dati utente
- [ ] Utente creato in DB (`agata_users`)
- [ ] Audit log registrato (`agata_audit_log`)
- [ ] `/auth/me` restituisce JSON corretto
- [ ] Logout funziona e cancella sessione

---

**Pronto per il test!** 🚀

Avvia l'app e prova il login Google.
