from __future__ import annotations

import math

import numpy as np

from ..config import settings
from .catalog_service import build_target_candidates
from .dataset_service import build_dataset_summary
from .frame_quality_service import build_frame_quality_summary, enrich_frame_quality_with_photometry
from .photometry_service import normalize_photometry_params, run_differential_photometry
from .reference_service import build_reference_payload
from .selection_service import build_comparison_candidates, choose_auto_target, detect_reference_sources
from .utils import utc_now_iso


def _build_base_inspection_from_summary(dataset_summary: dict) -> dict:
    reference_payload = build_reference_payload(dataset_summary)
    reference_frame = dataset_summary["frames"][dataset_summary["reference_frame_index"]]
    detected_sources = detect_reference_sources(reference_frame)
    auto_target = choose_auto_target(reference_payload, detected_sources, [])
    frame_quality = build_frame_quality_summary(dataset_summary)
    return {
        "dataset_summary": dataset_summary,
        "reference_payload": reference_payload,
        "reference_frame": reference_frame,
        "detected_sources": detected_sources,
        "auto_target": auto_target,
        "frame_quality": frame_quality,
    }


def _build_base_inspection(dataset_path: str) -> dict:
    dataset_summary = build_dataset_summary(dataset_path)
    return _build_base_inspection_from_summary(dataset_summary)


def _dataset_payload(dataset_summary: dict) -> dict:
    return {
        "dataset_id": dataset_summary["dataset_id"],
        "dataset_path": dataset_summary["dataset_path"],
        "fits_count": dataset_summary["fits_count"],
        "shape": dataset_summary["shape"],
        "same_shape": dataset_summary["same_shape"],
    }


def _build_comparison_payload(detected_sources: list[dict], target: dict | None) -> dict:
    comparison_candidates = build_comparison_candidates(detected_sources, target)
    return {
        "candidates": comparison_candidates,
        "auto_selected": [
            {"x": item["x"], "y": item["y"]}
            for item in comparison_candidates
            if item.get("auto_selected")
        ],
        "comparison_candidates_loaded": True,
    }


def _estimate_point_metrics(
    reference_frame: dict,
    point: dict,
    aperture_radius: float,
    annulus_inner_radius: float,
    annulus_outer_radius: float,
) -> dict | None:
    if not isinstance(point, dict) or point.get("x") is None or point.get("y") is None:
        return None

    data = np.asarray(reference_frame["data"], dtype=float)
    x = float(point["x"])
    y = float(point["y"])
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
    if stamp.size == 0:
        return None

    yy, xx = np.indices(stamp.shape)
    local_x = xx + x1
    local_y = yy + y1
    distance = np.hypot(local_x - x, local_y - y)
    aperture_mask = distance <= radius
    aperture_values = stamp[aperture_mask]
    finite_aperture = aperture_values[np.isfinite(aperture_values)]
    if finite_aperture.size == 0:
        return None

    box_y1 = max(0, y0 - 2)
    box_y2 = min(data.shape[0], y0 + 3)
    box_x1 = max(0, x0 - 2)
    box_x2 = min(data.shape[1], x0 + 3)
    local_box = np.asarray(data[box_y1:box_y2, box_x1:box_x2], dtype=float)
    local_box_finite = local_box[np.isfinite(local_box)]

    annulus_mask = (distance >= annulus_inner) & (distance <= annulus_outer)
    annulus_values = stamp[annulus_mask]
    finite_annulus = annulus_values[np.isfinite(annulus_values)]

    saturated_level = reference_frame["header"].get("SATURATE")
    try:
        saturated_level = float(saturated_level)
    except (TypeError, ValueError):
        saturated_level = None

    peak_adu = float(np.nanmax(finite_aperture))
    local_max_5x5_adu = float(np.nanmax(local_box_finite)) if local_box_finite.size else None
    aperture_sum_adu = float(np.nansum(finite_aperture))
    annulus_sum_adu = float(np.nansum(finite_annulus)) if finite_annulus.size else None
    annulus_median_adu = float(np.nanmedian(finite_annulus)) if finite_annulus.size else None
    return {
        "x": point.get("x"),
        "y": point.get("y"),
        "peak_adu": round(peak_adu, 3),
        "local_max_5x5_adu": round(local_max_5x5_adu, 3) if local_max_5x5_adu is not None else None,
        "aperture_sum_adu": round(aperture_sum_adu, 3),
        "annulus_sum_adu": round(annulus_sum_adu, 3) if annulus_sum_adu is not None else None,
        "annulus_median_adu": round(annulus_median_adu, 3) if annulus_median_adu is not None else None,
        "saturated": bool(peak_adu >= saturated_level) if saturated_level and math.isfinite(saturated_level) else None,
        "saturation_level_adu": round(float(saturated_level), 3) if saturated_level and math.isfinite(saturated_level) else None,
    }


def estimate_selection_metrics(
    dataset_path: str,
    *,
    target: dict | None = None,
    comparison_stars: list[dict] | None = None,
    aperture_radius: float | None = None,
    annulus_inner_radius: float | None = None,
    annulus_outer_radius: float | None = None,
) -> dict:
    inspection = _build_base_inspection(dataset_path)
    radius = aperture_radius if aperture_radius is not None else settings.default_aperture_radius
    annulus_inner = annulus_inner_radius if annulus_inner_radius is not None else settings.default_annulus_inner_radius
    annulus_outer = annulus_outer_radius if annulus_outer_radius is not None else settings.default_annulus_outer_radius
    target_metrics = _estimate_point_metrics(inspection["reference_frame"], target, radius, annulus_inner, annulus_outer)
    comparison_metrics = [
        item
        for item in (
            _estimate_point_metrics(inspection["reference_frame"], point, radius, annulus_inner, annulus_outer)
            for point in (comparison_stars or [])
        )
        if item is not None
    ]
    return {
        "status": "ok",
        "message": "Metriche ADU stimate sulla reference image.",
        "target": target_metrics,
        "comparison_stars": comparison_metrics,
    }


def inspect_ground_dataset(dataset_path: str) -> dict:
    inspection = _build_base_inspection(dataset_path)
    dataset_summary = inspection["dataset_summary"]
    reference_payload = inspection["reference_payload"]
    detected_sources = inspection["detected_sources"]
    auto_target = inspection["auto_target"]
    frame_quality = inspection["frame_quality"]

    return {
        "status": "ok",
        "message": "Dataset ground-based ispezionato correttamente.",
        "inspected_at_utc": utc_now_iso(),
        "dataset": _dataset_payload(dataset_summary),
        "reference": reference_payload,
        "targeting": {
            "auto_target": auto_target,
            "target_candidates": [],
            "target_candidates_loaded": False,
            "detected_sources": detected_sources[: settings.max_preview_sources],
        },
        "comparison_stars": {
            "candidates": [],
            "auto_selected": [],
            "comparison_candidates_loaded": False,
        },
        "frame_quality": frame_quality,
        "defaults": {
            "photometry": {
                "aperture_radius": settings.default_aperture_radius,
                "annulus_inner_radius": settings.default_annulus_inner_radius,
                "annulus_outer_radius": settings.default_annulus_outer_radius,
            }
        },
    }


def query_ground_target_candidates(dataset_path: str) -> dict:
    inspection = _build_base_inspection(dataset_path)
    target_candidates = build_target_candidates(inspection["reference_payload"], inspection["reference_frame"])
    auto_target = choose_auto_target(inspection["reference_payload"], inspection["detected_sources"], target_candidates)
    return {
        "status": "ok",
        "message": "Candidati target caricati.",
        "dataset": _dataset_payload(inspection["dataset_summary"]),
        "targeting": {
            "auto_target": auto_target,
            "target_candidates": target_candidates,
            "target_candidates_loaded": True,
        },
    }


def suggest_ground_comparison_stars(dataset_path: str, target: dict | None = None) -> dict:
    inspection = _build_base_inspection(dataset_path)
    effective_target = target if isinstance(target, dict) else inspection["auto_target"]
    return {
        "status": "ok",
        "message": "Comparison stars suggerite.",
        "dataset": _dataset_payload(inspection["dataset_summary"]),
        "comparison_stars": _build_comparison_payload(inspection["detected_sources"], effective_target),
    }


def run_ground_photometry(payload: dict) -> dict:
    dataset_path = str(payload.get("dataset_path", "")).strip()
    dataset_summary = build_dataset_summary(dataset_path)
    inspection = _build_base_inspection_from_summary(dataset_summary)
    inspect_payload = {
        "status": "ok",
        "message": "Dataset ground-based ispezionato correttamente.",
        "inspected_at_utc": utc_now_iso(),
        "dataset": _dataset_payload(dataset_summary),
        "reference": inspection["reference_payload"],
        "targeting": {
            "auto_target": inspection["auto_target"],
            "target_candidates": [],
            "target_candidates_loaded": False,
            "detected_sources": inspection["detected_sources"][: settings.max_preview_sources],
        },
        "comparison_stars": {
            "candidates": [],
            "auto_selected": [],
            "comparison_candidates_loaded": False,
        },
        "frame_quality": inspection["frame_quality"],
        "defaults": {
            "photometry": {
                "aperture_radius": settings.default_aperture_radius,
                "annulus_inner_radius": settings.default_annulus_inner_radius,
                "annulus_outer_radius": settings.default_annulus_outer_radius,
            }
        },
    }

    target = payload.get("target")
    if not isinstance(target, dict):
        target = inspect_payload["targeting"]["auto_target"]

    comparison_stars = payload.get("comparison_stars")
    comparison_payload = inspect_payload["comparison_stars"]
    if not isinstance(comparison_stars, list) or not comparison_stars:
        comparison_payload = _build_comparison_payload(inspection["detected_sources"], target)
        comparison_stars = comparison_payload["auto_selected"]

    frame_quality = inspect_payload["frame_quality"]
    included_frame_indices = payload.get("included_frame_indices")
    if not isinstance(included_frame_indices, list) or not included_frame_indices:
        included_frame_indices = [
            item["index"]
            for item in frame_quality["frames"]
            if not item.get("suspect")
        ]
        if not included_frame_indices:
            included_frame_indices = [item["index"] for item in frame_quality["frames"]]

    photometry_params = normalize_photometry_params(
        payload.get("photometry") if isinstance(payload.get("photometry"), dict) else {},
        inspect_payload["defaults"]["photometry"],
    )
    photometry_result = run_differential_photometry(
        dataset_summary,
        target=target,
        comparison_stars=comparison_stars,
        included_frame_indices=[int(item) for item in included_frame_indices],
        params=photometry_params,
    )
    enriched_frame_quality = enrich_frame_quality_with_photometry(
        frame_quality,
        photometry_result["series"]["target_flux"],
        photometry_result["series"]["comparison_flux"],
        photometry_result["series"]["centroid_shift_px"],
    )

    return {
        "status": "ok",
        "message": "Pipeline ground-based completata correttamente.",
        "inspected_at_utc": inspect_payload["inspected_at_utc"],
        "dataset": inspect_payload["dataset"],
        "reference": inspect_payload["reference"],
        "targeting": {
            **inspect_payload["targeting"],
            "selected_target": target,
        },
        "comparison_stars": {
            **comparison_payload,
            "selected": comparison_stars,
        },
        "frame_quality": enriched_frame_quality,
        "photometry": photometry_result,
        "defaults": inspect_payload["defaults"],
        "save": {
            "status": "idle",
            "saved": False,
            "message": "Nessun salvataggio automatico eseguito.",
            "session_id": None,
        },
    }
