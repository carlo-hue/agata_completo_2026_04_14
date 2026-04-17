import logging
from sqlalchemy import text
from agata.core.db.registry import db_route

logger = logging.getLogger(__name__)


@db_route('stars/upsert')
def upsert_star(payload: dict, db):
    """
    Upsert agata_star calcolando aggregati da agata_star_photometry.

    Replica la logica di star_service.upsert_star_photometry() con gestione
    della sessione delegata al dispatcher.

    Args:
        payload: {'gaia_id': str}
        db: SQLAlchemy session (gestita dal dispatcher)

    Returns:
        dict con gaia_id e total_points, oppure None se nessuna fotometria trovata
    """
    gaia_id = str(payload['gaia_id']).strip()
    # CRITICAL: agata_star_photometry.Source è BIGINT — serve int
    gaia_id_int = int(gaia_id)

    row = db.execute(text("""
        SELECT
            COUNT(*) as total_points,
            COUNT(DISTINCT catalogo) as num_catalogs,
            STRING_AGG(DISTINCT catalogo, ',' ORDER BY catalogo) as catalogs,
            MIN(hjd) as min_hjd,
            MAX(hjd) as max_hjd,
            MIN(vmag) as min_mag,
            MAX(vmag) as max_mag,
            MAX(catalog_import_id) as latest_import_id
        FROM agata_star_photometry
        WHERE source_id = :gaia_id_int
        GROUP BY source_id
    """), {'gaia_id_int': gaia_id_int}).fetchone()

    if not row or not row.total_points:
        logger.debug(f"Nessuna fotometria per gaia_id={gaia_id}, upsert saltato")
        return None

    imported_at = None
    if row.latest_import_id:
        imp = db.execute(text(
            "SELECT created_at FROM agata_catalog_imports WHERE id = :iid"
        ), {'iid': row.latest_import_id}).fetchone()
        if imp:
            imported_at = imp.created_at

    db.execute(text("""
        INSERT INTO agata_star
            (gaia_id, total_points, num_catalogs, catalogs,
             min_hjd, max_hjd, min_mag, max_mag,
             latest_import_id, last_imported_at,
             created_at, updated_at)
        VALUES
            (:gaia_id, :total_points, :num_catalogs, :catalogs,
             :min_hjd, :max_hjd, :min_mag, :max_mag,
             :latest_import_id, :last_imported_at,
             NOW(), NOW())
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
    """), {
        'gaia_id': gaia_id,
        'total_points': row.total_points,
        'num_catalogs': row.num_catalogs,
        'catalogs': row.catalogs,
        'min_hjd': row.min_hjd,
        'max_hjd': row.max_hjd,
        'min_mag': row.min_mag,
        'max_mag': row.max_mag,
        'latest_import_id': row.latest_import_id,
        'last_imported_at': imported_at,
    })

    return {'gaia_id': gaia_id, 'total_points': row.total_points}
