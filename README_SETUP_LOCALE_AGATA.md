# 📄 README – Setup locale AGATA (Windows)

---

## 🎯 Obiettivo

Configurare AGATA in ambiente locale con:

* PostgreSQL locale
* ambiente Python isolato (venv)
* bypass autenticazione OAuth (solo sviluppo)
* accesso completo all’applicazione

---

## ⚡ Checklist rapida

Prima di avviare:

* ✔ PostgreSQL attivo
* ✔ venv attivo
* ✔ file `.env` presente
* ✔ DB `catalogo_pg` esistente

---

## 📦 1. Clonazione repository

```powershell
cd C:\Users\CarloMarino\dev
git clone https://github.com/giorgio-astrogen/flask.git
cd flask
```

---

## 🐍 2. Ambiente Python

### ⚠️ Nota importante

Python 3.14 può causare errori (es. pandas).

👉 Usare Python 3.12 o 3.13

---

### Creazione ambiente virtuale

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
```

---

### Installazione dipendenze

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

### Dipendenze installate manualmente

```powershell
pip install flask-login
pip install python-dotenv
pip install Authlib
pip install "psycopg[binary]"
```

---

## 🗄️ 3. PostgreSQL locale

### Configurazione

* Database: `catalogo_pg`
* User: `agata_user`
* Password: `agata_pass_dev`

---

## ▶️ 3bis. Gestione PostgreSQL (Windows)

### Avvio servizio

```powershell
net start postgresql-x64-16
```

---

### Stop servizio

```powershell
net stop postgresql-x64-16
```

---

### Verifica stato

```powershell
Get-Service *postgres*
```

---

### Test connessione

```powershell
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U agata_user -d catalogo_pg -h localhost
```

---

## ⚙️ 4. File `.env`

Creare nella root del progetto:

```env
DATABASE_URL=postgresql+psycopg://agata_user:agata_pass_dev@localhost/catalogo_pg
FLASK_ENV=development
FLASK_DEBUG=1
DEV_AUTH_BYPASS=true
```

---

## 🔓 5. Bypass autenticazione (solo sviluppo)

### In `app.py`

```python
import os
app.config["DEV_AUTH_BYPASS"] = os.getenv("DEV_AUTH_BYPASS", "false")
```

---

### In `agata/auth/routes.py`

#### Route di login locale

```python
@auth_bp.route('/dev-login')
def dev_login():
    from datetime import datetime
    import uuid

    flag = current_app.config.get("DEV_AUTH_BYPASS", False)
    if isinstance(flag, str):
        flag = flag.lower() in ("1", "true", "yes", "on")

    if not flag:
        return jsonify({"error": "Dev login disabilitato"}), 404

    db = SessionLocal()

    try:
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
                association_id=None,
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
            user.last_login_ip = request.remote_addr
            db.commit()

        login_user(user, remember=True)

        return redirect('/admin/projects')

    finally:
        db.close()
```

---

### Modifica `login_page()`

```python
def login_page():
    flag = current_app.config.get("DEV_AUTH_BYPASS", False)
    if isinstance(flag, str):
        flag = flag.lower() in ("1", "true", "yes", "on")

    if flag:
        return redirect('/auth/dev-login')

    return render_template(...)
```

---

## 🧱 6. Creazione schema DB

⚠️ Importare i modelli PRIMA di creare le tabelle

```powershell
python
```

```python
import agata.auth_models.user
import agata.auth_models.association
import agata.auth_models.oauth_token
import agata.auth_models.audit_log

from agata.models import Base
from agata.db import engine

Base.metadata.create_all(bind=engine)
```

---

### Verifica tabelle

```sql
\dt
```

Devono comparire:

* agata_users
* agata_associations
* agata_oauth_tokens
* agata_audit_logs

---

## 🚀 7. Avvio applicazione

```powershell
cd C:\Users\CarloMarino\dev\flask
.venv\Scripts\activate
python app.py
```

---

## 🌐 8. Accesso

```text
http://127.0.0.1:5000
```

✔ login automatico
✔ utente dev creato
✔ accesso completo

---

## 🌿 9. Gestione Git

### Creazione branch locale

```bash
git checkout -b local-dev-auth-bypass
```

---

### Ripristino branch principale

```bash
git checkout main
git restore .
```

---

### Note

* NON pushare il branch dev
* contiene modifiche locali (bypass auth)

---

## ⚠️ Problemi incontrati

* Python 3.14 incompatibile → uso 3.12
* psycopg errore → installato `psycopg[binary]`
* OAuth non configurato → bypass dev
* `create_all()` inizialmente inefficace → mancavano import modelli

---

## 🎯 Stato finale

✔ AGATA funzionante in locale
✔ login bypass attivo
✔ DB operativo
✔ ambiente isolato con branch

---

## 🚀 Sviluppi futuri

* configurazione OAuth reale (Google)
* separazione config DEV/PROD
* script automatico di setup
* containerizzazione (Docker)


##  utilizzo HeidiSql
* prima aprire canale SSH
ssh -i "C:\Users\CarloMarino\.ssh\AstroGen01_key.pem" -L 3307:127.0.0.1:5432 astrogen01@4.232.73.56
poi lanciare HeidiSql ed aprire prod
---
