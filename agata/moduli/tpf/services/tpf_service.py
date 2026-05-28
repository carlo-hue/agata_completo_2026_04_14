from __future__ import annotations

import logging
import math
from time import perf_counter

import numpy as np
from astroquery.mast import Catalogs
from astroquery.vizier import Vizier
from astropy import units as u
from astropy.coordinates import SkyCoord

from ..config import settings
from .lightcurve_service import build_auto_masks, compute_lightcurve_stub, compute_real_lightcurve, normalize_manual_masks
from .tpf_data_service import load_local_tpf, load_local_tpf_frames
from .utils import (
    build_nearby_source_entry,
    build_overlay_source_entry,
    point_is_inside_grid,
    rounded_or_none,
    validate_gaia_source_id,
    validate_sector,
)

LOGGER = logging.getLogger(__name__)
PIXEL_SCALE_ARCSEC = 21.0
NEARBY_RADIUS_DEG = 0.02
PREVIEW_SIZE_PX = 11
MAX_NEARBY_SOURCES = 25
MAX_OVERLAY_SOURCES = 50
AUTO_TARGET_THRESHOLD_SIGMA = 15.0
AUTO_BACKGROUND_THRESHOLD_SIGMA = 0.001
TIC_REFERENCE_RADIUS_ARCSEC = 5.0
VSX_MATCH_RADIUS_ARCSEC = 2.0


def _empty_masks_payload(message: str) -> dict:
    return {
        "available": False,
        "mode": "not-available",
        "message": message,
        "target": [],
        "background": [],
        "summary": {
            "target_pixels": 0,
            "background_pixels": 0,
        },
    }


def _empty_overlay_payload(message: str) -> dict:
    return {
        "status": "not-available",
        "message": message,
        "target_position": None,
        "gaia_sources": [],
    }


def _empty_frames_payload(message: str) -> dict:
    return {
        "available": False,
        "count": 0,
        "time": [],
        "grids": [],
        "initial_index": 0,
        "message": message,
    }


def _relative_flux_from_gmag(gmag: float | None, reference_gmag: float | None) -> float:
    if gmag is None:
        return 0.2
    ref = reference_gmag if reference_gmag is not None else gmag
    return max(0.05, math.pow(10.0, -0.4 * (float(gmag) - float(ref))))


def _safe_float(value):
    if np.ma.is_masked(value):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _target_has_coordinates(target_info: dict | None) -> bool:
    if not isinstance(target_info, dict):
        return False
    return target_info.get("ra_deg") is not None and target_info.get("dec_deg") is not None


def _extract_tpf_center_coordinates(tpf_payload: dict | None) -> tuple[float | None, float | None]:
    if not isinstance(tpf_payload, dict):
        return None, None

    pixel_world = ((tpf_payload.get("metadata") or {}).get("pixel_world") or {})
    ra_grid = pixel_world.get("ra_deg")
    dec_grid = pixel_world.get("dec_deg")
    if not isinstance(ra_grid, list) or not isinstance(dec_grid, list) or not ra_grid or not dec_grid:
        return None, None

    center_row = len(ra_grid) // 2
    center_col = len(ra_grid[center_row]) // 2 if isinstance(ra_grid[center_row], list) and ra_grid[center_row] else 0
    try:
        ra_deg = float(ra_grid[center_row][center_col])
        dec_deg = float(dec_grid[center_row][center_col])
    except (TypeError, ValueError, IndexError):
        return None, None
    return rounded_or_none(ra_deg, 6), rounded_or_none(dec_deg, 6)


def _build_local_only_target_info(gaia_source_id: str, real_tpf: dict | None = None) -> dict:
    ra_deg, dec_deg = _extract_tpf_center_coordinates(real_tpf)
    return {
        "gaia_source_id": gaia_source_id,
        "ra_deg": ra_deg,
        "dec_deg": dec_deg,
        "gmag": None,
        "catalog": "Gaia unavailable",
    }


def _resolve_target_info_with_fallback(gaia_source_id: str, real_tpf: dict | None = None) -> tuple[dict, dict]:
    try:
        target_info = _fetch_gaia_dr3_target(gaia_source_id)
        return target_info, {
            "available": True,
            "mode": "gaia",
            "message": "Target risolto via Gaia DR3.",
        }
    except Exception as err:
        if real_tpf is None:
            raise
        LOGGER.warning(
            "Gaia target resolution unavailable for gaia_source_id=%s, continuing with local TPF fallback: %s",
            gaia_source_id,
            err,
        )
        target_info = _build_local_only_target_info(gaia_source_id, real_tpf=real_tpf)
        message = "Gaia non disponibile: pipeline TPF eseguita in modalita locale sul file TPF reale."
        if not _target_has_coordinates(target_info):
            message += " Coordinate target non ricostruibili dal TPF locale."
        return target_info, {
            "available": False,
            "mode": "local-tpf-fallback",
            "message": message,
            "error": str(err),
        }


def _fetch_gaia_dr3_target(gaia_source_id: str) -> dict:
    try:
        vizier = Vizier(columns=['Source', 'RA_ICRS', 'DE_ICRS', 'Gmag'], catalog='I/350')
        vizier.cache = False
        results = vizier.query_constraints(Source=str(gaia_source_id))
        if results is None or len(results) == 0:
            raise ValueError("gaia_source_id non trovato in Gaia DR3")
        table = results[0]
        if len(table) == 0:
            raise ValueError("gaia_source_id non trovato in Gaia DR3")
        row = table[0]
        LOGGER.info("Vizier query succeeded for gaia_source_id=%s: RA=%.6f DEC=%.6f Gmag=%s",
                    gaia_source_id, row["RA_ICRS"], row["DE_ICRS"], row["Gmag"])
        return {
            "gaia_source_id": str(row["Source"]),
            "ra_deg": rounded_or_none(row["RA_ICRS"], 6),
            "dec_deg": rounded_or_none(row["DE_ICRS"], 6),
            "gmag": rounded_or_none(row["Gmag"], 4),
            "catalog": "Gaia DR3",
        }
    except Exception as err:
        LOGGER.exception("Vizier query failed for gaia_source_id=%s: %s", gaia_source_id, err)
        raise ValueError(f"Impossibile risolvere gaia_source_id {gaia_source_id}: {err}") from err


def _fetch_nearby_gaia_sources(target_info: dict, radius_deg: float = NEARBY_RADIUS_DEG) -> list[dict]:
    if not _target_has_coordinates(target_info):
        return []
    ra = float(target_info["ra_deg"])
    dec = float(target_info["dec_deg"])
    center = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs")
    cos_dec = math.cos(math.radians(dec)) or 1.0

    try:
        vizier = Vizier(columns=['Source', 'RA_ICRS', 'DE_ICRS', 'Gmag'], row_limit=MAX_NEARBY_SOURCES + 1)
        results = vizier.query_region(
            SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs"),
            radius=radius_deg * u.deg,
            catalog='I/350'  # Gaia DR3
        )
        if not results or len(results) == 0:
            return []

        table = results[0]
        entries = []
        for row in table:
            source_id = str(row['Source'])
            if source_id == target_info["gaia_source_id"]:
                continue
            row_ra = float(row['RA_ICRS'])
            row_dec = float(row['DE_ICRS'])
            coord = SkyCoord(row_ra * u.deg, row_dec * u.deg, frame="icrs")
            dist_arcsec = center.separation(coord).arcsec
            offset_x_arcsec = (row_ra - ra) * 3600.0 * cos_dec
            offset_y_arcsec = (row_dec - dec) * 3600.0
            gmag = _safe_float(row['Gmag']) if 'Gmag' in table.colnames else None
            entries.append(
                build_nearby_source_entry(
                    source_id=source_id,
                    ra=row_ra,
                    dec=row_dec,
                    gmag=gmag,
                    dist_arcsec=dist_arcsec,
                    pixel_scale_arcsec=PIXEL_SCALE_ARCSEC,
                    offset_x_px=offset_x_arcsec / PIXEL_SCALE_ARCSEC,
                    offset_y_px=offset_y_arcsec / PIXEL_SCALE_ARCSEC,
                )
            )
        entries.sort(key=lambda item: item.get("dist_arcsec") if item.get("dist_arcsec") is not None else float("inf"))
        return entries
    except Exception as err:
        LOGGER.exception("Vizier query failed for nearby Gaia sources: %s", err)
        return []


def _resolve_reference_magnitude(target_info: dict, tpf_metadata: dict | None) -> dict:
    metadata = dict(tpf_metadata or {})
    header_tessmag = metadata.get("tessmag")
    header_tessmag_key = metadata.get("tessmag_key")
    if header_tessmag is not None:
        LOGGER.info(
            "Using TESS magnitude from TPF header for gaia_source_id=%s key=%s value=%s",
            target_info.get("gaia_source_id"),
            header_tessmag_key,
            header_tessmag,
        )
        metadata["reference_mag_value"] = header_tessmag
        metadata["reference_mag_band"] = "TESS"
        metadata["reference_mag_key"] = header_tessmag_key or "TESSMAG"
        metadata["reference_mag_source"] = "tpf_header"
        return metadata

    if _target_has_coordinates(target_info):
        try:
            coord = SkyCoord(
                ra=float(target_info["ra_deg"]) * u.deg,
                dec=float(target_info["dec_deg"]) * u.deg,
                frame="icrs",
            )
            catalog = Catalogs.query_region(coord, radius=(TIC_REFERENCE_RADIUS_ARCSEC * u.arcsec), catalog="TIC")
            if catalog is not None and len(catalog) > 0:
                catalog_sorted = catalog
                if "dstArcSec" in catalog.colnames:
                    catalog_sorted = catalog[np.argsort(catalog["dstArcSec"])]
                best_row = catalog_sorted[0]
                tmag_value = best_row["Tmag"] if "Tmag" in catalog.colnames else None
                if tmag_value is not None:
                    tmag_numeric = rounded_or_none(tmag_value, 6)
                    if tmag_numeric is not None and 0.0 < float(tmag_numeric) < 30.0:
                        LOGGER.info(
                            "Using TIC catalog Tmag for gaia_source_id=%s value=%s",
                            target_info.get("gaia_source_id"),
                            tmag_numeric,
                        )
                        metadata["reference_mag_value"] = float(tmag_numeric)
                        metadata["reference_mag_band"] = "TESS"
                        metadata["reference_mag_key"] = "Tmag"
                        metadata["reference_mag_source"] = "tic_catalog"
                        if "ID" in catalog.colnames:
                            metadata["reference_mag_catalog_id"] = str(best_row["ID"])
                        return metadata
        except Exception:
            LOGGER.exception("TIC reference magnitude lookup failed for gaia_source_id=%s", target_info.get("gaia_source_id"))
    else:
        LOGGER.info("Skipping TIC reference magnitude lookup for gaia_source_id=%s: coordinates unavailable", target_info.get("gaia_source_id"))

    gaia_gmag = target_info.get("gmag")
    if gaia_gmag is not None:
        LOGGER.info(
            "Falling back to Gaia G magnitude for gaia_source_id=%s value=%s",
            target_info.get("gaia_source_id"),
            gaia_gmag,
        )
        metadata["reference_mag_value"] = gaia_gmag
        metadata["reference_mag_band"] = "Gaia G"
        metadata["reference_mag_key"] = "phot_g_mean_mag"
        metadata["reference_mag_source"] = "gaia_catalog_fallback"
        return metadata

    LOGGER.info("No reference magnitude available for gaia_source_id=%s", target_info.get("gaia_source_id"))
    metadata["reference_mag_value"] = None
    metadata["reference_mag_band"] = None
    metadata["reference_mag_key"] = None
    metadata["reference_mag_source"] = None
    return metadata


def _estimate_overlay_radius_deg(shape: tuple[int, int] | list[int]) -> float:
    rows = int(shape[0])
    cols = int(shape[1])
    diagonal_px = math.sqrt((rows * rows) + (cols * cols))
    radius_arcsec = max(60.0, (diagonal_px * PIXEL_SCALE_ARCSEC * 0.6))
    return round(radius_arcsec / 3600.0, 5)


def _crossmatch_overlay_vsx(sources: list[dict], ra_center: float, dec_center: float, radius_deg: float) -> None:
    if not sources:
        return

    try:
        import astropy.units as u
        import astropy.coordinates as coord
        from astropy.coordinates import Angle, match_coordinates_sky
        from astroquery.vizier import Vizier
    except ImportError:
        LOGGER.info("VSX cross-match skipped: astroquery.vizier non disponibile.")
        return

    try:
        center = coord.SkyCoord(ra=ra_center * u.deg, dec=dec_center * u.deg, frame="icrs")
        source_coords = coord.SkyCoord(
            ra=[float(item["ra_deg"]) for item in sources] * u.deg,
            dec=[float(item["dec_deg"]) for item in sources] * u.deg,
            frame="icrs",
        )
        vizier = Vizier(columns=["OID", "Type", "Name", "RAJ2000", "DEJ2000"])
        vizier.ROW_LIMIT = -1
        catalogs = vizier.query_region(center, radius=Angle(radius_deg, unit=u.deg), catalog=["B/vsx/vsx"])
        if catalogs is None or len(catalogs) == 0:
            LOGGER.info("VSX cross-match: nessun match di catalogo nel campo overlay.")
            return

        vsx_table = catalogs[0]
        if len(vsx_table) == 0:
            LOGGER.info("VSX cross-match: catalogo vuoto nel campo overlay.")
            return

        vsx_coords = coord.SkyCoord(
            ra=vsx_table["RAJ2000"],
            dec=vsx_table["DEJ2000"],
            unit=(u.deg, u.deg),
            frame="icrs",
        )
        idx, sep2d, _ = match_coordinates_sky(source_coords, vsx_coords)
        max_sep = VSX_MATCH_RADIUS_ARCSEC * u.arcsec
        match_count = 0
        for source_index, separation in enumerate(sep2d):
            if separation > max_sep:
                continue
            source = sources[source_index]
            row = vsx_table[idx[source_index]]
            catalogs_list = list(source.get("variable_catalogs") or [])
            if "AAVSO VSX" not in catalogs_list:
                catalogs_list.append("AAVSO VSX")
            source["variable_catalogs"] = catalogs_list
            source["is_variable"] = True
            if not source.get("variable_type") and "Type" in vsx_table.colnames:
                source["variable_type"] = str(row["Type"]) if row["Type"] is not None else None
            if "OID" in vsx_table.colnames and row["OID"] is not None:
                source["variable_oid"] = str(row["OID"])
            if "Name" in vsx_table.colnames and row["Name"] is not None:
                source["variable_name"] = str(row["Name"])
            if "Period" in vsx_table.colnames and row["Period"] is not None:
                source["variable_period_days"] = rounded_or_none(row["Period"], 6)
            match_count += 1
        LOGGER.info("VSX cross-match overlay completato: %s stelle matchate.", match_count)
    except Exception:
        LOGGER.exception("VSX cross-match overlay fallito per gaia_source_id field center=(%s,%s)", ra_center, dec_center)


def _world_to_tpf_pixel(ra: float, dec: float, wcs, shape: tuple[int, int] | list[int]) -> tuple:
    """Convert RA/DEC to TPF cutout pixels using the cutout WCS directly."""
    if wcs is None:
        return None, None
    try:
        x, y = wcs.all_world2pix(float(ra), float(dec), 0)
        return float(x), float(y)
    except Exception as e:
        LOGGER.debug("Failed to convert world to TPF pixel: %s", str(e))
        return None, None


def _build_target_position(target_info: dict, shape: tuple[int, int] | list[int], wcs) -> dict:
    rows = int(shape[0])
    cols = int(shape[1])
    fallback = {
        "x": round((cols - 1) / 2.0, 3),
        "y": round((rows - 1) / 2.0, 3),
        "gmag": rounded_or_none(target_info.get("gmag"), 4),
        "source": "fallback-center",
    }
    if wcs is None:
        LOGGER.warning("WCS not available: using center fallback for target position")
        return fallback
    if not _target_has_coordinates(target_info):
        LOGGER.warning("Target coordinates unavailable: using center fallback for target position")
        return fallback

    try:
        x, y = _world_to_tpf_pixel(target_info["ra_deg"], target_info["dec_deg"], wcs, shape)
        if x is None or y is None:
            LOGGER.warning("Target conversion returned None")
            return fallback
        if not point_is_inside_grid(x, y, shape):
            LOGGER.warning("Target world-to-pixel position fell outside TPF grid: x=%s y=%s", x, y)
            return fallback
        return {
            "x": rounded_or_none(x, 3),
            "y": rounded_or_none(y, 3),
            "gmag": rounded_or_none(target_info.get("gmag"), 4),
            "source": "wcs",
        }
    except Exception:
        LOGGER.exception("Failed to convert target sky position to TPF pixel coordinates")
        return fallback


def _fetch_gaia_overlay_sources(target_info: dict, shape: tuple[int, int] | list[int], wcs) -> tuple[list[dict], str, dict]:
    if wcs is None:
        return [], "Overlay Gaia non disponibile: WCS non disponibile.", {"error": "no_wcs"}
    if not _target_has_coordinates(target_info):
        return [], "Overlay Gaia non disponibile: coordinate target assenti.", {"error": "no_coords"}

    ra = float(target_info["ra_deg"])
    dec = float(target_info["dec_deg"])
    radius_deg = _estimate_overlay_radius_deg(shape)
    gaia_source_id = target_info.get("gaia_source_id", "unknown")

    try:
        rows = int(shape[0])
        cols = int(shape[1])
        center_x = (cols - 1) / 2.0
        center_y = (rows - 1) / 2.0
        query_ra, query_dec = wcs.all_pix2world(center_x, center_y, 0)
        query_ra = float(query_ra)
        query_dec = float(query_dec)

        LOGGER.info(
            "Querying Vizier Gaia overlay sources for gaia_source_id=%s center_ra=%.6f center_dec=%.6f radius_deg=%.6f",
            gaia_source_id,
            query_ra,
            query_dec,
            radius_deg,
        )
        LOGGER.info("=== DEBUG: TPF CENTER COORDINATES ===")
        LOGGER.info("TPF WCS center RA=%.6f DEC=%.6f", query_ra, query_dec)

        vizier = Vizier(columns=['Source', 'RA_ICRS', 'DE_ICRS', 'Gmag', 'Var'], row_limit=-1)
        results = vizier.query_region(
            SkyCoord(ra=query_ra * u.deg, dec=query_dec * u.deg, frame="icrs"),
            radius=radius_deg * u.deg,
            catalog='I/350'  # Gaia DR3
        )
        sources = []
        target_coord = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs")

        accepted_count = 0
        rejected_count = 0
        rejected_samples = []
        accepted_samples = []
        target_x, target_y = _world_to_tpf_pixel(ra, dec, wcs, shape)

        def build_debug_sample(
            source_id,
            x,
            y,
            row_ra,
            row_dec,
            gmag,
            dist_arcsec,
            is_variable,
            variable_type,
            variable_catalogs,
        ) -> dict:
            dist_target_px = None
            if target_x is not None and target_y is not None:
                dist_target_px = math.hypot(float(x) - float(target_x), float(y) - float(target_y))
            return {
                "id": source_id,
                "x": rounded_or_none(x, 3),
                "y": rounded_or_none(y, 3),
                "ra_deg": rounded_or_none(row_ra, 6),
                "dec_deg": rounded_or_none(row_dec, 6),
                "gmag": rounded_or_none(gmag, 4),
                "dist_target_arcsec": rounded_or_none(dist_arcsec, 3),
                "dist_target_px": rounded_or_none(dist_target_px, 3),
                "is_variable": bool(is_variable),
                "variable_type": variable_type,
                "variable_catalogs": list(variable_catalogs or []),
            }

        if results and len(results) > 0:
            table = results[0]
            LOGGER.info("=== VIZIER QUERY RESULT ===")
            LOGGER.info("Vizier returned %d TOTAL sources (before filter), gaia_source_id=%s", len(table), gaia_source_id)
            LOGGER.info("Grid shape for filtering: %s", shape)
        else:
            LOGGER.info("Vizier query returned 0 sources for gaia_source_id=%s", gaia_source_id)
            return [], "Sorgenti Gaia overlay non disponibili: nessun risultato dalla query.", {"total_vizier": 0, "accepted": 0, "rejected": 0}

        for row in table:
            source_id = str(row['Source'])
            if source_id == target_info["gaia_source_id"]:
                continue
            row_ra = float(row['RA_ICRS'])
            row_dec = float(row['DE_ICRS'])
            row_coord = SkyCoord(ra=row_ra * u.deg, dec=row_dec * u.deg, frame="icrs")
            dist_arcsec = float(target_coord.separation(row_coord).arcsec)
            x, y = _world_to_tpf_pixel(row_ra, row_dec, wcs, shape)
            if x is None or y is None:
                rejected_count += 1
                LOGGER.debug("Vizier Gaia source %s: world-to-pixel conversion failed", source_id)
                continue
            gmag = _safe_float(row['Gmag']) if 'Gmag' in table.colnames else None
            # Controlla variabilità Gaia (photvariableflag)
            is_variable_gaia = row.get('Var') == 'VARIABLE' if 'Var' in row.colnames else False
            variable_catalogs = ['Gaia DR3'] if is_variable_gaia else []
            variable_type = 'Gaia DR3' if is_variable_gaia else None
            LOGGER.debug("Vizier Gaia source %s: ra=%.6f dec=%.6f → pixel x=%.3f y=%.3f for gaia_source_id=%s", source_id, row_ra, row_dec, x, y, gaia_source_id)
            if not point_is_inside_grid(x, y, shape):
                rejected_count += 1
                if len(rejected_samples) < 10:
                    rejected_samples.append(build_debug_sample(
                        source_id,
                        x,
                        y,
                        row_ra,
                        row_dec,
                        gmag,
                        dist_arcsec,
                        is_variable_gaia,
                        variable_type,
                        variable_catalogs,
                    ))
                LOGGER.info("REJECTED: Source %s at pixel (%.3f, %.3f) is outside grid shape=%s", source_id, x, y, shape)
                continue
            accepted_count += 1
            if len(accepted_samples) < 5:
                accepted_samples.append(build_debug_sample(
                    source_id,
                    x,
                    y,
                    row_ra,
                    row_dec,
                    gmag,
                    dist_arcsec,
                    is_variable_gaia,
                    variable_type,
                    variable_catalogs,
                ))
            LOGGER.info("ACCEPTED: Source %s at pixel (%.3f, %.3f) RA=%.6f DEC=%.6f", source_id, x, y, row_ra, row_dec)
            sources.append(
                build_overlay_source_entry(
                    source_id,
                    x,
                    y,
                    gmag,
                    row_ra,
                    row_dec,
                    dist_arcsec=dist_arcsec,
                    is_variable=is_variable_gaia,
                    variable_type=variable_type,
                    variable_catalogs=variable_catalogs,
                )
            )
        LOGGER.info("=== FILTER RESULT ===")
        LOGGER.info("Total Vizier sources: %d | Accepted: %d | Rejected: %d", len(table), accepted_count, rejected_count)

        # Log campioni
        if rejected_samples:
            LOGGER.info("=== CAMPIONE RIFIUTATE (primi 10) ===")
            for sample in rejected_samples[:10]:
                LOGGER.info("  ID %s: x=%.3f, y=%.3f", sample["id"], sample["x"], sample["y"])
        if accepted_samples:  # accepted
            LOGGER.info("=== CAMPIONE ACCETTATE (prime 5) ===")
            for sample in accepted_samples[:5]:
                LOGGER.info("  ID %s: x=%.3f, y=%.3f", sample["id"], sample["x"], sample["y"])

        _crossmatch_overlay_vsx(sources, ra, dec, radius_deg)
        sources.sort(
            key=lambda item: (
                item.get("dist_arcsec") if item.get("dist_arcsec") is not None else float("inf"),
                item.get("gmag") if item.get("gmag") is not None else float("inf"),
            )
        )
        variable_count = sum(1 for item in sources if item.get("is_variable"))

        debug_stats = {
            "total_vizier": len(table),
            "accepted": accepted_count,
            "rejected": rejected_count,
            "radius_deg": radius_deg,
            "center_ra": query_ra,
            "center_dec": query_dec,
            "target_ra": ra,
            "target_dec": dec,
            "query_center_pixel": [round(center_x, 3), round(center_y, 3)],
            "returned_to_frontend": len(sources),
            "selection_order": "all_inside_grid_sorted_by_target_distance_then_gmag",
            "accepted_samples": accepted_samples,
            "rejected_samples": rejected_samples,
        }

        return sources, f"Sorgenti Gaia overlay disponibili: {len(sources)} nel campo TPF, variabili note: {variable_count}.", debug_stats
    except Exception as e:
        LOGGER.exception("Gaia overlay query failed for gaia_source_id=%s: %s", target_info.get("gaia_source_id", "unknown"), str(e))
        return [], f"Overlay Gaia non disponibile: {str(e)}", {"error": str(e)}


def _build_real_tpf_overlay(target_info: dict, tpf_payload: dict, wcs) -> dict:
    shape = tuple(tpf_payload.get("shape") or (0, 0))
    gaia_source_id = target_info.get("gaia_source_id", "unknown")

    # Log WCS properties for debugging
    if wcs:
        try:
            wcs_shape = f"has_celestial={wcs.has_celestial}, pixel_shape={wcs.pixel_shape}"
            LOGGER.info("Building overlay for gaia_source_id=%s with WCS: %s, TPF shape=%s", gaia_source_id, wcs_shape, shape)
        except Exception:
            LOGGER.info("Building overlay for gaia_source_id=%s with WCS (unable to log properties), TPF shape=%s", gaia_source_id, shape)
    else:
        LOGGER.warning("Building overlay for gaia_source_id=%s with no WCS", gaia_source_id)

    target_position = _build_target_position(target_info, shape, wcs)
    gaia_sources, overlay_message, debug_stats = _fetch_gaia_overlay_sources(target_info, shape, wcs)
    metadata = tpf_payload.get("metadata") if isinstance(tpf_payload.get("metadata"), dict) else {}
    debug_stats["wcs_source"] = metadata.get("wcs_source")
    debug_stats["wcs_warning"] = metadata.get("wcs_warning")
    debug_stats["flux_shape"] = metadata.get("flux_shape")
    debug_stats["target_pixel_x"] = target_position.get("x")
    debug_stats["target_pixel_y"] = target_position.get("y")
    debug_stats["target_pixel_source"] = target_position.get("source")
    if point_is_inside_grid(target_position.get("x"), target_position.get("y"), shape):
        rows = int(shape[0])
        cols = int(shape[1])
        edge_margin = min(
            float(target_position["x"]) + 0.5,
            float(target_position["y"]) + 0.5,
            (cols - 0.5) - float(target_position["x"]),
            (rows - 0.5) - float(target_position["y"]),
        )
        if edge_margin < 1.0:
            debug_stats["target_edge_warning"] = "Target Gaia entro 1 pixel dal bordo del TPF."

    LOGGER.info("Overlay build complete for gaia_source_id=%s: target_position=%s, gaia_sources_count=%d",
                gaia_source_id, target_position.get("source"), len(gaia_sources))

    return {
        "status": "ok",
        "message": overlay_message,
        "target_position": target_position,
        "gaia_sources": gaia_sources,
        "variable_sources_count": sum(1 for item in gaia_sources if item.get("is_variable")),
        "debug_stats": debug_stats,
    }


def _add_crval_target_debug(tpf_payload: dict, target_info: dict, tpf_wcs) -> None:
    if tpf_wcs is None or target_info.get("ra_deg") is None:
        return
    try:
        crval1 = float(tpf_wcs.wcs.crval[0])
        crval2 = float(tpf_wcs.wcs.crval[1])
        target_ra = float(target_info["ra_deg"])
        target_dec = float(target_info["dec_deg"])
        if "metadata" not in tpf_payload:
            tpf_payload["metadata"] = {}
        if "wcs_debug" not in tpf_payload["metadata"]:
            tpf_payload["metadata"]["wcs_debug"] = {}
        tpf_payload["metadata"]["wcs_debug"]["crval_vs_target"] = {
            "wcs_crval": [round(crval1, 5), round(crval2, 5)],
            "target_info": [round(target_ra, 5), round(target_dec, 5)],
            "delta_ra_arcsec": round((crval1 - target_ra) * 3600, 2),
            "delta_dec_arcsec": round((crval2 - target_dec) * 3600, 2),
        }
    except Exception as e:
        LOGGER.debug("Failed to add CRVAL alignment diagnostic: %s", str(e))


def build_tpf_metadata_payload(gaia_source_id: str, sector) -> dict:
    normalized_gaia_source_id = validate_gaia_source_id(gaia_source_id)
    normalized_sector = validate_sector(sector)
    real_tpf = load_local_tpf(normalized_gaia_source_id, normalized_sector, settings.local_tpf_data_dir, include_frames=False)
    target_info, gaia_status = _resolve_target_info_with_fallback(normalized_gaia_source_id, real_tpf=real_tpf)
    if real_tpf is None:
        return {
            "status": "ok",
            "metadata": {"gaia_status": gaia_status},
            "target_info": target_info,
            "overlay": _empty_overlay_payload("Overlay Gaia disponibile solo con TPF reale e WCS utilizzabile."),
        }

    real_tpf.pop("_time_values", None)
    real_tpf.pop("_flux_cube", None)
    tpf_wcs = real_tpf.pop("_wcs", None)
    tpf_payload = real_tpf
    metadata = _resolve_reference_magnitude(target_info, tpf_payload.get("metadata"))
    metadata["gaia_status"] = gaia_status
    tpf_payload["metadata"] = metadata
    overlay = _build_real_tpf_overlay(target_info, tpf_payload, tpf_wcs)
    _add_crval_target_debug(tpf_payload, target_info, tpf_wcs)
    return {
        "status": "ok",
        "metadata": tpf_payload.get("metadata") or metadata,
        "target_info": target_info,
        "overlay": overlay,
    }


def _build_flux_grid(target_info: dict, nearby_sources: list[dict]) -> list[list[float]]:
    size = PREVIEW_SIZE_PX
    center = size // 2
    sigma_px = 0.85
    target_weight = _relative_flux_from_gmag(target_info.get("gmag"), target_info.get("gmag"))
    sources = [{"x": 0.0, "y": 0.0, "weight": target_weight}]
    for source in nearby_sources:
        sources.append(
            {
                "x": float(source.get("offset_x_px") or 0.0),
                "y": float(source.get("offset_y_px") or 0.0),
                "weight": _relative_flux_from_gmag(source.get("gmag"), target_info.get("gmag")),
            }
        )

    grid = []
    peak = 0.0
    for row in range(size):
        row_values = []
        for col in range(size):
            x = col - center
            y = row - center
            value = 0.0
            for source in sources:
                dx = x - source["x"]
                dy = y - source["y"]
                value += source["weight"] * math.exp(-((dx * dx + dy * dy) / (2.0 * sigma_px * sigma_px)))
            peak = max(peak, value)
            row_values.append(value)
        grid.append(row_values)
    if peak <= 0:
        return [[0.0 for _ in range(size)] for _ in range(size)]
    return [[round((value / peak) * 100.0, 3) for value in row] for row in grid]


def _build_tpf_preview(target_info: dict, sector: int, nearby_sources: list[dict]) -> dict:
    flux_grid = _build_flux_grid(target_info, nearby_sources)
    center = PREVIEW_SIZE_PX // 2
    return {
        "status": "ok",
        "available": True,
        "mode": "preview",
        "message": f"Preview TPF sintetica attiva: nessun file locale trovato per gaia_source_id={target_info['gaia_source_id']} e sector={sector}.",
        "pixel_scale_arcsec": PIXEL_SCALE_ARCSEC,
        "suggested_cutout_size_px": PREVIEW_SIZE_PX,
        "target": target_info,
        "nearby_sources": nearby_sources,
        "flux_grid": flux_grid,
        "source": {
            "type": "synthetic_preview",
            "path": None,
            "filename": None,
            "lookup_key": {
                "gaia_source_id": target_info["gaia_source_id"],
                "sector": sector,
            },
        },
        "metadata": {
            "sector": sector,
            "camera": None,
            "ccd": None,
            "tessmag": None,
            "ticid": None,
        },
        "masks": _empty_masks_payload("Maschere automatiche disponibili solo con TPF reale."),
        "frames": _empty_frames_payload("Navigazione frame disponibile solo con TPF reale."),
        "overlay": {
            "status": "preview",
            "message": "Overlay Gaia e target disponibile solo con TPF reale e WCS utilizzabile.",
            "target_position": {
                "x": center,
                "y": center,
                "source": "fallback-center",
            },
            "gaia_sources": [],
        },
        "preview": {
            "center_pixel": {"x": center, "y": center},
            "neighbors_count": len(nearby_sources),
        },
    }


def run_tpf_pipeline(gaia_source_id: str, sector, masks: dict | None = None, skip_target_info: bool = False) -> dict:
    normalized_gaia_source_id = validate_gaia_source_id(gaia_source_id)
    normalized_sector = validate_sector(sector)
    pipeline_started_at = perf_counter()
    LOGGER.info(
        "Starting TPF pipeline for gaia_source_id=%s sector=%s manual_masks=%s skip_target_info=%s",
        normalized_gaia_source_id,
        normalized_sector,
        bool(masks),
        skip_target_info,
    )
    try:
        load_tpf_started_at = perf_counter()
        real_tpf = load_local_tpf(normalized_gaia_source_id, normalized_sector, settings.local_tpf_data_dir, include_frames=False)
        LOGGER.info(
            "TPF timing | gaia_source_id=%s sector=%s step=load_local_tpf elapsed_s=%.3f found=%s",
            normalized_gaia_source_id,
            normalized_sector,
            perf_counter() - load_tpf_started_at,
            bool(real_tpf),
        )
        target_fetch_started_at = perf_counter()
        if real_tpf is not None and skip_target_info:
            target_info = {
                "gaia_source_id": normalized_gaia_source_id,
                "ra_deg": None,
                "dec_deg": None,
                "gmag": None,
            }
            gaia_status = {
                "available": False,
                "mode": "skipped",
                "message": "Metadata risolto asincrono.",
            }
            LOGGER.info(
                "TPF timing | gaia_source_id=%s sector=%s step=fetch_target elapsed_s=%.3f gaia_available=%s",
                normalized_gaia_source_id,
                normalized_sector,
                perf_counter() - target_fetch_started_at,
                False,
            )
        else:
            target_info, gaia_status = _resolve_target_info_with_fallback(normalized_gaia_source_id, real_tpf=real_tpf)
        LOGGER.info(
            "TPF timing | gaia_source_id=%s sector=%s step=fetch_target elapsed_s=%.3f gaia_available=%s",
            normalized_gaia_source_id,
            normalized_sector,
            perf_counter() - target_fetch_started_at,
            gaia_status.get("available"),
        )
        if real_tpf is not None:
            LOGGER.info("Using real local TPF for gaia_source_id=%s sector=%s", normalized_gaia_source_id, normalized_sector)
            raw_time = real_tpf.pop("_time_values", None)
            raw_flux_cube = real_tpf.pop("_flux_cube", None)
            tpf_wcs = real_tpf.pop("_wcs", None)
            tpf_payload = real_tpf

            reference_mag_started_at = perf_counter()
            if target_info.get("ra_deg") is not None:
                tpf_payload["metadata"] = _resolve_reference_magnitude(target_info, tpf_payload.get("metadata"))
            else:
                tpf_payload["metadata"] = tpf_payload.get("metadata") or {}
                tpf_payload["metadata"]["reference_mag_value"] = None
                tpf_payload["metadata"]["reference_mag_band"] = None
                tpf_payload["metadata"]["reference_mag_key"] = None
                tpf_payload["metadata"]["reference_mag_source"] = None
            tpf_payload["metadata"]["gaia_status"] = gaia_status
            LOGGER.info(
                "TPF timing | gaia_source_id=%s sector=%s step=resolve_reference_magnitude elapsed_s=%.3f reference_band=%s reference_source=%s",
                normalized_gaia_source_id,
                normalized_sector,
                perf_counter() - reference_mag_started_at,
                tpf_payload["metadata"].get("reference_mag_band"),
                tpf_payload["metadata"].get("reference_mag_source"),
            )
            overlay_started_at = perf_counter()
            if target_info.get("ra_deg") is not None:
                tpf_payload["overlay"] = _build_real_tpf_overlay(target_info, tpf_payload, tpf_wcs)
            else:
                tpf_payload["overlay"] = {"gaia_sources": [], "message": "Overlay caricato asincrono."}
            LOGGER.info(
                "TPF timing | gaia_source_id=%s sector=%s step=build_overlay elapsed_s=%.3f sources=%s",
                normalized_gaia_source_id,
                normalized_sector,
                perf_counter() - overlay_started_at,
                len(tpf_payload["overlay"].get("gaia_sources") or []),
            )
            pipeline_mode = "real"
            tpf_payload["masks"] = _empty_masks_payload("Maschere non disponibili.")
            lightcurve = compute_lightcurve_stub(
                normalized_gaia_source_id,
                target_info,
                "Light curve reale non disponibile: errore nella costruzione iniziale.",
            )
            if raw_time is not None and raw_flux_cube is not None:
                if masks is not None:
                    manual_masks_started_at = perf_counter()
                    masks_payload, target_mask, background_mask = normalize_manual_masks(masks, tuple(raw_flux_cube.shape[1:]))
                    tpf_payload["masks"] = masks_payload
                    LOGGER.info(
                        "TPF timing | gaia_source_id=%s sector=%s step=normalize_manual_masks elapsed_s=%.3f",
                        normalized_gaia_source_id,
                        normalized_sector,
                        perf_counter() - manual_masks_started_at,
                    )
                    manual_lightcurve_started_at = perf_counter()
                    lightcurve = compute_real_lightcurve(
                        raw_time,
                        raw_flux_cube,
                        target_mask,
                        background_mask,
                            gaia_source_id=normalized_gaia_source_id,
                            tpf_source=tpf_payload.get("source"),
                            tpf_metadata=tpf_payload.get("metadata"),
                            extraction_metadata={
                                "mask_origin": "manual",
                                "target_threshold": None,
                                "background_threshold": None,
                                "sigma_clipping": None,
                            },
                        mode="real-manual-mask",
                        message="Light curve aggiornata con maschere modificate manualmente.",
                    )
                    LOGGER.info(
                        "TPF timing | gaia_source_id=%s sector=%s step=compute_real_lightcurve_manual elapsed_s=%.3f points=%s",
                        normalized_gaia_source_id,
                        normalized_sector,
                        perf_counter() - manual_lightcurve_started_at,
                        len(lightcurve.get("time") or []),
                    )
                else:
                    try:
                        auto_masks_started_at = perf_counter()
                        masks_payload, target_mask, background_mask = build_auto_masks(raw_flux_cube)
                        tpf_payload["masks"] = masks_payload
                        LOGGER.info(
                            "TPF timing | gaia_source_id=%s sector=%s step=build_auto_masks elapsed_s=%.3f",
                            normalized_gaia_source_id,
                            normalized_sector,
                            perf_counter() - auto_masks_started_at,
                        )
                        auto_lightcurve_started_at = perf_counter()
                        lightcurve = compute_real_lightcurve(
                            raw_time,
                            raw_flux_cube,
                            target_mask,
                            background_mask,
                            gaia_source_id=normalized_gaia_source_id,
                            tpf_source=tpf_payload.get("source"),
                            tpf_metadata=tpf_payload.get("metadata"),
                            extraction_metadata={
                                "mask_origin": "auto",
                                "target_threshold": f"median_grid > background + {AUTO_TARGET_THRESHOLD_SIGMA} * scatter",
                                "background_threshold": f"median_grid <= background + {AUTO_BACKGROUND_THRESHOLD_SIGMA} * scatter",
                                "sigma_clipping": None,
                            },
                        )
                        LOGGER.info(
                            "TPF timing | gaia_source_id=%s sector=%s step=compute_real_lightcurve_auto elapsed_s=%.3f points=%s",
                            normalized_gaia_source_id,
                            normalized_sector,
                            perf_counter() - auto_lightcurve_started_at,
                            len(lightcurve.get("time") or []),
                        )
                    except Exception as err:
                        LOGGER.exception(
                            "Automatic mask/light curve generation failed for gaia_source_id=%s sector=%s",
                            normalized_gaia_source_id,
                            normalized_sector,
                        )
                        lightcurve = compute_lightcurve_stub(
                            normalized_gaia_source_id,
                            target_info,
                            f"Light curve reale non disponibile: {err}",
                        )
            else:
                LOGGER.warning(
                    "Real TPF loaded without raw time/flux for gaia_source_id=%s sector=%s",
                    normalized_gaia_source_id,
                    normalized_sector,
                )
                lightcurve = compute_lightcurve_stub(
                    normalized_gaia_source_id,
                    target_info,
                    "Light curve reale non disponibile: dati temporali o cubo FLUX assenti.",
                )

            _add_crval_target_debug(tpf_payload, target_info, tpf_wcs)
        else:
            LOGGER.info("Falling back to synthetic TPF preview for gaia_source_id=%s sector=%s", normalized_gaia_source_id, normalized_sector)
            nearby_sources = _fetch_nearby_gaia_sources(target_info)
            tpf_payload = _build_tpf_preview(target_info, normalized_sector, nearby_sources)
            pipeline_mode = "preview"
            lightcurve = compute_lightcurve_stub(
                normalized_gaia_source_id,
                target_info,
                "Light curve non disponibile: il TPF reale non e' stato trovato, resta attivo il fallback sintetico.",
            )

        LOGGER.info(
            "TPF timing | gaia_source_id=%s sector=%s step=run_tpf_pipeline_total elapsed_s=%.3f mode=%s",
            normalized_gaia_source_id,
            normalized_sector,
            perf_counter() - pipeline_started_at,
            pipeline_mode,
        )
        return {
            "status": "ok",
            "message": gaia_status.get("message") if not gaia_status.get("available") else "Pipeline TPF completata correttamente.",
            "mode": pipeline_mode,
            "input": {"gaia_source_id": normalized_gaia_source_id, "sector": normalized_sector},
            "gaia": gaia_status,
            "target": target_info,
            "tpf": tpf_payload,
            "lightcurve": lightcurve,
            "save": {
                "status": "idle",
                "message": "Nessun salvataggio automatico eseguito durante il Run.",
                "mode": "manual",
                "saved": False,
                "save_id": None,
                "summary": {
                    "gaia_source_id": normalized_gaia_source_id,
                    "sector": normalized_sector,
                    "tpf_available": bool(tpf_payload.get("available")),
                    "lightcurve_available": bool(lightcurve.get("available")),
                },
            },
        }
    except ValueError:
        LOGGER.warning(
            "TPF pipeline validation failed for gaia_source_id=%s sector=%s",
            normalized_gaia_source_id,
            normalized_sector,
        )
        raise
    except Exception:
        LOGGER.exception("TPF pipeline failed for gaia_source_id=%s sector=%s", normalized_gaia_source_id, normalized_sector)
        raise


def load_tpf_frame_window(gaia_source_id: str, sector, frame_start: int, frame_end: int) -> dict:
    normalized_gaia_source_id = validate_gaia_source_id(gaia_source_id)
    normalized_sector = validate_sector(sector)
    safe_frame_start = int(frame_start)
    safe_frame_end = int(frame_end)
    if safe_frame_start < 0 or safe_frame_end < 0:
        raise ValueError("Intervallo frame non valido")
    if safe_frame_end < safe_frame_start:
        raise ValueError("Intervallo frame non valido")

    frames_payload = load_local_tpf_frames(
        normalized_gaia_source_id,
        normalized_sector,
        settings.local_tpf_data_dir,
        safe_frame_start,
        safe_frame_end,
    )
    if frames_payload is None:
        raise ValueError("Frame TPF reali non disponibili per il target richiesto")

    return {
        "status": "ok",
        "message": "Frame TPF caricati correttamente.",
        "input": {
            "gaia_source_id": normalized_gaia_source_id,
            "sector": normalized_sector,
            "frame_start": safe_frame_start,
            "frame_end": safe_frame_end,
        },
        "frames": frames_payload,
    }
