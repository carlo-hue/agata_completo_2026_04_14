from __future__ import annotations

import logging
import math

from astropy.coordinates import Angle, SkyCoord
import astropy.units as u

from .utils import rounded_or_none

LOGGER = logging.getLogger(__name__)


def validate_reference_wcs(reference_frame: dict) -> dict:
    header = reference_frame.get("header") or {}
    wcs = reference_frame.get("wcs")
    missing: list[str] = []

    ctype_keys = ["CTYPE1", "CTYPE2"]
    missing.extend([key for key in ctype_keys if key not in header])

    crval_keys = ["CRVAL1", "CRVAL2"]
    missing.extend([key for key in crval_keys if key not in header])

    crpix_keys = ["CRPIX1", "CRPIX2"]
    missing.extend([key for key in crpix_keys if key not in header])

    has_cd = all(key in header for key in ("CD1_1", "CD1_2", "CD2_1", "CD2_2"))
    has_pc_cdelt = (
        all(key in header for key in ("PC1_1", "PC1_2", "PC2_1", "PC2_2"))
        and all(key in header for key in ("CDELT1", "CDELT2"))
    )
    has_cdelt = all(key in header for key in ("CDELT1", "CDELT2"))

    if not (has_cd or has_pc_cdelt or has_cdelt):
        missing.append("CD1_1/CD1_2/CD2_1/CD2_2 oppure PC1_1/PC1_2/PC2_1/PC2_2 + CDELT1/CDELT2")

    if wcs is None:
        missing.append("WCS non costruibile da header")

    return {
        "valid": not missing,
        "missing": missing,
    }


def build_target_candidates(reference_payload: dict, reference_frame: dict, *, search_radius_arcsec: float | None = None) -> dict:
    center_sky = reference_payload.get("center_sky")
    center_pixel = reference_payload.get("center_pixel") or {"x": 0.0, "y": 0.0}
    wcs = reference_frame.get("wcs")
    if not center_sky or wcs is None:
        return {
            "candidates": [],
            "provider_statuses": [
                {
                    "provider_key": "reference",
                    "provider_label": "Reference/WCS",
                    "status": "unavailable",
                    "count": 0,
                    "message": "Centro campo o WCS non disponibili.",
                }
            ],
        }

    candidates: list[dict] = []
    provider_statuses: list[dict] = []
    vsx_candidates, vsx_status = _query_vsx_candidates(center_sky, center_pixel, wcs, reference_frame, search_radius_arcsec=search_radius_arcsec)
    exo_candidates, exo_status = _query_exoplanet_candidates(center_sky, center_pixel, wcs, reference_frame, search_radius_arcsec=search_radius_arcsec)
    candidates.extend(vsx_candidates)
    candidates.extend(exo_candidates)
    provider_statuses.append(vsx_status)
    provider_statuses.append(exo_status)
    candidates.sort(
        key=lambda item: (
            item.get("priority_rank") if item.get("priority_rank") is not None else 9999,
            item.get("distance_from_center_px") if item.get("distance_from_center_px") is not None else float("inf"),
        )
    )
    return {
        "candidates": candidates,
        "provider_statuses": provider_statuses,
    }


def _query_vsx_candidates(center_sky: dict, center_pixel: dict, wcs, reference_frame: dict, *, search_radius_arcsec: float | None = None) -> tuple[list[dict], dict]:
    try:
        from astroquery.vizier import Vizier
    except Exception:
        return [], _provider_status("vsx", "AAVSO VSX", "unavailable", 0, "astroquery.vizier non disponibile")

    try:
        center = SkyCoord(center_sky["ra_deg"] * u.deg, center_sky["dec_deg"] * u.deg)
        radius = _catalog_radius(search_radius_arcsec, reference_frame)
        vizier = Vizier(columns=["OID", "Name", "Type", "RAJ2000", "DEJ2000"])
        vizier.ROW_LIMIT = 25
        result = vizier.query_region(center, radius=radius, catalog=["B/vsx/vsx"])
        if not result or len(result) == 0:
            return [], _provider_status("vsx", "AAVSO VSX", "ok", 0, "0 candidati nel raggio richiesto")
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
        return candidates, _provider_status("vsx", "AAVSO VSX", "ok", len(candidates), f"{len(candidates)} candidati")
    except Exception:
        LOGGER.exception("VSX candidate lookup failed")
        return [], _provider_status("vsx", "AAVSO VSX", "error", 0, "query fallita")


def _query_exoplanet_candidates(center_sky: dict, center_pixel: dict, wcs, reference_frame: dict, *, search_radius_arcsec: float | None = None) -> tuple[list[dict], dict]:
    try:
        from astroquery.ipac.nexsci.nasa_exoplanet_archive import NasaExoplanetArchive
    except Exception:
        return [], _provider_status("exo", "NASA Exoplanet Archive", "unavailable", 0, "astroquery exoplanet archive non disponibile")

    try:
        center = SkyCoord(center_sky["ra_deg"] * u.deg, center_sky["dec_deg"] * u.deg)
        radius = _catalog_radius(search_radius_arcsec, reference_frame)
        table = NasaExoplanetArchive.query_region(
            table="pscomppars",
            coordinates=center,
            radius=radius,
        )
        candidates = []
        if table is None:
            return candidates, _provider_status("exo", "NASA Exoplanet Archive", "ok", 0, "0 candidati nel raggio richiesto")
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
        return candidates, _provider_status("exo", "NASA Exoplanet Archive", "ok", len(candidates), f"{len(candidates)} candidati")
    except Exception:
        LOGGER.exception("Exoplanet candidate lookup failed")
        return [], _provider_status("exo", "NASA Exoplanet Archive", "error", 0, "query fallita")


def _estimate_field_radius_deg(reference_frame: dict) -> float:
    rows, cols = reference_frame["shape"]
    diagonal_px = math.sqrt(rows * rows + cols * cols)
    # Conservativo per immagini ground-based senza assumere una plate scale precisa.
    return max(0.05, min(1.0, diagonal_px / 3600.0))


def _catalog_radius(search_radius_arcsec: float | None, reference_frame: dict) -> Angle:
    if search_radius_arcsec is not None:
        try:
            radius_arcsec = float(search_radius_arcsec)
        except (TypeError, ValueError):
            radius_arcsec = None
        if radius_arcsec is not None and math.isfinite(radius_arcsec) and radius_arcsec > 0:
            return Angle(radius_arcsec, unit=u.arcsec)
    return Angle(_estimate_field_radius_deg(reference_frame), unit=u.deg)


def _provider_status(provider_key: str, provider_label: str, status: str, count: int, message: str) -> dict:
    return {
        "provider_key": provider_key,
        "provider_label": provider_label,
        "status": status,
        "count": int(count),
        "message": message,
    }


def _in_bounds(x: float, y: float, shape: list[int]) -> bool:
    rows, cols = int(shape[0]), int(shape[1])
    return 0 <= x < cols and 0 <= y < rows
