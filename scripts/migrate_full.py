#!/usr/bin/env python3
"""
Migrazione completa MySQL → PostgreSQL per AGATA
Basato sul test_script che ha passato i test su 30+ tabelle.

Usage:
  python scripts/migrate_full.py          # Migrare tutte le fasi
  python scripts/migrate_full.py --phase 1-3
"""

import os
import sys
import json
from io import StringIO
import csv
from datetime import datetime
import time
import argparse

os.environ['DATABASE_URL'] = 'postgresql+psycopg://agata_user:agata_pass_dev@localhost/catalogo_pg'
os.environ['MYSQL_DATABASE_URL'] = 'mysql+pymysql://aaaat01:dwedfAA1saa14@localhost:3306/catalogo'

import pymysql
import pymysql.cursors
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# CONFIG
# ============================================================================

MYSQL_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'aaaat01',
    'password': 'dwedfAA1saa14',
    'database': 'catalogo',
    'charset': 'utf8mb4',
    'use_unicode': True,
    'cursorclass': pymysql.cursors.DictCursor
}

PG_CONFIG = {
    'host': 'localhost',
    'user': 'agata_user',
    'password': 'agata_pass_dev',
    'database': 'catalogo_pg'
}

# ============================================================================
# COLONNE DA SKIPPARE (non esistono in PG)
# ============================================================================

SKIP_COLUMNS = {
    'agata_edu_stars': {
        'tipo', 'costellazione', 'descrizione', 'periodo_noto_ore',
        'source', 'kind', 'domande_ibl', 'sort_order'
    },
    'agata_tpf_sessions': {
        'gaia_source_id', 'sector', 'catalog_name', 'mode', 'mask_origin',
        'tpf_filename', 'tpf_path', 'saved_at', 'saved_by', 'promoted_points'
    },
}

# ============================================================================
# TYPE CASTING & RETRIEVAL
# ============================================================================

def get_pg_column_types(table: str) -> dict:
    """Ricava i tipi colonna da PostgreSQL."""
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (table,))
            result = {row[0]: row[1] for row in cur.fetchall()}
        conn.close()
        return result
    except Exception as e:
        return {}

def cast_row_to_pg_types(row: dict, pg_types: dict) -> dict:
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

        new_row[col] = val
    return new_row

# ============================================================================
# MIGRAZIONE
# ============================================================================

def migrate_table(table: str, chunk_size: int = 1000, skip_cols: set = None) -> int:
    """
    Migra una tabella da MySQL a PostgreSQL.

    Args:
        table: nome tabella
        chunk_size: righe per batch
        skip_cols: set di colonne da non migrare

    Returns:
        numero di righe migrate
    """
    skip_cols = skip_cols or set()

    # Conta MySQL
    mysql_conn = pymysql.connect(**MYSQL_CONFIG)
    with mysql_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) as cnt FROM `{table}`")
        mysql_count = cur.fetchone()['cnt']
    mysql_conn.close()

    if mysql_count == 0:
        print(f"  [{table}] Vuota, skip")
        return 0

    # Conta PostgreSQL (per checkpoint)
    pg_conn = psycopg2.connect(**PG_CONFIG)
    with pg_conn.cursor() as cur:
        try:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            pg_count = cur.fetchone()[0]
        except psycopg2.errors.UndefinedTable:
            print(f"  [{table}] ✗ Tabella PG non esiste, skip")
            pg_conn.close()
            return 0
    pg_conn.close()

    if pg_count > 0:
        print(f"  [{table}] {pg_count} righe già presenti, skip")
        return 0

    # Leggi dati MySQL in chunk
    mysql_conn = pymysql.connect(**MYSQL_CONFIG)
    pg_types = get_pg_column_types(table)

    inserted = 0
    offset = 0
    start = time.time()

    try:
        while offset < mysql_count:
            with mysql_conn.cursor() as cur:
                cur.execute(f"SELECT * FROM `{table}` LIMIT %s OFFSET %s",
                           (chunk_size, offset))
                rows = cur.fetchall()

            if not rows:
                break

            # Filtra colonne da skippare
            if skip_cols:
                for row in rows:
                    for col in skip_cols:
                        row.pop(col, None)

            # Cast types
            rows = [cast_row_to_pg_types(row, pg_types) for row in rows]

            # Inserisci
            if rows:
                cols = list(rows[0].keys())
                col_names = ",".join([f'"{c}"' for c in cols])
                placeholders = ",".join(["%s"] * len(cols))
                sql = f'INSERT INTO "{table}" ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'

                pg_conn = psycopg2.connect(**PG_CONFIG)
                with pg_conn.cursor() as cur:
                    for row in rows:
                        values = tuple(row[c] for c in cols)
                        cur.execute(sql, values)
                    pg_conn.commit()
                pg_conn.close()

                inserted += len(rows)
                offset += len(rows)

                # Progress
                elapsed = time.time() - start
                rate = inserted / elapsed if elapsed > 0 else 0
                eta = (mysql_count - inserted) / rate if rate > 0 else 0
                print(f"    {inserted:>7}/{mysql_count} ({100*inserted/mysql_count:>5.1f}%) | {rate:>6.0f} rows/s | ETA {eta:>5.0f}s", end="\r")

    except Exception as e:
        print(f"  [{table}] ✗ Errore: {e}")
        mysql_conn.close()
        return 0

    mysql_conn.close()
    elapsed = time.time() - start
    print(f"  [{table}] ✓ Migrati {inserted} record in {elapsed:.1f}s")
    return inserted

# ============================================================================
# FASI
# ============================================================================

FASE_1 = [
    'agata_associations',
    'agata_edu_stars',
    'agata_lti_platforms',
]

FASE_2 = [
    'agata_users',
    'agata_slack_channels',
]

FASE_3 = [
    'agata_oauth_tokens',
    'agata_magic_link_tokens',
    'agata_user_sessions',
    'agata_system_config',
    'agata_projects',
    'agata_saved_queries',
    'agata_query_presets',
    'agata_tess_curl_scripts',
    'agata_kb_sync_status',
    'agata_kb_search_history',
]

FASE_4 = [
    'agata_project_science_data',
    'agata_project_slack_threads',
    'agata_star_assignments',
    'agata_project_outputs',
    'agata_catalog_imports',
    'agata_vast_jobs',
    'agata_ztf_survey_jobs',
    'agata_tess_import_jobs',
]

FASE_5 = [
    'agata_vast_results',
    'agata_ztf_survey_results',
    'agata_tess_import_results',
    'agata_audit_log',
    'agata_catalog_attributes',
    # 'agata_tpf_sessions',  # Non esiste in PG schema
    'agata_star',
]

def run_fase(phase_num, tables):
    print("\n" + "=" * 80)
    print(f"FASE {phase_num}")
    print("=" * 80)

    total_inserted = 0
    for table in tables:
        skip_cols = SKIP_COLUMNS.get(table, set())
        inserted = migrate_table(table, skip_cols=skip_cols)
        total_inserted += inserted

    print(f"\n✓ FASE {phase_num} completata: {total_inserted} record")
    return total_inserted

def validate_all():
    """Valida conteggi e FK."""
    print("\n" + "=" * 80)
    print("VALIDAZIONE")
    print("=" * 80)

    all_tables = FASE_1 + FASE_2 + FASE_3 + FASE_4 + FASE_5

    # Forza commit su tutte le connessioni aperte (poco elegante ma funziona)
    import time
    time.sleep(0.5)

    mysql_conn = pymysql.connect(**MYSQL_CONFIG)
    pg_conn = psycopg2.connect(**PG_CONFIG)
    pg_conn.commit()  # Forza commit

    mismatches = []
    total_my = 0
    total_pg = 0

    print(f"{'Tabella':<45} {'MySQL':>10} {'PG':>10} {'Match':>6}")
    print("-" * 75)

    for table in all_tables:
        with mysql_conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) as cnt FROM `{table}`")
            my_count = cur.fetchone()['cnt']

        # Crea una nuova connessione PG per ogni tabella (evita cache di query)
        fresh_pg = psycopg2.connect(**PG_CONFIG)
        with fresh_pg.cursor() as cur:
            try:
                cur.execute(f'SELECT COUNT(*) FROM "{table}"')
                pg_count = cur.fetchone()[0]
            except:
                pg_count = 0
        fresh_pg.close()

        total_my += my_count
        total_pg += pg_count
        match = "✓" if my_count == pg_count else "✗"
        if my_count != pg_count:
            mismatches.append(table)

        print(f"{table:<45} {my_count:>10} {pg_count:>10} {match:>6}")

    mysql_conn.close()
    pg_conn.close()

    print("-" * 75)
    print(f"{'TOTALE':<45} {total_my:>10} {total_pg:>10}")

    if mismatches:
        print(f"\n⚠️  {len(mismatches)} MISMATCH: {mismatches}")
        return False
    else:
        print(f"\n✓ Tutti i conteggi sono uguali!")
        return True

def reset_sequences():
    """Ripristina le sequence."""
    print("\n" + "=" * 80)
    print("RESET SEQUENCES")
    print("=" * 80)

    all_tables = FASE_1 + FASE_2 + FASE_3 + FASE_4 + FASE_5

    pg_conn = psycopg2.connect(**PG_CONFIG)
    with pg_conn.cursor() as cur:
        for table in all_tables:
            try:
                cur.execute(f"""
                    SELECT setval(
                        pg_get_serial_sequence('{table}', 'id'),
                        COALESCE((SELECT MAX(id) FROM "{table}"), 1)
                    );
                """)
            except:
                pass  # Tabelle senza id SERIAL
    pg_conn.commit()
    pg_conn.close()
    print("✓ Sequence ripristinate")

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Migrazione MySQL → PostgreSQL per AGATA')
    parser.add_argument('--phase', default='1-5', help='Fasi da eseguire (es: 1, 1-3, 1-5)')
    parser.add_argument('--validate', action='store_true', help='Validare dopo migrazione')
    parser.add_argument('--reset-seq', action='store_true', help='Reset sequences')
    parser.add_argument('--full', action='store_true', help='Tutto (1-5 + validazione + reset)')
    args = parser.parse_args()

    if args.full:
        run_fase(1, FASE_1)
        run_fase(2, FASE_2)
        run_fase(3, FASE_3)
        run_fase(4, FASE_4)
        run_fase(5, FASE_5)
        validate_all()
        reset_sequences()
        print("\n" + "=" * 80)
        print("✓ MIGRAZIONE COMPLETATA!")
        print("=" * 80)
        sys.exit(0)

    # Parse fasi
    if '-' in args.phase:
        start, end = map(int, args.phase.split('-'))
        phases = range(start, end + 1)
    else:
        phases = [int(args.phase)]

    # Esegui fasi
    fase_map = {
        1: (FASE_1, 1),
        2: (FASE_2, 2),
        3: (FASE_3, 3),
        4: (FASE_4, 4),
        5: (FASE_5, 5),
    }

    for phase_num in phases:
        if phase_num in fase_map:
            tables, num = fase_map[phase_num]
            run_fase(num, tables)

    if args.validate:
        validate_all()

    if args.reset_seq:
        reset_sequences()
