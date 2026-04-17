# AGATA – Integra Nuovo Catalogo Esterno

**Argomenti:** `$ARGUMENTS` = `<nome_catalogo> "<URL base API>" "<descrizione breve>"`

Esempio: `/agata-new-catalog vizier "https://vizier.cds.unistra.fr/TAPVizieR/tap" "Query cataloghi CDS via TAP"`

---

## Contesto Progetto

**Sistema:** AGATA | Cataloghi esterni via admin module

**Pattern di riferimento obbligatorio:** leggi `agata/moduli/admin/routes/catalogs/asassn.py` (struttura completa)

**Pattern servizi comuni:** leggi `agata/moduli/admin/routes/catalogs/__init__.py` (come sono registrati i catalogs)

**Frontend pattern:** leggi `agata/moduli/variable_stars/static/js/variable_stars/import_catalogs.js` (workflow UI con preview + confirm)

---

## File da Creare

### 1. Route file: `agata/moduli/admin/routes/catalogs/<nome_catalogo>.py`

Struttura obbligatoria:
- Header docstring con: nome catalogo, URL API, workflow step-by-step, caratteristiche (bande, cadenza, copertura)
- Costanti di configurazione (TIMEOUT per ogni fase, URL primari/fallback)
- Import da decorators: `from agata.moduli.admin.decorators import admin_required`
- Endpoint auto-flow: `POST /api/catalogs/<nome>/auto/search-data` (Step 1: preview) e `POST /api/catalogs/<nome>/auto/download-data` (Step 2: confirm)
- Separazione in due step (search preview + confirm download)
- Timeout espliciti per ogni chiamata HTTP esterna
- Fallback URL se API ha endpoint primario/secondario
- HTTP 502 per errori servizi esterni, 422 per validazione input

### 2. Modifica `agata/moduli/admin/routes/catalogs/__init__.py`:

Aggiungi:
```python
from . import <nome_catalogo>
```

E aggiorna la docstring con la descrizione del nuovo catalogo.

---

## Regole Non Negoziabili

- Timeout configurabili via costanti (NON hardcoded in `requests.get`)
- `try/except requests.exceptions.Timeout` separato da altri errori
- HTTP 502 per errori servizi esterni, 422 per validazione input
- Ogni endpoint decorato con `@login_required` e `@admin_required('analyst')`
- Nessuna logica di business scientifica nella route — creare service se necessario
- `logger = logging.getLogger(__name__)` a livello di modulo
- Endpoint deve tornare JSON con struttura: `{"data": [...], "preview": {...}, "stats": {...}}`

---

## Output Atteso

1. File route completo con tutti gli endpoint (search-data + download-data)
2. Modifica a `__init__.py` dei catalogs
3. Se la logica è complessa: proposta di un service file in `agata/moduli/admin/services/<nome>_service.py`
4. Snippet JS da aggiungere a `import_catalogs.js` per la UI (pattern: `search<NomeCatalogo>()/display<NomeCatalogo>Results()/execute<NomeCatalogo>Import()`)
5. Checklist:
   - [ ] Timeout espliciti per ogni fase
   - [ ] Due endpoint (search + download)
   - [ ] Registrato in `catalogs/__init__.py`
   - [ ] Snippet JS dispatcher nel `searchImportCatalogs()`
   - [ ] Response JSON con "data", "preview", "stats"
   - [ ] Gestione errori timeout e rete separata
