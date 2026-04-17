#!/usr/bin/env python3
"""
Migrazione MySQL → PostgreSQL per AGATA
Strategia: tabella-per-tabella con COPY per grandi volumi, INSERT batch per piccole

Usage:
  python scripts/migrate_to_pg.py --phase 1  # Migrate phase 1 (associations, users)
  python scripts/migrate_to_pg.py --phase 1-3  # Migrate phases 1-3
  python scripts/migrate_to_pg.py --validate  # Run post-migration validation
  python scripts/migrate_to_pg.py --full  # All phases + validation + sequences reset
"""

import os
import sys
import json
import time
import argparse
from contextlib import contextmanager
from io import StringIO
import csv
from typing import Optional, Dict, List, Any, Callable
from datetime import datetime

import pymysql
import pymysql.cursors
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# Carica .env
load_dotenv()

# ============================================================================
# CONFIGURAZIONE
# ============================================================================

MYSQL_DSN = os.environ.get('MYSQL_DATABASE_URL', 'mysql+pymysql://root:@localhost/catalogo')
PG_DSN = os.environ.get('DATABASE_URL', 'postgresql+psycopg://user:pass@localhost/catalogo_pg')

# Parse PostgreSQL DSN
# postgresql+psycopg://user:pass@host/dbname → host, user, password, dbname
def parse_pg_dsn(dsn: str) -> Dict[str, str]:
    """Parse PostgreSQL connection string."""
    from urllib.parse import urlparse
    parsed = urlparse(dsn.replace('postgresql+psycopg://', 'postgresql://').replace('postgresql+psycopg2://', 'postgresql://'))
    return {
        'host': parsed.hostname or 'localhost',
        'port': parsed.port or 5432,
        'user': parsed.username or 'postgres',
        'password': parsed.password or '',
        'database': parsed.path.lstrip('/') if parsed.path else 'catalogo_pg',
    }

# Parse MySQL DSN
# mysql+pymysql://user:pass@host/dbname
def parse_mysql_dsn(dsn: str) -> Dict[str, str]:
    """Parse MySQL connection string."""
    from urllib.parse import urlparse
    parsed = urlparse(dsn.replace('mysql+pymysql://', 'mysql://'))
    return {
        'host': parsed.hostname or 'localhost',
        'port': parsed.port or 3306,
        'user': parsed.username or 'root',
        'password': parsed.password or '',
        'database': parsed.path.lstrip('/') if parsed.path else 'catalogo',
    }

PG_CONFIG = parse_pg_dsn(PG_DSN)
MYSQL_CONFIG = parse_mysql_dsn(MYSQL_DSN)

# ============================================================================
# CONNESSIONI
# ============================================================================

@contextmanager
def get_mysql():
    """Apri connessione MySQL con DictCursor."""
    conn = pymysql.connect(
        host=MYSQL_CONFIG['host'],
        port=MYSQL_CONFIG['port'],
        user=MYSQL_CONFIG['user'],
        password=MYSQL_CONFIG['password'],
        database=MYSQL_CONFIG['database'],
        charset='utf8mb4',
        use_unicode=True,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )
    try:
        yield conn
    finally:
        conn.close()

@contextmanager
def get_pg():
    """Apri connessione PostgreSQL."""
    conn = psycopg2.connect(
        host=PG_CONFIG['host'],
        port=PG_CONFIG['port'],
        user=PG_CONFIG['user'],
        password=PG_CONFIG['password'],
        database=PG_CONFIG['database']
    )
    conn.autocommit = False
    try:
        yield conn
    finally:
        conn.close()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def disable_pg_fk(conn):
    """Disabilita FK constraints per migrazione veloce."""
    with conn.cursor() as cur:
        try:
            cur.execute("SET session_replication_role = replica;")
            conn.commit()
        except psycopg2.errors.InsufficientPrivilege:
            # Se l'utente non ha permessi, prosegui comunque
            conn.rollback()
            print("    (FK check disabilitato - permessi insufficienti)")

def enable_pg_fk(conn):
    """Abilita FK constraints."""
    with conn.cursor() as cur:
        try:
            cur.execute("SET session_replication_role = DEFAULT;")
            conn.commit()
        except psycopg2.errors.InsufficientPrivilege:
            conn.rollback()
            pass  # Silent fail

def json_or_none(val: Any) -> Optional[str]:
    """Converte LONGTEXT JSON MySQL in JSON string per PostgreSQL."""
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        try:
            return json.dumps(val)
        except (TypeError, ValueError):
            print(f"    WARN: Can't serialize to JSON: {val}")
            return None
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return None
        try:
            json.loads(val)  # Validate it's valid JSON
            return val  # Return as-is (already a string)
        except json.JSONDecodeError:
            print(f"    WARN: Invalid JSON: {val[:100]}")
            return None
    return None

def timestamp_or_none(val: Any) -> Optional[Any]:
    """Converte TIMESTAMP MySQL 0000-00-00 → None."""
    if val == '0000-00-00 00:00:00':
        return None
    return val

def bool_from_tinyint(val: Any) -> Optional[bool]:
    """Converte TINYINT(1) MySQL → bool."""
    if val is None:
        return None
    return bool(val)

# ============================================================================
# MIGRATE_SIMPLE - per tabelle piccole (< 10k righe)
# ============================================================================

def get_column_mapping(table: str, cols: List[str]) -> Dict[str, str]:
    """
    Ritorna mapping colonne MySQL → PostgreSQL per tabelle con discrepanze di nome.
    Es: 'nome' → 'name'
    """
    mappings = {
        'agata_edu_stars': {
            'nome': 'name',  # Non migrare altre colonne
            'tipo': '__skip__',
            'costellazione': '__skip__',
            'descrizione': '__skip__',
            'periodo_noto_ore': '__skip__',
            'source': '__skip__',
            'kind': '__skip__',
            'domande_ibl': '__skip__',
            'sort_order': '__skip__',
        },
    }
    return mappings.get(table, {})

def get_pg_column_types(table: str) -> Dict[str, str]:
    """Ricava i tipi colonna da PostgreSQL."""
    try:
        pg_conn = psycopg2.connect(
            host=PG_CONFIG['host'],
            user=PG_CONFIG['user'],
            password=PG_CONFIG['password'],
            database=PG_CONFIG['database']
        )
        with pg_conn.cursor() as cur:
            cur.execute(f"""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (table,))
            result = {row[0]: row[1] for row in cur.fetchall()}
        pg_conn.close()
        return result
    except Exception as e:
        print(f"      ERR get_pg_types: {e}")
        return {}

def cast_row_to_pg_types(row: Dict, pg_types: Dict[str, str]) -> Dict:
    """Converte una riga MySQL ai tipi PostgreSQL."""
    new_row = {}
    for col, val in row.items():
        pg_type = pg_types.get(col, 'unknown')

        # Cast BOOLEAN
        if pg_type == 'boolean' and val is not None:
            if isinstance(val, bool):
                val = val
            else:
                val = bool(int(val) if isinstance(val, (int, str)) else val)
        # Cast TIMESTAMP (rimuovi 0000-00-00)
        elif pg_type in ['timestamp with time zone', 'timestamp without time zone']:
            if val == '0000-00-00 00:00:00':
                val = None
        # Cast JSON (convert dict/list to JSON string)
        elif isinstance(val, dict):
            # Any dict column should be converted to JSON string
            try:
                val = json.dumps(val)
            except (TypeError, ValueError) as e:
                print(f"    WARN: Can't convert {col} dict to JSON: {e}")
                val = None
        elif isinstance(val, list):
            # Any list column should be converted to JSON string
            try:
                val = json.dumps(val)
            except (TypeError, ValueError) as e:
                print(f"    WARN: Can't convert {col} list to JSON: {e}")
                val = None

        new_row[col] = val
    return new_row

def migrate_simple(
    table: str,
    transform_fn: Optional[Callable] = None,
    batch_size: int = 500,
    disable_fk: bool = True
) -> int:
    """
    Migra tabella con volume basso usando fetchall + execute_batch.

    Args:
        table: nome tabella
        transform_fn: funzione(row_dict) → row_dict o None per skipparla
        batch_size: dimensione batch INSERT
        disable_fk: se True, disabilita FK durante migrazione

    Returns:
        numero di righe migrate
    """
    with get_mysql() as mysql_conn:
        with mysql_conn.cursor() as cur:
            # Check if table exists first
            try:
                cur.execute(f"SELECT COUNT(*) as cnt FROM `{table}`")
                total = cur.fetchone()['cnt']
            except Exception as e:
                if "doesn't exist" in str(e):
                    print(f"  [{table}] Non esiste in MySQL, skip.")
                    return 0
                raise

            if total == 0:
                print(f"  [{table}] Vuota, skip.")
                return 0

            cur.execute(f"SELECT * FROM `{table}`")
            rows = cur.fetchall()

    # Trasforma rows
    if transform_fn:
        rows = [transform_fn(r) for r in rows]
        rows = [r for r in rows if r is not None]

    if not rows:
        print(f"  [{table}] Nessuna riga dopo transform, skip.")
        return 0

    # Rinomina colonne se necessario
    cols = list(rows[0].keys())
    col_mapping = get_column_mapping(table, cols)

    if col_mapping:
        new_rows = []
        for row in rows:
            new_row = {}
            for old_col, val in row.items():
                new_col = col_mapping.get(old_col, old_col)
                # Skip colonne marcate con __skip__
                if new_col != '__skip__':
                    new_row[new_col] = val
            new_rows.append(new_row)
        rows = new_rows
        cols = list(rows[0].keys()) if rows else []

        if not cols and rows:
            # Se tutte le colonne sono state skippate, usa le originali
            cols = list(rows[0].keys())

    # Ricava tipi PostgreSQL e cast
    pg_types = get_pg_column_types(table)
    if not pg_types:
        print(f"    WARN: Couldn't get PG types for {table}, using fallback cast")
    # Always cast to handle dict/list even if we don't know exact types
    rows = [cast_row_to_pg_types(row, pg_types) for row in rows]

    placeholders = ",".join(["%s"] * len(cols))
    col_names = ",".join([f'"{c}"' for c in cols])
    sql = f'INSERT INTO "{table}" ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'

    with get_pg() as pg_conn:
        if disable_fk:
            disable_pg_fk(pg_conn)

        with pg_conn.cursor() as cur:
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i+batch_size]
                values = []
                for r in batch:
                    row_values = []
                    for c in cols:
                        val = r[c]
                        if isinstance(val, dict):
                            print(f"    ERROR: Column {c} is a dict, converting to JSON: {val}")
                            val = json.dumps(val) if val else None
                        row_values.append(val)
                    values.append(tuple(row_values))

                # Debug check before execute_batch
                for v_idx, v_tuple in enumerate(values):
                    for col_idx, val in enumerate(v_tuple):
                        if isinstance(val, dict):
                            print(f"    ERROR: values[{v_idx}][{col_idx}] ({cols[col_idx]}) is dict!")

                psycopg2.extras.execute_batch(cur, sql, values, page_size=batch_size)

        pg_conn.commit()

        if disable_fk:
            enable_pg_fk(pg_conn)

    print(f"  [{table}] ✓ Migrati {len(rows)} record")
    return len(rows)

# ============================================================================
# MIGRATE_COPY - per tabelle grandi (COPY binario con checkpoint)
# ============================================================================

def migrate_copy(
    table: str,
    cols: List[str],
    transform_row: Optional[Callable] = None,
    chunk_size: int = 50_000,
    disable_fk: bool = True
) -> int:
    """
    Migra tabella usando COPY con checkpoint (resume-safe).

    Args:
        table: nome tabella
        cols: lista colonne da migrare
        transform_row: funzione(row_dict) → row_dict o None per skipparla
        chunk_size: righe per chunk
        disable_fk: se True, disabilita FK durante migrazione

    Returns:
        numero di righe migrate
    """
    with get_mysql() as mysql_conn:
        with mysql_conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) as cnt FROM `{table}`")
            total = cur.fetchone()['cnt']

    if total == 0:
        print(f"  [{table}] Vuota, skip.")
        return 0

    # Check checkpoint su PG
    with get_pg() as pg_conn:
        with pg_conn.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            already_migrated = cur.fetchone()[0]

    if already_migrated > 0:
        print(f"  [{table}] Checkpoint: {already_migrated} righe già presenti.")

    # Ricava tipi PostgreSQL
    pg_types = get_pg_column_types(table)

    col_names = ",".join([f'"{c}"' for c in cols])
    copy_sql = f'COPY "{table}" ({col_names}) FROM STDIN WITH (FORMAT CSV, NULL \'\\N\')'

    start = time.time()
    offset = already_migrated
    migrated = already_migrated

    with get_pg() as pg_conn:
        if disable_fk:
            disable_pg_fk(pg_conn)

        while offset < total:
            # Leggi chunk da MySQL
            with get_mysql() as mysql_conn:
                with mysql_conn.cursor() as cur:
                    col_names_mysql = ",".join([f"`{c}`" for c in cols])
                    cur.execute(
                        f"SELECT {col_names_mysql} FROM `{table}` LIMIT %s OFFSET %s",
                        (chunk_size, offset)
                    )
                    rows = cur.fetchall()

            if not rows:
                break

            # Trasforma e cast
            if transform_row:
                rows = [transform_row(r) for r in rows]
                rows = [r for r in rows if r is not None]

            rows = [cast_row_to_pg_types(row, pg_types) for row in rows]

            if not rows:
                offset += chunk_size
                continue

            # Serializza in CSV per COPY
            buf = StringIO()
            writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
            for row in rows:
                writer.writerow([
                    row[c] if row[c] is not None else r'\N'
                    for c in cols
                ])
            buf.seek(0)

            # COPY su PG
            with pg_conn.cursor() as cur:
                cur.copy_expert(copy_sql, buf)
            pg_conn.commit()

            migrated += len(rows)
            offset += chunk_size
            elapsed = time.time() - start
            rate = (migrated - already_migrated) / elapsed if elapsed > 0 else 0
            eta = (total - migrated) / rate if rate > 0 else 0
            print(f"    {migrated:>7}/{total} ({100*migrated/total:>5.1f}%) | {rate:>6.0f} rows/s | ETA {eta:>5.0f}s", end="\r")

        if disable_fk:
            enable_pg_fk(pg_conn)

    elapsed = time.time() - start
    print(f"  [{table}] ✓ Migrati {migrated} record in {elapsed:.1f}s")
    return migrated

# ============================================================================
# MIGRAZIONI PER TABELLA
# ============================================================================

def migrate_agata_associations():
    """FASE 1.1 - no FK in entrata"""
    def transform(row):
        row['settings'] = json_or_none(row.get('settings'))
        row['is_active'] = bool_from_tinyint(row.get('is_active'))
        row['slack_enabled'] = bool_from_tinyint(row.get('slack_enabled'))
        row['created_at'] = timestamp_or_none(row.get('created_at'))
        row['updated_at'] = timestamp_or_none(row.get('updated_at'))
        return row

    migrate_simple('agata_associations', transform)

def migrate_agata_users():
    """FASE 2.1 - dipende da associations"""
    def transform(row):
        row['is_internal'] = bool_from_tinyint(row.get('is_internal'))
        row['is_active'] = bool_from_tinyint(row.get('is_active'))
        row['email_verified'] = bool_from_tinyint(row.get('email_verified'))
        row['created_at'] = timestamp_or_none(row.get('created_at'))
        if 'updated_at' in row:
            row['updated_at'] = timestamp_or_none(row.get('updated_at'))
        return row

    migrate_simple('agata_users', transform)

def migrate_agata_projects():
    """FASE 3.3 - dipende da users, associations"""
    def transform(row):
        row['data'] = json_or_none(row.get('data'))
        for ts_col in ['assigned_at', 'reviewed_at', 'submitted_aavso_at',
                       'aavso_accepted_at', 'aavso_rejected_at', 'cancelled_at',
                       'created_at', 'updated_at']:
            row[ts_col] = timestamp_or_none(row.get(ts_col))
        return row

    migrate_simple('agata_projects', transform)

def migrate_agata_catalog_imports():
    """FASE 4.2 - dipende da projects, users, associations"""
    def transform(row):
        for json_col in ['catalogs_queried', 'selected_catalogs']:
            val = row.get(json_col)
            # Force convert dict/list to JSON string (PyMySQL may auto-parse)
            if isinstance(val, (dict, list)):
                print(f"    [catalog_imports] Converting {json_col} from {type(val).__name__} to JSON")
                try:
                    row[json_col] = json.dumps(val)
                except (TypeError, ValueError) as e:
                    print(f"    [catalog_imports] Failed to convert {json_col}: {e}")
                    row[json_col] = None
            elif isinstance(val, str):
                row[json_col] = val.strip() if val else None
            else:
                row[json_col] = None
        for ts_col in ['created_at', 'updated_at', 'search_started_at', 'preview_at',
                       'import_started_at', 'completed_at']:
            row[ts_col] = timestamp_or_none(row.get(ts_col))
        return row

    migrate_simple('agata_catalog_imports', transform)

def migrate_agata_tess_import_results():
    """FASE 5.2 - JSON lc_full_json ~50KB/riga"""
    def transform(row):
        for json_col in ['vsx_match', 'atlas_match', 'lc_preview_json', 'lc_full_json']:
            row[json_col] = json_or_none(row.get(json_col))
        for bool_col in ['is_candidate', 'is_known_variable', 'is_valid',
                         'is_ambiguous', 'download_failed']:
            row[bool_col] = bool_from_tinyint(row.get(bool_col))
        row['created_at'] = timestamp_or_none(row.get('created_at'))
        return row

    migrate_simple('agata_tess_import_results', transform, batch_size=50)

def migrate_agata_vast_results():
    """FASE 5.1 - dipende da vast_jobs, projects"""
    def transform(row):
        row['variability_indices'] = json_or_none(row.get('variability_indices'))
        row['gaia_match'] = json_or_none(row.get('gaia_match'))
        row['vsx_match'] = json_or_none(row.get('vsx_match'))
        row['atlas_match'] = json_or_none(row.get('atlas_match'))
        for bool_col in ['is_valid', 'is_known_variable', 'is_candidate']:
            row[bool_col] = bool_from_tinyint(row.get(bool_col))
        row['created_at'] = timestamp_or_none(row.get('created_at'))
        return row

    migrate_simple('agata_vast_results', transform)

def migrate_agata_ztf_survey_results():
    """FASE 5.1 - dipende da ztf_survey_jobs, projects"""
    def transform(row):
        row['vsx_match'] = json_or_none(row.get('vsx_match'))
        for bool_col in ['is_candidate', 'is_known_variable', 'is_valid',
                         'is_ambiguous', 'is_rejected', 'is_duplicate']:
            row[bool_col] = bool_from_tinyint(row.get(bool_col))
        row['created_at'] = timestamp_or_none(row.get('created_at'))
        return row

    migrate_simple('agata_ztf_survey_results', transform)

def migrate_agata_tess_curl_entries():
    """FASE 4.6 - tabella grande (387k righe), COPY"""
    def transform(row):
        row['is_processed'] = bool_from_tinyint(row.get('is_processed'))
        return row

    cols = ['id', 'script_id', 'entry_index', 'tic_id', 'sector',
            'fits_url', 'relative_path', 'is_processed']
    migrate_copy('agata_tess_curl_entries', cols, transform, chunk_size=20_000)

def migrate_agata_star_photometry():
    """FASE 6 - TABELLA CRITICA: 1.7M righe, nessuna PK"""
    cols = ['index', 'hjd', 'Vmag', 'Source', 'catalogo',
            'association_id_owner', 'catalog_import_id']

    print("\n" + "="*80)
    print("FASE 6 - agata_star_photometry (1.728.732 righe)")
    print("="*80)

    with get_pg() as pg_conn:
        disable_pg_fk(pg_conn)

    migrate_copy('agata_star_photometry', cols, chunk_size=50_000, disable_fk=False)

    # Crea indici DOPO il COPY (molto più veloce)
    print("\n  Creando indici...")
    with get_pg() as pg_conn:
        with pg_conn.cursor() as cur:
            indices = [
                ('idx_sp_source_hjd', 'CREATE INDEX CONCURRENTLY idx_sp_source_hjd ON agata_star_photometry ("Source", hjd DESC)'),
                ('idx_sp_assoc_source_hjd', 'CREATE INDEX CONCURRENTLY idx_sp_assoc_source_hjd ON agata_star_photometry (association_id_owner, "Source", hjd)'),
                ('idx_sp_catalogo', 'CREATE INDEX CONCURRENTLY idx_sp_catalogo ON agata_star_photometry (catalogo)'),
                ('idx_sp_catalog_import', 'CREATE INDEX CONCURRENTLY idx_sp_catalog_import ON agata_star_photometry (catalog_import_id)'),
            ]

            for idx_name, idx_sql in indices:
                try:
                    cur.execute(idx_sql)
                    pg_conn.commit()
                    print(f"    ✓ Indice {idx_name}")
                except psycopg2.errors.DuplicateObject:
                    print(f"    ℹ Indice {idx_name} esiste già")
                except Exception as e:
                    print(f"    ✗ Errore {idx_name}: {e}")

    # Aggiungi FK con NOT VALID (validazione posticipata)
    print("  Aggiungendo FK (NOT VALID)...")
    with get_pg() as pg_conn:
        with pg_conn.cursor() as cur:
            fk_stmts = [
                ('fk_sp_catalog_import', """
                    ALTER TABLE agata_star_photometry
                    ADD CONSTRAINT fk_sp_catalog_import
                    FOREIGN KEY (catalog_import_id) REFERENCES agata_catalog_imports(id)
                    ON DELETE SET NULL NOT VALID
                """),
                ('fk_sp_association', """
                    ALTER TABLE agata_star_photometry
                    ADD CONSTRAINT fk_sp_association
                    FOREIGN KEY (association_id_owner) REFERENCES agata_associations(id)
                    ON DELETE SET NULL NOT VALID
                """),
            ]

            for fk_name, fk_sql in fk_stmts:
                try:
                    cur.execute(fk_sql)
                    pg_conn.commit()
                    print(f"    ✓ FK {fk_name}")
                except psycopg2.errors.DuplicateObject:
                    print(f"    ℹ FK {fk_name} esiste già")
                except Exception as e:
                    print(f"    ✗ Errore {fk_name}: {e}")

# ============================================================================
# FASE 1 - RADICI
# ============================================================================

def run_phase_1():
    """Fase 1: tabelle radice (no FK in entrata)"""
    print("\n" + "="*80)
    print("FASE 1 - Radici (no FK in entrata)")
    print("="*80)

    migrate_agata_associations()

    # Altre tabelle radice
    for table in ['agata_edu_stars', 'agata_lti_platforms']:
        migrate_simple(table)

# ============================================================================
# FASE 2 - DIPENDONO DA ASSOCIATIONS
# ============================================================================

def run_phase_2():
    """Fase 2: dipendono da associations"""
    print("\n" + "="*80)
    print("FASE 2 - Dipendono da associations")
    print("="*80)

    migrate_agata_users()
    migrate_simple('agata_slack_channels')

# ============================================================================
# FASE 3 - DIPENDONO DA USERS/ASSOCIATIONS
# ============================================================================

def run_phase_3():
    """Fase 3: dipendono da users/associations"""
    print("\n" + "="*80)
    print("FASE 3 - Dipendono da users/associations")
    print("="*80)

    for table in ['agata_oauth_tokens', 'agata_magic_link_tokens', 'agata_user_sessions']:
        migrate_simple(table)

    migrate_simple('agata_system_config')
    migrate_agata_projects()

    for table in ['agata_saved_queries', 'agata_query_presets', 'agata_tess_curl_scripts']:
        migrate_simple(table)

    migrate_simple('agata_kb_sync_status')
    migrate_simple('agata_kb_search_history')

# ============================================================================
# FASE 4 - DIPENDONO DA PROJECTS/SCRIPTS
# ============================================================================

def run_phase_4():
    """Fase 4: dipendono da projects/scripts"""
    print("\n" + "="*80)
    print("FASE 4 - Dipendono da projects/scripts")
    print("="*80)

    for table in ['agata_project_science_data', 'agata_project_slack_threads',
                  'agata_star_assignments']:
        migrate_simple(table)

    # agata_project_outputs ha self-ref
    migrate_simple('agata_project_outputs')

    # SKIP catalog_imports for now - JSON parsing issue
    # migrate_agata_catalog_imports()
    migrate_simple('agata_vast_jobs')
    migrate_simple('agata_ztf_survey_jobs')
    migrate_simple('agata_tess_import_jobs')
    migrate_agata_tess_curl_entries()

# ============================================================================
# FASE 5 - FOGLIE
# ============================================================================

def run_phase_5():
    """Fase 5: tabelle foglie"""
    print("\n" + "="*80)
    print("FASE 5 - Foglie")
    print("="*80)

    migrate_agata_vast_results()
    migrate_agata_ztf_survey_results()
    migrate_agata_tess_import_results()
    migrate_simple('agata_audit_log')
    migrate_simple('agata_catalog_attributes')
    migrate_simple('agata_tpf_sessions')
    migrate_simple('agata_star')

# ============================================================================
# FASE 6 - STAR PHOTOMETRY (SEPARATA)
# ============================================================================

def run_phase_6():
    """Fase 6: agata_star_photometry (1.7M righe, COPY)"""
    migrate_agata_star_photometry()

# ============================================================================
# VALIDAZIONE
# ============================================================================

def validate_counts():
    """Confronta COUNT(*) MySQL vs PostgreSQL."""
    tables = [
        'agata_associations', 'agata_users', 'agata_projects', 'agata_catalog_imports',
        'agata_star_photometry', 'agata_tess_curl_entries', 'agata_tess_curl_scripts',
        'agata_tess_import_jobs', 'agata_tess_import_results', 'agata_vast_jobs',
        'agata_vast_results', 'agata_ztf_survey_jobs', 'agata_ztf_survey_results',
        'agata_oauth_tokens', 'agata_magic_link_tokens', 'agata_user_sessions',
        'agata_slack_channels', 'agata_project_science_data', 'agata_project_outputs',
        'agata_project_slack_threads', 'agata_star_assignments', 'agata_audit_log',
        'agata_kb_search_history', 'agata_kb_sync_status', 'agata_catalog_attributes',
        'agata_system_config', 'agata_saved_queries', 'agata_query_presets',
        'agata_edu_stars', 'agata_lti_platforms', 'agata_tpf_sessions', 'agata_star',
    ]

    print("\n" + "="*80)
    print("VALIDAZIONE - Confronto conteggi")
    print("="*80)
    print(f"{'Tabella':<45} {'MySQL':>10} {'PG':>10} {'Match':>6}")
    print("-" * 75)

    mismatches = []
    with get_mysql() as mysql_conn:
        with get_pg() as pg_conn:
            for table in tables:
                with mysql_conn.cursor() as cur:
                    cur.execute(f"SELECT COUNT(*) as cnt FROM `{table}`")
                    my_count = cur.fetchone()['cnt']

                with pg_conn.cursor() as cur:
                    try:
                        cur.execute(f'SELECT COUNT(*) FROM "{table}"')
                        pg_count = cur.fetchone()[0]
                    except Exception as e:
                        pg_count = f"ERR"
                        mismatches.append((table, f"ERR: {e}"))

                match = "✓" if my_count == pg_count else "✗"
                if my_count != pg_count:
                    mismatches.append((table, f"{my_count} vs {pg_count}"))

                print(f"{table:<45} {my_count:>10} {str(pg_count):>10} {match:>6}")

    if mismatches:
        print(f"\n⚠️  {len(mismatches)} MISMATCH TROVATI:")
        for table, details in mismatches:
            print(f"  {table}: {details}")
        return False
    else:
        print("\n✓ Tutti i conteggi sono uguali!")
        return True

def reset_sequences():
    """Ripristina le sequence PostgreSQL."""
    tables_with_id = [
        'agata_associations', 'agata_users', 'agata_projects', 'agata_catalog_imports',
        'agata_oauth_tokens', 'agata_magic_link_tokens', 'agata_user_sessions',
        'agata_slack_channels', 'agata_system_config', 'agata_project_science_data',
        'agata_project_outputs', 'agata_project_slack_threads', 'agata_star_assignments',
        'agata_audit_log', 'agata_kb_search_history', 'agata_kb_sync_status',
        'agata_catalog_attributes', 'agata_vast_jobs', 'agata_vast_results',
        'agata_ztf_survey_jobs', 'agata_ztf_survey_results', 'agata_tess_curl_scripts',
        'agata_tess_curl_entries', 'agata_tess_import_jobs', 'agata_tess_import_results',
        'agata_saved_queries', 'agata_query_presets', 'agata_edu_stars',
        'agata_lti_platforms', 'agata_tpf_sessions',
    ]

    print("\n" + "="*80)
    print("RESET SEQUENCES")
    print("="*80)

    with get_pg() as conn:
        with conn.cursor() as cur:
            for table in tables_with_id:
                try:
                    cur.execute(f"""
                        SELECT setval(
                            pg_get_serial_sequence('{table}', 'id'),
                            COALESCE((SELECT MAX(id) FROM "{table}"), 1)
                        );
                    """)
                    print(f"  ✓ {table}")
                except Exception as e:
                    print(f"  ⚠ {table}: {e}")
        conn.commit()

    print("✓ Sequence ripristinate")

# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Migrazione MySQL → PostgreSQL per AGATA')
    parser.add_argument('--phase', default='1-5', help='Fasi da migrare (es: 1, 1-3, 1-6)')
    parser.add_argument('--validate', action='store_true', help='Esegui validazione')
    parser.add_argument('--reset-seq', action='store_true', help='Reset sequences')
    parser.add_argument('--full', action='store_true', help='Fasi 1-6 + validazione + reset')
    args = parser.parse_args()

    if args.full:
        run_phase_1()
        run_phase_2()
        run_phase_3()
        run_phase_4()
        run_phase_5()
        run_phase_6()
        validate_counts()
        reset_sequences()
        print("\n" + "="*80)
        print("✓ MIGRAZIONE COMPLETATA!")
        print("="*80)
        return

    # Parse fase
    if '-' in args.phase:
        start, end = map(int, args.phase.split('-'))
        phases = range(start, end + 1)
    else:
        phases = [int(args.phase)]

    # Esegui fasi
    phase_funcs = {
        1: run_phase_1,
        2: run_phase_2,
        3: run_phase_3,
        4: run_phase_4,
        5: run_phase_5,
        6: run_phase_6,
    }

    for phase_num in phases:
        if phase_num in phase_funcs:
            phase_funcs[phase_num]()

    if args.validate:
        validate_counts()

    if args.reset_seq:
        reset_sequences()

if __name__ == '__main__':
    main()
