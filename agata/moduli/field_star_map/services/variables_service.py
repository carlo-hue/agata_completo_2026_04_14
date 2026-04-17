from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from astropy import units as u
from astropy.coordinates import SkyCoord
from astroquery.vizier import Vizier


@dataclass
class KnownVariable:
    ra: float
    dec: float
    name: str | None
    var_type: str | None
    period_days: float | None = None
    catalog: str = "VSX"


def _normalize_value(value: Any) -> str | None:
    if value is None:
        return None
    if getattr(value, "mask", False) is True:
        return None
    text = str(value).strip()
    return text if text else None


def _first_present(row: Any, keys: list[str]) -> Any:
    available = set(row.keys())
    for key in keys:
        if key in available:
            return row[key]
    return None


def query_known_variables(ra0_deg: float, dec0_deg: float, radius_arcmin: float) -> list[KnownVariable]:
    """Single extension point for known variable catalogs (currently VSX via VizieR)."""
    vizier = Vizier(columns=["*"], row_limit=-1)
    center = SkyCoord(ra=ra0_deg * u.deg, dec=dec0_deg * u.deg, frame="icrs")

    tables = vizier.query_region(center, radius=radius_arcmin * u.arcmin, catalog="B/vsx/vsx")
    if not tables:
        return []

    table = tables[0]
    variables: list[KnownVariable] = []

    for row in table:
        ra_val = _first_present(row, ["RAJ2000", "RA_ICRS", "RAdeg", "RA"])
        dec_val = _first_present(row, ["DEJ2000", "DE_ICRS", "DEdeg", "DE"])
        if ra_val is None or dec_val is None:
            continue

        try:
            ra = float(ra_val)
            dec = float(dec_val)
        except (TypeError, ValueError):
            continue

        name = _normalize_value(_first_present(row, ["Name", "OID", "VarName", "VSX", "id"]))
        var_type = _normalize_value(_first_present(row, ["Type", "VType", "VarType"]))
        period_raw = _first_present(row, ["Period", "Per", "P"])
        period_days: float | None = None
        if period_raw is not None and not (getattr(period_raw, "mask", False) is True):
            try:
                value = float(period_raw)
                period_days = value if math.isfinite(value) else None
            except (TypeError, ValueError):
                period_days = None

        variables.append(KnownVariable(ra=ra, dec=dec, name=name, var_type=var_type, period_days=period_days))

    return variables
