# agata/admin/services/star_service.py
"""
Star Service

Business logic per aggiornamento cache agata_star.
Separato dalla route stars_catalog.py per rispettare la layering:
  services -> models/DB
  routes   -> services  (mai services -> routes)
"""
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


def upsert_star_photometry(db: Session, gaia_id: str) -> None:
    """
    Recalcola e UPSERT agata_star dalla fotometria live in agata_star_photometry.

    Chiamato dopo ogni import fotometrico per mantenere aggiornata la cache
    di riepilogo usata dalla pagina stars-catalog.

    Non solleva mai eccezioni: gli errori sono loggati come warning
    per non bloccare il flusso di import del caller.

    Args:
        db: SQLAlchemy session (già aperta dal caller)
        gaia_id: Gaia DR3 source ID (stringa o intero)
    """
    try:
        gaia_id = str(gaia_id).strip()
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
            return

        imported_at = None
        if row.latest_import_id:
            imp = db.execute(text(
                "SELECT created_at FROM agata_catalog_imports WHERE id = :iid"
            ), {'iid': row.latest_import_id}).fetchone()
            if imp:
                imported_at = imp.created_at

        try:
            db.execute(text("""
                INSERT INTO agata_star
                    (gaia_id, total_points, num_catalogs, catalogs,
                     min_hjd, max_hjd, min_mag, max_mag,
                     latest_import_id, last_imported_at,
                     is_known_variable,
                     num_assignments, has_active_project,
                     created_at, updated_at)
                VALUES
                    (:gaia_id, :total_points, :num_catalogs, :catalogs,
                     :min_hjd, :max_hjd, :min_mag, :max_mag,
                     :latest_import_id, :last_imported_at,
                     0,
                     0, 0,
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
        except Exception as upsert_err:
            db.rollback()
            logger.warning(f"agata_star upsert failed for {gaia_id}: {upsert_err}")
    except Exception as e:
        logger.warning(f"agata_star photometry upsert failed for {gaia_id}: {e}")
