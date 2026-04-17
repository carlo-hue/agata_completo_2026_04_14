# AGATA – Admin RBAC / Workflow / Audit

**Argomenti:** `$ARGUMENTS` = `<tipo_intervento> <file_target> "<descrizione>"`

Tipo intervento: `add-protection | add-audit | add-role-check | add-scope-filter`

Esempio: `/agata-rbac add-protection agata/moduli/lightcurve/__init__.py "Proteggere il modulo lightcurve con ruolo analyst"`

---

## Contesto Progetto

**Sistema:** AGATA | RBAC multi-livello, multi-tenant, audit obbligatorio per azioni critiche

**Gerarchia ruoli:** `superuser(4) > admin(3) > reviewer(2) > analyst(1) > viewer(0)`

**Riferimento RBAC:** leggi `agata/moduli/admin/decorators.py` (intero file)

**Pattern @before_request:** leggi `agata/moduli/galassie_nane/__init__.py`

**Pattern audit_action:** leggi `agata/moduli/admin/decorators.py` (decorator `audit_action`)

---

## Interventi Disponibili

### `add-protection` – Aggiungere @before_request a un blueprint

Copia il pattern esatto da `galassie_nane/__init__.py`:
- `LOCAL_DEV_BYPASS_AUTH` check
- Static files bypass
- `is_authenticated` check → 401
- `is_active` check → 403
- Role check con `allowed_roles` set → 403

### `add-audit` – Aggiungere @audit_action a una route

```python
@audit_action('entity_action', 'entity_type')
def my_route():
    ...
```

Usa il decorator esistente in `agata/moduli/admin/decorators.py`.

`action` format: `'<entità>_<verbo>'` (es. `'project_state_changed'`, `'user_updated'`)

### `add-role-check` – Aggiungere @admin_required a una route specifica

```python
@admin_required('admin')   # admin o superuser
@admin_required('reviewer') # reviewer, admin, superuser
@admin_required('superuser') # solo superuser
```

### `add-scope-filter` – Aggiungere multi-tenant filtering a una query

```python
from agata.moduli.admin.decorators import get_scoped_association_id
association_id = get_scoped_association_id()
query = db.query(Model)
if association_id is not None:
    query = query.filter(Model.association_id == association_id)
```

Usa `get_scoped_association_id()` (None = superuser, vede tutto).

Usa `is_own_association(id)` per check accesso su singola entità.

---

## Regole Non Negoziabili

- **MAI** accesso diretto a `current_user.role == 'admin'` nelle route (usare decorators)
- `@before_request` per protezione blueprints completi (non `@login_required` su ogni route individuale del modulo)
- `@login_required` su route admin individuali (oltre a `@before_request` del blueprint)
- Audit log su: creazione, modifica stato, cancellazione di qualsiasi entità critica
- Multi-tenant: OGNI query su dati tenantizzati deve filtrare per `association_id`
- Superuser vede tutto (`association_id=None` da `get_scoped_association_id()`)

---

## Output Atteso

1. Codice da aggiungere/modificare (solo sezioni rilevanti)
2. Spiegazione del modello di sicurezza applicato
3. Verifica che non ci siano escalation di privilegi non intenzionali
4. Checklist:
   - [ ] Pattern copiato esatto (non reinventato)
   - [ ] LOCAL_DEV_BYPASS_AUTH presente (solo in @before_request)
   - [ ] Tutti i ruoli nella gerarchia considerati
   - [ ] Multi-tenant scope applicato alle query
   - [ ] Audit log su azioni critiche
   - [ ] Nessun hardcoded role check nelle route
