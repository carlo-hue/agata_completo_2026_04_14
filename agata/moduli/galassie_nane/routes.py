from __future__ import annotations

import os

from flask import jsonify, render_template, request

from . import galassie_nane_bp
from .services.saved_runs import list_saved_runs, load_saved_run, save_named_run
from .services.single_run import SingleRunParams, run_single_field_analysis


@galassie_nane_bp.get("/")
def index():
    api_base_url = os.getenv("GALASSIE_NANE_API_BASE_URL", "http://localhost:8000")
    return render_template("galassie_nane/index.html", api_base_url=api_base_url)


@galassie_nane_bp.get("/descrizione")
def descrizione():
    return render_template("galassie_nane/descrizione.html")


@galassie_nane_bp.post("/api/single-run")
def single_run():
    payload = request.get_json(silent=True) or {}
    params = SingleRunParams.from_payload(payload)
    try:
        result = run_single_field_analysis(params)
        return jsonify(result)
    except NotImplementedError as exc:
        return jsonify({"error": str(exc), "provider_mode": "real"}), 501
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


@galassie_nane_bp.post("/api/save-run")
def save_run():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    result = payload.get("result")
    params = payload.get("input")

    if not name:
        return jsonify({"error": "Inserisci un nome per il salvataggio"}), 400
    if not isinstance(result, dict):
        return jsonify({"error": "Nessun risultato da salvare"}), 400

    try:
        saved = save_named_run(
            name,
            {
                "input": params if isinstance(params, dict) else None,
                "result": result,
            },
        )
        return jsonify(saved), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Salvataggio fallito: {exc}"}), 500


@galassie_nane_bp.get("/api/saved-runs")
def api_list_saved_runs():
    try:
        limit = int(request.args.get("limit", 50))
    except Exception:
        limit = 50
    return jsonify({"items": list_saved_runs(limit=limit)})


@galassie_nane_bp.get("/api/saved-runs/<run_id>")
def api_get_saved_run(run_id: str):
    try:
        return jsonify(load_saved_run(run_id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"error": f"Lettura run fallita: {exc}"}), 500
