from __future__ import annotations

import csv
from datetime import datetime
import json
import os
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import current_user

from .schemas import PhotometryConfig, Point, TargetCoordinates


def create_blueprint() -> Blueprint:
    blueprint = Blueprint(
        "lightcurve",
        __name__,
        url_prefix="/agata/lightcurve",
        template_folder="templates",
        static_folder="static",
    )

    @blueprint.before_request
    def require_analyst_role():
        """Protezione globale: richiede ruolo minimo analyst."""
        if current_app.config.get("LOCAL_DEV_BYPASS_AUTH", False):
            return None
        if request.endpoint and "static" in request.endpoint:
            return None
        if not current_user.is_authenticated:
            return "Access denied: Authentication required", 401
        if not current_user.is_active:
            return "Access denied: Account disabled", 403
        allowed_roles = {"analyst", "reviewer", "admin", "superuser"}
        if current_user.role not in allowed_roles:
            return f"Access denied: Role '{current_user.role}' not permitted", 403
        return None

    @blueprint.get("/")
    def index():
        return render_template(
            "lightcurve/index.html",
            initial_folder=str(request.args.get("folder", "")).strip(),
        )

    @blueprint.post("/api/preview")
    def preview():
        payload = request.get_json(silent=True) or {}
        folder = str(payload.get("folder", "")).strip()
        if not folder:
            return jsonify({"error": "Il campo folder è obbligatorio."}), 400
        if not os.path.isdir(folder):
            return jsonify({"error": "La cartella indicata non esiste."}), 400

        try:
            from .photometry import reference_frame_metadata

            target_coordinates_payload = payload.get("target_coordinates") or {}
            target_coordinates = TargetCoordinates(
                ra=str(target_coordinates_payload.get("ra", "")).strip() or None,
                dec=str(target_coordinates_payload.get("dec", "")).strip() or None,
            )
            reference = reference_frame_metadata(folder, target_coordinates=target_coordinates)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify(
            {
                "folder": folder,
                "frame_path": reference["frame_path"],
                "fits_count": reference["fits_count"],
                "width": reference["width"],
                "height": reference["height"],
                "preview_png_base64": reference["preview_png_base64"],
                "auto_target": reference["auto_target"],
                "overlay": reference["overlay"],
            }
        )

    @blueprint.post("/api/evaluate-selection")
    def evaluate_selection():
        payload = request.get_json(silent=True) or {}
        folder = str(payload.get("folder", "")).strip()
        if not folder:
            return jsonify({"error": "Il campo folder è obbligatorio."}), 400

        try:
            from .photometry import evaluate_selection as evaluate_selection_payload

            config = PhotometryConfig.from_payload(payload.get("config") or {})
            target_payload = payload.get("target") or None
            target = None
            if target_payload and "x" in target_payload and "y" in target_payload:
                target = Point(float(target_payload["x"]), float(target_payload["y"]))
            comparators = [
                Point(float(item["x"]), float(item["y"]))
                for item in (payload.get("comparators") or [])
            ]
            target_coordinates_payload = payload.get("target_coordinates") or {}
            target_coordinates = TargetCoordinates(
                ra=str(target_coordinates_payload.get("ra", "")).strip() or None,
                dec=str(target_coordinates_payload.get("dec", "")).strip() or None,
            )
            result = evaluate_selection_payload(
                folder,
                target,
                comparators,
                config,
                target_coordinates=target_coordinates,
            )
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify(result)

    @blueprint.post("/api/snap-point")
    def snap_point():
        payload = request.get_json(silent=True) or {}
        folder = str(payload.get("folder", "")).strip()
        if not folder:
            return jsonify({"error": "Il campo folder è obbligatorio."}), 400

        point_payload = payload.get("point") or {}
        if "x" not in point_payload or "y" not in point_payload:
            return jsonify({"error": "Il punto deve includere coordinate x e y."}), 400

        try:
            from .photometry import snap_point_to_star

            config = PhotometryConfig.from_payload(payload.get("config") or {})
            point = Point(float(point_payload["x"]), float(point_payload["y"]))
            result = snap_point_to_star(folder, point, config)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify(result)

    @blueprint.post("/api/run")
    def run():
        payload = request.get_json(silent=True) or {}
        folder = str(payload.get("folder", "")).strip()
        if not folder:
            return jsonify({"error": "Il campo folder è obbligatorio."}), 400

        target_payload = payload.get("target") or {}
        comparators_payload = payload.get("comparators") or []
        if "x" not in target_payload or "y" not in target_payload:
            return jsonify({"error": "Il target deve includere coordinate x e y."}), 400
        if len(comparators_payload) < 1:
            return jsonify({"error": "Serve almeno un comparatore."}), 400

        try:
            from .photometry import run_lightcurve

            config = PhotometryConfig.from_payload(payload.get("config") or {})
            target = Point(float(target_payload["x"]), float(target_payload["y"]))
            comparators = [Point(float(item["x"]), float(item["y"])) for item in comparators_payload]
            target_coordinates_payload = payload.get("target_coordinates") or {}
            target_coordinates = TargetCoordinates(
                ra=str(target_coordinates_payload.get("ra", "")).strip() or None,
                dec=str(target_coordinates_payload.get("dec", "")).strip() or None,
            )
            result = run_lightcurve(folder, target, comparators, config, target_coordinates=target_coordinates)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify(result)

    @blueprint.post("/api/export")
    def export():
        payload = request.get_json(silent=True) or {}
        result = payload.get("result") or {}
        folder = str(payload.get("folder", "")).strip()
        if not result:
            return jsonify({"error": "Manca il risultato da esportare."}), 400

        try:
            export_payload = save_export_payload(folder, result)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify(export_payload)

    return blueprint


def save_export_payload(folder: str, result: dict) -> dict:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_dir = Path(__file__).resolve().parent / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    json_path = export_dir / f"lightcurve_export_{timestamp}.json"
    csv_path = export_dir / f"lightcurve_curve_{timestamp}.csv"

    export_data = {
        "component": "lightcurve",
        "folder": folder,
        "timestamp": timestamp,
        "result": result,
    }
    json_path.write_text(json.dumps(export_data, indent=2), encoding="utf-8")
    write_curve_csv(csv_path, result.get("series") or {})

    reference_frame = result.get("reference_frame") or {}
    selection = result.get("selection") or {}
    return {
        "ok": True,
        "component": "lightcurve",
        "export": {
            "folder": str(export_dir),
            "timestamp": timestamp,
            "files": {
                "json": str(json_path),
                "csv": str(csv_path),
            },
        },
        "result": {
            "points": len((result.get("series") or {}).get("jd") or []),
            "effective_comparators_count": selection.get("effective_comparators_count"),
            "target_ra_deg": reference_frame.get("target_ra_deg"),
            "target_dec_deg": reference_frame.get("target_dec_deg"),
        },
    }


def write_curve_csv(csv_path: Path, series: dict) -> None:
    fields = [
        "jd",
        "flux_target",
        "comparison_sum",
        "flux_normalized",
        "flux_detrended",
        "airmass",
        "altitude_deg",
        "background_target",
        "fwhm_target",
        "xcen_target",
        "ycen_target",
    ]
    rows = zip(*(series.get(field) or [] for field in fields), strict=False)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(fields)
        writer.writerows(rows)
