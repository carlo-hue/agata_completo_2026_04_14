# agata/auth_models/star.py
"""
Star model - Denormalized cache row per stella del catalogo centrale.

agata_star maintains pre-calculated aggregate statistics from:
- agata_star_photometry (photometry)
- agata_star_assignments (assignments)
- agata_projects (projects)
- agata_vast_results (variability)
- agata_catalog_imports (latest import)

Updated via synchronous hooks on every state-changing operation.
"""
from sqlalchemy import String, Integer, Double, Float, DateTime, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from agata.models import Base


class Star(Base):
    """
    Denormalized cache: 1 row per Gaia ID in catalog.

    Keeps denormalized copies of aggregates to enable O(1) filtering/sorting
    on stars_catalog page, avoiding N+1 queries and GROUP BY on agata_star_photometry.
    """
    __tablename__ = "agata_star"

    # Primary Key
    gaia_id: Mapped[str] = mapped_column(
        String(50), primary_key=True,
        comment="Gaia DR3 source ID (VARCHAR, never cast to int)"
    )

    # Coordinates
    ra: Mapped[float | None] = mapped_column(Double, nullable=True)
    dec_deg: Mapped[float | None] = mapped_column(Double, nullable=True)

    # Photometry aggregates (from agata_star_photometry)
    total_points: Mapped[int] = mapped_column(Integer, default=0)
    num_catalogs: Mapped[int] = mapped_column(Integer, default=0)
    catalogs: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="CSV list: 'TESS,ZTF,ASASSN'"
    )

    min_hjd: Mapped[float | None] = mapped_column(Double, nullable=True)
    max_hjd: Mapped[float | None] = mapped_column(Double, nullable=True)
    min_mag: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_mag: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Import tracking
    latest_import_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="FK → agata_catalog_imports.id (soft ref, not enforced)"
    )
    last_imported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # VAST data (from agata_vast_results)
    is_known_variable: Mapped[int] = mapped_column(SmallInteger, default=0)
    variable_types: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="CSV list: 'RRab,HADS'"
    )
    catalog_matches: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="CSV list: 'VSX,Gaia'"
    )

    # State flags
    num_assignments: Mapped[int] = mapped_column(Integer, default=0)
    has_active_project: Mapped[int] = mapped_column(SmallInteger, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f"<Star(gaia_id='{self.gaia_id}', points={self.total_points})>"
