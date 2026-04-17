from __future__ import annotations

import logging
import math

import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord
from flask import jsonify, render_template, request, url_for

from . import mappe_stelle_bp
from .services.gaia_service import GaiaQueryError, get_target_by_source_id, query_field_stars
from .services.projection import project_tangent_offsets_arcsec
from .services.variables_service import query_known_variables

MATCH_RADIUS_ARCSEC = 2.0
TOP_CONTAMINANTS_N = 20
logger = logging.getLogger(__name__)


def _parse_float_arg(name: str, default: float, *, gt_zero: bool = True) -> float:
    raw = request.args.get(name, default)
    value = float(raw)
    if gt_zero and value <= 0:
        raise ValueError(f"{name} must be > 0")
    return value


def _parse_int_arg(name: str, default: int, *, gt_zero: bool = True) -> int:
    raw = request.args.get(name, default)
    value = int(raw)
    if gt_zero and value <= 0:
        raise ValueError(f"{name} must be > 0")
    return value


def _parse_overlay_radii_pixels(raw: str) -> list[int]:
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    if not parts:
        raise ValueError("overlay_radii_pixels must contain at least one integer")

    radii: list[int] = []
    for part in parts:
        value = int(part)
        if value <= 0:
            raise ValueError("overlay_radii_pixels must contain positive integers")
        if value not in radii:
            radii.append(value)
    return radii


def _normalize_source_id() -> str:
    source_id = (request.args.get("gaia_id") or request.args.get("source_id") or "").strip()
    if not source_id:
        raise ValueError("gaia_id or source_id is required")
    return source_id


def _build_field_star_map_payload(
    *,
    source_id: str,
    half_size_arcmin: float,
    delta_mag: float,
    pixel_scale_arcsec: float,
    tess_prf_sigma_pixels: float,
    overlay_radii_pixels: list[int],
    max_results: int,
) -> tuple[dict, int]:
    notes: list[str] = []
    half_size_arcsec = half_size_arcmin * 60.0
    cone_radius_arcmin = half_size_arcmin * math.sqrt(2)
    tess_prf_sigma_arcsec = tess_prf_sigma_pixels * pixel_scale_arcsec

    try:
        target = get_target_by_source_id(source_id)
        if target is None:
            return {"error": "source_id not found", "source_id": source_id}, 404

        mag_limit = target.g_mag + delta_mag
        field = query_field_stars(
            ra_deg=target.ra,
            dec_deg=target.dec,
            cone_radius_arcmin=cone_radius_arcmin,
            g_mag_limit=mag_limit,
            max_results=max_results,
        )
    except ValueError as exc:
        return {"error": str(exc)}, 422
    except GaiaQueryError as exc:
        return {"error": "Gaia query failed", "detail": str(exc)}, 502

    ra_values = [star["ra"] for star in field.stars]
    dec_values = [star["dec"] for star in field.stars]
    x_arcsec, y_arcsec = project_tangent_offsets_arcsec(ra_values, dec_values, target.ra, target.dec)

    mask_square = (np.abs(x_arcsec) <= half_size_arcsec) & (np.abs(y_arcsec) <= half_size_arcsec)

    square_stars: list[dict] = []
    for idx, star in enumerate(field.stars):
        if not bool(mask_square[idx]):
            continue

        g_mag = star["g_mag"]
        star_delta_mag = g_mag - target.g_mag
        flux_ratio = float(10 ** (-0.4 * star_delta_mag))
        x_val = float(x_arcsec[idx])
        y_val = float(y_arcsec[idx])
        r_arcsec = float(math.hypot(x_val, y_val))
        distance_weight = math.exp(-0.5 * (r_arcsec / tess_prf_sigma_arcsec) ** 2)
        weighted_flux_ratio = float(flux_ratio * distance_weight)

        square_stars.append(
            {
                "source_id": star["source_id"],
                "ra": star["ra"],
                "dec": star["dec"],
                "x_arcsec": x_val,
                "y_arcsec": y_val,
                "r_arcsec": r_arcsec,
                "g_mag": g_mag,
                "delta_mag": float(star_delta_mag),
                "flux_ratio": flux_ratio,
                "weighted_flux_ratio": weighted_flux_ratio,
                "is_variable": False,
                "var_catalog": None,
                "var_type": None,
                "var_name": None,
                "period_days": None,
            }
        )

    try:
        variables = query_known_variables(target.ra, target.dec, cone_radius_arcmin)
    except Exception as exc:  # noqa: BLE001
        variables = []
        notes.append(f"Variable catalog query failed: {exc}")

    if square_stars and variables:
        star_coords = SkyCoord(
            ra=[star["ra"] for star in square_stars] * u.deg,
            dec=[star["dec"] for star in square_stars] * u.deg,
            frame="icrs",
        )
        var_coords = SkyCoord(
            ra=[item.ra for item in variables] * u.deg,
            dec=[item.dec for item in variables] * u.deg,
            frame="icrs",
        )

        idx_match, sep2d, _ = star_coords.match_to_catalog_sky(var_coords)
        for i, separation in enumerate(sep2d):
            if separation.arcsec <= MATCH_RADIUS_ARCSEC:
                matched = variables[int(idx_match[i])]
                square_stars[i]["is_variable"] = True
                square_stars[i]["var_catalog"] = matched.catalog
                square_stars[i]["var_type"] = matched.var_type
                square_stars[i]["var_name"] = matched.name
                square_stars[i]["period_days"] = matched.period_days

    if field.truncated:
        notes.append(f"Result set truncated to max_results={max_results}.")

    top_contaminants = sorted(square_stars, key=lambda item: item["weighted_flux_ratio"], reverse=True)[:TOP_CONTAMINANTS_N]

    return {
        "target": {
            "source_id": target.source_id,
            "ra": target.ra,
            "dec": target.dec,
            "g_mag": target.g_mag,
        },
        "params": {
            "half_size_arcmin": half_size_arcmin,
            "half_size_arcsec": half_size_arcsec,
            "delta_mag": delta_mag,
            "pixel_scale_arcsec": pixel_scale_arcsec,
            "overlay_radii_pixels": overlay_radii_pixels,
            "overlay_radii_arcsec": [float(pixel_scale_arcsec * radius) for radius in overlay_radii_pixels],
            "cone_radius_arcmin": cone_radius_arcmin,
            "match_radius_arcsec": MATCH_RADIUS_ARCSEC,
            "tess_prf_sigma_pixels": tess_prf_sigma_pixels,
            "tess_prf_sigma_arcsec": tess_prf_sigma_arcsec,
        },
        "stars": square_stars,
        "top_contaminants": top_contaminants,
        "meta": {
            "stars_cone_count": field.cone_count,
            "stars_square_count": len(square_stars),
            "truncated": field.truncated,
            "notes": notes,
        },
    }, 200


@mappe_stelle_bp.get("")
@mappe_stelle_bp.get("/")
def index():
    initial_gaia_id = (request.args.get("gaia_id") or request.args.get("source_id") or "5853498713190525696").strip()
    return render_template(
        "mappe_stelle/index.html",
        api_base_url=request.script_root + url_for("mappe_stelle.health").rsplit("/health", 1)[0],
        initial_gaia_id=initial_gaia_id,
    )


@mappe_stelle_bp.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@mappe_stelle_bp.get("/api/field-star-map")
def field_star_map():
    try:
        source_id = _normalize_source_id()
        half_size_arcmin = _parse_float_arg("half_size_arcmin", 3.5)
        delta_mag = _parse_float_arg("delta_mag", 6.0)
        pixel_scale_arcsec = _parse_float_arg("pixel_scale_arcsec", 21.0)
        tess_prf_sigma_pixels = _parse_float_arg("tess_prf_sigma_pixels", 1.0)
        overlay_radii_pixels = _parse_overlay_radii_pixels(request.args.get("overlay_radii_pixels", "1,2,3,5"))
        max_results = _parse_int_arg("max_results", 5000)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    try:
        payload, status_code = _build_field_star_map_payload(
            source_id=source_id,
            half_size_arcmin=half_size_arcmin,
            delta_mag=delta_mag,
            pixel_scale_arcsec=pixel_scale_arcsec,
            tess_prf_sigma_pixels=tess_prf_sigma_pixels,
            overlay_radii_pixels=overlay_radii_pixels,
            max_results=max_results,
        )
        return jsonify(payload), status_code
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error in mappe_stelle API")
        return jsonify({"error": "Internal server error", "detail": str(exc)}), 500
