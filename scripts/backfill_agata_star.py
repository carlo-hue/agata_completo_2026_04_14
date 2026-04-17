#!/usr/bin/env python3
"""
One-time backfill: populates agata_star from existing database state.

Run AFTER deploying update hooks (Phase 3) and BEFORE enabling Phase 4 query.
This script is idempotent - safe to re-run.

Usage:
    cd /var/www/astrogen
    python scripts/backfill_agata_star.py [--dry-run] [--batch-size 200]
"""
import sys
import argparse
import logging
from datetime import datetime

# Setup path
sys.path.insert(0, '/var/www/astrogen')

from agata.db import SessionLocal
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def backfill(dry_run: bool = False, batch_size: int = 200):
    db = SessionLocal()
    try:
        # ===== STEP 1: Get all distinct Gaia IDs from agata_star_photometry =====
        logger.info("Step 1: Fetching distinct Gaia IDs from agata_star_photometry...")
        gaia_ids = [
            str(row[0]) for row in db.execute(text(
                "SELECT DISTINCT source_id FROM agata_star_photometry WHERE source_id IS NOT NULL"
            )).fetchall()
        ]
        logger.info(f"Found {len(gaia_ids)} distinct Gaia IDs")

        # ===== STEP 2: Process in batches =====
        total_upserted = 0
        for batch_start in range(0, len(gaia_ids), batch_size):
            batch = gaia_ids[batch_start:batch_start + batch_size]
            placeholders = ','.join([f':g{i}' for i in range(len(batch))])
            params = {f'g{i}': gid for i, gid in enumerate(batch)}

            # --- 2a. Photometry aggregates from agata_star_photometry ---
            phot_rows = db.execute(text(f"""
                SELECT
                    source_id::text as gaia_id,
                    COUNT(*) as total_points,
                    COUNT(DISTINCT catalogo) as num_catalogs,
                    STRING_AGG(DISTINCT catalogo, ',' ORDER BY catalogo) as catalogs,
                    MIN(hjd) as min_hjd,
                    MAX(hjd) as max_hjd,
                    MIN(vmag) as min_mag,
                    MAX(vmag) as max_mag,
                    MAX(catalog_import_id) as latest_import_id
                FROM agata_star_photometry
                WHERE source_id IN ({placeholders})
                GROUP BY source_id
            """), params).fetchall()

            # --- 2b. latest_import_id -> created_at from agata_catalog_imports ---
            import_ids = list({r.latest_import_id for r in phot_rows if r.latest_import_id})
            import_dates = {}
            if import_ids:
                imp_ph = ','.join([f':imp{i}' for i in range(len(import_ids))])
                imp_rows = db.execute(text(f"""
                    SELECT id, created_at FROM agata_catalog_imports
                    WHERE id IN ({imp_ph})
                """), {f'imp{i}': iid for i, iid in enumerate(import_ids)}).fetchall()
                import_dates = {r.id: r.created_at for r in imp_rows}

            # --- 2c. VAST data ---
            # NOTE: is_known_variable è settato SOLO da VSX + Gaia flags (esclude ATLAS per filtro catalogo)
            vast_rows = db.execute(text(f"""
                SELECT
                    gaia_source_id::text as gaia_id,
                    MAX(is_known_variable) as is_known_variable,
                    STRING_AGG(DISTINCT variable_type, ',') as variable_types,
                    STRING_AGG(DISTINCT catalog_matches, ',') as catalog_matches
                FROM agata_vast_results
                WHERE gaia_source_id IN ({placeholders})
                  AND is_valid = 1
                GROUP BY gaia_source_id
            """), params).fetchall()
            vast_map = {r.gaia_id: r for r in vast_rows}

            # --- 2d. Assignment counts ---
            assign_rows = db.execute(text(f"""
                SELECT gaia_id, COUNT(*) as cnt
                FROM agata_star_assignments
                WHERE gaia_id IN ({placeholders})
                GROUP BY gaia_id
            """), params).fetchall()
            assign_map = {r.gaia_id: r.cnt for r in assign_rows}

            # --- 2e. Active project flag ---
            project_rows = db.execute(text(f"""
                SELECT DISTINCT gaia_id
                FROM agata_projects
                WHERE gaia_id IN ({placeholders})
                  AND state != 'cancelled'
            """), params).fetchall()
            project_set = {r.gaia_id for r in project_rows}

            # --- 2f. Coordinates from agata_projects (best available) ---
            coord_rows = db.execute(text(f"""
                SELECT gaia_id, ra, dec_deg
                FROM agata_projects
                WHERE gaia_id IN ({placeholders})
                  AND ra IS NOT NULL
                LIMIT 1
            """), params).fetchall()
            coord_map = {r.gaia_id: (r.ra, r.dec_deg) for r in coord_rows}

            # --- 2g. UPSERT batch ---
            for row in phot_rows:
                gid = str(row.gaia_id)
                vast = vast_map.get(gid)
                import_id = row.latest_import_id
                imported_at = import_dates.get(import_id) if import_id else None
                coords = coord_map.get(gid, (None, None))

                upsert_sql = text("""
                    INSERT INTO agata_star
                        (gaia_id, ra, dec_deg, total_points, num_catalogs, catalogs,
                         min_hjd, max_hjd, min_mag, max_mag,
                         latest_import_id, last_imported_at,
                         is_known_variable, variable_types, catalog_matches,
                         num_assignments, has_active_project,
                         created_at, updated_at)
                    VALUES
                        (:gaia_id, :ra, :dec_deg, :total_points, :num_catalogs, :catalogs,
                         :min_hjd, :max_hjd, :min_mag, :max_mag,
                         :latest_import_id, :last_imported_at,
                         :is_known_variable, :variable_types, :catalog_matches,
                         :num_assignments, :has_active_project,
                         NOW(), NOW())
                    ON CONFLICT (gaia_id) DO UPDATE SET
                        ra                = EXCLUDED.ra,
                        dec_deg           = EXCLUDED.dec_deg,
                        total_points      = EXCLUDED.total_points,
                        num_catalogs      = EXCLUDED.num_catalogs,
                        catalogs          = EXCLUDED.catalogs,
                        min_hjd           = EXCLUDED.min_hjd,
                        max_hjd           = EXCLUDED.max_hjd,
                        min_mag           = EXCLUDED.min_mag,
                        max_mag           = EXCLUDED.max_mag,
                        latest_import_id  = EXCLUDED.latest_import_id,
                        last_imported_at  = EXCLUDED.last_imported_at,
                        is_known_variable = EXCLUDED.is_known_variable,
                        variable_types    = EXCLUDED.variable_types,
                        catalog_matches   = EXCLUDED.catalog_matches,
                        num_assignments   = EXCLUDED.num_assignments,
                        has_active_project = EXCLUDED.has_active_project,
                        updated_at        = NOW()
                """)

                if not dry_run:
                    db.execute(upsert_sql, {
                        'gaia_id': gid,
                        'ra': coords[0],
                        'dec_deg': coords[1],
                        'total_points': row.total_points,
                        'num_catalogs': row.num_catalogs,
                        'catalogs': row.catalogs,
                        'min_hjd': row.min_hjd,
                        'max_hjd': row.max_hjd,
                        'min_mag': row.min_mag,
                        'max_mag': row.max_mag,
                        'latest_import_id': import_id,
                        'last_imported_at': imported_at,
                        'is_known_variable': int(vast.is_known_variable) if vast else 0,
                        'variable_types': vast.variable_types if vast else None,
                        'catalog_matches': vast.catalog_matches if vast else None,
                        'num_assignments': assign_map.get(gid, 0),
                        'has_active_project': 1 if gid in project_set else 0,
                    })

                total_upserted += 1

            if not dry_run:
                db.commit()

            logger.info(
                f"Batch {batch_start//batch_size + 1}: "
                f"processed {batch_start + len(batch)}/{len(gaia_ids)} stars"
            )

        logger.info(f"Backfill complete. Total upserted: {total_upserted}")
        if dry_run:
            logger.info("DRY RUN - no changes committed")

    finally:
        db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--batch-size', type=int, default=200)
    args = parser.parse_args()
    backfill(dry_run=args.dry_run, batch_size=args.batch_size)
