from __future__ import annotations

import logging
import math

from astropy.coordinates import Angle, SkyCoord
import astropy.units as u

from .utils import rounded_or_none

LOGGER = logging.getLogger(__name__)


def build_target_candidates(reference_payload: dict, reference_frame: dict) -> list[dict]:
    center_sky = reference_payload.get("center_sky")
    center_pixel = reference_payload.get("center_pixel") or {"x": 0.0, "y": 0.0}
    wcs = reference_frame.get("wcs")
    if not center_sky or wcs is None:
        return []

    candidates: list[dict] = []
    candidates.extend(_query_vsx_candidates(center_sky, center_pixel, wcs, reference_frame))
    candidates.extend(_query_exoplanet_candidates(center_sky, center_pixel, wcs, reference_frame))
    candidates.sort(
        key=lambda item: (
            item.get("priority_rank") if item.get("priority_rank") is not None else 9999,
            item.get("distance_from_center_px") if item.get("distance_from_center_px") is not None else float("inf"),
        )
    )
    return candidates


def _query_vsx_candidates(center_sky: dict, center_pixel: dict, wcs, reference_frame: dict) -> list[dict]:
    try:
        from astroquery.vizier import Vizier
    except Exception:
        return []

    try:
        center = SkyCoord(center_sky["ra_deg"] * u.deg, center_sky["dec_deg"] * u.deg)
        radius = Angle(_estimate_field_radius_deg(reference_frame), unit=u.deg)
        vizier = Vizier(columns=["OID", "Name", "Type", "RAJ2000", "DEJ2000"])
        vizier.ROW_LIMIT = 25
        result = vizier.query_region(center, radius=radius, catalog=["B/vsx/vsx"])
        if not result or len(result) == 0:
            return []
        table = result[0]
        candidates = []
        for row in table:
            try:
                sky = SkyCoord(row["RAJ2000"], row["DEJ2000"], unit=(u.deg, u.deg))
                x, y = wcs.world_to_pixel(sky)
            except Exception:
                continue
            if not _in_bounds(x, y, reference_frame["shape"]):
                continue
            distance = math.hypot(float(x) - float(center_pixel["x"]), float(y) - float(center_pixel["y"]))
            candidates.append({
                "candidate_id": f"vsx-{row['OID']}",
                "label": str(row["Name"] or row["OID"]),
                "catalog_type": "variable_star",
                "catalog_name": "AAVSO VSX",
                "subtype": str(row["Type"]) if row["Type"] is not None else None,
                "x": rounded_or_none(x, 3),
                "y": rounded_or_none(y, 3),
                "ra_deg": rounded_or_none(sky.ra.deg, 6),
                "dec_deg": rounded_or_none(sky.dec.deg, 6),
                "distance_from_center_px": rounded_or_none(distance, 3),
                "priority_rank": 10,
            })
        return candidates
    except Exception:
        LOGGER.exception("VSX candidate lookup failed")
        return []


def _query_exoplanet_candidates(center_sky: dict, center_pixel: dict, wcs, reference_frame: dict) -> list[dict]:
    try:
        from astroquery.ipac.nexsci.nasa_exoplanet_archive import NasaExoplanetArchive
    except Exception:
        return []

    try:
        center = SkyCoord(center_sky["ra_deg"] * u.deg, center_sky["dec_deg"] * u.deg)
        radius_deg = _estimate_field_radius_deg(reference_frame)
        table = NasaExoplanetArchive.query_region(
            table="pscomppars",
            coordinates=center,
            radius=radius_deg * u.deg,
        )
        candidates = []
        if table is None:
            return candidates
        for row in table[:25]:
            try:
                ra_deg = float(row["ra"])
                dec_deg = float(row["dec"])
                sky = SkyCoord(ra_deg * u.deg, dec_deg * u.deg)
                x, y = wcs.world_to_pixel(sky)
            except Exception:
                continue
            if not _in_bounds(x, y, reference_frame["shape"]):
                continue
            distance = math.hypot(float(x) - float(center_pixel["x"]), float(y) - float(center_pixel["y"]))
            candidates.append({
                "candidate_id": f"exo-{row['pl_name']}",
                "label": str(row["pl_name"]),
                "catalog_type": "exoplanet_host",
                "catalog_name": "NASA Exoplanet Archive",
                "subtype": str(row["hostname"]) if row["hostname"] is not None else None,
                "x": rounded_or_none(x, 3),
                "y": rounded_or_none(y, 3),
                "ra_deg": rounded_or_none(ra_deg, 6),
                "dec_deg": rounded_or_none(dec_deg, 6),
                "distance_from_center_px": rounded_or_none(distance, 3),
                "priority_rank": 20,
            })
        return candidates
    except Exception:
        LOGGER.exception("Exoplanet candidate lookup failed")
        return []


def _estimate_field_radius_deg(reference_frame: dict) -> float:
    rows, cols = reference_frame["shape"]
    diagonal_px = math.sqrt(rows * rows + cols * cols)
    # Conservativo per immagini ground-based senza assumere una plate scale precisa.
    return max(0.05, min(1.0, diagonal_px / 3600.0))


def _in_bounds(x: float, y: float, shape: list[int]) -> bool:
    rows, cols = int(shape[0]), int(shape[1])
    return 0 <= x < cols and 0 <= y < rows

