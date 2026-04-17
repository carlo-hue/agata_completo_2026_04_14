from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from astroquery.vizier import Vizier

from astropy.coordinates import SkyCoord
import astropy.units as u

def _json_safe(v):
    # MaskedConstant (numpy.ma.core.MaskedConstant) - convert to None
    try:
        import numpy.ma as ma
        if isinstance(v, type(ma.masked)):
            return None
    except Exception:
        pass

    # numpy scalars (int64, float64, etc.)
    try:
        import numpy as np
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating,)):
            return float(v)
        if isinstance(v, (np.bool_,)):
            return bool(v)
    except Exception:
        pass

    # astropy quantities / masked
    try:
        # Quantity
        if hasattr(v, "value") and hasattr(v, "unit"):
            return _json_safe(v.value)
    except Exception:
        pass

    # bytes
    if isinstance(v, (bytes, bytearray)):
        return v.decode(errors="replace")

    # default python types ok
    return v


@dataclass(frozen=True)
class VizierRowResult:
    values: Dict[str, Any]


class VizierClient:
    """
    Wrapper minimale su astroquery.vizier.
    """

    def __init__(self, timeout_s: int = 20) -> None:
        # Vizier usa questa timeout globale (seconds)
        Vizier.TIMEOUT = timeout_s

    def query_by_source_id(
        self,
        catalog_id: str,
        source_id_field: str,
        source_id_value: str,
        columns: List[str],
    ) -> List[VizierRowResult]:
        v = Vizier(columns=columns)
        tables = v.query_constraints(catalog=catalog_id, **{source_id_field: source_id_value})
        return self._tables_to_rows(tables)
    
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    def query_cone(
        self,
        catalog_id: str,
        ra_deg: float,
        dec_deg: float,
        radius_arcsec: float,
        columns: List[str],
        gmag_max: Optional[float] = None,
    ) -> List[VizierRowResult]:
        import logging
        logger = logging.getLogger(__name__)

        # Setup column filters for magnitude constraint
        column_filters = {}
        if gmag_max is not None:
            column_filters['Gmag'] = f'<{gmag_max}'
            logger.debug(f"[VizierClient] query_cone: gmag_max={gmag_max}, applying filter Gmag<{gmag_max}")
        else:
            logger.debug(f"[VizierClient] query_cone: gmag_max=None (no magnitude filter)")

        # CRITICAL FIX: astroquery.vizier has a bug with high-precision coordinates (>4 decimals)
        # Round to 4 decimals (~0.01 arcsec precision, sufficient for astronomy, avoids numeric issues)
        ra_deg = round(ra_deg, 4)
        dec_deg = round(dec_deg, 4)

        v = Vizier(columns=columns, column_filters=column_filters)
        v.table = None  # Reset cached table to force fresh query
        coord = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame="icrs")
        radius = radius_arcsec * u.arcsec

        tables = v.query_region(coord, radius=radius, catalog=catalog_id)
        result_count = len(self._tables_to_rows(tables))
        logger.debug(f"[VizierClient] query_cone: returned {result_count} rows (RA={ra_deg:.2f}, Dec={dec_deg:.2f}, radius={radius_arcsec}\")")

        return self._tables_to_rows(tables)


    def _tables_to_rows(self, tables) -> List[VizierRowResult]:
        if not tables:
            return []

        out: List[VizierRowResult] = []
        for table in tables:
            colnames = list(table.colnames)
            for row in table:
                values = {c: _json_safe(row[c]) for c in colnames}
                out.append(VizierRowResult(values=values))
        return out
