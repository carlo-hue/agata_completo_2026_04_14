from __future__ import annotations

import math

import numpy as np
import astropy.units as u

from ..config import settings
from .catalog_service import build_target_candidates
from .dataset_service import build_dataset_summary, load_reference_frame
from .frame_quality_service import build_frame_quality_summary, enrich_frame_quality_with_photometry
from .photometry_service import measure_reference_aperture_metrics, normalize_photometry_params, run_differential_photometry
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


def _build_base_inspection(dataset_path: str, *, include_wcs: bool = False, include_time_jd: bool = False, progress_callback=None) -> dict:
    dataset_summary = build_dataset_summary(
        dataset_path,
        include_time_jd=include_time_jd,
        include_wcs=include_wcs,
        progress_callback=progress_callback,
    )
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
    params = normalize_photometry_params({
        "aperture_radius": aperture_radius,
        "annulus_inner_radius": annulus_inner_radius,
        "annulus_outer_radius": annulus_outer_radius,
    }, {
        "aperture_radius": settings.default_aperture_radius,
        "annulus_inner_radius": settings.default_annulus_inner_radius,
        "annulus_outer_radius": settings.default_annulus_outer_radius,
    })
    measured = measure_reference_aperture_metrics(reference_frame, points=[point], params=params, refine_points=False)
    if not measured:
        return None
    metrics = measured[0]

    saturated_level = reference_frame["header"].get("SATURATE")
    try:
        saturated_level = float(saturated_level)
    except (TypeError, ValueError):
        saturated_level = None
    ra_deg = None
    dec_deg = None
    ra_hms = None
    dec_dms = None
    wcs = reference_frame.get("wcs")
    if wcs is not None:
        try:
            sky = wcs.pixel_to_world(float(metrics.get("refined_x", metrics["x"])), float(metrics.get("refined_y", metrics["y"])))
            ra_deg = float(sky.ra.deg)
            dec_deg = float(sky.dec.deg)
            ra_hms = sky.ra.to_string(unit=u.hourangle, sep=":", precision=2, pad=True)
            dec_dms = sky.dec.to_string(unit=u.deg, sep=":", precision=2, alwayssign=True, pad=True)
        except Exception:
            ra_deg = None
            dec_deg = None
            ra_hms = None
            dec_dms = None
    return {
        "x": metrics.get("x"),
        "y": metrics.get("y"),
        "refined_x": metrics.get("refined_x"),
        "refined_y": metrics.get("refined_y"),
        "centroid_shift_px": metrics.get("centroid_shift_px"),
        "ra_deg": round(ra_deg, 6) if ra_deg is not None else None,
        "dec_deg": round(dec_deg, 6) if dec_deg is not None else None,
        "ra_hms": ra_hms,
        "dec_dms": dec_dms,
        "peak_adu": metrics.get("peak_adu"),
        "local_max_5x5_adu": metrics.get("local_max_5x5_adu"),
        "aperture_sum_adu": metrics.get("aperture_sum_adu"),
        "aperture_net_adu": metrics.get("aperture_net_adu"),
        "aperture_area_px": metrics.get("aperture_area_px"),
        "annulus_sum_adu": metrics.get("annulus_sum_adu"),
        "annulus_mean_adu": metrics.get("annulus_mean_adu"),
        "annulus_median_adu": metrics.get("annulus_median_adu"),
        "annulus_area_px": metrics.get("annulus_area_px"),
        "saturated": bool(float(metrics["peak_adu"]) >= saturated_level) if metrics.get("peak_adu") is not None and saturated_level and math.isfinite(saturated_level) else None,
        "saturation_level_adu": round(float(saturated_level), 3) if saturated_level and math.isfinite(saturated_level) else None,
    }


def estimate_selection_metrics(
    dataset_path: str,
    *,
    reference_path: str | None = None,
    target: dict | None = None,
    comparison_stars: list[dict] | None = None,
    aperture_radius: float | None = None,
    annulus_inner_radius: float | None = None,
    annulus_outer_radius: float | None = None,
) -> dict:
    radius = aperture_radius if aperture_radius is not None else settings.default_aperture_radius
    annulus_inner = annulus_inner_radius if annulus_inner_radius is not None else settings.default_annulus_inner_radius
    annulus_outer = annulus_outer_radius if annulus_outer_radius is not None else settings.default_annulus_outer_radius
    reference_frame = load_reference_frame(reference_path, include_wcs=True) if reference_path else _build_base_inspection(
        dataset_path,
        include_wcs=True,
        include_time_jd=False,
    )["reference_frame"]
    target_metrics = _estimate_point_metrics(reference_frame, target, radius, annulus_inner, annulus_outer)
    comparison_metrics = [
        item
        for item in (
            _estimate_point_metrics(reference_frame, point, radius, annulus_inner, annulus_outer)
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


def inspect_ground_dataset(dataset_path: str, *, progress_callback=None) -> dict:
    inspection = _build_base_inspection(
        dataset_path,
        include_wcs=False,
        include_time_jd=False,
        progress_callback=progress_callback,
    )
    dataset_summary = inspection["dataset_summary"]
    reference_payload = inspection["reference_payload"]
    detected_sources = inspection["detected_sources"]
    auto_target = inspection["auto_target"]
    frame_quality = inspection["frame_quality"]

    if callable(progress_callback):
        progress_callback(stage="reference", message="Costruzione reference image...", current=1, total=3)
        progress_callback(stage="detect_sources", message="Rilevamento sorgenti e metriche quality...", current=2, total=3)
        progress_callback(stage="finalize", message="Preparazione payload frontend...", current=3, total=3)

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
    inspection = _build_base_inspection(dataset_path, include_wcs=True, include_time_jd=False)
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
    inspection = _build_base_inspection(dataset_path, include_wcs=False, include_time_jd=False)
    effective_target = target if isinstance(target, dict) else inspection["auto_target"]
    return {
        "status": "ok",
        "message": "Comparison stars suggerite.",
        "dataset": _dataset_payload(inspection["dataset_summary"]),
        "comparison_stars": _build_comparison_payload(inspection["detected_sources"], effective_target),
    }


def run_ground_photometry(payload: dict) -> dict:
    dataset_path = str(payload.get("dataset_path", "")).strip()
    dataset_summary = build_dataset_summary(dataset_path, include_time_jd=True, include_wcs=False)
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
