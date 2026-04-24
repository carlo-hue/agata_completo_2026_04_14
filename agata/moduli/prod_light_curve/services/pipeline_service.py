from __future__ import annotations

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
