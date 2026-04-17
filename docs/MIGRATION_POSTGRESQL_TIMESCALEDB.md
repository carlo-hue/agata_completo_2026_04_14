# Piano di Migrazione: MySQL → PostgreSQL + TimescaleDB

**Versione documento**: 1.0  
**Data**: 2026-04-05  
**Applicazione**: AGATA v2.14.x  
**Obiettivo**: Ridurre spazio su disco (-90% per dati fotometrici), migliorare velocità query time series, eliminare cache manuale tramite Continuous Aggregates

In fondo al file il piano e le considerazioni per migrare
---

## Indice

1. [Motivazione e benefici attesi](#1-motivazione-e-benefici-attesi)
2. [Analisi del codebase attuale](#2-analisi-del-codebase-attuale)
3. [Equivalenze MySQL → PostgreSQL](#3-equivalenze-mysql--postgresql)
4. [Schema PostgreSQL + TimescaleDB](#4-schema-postgresql--timescaledb)
5. [Modifiche al codice Python — file per file](#5-modifiche-al-codice-python--file-per-file)
6. [Migrazione dati con pgloader](#6-migrazione-dati-con-pgloader)
7. [Setup infrastruttura](#7-setup-infrastruttura)
8. [Piano di esecuzione — 4 settimane](#8-piano-di-esecuzione--4-settimane)
9. [Checklist di verifica](#9-checklist-di-verifica)
10. [Rollback plan](#10-rollback-plan)

---

## 1. Motivazione e benefici attesi

### Il problema

La tabella `agata_star_photometry` è il bacino centrale di tutti i dati fotometrici da TESS, ZTF, ASAS-SN, OGLE, VAST. Schema attuale:

```sql
-- MySQL (attuale)
agata_star_photometry:
  index                BIGINT       -- opzionale, spesso NULL
  hjd                  DOUBLE       -- HJD timestamp, 100% present
  Vmag                 DOUBLE       -- magnitudine, 100% present
  Source               BIGINT       -- Gaia DR3 ID, 100% present
  catalogo             TEXT         -- 'TESS', 'ZTF', 'ASAS-SN', ecc.
  association_id_owner INT          -- sparse, ~1% non-null
  catalog_import_id    INT          -- ~80% present
```

Volume tipico: 10.000–100.000 righe per stella. Con migliaia di stelle, la tabella può raggiungere centinaia di milioni di righe senza alcuna compressione o partizionamento.

### Benefici di PostgreSQL + TimescaleDB

| Metrica | MySQL attuale | TimescaleDB | Miglioramento |
|---------|---------------|-------------|---------------|
| Spazio per 1M righe | ~80 MB | ~6-8 MB | **-92%** |
| Spazio per 50M righe | ~4 GB | ~300-400 MB | **-92%** |
| Query `WHERE source_id = :id` (hot path) | 15-40 ms | 10-25 ms | -35% |
| Query `WHERE hjd BETWEEN t1 AND t2` | full scan | chunk pruning | **-80-95%** |
| Aggregazioni (min/max/count per stella) | 20-80 ms | ~1 ms (continuous aggregate) | **-99%** |
| Bulk INSERT (pipeline import, 10k righe) | ~500 ms | ~400 ms | -20% |

**Benefici architetturali aggiuntivi**:
- I **Continuous Aggregates** sostituiscono la cache manuale `agata_star` per la parte fotometrica: non serve più l'hook sincronico in `upsert_star()` che ricalcola COUNT/MIN/MAX dopo ogni import.
- La funzione `time_bucket()` di TimescaleDB consente downsampling nativo per preview UI, senza tabelle accessorie.
- La compressione è **automatica per policy** (dati > 30 giorni compressi automaticamente) — zero manutenzione.

---

## 2. Analisi del codebase attuale

### Dimensioni del refactoring

| Elemento | Quantità |
|----------|----------|
| Tabelle nel database | 22 |
| File Python con SQL raw (`text()`) | 39 |
| Istanze totali `text(...)` nel codebase | 108 |
| Funzioni MySQL-specific da convertire | 35+ occorrenze in 12 file |
| File che referenziano `agata_star_photometry` | 26 |
| Modelli SQLAlchemy ORM dichiarativi | 23 |
| File SQL di migration | 11 |

### Dipendenza MySQL

`requirements.txt` — da rimuovere/sostituire:
```
PyMySQL==1.1.2  →  psycopg[binary]>=3.2.0
```

`agata/db.py` — il motore SQLAlchemy usa già `future=True` (SQLAlchemy 2.0): la migrazione del driver è minimale.

---

## 3. Equivalenze MySQL → PostgreSQL

Tutte le funzioni MySQL-specific presenti nel codebase con la loro traduzione esatta.

### 3.1 GROUP_CONCAT → STRING_AGG / ARRAY_TO_STRING

**Occorrenze**: `stars.py:31`, `star_service.py:40`, `catalog_common_service.py:625`, `catalog_import_service.py:815`, `stars_catalog.py:50,363`, `vast_service.py:2219,2224`

```sql
-- MySQL (da)
GROUP_CONCAT(DISTINCT catalogo ORDER BY catalogo SEPARATOR ',')

-- PostgreSQL (a)
-- Opzione A: se l'ordine non è critico (raccomandato, più semplice)
STRING_AGG(DISTINCT catalogo, ',')

-- Opzione B: se l'ordine alfabetico è necessario
ARRAY_TO_STRING(ARRAY(SELECT DISTINCT unnest(ARRAY_AGG(catalogo)) ORDER BY 1), ',')

-- Opzione C (più leggibile, subquery):
(SELECT STRING_AGG(c, ',' ORDER BY c)
 FROM (SELECT DISTINCT catalogo AS c FROM agata_star_photometry WHERE source_id = :id) sub)
```

**Nota**: `GROUP_CONCAT` con `ORDER BY` dentro `DISTINCT` non è supportato in PostgreSQL. Usare la Opzione B o C dove l'ordinamento è semanticamente rilevante (es. display nella UI). Per i campi `catalogs` in `agata_star` l'ordine non è critico — usare Opzione A.

```sql
-- MySQL (da) — stars_catalog.py:363 (GROUP_CONCAT con CONCAT e SEPARATOR '|')
GROUP_CONCAT(
    CONCAT(sa.id, ':', sa.association_id, ':', a.name, ':', DATE(sa.assigned_at))
    ORDER BY sa.assigned_at
    SEPARATOR '|'
)

-- PostgreSQL (a)
STRING_AGG(
    sa.id || ':' || sa.association_id || ':' || a.name || ':' || DATE(sa.assigned_at)::TEXT,
    '|'
    ORDER BY sa.assigned_at
)
```

```sql
-- MySQL (da) — vast_service.py:2219 (GROUP_CONCAT in subquery UPDATE)
SELECT GROUP_CONCAT(DISTINCT variable_type SEPARATOR ',')
FROM agata_vast_results
WHERE CAST(gaia_source_id AS CHAR) = :gid AND is_valid = 1

-- PostgreSQL (a)
SELECT STRING_AGG(DISTINCT variable_type, ',')
FROM agata_vast_results
WHERE gaia_source_id::TEXT = :gid AND is_valid = 1
```

### 3.2 ON DUPLICATE KEY UPDATE → INSERT ... ON CONFLICT DO UPDATE

**Occorrenze**: `stars.py:65`, `star_service.py:73`, `catalog_common_service.py:644`, `catalog_import_service.py:834`, `stars_catalog.py:881,1227`, `projects.py:842`, `tpf/save_service.py:289`

**Prerequisito**: PostgreSQL richiede un vincolo `UNIQUE` o `PRIMARY KEY` esplicito sulla colonna di conflitto. La tabella `agata_star` deve avere `UNIQUE(gaia_id)`.

```sql
-- MySQL (da) — pattern ricorrente in stars.py, star_service.py, catalog services
INSERT INTO agata_star
    (gaia_id, total_points, num_catalogs, catalogs, ...)
VALUES
    (:gaia_id, :total_points, ...)
ON DUPLICATE KEY UPDATE
    total_points     = VALUES(total_points),
    num_catalogs     = VALUES(num_catalogs),
    catalogs         = VALUES(catalogs),
    ...
    updated_at       = NOW()

-- PostgreSQL (a)
INSERT INTO agata_star
    (gaia_id, total_points, num_catalogs, catalogs, ...)
VALUES
    (:gaia_id, :total_points, ...)
ON CONFLICT (gaia_id) DO UPDATE SET
    total_points     = EXCLUDED.total_points,
    num_catalogs     = EXCLUDED.num_catalogs,
    catalogs         = EXCLUDED.catalogs,
    ...
    updated_at       = NOW()
```

```sql
-- MySQL (da) — stars_catalog.py:881, projects.py:842 (pattern con subquery)
INSERT INTO agata_star (gaia_id, num_assignments, created_at, updated_at)
VALUES (:gid, 1, NOW(), NOW())
ON DUPLICATE KEY UPDATE
    num_assignments = (SELECT COUNT(*) FROM agata_star_assignments WHERE gaia_id = :gid),
    updated_at = NOW()

-- PostgreSQL (a)
INSERT INTO agata_star (gaia_id, num_assignments, created_at, updated_at)
VALUES (:gid, 1, NOW(), NOW())
ON CONFLICT (gaia_id) DO UPDATE SET
    num_assignments = (SELECT COUNT(*) FROM agata_star_assignments WHERE gaia_id = :gid),
    updated_at = NOW()
```

```sql
-- MySQL (da) — tpf/save_service.py:289 (tabella TPF dinamica)
INSERT INTO {TPF_STAR_TABLE}
    (gaia_id, total_points, num_catalogs, catalogs, ...)
VALUES (...)
ON DUPLICATE KEY UPDATE
    total_points = VALUES(total_points),
    ...

-- PostgreSQL (a)
INSERT INTO {TPF_STAR_TABLE}
    (gaia_id, total_points, num_catalogs, catalogs, ...)
VALUES (...)
ON CONFLICT (gaia_id) DO UPDATE SET
    total_points = EXCLUDED.total_points,
    ...
```

### 3.3 FIND_IN_SET → ANY con STRING_TO_ARRAY

**Occorrenze**: `stars_catalog.py:138,141,309,317`

```sql
-- MySQL (da) — stars_catalog.py:138 (filtri avanzati, dinamico)
FIND_IN_SET(:pname, COALESCE(col_sql, '')) > 0
-- es: FIND_IN_SET(:catalog_filter, s.catalogs) > 0

-- PostgreSQL (a)
:pname = ANY(STRING_TO_ARRAY(COALESCE(col_sql, ''), ','))
-- es: :catalog_filter = ANY(STRING_TO_ARRAY(COALESCE(s.catalogs, ''), ','))
```

```sql
-- MySQL (da) — stars_catalog.py:141 (negazione)
FIND_IN_SET(:pname, COALESCE(col_sql, '')) = 0

-- PostgreSQL (a)
NOT (:pname = ANY(STRING_TO_ARRAY(COALESCE(col_sql, ''), ',')))
```

**Nota architetturale**: Considerare la migrazione della colonna `catalogs` in `agata_star` da `VARCHAR` (lista CSV) a `TEXT[]` (array PostgreSQL nativo). Questo renderebbe i filtri più naturali:
```sql
-- Con colonna array nativa
:catalog_filter = ANY(s.catalogs)
-- Invece di STRING_TO_ARRAY ogni volta
```
Questa è un'ottimizzazione facoltativa — richiede aggiornamento anche di tutti i INSERT/UPDATE su `agata_star.catalogs`.

### 3.4 CAST(col AS CHAR/UNSIGNED) → cast PostgreSQL

**Occorrenze**: `stars_catalog.py:262,329,1460`, `ztf_survey_service.py:900`, `vast_service.py:2216`

```sql
-- MySQL (da)
CAST(Source AS CHAR)
CAST(s.gaia_id AS UNSIGNED)
CAST(gaia_source_id AS CHAR)

-- PostgreSQL (a)
Source::TEXT           -- o CAST(Source AS TEXT)
s.gaia_id::BIGINT      -- o CAST(s.gaia_id AS BIGINT)
gaia_source_id::TEXT
```

### 3.5 COLLATE utf8mb4_unicode_ci → rimuovere

**Occorrenze**: `stars_catalog.py:261-262`

```sql
-- MySQL (da)
s.gaia_id COLLATE utf8mb4_unicode_ci IN (
    SELECT CAST(Source AS CHAR) COLLATE utf8mb4_unicode_ci
    FROM agata_star_photometry
    WHERE catalog_import_id = :import_filter_id
)

-- PostgreSQL (a) — COLLATE non necessario, PostgreSQL usa locale DB
s.gaia_id IN (
    SELECT source_id::TEXT
    FROM agata_star_photometry
    WHERE catalog_import_id = :import_filter_id
)
```

### 3.6 DATE_SUB → interval PostgreSQL

**Occorrenze**: `stars_catalog.py:304-305`

```sql
-- MySQL (da)
s.last_imported_at >= DATE_SUB(NOW(), INTERVAL 1 DAY)
s.last_imported_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)

-- PostgreSQL (a)
s.last_imported_at >= NOW() - INTERVAL '1 day'
s.last_imported_at >= NOW() - INTERVAL '7 days'
```

### 3.7 IFNULL → COALESCE (già usato in codebase)

**Occorrenze**: `vast_service.py:2214`

```sql
-- MySQL (da)
IFNULL(expr, default)

-- PostgreSQL (a) — COALESCE è già usato in altre parti del codebase
COALESCE(expr, default)
```

### 3.8 IF(cond, a, b) → CASE WHEN

Se presente nel codebase:

```sql
-- MySQL (da)
IF(s.is_superuser = 1, 'all', 'mine')

-- PostgreSQL (a)
CASE WHEN s.is_superuser = 1 THEN 'all' ELSE 'mine' END
```

### 3.9 AUTO_INCREMENT → SERIAL (migration SQL)

Nei file `docs/migrations/*.sql`:

```sql
-- MySQL (da)
id INT AUTO_INCREMENT PRIMARY KEY,

-- PostgreSQL (a)
id SERIAL PRIMARY KEY,
-- oppure (forma moderna):
id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
```

### 3.10 ENGINE e CHARSET → rimuovere

```sql
-- MySQL (da)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- PostgreSQL (a) — semplicemente:
);
```

### 3.11 ENUM → VARCHAR con CHECK CONSTRAINT

PostgreSQL supporta `ENUM` tramite tipi custom, ma la pratica comune è usare `VARCHAR` con `CHECK`:

```sql
-- MySQL (da)
state ENUM('pending','downloading','completed','failed') NOT NULL

-- PostgreSQL (a)
state VARCHAR(50) NOT NULL CHECK (state IN ('pending','downloading','completed','failed'))
-- oppure creare un tipo ENUM:
CREATE TYPE job_state AS ENUM ('pending','downloading','completed','failed');
state job_state NOT NULL
```

La seconda opzione è più robusta — creare un tipo per ogni ENUM significativo.

### 3.12 TINYINT → SMALLINT o BOOLEAN

```sql
-- MySQL (da)
is_valid TINYINT(1)
progress_pct TINYINT

-- PostgreSQL (a)
is_valid BOOLEAN
progress_pct SMALLINT
```

### 3.13 NOW() → NOW() (compatibile) / CURRENT_TIMESTAMP

```sql
-- MySQL e PostgreSQL: NOW() funziona uguale
-- CURRENT_TIMESTAMP funziona uguale
-- Nessuna modifica necessaria
```

---

## 4. Schema PostgreSQL + TimescaleDB

### 4.1 Tabella `agata_star_photometry` come Hypertable

```sql
-- ============================================================
-- FILE: docs/migrations/pg_001_agata_star_photometry.sql
-- ============================================================

-- Assicurarsi che l'estensione TimescaleDB sia installata
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Crea la tabella (schema identico al MySQL ma con tipi PostgreSQL)
CREATE TABLE IF NOT EXISTS agata_star_photometry (
    hjd                  DOUBLE PRECISION NOT NULL,
    vmag                 DOUBLE PRECISION,
    source_id            BIGINT NOT NULL,
    catalogo             VARCHAR(100) NOT NULL DEFAULT '',
    association_id_owner INTEGER REFERENCES agata_associations(id),
    catalog_import_id    INTEGER REFERENCES agata_catalog_imports(id)
    -- NOTA: colonna 'index' rimossa — era opzionale e mai usata nelle query critiche
);

-- NOTA sui nomi colonne:
--   Source → source_id    (snake_case, convenzione PostgreSQL)
--   Vmag   → vmag         (lowercase)
-- Richiede aggiornamento di tutte le query Python (find/replace globale)

-- Converti in Hypertable partizionata su hjd
-- chunk_time_interval = 30.0 giorni di HJD
SELECT create_hypertable(
    'agata_star_photometry',
    'hjd',
    chunk_time_interval => 30.0,
    if_not_exists => TRUE
);

-- Indice primario per hot path: WHERE source_id = :id
CREATE INDEX idx_phot_source_hjd ON agata_star_photometry (source_id, hjd DESC);

-- Indice per query admin: WHERE catalog_import_id = :id
CREATE INDEX idx_phot_import ON agata_star_photometry (catalog_import_id);

-- Indice per query owner: WHERE association_id_owner = :id
CREATE INDEX idx_phot_owner ON agata_star_photometry (association_id_owner);

-- ============================================================
-- COMPRESSIONE COLUMNAR
-- ============================================================

-- Abilita compressione
ALTER TABLE agata_star_photometry SET (
    timescaledb.compress = TRUE,
    timescaledb.compress_orderby = 'hjd DESC',
    timescaledb.compress_segmentby = 'source_id, catalogo'
);

-- Policy automatica: comprimi i chunk più vecchi di 30 giorni
SELECT add_compression_policy(
    'agata_star_photometry',
    compress_after => 30.0::DOUBLE PRECISION,
    if_not_exists => TRUE
);

-- ============================================================
-- CONTINUOUS AGGREGATE (sostituisce cache manuale agata_star
-- per la parte fotometrica)
-- ============================================================

CREATE MATERIALIZED VIEW phot_star_summary
WITH (timescaledb.continuous) AS
SELECT
    source_id,
    catalogo,
    COUNT(*)              AS n_points,
    MIN(hjd)              AS min_hjd,
    MAX(hjd)              AS max_hjd,
    MIN(vmag)             AS min_vmag,
    MAX(vmag)             AS max_vmag
FROM agata_star_photometry
GROUP BY source_id, catalogo;

-- Aggiornamento automatico ogni ora
SELECT add_continuous_aggregate_policy(
    'phot_star_summary',
    start_offset => 3.0::DOUBLE PRECISION,   -- HJD offset (3 giorni)
    end_offset   => (1.0/24.0)::DOUBLE PRECISION,  -- 1 ora
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);
```

### 4.2 Conversione migration SQL per le altre tabelle

Esempio di conversione del file `001_create_vast_tables.sql`:

```sql
-- MySQL originale (da)
CREATE TABLE IF NOT EXISTS agata_vast_jobs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    state ENUM('pending','downloading','vast_analysis','completed','failed') NOT NULL,
    progress_pct TINYINT DEFAULT 0 NOT NULL,
    is_valid TINYINT(1) DEFAULT 1,
    ...
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- PostgreSQL (a)
CREATE TYPE vast_job_state AS ENUM (
    'pending','downloading','validating','vast_analysis',
    'uploading','completed','failed','cancelled'
);

CREATE TABLE IF NOT EXISTS agata_vast_jobs (
    id SERIAL PRIMARY KEY,
    state vast_job_state NOT NULL DEFAULT 'pending',
    progress_pct SMALLINT DEFAULT 0 NOT NULL,
    is_valid BOOLEAN DEFAULT TRUE,
    ...
    -- ENGINE e CHARSET rimossi
);
```

Applicare lo stesso pattern a tutti gli 11 file in `docs/migrations/`.

---

## 5. Modifiche al codice Python — file per file

### Priorità P0 — Critici, Settimana 1

#### `agata/core/db/handlers/stars.py` (linee 27-87)

Contiene il pattern `upsert_star` con `GROUP_CONCAT` + `ON DUPLICATE KEY UPDATE`.

```python
# DA (MySQL):
row = db.execute(text("""
    SELECT
        COUNT(*) as total_points,
        COUNT(DISTINCT catalogo) as num_catalogs,
        GROUP_CONCAT(DISTINCT catalogo ORDER BY catalogo SEPARATOR ',') as catalogs,
        MIN(hjd) as min_hjd,
        MAX(hjd) as max_hjd,
        MIN(Vmag) as min_mag,
        MAX(Vmag) as max_mag,
        MAX(catalog_import_id) as latest_import_id
    FROM agata_star_photometry
    WHERE Source = :gaia_id_int
    GROUP BY Source
"""), {'gaia_id_int': gaia_id_int}).fetchone()

# A (PostgreSQL):
row = db.execute(text("""
    SELECT
        COUNT(*)                     AS total_points,
        COUNT(DISTINCT catalogo)     AS num_catalogs,
        STRING_AGG(DISTINCT catalogo, ',') AS catalogs,
        MIN(hjd)                     AS min_hjd,
        MAX(hjd)                     AS max_hjd,
        MIN(vmag)                    AS min_mag,
        MAX(vmag)                    AS max_mag,
        MAX(catalog_import_id)       AS latest_import_id
    FROM agata_star_photometry
    WHERE source_id = :gaia_id_int
    GROUP BY source_id
"""), {'gaia_id_int': gaia_id_int}).fetchone()
```

```python
# DA (MySQL) — ON DUPLICATE KEY UPDATE:
db.execute(text("""
    INSERT INTO agata_star
        (gaia_id, total_points, num_catalogs, catalogs, ...)
    VALUES (:gaia_id, ...)
    ON DUPLICATE KEY UPDATE
        total_points     = VALUES(total_points),
        ...
        updated_at       = NOW()
"""), {...})

# A (PostgreSQL) — ON CONFLICT DO UPDATE:
db.execute(text("""
    INSERT INTO agata_star
        (gaia_id, total_points, num_catalogs, catalogs, ...)
    VALUES (:gaia_id, ...)
    ON CONFLICT (gaia_id) DO UPDATE SET
        total_points     = EXCLUDED.total_points,
        num_catalogs     = EXCLUDED.num_catalogs,
        catalogs         = EXCLUDED.catalogs,
        min_hjd          = EXCLUDED.min_hjd,
        max_hjd          = EXCLUDED.max_hjd,
        min_mag          = EXCLUDED.min_mag,
        max_mag          = EXCLUDED.max_mag,
        latest_import_id = EXCLUDED.latest_import_id,
        last_imported_at = EXCLUDED.last_imported_at,
        updated_at       = NOW()
"""), {...})
```

**Stesso pattern** identico in `agata/moduli/admin/services/star_service.py` (linee 36-97) e in `catalog_common_service.py` (linee 621-654) e `catalog_import_service.py` (linee 811-856) — applicare la stessa conversione.

---

#### `agata/moduli/admin/routes/stars_catalog.py` — 45 occorrenze totali

**[1] Filtri avanzati — `build_adv_filter_clauses()` (linee 137-141)**:

```python
# DA (MySQL):
if op == 'contains' and col_type == 'csv_set':
    clauses.append(f"FIND_IN_SET(:{pname}, COALESCE({col_sql}, '')) > 0")

if op == 'not_contains' and col_type == 'csv_set':
    clauses.append(f"FIND_IN_SET(:{pname}, COALESCE({col_sql}, '')) = 0")

# A (PostgreSQL):
if op == 'contains' and col_type == 'csv_set':
    clauses.append(f":{pname} = ANY(STRING_TO_ARRAY(COALESCE({col_sql}, ''), ','))")

if op == 'not_contains' and col_type == 'csv_set':
    clauses.append(f"NOT (:{pname} = ANY(STRING_TO_ARRAY(COALESCE({col_sql}, ''), ',')))")
```

**[2] Import filter subquery (linee 261-266)**:

```python
# DA (MySQL):
import_gaia_subquery = """
    AND s.gaia_id COLLATE utf8mb4_unicode_ci IN (
        SELECT CAST(Source AS CHAR) COLLATE utf8mb4_unicode_ci
        FROM agata_star_photometry
        WHERE catalog_import_id = :import_filter_id
    )
"""

# A (PostgreSQL):
import_gaia_subquery = """
    AND s.gaia_id IN (
        SELECT source_id::TEXT
        FROM agata_star_photometry
        WHERE catalog_import_id = :import_filter_id
    )
"""
```

**[3] Catalog e variable_type filter (linee 309, 317)**:

```python
# DA (MySQL):
catalog_clause = ("FIND_IN_SET(:catalog_filter, s.catalogs) > 0"
                  if catalog_filter else "1=1")
vtype_clause = ("FIND_IN_SET(:variable_type_filter, COALESCE(s.variable_types,'')) > 0"
                if variable_type_filter else "1=1")

# A (PostgreSQL):
catalog_clause = (":catalog_filter = ANY(STRING_TO_ARRAY(COALESCE(s.catalogs, ''), ','))"
                  if catalog_filter else "TRUE")
vtype_clause = (":variable_type_filter = ANY(STRING_TO_ARRAY(COALESCE(s.variable_types, ''), ','))"
                if variable_type_filter else "TRUE")
```

**[4] Sort map — CAST AS UNSIGNED (linea 329)**:

```python
# DA (MySQL):
sort_map = {
    'gaia_id': f"CAST(s.gaia_id AS UNSIGNED) {sort_dir}",
    ...
}

# A (PostgreSQL):
sort_map = {
    'gaia_id': f"s.gaia_id::BIGINT {sort_dir}",
    ...
}
```

**[5] GROUP_CONCAT nella SELECT principale (linee 363-373)**:

```python
# DA (MySQL):
"""
(
    SELECT GROUP_CONCAT(
        CONCAT(sa.id, ':', sa.association_id, ':',
               a.name, ':', DATE(sa.assigned_at))
        ORDER BY sa.assigned_at
        SEPARATOR '|'
    )
    FROM agata_star_assignments sa
    JOIN agata_associations a ON a.id = sa.association_id
    WHERE sa.gaia_id = s.gaia_id
      AND (:filter_assoc_id IS NULL OR sa.association_id = :filter_assoc_id)
) AS assignments_packed,
"""

# A (PostgreSQL):
"""
(
    SELECT STRING_AGG(
        sa.id::TEXT || ':' || sa.association_id::TEXT || ':' ||
        a.name || ':' || DATE(sa.assigned_at)::TEXT,
        '|'
        ORDER BY sa.assigned_at
    )
    FROM agata_star_assignments sa
    JOIN agata_associations a ON a.id = sa.association_id
    WHERE sa.gaia_id = s.gaia_id
      AND (:filter_assoc_id IS NULL OR sa.association_id = :filter_assoc_id)
) AS assignments_packed,
"""
```

**[6] Date filter — DATE_SUB (linee 304-305)**:

```python
# DA (MySQL):
'24h': "s.last_imported_at >= DATE_SUB(NOW(), INTERVAL 1 DAY)",
'7d':  "s.last_imported_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)",

# A (PostgreSQL):
'24h': "s.last_imported_at >= NOW() - INTERVAL '1 day'",
'7d':  "s.last_imported_at >= NOW() - INTERVAL '7 days'",
```

**[7] Ricerca Gaia ID (linee 1452-1464)**:

```python
# DA (MySQL):
"""
SELECT
    Source as gaia_id,
    COUNT(*) as total_points,
    COUNT(DISTINCT catalogo) as num_catalogs,
    GROUP_CONCAT(DISTINCT catalogo) as catalogs
FROM agata_star_photometry
WHERE Source IS NOT NULL AND Source > 0
  AND CAST(Source AS CHAR) LIKE :search
  AND (association_id_owner IS NULL OR association_id_owner = :user_assoc_id OR :is_superuser = 1)
GROUP BY Source
ORDER BY total_points DESC
LIMIT :limit OFFSET :offset
"""

# A (PostgreSQL):
"""
SELECT
    source_id                            AS gaia_id,
    COUNT(*)                             AS total_points,
    COUNT(DISTINCT catalogo)             AS num_catalogs,
    STRING_AGG(DISTINCT catalogo, ',')   AS catalogs
FROM agata_star_photometry
WHERE source_id IS NOT NULL AND source_id > 0
  AND source_id::TEXT LIKE :search
  AND (association_id_owner IS NULL OR association_id_owner = :user_assoc_id OR :is_superuser = TRUE)
GROUP BY source_id
ORDER BY total_points DESC
LIMIT :limit OFFSET :offset
"""
```

**[8] ON DUPLICATE KEY UPDATE (linee 881, 1227)**:

Applicare la stessa conversione `ON CONFLICT (gaia_id) DO UPDATE SET` descritta sopra.

---

#### `agata/moduli/admin/services/star_service.py` (linee 36-97)

Pattern identico a `handlers/stars.py`. Applicare le stesse conversioni `GROUP_CONCAT → STRING_AGG` e `ON DUPLICATE KEY → ON CONFLICT`.

---

### Priorità P1 — Alti, Settimana 2

#### `agata/moduli/admin/services/catalog_common_service.py` (linee 541-654)

Stesso pattern `GROUP_CONCAT` + `ON DUPLICATE KEY UPDATE` ripetuto due volte. Applicare le conversioni descritte per `stars.py`.

#### `agata/moduli/admin/services/catalog_import_service.py` (linee 808-856)

Stesso pattern `GROUP_CONCAT` + `ON DUPLICATE KEY UPDATE`. Applicare le conversioni descritte.

#### `docs/migrations/*.sql` (11 file)

Conversioni da applicare a tutti i file:

```bash
# Script sed per conversione automatica (eseguire per ogni file .sql)
sed -i \
  -e 's/INT AUTO_INCREMENT PRIMARY KEY/SERIAL PRIMARY KEY/g' \
  -e 's/BIGINT AUTO_INCREMENT PRIMARY KEY/BIGSERIAL PRIMARY KEY/g' \
  -e 's/) ENGINE=InnoDB.*$/);/g' \
  -e 's/DEFAULT CHARSET=utf8mb4[^;]*//g' \
  -e 's/COLLATE utf8mb4_unicode_ci//g' \
  -e 's/TINYINT(1)/BOOLEAN/g' \
  -e 's/TINYINT DEFAULT 0/SMALLINT DEFAULT 0/g' \
  docs/migrations/*.sql
```

**Attenzione**: I `COMMENT` su colonne non sono supportati in PostgreSQL inline — rimuoverli o spostarli come `COMMENT ON COLUMN`.

I tipi `ENUM` richiedono creazione di tipi separati (non sostituibili via sed) — fare manualmente.

---

### Priorità P2 — Medi, Settimana 3

#### `agata/moduli/admin/services/ztf_survey_service.py` (linea 900)

```python
# DA (MySQL):
text(f"SELECT DISTINCT CAST(Source AS CHAR) FROM agata_star_photometry "
     f"WHERE catalogo IN ('ZTFr','ZTFg','ZTFi') AND Source IN ({placeholders})")

# A (PostgreSQL):
text(f"SELECT DISTINCT source_id::TEXT FROM agata_star_photometry "
     f"WHERE catalogo IN ('ZTFr','ZTFg','ZTFi') AND source_id IN ({placeholders})")
```

#### `agata/moduli/admin/services/vast_service.py` (linee 2210-2230)

```python
# DA (MySQL):
db.execute(text("""
    UPDATE agata_star SET
        is_known_variable = (
            SELECT COALESCE(MAX(is_known_variable), 0)
            FROM agata_vast_results
            WHERE CAST(gaia_source_id AS CHAR) = :gid AND is_valid = 1
        ),
        variable_types = (
            SELECT GROUP_CONCAT(DISTINCT variable_type SEPARATOR ',')
            FROM agata_vast_results
            WHERE CAST(gaia_source_id AS CHAR) = :gid AND is_valid = 1
        ),
        catalog_matches = (
            SELECT GROUP_CONCAT(DISTINCT catalog_matches SEPARATOR ',')
            FROM agata_vast_results
            WHERE CAST(gaia_source_id AS CHAR) = :gid AND is_valid = 1
        ),
        updated_at = NOW()
    WHERE gaia_id = :gid
"""), {'gid': gid})

# A (PostgreSQL):
db.execute(text("""
    UPDATE agata_star SET
        is_known_variable = (
            SELECT COALESCE(MAX(is_known_variable::INT)::BOOLEAN, FALSE)
            FROM agata_vast_results
            WHERE gaia_source_id::TEXT = :gid AND is_valid = TRUE
        ),
        variable_types = (
            SELECT STRING_AGG(DISTINCT variable_type, ',')
            FROM agata_vast_results
            WHERE gaia_source_id::TEXT = :gid AND is_valid = TRUE
        ),
        catalog_matches = (
            SELECT STRING_AGG(DISTINCT catalog_matches, ',')
            FROM agata_vast_results
            WHERE gaia_source_id::TEXT = :gid AND is_valid = TRUE
        ),
        updated_at = NOW()
    WHERE gaia_id = :gid
"""), {'gid': gid})
```

#### `agata/moduli/tpf/services/save_service.py` (linee 283-299)

Applicare la conversione `ON DUPLICATE KEY → ON CONFLICT` già descritta.

#### `agata/moduli/admin/routes/projects.py` (linea 838)

Applicare la conversione `ON DUPLICATE KEY → ON CONFLICT` già descritta.

#### `agata/db.py` — Cambio driver

```python
# DA:
DATABASE_URL = os.getenv('DATABASE_URL')
# Valore attuale in .env: mysql+pymysql://user:pass@host/agata_db

# A: aggiornare .env
# DATABASE_URL=postgresql+psycopg://user:pass@host/agata_db

# Nessuna altra modifica necessaria in db.py
# SQLAlchemy 2.0 con future=True è già compatibile PostgreSQL
```

`requirements.txt`:
```
# Rimuovere:
PyMySQL==1.1.2

# Aggiungere:
psycopg[binary]>=3.2.0
```

---

### Priorità P3 — Verifica compatibilità, Settimana 4

I seguenti file referenziano `agata_star_photometry` con query probabilmente compatibili (solo `WHERE source_id = :id`, `INSERT`, `DELETE`). Verificare ma non dovrebbero richiedere modifiche significative:

- `agata/moduli/variable_stars/services/db_loader.py` — `SELECT hjd, Vmag, catalogo WHERE Source = :id` → rinominare colonne
- `agata/moduli/admin/services/asassn.py`
- `agata/moduli/admin/services/ogle.py`
- `agata/moduli/admin/services/ztf.py`
- `agata/moduli/admin/services/tess.py`
- Script backfill in `scripts/`

**Rename colonne** — da cercare/sostituire globalmente in tutti i file .py:

```bash
# Find/replace globale (case-sensitive):
# Source     → source_id    (colonna Gaia DR3 ID)
# Vmag       → vmag         (magnitudine)

# Comando grep per trovare tutte le occorrenze:
grep -rn "Source\b\|Vmag\b" agata/ --include="*.py" | grep -v "\.pyc"
```

---

## 6. Migrazione dati con pgloader

### 6.1 Installazione pgloader

```bash
# Ubuntu/Debian
sudo apt-get install pgloader

# oppure Docker
docker pull dimitri/pgloader
```

### 6.2 File di configurazione pgloader

Creare `scripts/pgloader_agata.load`:

```
LOAD DATABASE
    FROM      mysql://agata_user:agata_pass@localhost/agata_db
    INTO      postgresql://agata_user:agata_pass@localhost/agata_db_pg

WITH
    include drop,
    create tables,
    create indexes,
    reset sequences,
    foreign keys,
    downcase identifiers

CAST
    type tinyint(1) to boolean using tinyint-to-boolean,
    type tinyint    to smallint,
    type datetime   to timestamptz,

EXCLUDING TABLE NAMES MATCHING 'agata_star_photometry'  -- migrata separatamente

BEFORE LOAD DO
    $$ CREATE EXTENSION IF NOT EXISTS timescaledb; $$;
```

**Nota**: `agata_star_photometry` va migrata separatamente perché richiede conversione in hypertable post-migrazione dati.

### 6.3 Migrazione `agata_star_photometry` separata

```bash
# 1. Crea la tabella PostgreSQL con lo schema TimescaleDB (vedi sezione 4.1)
psql -d agata_db_pg -f docs/migrations/pg_001_agata_star_photometry.sql

# 2. Esporta da MySQL
mysqldump --single-transaction --no-create-info \
          agata_db agata_star_photometry \
          --fields-terminated-by=',' \
          --lines-terminated-by='\n' \
          --tab=/tmp/phot_export/ \
          2>/dev/null

# Oppure con CSV:
mysql -u agata_user -p agata_db -e "
    SELECT hjd, Vmag, Source, catalogo, association_id_owner, catalog_import_id
    FROM agata_star_photometry
    INTO OUTFILE '/tmp/phot_export.csv'
    FIELDS TERMINATED BY ','
    ENCLOSED BY '\"'
    LINES TERMINATED BY '\n'
"

# 3. Importa in PostgreSQL
psql -d agata_db_pg -c "
    COPY agata_star_photometry (hjd, vmag, source_id, catalogo, association_id_owner, catalog_import_id)
    FROM '/tmp/phot_export.csv'
    WITH (FORMAT CSV, NULL 'NULL')
"

# 4. Verifica conteggio
mysql -u agata_user -p agata_db -e "SELECT COUNT(*) FROM agata_star_photometry"
psql -d agata_db_pg -c "SELECT COUNT(*) FROM agata_star_photometry"
# I due numeri devono essere identici
```

### 6.4 Script Python per migrazione controllata (alternativa)

Per migrazione in batch con validazione:

```python
# scripts/migrate_photometry.py
"""
Migra agata_star_photometry da MySQL a PostgreSQL in batch da 100k righe.
Usare questo script se pgloader non è disponibile o si vuole controllo granulare.
"""
import os
from sqlalchemy import create_engine, text
import pandas as pd
from tqdm import tqdm

MYSQL_URL = os.getenv('MYSQL_DATABASE_URL')
PG_URL = os.getenv('PG_DATABASE_URL')

mysql_engine = create_engine(MYSQL_URL)
pg_engine = create_engine(PG_URL)

BATCH_SIZE = 100_000

with mysql_engine.connect() as src:
    total = src.execute(text("SELECT COUNT(*) FROM agata_star_photometry")).scalar()
    print(f"Righe totali: {total:,}")

    for offset in tqdm(range(0, total, BATCH_SIZE)):
        df = pd.read_sql(
            f"SELECT hjd, Vmag as vmag, Source as source_id, catalogo, "
            f"association_id_owner, catalog_import_id "
            f"FROM agata_star_photometry "
            f"ORDER BY Source, hjd "
            f"LIMIT {BATCH_SIZE} OFFSET {offset}",
            src
        )
        df.to_sql(
            'agata_star_photometry',
            pg_engine,
            if_exists='append',
            index=False,
            method='multi',
            chunksize=1000
        )

print("Migrazione completata.")
```

---

## 7. Setup infrastruttura

### 7.1 Installazione PostgreSQL + TimescaleDB su astrogen01 (dev)

```bash
# Ubuntu 22.04 / Debian 12

# 1. Installa PostgreSQL 16
sudo apt-get install -y postgresql-16 postgresql-client-16

# 2. Installa TimescaleDB
sudo apt-get install -y timescaledb-2-postgresql-16

# 3. Configura timescaledb in postgresql.conf
sudo timescaledb-tune --quiet --yes

# 4. Riavvia PostgreSQL
sudo systemctl restart postgresql

# 5. Crea database
sudo -u postgres psql -c "CREATE USER agata_user WITH PASSWORD 'agata_pass';"
sudo -u postgres psql -c "CREATE DATABASE agata_db OWNER agata_user;"
sudo -u postgres psql -d agata_db -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# 6. Verifica
sudo -u postgres psql -d agata_db -c "\dx"
# Deve mostrare timescaledb nell'elenco estensioni
```

### 7.2 `.env` — aggiornamento

```bash
# DA:
DATABASE_URL=mysql+pymysql://agata_user:agata_pass@localhost/agata_db

# A:
DATABASE_URL=postgresql+psycopg://agata_user:agata_pass@localhost/agata_db
```

### 7.3 `requirements.txt` — aggiornamento

```
# Rimuovere:
PyMySQL==1.1.2

# Aggiungere:
psycopg[binary]>=3.2.0
```

---

## 8. Piano di esecuzione — 4 settimane

### Settimana 1 — Setup + file critici P0

**Giorno 1-2: Setup infrastruttura**
- [ ] Installa PostgreSQL 16 + TimescaleDB su astrogen01
- [ ] Crea DB di test, estensioni, utente
- [ ] Aggiorna `agata/db.py` e `requirements.txt`
- [ ] Verifica connessione Flask ↔ PostgreSQL (avvio app, pagina login)

**Giorno 3-5: Refactor P0**
- [ ] `agata/core/db/handlers/stars.py` — `GROUP_CONCAT` + `ON DUPLICATE KEY`
- [ ] `agata/moduli/admin/services/star_service.py` — stesso pattern
- [ ] `agata/moduli/admin/routes/stars_catalog.py` — tutti i punti 1-8 della sezione 5
- [ ] Test unitario su ogni query modificata

---

### Settimana 2 — Schema + dati + P1

**Giorno 1-2: Schema PostgreSQL**
- [ ] Converti tutti i 11 file `docs/migrations/*.sql`
- [ ] Esegui migrations su DB di test
- [ ] Crea hypertable `agata_star_photometry` (sezione 4.1)
- [ ] Configura compressione e continuous aggregate

**Giorno 3-5: Migrazione dati + P1**
- [ ] Esegui migrazione dati con pgloader (tutte le tabelle tranne photometry)
- [ ] Esegui migrazione `agata_star_photometry` separata
- [ ] Verifica `COUNT(*)` pre/post per ogni tabella
- [ ] `agata/moduli/admin/services/catalog_common_service.py`
- [ ] `agata/moduli/admin/services/catalog_import_service.py`

---

### Settimana 3 — P2 + features TimescaleDB

**Giorno 1-3: Refactor P2**
- [ ] `agata/moduli/admin/services/ztf_survey_service.py`
- [ ] `agata/moduli/admin/services/vast_service.py`
- [ ] `agata/moduli/tpf/services/save_service.py`
- [ ] `agata/moduli/admin/routes/projects.py`

**Giorno 4-5: Features TimescaleDB**
- [ ] Verifica continuous aggregate `phot_star_summary` si popola correttamente
- [ ] Aggiorna `upsert_star()` in `stars.py`: leggi da `phot_star_summary` invece di fare GROUP BY su tutta la tabella
- [ ] Test pipeline import completa: TESS, ZTF, ASAS-SN

---

### Settimana 4 — P3 + testing + deploy dev

**Giorno 1-2: P3 e rename colonne**
- [ ] Find/replace globale `Source` → `source_id` e `Vmag` → `vmag` in tutti i file .py
- [ ] Verifica ogni file restante che tocca `agata_star_photometry`
- [ ] Test tutte le route principali

**Giorno 3-5: Testing e2e + benchmark**
- [ ] Test completo su astrogen01 (dev): login → import → analisi → visualizzazione curva
- [ ] Benchmark query:
  ```sql
  EXPLAIN ANALYZE SELECT hjd, vmag, catalogo
  FROM agata_star_photometry
  WHERE source_id = 123456789012345;
  ```
- [ ] Verifica compressione attiva dopo 30 giorni (o forzare manualmente):
  ```sql
  SELECT compress_chunk(c) FROM show_chunks('agata_star_photometry') c LIMIT 5;
  SELECT * FROM timescaledb_information.compressed_chunk_stats;
  ```
- [ ] Deploy su astrogen03 se tutto OK

---

## 9. Checklist di verifica

### Pre-migrazione (baseline)

```sql
-- Eseguire su MySQL e salvare i risultati
SELECT COUNT(*) FROM agata_star_photometry;
SELECT COUNT(DISTINCT source_id) FROM agata_star_photometry;  -- MySQL: Source
SELECT MIN(hjd), MAX(hjd) FROM agata_star_photometry;
SELECT COUNT(*) FROM agata_star;
SELECT COUNT(*) FROM agata_associations;
-- [salva output per confronto post-migrazione]
```

### Post-migrazione schema

```sql
-- Verifica hypertable
SELECT * FROM timescaledb_information.hypertables
WHERE hypertable_name = 'agata_star_photometry';
-- Atteso: 1 riga

-- Verifica chunk
SELECT * FROM timescaledb_information.chunks
WHERE hypertable_name = 'agata_star_photometry';
-- Atteso: N chunk (1 ogni 30 HJD di dati)

-- Verifica indici
SELECT indexname, indexdef FROM pg_indexes
WHERE tablename = 'agata_star_photometry';
```

### Post-migrazione dati

```sql
-- Confrontare con baseline MySQL
SELECT COUNT(*) FROM agata_star_photometry;
SELECT COUNT(DISTINCT source_id) FROM agata_star_photometry;
SELECT MIN(hjd), MAX(hjd) FROM agata_star_photometry;
SELECT COUNT(*) FROM agata_star;
SELECT COUNT(*) FROM agata_associations;
```

### Verifica performance

```sql
-- Query hot path
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT hjd, vmag, catalogo
FROM agata_star_photometry
WHERE source_id = 123456789012345  -- sostituire con un ID reale
  AND vmag IS NOT NULL;
-- Atteso: Index Scan on idx_phot_source_hjd, NON Seq Scan

-- Verifica continuous aggregate
SELECT * FROM phot_star_summary
WHERE source_id = 123456789012345;
-- Atteso: righe con n_points, min/max hjd e vmag per catalogo
```

### Verifica compressione

```sql
-- Forzare compressione per test (senza aspettare 30 giorni)
SELECT compress_chunk(c)
FROM show_chunks('agata_star_photometry') c
LIMIT 10;

-- Verifica ratio
SELECT
    chunk_name,
    before_compression_total_bytes / 1024 / 1024 AS before_mb,
    after_compression_total_bytes  / 1024 / 1024 AS after_mb,
    ROUND(100.0 - (after_compression_total_bytes::FLOAT /
                   before_compression_total_bytes * 100), 1) AS pct_saved
FROM timescaledb_information.compressed_chunk_stats
WHERE hypertable_name = 'agata_star_photometry'
ORDER BY before_compression_total_bytes DESC;
-- Atteso: pct_saved tra 85% e 95%
```

### Verifica funzionale UI

- [ ] Login con Google OAuth funziona
- [ ] Pagina "Stars Catalog" carica e mostra stelle con filtri
- [ ] Import TESS da UI completa senza errori
- [ ] Curva di luce di una stella nota si visualizza correttamente
- [ ] Analisi variabilità (Lomb-Scargle) produce output
- [ ] Pipeline VAST completa un job di test
- [ ] Pipeline ZTF completa un job di test

---

## 10. Rollback plan

In caso di problemi critici dopo il deploy su produzione:

### Rollback immediato (< 1 ora di downtime)

1. Fermare Apache su astrogen03
2. Ripristinare `DATABASE_URL` nel `.env` (puntare a MySQL)
3. Ripristinare `agata/db.py` e `requirements.txt` da git tag pre-migrazione
4. Reinstallare requirements: `pip install -r requirements.txt`
5. Riavviare Apache
6. Verificare funzionamento

### Prerequisito rollback

- **Non eliminare il database MySQL** fino a validazione completa in produzione (minimo 2 settimane dopo deploy)
- Mantenere il MySQL in read-only mode come fallback
- Fare un backup MySQL completo immediatamente prima di iniziare il deploy su produzione

```bash
# Backup MySQL pre-deploy
mysqldump -u agata_user -p agata_db > backups/agata_db_pre_pg_migration_$(date +%Y%m%d).sql
gzip backups/agata_db_pre_pg_migration_$(date +%Y%m%d).sql
```

---

## Appendice: comandi utili TimescaleDB

```sql
-- Stato generale
SELECT * FROM timescaledb_information.hypertables;
SELECT * FROM timescaledb_information.jobs;
SELECT * FROM timescaledb_information.job_stats WHERE job_id IN (
    SELECT job_id FROM timescaledb_information.jobs
    WHERE hypertable_name = 'agata_star_photometry'
);

-- Chunks
SELECT show_chunks('agata_star_photometry');
SELECT * FROM timescaledb_information.chunks
WHERE hypertable_name = 'agata_star_photometry'
ORDER BY range_start;

-- Forzare compressione manuale
SELECT compress_chunk(c) FROM show_chunks('agata_star_photometry') c;

-- Decomprimere (per operazioni bulk come DELETE/UPDATE su dati storici)
SELECT decompress_chunk(c) FROM show_chunks('agata_star_photometry') c
WHERE range_start < NOW() - INTERVAL '90 days';

-- Statistiche spazio
SELECT
    hypertable_name,
    pg_size_pretty(total_bytes) AS total,
    pg_size_pretty(table_bytes) AS table,
    pg_size_pretty(index_bytes) AS index,
    pg_size_pretty(toast_bytes) AS toast
FROM timescaledb_information.hypertable_detailed_size('agata_star_photometry');

-- Aggiornare manualmente il continuous aggregate
CALL refresh_continuous_aggregate('phot_star_summary', NULL, NULL);
```




Piano: Migrazione MySQL → PostgreSQL + TimescaleDB
Contesto
La tabella agata_star_photometry è il bacino centrale dei dati fotometrici (TESS, ZTF, ASAS-SN, OGLE, VAST): serie temporali con hjd (tempo), Vmag (magnitudine), Source (Gaia DR3 ID), catalogo.

Problema: Crescita illimitata, nessuna compressione, nessuna ottimizzazione per time series.

Obiettivo: Valutare la migrazione a PostgreSQL + TimescaleDB per risparmiare spazio e migliorare velocità di recupero dati.

Stato attuale del codebase
Metrica	Valore
Tabelle database	22
File Python con SQL raw	39
Istanze text() SQL	108
Funzioni MySQL-specific	35+ occorrenze in 12+ file
File che toccano agata_star_photometry	26
Modelli SQLAlchemy ORM	23
Dipendenza MySQL: PyMySQL==1.1.2 in requirements.

Cosa guadagna AGATA con TimescaleDB
1. Compressione nativa delle time series (-70-90% spazio)
TimescaleDB usa compressione columnar per chunk ottimizzata per double series quasi-monotone. Per agata_star_photometry:

hjd (sequenza quasi-monotona): ratio atteso 10x-20x
Vmag (serie con variazione lenta): ratio atteso 3x-5x
catalogo (stringa ripetuta): ratio atteso 50x con dictionary encoding
Benchmark reali TimescaleDB: 10-15x di compressione su time series astronomiche simili.

Confronto:

Approccio	Spazio stimato per 1M righe
MySQL InnoDB raw	~80 MB
MySQL InnoDB COMPRESSED	~50 MB (-37%)
PostgreSQL plain	~65 MB
TimescaleDB compressed	~6-8 MB (-92%)
2. Query time range ultra-veloci (chunk pruning)
TimescaleDB divide la tabella in chunks temporali (es. 7 giorni di HJD). Una query WHERE hjd BETWEEN :t1 AND :t2 accede solo ai chunk rilevanti — identico al partition pruning MySQL ma automatico, adattivo, e ottimizzato per time series.

Per AGATA:

Phase folding (WHERE Source = :gaia_id ORDER BY hjd): accesso diretto ai chunk per quella stella
Analisi periodo temporale (WHERE hjd > :epoch): chunk pruning automatico
3. Funzioni time series native
TimescaleDB aggiunge funzioni SQL che AGATA può usare direttamente:

-- Downsampling intelligente per preview (già desiderato nell'architettura)
SELECT time_bucket(0.01, hjd) as hjd_bin,
       avg(Vmag) as vmag_avg,
       catalogo
FROM agata_star_photometry
WHERE source_id = :gaia_id
GROUP BY hjd_bin, catalogo
ORDER BY hjd_bin;

-- Continuous aggregate (pre-calcola automaticamente i preview)
CREATE MATERIALIZED VIEW phot_preview
WITH (timescaledb.continuous) AS
SELECT source_id, catalogo,
       time_bucket(0.01, hjd) as hjd_bin,
       avg(Vmag) as vmag_avg,
       count(*) as n_points
FROM agata_star_photometry
GROUP BY source_id, catalogo, hjd_bin;
4. Continuous Aggregates → elimina la cache manuale
Attualmente agata_star mantiene aggregati manuali (total_points, min_hjd, max_hjd, ecc.) aggiornati via hook sincronico a ogni import. Con TimescaleDB i Continuous Aggregates si aggiornano automaticamente in background — eliminando il codice di upsert_star() per la parte fotometrica.

5. Compressione policy automatica
-- Comprime automaticamente i chunk più vecchi di 30 giorni
SELECT add_compression_policy('agata_star_photometry', INTERVAL '30 days');
I dati recenti (importati di recente) restano non compressi per write veloci; i dati storici si comprimono automaticamente.

Costo della migrazione: analisi dettagliata
Funzioni MySQL-specific da convertire (35+ occorrenze)
Funzione MySQL	Equivalente PostgreSQL	File critici	Sforzo
GROUP_CONCAT(DISTINCT x ORDER BY x SEPARATOR ',')	STRING_AGG(DISTINCT x, ',') (no ORDER in DISTINCT) o ARRAY_TO_STRING(ARRAY_AGG(DISTINCT x), ',')	handlers/stars.py, stars_catalog.py, star_service.py	2-3h
ON DUPLICATE KEY UPDATE	INSERT ... ON CONFLICT (col) DO UPDATE SET ...	handlers/stars.py, catalog services	3-4h
FIND_IN_SET(val, col)	val = ANY(STRING_TO_ARRAY(col, ',')) o redesign con array column	stars_catalog.py (4 occorrenze)	1-2h
CAST(col AS CHAR)	col::TEXT o CAST(col AS TEXT)	stars_catalog.py, ztf_service.py, vast_service.py	1h
IFNULL(a, b)	COALESCE(a, b)	vari	30min
IF(cond, a, b)	CASE WHEN cond THEN a ELSE b END	vari	30min
AUTO_INCREMENT → migration SQL	SERIAL o GENERATED ALWAYS AS IDENTITY	11 file .sql	2h
ENGINE=InnoDB, CHARSET=utf8mb4	rimuovere (PostgreSQL non li usa)	11 file .sql	30min
COLLATE utf8mb4_unicode_ci	rimuovere o usare COLLATE "und-x-icu"	stars_catalog.py	negligibile
Stima totale refactoring SQL: 12-16 ore

Cambio driver DB
agata/db.py usa PyMySQL via SQLAlchemy. Cambio richiesto:

# Da:
from sqlalchemy import create_engine
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://user:pass@host/db"

# A:
SQLALCHEMY_DATABASE_URL = "postgresql+psycopg://user:pass@host/db"
Requirements:

# Rimuovere: PyMySQL==1.1.2
# Aggiungere: psycopg[binary]>=3.2.0
SQLAlchemy 2.0+ è già configurato (future=True) — la migrazione del driver è 1-2 ore incluso testing connessione.

File Python da modificare (priorità)
P0 — Critici (settimana 1):

agata/core/db/handlers/stars.py — GROUP_CONCAT + ON DUPLICATE KEY (8+ occorrenze)
agata/moduli/admin/routes/stars_catalog.py — FIND_IN_SET (4) + GROUP_CONCAT (4) + CAST (3) = 45 istanze SQL totali
agata/moduli/admin/services/star_service.py — GROUP_CONCAT
P1 — Alti (settimana 2):

agata/moduli/admin/services/catalog_import_service.py
agata/moduli/admin/services/catalog_common_service.py
11 file in docs/migrations/ — solo sintassi SQL
P2 — Medi (settimana 3):

agata/moduli/admin/services/ztf_survey_service.py
agata/moduli/admin/services/vast_service.py
agata/db.py — cambio driver
requirements.txt — PyMySQL → psycopg
P3 — Bassi (settimana 4):

Restanti 26 file che toccano agata_star_photometry (verificare compatibilità query)
Testing e2e
Schema TimescaleDB per agata_star_photometry
-- PostgreSQL + TimescaleDB: conversione schema

-- 1. Crea tabella come hypertable (partizionamento su hjd)
CREATE TABLE agata_star_photometry (
  hjd                  DOUBLE PRECISION NOT NULL,
  vmag                 DOUBLE PRECISION,
  source_id            BIGINT NOT NULL,
  catalogo             VARCHAR(100) NOT NULL DEFAULT '',
  association_id_owner INTEGER REFERENCES agata_associations(id),
  catalog_import_id    INTEGER REFERENCES agata_catalog_imports(id)
  -- NOTE: 'index' rimosso (obsoleto, non usato in query critiche)
);

-- 2. Converti in hypertable partizionata su hjd
-- chunk_time_interval: 30 giorni di HJD (~30 giorni astronomici)
SELECT create_hypertable(
  'agata_star_photometry',
  'hjd',
  chunk_time_interval => 30.0,
  if_not_exists => TRUE
);

-- 3. Indice primario per hot path
CREATE INDEX ON agata_star_photometry (source_id, hjd DESC);

-- 4. Abilita compressione columnar
ALTER TABLE agata_star_photometry SET (
  timescaledb.compress,
  timescaledb.compress_orderby = 'hjd DESC',
  timescaledb.compress_segmentby = 'source_id, catalogo'
);

-- 5. Policy: comprimi automaticamente chunk > 30 giorni
SELECT add_compression_policy('agata_star_photometry', INTERVAL '30 days');

-- 6. Continuous aggregate per preview (sostituisce cache manuale)
CREATE MATERIALIZED VIEW phot_star_summary
WITH (timescaledb.continuous) AS
SELECT
  source_id,
  catalogo,
  COUNT(*) as n_points,
  MIN(hjd) as min_hjd,
  MAX(hjd) as max_hjd,
  MIN(vmag) as min_vmag,
  MAX(vmag) as max_vmag
FROM agata_star_photometry
GROUP BY source_id, catalogo;

-- Aggiornamento automatico ogni ora
SELECT add_continuous_aggregate_policy(
  'phot_star_summary',
  start_offset => INTERVAL '3 days',
  end_offset => INTERVAL '1 hour',
  schedule_interval => INTERVAL '1 hour'
);
Nota: source_id al posto di Source (convenzione snake_case PostgreSQL). Richiede update di tutte le query, ma è un rename globale facile.

Miglioramenti quantificati
Metrica	MySQL (attuale)	TimescaleDB	Miglioramento
Spazio per 1M righe	~80 MB	~6-8 MB	-90%
Spazio per 50M righe	~4 GB	~300-400 MB	-90%
Query WHERE source_id = :id (hot)	15-40ms	10-25ms	-30-40%
Query WHERE hjd BETWEEN t1 AND t2	full scan o slow range	chunk pruning	-80-95%
Query aggregazioni (min/max/count)	20-80ms	~1ms (continuous aggregate)	-99%
Insert bulk (pipeline import)	~500ms/10k righe	~400ms/10k righe	-20%
Piano di migrazione in 4 settimane
Settimana 1 — Setup PostgreSQL + conversione critici
Setup PostgreSQL + TimescaleDB su astrogen01 (dev)
Converti agata/db.py + requirements.txt
Refactor P0: handlers/stars.py, stars_catalog.py, star_service.py
Verifica connessione e query base
Settimana 2 — Migrazione schema e dati
Converti tutti i 11 file docs/migrations/*.sql a PostgreSQL syntax
Crea hypertable agata_star_photometry con compressione
Refactor P1: catalog services
Migration script: mysqldump → pgloader per dati esistenti
Settimana 3 — Refactor restanti + TimescaleDB features
Refactor P2: ztf_survey_service, vast_service, db.py
Implementa continuous aggregate phot_star_summary
Aggiorna upsert_star() per usare continuous aggregate invece di query manuali
Test pipeline import completa (TESS, ZTF, ASAS-SN)
Settimana 4 — Testing, tuning, deploy
Refactor P3: file rimanenti
Testing e2e su astrogen01
Benchmark query pre/post
Deploy su astrogen03 con PostgreSQL
Strumento di migrazione dati: pgloader
# Migrazione automatica MySQL → PostgreSQL
pgloader mysql://user:pass@localhost/agata_db \
         postgresql://user:pass@localhost/agata_db \
         --with "quote identifiers"

# pgloader gestisce automaticamente:
# - AUTO_INCREMENT → SERIAL
# - tipo conversioni (TINYINT → SMALLINT, TEXT → TEXT)
# - Trasferimento dati in parallelo
Alternativa: script Python con pandas + SQLAlchemy per controllo granulare.

Rischi e mitigazioni
Rischio	Probabilità	Impatto	Mitigazione
FIND_IN_SET su colonne CSV	Alta	Medio	Convertire a array[] PostgreSQL o riscrivere query con ANY()
GROUP_CONCAT con DISTINCT + ORDER BY	Alta	Basso	ARRAY_TO_STRING(ARRAY_AGG(DISTINCT x), ',') — perde ordinamento, verificare se necessario
ON DUPLICATE KEY UPDATE semantics	Media	Medio	ON CONFLICT (col) DO UPDATE — richiede vincolo UNIQUE esplicito su PostgreSQL
agata_star_photometry senza PRIMARY KEY	Alta	Alto	Aggiungere id BIGSERIAL o usare (hjd, source_id) come primary key composita per hypertable
pgloader incompatibilità tipi	Bassa	Medio	Validare migrazione con SELECT COUNT(*) pre/post per ogni tabella
Chunk pruning non attivo (query senza hjd)	Alta	Basso	Le query WHERE source_id = :id usano l'indice su source_id, non il chunk pruning — performance invariata
File critici da modificare
File	Tipo modifica	Priorità
agata/db.py	Cambio driver PyMySQL → psycopg	P2
requirements.txt	PyMySQL → psycopg[binary]	P2
agata/core/db/handlers/stars.py	GROUP_CONCAT, ON DUPLICATE KEY	P0
agata/moduli/admin/routes/stars_catalog.py	FIND_IN_SET, GROUP_CONCAT, CAST	P0
agata/moduli/admin/services/star_service.py	GROUP_CONCAT	P0
agata/moduli/admin/services/catalog_import_service.py	query SQL generali	P1
agata/moduli/admin/services/catalog_common_service.py	query SQL generali	P1
docs/migrations/*.sql (11 file)	AUTO_INCREMENT→SERIAL, ENGINE→rimuovere	P1
agata/moduli/admin/services/ztf_survey_service.py	CAST, query specifiche	P2
agata/moduli/admin/services/vast_service.py	query specifiche	P2
agata/moduli/variable_stars/services/db_loader.py	verificare compatibilità	P3
Verifica finale
SELECT COUNT(*), COUNT(DISTINCT source_id), MIN(hjd), MAX(hjd) FROM agata_star_photometry — identico pre/post
SELECT * FROM timescaledb_information.chunks WHERE hypertable_name = 'agata_star_photometry' — verificare chunk attivi
EXPLAIN (ANALYZE, BUFFERS) SELECT hjd, vmag, catalogo FROM agata_star_photometry WHERE source_id = :id — verificare Index Scan (non Seq Scan)
SELECT * FROM timescaledb_information.compressed_chunk_stats — verificare ratio di compressione post-policy
Caricamento curva di luce da UI per stella nota — verificare tempi e dati corretti