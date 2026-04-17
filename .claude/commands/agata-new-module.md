# AGATA – Crea Nuovo Modulo

**Argomenti:** `$ARGUMENTS` = `<nome_modulo> "<descrizione breve>" <ruolo_minimo>`

Esempio: `/agata-new-module spectroscopy "Analisi spettri stellari" analyst`

---

## Contesto Progetto

**Sistema:** AGATA | Flask + MySQL | Architettura modulare vincolata

**Gold standard obbligatorio:** leggi TUTTI i file in `agata/moduli/field_star_map/` prima di procedere.

**Riferimento RBAC:** leggi `agata/moduli/galassie_nane/__init__.py`.

**Registrazione blueprint:** leggi `app.py` (sezione Import blueprints).

---

## Struttura da Creare

Crea la seguente struttura per il modulo `$ARGUMENTS` (primo token = nome_modulo):

```
agata/moduli/<nome_modulo>/
  __init__.py
  routes.py
  services/
    __init__.py
    <nome_modulo>_service.py
  templates/
    <nome_blueprint>/
      index.html
  static/
    <nome_blueprint>/
      css/
        .gitkeep
      js/
        .gitkeep
```

---

## Regole Non Negoziabili

### `__init__.py`:

- Blueprint name = snake_case del modulo (es. `spectroscopy_bp`)
- `url_prefix="/agata/<nome-kebab-case>"`
- `template_folder="templates"`, `static_folder="static"`
- `@<blueprint>.before_request` con protezione RBAC (copia pattern da `galassie_nane/__init__.py`)
- Ruolo minimo dal terzo argomento (default: `analyst`)
- `LOCAL_DEV_BYPASS_AUTH` check obbligatorio
- Import routes DOPO la definizione del blueprint (bottom of file, noqa: E402,F401)

### `routes.py`:

- `from __future__ import annotations`
- `import logging; logger = logging.getLogger(__name__)`
- Importa dal blueprint locale: `from . import <blueprint_name>`
- Importa da services: `from .services.<nome>_service import ...`
- Route index: `@<bp>.get("")` e `@<bp>.get("/")`
- Route API con prefisso `/api/`
- **Nessun algoritmo scientifico nelle route** — solo parse input, chiama service, restituisci JSON/template
- HTTP status semantici: 422 validazione, 502 servizio esterno, 500 errore interno

### `services/<nome>_service.py`:

- `from __future__ import annotations`
- `from dataclasses import dataclass`
- **Nessun import Flask** (NO `from flask import ...`)
- Dataclass per ogni tipo di input/output complesso
- Timeout espliciti per API esterne via `os.getenv("XXXX_TIMEOUT_SECONDS", "20")`
- Retry configurabile via env vars
- Funzioni pure e testabili in isolamento

---

## Anti-Pattern Vietati

- `from flask import request` nei services
- Algoritmi scientifici nelle route
- Modelli SQLAlchemy dentro il modulo (vanno in `agata/auth_models/`)
- Blueprint senza `@before_request` RBAC
- Routes importate prima della definizione del blueprint

---

## Output Atteso

1. Tutti i file del modulo con contenuto completo
2. La modifica a `app.py` (sezione da aggiungere)
3. Checklist di verifica:
   - [ ] `url_prefix` usa kebab-case
   - [ ] `@before_request` presente con `LOCAL_DEV_BYPASS_AUTH` check
   - [ ] `routes.py` non contiene logica scientifica
   - [ ] `services` non importa Flask
   - [ ] Blueprint registrato in `app.py`
   - [ ] Template directory corrisponde al nome blueprint
   - [ ] Static folder obbedisce naming convention
