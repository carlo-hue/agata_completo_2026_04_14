"""
preview_routes.py - Preview lightcurve da job pipeline senza promozione

Permette di aprire l'editor di stelle variabili direttamente da un risultato
di job pipeline (ZTF Survey, TESS Bulk Import, VAST) con solo i tab utili
visibili (Curva di Luce, Periodogramma, Analisi in Fase).
"""
import logging
from flask import request, render_template, jsonify, Response
from flask_login import current_user

from agata.moduli.variable_stars import variable_stars_bp
from agata.moduli.variable_stars.services.preview_loader import load_preview
from agata.moduli.variable_stars.services.arrow_parser import sessions_to_arrow_response
from agata.db import SessionLocal

logger = logging.getLogger(__name__)

# Sorgenti valide
_VALID_SOURCES = ("ztf", "tess", "vast")

# Mappa source → associazione_id checker
# ZTF e TESS hanno association_id sul job; VAST non filtra per association (superuser only)
_SOURCE_ASSOCIATION_CHECK = {
    "ztf": lambda row, user: (
        user.role == "superuser"
        or row.job.association_id is None
        or row.job.association_id == user.association_id
    ),
    "tess": lambda row, user: (
        user.role == "superuser"
        or row.job.association_id is None
        or row.job.association_id == user.association_id
    ),
    "vast": lambda row, user: (
        # VAST jobs appartengono a un'associazione ma non hanno association_id esplicito
        # I superuser vedono tutto; admin vedono solo job della propria associazione
        user.role in ("superuser", "admin")
    ),
}


@variable_stars_bp.get("/preview")
def preview_index():
    """
    Pagina di preview lightcurve da job pipeline.

    Apre l'editor in modalità 'preview': solo tab Curva di Luce,
    Periodogramma e Analisi in Fase sono visibili. I restanti tab
    (Cataloghi, Import Cataloghi, Field Star Map, History, Analisi di Supporto)
    sono nascosti.

    Query Parameters:
        source (str):     'ztf' | 'tess' | 'vast'
        result_id (int):  PK del risultato nel modello pipeline corrispondente

    Returns:
        HTML: template index.html con preview_mode=True e label stella
        400:  source o result_id mancanti/non validi
        403:  risultato di altra associazione
        404:  risultato non trovato
        500:  errore interno
    """
    source = request.args.get("source", "").lower()
    result_id = request.args.get("result_id", type=int)

    if source not in _VALID_SOURCES or not result_id:
        return render_template(
            "variable_stars/index.html",
            preview_mode=False,
            preview_label=None,
            preview_source=None,
            preview_result_id=None,
            project=None,
            is_superuser=(current_user.role == "superuser"),
            is_admin=(current_user.role == "admin"),
            project_state=None,
            user_role=current_user.role,
            error_message="Parametri preview non validi. Specificare source (ztf/tess/vast) e result_id.",
            error_type="bad_request",
        ), 400

    db = SessionLocal()
    try:
        # Verifica esistenza e autorizzazione prima del load completo
        error, row = _check_access(db, source, result_id)
        if error:
            return render_template(
                "variable_stars/index.html",
                preview_mode=False,
                preview_label=None,
                preview_source=None,
                preview_result_id=None,
                project=None,
                is_superuser=(current_user.role == "superuser"),
                is_admin=(current_user.role == "admin"),
                project_state=None,
                user_role=current_user.role,
                error_message=error["message"],
                error_type=error["type"],
            ), error["status"]

        # Carica la preview per ottenere il label
        result = load_preview(db, source, result_id)
        preview_label = result.label

    except LookupError as e:
        logger.warning(f"preview_index: {e}")
        return render_template(
            "variable_stars/index.html",
            preview_mode=False,
            preview_label=None,
            preview_source=None,
            preview_result_id=None,
            project=None,
            is_superuser=(current_user.role == "superuser"),
            is_admin=(current_user.role == "admin"),
            project_state=None,
            user_role=current_user.role,
            error_message=str(e),
            error_type="not_found",
        ), 404
    except Exception as e:
        logger.exception(f"Errore imprevisto in preview_index: source={source} result_id={result_id}")
        return render_template(
            "variable_stars/index.html",
            preview_mode=False,
            preview_label=None,
            preview_source=None,
            preview_result_id=None,
            project=None,
            is_superuser=(current_user.role == "superuser"),
            is_admin=(current_user.role == "admin"),
            project_state=None,
            user_role=current_user.role,
            error_message="Errore interno server.",
            error_type="internal",
        ), 500
    finally:
        db.close()

    return render_template(
        "variable_stars/index.html",
        project=None,
        preview_mode=True,
        preview_label=preview_label,
        preview_source=source,
        preview_result_id=result_id,
        is_superuser=(current_user.role == "superuser"),
        is_admin=(current_user.role == "admin"),
        project_state=None,
        user_role=current_user.role,
        error_message=None,
        error_type=None,
    )


@variable_stars_bp.get("/api/preview-lightcurve.arrow")
def api_preview_lightcurve_arrow():
    """
    Carica la lightcurve per preview in formato Apache Arrow IPC stream.

    Analogo a /api/lightcurve.arrow ma legge dal job pipeline invece che
    da agata_star_photometry / Project.

    Query Parameters:
        source (str):     'ztf' | 'tess' | 'vast'
        result_id (int):  PK del risultato nel modello pipeline

    Returns:
        Response: Arrow IPC stream con colonne:
            - point_id:    int32
            - session_id:  int32
            - session_name: string
            - jd:          float64
            - mag:         float32
        400: parametri non validi
        403: accesso non autorizzato
        404: risultato non trovato
        502: errore servizio esterno (IRSA)
        500: errore interno
    """
    source = request.args.get("source", "").lower()
    result_id = request.args.get("result_id", type=int)

    if source not in _VALID_SOURCES or not result_id:
        return jsonify({"error": "Parametri non validi: source e result_id obbligatori"}), 400

    db = SessionLocal()
    try:
        error, _ = _check_access(db, source, result_id)
        if error:
            return jsonify({"error": error["message"]}), error["status"]

        result = load_preview(db, source, result_id)
    except LookupError as e:
        logger.warning(f"api_preview_lightcurve: {e}")
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.exception(f"Errore imprevisto in api_preview_lightcurve: source={source} result_id={result_id}")
        return jsonify({"error": "Errore interno server", "detail": str(e)}), 500
    finally:
        db.close()

    if result.error:
        # Errore nel caricamento dati (es. IRSA non risponde, dati assenti)
        return jsonify({"error": result.error}), 502

    if not result.sessions:
        return jsonify({"error": "Nessun dato disponibile per questa sorgente"}), 404

    logger.info(f"Preview Arrow: source={source} result_id={result_id} → {sum(len(s['jd']) for s in result.sessions)} punti, {len(result.sessions)} sessioni")

    buf = sessions_to_arrow_response(result.sessions)
    return Response(
        buf,
        mimetype="application/vnd.apache.arrow.stream",
        headers={"Cache-Control": "no-store"},
    )


# ---------------------------------------------------------------------------
# Helper: verifica accesso al risultato
# ---------------------------------------------------------------------------

def _check_access(db, source: str, result_id: int):
    """
    Verifica che il risultato esista e che l'utente abbia accesso.

    Returns:
        (None, row)          → accesso OK
        (error_dict, None)   → accesso negato o non trovato
    """
    from agata.auth_models.ztf_survey_job import ZtfSurveyResult
    from agata.auth_models.tess_import_job import TessImportResult
    from agata.auth_models.vast_job import VastResult

    model_map = {"ztf": ZtfSurveyResult, "tess": TessImportResult, "vast": VastResult}
    model = model_map[source]
    row = db.get(model, result_id)

    if row is None:
        return {"message": f"Risultato {source.upper()} id={result_id} non trovato", "type": "not_found", "status": 404}, None

    checker = _SOURCE_ASSOCIATION_CHECK[source]
    if not checker(row, current_user):
        logger.warning(
            f"User {current_user.id} (assoc={current_user.association_id}) "
            f"tentò di accedere a {source} result_id={result_id}"
        )
        return {"message": "Non autorizzato ad accedere a questo risultato", "type": "forbidden", "status": 403}, None

    return None, row
