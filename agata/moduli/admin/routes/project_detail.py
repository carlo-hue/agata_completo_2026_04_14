# agata/admin/routes/project_detail.py
"""
API Routes per Vista Dettaglio Project

Endpoint per gestione completa del ciclo di vita progetto
"""
from typing import Optional
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from sqlalchemy import desc
from datetime import datetime
import logging

from agata.db import SessionLocal
from agata.auth_models import (
    Project, User, ProjectSlackThread, ProjectScienceData,
    ProjectOutput, AuditLog
)
from agata.moduli.admin.decorators import admin_required, audit_action
from agata.moduli.admin.commands import (
    AssignAnalystCommand, SendToReviewCommand,
    CancelProjectCommand, CloseProjectCommand, CommandError
)
from agata.moduli.admin.services.project_state_policy import get_allowed_actions, get_state_badge_color

# Import servizi analisi variabili
from agata.moduli.admin.services.variability_analysis import (
    trova_stelle_analoghe,
    generate_phased_comparison_plot,
    get_lightcurve_from_db
)

# Singleton globale per embedding service (evita ricaricamento modello ad ogni richiesta)
_embedding_service_instance = None
_vector_store_instance = None

logger = logging.getLogger(__name__)


project_detail_bp = Blueprint('project_detail', __name__, url_prefix='/api/projects')


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_project_or_404(project_id: int, db) -> Project:
    """Get project by ID with eager loaded relationships to avoid N+1 queries"""
    from sqlalchemy.orm import joinedload

    project = db.query(Project).options(
        joinedload(Project.association),
        joinedload(Project.assigned_user),
        joinedload(Project.reviewer)
    ).filter_by(id=project_id).first()
    if not project:
        raise Exception(f"Project {project_id} not found")
    return project


def serialize_project_detail(project: Project, db) -> dict:
    """Serializza progetto completo per vista dettaglio"""
    # === OPTIMIZATION: Relationships eagerly loaded from get_project_or_404 ===
    # Relationships loaded via joinedload: association, assigned_user, reviewer
    # Slack thread, science data, and outputs queried separately (still indexed by project_id)

    # Slack thread info (batch load separately)
    slack_thread = db.query(ProjectSlackThread).filter_by(
        project_id=project.id,
        is_active=True
    ).first()

    # Science data
    science_data = db.query(ProjectScienceData).filter_by(
        project_id=project.id
    ).first()

    # Outputs (solo versioni correnti)
    outputs = db.query(ProjectOutput).filter_by(
        project_id=project.id,
        is_current=True
    ).order_by(desc(ProjectOutput.uploaded_at)).all()

    # Azioni consentite per utente corrente
    allowed_actions = get_allowed_actions(project, current_user)

    return {
        'id': project.id,
        'project_code': project.project_code,
        'gaia_id': project.gaia_id,
        'title': project.title,
        'state': project.state,
        'state_badge_color': get_state_badge_color(project.state),
        'source': project.source,
        'ra': project.ra,
        'dec_deg': project.dec_deg,
        'magnitude': project.magnitude,

        # Association
        'association': {
            'id': project.association.id,
            'name': project.association.name,
            'slug': project.association.slug
        } if project.association else None,

        # Assignment
        'assigned_to': {
            'id': project.assigned_user.id,
            'name': project.assigned_user.name,
            'email': project.assigned_user.email
        } if project.assigned_user else None,
        'assigned_at': project.assigned_at.isoformat() if project.assigned_at else None,

        # Review
        'reviewer': {
            'id': project.reviewer.id,
            'name': project.reviewer.name,
            'email': project.reviewer.email
        } if project.reviewer else None,
        'reviewed_at': project.reviewed_at.isoformat() if project.reviewed_at else None,
        'review_notes': project.review_notes,

        # AAVSO
        'submitted_aavso_at': project.submitted_aavso_at.isoformat() if project.submitted_aavso_at else None,
        'aavso_accepted_at': project.aavso_accepted_at.isoformat() if project.aavso_accepted_at else None,
        'aavso_rejected_at': project.aavso_rejected_at.isoformat() if project.aavso_rejected_at else None,

        # Cancellation
        'cancelled_at': project.cancelled_at.isoformat() if project.cancelled_at else None,
        'cancellation_reason': project.cancellation_reason,

        # Slack context
        'slack': {
            'type': slack_thread.slack_type if slack_thread else None,
            'channel_id': slack_thread.channel_id if slack_thread else None,
            'thread_ts': slack_thread.thread_ts if slack_thread else None,
            'last_message_ts': slack_thread.last_message_ts if slack_thread else None,
            'last_message_preview': slack_thread.last_message_preview if slack_thread else None,
            'link': f"slack://channel?team=T01234&id={slack_thread.channel_id}&message={slack_thread.thread_ts}" if slack_thread else None
        } if slack_thread else None,

        # Science data
        'science_data': {
            'classification': science_data.classification,
            'period_days': science_data.period_days,
            'period_uncertainty': science_data.period_uncertainty,
            'confidence_level': science_data.confidence_level,
            'scientific_notes': science_data.scientific_notes,
            'dataset_drive_url': science_data.dataset_drive_url,
            'updated_at': science_data.updated_at.isoformat() if science_data.updated_at else None
        } if science_data else None,

        # Outputs
        'outputs': [{
            'id': output.id,
            'type': output.output_type,
            'file_name': output.file_name,
            'file_url': output.file_url,
            'description': output.description,
            'version': output.version,
            'uploaded_at': output.uploaded_at.isoformat()
        } for output in outputs],

        # Metadata
        'created_at': project.created_at.isoformat(),
        'updated_at': project.updated_at.isoformat(),

        # Azioni consentite per UI
        'allowed_actions': allowed_actions
    }


# ============================================================================
# ENDPOINTS
# ============================================================================

@project_detail_bp.route('/<int:project_id>', methods=['GET'])
@login_required
def get_project_detail(project_id: int):
    """
    GET /api/projects/<id>
    Ritorna dettaglio completo progetto per vista dettaglio
    """
    db = SessionLocal()
    try:
        project = get_project_or_404(project_id, db)

        # Verifica permessi (user può vedere progetti della sua associazione)
        if current_user.role not in ['superuser', 'admin']:
            if project.association_id != current_user.association_id:
                return jsonify({'error': 'Unauthorized'}), 403

        data = serialize_project_detail(project, db)
        return jsonify(data), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@project_detail_bp.route('/<int:project_id>/assign', methods=['POST'])
@login_required
@admin_required('admin')
def assign_project(project_id: int):
    """
    POST /api/projects/<id>/assign
    Assegna progetto a un analista

    Body: {"analyst_id": "uuid"}
    """
    db = SessionLocal()
    try:
        data = request.get_json()
        analyst_id = data.get('analyst_id')

        if not analyst_id:
            return jsonify({'error': 'analyst_id required'}), 400

        project = get_project_or_404(project_id, db)
        analyst = db.query(User).filter_by(id=analyst_id).first()

        if not analyst:
            return jsonify({'error': 'Analyst not found'}), 404

        # Esegui comando
        cmd = AssignAnalystCommand(
            db=db,
            project=project,
            analyst=analyst,
            current_user=current_user,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )

        result = cmd.execute()

        return jsonify({
            'success': True,
            'message': result.message,
            'project': serialize_project_detail(project, db)
        }), 200

    except CommandError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@project_detail_bp.route('/<int:project_id>/send-to-review', methods=['POST'])
@login_required
def send_to_review(project_id: int):
    """
    POST /api/projects/<id>/send-to-review
    Invia progetto in revisione

    Può essere eseguito dall'analista assegnato o da admin/superuser
    """
    db = SessionLocal()
    try:
        project = get_project_or_404(project_id, db)

        cmd = SendToReviewCommand(
            db=db,
            project=project,
            current_user=current_user,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )

        result = cmd.execute()

        return jsonify({
            'success': True,
            'message': result.message,
            'project': serialize_project_detail(project, db)
        }), 200

    except CommandError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@project_detail_bp.route('/<int:project_id>/cancel', methods=['POST'])
@login_required
@admin_required('admin')
def cancel_project(project_id: int):
    """
    POST /api/projects/<id>/cancel
    Annulla progetto

    Body: {"reason": "motivazione cancellazione"}
    """
    db = SessionLocal()
    try:
        data = request.get_json()
        reason = data.get('reason')

        if not reason:
            return jsonify({'error': 'reason required'}), 400

        project = get_project_or_404(project_id, db)

        cmd = CancelProjectCommand(
            db=db,
            project=project,
            current_user=current_user,
            reason=reason,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )

        result = cmd.execute()

        return jsonify({
            'success': True,
            'message': result.message,
            'project': serialize_project_detail(project, db)
        }), 200

    except CommandError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@project_detail_bp.route('/<int:project_id>/close', methods=['POST'])
@login_required
@admin_required('reviewer')
def close_project(project_id: int):
    """
    POST /api/projects/<id>/close
    Chiudi progetto dopo completamento

    Body (opzionale): {"notes": "note finali reviewer"}
    """
    db = SessionLocal()
    try:
        data = request.get_json() or {}
        notes = data.get('notes')

        project = get_project_or_404(project_id, db)

        cmd = CloseProjectCommand(
            db=db,
            project=project,
            current_user=current_user,
            notes=notes,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )

        result = cmd.execute()

        return jsonify({
            'success': True,
            'message': result.message,
            'project': serialize_project_detail(project, db)
        }), 200

    except CommandError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@project_detail_bp.route('/<int:project_id>/timeline', methods=['GET'])
@login_required
def get_project_timeline(project_id: int):
    """
    GET /api/projects/<id>/timeline
    Ritorna timeline eventi audit per progetto

    Query params:
    - limit: numero eventi (default 50)
    - offset: skip eventi (default 0)
    """
    db = SessionLocal()
    try:
        project = get_project_or_404(project_id, db)

        # Verifica permessi
        if current_user.role not in ['superuser', 'admin']:
            if project.association_id != current_user.association_id:
                return jsonify({'error': 'Unauthorized'}), 403

        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))

        # Query eventi
        events = db.query(AuditLog).filter_by(
            entity_type='project',
            entity_id=str(project_id)
        ).order_by(desc(AuditLog.created_at)).limit(limit).offset(offset).all()

        return jsonify({
            'project_id': project_id,
            'events': [{
                'id': event.id,
                'action': event.action,
                'description': event.description,
                'old_value': event.old_value,
                'new_value': event.new_value,
                'outcome': event.outcome,
                'error_message': event.error_message,
                'user_email': event.user_email,
                'created_at': event.created_at.isoformat()
            } for event in events],
            'total': db.query(AuditLog).filter_by(
                entity_type='project',
                entity_id=str(project_id)
            ).count()
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@project_detail_bp.route('/<int:project_id>/science-data', methods=['GET', 'PUT'])
@login_required
def manage_science_data(project_id: int):
    """
    GET /api/projects/<id>/science-data - Leggi dati scientifici
    PUT /api/projects/<id>/science-data - Aggiorna dati scientifici
    """
    db = SessionLocal()
    try:
        project = get_project_or_404(project_id, db)

        # Verifica permessi
        if current_user.role not in ['superuser', 'admin', 'analyst', 'reviewer']:
            return jsonify({'error': 'Unauthorized'}), 403

        if request.method == 'GET':
            science_data = db.query(ProjectScienceData).filter_by(
                project_id=project_id
            ).first()

            if not science_data:
                return jsonify(None), 200

            return jsonify({
                'classification': science_data.classification,
                'period_days': science_data.period_days,
                'period_uncertainty': science_data.period_uncertainty,
                'confidence_level': science_data.confidence_level,
                'scientific_notes': science_data.scientific_notes,
                'dataset_drive_url': science_data.dataset_drive_url,
                'updated_at': science_data.updated_at.isoformat()
            }), 200

        elif request.method == 'PUT':
            data = request.get_json()

            # Get or create science data
            science_data = db.query(ProjectScienceData).filter_by(
                project_id=project_id
            ).first()

            if not science_data:
                science_data = ProjectScienceData(project_id=project_id)
                db.add(science_data)

            # Update fields
            if 'classification' in data:
                science_data.classification = data['classification']
            if 'period_days' in data:
                science_data.period_days = data['period_days']
            if 'period_uncertainty' in data:
                science_data.period_uncertainty = data['period_uncertainty']
            if 'confidence_level' in data:
                science_data.confidence_level = data['confidence_level']
            if 'scientific_notes' in data:
                science_data.scientific_notes = data['scientific_notes']
            if 'dataset_drive_url' in data:
                science_data.dataset_drive_url = data['dataset_drive_url']

            science_data.updated_by = current_user.id

            db.commit()

            return jsonify({
                'success': True,
                'message': 'Dati scientifici aggiornati con successo'
            }), 200

    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# =============================================================================
# ANALISI COMPARATIVA STELLE VARIABILI
# =============================================================================

@project_detail_bp.route('/<int:project_id>/variability/search-analogues', methods=['POST'])
@login_required
@admin_required('analyst')
def search_variable_analogues(project_id: int):
    """
    POST /api/projects/<id>/variability/search-analogues

    Cerca stelle variabili analoghe basate su parametri stellari e periodo.

    Body JSON:
    - periods: List[float] - Lista periodi candidati (giorni)
    - bp_rp: float (opzionale) - Colore BP-RP
    - mag: float (opzionale) - Magnitudine G
    - teff: float (opzionale) - Temperatura efficace
    - top_n: int (opzionale) - Numero risultati (default 10)

    Returns:
        JSON con lista stelle analoghe ranked per similarità
    """
    db = SessionLocal()
    try:
        project = get_project_or_404(project_id, db)

        # Verifica permessi
        if current_user.role not in ['superuser', 'admin']:
            if project.association_id != current_user.association_id:
                return jsonify({'error': 'Unauthorized'}), 403

        data = request.get_json() or {}

        # Valida input - periodi opzionale ora se forniti range espliciti
        periodi = data.get('periods', [])

        # Recupera parametri stella (da science_data o override da body)
        science_data = db.query(ProjectScienceData).filter_by(
            project_id=project_id
        ).first()

        # Parametri base da body o fallback su progetto/science_data
        bp_rp = data.get('bp_rp')
        mag = data.get('mag') or project.magnitude
        teff = data.get('teff')
        top_n = data.get('top_n', 10)

        # Parametri VSX avanzati (nuovi)
        # Magnitudine: 4 campi (min_mag_min, min_mag_max, max_mag_min, max_mag_max)
        # VSX supporta solo min_mag e max_mag globali, quindi:
        # - min_mag VSX = min(tutti i valori) = magnitudine più brillante (numero più piccolo)
        # - max_mag VSX = max(tutti i valori) = magnitudine più debole (numero più grande)
        min_mag_min = data.get('min_mag_min')  # Mag minima - limite inferiore
        min_mag_max = data.get('min_mag_max')  # Mag minima - limite superiore
        max_mag_min = data.get('max_mag_min')  # Mag massima - limite inferiore
        max_mag_max = data.get('max_mag_max')  # Mag massima - limite superiore

        # Calcola range VSX globale
        mag_values = [v for v in [min_mag_min, min_mag_max, max_mag_min, max_mag_max] if v is not None]
        if mag_values:
            min_mag = min(mag_values)  # Più brillante (numero più piccolo)
            max_mag = max(mag_values)  # Più debole (numero più grande)
        else:
            min_mag = None
            max_mag = None

        period_min = data.get('period_min')
        period_max = data.get('period_max')
        vartype = data.get('vartype')
        spec_type = data.get('spec_type')
        radius_deg = 5.0  # Fisso, non più specificabile dall'utente

        if not project.gaia_id:
            return jsonify({'error': 'Project must have gaia_id for analogue search'}), 400

        # Query Gaia per recuperare coordinate e parametri mancanti
        from agata.moduli.admin.services.catalog_common_service import resolve_gaia_coordinates

        # Se mancano coordinate, recuperale da Gaia
        if not project.ra or not project.dec_deg:
            logger.info(f"Coordinates missing for project {project_id}, resolving from Gaia {project.gaia_id}")
            gaia_info = resolve_gaia_coordinates(project.gaia_id)
            if gaia_info:
                project_ra = gaia_info.get('ra')
                project_dec = gaia_info.get('dec')
                if not project_ra or not project_dec:
                    return jsonify({'error': 'Could not resolve coordinates from Gaia'}), 400
            else:
                return jsonify({'error': 'Could not resolve coordinates from Gaia'}), 400
        else:
            project_ra = project.ra
            project_dec = project.dec_deg

        # Recupera anche altri parametri da Gaia se necessario
        if bp_rp is None or teff is None:
            gaia_info = resolve_gaia_coordinates(project.gaia_id)
            if gaia_info:
                bp_rp = bp_rp or gaia_info.get('bp_rp')
                teff = teff or gaia_info.get('teff')

        # bp_rp non più strettamente richiesto se si usano altri parametri VSX
        if bp_rp is None:
            logger.warning(f"bp_rp not found for project {project_id}, proceeding with VSX-only search")

        # Log parametri ricerca
        search_info = f"project {project_id}: Gaia={project.gaia_id}, RA={project_ra:.4f}, Dec={project_dec:.4f}"
        if periodi:
            search_info += f", periods={periodi}"
        if max_mag or min_mag:
            search_info += f", mag={min_mag or '?'}-{max_mag or '?'}"
        if period_min or period_max:
            search_info += f", P={period_min or '?'}-{period_max or '?'}d"
        if vartype:
            search_info += f", type={vartype}"
        if spec_type:
            search_info += f", spec={spec_type}"

        logger.info(f"Searching analogues for {search_info}")

        analogues = trova_stelle_analoghe(
            gaia_id=project.gaia_id,
            bp_rp=bp_rp or 0.0,  # Fallback per compatibilità
            mag=mag,
            ra=project_ra,
            dec=project_dec,
            periodi=periodi,
            teff=teff,
            top_n=top_n,
            radius_deg=radius_deg,
            max_mag=max_mag,
            min_mag=min_mag,
            period_min=period_min,
            period_max=period_max,
            vartype=vartype,
            spec_type=spec_type
        )

        return jsonify({
            'success': True,
            'project_id': project_id,
            'gaia_id': project.gaia_id,
            'search_params': {
                'bp_rp': bp_rp,
                'mag': mag,
                'teff': teff,
                'periods': periodi,
                'radius_deg': radius_deg,
                'min_mag': min_mag,
                'max_mag': max_mag,
                'min_mag_min': min_mag_min,
                'min_mag_max': min_mag_max,
                'max_mag_min': max_mag_min,
                'max_mag_max': max_mag_max,
                'period_min': period_min,
                'period_max': period_max,
                'vartype': vartype,
                'spec_type': spec_type
            },
            'analogues_count': len(analogues),
            'analogues': analogues
        }), 200

    except Exception as e:
        logger.error(f"Error searching analogues: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@project_detail_bp.route('/<int:project_id>/variability/phased-comparison', methods=['POST'])
@login_required
@admin_required('analyst')
def generate_phased_comparison(project_id: int):
    """
    POST /api/projects/<id>/variability/phased-comparison

    Genera phased light curve comparison con χ² fit.

    Body JSON:
    - periodo: float - Periodo per phase folding (giorni)
    - analogue_gaia_ids: List[str] (opzionale) - Gaia IDs stelle analoghe da confrontare
    - catalog: str (opzionale) - Catalogo dati (default: tutti)

    Returns:
        JSON con plot base64 PNG e statistiche χ²
    """
    db = SessionLocal()
    try:
        project = get_project_or_404(project_id, db)

        # Verifica permessi
        if current_user.role not in ['superuser', 'admin']:
            if project.association_id != current_user.association_id:
                return jsonify({'error': 'Unauthorized'}), 403

        data = request.get_json() or {}
        periodo = data.get('periodo')

        if not periodo:
            return jsonify({'error': 'periodo (float) required'}), 400

        if not project.gaia_id:
            return jsonify({'error': 'Project must have gaia_id'}), 400

        catalog = data.get('catalog')  # es. 'ASAS-SN', 'TESS'
        analogue_ids = data.get('analogue_gaia_ids', [])

        logger.info(f"Generating phased comparison for project {project_id}: "
                   f"periodo={periodo}, analogues={len(analogue_ids)}")

        # Recupera LC target
        target_lc = get_lightcurve_from_db(db, project.gaia_id, catalog)

        if not target_lc:
            return jsonify({'error': f'No lightcurve data for Gaia {project.gaia_id}'}), 404

        # Prepara lightcurves per plot
        lightcurves_data = [{
            'time': target_lc['time'],
            'flux': target_lc['flux'],
            'flux_err': target_lc['flux_err'],
            'label': f"Target: {project.gaia_id[:12]}"
        }]

        # Aggiungi analoghe (max 3 per evitare overload plot)
        for aid in analogue_ids[:3]:
            analogue_lc = get_lightcurve_from_db(db, aid, catalog)
            if analogue_lc:
                lightcurves_data.append({
                    'time': analogue_lc['time'],
                    'flux': analogue_lc['flux'],
                    'flux_err': analogue_lc['flux_err'],
                    'label': f"Analogue: {aid[:12]}"
                })

        # Genera plot
        plot_base64 = generate_phased_comparison_plot(lightcurves_data, periodo)

        if not plot_base64:
            return jsonify({'error': 'Failed to generate comparison plot'}), 500

        return jsonify({
            'success': True,
            'project_id': project_id,
            'periodo': periodo,
            'lc_count': len(lightcurves_data),
            'plot': f"data:image/png;base64,{plot_base64}",
            'message': f'Generated phased comparison for {len(lightcurves_data)} light curves'
        }), 200

    except Exception as e:
        logger.error(f"Error generating phased comparison: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# ============================================================================
# SUPPORT ANALYSIS - PREPARAZIONE AAVSO/VSX
# ============================================================================

@project_detail_bp.route('/<int:project_id>/support-analysis', methods=['GET'])
@login_required
@admin_required('analyst')
def get_support_analysis_data(project_id: int):
    """
    GET /api/projects/<id>/support-analysis

    Recupera dati analisi di supporto per progetto.
    Include suggerimenti da Gaia DR3 per pre-popolazione campi.

    Returns:
        JSON con:
        - project: info base progetto
        - support_data: campi analisi supporto attuali
        - gaia_suggestions: suggerimenti da Gaia (se disponibili)
    """
    db = SessionLocal()
    try:
        project = get_project_or_404(project_id, db)

        # Verifica permessi
        if current_user.role not in ['superuser', 'admin']:
            if project.association_id != current_user.association_id:
                return jsonify({'error': 'Unauthorized'}), 403
            # Analyst: deve essere assegnato al progetto
            if current_user.role == 'analyst' and project.assigned_to != current_user.id:
                return jsonify({'error': 'Unauthorized - not assigned'}), 403

        # Recupera dati Gaia se disponibili per pre-popolazione (con retry per TAP instabile)
        gaia_suggestions = None
        gaia_data = None
        if project.gaia_id:
            from agata.moduli.admin.services.catalog_common_service import resolve_gaia_coordinates
            from agata.moduli.admin.routes.catalogs.tess import with_retries
            try:
                # Usa retry per Gaia TAP query (spesso instabile)
                gaia_data = with_retries(
                    lambda: resolve_gaia_coordinates(project.gaia_id, full_params=True),
                    label=f"Gaia TAP query for {project.gaia_id}",
                    tries=3,  # 3 tentativi per Gaia
                    base_sleep=1.0,  # 1 secondo base
                    timeout=30  # 30 secondi timeout per TAP
                )
                if gaia_data:
                    # Calcola VfromG dalla formula Gaia EDR3 (riusa funzione da vast_service)
                    from agata.moduli.admin.services.vast_service import _calculate_vmag_from_gaia
                    gmag = gaia_data.get('phot_g_mean_mag')
                    bp_rp = gaia_data.get('bp_rp')
                    v_from_g = _calculate_vmag_from_gaia(gmag, bp_rp) if gmag is not None else None

                    # Formatta per suggerimenti form
                    gaia_suggestions = {
                        'teff': gaia_data.get('teff'),
                        'color_bprp': bp_rp,
                        'distance': gaia_data.get('distance'),
                        'radius': gaia_data.get('radius'),
                        'luminosity': gaia_data.get('luminosity'),
                        'gmag': float(gmag) if gmag is not None else None,
                        'bp_rp': float(bp_rp) if bp_rp is not None else None,
                        'v_from_g': round(v_from_g, 4) if v_from_g is not None else None,
                    }
                    logger.info(f"✅ Gaia suggestions retrieved for project {project_id} (VfromG={v_from_g})")
            except Exception as e:
                error_msg = str(e)[:150]
                logger.warning(f"⚠️  Failed to get Gaia suggestions (TAP may be slow/unavailable): {error_msg}")

        # Coordinate J2000 con correzione moto proprio (da J2016 a J2000)
        ra_j2000 = gaia_data.get('ra_j2000') if gaia_data else None
        dec_j2000 = gaia_data.get('dec_j2000') if gaia_data else None
        if ra_j2000 is None:
            ra_j2000 = project.ra
        if dec_j2000 is None:
            dec_j2000 = project.dec_deg

        return jsonify({
            'project': {
                'id': project.id,
                'project_code': project.project_code,
                'gaia_id': project.gaia_id,
                'title': project.title,
                'ra': project.ra,
                'dec_deg': project.dec_deg,
                'ra_j2000': ra_j2000,
                'dec_j2000': dec_j2000,
                'magnitude': project.magnitude,
            },
            'support_data': {
                'spectral_class': project.spectral_class,
                'teff': project.teff,
                'distance': project.distance,
                'luminosity': project.luminosity,
                'radius': project.radius,
                'mass': project.mass,
                'color_bv': project.color_bv,
                'color_bprp': project.color_bprp,
                'variable_type': project.variable_type,
                'catalog_identifiers': project.catalog_identifiers,
                'variability_amplitude': project.variability_amplitude,
                'passband': project.passband,
                'period': project.period,
                'epoch': project.epoch,
            },
            'gaia_suggestions': gaia_suggestions
        }), 200

    except Exception as e:
        logger.error(f"Error getting support analysis data: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@project_detail_bp.route('/<int:project_id>/support-analysis', methods=['POST'])
@login_required
@admin_required('analyst')
def update_support_analysis_data(project_id: int):
    """
    POST /api/projects/<id>/support-analysis

    Salva dati analisi di supporto.

    Body JSON:
    - spectral_class: str (opzionale)
    - teff: float (opzionale)
    - distance: float (opzionale)
    - luminosity: float (opzionale)
    - radius: float (opzionale)
    - mass: float (opzionale)
    - color_bv: float (opzionale)
    - color_bprp: float (opzionale)
    - variable_type: str (opzionale)
    - catalog_identifiers: str (opzionale, multi-riga)
    - variability_amplitude: float (opzionale)
    - passband: str (opzionale)
    - period: float (opzionale)
    - epoch: float (opzionale)

    Returns:
        JSON con success message
    """
    db = SessionLocal()
    try:
        project = get_project_or_404(project_id, db)

        # Verifica permessi
        if current_user.role not in ['superuser', 'admin']:
            if project.association_id != current_user.association_id:
                return jsonify({'error': 'Unauthorized'}), 403
            # Analyst: deve essere assegnato al progetto
            if current_user.role == 'analyst' and project.assigned_to != current_user.id:
                return jsonify({'error': 'Unauthorized - not assigned'}), 403

        data = request.get_json() or {}

        # Aggiorna campi supporto analisi
        fields = [
            'spectral_class', 'teff', 'distance', 'luminosity', 'radius', 'mass',
            'color_bv', 'color_bprp', 'variable_type', 'catalog_identifiers',
            'variability_amplitude', 'passband', 'period', 'epoch'
        ]

        updated_fields = []
        for field in fields:
            if field in data:
                setattr(project, field, data[field])
                updated_fields.append(field)

        from datetime import datetime
        project.updated_at = datetime.utcnow()

        db.commit()

        logger.info(f"Support analysis data updated for project {project_id} by {current_user.email}: "
                   f"fields={updated_fields}")

        return jsonify({
            'success': True,
            'message': 'Dati analisi di supporto salvati con successo',
            'project_id': project_id,
            'updated_fields': updated_fields,
            'updated_at': project.updated_at.isoformat()
        }), 200

    except Exception as e:
        db.rollback()
        logger.error(f"Error updating support analysis data: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


def get_kb_services():
    """
    Ottiene istanze singleton di EmbeddingService e VectorStore
    per evitare di ricaricare il modello ad ogni richiesta (risparmio memoria/tempo)
    """
    global _embedding_service_instance, _vector_store_instance

    if _embedding_service_instance is None:
        from agata.kb.services.embedding_service import EmbeddingService
        logger.info("Inizializzazione EmbeddingService (sentence-transformers) - prima chiamata")
        _embedding_service_instance = EmbeddingService(provider='sentence-transformers')
        logger.info("EmbeddingService inizializzato e cachato")

    if _vector_store_instance is None:
        from agata.kb.services.vector_store import VectorStore
        _vector_store_instance = VectorStore()

    return _embedding_service_instance, _vector_store_instance


@project_detail_bp.route('/<int:project_id>/kb-query', methods=['POST'])
@login_required
@admin_required('analyst')
def kb_query(project_id: int):
    """
    POST /api/projects/<id>/kb-query

    Interroga Knowledge Base per validazione dati progetto.

    Body JSON:
    - query: str - Domanda per KB

    Returns:
        JSON con risultati KB:
        - success: bool
        - query: str
        - results: list di documenti/chunk rilevanti
        - count: int
    """
    logger.info(f"========== KB QUERY REQUEST - Project {project_id} ==========")
    db = SessionLocal()
    try:
        project = get_project_or_404(project_id, db)
        logger.info(f"Project: {project.project_code}, User: {current_user.email}")

        # Verifica permessi
        if current_user.role not in ['superuser', 'admin']:
            if project.association_id != current_user.association_id:
                return jsonify({'error': 'Unauthorized'}), 403
            # Analyst: deve essere assegnato al progetto
            if current_user.role == 'analyst' and project.assigned_to != current_user.id:
                return jsonify({'error': 'Unauthorized - not assigned'}), 403

        data = request.get_json() or {}
        query = data.get('query', '').strip()

        if not query:
            return jsonify({'error': 'Query vuota'}), 400

        # Importa KB search
        try:
            from agata.kb.services.vector_store import VectorStore
            from agata.kb.services.embedding_service import EmbeddingService
        except ImportError:
            logger.error("KB modules not available")
            return jsonify({
                'success': False,
                'error': 'Knowledge Base non disponibile. Verifica configurazione.'
            }), 500

        try:
            # Aggiungi contesto progetto alla query
            context_query = f"{query}\n\nContesto: Progetto {project.project_code}, Gaia ID {project.gaia_id}"
            logger.info(f"KB query: '{query}' (project: {project.project_code})")

            # Ottieni servizi KB singleton (evita ricaricamento modello)
            embedding_service, vector_store = get_kb_services()

            # Controlla se ci sono vettori
            total_vectors = vector_store.count_vectors()
            logger.info(f"Vector store contiene {total_vectors} documenti")

            if total_vectors == 0:
                logger.warning("Nessun vettore nel KB - esegui 'python -m agata.kb generate-embeddings' prima")
                return jsonify({
                    'success': True,
                    'query': query,
                    'results': [],
                    'count': 0,
                    'message': 'Knowledge Base vuoto. Esegui prima: python -m agata.kb generate-embeddings'
                }), 200

            # Genera embedding query
            query_embedding = embedding_service.embed(context_query)
            logger.info(f"Embedding generato: dimensione {len(query_embedding)}")

            # Ricerca vettoriale con boosting per stella corrente
            results_raw = vector_store.search(
                query_embedding=query_embedding,
                top_k=10,
                filters=None
            )
            logger.info(f"Trovati {len(results_raw)} risultati raw da {vector_store.count_vectors()} vettori totali")

            # Boost: aumenta score per risultati che menzionano la stessa stella
            import re as _re
            project_star_match = _re.search(r'GrAGVar\d+', project.project_code or '', _re.IGNORECASE)
            if project_star_match:
                star_id = project_star_match.group(0)
                for result in results_raw:
                    meta = result.get('metadata', {})
                    subject = meta.get('subject', '')
                    body = meta.get('body_text', '')
                    if star_id.lower() in subject.lower() or star_id.lower() in body.lower():
                        result['score'] = min(1.0, result['score'] + 0.15)
                    if meta.get('star_id') and meta['star_id'].lower() == star_id.lower():
                        result['score'] = min(1.0, result['score'] + 0.15)
                results_raw.sort(key=lambda x: x['score'], reverse=True)

            # Formatta risultati per risposta JSON
            results = []
            context_parts = []  # Per Cerebras LLM

            # Lista di keyword da escludere (case-insensitive)
            exclude_keywords = ['GUNVAG2', 'gunvag2']

            filtered_count = 0
            for i, result in enumerate(results_raw):
                metadata = result.get('metadata', {})

                # Filtra risultati con keyword escluse nel subject o body
                subject = metadata.get('subject', '').lower()
                body = metadata.get('body_text', '').lower()

                if any(keyword.lower() in subject or keyword.lower() in body for keyword in exclude_keywords):
                    filtered_count += 1
                    logger.info(f"Risultato {i+1} FILTRATO (contiene keyword esclusa): {metadata.get('subject', 'N/A')}")
                    continue

                logger.info(f"Risultato {i+1}: metadata={metadata}, score={result.get('score', 0.0)}")

                # Formatta per JSON response
                results.append({
                    'title': metadata.get('subject', metadata.get('title', 'Risultato')),
                    'content': metadata.get('body_text', result.get('text', 'Nessun contenuto')),
                    'source': metadata.get('source', 'unknown'),
                    'score': result.get('score', 0.0),
                    'from': metadata.get('from_name', 'Unknown'),
                    'date': metadata.get('date', 'unknown')
                })

                # Prepara contesto per LLM
                email_content = metadata.get('body_text', '')[:1000]  # Prime 1000 char
                context_parts.append(f"""
Email {len(results)} (Score: {result.get('score', 0):.3f})
Subject: {metadata.get('subject', 'No subject')}
From: {metadata.get('from_name', 'Unknown')} <{metadata.get('from_email', '')}>
Date: {metadata.get('date', 'Unknown')}

Content:
{email_content}
---
""")

            if filtered_count > 0:
                logger.info(f"Filtrati {filtered_count} risultati con keyword escluse")

            # Genera risposta con Cerebras LLM (come fa il CLI)
            llm_answer = None
            if results_raw:
                try:
                    context_text = '\n'.join(context_parts)
                    prompt = f"""Sei un assistente esperto in astronomia e analisi di stelle variabili.

Basandoti SOLO sulle seguenti email, rispondi alla domanda dell'utente in modo chiaro e dettagliato.
Se le informazioni non sono sufficienti, dillo chiaramente.

EMAIL RILEVANTI:
{context_text}

DOMANDA: {query}

Rispondi in italiano (o nella lingua della domanda) in modo chiaro e strutturato.
Cita le email quando possibile (es: "Secondo l'email del [data]...").
"""
                    from agata.moduli.variable_stars.services.llm_client import LLMClient
                    llm = LLMClient()
                    result = llm.generate(prompt, temperature=0.3, max_tokens=1000)
                    llm_answer = result['response_text']
                    logger.info("Risposta LLM generata con successo")
                except Exception as llm_error:
                    logger.error(f"Errore generazione LLM: {llm_error}")
                    llm_answer = None

            # Salva in history
            from agata.auth_models.kb_search_history import KBSearchHistory
            from datetime import datetime
            history = KBSearchHistory(
                user_id=current_user.id,
                query=query,
                results_count=len(results),
                search_duration_ms=0,
                created_at=datetime.utcnow()
            )
            db.add(history)
            db.commit()

            logger.info(f"KB query executed for project {project_id}: {len(results)} results")
            logger.info(f"Comando CLI equivalente: python -m agata.kb ask \"{query}\"")

            response_data = {
                'success': True,
                'query': query,
                'results': results,
                'count': len(results),
                'answer': llm_answer  # Risposta generata da Cerebras
            }
            logger.info(f"========== KB QUERY RESPONSE: {len(results)} results ==========")
            if results:
                logger.info(f"First result title: {results[0].get('title', 'N/A')}")
            else:
                logger.warning("NO RESULTS FOUND!")

            return jsonify(response_data), 200

        except Exception as kb_error:
            logger.error(f"KB query error: {kb_error}", exc_info=True)
            return jsonify({
                'success': False,
                'error': f'Errore durante query KB: {str(kb_error)}'
            }), 500

    except Exception as e:
        logger.error(f"Error in kb_query: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@project_detail_bp.route('/<int:project_id>/kb-star-context', methods=['GET'])
@login_required
@admin_required('analyst')
def kb_star_context(project_id: int):
    """
    GET /api/projects/<id>/kb-star-context

    Recupera contesto Knowledge Base per la stella del progetto.
    Lookup diretto per star ID (GrAGVar) nell'indice stella.
    Ritorna tutte le email, messaggi Teams, correzioni esperto.
    """
    db = SessionLocal()
    try:
        project = get_project_or_404(project_id, db)

        # Verifica permessi
        if current_user.role not in ['superuser', 'admin']:
            if project.association_id != current_user.association_id:
                return jsonify({'error': 'Unauthorized'}), 403
            if current_user.role == 'analyst' and project.assigned_to != current_user.id:
                return jsonify({'error': 'Unauthorized - not assigned'}), 403

        project_code = project.project_code or ''

        try:
            from agata.kb.services.star_index import get_star_context, load_star_index
            import re

            # Cerca per project_code esatto o GrAGVar ID contenuto nel code
            star_context = get_star_context(project_code)

            # Fallback: cerca GrAGVar nel project_code
            if not star_context:
                match = re.search(r'GrAGVar\d+', project_code, re.IGNORECASE)
                if match:
                    star_context = get_star_context(match.group(0))

            if star_context:
                # Conta per tipo
                email_count = len(star_context.get('email_ids', []))
                teams_count = len(star_context.get('teams_ids', []))
                expert_count = len(star_context.get('expert_emails', []))

                # Filtra correzioni: solo quelle dell'esperto prima
                corrections = star_context.get('corrections', [])
                expert_corrections = [c for c in corrections if c.get('is_expert')]
                team_corrections = [c for c in corrections if not c.get('is_expert')]

                return jsonify({
                    'success': True,
                    'found': True,
                    'star_id': project_code,
                    'email_count': email_count,
                    'teams_count': teams_count,
                    'expert_count': expert_count,
                    'variable_types_discussed': star_context.get('variable_types_discussed', []),
                    'period_values': star_context.get('period_values', []),
                    'amplitude_values': star_context.get('amplitude_values', []),
                    'expert_corrections': expert_corrections[:20],
                    'team_corrections': team_corrections[:10],
                    'attachments': star_context.get('attachments', [])[:30],
                    'messages': star_context.get('messages', [])[:20],
                    'last_expert_date': star_context.get('last_expert_date'),
                }), 200
            else:
                return jsonify({
                    'success': True,
                    'found': False,
                    'star_id': project_code,
                    'message': 'Nessun contesto KB trovato per questa stella'
                }), 200

        except Exception as kb_error:
            logger.warning(f"KB star context error: {kb_error}")
            return jsonify({
                'success': True,
                'found': False,
                'star_id': project_code,
                'message': f'Errore caricamento star index: {str(kb_error)}'
            }), 200

    except Exception as e:
        logger.error(f"Error in kb_star_context: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@project_detail_bp.route('/<int:project_id>/kb-validate-aavso', methods=['POST'])
@login_required
@admin_required('analyst')
def kb_validate_aavso(project_id: int):
    """
    POST /api/projects/<id>/kb-validate-aavso

    Valida campi di analisi AAVSO contro linee guida nel Knowledge Base.
    Usa il KB per trovare linee guida AAVSO e LLM per validazione.

    Body JSON:
    - variable_type: str (es: "RR Lyrae")
    - period: float (giorni)
    - amplitude: float (mag)
    - epoch: float (JD)
    - spectral_class: str (es: "A5 V")
    - passband: str (es: "V", "G")

    Returns:
        JSON con validazione:
        - success: bool
        - valid: bool - Se sono presenti errori critici
        - overall_score: int (0-100)
        - issues: list di problemi rilevati
        - suggestions: list di suggerimenti
        - aavso_compliance: dict con dettagli compliance
        - guidelines_summary: str con riassunto linee guida applicate
    """
    logger.info(f"========== AAVSO VALIDATION REQUEST - Project {project_id} ==========")
    db = SessionLocal()
    try:
        project = get_project_or_404(project_id, db)
        logger.info(f"Project: {project.project_code}, User: {current_user.email}")

        # Verifica permessi (stesso come kb_query)
        if current_user.role not in ['superuser', 'admin']:
            if project.association_id != current_user.association_id:
                return jsonify({'error': 'Unauthorized'}), 403
            if current_user.role == 'analyst' and project.assigned_to != current_user.id:
                return jsonify({'error': 'Unauthorized - not assigned'}), 403

        data = request.get_json() or {}
        logger.info(f"Validation data: {data}")

        # Estrai campi
        variable_type = data.get('variable_type', '').strip()
        period = data.get('period')
        amplitude = data.get('amplitude')
        epoch = data.get('epoch')
        spectral_class = data.get('spectral_class', '').strip()
        passband = data.get('passband', 'V').strip()

        if not variable_type or period is None:
            return jsonify({
                'error': 'Campi obbligatori mancanti: variable_type, period'
            }), 400

        try:
            from agata.kb.services.vector_store import VectorStore
            from agata.kb.services.embedding_service import EmbeddingService
        except ImportError:
            logger.error("KB modules not available")
            return jsonify({
                'success': False,
                'error': 'Knowledge Base non disponibile'
            }), 500

        try:
            # Crea query semantica per trovare linee guida AAVSO
            query = f"""AAVSO submission guidelines for {variable_type}.

Variable type: {variable_type}
Period: {period} days
Amplitude: {amplitude} mag
Passband: {passband}
Spectral class: {spectral_class}

Required checks:
- Period range validity for {variable_type}
- Amplitude consistency with variable type
- Epoch format (Julian Day)
- Spectral class compatibility
- Phase coverage requirements
- Light curve quality criteria
- Minimum observations required"""

            logger.info(f"AAVSO validation query created")

            # Ottieni servizi KB singleton
            embedding_service, vector_store = get_kb_services()

            total_vectors = vector_store.count_vectors()
            logger.info(f"Vector store contiene {total_vectors} documenti")

            if total_vectors == 0:
                return jsonify({
                    'success': True,
                    'valid': None,
                    'message': 'Knowledge Base vuoto - impossibile validare'
                }), 200

            # Genera embedding e ricerca documenti AAVSO
            query_embedding = embedding_service.embed(query)

            # Ricerca con filtro per documenti AAVSO
            results_raw = vector_store.search(
                query_embedding=query_embedding,
                top_k=3,
                filters=None  # TODO: aggiungere filtro tags=['aavso']
            )
            logger.info(f"Trovati {len(results_raw)} risultati per validazione AAVSO")

            # Prepara contesto per LLM
            context_parts = []
            for result in results_raw:
                metadata = result.get('metadata', {})
                # Estrai contenuto relevante
                content = metadata.get('body_text', metadata.get('content', ''))[:2000]

                if content:
                    context_parts.append(f"""
Source: {metadata.get('title', 'Document')} (Score: {result.get('score', 0):.2f})
Date: {metadata.get('date', 'N/A')}

{content}
---""")

            context_text = '\n'.join(context_parts)

            # Genera validazione con LLM
            validation_prompt = f"""Sei un esperto AAVSO submission. Valida questi dati di osservazione:

DATI INSERITI:
- Variable Type: {variable_type}
- Period: {period} days
- Amplitude: {amplitude} mag
- Epoch: {epoch} (JD)
- Spectral Class: {spectral_class}
- Passband: {passband}

LINEE GUIDA AAVSO (dal Knowledge Base):
{context_text}

COMPITO:
Valida i dati rispetto alle linee guida AAVSO. Ritorna SOLO un JSON valido (nessun testo aggiuntivo):

{{
  "valid": true/false,
  "overall_score": <0-100>,
  "issues": [
    {{
      "field": "period",
      "severity": "error|warning|info",
      "message": "Periodo incompatibile...",
      "source": "AAVSO guidelines",
      "suggested_fix": "Ricontrollare analisi..."
    }}
  ],
  "suggestions": [
    {{
      "field": "variable_type",
      "suggested_value": "...",
      "reason": "...",
      "confidence": "high|medium|low"
    }}
  ],
  "aavso_compliance": {{
    "period_range": "ok|warning|error",
    "amplitude_range": "ok|warning|error",
    "spectral_class": "ok|warning|error",
    "epoch_format": "ok|warning|error",
    "observations_count": "ok|warning|error"
  }},
  "guidelines_summary": "Breve riassunto linee guida applicate"
}}"""

            logger.info("Generazione validazione AAVSO con LLM...")
            from agata.moduli.variable_stars.services.llm_client import LLMClient
            import json

            llm = LLMClient()
            result = llm.generate(validation_prompt, temperature=0.2, max_tokens=1500)
            response_text = result['response_text'].strip()
            logger.info(f"LLM response length: {len(response_text)}")

            # Prova a parsare JSON dalla risposta
            validation_result = None
            try:
                # Ricerca il JSON nel testo (potrebbe avere testo aggiuntivo)
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                if json_start != -1 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    validation_result = json.loads(json_str)
                    logger.info("Validazione AAVSO JSON parsed correttamente")
            except json.JSONDecodeError as je:
                logger.error(f"JSON parsing error: {je}")
                # Fallback: crea risposta strutturata manuale
                validation_result = {
                    'valid': 'error' not in response_text.lower(),
                    'overall_score': 50,
                    'issues': [],
                    'suggestions': [],
                    'aavso_compliance': {},
                    'guidelines_summary': response_text[:500]
                }

            # Aggiungi metadati alla risposta
            response_data = {
                'success': True,
                'project_id': project_id,
                'validation': validation_result,
                'sources_count': len(results_raw),
                'data_validated': {
                    'variable_type': variable_type,
                    'period': period,
                    'amplitude': amplitude,
                    'spectral_class': spectral_class,
                    'passband': passband
                }
            }

            logger.info(f"========== AAVSO VALIDATION RESPONSE ==========")
            logger.info(f"Valid: {validation_result.get('valid', None)}, Score: {validation_result.get('overall_score', 0)}")

            return jsonify(response_data), 200

        except Exception as llm_error:
            logger.error(f"Errore validazione AAVSO: {llm_error}", exc_info=True)
            return jsonify({
                'success': False,
                'error': f'Errore durante validazione AAVSO: {str(llm_error)}'
            }), 500

    except Exception as e:
        logger.error(f"Error in kb_validate_aavso: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# =============================================================================
# VALIDAZIONE COMPLETEZZA DATI VARIABILE (KB + FALLBACK)
# =============================================================================

@project_detail_bp.route('/<int:project_id>/kb-validate-completeness', methods=['POST'])
@login_required
@admin_required('analyst')
@audit_action('kb_validate_completeness', 'project')
def kb_validate_completeness(project_id: int):
    """
    Valida completezza dati variabile stellare usando Knowledge Base.

    Controlla:
    1. Identificatori obbligatori/raccomandati (VSX ID, AAVSO ID, etc.)
    2. Cataloghi raccomandati per tipo variabile
    3. Precisione periodo adeguata per tipo variabile

    Input JSON:
    {
        "variable_type": "RR Lyrae",
        "period": 0.567,
        "period_precision": 0.0001,
        "amplitude": 1.2,
        "epoch": 2460000.5,
        "gaia_id": "Gaia DR3 123456",
        "vsx_id": null,
        "aavso_id": null,
        "catalog_identifiers": "2MASS J12345678-4512345",
        "ra": 123.456,
        "dec": -45.678,
        "catalogs_consulted": ["ASAS-SN", "Gaia"],
        "passband": "V",
        "spectral_class": "A5 V"
    }

    Output JSON:
    {
        "valid": false,
        "overall_score": 65,
        "missing_identifiers": [...],
        "catalog_recommendations": [...],
        "period_precision_check": {...},
        "data_quality_checks": [...],
        "overall_suggestions": [...]
    }
    """
    db: Session = SessionLocal()
    try:
        # Fetch project
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return jsonify({'error': 'Progetto non trovato'}), 404

        # Check permissions
        if current_user.role != 'superuser':
            if project.association_id != current_user.association_id:
                return jsonify({'error': 'Non autorizzato'}), 403

        # Parse request data
        data = request.get_json() or {}

        variable_type = data.get('variable_type', '').strip()
        period = data.get('period')
        period_precision = data.get('period_precision')
        amplitude = data.get('amplitude')
        gaia_id = data.get('gaia_id')
        vsx_id = data.get('vsx_id')
        aavso_id = data.get('aavso_id')
        ra = data.get('ra')
        dec = data.get('dec')
        catalogs_consulted = data.get('catalogs_consulted', [])

        if not variable_type:
            return jsonify({'error': 'variable_type è obbligatorio'}), 400

        logger.info(f"KB Validation for {variable_type}, project {project_id}")

        # Import validation rules
        from agata.kb.services.validation_rules import (
            missing_identifiers_for_type,
            recommended_catalogs_not_consulted,
            validate_period_precision,
            check_amplitude_ok,
            calculate_validation_score
        )

        # =====================================================================
        # 1. VALIDARE IDENTIFICATORI MANCANTI
        # =====================================================================

        provided_ids = {
            'gaia_id': gaia_id,
            'vsx_id': vsx_id,
            'aavso_id': aavso_id
        }

        missing_ids = missing_identifiers_for_type(variable_type, provided_ids)
        logger.info(f"Missing identifiers: {len(missing_ids)}")

        # =====================================================================
        # 2. VALIDARE CATALOGHI RACCOMANDATI
        # =====================================================================

        recommended_catalogs = recommended_catalogs_not_consulted(
            variable_type,
            catalogs_consulted or []
        )
        logger.info(f"Recommended catalogs not consulted: {len(recommended_catalogs)}")

        # =====================================================================
        # 3. VALIDARE PRECISIONE PERIODO
        # =====================================================================

        period_check = {"valid": True}
        if period is not None and period_precision is not None:
            try:
                period = float(period)
                period_precision = float(period_precision)
                period_check = validate_period_precision(variable_type, period, period_precision)
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not validate period: {e}")
                period_check = {"valid": True, "message": "Validazione periodo non disponibile"}

        # =====================================================================
        # 4. VALIDARE AMPIEZZA
        # =====================================================================

        amplitude_check = {"valid": True, "message": ""}
        if amplitude is not None:
            try:
                amplitude = float(amplitude)
                amplitude_valid, amplitude_msg = check_amplitude_ok(variable_type, amplitude)
                amplitude_check = {
                    "valid": amplitude_valid,
                    "message": amplitude_msg,
                    "field": "amplitude"
                }
            except (ValueError, TypeError):
                pass

        # =====================================================================
        # 5. CALCOLARE SCORE COMPLESSIVO
        # =====================================================================

        overall_score = calculate_validation_score(
            variable_type,
            missing_ids,
            recommended_catalogs,
            period_check.get("valid", True),
            amplitude_check.get("valid", True)
        )

        is_valid = (
            overall_score >= 60 and
            len([m for m in missing_ids if m["severity"] == "error"]) == 0
        )

        # =====================================================================
        # 6. GENERARE SUGGERIMENTI COMPLESSIVI
        # =====================================================================

        suggestions = []

        # Suggerimenti per identificatori mancanti
        for missing_id in missing_ids:
            if missing_id["severity"] == "error":
                suggestions.append(f"CRITICO: Aggiungi {missing_id['field']} prima di sottomissione AAVSO")
            elif missing_id["severity"] == "warning":
                suggestions.append(f"Aggiungi {missing_id['field']} per aumentare qualità sottomissione")

        # Suggerimenti per cataloghi
        if recommended_catalogs:
            high_priority = [c for c in recommended_catalogs if c.get("priority") == "high"]
            if high_priority:
                catalogs_str = ", ".join([c["catalog"] for c in high_priority])
                suggestions.append(f"Consulta cataloghi ad alta priorità: {catalogs_str}")

        # Suggerimenti per periodo
        if not period_check.get("valid"):
            if "suggested_action" in period_check:
                suggestions.append(f"Periodo: {period_check['suggested_action']}")

        # Suggerimenti per ampiezza
        if not amplitude_check.get("valid"):
            suggestions.append(f"Ampiezza: {amplitude_check.get('message', '')}")

        # =====================================================================
        # 6b. EXPERT WARNINGS (dalla KB - correzioni reali di Otero)
        # =====================================================================
        expert_warnings = []
        try:
            from agata.kb.services.expert_validation import get_expert_warnings
            import re as _re
            star_match = _re.search(r'GrAGVar\d+', project.project_code or '', _re.IGNORECASE)
            star_id_for_expert = star_match.group(0) if star_match else None
            expert_warnings = get_expert_warnings(variable_type, star_id=star_id_for_expert)
            if expert_warnings:
                logger.info(f"Expert warnings: {len(expert_warnings)} for type={variable_type}, star={star_id_for_expert}")
                for ew in expert_warnings:
                    if ew.get('source') == 'expert_star_specific':
                        suggestions.insert(0, f"ESPERTO AAVSO: {ew['text']}")
                    elif ew.get('severity') == 'high':
                        suggestions.append(f"Avviso esperto: {ew['text']}")
        except Exception as expert_err:
            logger.warning(f"Could not load expert warnings: {expert_err}")

        # =====================================================================
        # 7. SALVARE RICERCA NEL KB SEARCH HISTORY
        # =====================================================================

        try:
            from agata.auth_models import KBSearchHistory
            search_record = KBSearchHistory(
                user_id=current_user.id,
                user_email=current_user.email,
                association_id=current_user.association_id,
                query_type='validate_completeness',
                query_text=f"Validate: {variable_type}, P={period}, Prec={period_precision}",
                result_count=len(missing_ids) + len(recommended_catalogs),
                is_kb_backed=True,
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )
            db.add(search_record)
            db.commit()
            logger.info(f"KB validation search saved")
        except Exception as e:
            logger.warning(f"Could not save KB search history: {e}")
            db.rollback()

        # =====================================================================
        # 8. COSTRUIRE RESPONSE
        # =====================================================================

        response_data = {
            'success': True,
            'valid': is_valid,
            'overall_score': overall_score,
            'project_id': project_id,
            'project_code': project.project_code,
            'variable_type': variable_type,
            'missing_identifiers': missing_ids,
            'catalog_recommendations': recommended_catalogs,
            'period_precision_check': period_check,
            'amplitude_check': amplitude_check,
            'overall_suggestions': suggestions,
            'expert_warnings': expert_warnings,
            'validation_metadata': {
                'timestamp': datetime.now().isoformat(),
                'kb_backed': True,
                'using_fallback_rules': True,
                'has_expert_rules': len(expert_warnings) > 0,
                'has_kb_search': True
            }
        }

        logger.info(f"========== COMPLETENESS VALIDATION RESPONSE ==========")
        logger.info(f"Valid: {is_valid}, Score: {overall_score}")

        return jsonify(response_data), 200

    except Exception as e:
        logger.error(f"Error in kb_validate_completeness: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Errore durante validazione: {str(e)}'
        }), 500
    finally:
        db.close()


@project_detail_bp.route('/<int:project_id>/kb-similar-stars', methods=['POST'])
@login_required
@admin_required('analyst')
def kb_similar_stars(project_id: int):
    """
    POST /api/projects/<id>/kb-similar-stars

    Ricerca semantica nella KB per trovare stelle GrAGVar analoghe alla stella in analisi.
    Usa i parametri della stella (periodo, ampiezza, tipo provvisorio, note) per costruire
    una query semantica e recupera messaggi simili raggruppati per stella.

    Body JSON:
        period_days: float - periodo trovato dall'analisi
        amplitude_mag: float - ampiezza picco-picco stimata
        variable_type: str - tipo variabile provvisorio (es. EA, EW, DSCT)
        tess_sectors: list[int] - settori TESS disponibili
        notes: str - note libere dell'analista (es. "eclissi secondaria a fase 0.5")
        top_k: int - max risultati per query (default 15)
    """
    db = SessionLocal()
    try:
        project = get_project_or_404(project_id, db)
        if current_user.role not in ['superuser', 'admin']:
            if project.association_id != current_user.association_id:
                return jsonify({'error': 'Unauthorized'}), 403

        data = request.get_json() or {}
        period = data.get('period_days')
        amplitude = data.get('amplitude_mag')
        var_type = data.get('variable_type', '').strip()
        sectors = data.get('tess_sectors', [])
        notes = data.get('notes', '').strip()
        top_k = min(int(data.get('top_k', 15)), 30)

        # Costruisci query semantica dai parametri
        query_parts = []
        if var_type:
            query_parts.append(f"stella variabile di tipo {var_type}")
        if period:
            query_parts.append(f"periodo {period:.6f} giorni")
        if amplitude:
            query_parts.append(f"ampiezza {amplitude:.3f} magnitudini")
        if sectors:
            query_parts.append(f"curve di luce TESS settori {', '.join(str(s) for s in sectors)}")
        if notes:
            query_parts.append(notes)

        if not query_parts:
            return jsonify({'error': 'Almeno un parametro richiesto (period_days, variable_type, notes)'}), 400

        query_text = '. '.join(query_parts)

        embedding_service, vector_store = get_kb_services()
        query_vec = embedding_service.embed(query_text)
        raw_results = vector_store.search(query_vec, top_k=top_k)

        # Raggruppa per stella GrAGVar
        from agata.kb.services.star_index import get_star_images
        from collections import defaultdict

        by_star = defaultdict(lambda: {
            'star_id': None,
            'messages': [],
            'max_score': 0.0,
            'variable_types': set(),
            'images': [],
        })

        no_star_msgs = []

        for r in raw_results:
            meta = r.get('metadata', {})
            score = r.get('score', 0.0)
            source = meta.get('source', '')
            star_id = meta.get('star_id') or _extract_graagvar(
                meta.get('subject', '') + ' ' + meta.get('body_text', '')[:200]
            )

            msg_entry = {
                'source': source,
                'score': round(score, 3),
                'subject': meta.get('subject', ''),
                'from_name': meta.get('from_name', ''),
                'date': meta.get('date', ''),
                'is_expert': meta.get('from_email', '').endswith('aavso.org') if meta.get('from_email') else False,
                'body_preview': (meta.get('body_text') or '')[:300],
                'variable_type': meta.get('variable_type', ''),
            }

            if star_id:
                by_star[star_id]['star_id'] = star_id
                by_star[star_id]['messages'].append(msg_entry)
                if score > by_star[star_id]['max_score']:
                    by_star[star_id]['max_score'] = score
                if meta.get('variable_type'):
                    by_star[star_id]['variable_types'].add(meta['variable_type'])
            else:
                no_star_msgs.append(msg_entry)

        # Arricchisci ogni stella con immagini fisiche dai Teams
        analogues = []
        for star_id, entry in by_star.items():
            images = get_star_images(star_id)
            entry['images'] = images
            entry['variable_types'] = sorted(entry['variable_types'])
            entry['messages'].sort(key=lambda m: -m['score'])
            analogues.append(entry)

        # Ordina per score massimo decrescente
        analogues.sort(key=lambda x: -x['max_score'])

        return jsonify({
            'success': True,
            'query': query_text,
            'analogues': analogues[:10],  # max 10 stelle
            'unmatched_messages': no_star_msgs[:5],
            'total_results': len(raw_results),
        }), 200

    except Exception as e:
        logger.error(f"Error in kb_similar_stars: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        db.close()


def _extract_graagvar(text: str) -> Optional[str]:
    """Extract first GrAGVar ID from text, or None."""
    import re
    m = re.search(r'GrAGVar\s*(\d+)', text, re.IGNORECASE)
    return f"GrAGVar{m.group(1).zfill(3)}" if m else None


@project_detail_bp.route('/kb-teams-image/<star_id>/<path:filename>', methods=['GET'])
@login_required
@admin_required('analyst')
def kb_teams_image(star_id: str, filename: str):
    """
    GET /api/projects/kb-teams-image/<star_id>/<filename>

    Serve immagini fisiche dagli allegati Teams per una stella GrAGVar.
    Path traversal protetto: only serves files inside the Teams channel directory.
    """
    import re
    from flask import send_file, abort

    # Valida star_id
    if not re.match(r'^GrAGVar\d{1,3}$', star_id, re.IGNORECASE):
        abort(400)

    from agata.kb.services.star_index import TEAMS_CHANNEL_DIR, IMAGE_EXTENSIONS

    if not TEAMS_CHANNEL_DIR.exists():
        abort(404)

    # Cerca il file nelle cartelle del thread per questa stella
    for thread_dir in TEAMS_CHANNEL_DIR.iterdir():
        if not thread_dir.is_dir():
            continue
        if star_id.upper() not in thread_dir.name.upper():
            continue
        candidate = thread_dir / filename
        # Risolvi path reale e verifica che sia dentro TEAMS_CHANNEL_DIR
        try:
            resolved = candidate.resolve()
            resolved.relative_to(TEAMS_CHANNEL_DIR.resolve())
        except (ValueError, OSError):
            abort(403)
        if resolved.exists() and resolved.suffix.lower() in IMAGE_EXTENSIONS:
            return send_file(str(resolved))

    abort(404)


def _get_star_rating(star_id: str) -> int:
    """Legge il rating dalla directory Teams (prefisso numerico nel nome cartella)."""
    from agata.kb.services.star_index import TEAMS_CHANNEL_DIR
    if not TEAMS_CHANNEL_DIR.exists():
        return 0
    for d in TEAMS_CHANNEL_DIR.iterdir():
        if not d.is_dir():
            continue
        if star_id.upper() in d.name.upper():
            try:
                return int(d.name.split('-')[0])
            except (ValueError, IndexError):
                return 0
    return 0


def _get_star_gaia_id(star_id: str) -> Optional[str]:
    """Estrae il Gaia DR3 source ID dal nome della directory Teams per una stella GrAGVar.

    I nomi dir sono tipo: 8-ACV-GrAGVar049-5795202847132179456
    L'ultimo token numerico lungo (>= 10 cifre) è il Gaia ID.
    """
    import re
    from agata.kb.services.star_index import TEAMS_CHANNEL_DIR
    if not TEAMS_CHANNEL_DIR.exists():
        return None
    for d in TEAMS_CHANNEL_DIR.iterdir():
        if not d.is_dir():
            continue
        if star_id.upper() not in d.name.upper():
            continue
        # Cerca l'ultimo token che sia un numero di almeno 10 cifre
        tokens = d.name.split('-')
        for token in reversed(tokens):
            if re.match(r'^\d{10,}$', token):
                return token
    return None


def _classify_image(filename: str) -> str:
    """Classifica il tipo di immagine dal nome file."""
    fn = filename.lower()
    if any(k in fn for k in ['phase', 'fold', 'fase']):
        return 'phase_plot'
    if any(k in fn for k in ['period', 'lomb', 'pgram', 'periodigramma', 'bokeh']):
        return 'periodogram'
    if 'tpf' in fn:
        return 'tpf'
    if any(k in fn for k in ['vicin', 'neighbor', 'blend', 'stelle_vicin']):
        return 'nearby_stars'
    return 'other'


@project_detail_bp.route('/<int:project_id>/kb-guided-analysis', methods=['POST'])
@login_required
@admin_required('analyst')
def kb_guided_analysis(project_id: int):
    """
    POST /api/projects/<id>/kb-guided-analysis

    Ricerca RAG avanzata: trova le stelle GrAGVar approvate (rating >= 8) più simili
    alla stella in analisi, arricchisce con contesto esperto (Otero), e genera una
    guida strutturata con LLM per supportare la compilazione del template AAVSO.

    Body JSON:
        period_days: float
        amplitude_mag: float
        variable_type: str
        tess_sectors: list[int]
        notes: str
        teff: str
        spectral_class: str
        color_bprp: str
        catalog_identifiers: str
        min_rating: int (default 8)
    """
    import numpy as np
    from collections import defaultdict
    from agata.kb.services.star_index import load_star_index, get_star_images

    db = SessionLocal()
    try:
        project = get_project_or_404(project_id, db)
        if current_user.role not in ['superuser', 'admin']:
            if project.association_id != current_user.association_id:
                return jsonify({'error': 'Unauthorized'}), 403

        data = request.get_json() or {}
        period = data.get('period_days')
        amplitude = data.get('amplitude_mag')
        var_type = (data.get('variable_type') or '').strip()
        sectors = data.get('tess_sectors', [])
        notes = (data.get('notes') or '').strip()
        teff = (data.get('teff') or '').strip()
        spectral = (data.get('spectral_class') or '').strip()
        color_bprp = (data.get('color_bprp') or '').strip()
        catalog_ids = (data.get('catalog_identifiers') or '').strip()
        min_rating = int(data.get('min_rating', 8))

        if not period and not var_type and not notes:
            return jsonify({'error': 'Almeno un parametro richiesto (period_days, variable_type, notes)'}), 400

        # === Query expansion: 3 query semantiche diverse ===
        queries = []
        if var_type or period or amplitude:
            q1_parts = []
            if var_type:
                q1_parts.append(f"stella variabile tipo {var_type}")
            if period:
                q1_parts.append(f"periodo {period:.4f} giorni")
            if amplitude:
                q1_parts.append(f"ampiezza {amplitude:.2f} magnitudini")
            queries.append(' '.join(q1_parts))

        if sectors or notes:
            q2_parts = ['curva di luce TESS']
            if sectors:
                q2_parts.append(f"settori {', '.join(str(s) for s in sectors)}")
            if notes:
                q2_parts.append(notes)
            queries.append(' '.join(q2_parts))

        if var_type:
            queries.append(
                f"problemi analisi {var_type} blend contaminazione pixel TESS periodo doppio"
            )

        if not queries:
            queries = [notes or f"stella variabile {var_type}"]

        embedding_service, vector_store = get_kb_services()

        # Media dei vettori (query expansion)
        vecs = [np.array(embedding_service.embed(q)) for q in queries]
        combined_vec = np.mean(vecs, axis=0).tolist()

        raw_results = vector_store.search(combined_vec, top_k=25)

        # === Raggruppa per stella e rirank ===
        star_index = load_star_index()
        by_star = defaultdict(lambda: {
            'star_id': None,
            'rating': 0,
            'messages': [],
            'max_score': 0.0,
            'variable_types': set(),
        })

        for r in raw_results:
            meta = r.get('metadata', {})
            score = r.get('score', 0.0)
            star_id = meta.get('star_id') or _extract_graagvar(
                meta.get('subject', '') + ' ' + (meta.get('body_text') or '')[:200]
            )
            if not star_id:
                continue

            entry = by_star[star_id]
            entry['star_id'] = star_id
            entry['messages'].append({
                'source': meta.get('source', ''),
                'score': round(score, 3),
                'subject': meta.get('subject', ''),
                'from_name': meta.get('from_name', ''),
                'from_email': meta.get('from_email', ''),
                'date': meta.get('date', ''),
                'is_expert': (meta.get('from_email') or '').endswith('aavso.org'),
                'body_text': (meta.get('body_text') or '')[:2000],
            })
            if score > entry['max_score']:
                entry['max_score'] = score
            if meta.get('variable_type'):
                entry['variable_types'].add(meta['variable_type'])

        # Riranking con boost
        analogues_list = []
        for star_id, entry in by_star.items():
            rating = _get_star_rating(star_id)
            entry['rating'] = rating
            score = entry['max_score']

            if rating >= 8:
                score += 0.20
            elif rating >= 6:
                score += 0.05

            idx_entry = star_index.get(star_id, {})
            if var_type and var_type.upper() in [t.upper() for t in idx_entry.get('variable_types_discussed', [])]:
                score += 0.15

            if period:
                for p in idx_entry.get('period_values', []):
                    if p > 0 and abs(p - period) / period <= 0.10:
                        score += 0.10
                        break

            if idx_entry.get('expert_emails'):
                score += 0.05

            entry['reranked_score'] = round(min(score, 1.0), 3)
            analogues_list.append(entry)

        # Filtra per rating, con fallback progressivo
        approved = [a for a in analogues_list if a['rating'] >= min_rating]
        if len(approved) < 2:
            approved = [a for a in analogues_list if a['rating'] >= 6]
        if len(approved) < 2:
            approved = analogues_list

        approved.sort(key=lambda x: -x['reranked_score'])
        top_analogues = approved[:5]

        # === Arricchisci con immagini e correzioni Otero ===
        for a in top_analogues:
            sid = a['star_id']
            idx_entry = star_index.get(sid, {})

            raw_images = get_star_images(sid)
            type_order = {'phase_plot': 0, 'periodogram': 1, 'tpf': 2, 'nearby_stars': 3, 'other': 4}
            a['images'] = sorted([
                {'filename': img['filename'], 'type': _classify_image(img['filename']), 'thread_dir': img['thread_dir']}
                for img in raw_images
            ], key=lambda x: type_order.get(x['type'], 9))

            a['expert_corrections'] = [
                c['text'] for c in idx_entry.get('corrections', []) if c.get('is_expert')
            ][:8]

            a['variable_types'] = sorted(a['variable_types']) or idx_entry.get('variable_types_discussed', [])
            a['period_values'] = idx_entry.get('period_values', [])
            a['similarity_score'] = a['reranked_score']

            expert_msgs = sorted(
                [m for m in a['messages'] if m['is_expert']],
                key=lambda m: -m['score']
            )
            a['best_expert_text'] = expert_msgs[0]['body_text'] if expert_msgs else ''

        # === Prompt LLM ===
        stella_info = []
        if var_type:
            stella_info.append(f"Tipo ipotizzato: {var_type}")
        if period:
            stella_info.append(f"Periodo: {period:.6f} giorni")
        if amplitude:
            stella_info.append(f"Ampiezza: {amplitude:.3f} mag")
        if sectors:
            stella_info.append(f"Settori TESS: {', '.join(str(s) for s in sectors)}")
        if teff:
            stella_info.append(f"Teff: {teff} K")
        if spectral:
            stella_info.append(f"Classe spettrale: {spectral}")
        if color_bprp:
            stella_info.append(f"BP-RP: {color_bprp}")
        if catalog_ids:
            stella_info.append(f"Identificatori cataloghi: {catalog_ids[:200]}")
        if notes:
            stella_info.append(f"Note analista: {notes}")
        if project.gaia_id:
            stella_info.append(f"Gaia DR3: {project.gaia_id}")

        analogues_context_blocks = []
        for i, a in enumerate(top_analogues, 1):
            block = [
                f"CASO {i}: {a['star_id']} (rating={a['rating']}, similarità={a['similarity_score']})",
                f"  Tipo: {', '.join(a['variable_types']) or 'N/A'}",
                f"  Periodi discussi: {a['period_values'] or 'N/A'}",
                f"  Grafici: {', '.join(img['filename'] for img in a['images'][:4]) or 'nessuno'}",
            ]
            if a['expert_corrections']:
                block.append("  Correzioni Otero:")
                for c in a['expert_corrections'][:4]:
                    block.append(f"    - {c[:150]}")
            if a['best_expert_text']:
                block.append(f"  Email esperto:\n    {a['best_expert_text'][:600]}")
            analogues_context_blocks.append('\n'.join(block))

        prompt = f"""Sei un assistente esperto in astronomia delle stelle variabili e nel processo di submission al catalogo AAVSO VSX.

STELLA IN ANALISI:
{chr(10).join(f'- {s}' for s in stella_info)}

CASI PIÙ SIMILI GIÀ APPROVATI (rating >= {min_rating}):
{chr(10).join(analogues_context_blocks)}

Produci una guida strutturata con ESATTAMENTE queste 5 sezioni in italiano:

## 1. Caratteristiche Estratte dalla Stella in Analisi
(elenco puntato con parametri chiave e implicazioni astronomiche)

## 2. Casi Analoghi Approvati
Per ogni caso:
- **Star ID**:
- **Similarità**: (Alta/Media con motivazione tecnica)
- **Perché simile**: (ragionamento tecnico su periodo, tipo, ampiezza)
- **Insight chiave**:
- **Come è stato compilato il template**:

## 3. Template AAVSO Raccomandato
Guida sezione per sezione con suggerimenti di wording dove utile.

## 4. Indicazioni Otero Applicabili
(punti specifici dalle correzioni recuperate che si applicano a questo caso)

## 5. Rischi e Incertezze
(cosa va validato prima della submission, possibili errori)

Usa terminologia astronomica appropriata. Non inventare dati non presenti nel contesto."""

        guided_analysis = None
        try:
            from agata.moduli.variable_stars.services.llm_client import LLMClient
            llm = LLMClient()
            result = llm.generate(prompt, temperature=0.3, max_tokens=2000)
            guided_analysis = result.get('response_text')
        except Exception as llm_err:
            logger.warning(f"LLM error in kb_guided_analysis: {llm_err}")

        resp_analogues = []
        for a in top_analogues:
            resp_analogues.append({
                'star_id': a['star_id'],
                'rating': a['rating'],
                'variable_types': a['variable_types'],
                'similarity_score': a['similarity_score'],
                'period_values': a['period_values'],
                'expert_corrections': a['expert_corrections'],
                'images': a['images'],
                'messages_count': len(a['messages']),
                'has_expert': any(m['is_expert'] for m in a['messages']),
            })

        return jsonify({
            'success': True,
            'guided_analysis': guided_analysis,
            'analogues': resp_analogues,
            'queries_used': queries,
            'total_candidates': len(by_star),
            'min_rating_used': min_rating,
        }), 200

    except Exception as e:
        logger.error(f"Error in kb_guided_analysis: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        db.close()
