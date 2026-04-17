# Stars Catalog Data Flow - Come Mette Insieme i Dati

## Panoramica Funzione `stars_catalog_page()`

La funzione restituisce una **lista di stelle assegnate a un'associazione** con dati aggregati da 5 tabelle diverse. Ecco il flusso passo-passo:

---

## 🔍 FASE 1: Determinare Quale Dataset di Stelle Mostrare

### Step 1a: Ruolo dell'Utente
```python
is_superuser = current_user.role == 'superuser'  # Line 60
is_admin = current_user.role == 'admin'          # Line 61
is_analyst = current_user.role == 'analyst'      # Line 63
```

### Step 1b: Determinare `filter_association_id`
```python
filter_association_id = request.args.get('association_id', type=int)  # Line 66
if not is_superuser:
    filter_association_id = current_user.association_id  # Line 70 - forza propria associazione
```

### Step 1c: Decidere se caricare stelle
```python
should_load_stars = True
if is_superuser and not has_selected_filter:
    should_load_stars = False  # Line 90 - Superuser senza filtri non carica
```

**RISULTATO**: `filter_association_id` = associazione su cui filtrare

---

## 🗃️ FASE 2: Query Principale - Dati Fotometrici Base

### Se SUPERUSER (Line 122-178)
```python
# Caso A: filter_association_id IS SET (mostra stelle ASSEGNATE a quella associazione)
if filter_association_id:
    # Step 1: Get Gaia IDs assegnati
    assigned_gaia_ids = db.query(StarAssignment.gaia_id).filter(
        StarAssignment.association_id == filter_association_id
    ).all()  # Line 129-131

    # Step 2: Query fotometria per quei Gaia IDs
    stars_query = """
        SELECT DISTINCT
            ce.Source as gaia_id,
            COUNT(*) as total_points,
            COUNT(DISTINCT ce.catalogo) as num_catalogs,
            GROUP_CONCAT(DISTINCT ce.catalogo) as catalogs,
            MIN(ce.hjd) as min_hjd,
            MAX(ce.hjd) as max_hjd,
            MIN(ce.Vmag) as min_mag,
            MAX(ce.Vmag) as max_mag
        FROM Cataloghi_esterni ce
        WHERE ce.Source IN (gaia_ids_assegnati)
          AND (ce.association_id_owner IS NULL OR ce.association_id_owner = :filter_assoc_id)
        GROUP BY ce.Source
    """  # Line 139-155

# Caso B: filter_association_id IS NULL (mostra TUTTE le stelle del bacino centrale)
else:
    stars_query = """
        SELECT DISTINCT
            ce.Source as gaia_id,
            COUNT(*) as total_points,
            ...
        FROM Cataloghi_esterni ce
        WHERE ce.association_id_owner IS NULL  # Solo bacino centrale
        GROUP BY ce.Source
    """  # Line 162-177
```

### Se ADMIN/REVIEWER/ANALYST (Line 180-236)
```python
# Determina quali gaia_ids mostrare in base al ruolo
if is_analyst:
    # Analyst: mostra solo PROGETTI ASSEGNATI A LUI
    projects = db.query(Project).filter(
        Project.assigned_to == current_user.id,
        Project.association_id == filter_association_id,
        Project.state != 'cancelled'
    ).all()  # Line 198-202
    gaia_ids_assigned = set(p.gaia_id for p in projects)
else:
    # Admin/Reviewer: mostra TUTTE le stelle ASSEGNATE alla loro associazione
    assignments = db.query(StarAssignment).filter(
        StarAssignment.association_id == filter_association_id
    ).all()  # Line 206-208
    gaia_ids_assigned = set(a.gaia_id for a in assignments)

# Poi STESSA QUERY come superuser, ma filtra per propria associazione
stars_query = """
    SELECT DISTINCT
        ce.Source as gaia_id,
        COUNT(*) as total_points,
        ...
    FROM Cataloghi_esterni ce
    WHERE ce.Source IN (gaia_ids_assigned)
      AND (ce.association_id_owner IS NULL OR ce.association_id_owner = :filter_assoc_id)
    GROUP BY ce.Source
"""  # Line 217-233
```

**RISULTATO FASE 2**:
- `result` = lista di righe con (gaia_id, total_points, num_catalogs, catalogs, min_hjd, max_hjd, min_mag, max_mag)
- Dati raggruppati da **CATALOGHI_ESTERNI** per Source (Gaia ID)

---

## 🏗️ FASE 3: Build Cache Data Structures

Ora la funzione carica dati correlati in **CACHE** per evitare N+1 queries:

### Cache 1: Import Info (Line 245-301)
```python
import_cache = {}  # {gaia_id: {'ids': [...], 'info': {...}}}

# Step 1: Query quali import_ids associati a ogni stella
imports_data = db.execute("""
    SELECT Source, catalog_import_id
    FROM Cataloghi_esterni
    WHERE Source IN (all_gaia_ids) AND catalog_import_id IS NOT NULL
    GROUP BY Source, catalog_import_id
""")  # Line 250-259

# Step 2: Estrai import_ids univoci
import_ids_to_load = set()
for gaia_id_row, imp_id in imports_data:
    import_cache[str(gaia_id_row)] = {'ids': [imp_id], ...}
    import_ids_to_load.add(imp_id)  # Line 261-269

# Step 3: Load info per import (una volta sola!)
imports_info = db.execute("""
    SELECT id, search_type, search_value, created_at
    FROM agata_catalog_imports
    WHERE id IN (import_ids_to_load)
""")  # Line 277-284

# Step 4: Mappa info su cache
for imp_id in import_ids:
    import_info_map[imp_id] = {
        'id': imp_id,
        'search_type': search_type,
        'search_value': search_value,
        'created_at': created_at
    }  # Line 287-294

# Step 5: Popola cache con info
for gaia_id_key in import_cache:
    import_cache[gaia_id_key]['info'] = import_info_map[...]  # Line 296-301
```

**FLUSSO**: `Cataloghi_esterni.catalog_import_id` → `agata_catalog_imports`

### Cache 2: VAST Results (Line 303-339)
```python
vast_cache = {}  # {gaia_id: {variable_types: [...], is_known_variable: bool, catalog_matches: [...]}}

vast_results = db.execute("""
    SELECT
        gaia_source_id,
        GROUP_CONCAT(DISTINCT variable_type SEPARATOR ',') as variable_types,
        MAX(is_known_variable) as is_known_variable,
        GROUP_CONCAT(DISTINCT catalog_matches SEPARATOR ';') as all_catalog_matches
    FROM agata_vast_results
    WHERE gaia_source_id IN (all_gaia_ids)
      AND is_valid = TRUE
    GROUP BY gaia_source_id
""")  # Line 311-324

# Costruisci cache
for row in vast_results:
    vast_cache[str(row.gaia_source_id)] = {
        'variable_types': [...],
        'is_known_variable': bool(...),
        'catalog_matches': [...]
    }  # Line 326-336
```

**FLUSSO**: Gaia ID → `agata_vast_results`

### Cache 3: StarAssignment (Line 341-367)
```python
star_assignments_cache = {}  # {gaia_id: [StarAssignment, ...]}

# Batch query: carica TUTTI gli StarAssignment per gaia_ids
assignments_query = db.query(StarAssignment).filter(
    StarAssignment.gaia_id.in_(all_gaia_ids_str)
)

# Filter per propria associazione se non superuser
if not is_superuser:
    assignments_query = assignments_query.filter(
        StarAssignment.association_id == filter_association_id
    )  # Line 354-358

all_assignments = assignments_query.all()

# Costruisci cache
for assignment in all_assignments:
    gaia_id_str = str(assignment.gaia_id)
    star_assignments_cache[gaia_id_str] = [assignment, ...]  # Line 362-367
```

**FLUSSO**: Gaia ID → `agata_star_assignments`

### Cache 4: Projects (Line 369-387)
```python
projects_cache = {}  # {gaia_id: Project}

# Batch query: carica TUTTI i Project per gaia_ids
projects_query = db.query(Project).filter(
    Project.gaia_id.in_(all_gaia_ids_str),
    Project.state != 'cancelled'
)

# Filter per propria associazione se non superuser
if not is_superuser:
    projects_query = projects_query.filter(
        Project.association_id == filter_association_id
    )  # Line 375-379

all_projects = projects_query.all()

# Costruisci cache (1 per stella)
for project in all_projects:
    gaia_id_str = str(project.gaia_id)
    projects_cache[gaia_id_str] = project  # Line 383-387
```

**FLUSSO**: Gaia ID → `agata_projects`

---

## 🧩 FASE 4: Build Final Star Dict (Line 389-450)

Per ogni stella nel `result` principale, **assembla il dizionario finale** usando cache:

```python
for row in result:
    # Row contiene: gaia_id, total_points, num_catalogs, catalogs, min_hjd, max_hjd, min_mag, max_mag

    # Lookup #1: Catalogs (da row.catalogs split)
    catalogs_list = row.catalogs.split(',') if row.catalogs else []

    # Lookup #2: StarAssignment (da cache, NO QUERY)
    all_assignments = star_assignments_cache.get(str(row.gaia_id), [])

    # Lookup #3: Project (da cache, NO QUERY)
    project = projects_cache.get(str(row.gaia_id), None)

    # Lookup #4: Import info (da cache, NO QUERY)
    import_ids = import_cache.get(str(row.gaia_id), {}).get('ids', [])
    import_info = import_cache.get(str(row.gaia_id), {}).get('info')

    # Lookup #5: VAST data (da cache, NO QUERY)
    variable_types = vast_cache.get(str(row.gaia_id), {}).get('variable_types', [])
    is_known_variable = vast_cache.get(str(row.gaia_id), {}).get('is_known_variable', False)
    catalog_matches = vast_cache.get(str(row.gaia_id), {}).get('catalog_matches', [])

    # Assembla dict finale
    stars_raw.append({
        'gaia_id': row.gaia_id,
        'total_points': row.total_points,
        'num_catalogs': row.num_catalogs,
        'catalogs': catalogs_list,
        'min_hjd': row.min_hjd,
        'max_hjd': row.max_hjd,
        'min_mag': row.min_mag,
        'max_mag': row.max_mag,
        'last_data_date': row.last_data_date,
        'all_assignments': [
            {
                'id': a.id,
                'association_id': a.association_id,
                'association_name': a.association.name,  # ← SQLAlchemy lazy load
                'assigned_at': a.assigned_at.strftime('%Y-%m-%d')
            }
            for a in all_assignments
        ],
        'project_id': project.id if project else None,
        'project_code': project.project_code if project else None,
        'project_state': project.state if project else None,
        'project_association': project.association.name if project else None,  # ← SQLAlchemy lazy load
        'import_info': import_info,
        'import_ids': import_ids,
        'variable_types': variable_types,
        'is_known_variable': is_known_variable,
        'catalog_matches': catalog_matches,
        'can_create_project': can_create_project_logic,
        'can_self_assign': False
    })  # Line 415-450
```

**RISULTATO**: `stars_raw` = lista di dicts con TUTTI i dati aggregati

---

## 🔗 FASE 5: Apply Filters (Python-side!)

Dopo aver caricato TUTTO in memoria, applica filtri **IN PYTHON** (non SQL):

```python
# Filtro di stato
if state_filter == 'assigned':
    stars = [s for s in stars if s['all_assignments'] and not s['project_id']]

# Filtro per data
if date_filter == '24h':
    stars = [s for s in stars if s['import_ids'] and s['last_data_date'] >= cutoff_date]

# Filtro per catalogo
if catalog_filter:
    stars = [s for s in stars if catalog_filter in s['catalogs']]

# Filtro per variable_type
if variable_type_filter:
    stars = [s for s in stars if any(vt in s['variable_types'] for vt in selected_types)]

# Filtro per variabili note/non note
if variable_status_filter == 'known':
    stars = [s for s in stars if s['is_known_variable']]

# Ricerca Gaia ID
if gaia_search:
    stars = [s for s in stars if gaia_search in str(s['gaia_id'])]
```  # Line 453-528

---

## 📊 FASE 6: Sort & Paginate (Python-side!)

```python
# Ordinamento
if sort_by == 'gaia_id':
    stars = sorted(stars, key=lambda x: int(x['gaia_id']), reverse=reverse_order)
elif sort_by == 'points':
    stars = sorted(stars, key=lambda x: x['total_points'], reverse=reverse_order)
elif sort_by == 'catalogs':
    stars = sorted(stars, key=lambda x: x['num_catalogs'], reverse=reverse_order)
elif sort_by == 'date':
    stars = sorted(stars, key=sort_date_key, reverse=reverse_order)
# ... etc  # Line 530-575

# Paginazione
per_page = 50
total = len(stars)  # Numero TOTALE stelle
start_idx = (page - 1) * per_page
end_idx = start_idx + per_page
stars_paginated = stars[start_idx:end_idx]  # Mostra 50
```  # Line 593-598

---

## 📤 FASE 7: Return to Template

```python
return render_template(
    'admin/stars_catalog/list.html',
    stars=stars_paginated,                    # ← 50 stelle per pagina
    total_stars=total,                        # ← Numero totale
    available_catalogs=available_catalogs,
    available_imports=available_imports,
    available_variable_types=available_variable_types,
    filter_association_id=filter_association_id,
    state_filter=state_filter,
    # ... tutti i parametri filtri
)  # Line 611-636
```

---

## 📋 Query Sequence Summary

| Step | Tabella | Query Type | Quante | Risultato |
|------|---------|-----------|--------|-----------|
| 1 | agata_associations | SELECT (ORM) | 1 | Lista associazioni (solo superuser) |
| 2 | agata_star_assignments | SELECT (ORM) | 1 | Gaia IDs assegnati a associazione |
| 3 | **Cataloghi_esterni** | **SELECT GROUP BY** | **1** | **Base stars (fonte primaria!)** |
| 4 | Cataloghi_esterni | SELECT GROUP BY | 1 | Import IDs per stella |
| 5 | agata_catalog_imports | SELECT IN | 1 | Info import (search_type, created_at) |
| 6 | agata_vast_results | SELECT GROUP BY | 1 | VAST data (variable_type, is_known) |
| 7 | agata_star_assignments | SELECT IN (ORM) | 1 | **Batch StarAssignment** |
| 8 | agata_projects | SELECT IN (ORM) | 1 | **Batch Projects** |
| 9 | agata_catalog_imports (load2) | Query se non loaded | ~0-1 | Imports for dropdown |

**TOTAL**: ~9-10 query (batch optimized!)

---

## 🔴 Il Flusso REALE per Una Stella

Esempio: Stella Gaia ID = 5734104703954270464, Associazione = AstroGen

```
1. SUPERUSER/ADMIN navigates /admin/stars-catalog
   ↓
2. Query #1: SELECT * FROM agata_star_assignments
             WHERE association_id = 123 (AstroGen)
   → Finds: gaia_ids = [5734104703954270464, ...]
   ↓
3. Query #2 (GROUP BY Cataloghi_esterni):
   SELECT Source, COUNT(*), GROUP_CONCAT(catalogo)
   FROM Cataloghi_esterni
   WHERE Source IN (5734104703954270464, ...)
   GROUP BY Source
   → Returns: {gaia_id: 5734104703954270464,
              total_points: 948,
              catalogs: "TESS,ZTF,ASASSN"}
   ↓
4. Query #3 (Import IDs):
   SELECT Source, catalog_import_id
   FROM Cataloghi_esterni
   WHERE Source IN (5734104703954270464, ...)
     AND catalog_import_id IS NOT NULL
   GROUP BY Source, catalog_import_id
   → Returns: {5734104703954270464: [119, 123, 125]}
   ↓
5. Query #4 (Import Info):
   SELECT id, search_type, search_value, created_at
   FROM agata_catalog_imports
   WHERE id IN (119, 123, 125)
   → Returns: {119: {search_type: 'gaia_id', created_at: '2026-02-15 14:30'}}
   ↓
6. Query #5 (VAST Results):
   SELECT gaia_source_id, variable_type, is_known_variable
   FROM agata_vast_results
   WHERE gaia_source_id IN (5734104703954270464, ...)
   GROUP BY gaia_source_id
   → Returns: {5734104703954270464: {variable_types: ['RRab'], is_known: true}}
   ↓
7. Query #6 (StarAssignments BATCH):
   SELECT * FROM agata_star_assignments
   WHERE gaia_id IN (5734104703954270464, ...)
   → Finds: {5734104703954270464: [
       {id: 45, association_id: 123, assigned_at: '2025-11-20'}
     ]}
   ↓
8. Query #7 (Projects BATCH):
   SELECT * FROM agata_projects
   WHERE gaia_id IN (5734104703954270464, ...)
     AND state != 'cancelled'
   → Finds: {5734104703954270464:
       {id: 12, project_code: 'AGATA-2025-001', state: 'assigned', ...}
   }
   ↓
9. PYTHON ASSEMBLY:
   star_dict = {
     gaia_id: 5734104703954270464,
     total_points: 948,
     catalogs: ['TESS', 'ZTF', 'ASASSN'],
     all_assignments: [{id: 45, association_id: 123, ...}],
     project_id: 12,
     project_code: 'AGATA-2025-001',
     import_info: {id: 119, created_at: '2026-02-15 14:30'},
     variable_types: ['RRab'],
     is_known_variable: true,
     ...
   }
   ↓
10. PYTHON FILTERS: (non applicati a questa stella se soddisfa criteri)
    - state_filter: 'with_project' ✓ (ha project_id)
    - catalog_filter: 'TESS' ✓ (è in catalogs)
    - variable_type_filter: 'RRab' ✓ (è in variable_types)
   ↓
11. PAGINATION: Stella finisce nella pagina corrente se position in range
    ↓
12. RENDER: HTML mostra stella con tutti i dati aggregati
```

---

## 🎯 Conclusione: Come i Dati Sono Messi Insieme

| Aspetto | Come |
|---------|------|
| **Fotometria base** | GROUP BY Source da **Cataloghi_esterni** |
| **Assegnazioni** | da **agata_star_assignments** (batch query) |
| **Progetto** | da **agata_projects** (batch query) |
| **Import info** | da **agata_catalog_imports** (via catalog_import_id) |
| **VAST data** | da **agata_vast_results** (gaia_source_id match) |
| **Filtri** | Applicati **IN PYTHON** (dopo caricamento completo) |
| **Ordinamento** | IN PYTHON (sorted() su lista completa) |
| **Paginazione** | IN PYTHON (slice [0:50]) |

**Chiave**: I dati da 5 tabelle sono **assemblati in cache**, poi **filtrati/ordinati/paginati in Python** (non SQL).

---

**Generato**: 2026-02-19
**Scopo**: Comprendere il data flow di `stars_catalog_page()` dal punto di vista della funzione
