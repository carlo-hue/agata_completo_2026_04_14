from __future__ import annotations

import math

import numpy as np
from astropy.coordinates import EarthLocation, SkyCoord
from astropy.stats import SigmaClip
from astropy.time import Time
import astropy.units as u
from photutils.aperture import (
    ApertureStats,
    CircularAnnulus,
    CircularAperture,
    aperture_photometry,
)
from photutils.centroids import centroid_com

from .utils import rounded_or_none

# Sigma-clipping usato per la stima del background nell'anello (standard AstroImageJ).
_SIGMA_CLIP = SigmaClip(sigma=3.0, maxiters=5)


def normalize_photometry_params(payload: dict, defaults: dict) -> dict:
    aperture_radius = float(payload.get("aperture_radius", defaults["aperture_radius"]))
    annulus_inner_radius = float(payload.get("annulus_inner_radius", defaults["annulus_inner_radius"]))
    annulus_outer_radius = float(payload.get("annulus_outer_radius", defaults["annulus_outer_radius"]))
    if aperture_radius <= 0:
        raise ValueError("aperture_radius deve essere > 0")
    if annulus_inner_radius <= aperture_radius:
        raise ValueError("annulus_inner_radius deve essere maggiore di aperture_radius")
    if annulus_outer_radius <= annulus_inner_radius:
        raise ValueError("annulus_outer_radius deve essere maggiore di annulus_inner_radius")
    return {
        "aperture_radius": aperture_radius,
        "annulus_inner_radius": annulus_inner_radius,
        "annulus_outer_radius": annulus_outer_radius,
    }


def measure_reference_aperture_metrics(
    reference_frame: dict,
    *,
    points: list[dict],
    params: dict,
    refine_points: bool = True,
) -> list[dict]:
    data = np.asarray(reference_frame["data"], dtype=float)
    valid_items = []
    for item in points:
        if not isinstance(item, dict) or item.get("x") is None or item.get("y") is None:
            continue
        valid_items.append({
            "raw": item,
            "point": (float(item["x"]), float(item["y"])),
        })
    if not valid_items:
        return []

    refined_points = [
        _refine_centroid(data, item["point"]) if refine_points else item["point"]
        for item in valid_items
    ]
    aperture = CircularAperture(refined_points, r=float(params["aperture_radius"]))
    annulus = CircularAnnulus(
        refined_points,
        r_in=float(params["annulus_inner_radius"]),
        r_out=float(params["annulus_outer_radius"]),
    )
    phot_ap = aperture_photometry(data, aperture)

    # Sigma-clipped median per pixel nell'anello: robusto alle stelle contaminanti.
    annulus_stats = ApertureStats(data, annulus, sigma_clip=_SIGMA_CLIP)
    sky_per_px = np.asarray(annulus_stats.median, dtype=float)
    net_flux = np.asarray(phot_ap["aperture_sum"], dtype=float) - sky_per_px * aperture.area

    results = []
    for index, item in enumerate(valid_items):
        refined_point = refined_points[index]
        raw_diagnostics = _local_point_diagnostics(
            data,
            item["point"],
            aperture_radius=float(params["aperture_radius"]),
            annulus_inner_radius=float(params["annulus_inner_radius"]),
            annulus_outer_radius=float(params["annulus_outer_radius"]),
        )
        diagnostics = _local_point_diagnostics(
            data,
            refined_point,
            aperture_radius=float(params["aperture_radius"]),
            annulus_inner_radius=float(params["annulus_inner_radius"]),
            annulus_outer_radius=float(params["annulus_outer_radius"]),
        )
        results.append({
            "x": rounded_or_none(item["point"][0], 3),
            "y": rounded_or_none(item["point"][1], 3),
            "refined_x": rounded_or_none(refined_point[0], 3),
            "refined_y": rounded_or_none(refined_point[1], 3),
            "centroid_shift_px": rounded_or_none(
                float(math.hypot(refined_point[0] - item["point"][0], refined_point[1] - item["point"][1])),
                4,
            ),
            "aperture_sum_adu": rounded_or_none(float(phot_ap["aperture_sum"][index]), 3),
            "aperture_net_adu": rounded_or_none(float(net_flux[index]), 3),
            # sky_per_px: mediana sigma-clipped dell'anello (ADU/pixel).
            "annulus_sky_per_px": rounded_or_none(float(sky_per_px[index]), 3),
            "raw_peak_adu": raw_diagnostics.get("peak_adu"),
            "raw_local_max_5x5_adu": raw_diagnostics.get("local_max_5x5_adu"),
            **diagnostics,
        })
    return results


def run_differential_photometry(
    dataset_summary: dict,
    *,
    target: dict,
    comparison_stars: list[dict],
    included_frame_indices: list[int],
    params: dict,
) -> dict:
    if target is None or target.get("x") is None or target.get("y") is None:
        raise ValueError("Target mancante o non valido")
    if not comparison_stars:
        raise ValueError("Serve almeno una comparison star")
    if not included_frame_indices:
        raise ValueError("Nessun frame selezionato per la fotometria")

    frames = dataset_summary["frames"]
    target_point = (float(target["x"]), float(target["y"]))
    comparison_points = [(float(item["x"]), float(item["y"])) for item in comparison_stars]

    # RA/Dec del target per correzione baricentrica (disponibili solo se WCS risolto).
    target_ra_deg = _safe_float(target.get("ra_deg"))
    target_dec_deg = _safe_float(target.get("dec_deg"))

    target_flux = []
    comparison_flux = []
    comparison_individual_flux = []   # flusso netto per ogni comparison star, per frame
    normalized_flux = []
    differential_mag = []
    sigma_differential_mag_series = []
    sigma_normalized_flux_series = []
    time_jd = []
    bjd_tdb_series = []
    centroid_shift = []
    per_frame_rows = []
    refined_target_positions = []

    for frame_index in included_frame_indices:
        frame = frames[int(frame_index)]
        data = np.asarray(frame["data"], dtype=float)
        header = frame.get("header") or {}

        refined_target = _refine_centroid(data, target_point)
        refined_comparisons = [_refine_centroid(data, point) for point in comparison_points]
        positions = [refined_target, *refined_comparisons]

        aperture = CircularAperture(positions, r=float(params["aperture_radius"]))
        annulus = CircularAnnulus(
            positions,
            r_in=float(params["annulus_inner_radius"]),
            r_out=float(params["annulus_outer_radius"]),
        )

        phot_ap = aperture_photometry(data, aperture)

        # Background: mediana sigma-clipped dell'anello per pixel (immune a stelle contaminanti).
        annulus_stats = ApertureStats(data, annulus, sigma_clip=_SIGMA_CLIP)
        sky_per_px = np.asarray(annulus_stats.median, dtype=float)
        net_flux = np.asarray(phot_ap["aperture_sum"], dtype=float) - sky_per_px * aperture.area

        current_target_flux = float(net_flux[0])
        current_comparison_individual = [float(net_flux[i + 1]) for i in range(len(comparison_points))]
        current_comparison_flux = float(np.nansum(current_comparison_individual))

        current_ratio = current_target_flux / max(current_comparison_flux, 1e-9)
        current_mag = -2.5 * math.log10(max(current_ratio, 1e-12))

        # Propagazione degli errori: shot noise + sky noise + read noise (Merline & Howell 1995).
        gain, rdnoise_e = _extract_noise_params(header)
        n_pix = float(aperture.area)
        sigma_tgt = _photon_noise_adu(current_target_flux, float(sky_per_px[0]), n_pix, gain, rdnoise_e)
        sigma_comps = [
            _photon_noise_adu(f, float(sky_per_px[i + 1]), n_pix, gain, rdnoise_e)
            for i, f in enumerate(current_comparison_individual)
        ]
        sigma_ens = math.sqrt(sum(s * s for s in sigma_comps))
        sigma_dm = _sigma_differential_mag(current_target_flux, current_comparison_flux, sigma_tgt, sigma_ens)
        sigma_nf = _sigma_normalized_flux(current_target_flux, current_comparison_flux, sigma_tgt, sigma_ens)

        # Correzione baricentrica JD_UTC → BJD_TDB (richiede RA/Dec del target).
        jd_frame = frame.get("time_jd")
        bjd = _compute_bjd_tdb(jd_frame, target_ra_deg, target_dec_deg, header)

        target_flux.append(current_target_flux)
        comparison_flux.append(current_comparison_flux)
        comparison_individual_flux.append(current_comparison_individual)
        normalized_flux.append(current_ratio)
        differential_mag.append(current_mag)
        sigma_differential_mag_series.append(sigma_dm)
        sigma_normalized_flux_series.append(sigma_nf)
        time_jd.append(jd_frame)
        bjd_tdb_series.append(bjd)
        centroid_shift.append(float(math.hypot(
            refined_target[0] - target_point[0],
            refined_target[1] - target_point[1],
        )))
        refined_target_positions.append({
            "x": rounded_or_none(refined_target[0], 3),
            "y": rounded_or_none(refined_target[1], 3),
        })
        per_frame_rows.append({
            "frame_index": int(frame_index),
            "filename": frame.get("filename"),
            "time_jd": jd_frame,
            "bjd_tdb": bjd,
            "target_flux": rounded_or_none(current_target_flux, 6),
            "comparison_flux": rounded_or_none(current_comparison_flux, 6),
            "comparison_individual_flux": [rounded_or_none(f, 6) for f in current_comparison_individual],
            "ratio_flux": rounded_or_none(current_ratio, 8),
            "differential_mag": rounded_or_none(current_mag, 6),
            "sigma_differential_mag": sigma_dm,
            "sigma_normalized_flux": sigma_nf,
            "centroid_shift_px": rounded_or_none(centroid_shift[-1], 4),
        })

    # Normalizzazione al flusso mediano (≈ 1.0 fuori transito / media della serie).
    normalized_flux_array = np.asarray(normalized_flux, dtype=float)
    flux_scale = float(np.nanmedian(normalized_flux_array)) if normalized_flux_array.size else 1.0
    if not math.isfinite(flux_scale) or flux_scale == 0:
        flux_scale = 1.0
    normalized_flux_array = normalized_flux_array / flux_scale

    # Le incertezze sul flusso normalizzato scalano di conseguenza.
    sigma_normalized_flux_array = np.asarray(
        [s / flux_scale if s is not None else None for s in sigma_normalized_flux_series],
        dtype=object,
    )

    ordered_rows = []
    for index, row in enumerate(per_frame_rows):
        ordered_rows.append({
            **row,
            "differential_flux": float(normalized_flux_array[index]),
            # sigma_normalized_flux_array è già diviso per flux_scale.
            "sigma_differential_flux": (
                rounded_or_none(float(sigma_normalized_flux_array[index]), 8)
                if sigma_normalized_flux_array[index] is not None else None
            ),
            "centroid_shift_px": centroid_shift[index],
            "refined_target_position": refined_target_positions[index],
        })

    ordered_rows.sort(
        key=lambda item: (
            item["time_jd"] is None,
            float(item["time_jd"]) if item["time_jd"] is not None else float("inf"),
            item["frame_index"],
        )
    )

    has_bjd = any(item["bjd_tdb"] is not None for item in ordered_rows)
    has_errors = any(item["sigma_differential_mag"] is not None for item in ordered_rows)

    return {
        "available": True,
        "message": "Fotometria differential aperture eseguita sul server.",
        "params": params,
        "background_method": "sigma-clipped median (3σ, 5 iter)",
        "selection": {
            "target": {
                "x": rounded_or_none(target_point[0], 3),
                "y": rounded_or_none(target_point[1], 3),
            },
            "comparison_stars": [
                {"x": rounded_or_none(point[0], 3), "y": rounded_or_none(point[1], 3)}
                for point in comparison_points
            ],
            "included_frame_indices": [int(item["frame_index"]) for item in ordered_rows],
        },
        "series": {
            "time_jd": [rounded_or_none(item["time_jd"], 8) for item in ordered_rows],
            "bjd_tdb": [rounded_or_none(item["bjd_tdb"], 8) for item in ordered_rows] if has_bjd else None,
            "target_flux": [rounded_or_none(item["target_flux"], 6) for item in ordered_rows],
            "comparison_flux": [rounded_or_none(item["comparison_flux"], 6) for item in ordered_rows],
            "differential_flux": [rounded_or_none(item["differential_flux"], 8) for item in ordered_rows],
            "differential_mag": [rounded_or_none(item["differential_mag"], 6) for item in ordered_rows],
            "sigma_differential_mag": (
                [item["sigma_differential_mag"] for item in ordered_rows] if has_errors else None
            ),
            "sigma_differential_flux": (
                [item.get("sigma_differential_flux") for item in ordered_rows] if has_errors else None
            ),
            "centroid_shift_px": [rounded_or_none(item["centroid_shift_px"], 4) for item in ordered_rows],
        },
        "per_frame": [
            {
                "frame_index": int(item["frame_index"]),
                "filename": item.get("filename"),
                "time_jd": rounded_or_none(item["time_jd"], 8),
                "bjd_tdb": rounded_or_none(item["bjd_tdb"], 8),
                "target_flux": rounded_or_none(item["target_flux"], 6),
                "comparison_flux": rounded_or_none(item["comparison_flux"], 6),
                "comparison_individual_flux": item.get("comparison_individual_flux"),
                "ratio_flux": rounded_or_none(item["differential_flux"], 8),
                "differential_mag": rounded_or_none(item["differential_mag"], 6),
                "sigma_differential_mag": item.get("sigma_differential_mag"),
                "centroid_shift_px": rounded_or_none(item["centroid_shift_px"], 4),
            }
            for item in ordered_rows
        ],
        "summary": {
            "used_frames": len(included_frame_indices),
            "time_min_jd": (
                rounded_or_none(min(item for item in time_jd if item is not None), 8)
                if any(item is not None for item in time_jd) else None
            ),
            "time_max_jd": (
                rounded_or_none(max(item for item in time_jd if item is not None), 8)
                if any(item is not None for item in time_jd) else None
            ),
            "bjd_tdb_available": has_bjd,
            "errors_available": has_errors,
            "normalized_flux_scatter": rounded_or_none(float(np.nanstd(normalized_flux_array)), 8),
            "centroid_shift_median_px": rounded_or_none(
                float(np.nanmedian(np.asarray(centroid_shift, dtype=float))), 4
            ),
        },
        "diagnostics": {
            "refined_target_positions": [item["refined_target_position"] for item in ordered_rows],
        },
    }


# ---------------------------------------------------------------------------
# Helpers: noise model
# ---------------------------------------------------------------------------

def _extract_noise_params(header) -> tuple[float, float]:
    """Returns (gain e-/ADU, read_noise e-). Falls back to gain=1, rdnoise=0."""
    gain = None
    for key in ("EGAIN", "GAIN"):
        try:
            v = float(header.get(key) or 0)
            if v > 0:
                gain = v
                break
        except (TypeError, ValueError):
            pass
    if gain is None:
        gain = 1.0

    rdnoise = 0.0
    for key in ("RDNOISE", "READNOIS", "ENOISE"):
        try:
            v = float(header.get(key) or 0)
            if v >= 0:
                rdnoise = v
                break
        except (TypeError, ValueError):
            pass
    return gain, rdnoise


def _photon_noise_adu(
    net_flux_adu: float,
    sky_per_px: float,
    n_pix: float,
    gain: float,
    rdnoise_e: float,
) -> float:
    """
    Total photometric uncertainty in ADU.
    Merline & Howell (1995): sigma = sqrt(N/G + n*(S/G + (RN/G)^2))
    where N=net flux ADU, G=gain e-/ADU, n=aperture pixels, S=sky/px ADU, RN=read noise e-.
    """
    shot_sq = max(net_flux_adu, 0.0) / max(gain, 1e-9)
    sky_noise_per_px_sq = max(sky_per_px, 0.0) / max(gain, 1e-9) + (rdnoise_e / max(gain, 1e-9)) ** 2
    sky_sq = n_pix * sky_noise_per_px_sq
    return math.sqrt(shot_sq + sky_sq)


def _sigma_differential_mag(
    f_target: float,
    f_ens: float,
    sigma_target: float,
    sigma_ens: float,
) -> float | None:
    """Uncertainty in differential magnitude (mag). Returns None if flux is non-positive."""
    if f_target <= 0 or f_ens <= 0:
        return None
    snr_t = f_target / max(sigma_target, 1e-12)
    snr_e = f_ens / max(sigma_ens, 1e-12)
    return rounded_or_none(1.0857 * math.sqrt(1.0 / snr_t ** 2 + 1.0 / snr_e ** 2), 6)


def _sigma_normalized_flux(
    f_target: float,
    f_ens: float,
    sigma_target: float,
    sigma_ens: float,
) -> float | None:
    """Uncertainty in the raw flux ratio (before series normalization)."""
    if f_target <= 0 or f_ens <= 0:
        return None
    ratio = f_target / max(f_ens, 1e-9)
    rel_err_sq = (sigma_target / max(f_target, 1e-9)) ** 2 + (sigma_ens / max(f_ens, 1e-9)) ** 2
    return rounded_or_none(ratio * math.sqrt(rel_err_sq), 8)


# ---------------------------------------------------------------------------
# Helpers: barycentric time correction
# ---------------------------------------------------------------------------

def _compute_bjd_tdb(
    jd_utc: float | None,
    ra_deg: float | None,
    dec_deg: float | None,
    header,
) -> float | None:
    """
    Converte JD_UTC in BJD_TDB applicando la correzione di light travel time.
    Restituisce None se RA/Dec del target non sono disponibili (WCS non risolto).
    La posizione dell'osservatorio viene letta dall'header FITS (SITELONG/SITELAT);
    in assenza, si usa il geocentro (errore max ~6 ms, trascurabile per uso amatoriale).
    """
    if jd_utc is None or ra_deg is None or dec_deg is None:
        return None
    try:
        t = Time(jd_utc, format="jd", scale="utc")
        target_coord = SkyCoord(ra_deg * u.deg, dec_deg * u.deg)
        lon = _header_float_any(header, "SITELONG", "LONG-OBS", "OBSGEO-L")
        lat = _header_float_any(header, "SITELAT", "LAT-OBS", "OBSGEO-B")
        alt = _header_float_any(header, "SITEELEV", "ALT-OBS", "OBSGEO-H") or 0.0
        if lon is not None and lat is not None:
            location = EarthLocation(lon=lon * u.deg, lat=lat * u.deg, height=float(alt) * u.m)
        else:
            location = EarthLocation.from_geocentric(0, 0, 0, unit=u.m)
        ltt = t.light_travel_time(target_coord, location=location)
        return rounded_or_none(float((t.tdb + ltt).jd), 8)
    except Exception:
        return None


def _header_float_any(header, *keys: str) -> float | None:
    for key in keys:
        try:
            v = header.get(key)
            if v is not None:
                return float(v)
        except (TypeError, ValueError):
            pass
    return None


def _safe_float(value) -> float | None:
    try:
        v = float(value)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Helpers: centroid & diagnostics
# ---------------------------------------------------------------------------

def _refine_centroid(data: np.ndarray, point: tuple[float, float], radius: int = 8) -> tuple[float, float]:
    x0 = int(round(point[0]))
    y0 = int(round(point[1]))
    y1 = max(0, y0 - radius)
    y2 = min(data.shape[0], y0 + radius + 1)
    x1 = max(0, x0 - radius)
    x2 = min(data.shape[1], x0 + radius + 1)
    stamp = np.asarray(data[y1:y2, x1:x2], dtype=float)
    if stamp.size == 0:
        return point
    finite = stamp[np.isfinite(stamp)]
    if finite.size == 0:
        return point
    stamp = stamp - float(np.nanmedian(finite))
    stamp[stamp < 0] = 0
    stamp = np.nan_to_num(stamp, nan=0.0)
    if np.nansum(stamp) <= 0:
        return point
    cy, cx = centroid_com(stamp)
    return float(x1 + cx), float(y1 + cy)


def _local_point_diagnostics(
    data: np.ndarray,
    point: tuple[float, float],
    *,
    aperture_radius: float,
    annulus_inner_radius: float,
    annulus_outer_radius: float,
) -> dict:
    x = float(point[0])
    y = float(point[1])
    radius = max(1.0, float(aperture_radius))
    annulus_inner = max(radius, float(annulus_inner_radius))
    annulus_outer = max(annulus_inner, float(annulus_outer_radius))
    sampling_radius = max(radius, annulus_outer, 2.0)
    x0 = int(round(x))
    y0 = int(round(y))
    y1 = max(0, int(math.floor(y - sampling_radius)))
    y2 = min(data.shape[0], int(math.ceil(y + sampling_radius)) + 1)
    x1 = max(0, int(math.floor(x - sampling_radius)))
    x2 = min(data.shape[1], int(math.ceil(x + sampling_radius)) + 1)
    stamp = np.asarray(data[y1:y2, x1:x2], dtype=float)
    yy, xx = np.indices(stamp.shape)
    local_x = xx + x1
    local_y = yy + y1
    distance = np.hypot(local_x - x, local_y - y)
    aperture_mask = distance <= radius
    annulus_mask = (distance >= annulus_inner) & (distance <= annulus_outer)
    finite_aperture = stamp[aperture_mask]
    finite_aperture = finite_aperture[np.isfinite(finite_aperture)]
    finite_annulus = stamp[annulus_mask]
    finite_annulus = finite_annulus[np.isfinite(finite_annulus)]

    box_y1 = max(0, y0 - 2)
    box_y2 = min(data.shape[0], y0 + 3)
    box_x1 = max(0, x0 - 2)
    box_x2 = min(data.shape[1], x0 + 3)
    local_box = np.asarray(data[box_y1:box_y2, box_x1:box_x2], dtype=float)
    local_box_finite = local_box[np.isfinite(local_box)]

    return {
        "peak_adu": rounded_or_none(float(np.nanmax(finite_aperture)), 3) if finite_aperture.size else None,
        "local_max_5x5_adu": rounded_or_none(float(np.nanmax(local_box_finite)), 3) if local_box_finite.size else None,
        "aperture_area_px": int(finite_aperture.size),
        "annulus_sum_adu": rounded_or_none(float(np.nansum(finite_annulus)), 3) if finite_annulus.size else None,
        "annulus_median_adu": rounded_or_none(float(np.nanmedian(finite_annulus)), 3) if finite_annulus.size else None,
        "annulus_area_px": int(finite_annulus.size),
    }
