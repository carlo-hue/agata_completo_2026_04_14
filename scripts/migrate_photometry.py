#!/usr/bin/env python3
"""
Migrazione agata_star_photometry (1.728.732 righe da MySQL)

Questa tabella è critica e ha schema modificato in PostgreSQL.
Strategy: COPY binario in chunk, progress bar, con checkpoint.

Tempo stimato: 5-10 minuti a seconda dell'hardware.
"""

import os
import sys
import time
import csv
from io import StringIO

os.environ['DATABASE_URL'] = 'postgresql+psycopg://agata_user:agata_pass_dev@localhost/catalogo_pg'

import pymysql
import pymysql.cursors
import psycopg2
from dotenv import load_dotenv

load_dotenv()

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

def migrate_photometry():
    """Migra agata_star_photometry usando COPY binario."""

    print("=" * 80)
    print("MIGRAZIONE: agata_star_photometry (1.7M+ righe)")
    print("=" * 80)

    # Conta MySQL
    mysql_conn = pymysql.connect(**MYSQL_CONFIG)
    with mysql_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) as cnt FROM agata_star_photometry")
        mysql_count = cur.fetchone()['cnt']
    print(f"\nMySQL: {mysql_count:,} righe")

    # Conta PostgreSQL (checkpoint)
    pg_conn = psycopg2.connect(**PG_CONFIG)
    with pg_conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM "agata_star_photometry"')
        pg_count = cur.fetchone()[0]
    pg_conn.close()

    if pg_count > 0:
        print(f"PostgreSQL: {pg_count:,} righe già presenti, skip")
        return

    # Colonne MySQL → PostgreSQL
    # MySQL: index, hjd, Vmag, Source, catalogo, association_id_owner, catalog_import_id
    # PG: hjd, vmag, source_id, catalogo, association_id_owner, catalog_import_id
    # (no 'index' in PG, rinominato Source→source_id, Vmag→vmag)

    cols_mysql = ['index', 'hjd', 'Vmag', 'Source', 'catalogo', 'association_id_owner', 'catalog_import_id']
    cols_pg = ['hjd', 'vmag', 'source_id', 'catalogo', 'association_id_owner', 'catalog_import_id']

    print(f"Colonne MySQL: {cols_mysql}")
    print(f"Colonne PG: {cols_pg}")
    print()

    # COPY statement
    col_names = ",".join([f'"{c}"' for c in cols_pg])
    copy_sql = f'COPY "agata_star_photometry" ({col_names}) FROM STDIN WITH (FORMAT CSV, NULL \'\\N\')'

    # Migra in chunk
    chunk_size = 50_000
    offset = 0
    migrated = 0
    start = time.time()

    pg_conn = psycopg2.connect(**PG_CONFIG)

    try:
        while offset < mysql_count:
            # Leggi chunk MySQL
            mysql_conn = pymysql.connect(**MYSQL_CONFIG)
            with mysql_conn.cursor() as cur:
                cur.execute(f"""
                    SELECT `index`, hjd, Vmag, Source, catalogo, association_id_owner, catalog_import_id
                    FROM agata_star_photometry
                    LIMIT %s OFFSET %s
                """, (chunk_size, offset))
                rows = cur.fetchall()
            mysql_conn.close()

            if not rows:
                break

            # Serializza in CSV (mappa colonne MySQL → PG)
            buf = StringIO()
            writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
            for row in rows:
                # Mappa: index (skip), hjd, Vmag→vmag, Source→source_id, catalogo, association_id_owner, catalog_import_id
                writer.writerow([
                    row['hjd'] if row['hjd'] is not None else r'\N',
                    row['Vmag'] if row['Vmag'] is not None else r'\N',
                    row['Source'] if row['Source'] is not None else r'\N',
                    row['catalogo'] if row['catalogo'] is not None else r'\N',
                    row['association_id_owner'] if row['association_id_owner'] is not None else r'\N',
                    row['catalog_import_id'] if row['catalog_import_id'] is not None else r'\N',
                ])
            buf.seek(0)

            # COPY su PG
            with pg_conn.cursor() as cur:
                cur.copy_expert(copy_sql, buf)
            pg_conn.commit()

            migrated += len(rows)
            offset += len(rows)

            # Progress
            elapsed = time.time() - start
            rate = migrated / elapsed if elapsed > 0 else 0
            eta = (mysql_count - migrated) / rate if rate > 0 else 0
            pct = 100 * migrated / mysql_count

            # Detailed progress bar
            bar_width = 40
            bar_filled = int(bar_width * migrated / mysql_count)
            bar = "█" * bar_filled + "░" * (bar_width - bar_filled)

            print(f"\r  [{bar}] {migrated:>9,}/{mysql_count:,} ({pct:>5.1f}%) | {rate:>6.0f} rows/s | ETA {eta:>6.0f}s", end="", flush=True)

        print()  # newline

    except Exception as e:
        print(f"\n✗ Errore: {e}")
        pg_conn.close()
        mysql_conn.close()
        return False

    pg_conn.close()

    elapsed = time.time() - start
    print(f"\n✓ Migrazione completata: {migrated:,} righe in {elapsed:.1f}s ({migrated/elapsed:.0f} rows/s)")

    # Crea indici
    print("\nCreazione indici...")
    pg_conn = psycopg2.connect(**PG_CONFIG)
    with pg_conn.cursor() as cur:
        indices = [
            ('idx_sp_source_hjd', 'CREATE INDEX CONCURRENTLY idx_sp_source_hjd ON agata_star_photometry ("Source", hjd DESC)'),
            ('idx_sp_assoc_source_hjd', 'CREATE INDEX CONCURRENTLY idx_sp_assoc_source_hjd ON agata_star_photometry (association_id_owner, "Source", hjd)'),
            ('idx_sp_catalogo', 'CREATE INDEX CONCURRENTLY idx_sp_catalogo ON agata_star_photometry (catalogo)'),
            ('idx_sp_catalog_import', 'CREATE INDEX CONCURRENTLY idx_sp_catalog_import ON agata_star_photometry (catalog_import_id)'),
        ]

        for idx_name, idx_sql in indices:
            try:
                print(f"  {idx_name}...", end=' ', flush=True)
                cur.execute(idx_sql)
                pg_conn.commit()
                print("✓")
            except Exception as e:
                print(f"⚠ {e}")

    # Aggiungi FK
    print("\nAggiunta FK (NOT VALID)...")
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
                print(f"  {fk_name}...", end=' ', flush=True)
                cur.execute(fk_sql)
                pg_conn.commit()
                print("✓")
            except Exception as e:
                print(f"⚠ {e}")

    pg_conn.close()

    print("\n" + "=" * 80)
    print("✓ MIGRAZIONE agata_star_photometry COMPLETATA!")
    print("=" * 80)
    return True

if __name__ == '__main__':
    success = migrate_photometry()
    sys.exit(0 if success else 1)
