# 📄 README – Setup locale AGATA (Windows)

---

## 🎯 Obiettivo

Configurare AGATA in ambiente locale con:

- PostgreSQL locale
- ambiente Python isolato (`venv`)
- bypass autenticazione OAuth (solo sviluppo)
- accesso completo all’applicazione senza Google OAuth

---

## ⚡ Checklist rapida

Prima di avviare:

- ✔ PostgreSQL attivo
- ✔ venv attivo
- ✔ file `.env` presente
- ✔ DB `catalogo_pg` esistente
- ✔ tabelle auth create

---

## 📦 1. Clonazione repository

```powershell
cd C:\Users\CarloMarino\dev
git clone https://github.com/giorgio-astrogen/flask.git
cd flask
```

---

## 🐍 2. Ambiente Python

⚠️ Usare Python 3.12 o 3.13

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install flask-login python-dotenv Authlib "psycopg[binary]"
```

---

## 🗄️ 3. AVVIO PostgreSQL locale

- DB: `catalogo_pg`
- User: `agata_user`
- Password: `agata_pass_dev`

Avvio:

```powershell
net start postgresql-x64-16
```

---

## ⚙️ 4. File `.env`

```env
DATABASE_URL=postgresql+psycopg://agata_user:agata_pass_dev@localhost/catalogo_pg
FLASK_ENV=development
FLASK_DEBUG=1
DEV_AUTH_BYPASS=true
```

---

## 🔓 5. Bypass autenticazione

### In `app.py`

Dopo `app = Flask(...)`:

```python
flag = os.getenv("DEV_AUTH_BYPASS", "false")
app.config["DEV_AUTH_BYPASS"] = flag.lower() in ("1", "true", "yes", "on")

print("DEV_AUTH_BYPASS =", app.config["DEV_AUTH_BYPASS"])
```

---

### In `agata/auth/routes.py`

#### Modifica login_page

```python
flag = current_app.config.get("DEV_AUTH_BYPASS", False)
if flag:
    return redirect('/auth/dev-login')
```

#### Aggiungi dev-login

```python
@auth_bp.route('/dev-login')
def dev_login():
    db: Session = SessionLocal()
    try:
        flag = current_app.config.get("DEV_AUTH_BYPASS", False)
        if not flag:
            return jsonify({"error": "Dev login disabilitato"}), 404

        user = db.query(User).filter_by(email='dev@local').first()

        if not user:
            user = User(
                id=str(uuid.uuid4()),
                email='dev@local',
                name='Dev',
                surname='Local',
                provider='dev',
                provider_user_id='dev-local-user',
                is_internal=True,
                role='superuser',
                is_active=True,
                email_verified=True,
                last_login=datetime.utcnow(),
                last_login_ip=request.remote_addr,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user.last_login = datetime.utcnow()
            db.commit()

        login_user(user, remember=True)
        return redirect(url_for('admin.list_projects'))

    finally:
        db.close()
```

---

## 🚀 6. Avvio AGATA

```powershell
cd C:\Users\CarloMarino\dev\flask
.venv\Scripts\activate
python app.py
```

Output atteso:

```
DEV_AUTH_BYPASS = True
Running on http://127.0.0.1:5000
```

---

## 🌐 7. Accesso AGATA

```
http://127.0.0.1:5000
```

Flusso:

```
/ → /auth/index → /auth/dev-login → /admin/projects
```

---

## ⚠️ Troubleshooting

### 404 su /auth/dev-login
→ route non presente in routes.py

### bypass non attivo
→ controllare print DEV_AUTH_BYPASS

### NameError app
→ config messa prima di Flask()

---

## 🎯 Stato finale

✔ Login automatico  
✔ OAuth bypassato  
✔ Ambiente locale funzionante  

---

## 🚀 Futuro

- Docker
- config DEV/PROD separata
- auto-login senza route
