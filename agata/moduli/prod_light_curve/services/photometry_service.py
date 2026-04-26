from __future__ import annotations

import math

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.time import Time
import astropy.units as u
from photutils.aperture import CircularAnnulus, CircularAperture, aperture_photometry
from photutils.centroids import centroid_com

from .utils import rounded_or_none


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
    phot_an = aperture_photometry(data, annulus)
    background_mean = np.asarray(phot_an["aperture_sum"] / annulus.area, dtype=float)
    net_flux = np.asarray(phot_ap["aperture_sum"] - background_mean * aperture.area, dtype=float)

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
            "annulus_mean_adu": rounded_or_none(float(background_mean[index]), 3),
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

    frames = dataset_summary["frames"]
    if not included_frame_indices:
        raise ValueError("Nessun frame selezionato per la fotometria")

    target_flux = []
    comparison_flux = []
    normalized_flux = []
    differential_mag = []
    time_jd = []
    centroid_shift = []
    per_frame_rows = []
    refined_target_positions = []

    target_point = (float(target["x"]), float(target["y"]))
    comparison_points = [(float(item["x"]), float(item["y"])) for item in comparison_stars]

    for frame_index in included_frame_indices:
        frame = frames[int(frame_index)]
        data = np.asarray(frame["data"], dtype=float)
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
        phot_an = aperture_photometry(data, annulus)
        background = np.asarray(phot_an["aperture_sum"] / annulus.area, dtype=float)
        net_flux = np.asarray(phot_ap["aperture_sum"] - background * aperture.area, dtype=float)

        current_target_flux = float(net_flux[0])
        current_comparison_flux = float(np.nansum(net_flux[1:]))
        current_ratio = current_target_flux / max(current_comparison_flux, 1e-9)
        current_mag = -2.5 * math.log10(max(current_ratio, 1e-12))

        target_flux.append(current_target_flux)
        comparison_flux.append(current_comparison_flux)
        normalized_flux.append(current_ratio)
        differential_mag.append(current_mag)
        time_jd.append(frame.get("time_jd"))
        centroid_shift.append(float(math.hypot(refined_target[0] - target_point[0], refined_target[1] - target_point[1])))
        refined_target_positions.append({"x": rounded_or_none(refined_target[0], 3), "y": rounded_or_none(refined_target[1], 3)})
        per_frame_rows.append({
            "frame_index": int(frame_index),
            "filename": frame.get("filename"),
            "time_jd": frame.get("time_jd"),
            "target_flux": rounded_or_none(current_target_flux, 6),
            "comparison_flux": rounded_or_none(current_comparison_flux, 6),
            "ratio_flux": rounded_or_none(current_ratio, 8),
            "differential_mag": rounded_or_none(current_mag, 6),
            "centroid_shift_px": rounded_or_none(centroid_shift[-1], 4),
        })

    normalized_flux_array = np.asarray(normalized_flux, dtype=float)
    flux_scale = float(np.nanmedian(normalized_flux_array)) if normalized_flux_array.size else 1.0
    if not math.isfinite(flux_scale) or flux_scale == 0:
        flux_scale = 1.0
    normalized_flux_array = normalized_flux_array / flux_scale

    return {
        "available": True,
        "message": "Fotometria differential aperture eseguita sul server.",
        "params": params,
        "selection": {
            "target": {
                "x": rounded_or_none(target_point[0], 3),
                "y": rounded_or_none(target_point[1], 3),
            },
            "comparison_stars": [
                {"x": rounded_or_none(point[0], 3), "y": rounded_or_none(point[1], 3)}
                for point in comparison_points
            ],
            "included_frame_indices": [int(item) for item in included_frame_indices],
        },
        "series": {
            "time_jd": [rounded_or_none(item, 8) for item in time_jd],
            "target_flux": [rounded_or_none(item, 6) for item in target_flux],
            "comparison_flux": [rounded_or_none(item, 6) for item in comparison_flux],
            "differential_flux": [rounded_or_none(item, 8) for item in normalized_flux_array.tolist()],
            "differential_mag": [rounded_or_none(item, 6) for item in differential_mag],
            "centroid_shift_px": [rounded_or_none(item, 4) for item in centroid_shift],
        },
        "per_frame": per_frame_rows,
        "summary": {
            "used_frames": len(included_frame_indices),
            "time_min_jd": rounded_or_none(min(item for item in time_jd if item is not None), 8) if any(item is not None for item in time_jd) else None,
            "time_max_jd": rounded_or_none(max(item for item in time_jd if item is not None), 8) if any(item is not None for item in time_jd) else None,
            "normalized_flux_scatter": rounded_or_none(float(np.nanstd(normalized_flux_array)), 8),
            "centroid_shift_median_px": rounded_or_none(float(np.nanmedian(np.asarray(centroid_shift, dtype=float))), 4),
        },
        "diagnostics": {
            "refined_target_positions": refined_target_positions,
        },
    }


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
