from __future__ import annotations

import logging

from flask import Blueprint, current_app, jsonify, render_template, request, url_for

from .config import settings
from .services import (
    browse_dataset_directories,
    delete_prod_session,
    estimate_selection_metrics,
    get_job_result,
    get_job_status,
    inspect_ground_dataset,
    list_prod_sessions,
    query_ground_target_candidates,
    restore_prod_session,
    run_ground_photometry,
    save_prod_session,
    solve_reference_astrometry,
    start_inspect_job,
    suggest_ground_comparison_stars,
)
from .services.job_service import JobNotFoundError

LOGGER = logging.getLogger(__name__)


def _json_error(message: str, status_code: int = 400):
    return jsonify({"status": "error", "message": message}), status_code


def _optional_url(endpoint: str, fallback: str = "#") -> str:
    if endpoint not in current_app.view_functions:
        return fallback
    try:
        return url_for(endpoint)
    except Exception:
        return fallback


def create_blueprint() -> Blueprint:
    bp = Blueprint(
        "prod_light_curve",
        __name__,
        template_folder="templates",
        static_folder="static",
        url_prefix="/agata/prod-light-curve",
    )

    @bp.get("/")
    def index():
        return render_template(
            "prod_light_curve/index.html",
            module_title=settings.module_title,
            scaffold_message=settings.placeholder_message,
            module_links={
                "admin": _optional_url("admin.list_projects"),
                "variable_stars": _optional_url("variable_stars.index"),
                "exoplanets": _optional_url("exoplanets.index"),
                "field_star_map": _optional_url("field_star_map.index"),
                "galassie_nane": _optional_url("galassie_nane.index"),
                "tess_tce": _optional_url("tess_tce.index"),
                "tpf": _optional_url("tpf.index"),
                "prod_light_curve": url_for("prod_light_curve.index"),
            },
            default_aperture_radius=settings.default_aperture_radius,
            default_annulus_inner_radius=settings.default_annulus_inner_radius,
            default_annulus_outer_radius=settings.default_annulus_outer_radius,
            default_dataset_root=settings.default_dataset_root,
        )

    @bp.get("/health")
    def health():
        return jsonify({"status": "ok", "component": "prod_light_curve"})

    @bp.post("/api/inspect")
    def inspect_api():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return _json_error("payload JSON non valido", 400)
        dataset_path = str(payload.get("dataset_path", "")).strip()
        if not dataset_path:
            return _json_error("dataset_path mancante", 400)
        try:
            result = start_inspect_job(dataset_path)
        except ValueError as err:
            return _json_error(str(err), 400)
        except Exception as err:
            LOGGER.exception("Ground dataset inspect start failed for %s", dataset_path)
            return _json_error(str(err), 502)
        return jsonify(result), 202

    @bp.get("/api/inspect-status/<job_id>")
    def inspect_status_api(job_id: str):
        try:
            result = get_job_status(job_id)
        except JobNotFoundError as err:
            return _json_error(str(err), 404)
        except Exception as err:
            LOGGER.exception("Ground dataset inspect status failed for %s", job_id)
            return _json_error(str(err), 502)
        return jsonify(result)

    @bp.get("/api/inspect-result/<job_id>")
    def inspect_result_api(job_id: str):
        try:
            result = get_job_result(job_id)
        except ValueError as err:
            return _json_error(str(err), 400)
        except Exception as err:
            LOGGER.exception("Ground dataset inspect result failed for %s", job_id)
            return _json_error(str(err), 502)
        return jsonify(result)

    @bp.post("/api/browse-datasets")
    def browse_datasets_api():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return _json_error("payload JSON non valido", 400)
        requested_path = str(payload.get("path", "")).strip() or None
        try:
            result = browse_dataset_directories(requested_path)
        except ValueError as err:
            return _json_error(str(err), 400)
        except Exception as err:
            LOGGER.exception("Dataset directory browse failed for %s", requested_path)
            return _json_error(str(err), 502)
        return jsonify(result)

    @bp.post("/api/run")
    def run_api():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return _json_error("payload JSON non valido", 400)
        dataset_path = str(payload.get("dataset_path", "")).strip()
        if not dataset_path:
            return _json_error("dataset_path mancante", 400)
        try:
            result = run_ground_photometry(payload)
        except ValueError as err:
            return _json_error(str(err), 400)
        except Exception as err:
            LOGGER.exception("Ground photometry failed for %s", dataset_path)
            return _json_error(str(err), 502)
        return jsonify(result)

    @bp.post("/api/estimate-selection")
    def estimate_selection_api():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return _json_error("payload JSON non valido", 400)
        dataset_path = str(payload.get("dataset_path", "")).strip()
        if not dataset_path:
            return _json_error("dataset_path mancante", 400)
        reference_path = str(payload.get("reference_path", "")).strip() or None
        target = payload.get("target") if isinstance(payload.get("target"), dict) else None
        comparison_stars = payload.get("comparison_stars") if isinstance(payload.get("comparison_stars"), list) else []
        aperture_radius = payload.get("aperture_radius")
        annulus_inner_radius = payload.get("annulus_inner_radius")
        annulus_outer_radius = payload.get("annulus_outer_radius")
        try:
            result = estimate_selection_metrics(
                dataset_path,
                reference_path=reference_path,
                target=target,
                comparison_stars=comparison_stars,
                aperture_radius=float(aperture_radius) if aperture_radius not in (None, "") else None,
                annulus_inner_radius=float(annulus_inner_radius) if annulus_inner_radius not in (None, "") else None,
                annulus_outer_radius=float(annulus_outer_radius) if annulus_outer_radius not in (None, "") else None,
            )
        except ValueError as err:
            return _json_error(str(err), 400)
        except Exception as err:
            LOGGER.exception("Selection metrics estimation failed for %s", dataset_path)
            return _json_error(str(err), 502)
        return jsonify(result)

    @bp.post("/api/query-targets")
    def query_targets_api():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return _json_error("payload JSON non valido", 400)
        dataset_path = str(payload.get("dataset_path", "")).strip()
        reference_path = str(payload.get("reference_path", "")).strip() or None
        search_radius_arcsec = payload.get("search_radius_arcsec")
        if not dataset_path:
            return _json_error("dataset_path mancante", 400)
        try:
            result = query_ground_target_candidates(
                dataset_path,
                search_radius_arcsec=search_radius_arcsec,
                reference_path=reference_path,
            )
        except ValueError as err:
            return _json_error(str(err), 400)
        except Exception as err:
            LOGGER.exception("Ground target query failed for %s", dataset_path)
            return _json_error(str(err), 502)
        return jsonify(result)

    @bp.post("/api/solve-astrometry")
    def solve_astrometry_api():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return _json_error("payload JSON non valido", 400)
        reference_path = str(payload.get("reference_path", "")).strip()
        if not reference_path:
            return _json_error("reference_path mancante", 400)
        try:
            result = solve_reference_astrometry(reference_path)
        except ValueError as err:
            return _json_error(str(err), 400)
        except Exception as err:
            LOGGER.exception("Ground astrometry solve failed for %s", reference_path)
            return _json_error(str(err), 502)
        return jsonify(result)

    @bp.post("/api/suggest-comparisons")
    def suggest_comparisons_api():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return _json_error("payload JSON non valido", 400)
        dataset_path = str(payload.get("dataset_path", "")).strip()
        if not dataset_path:
            return _json_error("dataset_path mancante", 400)
        target = payload.get("target") if isinstance(payload.get("target"), dict) else None
        try:
            result = suggest_ground_comparison_stars(dataset_path, target=target)
        except ValueError as err:
            return _json_error(str(err), 400)
        except Exception as err:
            LOGGER.exception("Ground comparison suggestion failed for %s", dataset_path)
            return _json_error(str(err), 502)
        return jsonify(result)

    @bp.post("/api/save")
    def save_api():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict) or not payload:
            return _json_error("payload di salvataggio mancante", 400)
        try:
            result = save_prod_session(payload)
        except ValueError as err:
            return _json_error(str(err), 400)
        except Exception as err:
            LOGGER.exception("Ground session save failed")
            return _json_error(str(err), 502)
        return jsonify(result)

    @bp.post("/api/sessions")
    def sessions_api():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return _json_error("payload JSON non valido", 400)
        dataset_path = str(payload.get("dataset_path", "")).strip()
        if not dataset_path:
            return _json_error("dataset_path mancante", 400)
        try:
            result = list_prod_sessions(dataset_path)
        except ValueError as err:
            return _json_error(str(err), 400)
        except Exception as err:
            LOGGER.exception("Ground sessions listing failed for %s", dataset_path)
            return _json_error(str(err), 502)
        return jsonify(result)

    @bp.post("/api/restore")
    def restore_api():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return _json_error("payload JSON non valido", 400)
        session_id = str(payload.get("session_id", "")).strip()
        if not session_id:
            return _json_error("session_id mancante", 400)
        try:
            result = restore_prod_session(session_id)
        except ValueError as err:
            return _json_error(str(err), 400)
        except Exception as err:
            LOGGER.exception("Ground session restore failed for %s", session_id)
            return _json_error(str(err), 502)
        return jsonify(result)

    @bp.post("/api/delete")
    def delete_api():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return _json_error("payload JSON non valido", 400)
        session_id = str(payload.get("session_id", "")).strip()
        if not session_id:
            return _json_error("session_id mancante", 400)
        try:
            result = delete_prod_session(session_id)
        except ValueError as err:
            return _json_error(str(err), 400)
        except Exception as err:
            LOGGER.exception("Ground session delete failed for %s", session_id)
            return _json_error(str(err), 502)
        return jsonify(result)

    return bp


bp = create_blueprint()
