# Analisi Relazioni Database - AGATA Stars Catalog

## Problema Attuale

La schema del database ha relazioni logicamente confuse. Analizziamo il flusso dati reale dal codice `stars_catalog.py`:

---

## 1. CATALOGHI_ESTERNI (Bacino Centrale Fotometria)

### Analisi del Codice
```python
# Line 151-154: Query usa Source (Gaia ID) e association_id_owner
SELECT ce.Source as gaia_id
FROM Cataloghi_esterni ce
WHERE ce.Source IN (lista_gaia_ids)
  AND (ce.association_id_owner IS NULL OR ce.association_id_owner = :filter_assoc_id)
GROUP BY ce.Source
```

### Uso Attuale
- **Source** = Gaia DR3 ID (bigint, **NON ha PK**, raggruppato in query)
- **association_id_owner** = associazione proprietaria dei dati
- **catalog_import_id** = da QUALE import è venuta la riga

### Il Problema: `catalog_import_id`
```python
# Line 252-256: Recupera import_ids
SELECT Source, catalog_import_id
FROM Cataloghi_esterni
WHERE Source IN (lista) AND catalog_import_id IS NOT NULL
GROUP BY Source, catalog_import_id
```

**PROBLEMA LOGICO**: `catalog_import_id` è FK a `agata_catalog_imports` (id), MA:
- Una stella può essere importata da MULTIPLI import (stessa stella, catalogo diverso)
- `catalog_import_id` denormalizza "da quale import è venuto questo punto"
- **NON è una relazione 1:N stella→import**, è 1:1 per RIGA fotometrica

**SOLUZIONE**: Togliere `catalog_import_id` da schema ER (è implementation detail di tracciamento)

### Indici Corretti per CATALOGHI_ESTERNI
```sql
-- PRIMARY: Nessuno (è tabella log fotometrica, no PK)

-- Indici Necessari:
CREATE INDEX idx_cataloghi_esterni_source
  ON Cataloghi_esterni(Source);

CREATE INDEX idx_cataloghi_esterni_source_owner
  ON Cataloghi_esterni(Source, association_id_owner);

CREATE INDEX idx_cataloghi_esterni_catalog_import_id
  ON Cataloghi_esterni(catalog_import_id);  -- Per join a agata_catalog_imports
```

---

## 2. AGATA_STAR_ASSIGNMENTS (Assegnazione Stelle)

### Analisi del Codice
```python
# Line 206-209: Carica assegnazioni per associazione
assignments = db.query(StarAssignment).filter(
    StarAssignment.association_id == filter_association_id
).all()
gaia_ids_assigned = set(a.gaia_id for a in assignments)
```

### Schema Attuale
| Campo | Tipo | Ruolo |
|-------|------|-------|
| `id` | PK | Auto-increment |
| `gaia_id` | string | Gaia DR3 ID |
| `association_id` | FK | **Chiave composita con gaia_id** |
| `assigned_by` | FK | User che ha assegnato |
| `assigned_at` | timestamp | Quando |
| `project_id` | FK | Progetto creato da questa assegnazione |
| `notes` | text | Note |

### Chiave Logica
```sql
UNIQUE(gaia_id, association_id)  -- Una stella assegnata UNA VOLTA per associazione
```

**PROBLEMA**: Hai detto che `association_id` e `project_id` dovrebbero essere TOLTE.

**MA**: Analizziamo il flusso reale...

### Flusso Reale (dal codice)
```
1. SUPERUSER assegna stella a ASSOCIAZIONE
   → StarAssignment(gaia_id, association_id, assigned_by)

2. ADMIN vede stelle assegnate alla SUA associazione
   → SELECT ... WHERE association_id = :assoc_id

3. ADMIN crea PROGETTO da assegnazione
   → Project(gaia_id, association_id, assigned_to)
   → StarAssignment.project_id = project.id
```

**IL PUNTO CRITICO**: Guarda line 370-379:
```python
# Carica PROGETTI per stella
projects_query = db.query(Project).filter(
    Project.gaia_id.in_(all_gaia_ids_str),
    Project.state != 'cancelled'
)

if not is_superuser:
    # Admin/Analyst: filtra per propria associazione
    projects_query = projects_query.filter(
        Project.association_id == filter_association_id  # ← USA association_id DI PROJECT!
    )
```

**Quindi Project HA association_id**, non StarAssignment!

---

## 3. AGATA_PROJECTS (Progetti Workflow)

### Analisi del Codice
```python
# Line 370-379: Query per recuperare progetti
projects_query = db.query(Project).filter(
    Project.gaia_id.in_(all_gaia_ids_str),
    Project.state != 'cancelled'
).filter(
    Project.association_id == filter_association_id
)
```

### Schema Attuale
```
id (PK)
project_code (UK)
gaia_id (string) ← Stella
tic_id (int)
association_id (FK) ← L'ASSOCIAZIONE A CUI APPARTIENE IL PROGETTO
title, state, assigned_to, reviewed_by, ...
```

**CORRELAZIONE 1:1**:
- **1 stella** (gaia_id) → **1 progetto per associazione** (a causa UNIQUE constraint logico)
- Ma il codice non lo enforza esplicitamente

---

## 4. AGATA_CATALOG_IMPORTS (Tracciamento Importazioni)

### Analisi del Codice
```python
# Line 277-284: Carica info import
imports_info = db.execute(
    text(f"""
        SELECT id, search_type, search_value, created_at
        FROM agata_catalog_imports
        WHERE id IN ({import_placeholders})
    """),
    import_query_params
).fetchall()
```

### Schema Attuale
| Campo | Tipo | Ruolo |
|-------|------|-------|
| `id` | PK | - |
| `resolved_gaia_id` | string | Stella ricercata |
| `project_id` | FK | Project creato da questo import |
| `target_association_id` | FK | Associazione target |
| ... |

### Flusso (dal commento docstring)
```
1. Superuser/Admin cerca stella (pending → searching)
2. Sistema interroga cataloghi (searching → preview)
3. Preview risultati disponibili
4. Import selettivo (preview → importing → completed)
5. Creazione Project opzionale (link project_id)
```

**PROBLEMA LOGICO**:
- `project_id` = progetto creato da questo import
- `target_association_id` = associazione target per il progetto
- Ma il codice legge solo `id, search_type, search_value, created_at`
- **Il vero legame è**: Import → Popola Cataloghi_esterni → Stella → StarAssignment → Project

**RELAZIONE VERA**:
```
agata_catalog_imports
  ↓ populates (via catalog_import_id)
Cataloghi_esterni
  ↓ (raggruppato per Source/gaia_id)
Stella virtuale
  ↓ (StarAssignment crea assegnazione)
agata_star_assignments
  ↓ (admin crea project)
agata_projects
```

---

## Proposta di Correzione Schema ER

### Elimina (Non Sono Relazioni Dirette)

1. **`catalog_import_id` da CATALOGHI_ESTERNI schema ER**
   - È dettaglio di tracciamento (quale import→quale riga)
   - Può rimanere nel DB come colonna, ma NON come relazione nel ER diagram
   - Motivo: Molti-a-Molti non rappresentabile direttamente

2. **`association_id` da AGATA_STAR_ASSIGNMENTS schema ER**
   - NO ASPETTA! Vedi sotto...

3. **`project_id` da AGATA_STAR_ASSIGNMENTS schema ER**
   - Motivo: Relazione è STAR_ASSIGNMENT → crea → PROJECT
   - Meglio modellare come STAR_ASSIGNMENT ||--|| PROJECT

### Mantieni

1. **`association_id` in AGATA_PROJECTS** ✓
   - Essenziale per filtri admin ("mostra stelle della TUA associazione")

2. **`gaia_id` come chiave logica** ✓
   - Collega stelle virtuali tra tabelle

3. **`association_id` in AGATA_STAR_ASSIGNMENTS** ✓
   - Chiave composita (gaia_id, association_id)
   - Essenziale per query "stelle assegnate a questa associazione"

### Aggiungi Indici Mancanti

```sql
-- CATALOGHI_ESTERNI
CREATE INDEX idx_cataloghi_esterni_source
  ON Cataloghi_esterni(Source);  -- Per GROUP BY e WHERE Source IN

CREATE INDEX idx_cataloghi_esterni_source_owner
  ON Cataloghi_esterni(Source, association_id_owner);  -- Per filtri

CREATE UNIQUE INDEX uk_star_assignments_gaia_assoc
  ON agata_star_assignments(gaia_id, association_id);  -- Chiave composita

CREATE UNIQUE INDEX uk_project_gaia_assoc
  ON agata_projects(gaia_id, association_id);  -- 1 progetto per stella per associazione
```

---

## Relazioni Finali (ER Diagram Corretto)

```
ASSOCIATIONS
  ↓ ||--o{
PROJECTS (has association_id)

ASSOCIATIONS
  ↓ ||--o{
STAR_ASSIGNMENTS (has association_id)

STAR_ASSIGNMENTS
  ↓ ||--|| (uno-a-uno)
PROJECTS (via gaia_id + association_id)

CATALOG_IMPORTS
  ↓ (populates via catalog_import_id, NON in ER)
CATALOGHI_ESTERNI

CATALOGHI_ESTERNI
  ↓ (raggruppa per Source/gaia_id, NON relazione diretta)
STAR_ASSIGNMENTS (tramite gaia_id search)

STAR_ASSIGNMENTS
  ↓ can-become (logica)
PROJECTS (Admin crea Project da Assignment)
```

---

## Correzioni Necessarie su ER_DIAGRAM_WITH_FIELDS.md

### Tolti
1. Relazione diretta `CATALOG_IMPORTS → CATALOGHI_ESTERNI` (rimani, ma agnota come "denormalized tracking")
2. `catalog_import_id` field da CATALOGHI_ESTERNI

### Aggiunti
1. Vincolo UNIQUE su STAR_ASSIGNMENTS: `(gaia_id, association_id)`
2. Vincolo UNIQUE su PROJECTS (logico): `(gaia_id, association_id)`
3. Indici PRIMARY: `Source` di CATALOGHI_ESTERNI (o almeno INDEX)

### Chiariti
1. CATALOGHI_ESTERNI: "Bacino centrale fotometria, raggruppa per Source (gaia_id)"
2. STAR_ASSIGNMENTS: "Assegnazione stella a associazione, chiave composita"
3. PROJECTS: "Uno per stella per associazione"

---

## Riepilogo Risposte

**Tu hai detto:**
- ❌ "agata_star_assignments ha gaia_id come chiave e association_id come chiave e project_id come chiave esterna"
  - **GIUSTO**: (gaia_id, association_id) è chiave logica
  - **SBAGLIATO**: project_id NON dovrebbe stare qui
  - **SOLUZIONE**: Relazione è STAR_ASSIGNMENT (created_from/becomes) PROJECT

- ✅ "agata_projects ha id PK con indice e non deve avere association_id"
  - **SBAGLIATO**: association_id DEVE stare qui per filtri admin
  - **SOLUZIONE**: Mantieni association_id in PROJECTS

- ✓ "Cataloghi_esterni dove c'è la chiave catalog_import_id non va bene e deve essere tolta"
  - **PARZIALMENTE VERO**: Togliere da RELAZIONE nel ER diagram
  - **MANTIENERE**: Come colonna nel DB per tracciamento

- ✓ "deve avere un indice su Source (che è il gaia_id)"
  - **CORRETTO**: PRIMARY INDEX su Source (o almeno INDEX)

---

**Generato**: 2026-02-19
**Basato su**: Analisi stars_catalog.py (1100+ linee)
**Stato**: Ready per correggere ER_DIAGRAM_WITH_FIELDS.md
