"""
Helper mixin for refreshing continuous aggregates after data import.
Used by: VAST, TESS, ZTF services, and catalog_import_service.

This module provides a centralized, reusable approach to refresh materialized
views on-demand after job completion, ensuring data freshness without waiting
for scheduled refresh policies.
"""
import logging
from sqlalchemy import text
from typing import Optional

logger = logging.getLogger(__name__)


class CaggRefreshMixin:
    """Mixin to add cagg refresh capability to services."""

    @staticmethod
    def refresh_cagg_for_table(db, table_name: str, cagg_name: str) -> bool:
        """
        Refresh a continuous aggregate for the given table.

        This method performs an on-demand refresh of a materialized view,
        ensuring data is fresh immediately after job completion. If the refresh
        fails, it logs a warning but does NOT raise an exception, as the cagg
        will auto-refresh on its scheduled interval anyway.

        Args:
            db: SQLAlchemy session
            table_name: Physical table name (e.g., 'agata_tess_import_results')
            cagg_name: CAGG view name (e.g., 'tess_job_summary')

        Returns:
            True if refresh succeeded, False otherwise
        """
        try:
            db.session.execute(text(f"""
                CALL refresh_continuous_aggregate(
                    '{cagg_name}',
                    CURRENT_TIMESTAMP - INTERVAL '1 day',
                    CURRENT_TIMESTAMP
                )
            """))
            db.session.commit()
            logger.info(f"Refreshed cagg '{cagg_name}' for table '{table_name}'")
            return True
        except Exception as e:
            logger.warning(f"Could not refresh cagg '{cagg_name}': {e}")
            # Non-critical: cagg will auto-refresh on schedule (6 hours for jobs, 1 hour for photometry)
            return False

    @staticmethod
    def refresh_star_photometry_cagg(db) -> bool:
        """
        Refresh all 3 star_photometry aggregates (hourly, daily, monthly).

        Called after catalog import to ensure photometry aggregates are fresh.
        This refreshes a larger time window (7 days back) to capture recent imports.

        Args:
            db: SQLAlchemy session

        Returns:
            True if all refreshes succeeded, False if any failed
        """
        views = [
            'phot_hourly_summary',
            'phot_daily_summary',
            'phot_monthly_summary'
        ]

        success = True
        for view in views:
            try:
                db.session.execute(text(f"""
                    CALL refresh_continuous_aggregate(
                        '{view}',
                        CURRENT_TIMESTAMP - INTERVAL '7 days',
                        CURRENT_TIMESTAMP
                    )
                """))
                logger.info(f"Refreshed cagg '{view}'")
            except Exception as e:
                logger.warning(f"Could not refresh cagg '{view}': {e}")
                success = False

        try:
            db.session.commit()
        except Exception as e:
            logger.warning(f"Could not commit cagg refreshes: {e}")
            success = False

        return success
