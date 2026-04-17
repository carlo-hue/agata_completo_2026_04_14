# agata/admin/routes/ztf_survey.py
"""
ZTF Field Survey Pipeline Routes

Gestione pipeline di survey fotometrico ZTF su area di cielo:
- Lista job con form di creazione
- Dettaglio job con risultati e promozione
- API JSON per UI dinamica
"""
import logging
import threading
from flask import render_template, jsonify, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import text

from agata.moduli.admin import admin_bp
from agata.moduli.admin.decorators import admin_required
from agata.db import SessionLocal, get_clean_session
from agata.auth_models.ztf_survey_job import ZtfSurveyJob, ZtfSurveyResult

logger = logging.getLogger(__name__)

# Lazy-load service (evita errori di init se dipendenze mancanti)
_ztf_survey_service = None


def get_ztf_survey_service():
    global _ztf_survey_service
    if _ztf_survey_service is None:
        from agata.moduli.admin.services.ztf_survey_service import ZtfSurveyService
        _ztf_survey_service = ZtfSurveyService()
    return _ztf_survey_service


# =========================================================================
# UI PAGES
# =========================================================================

@admin_bp.route('/ztf-survey/jobs')
@login_required
@admin_required('admin')
def ztf_survey_jobs_page():
    """Pagina lista job ZTF Survey con form di creazione."""
    db = SessionLocal()
    try:
        query = db.query(ZtfSurveyJob).order_by(ZtfSurveyJob.created_at.desc())
        # Scoping per associazione (admin vede solo i propri)
        if current_user.role != 'superuser':
            query = query.filter(
                ZtfSurveyJob.association_id == current_user.association_id
            )
        jobs = query.limit(100).all()

        return render_template(
            'admin/ztf_survey/jobs.html',
            jobs=jobs,
            page_title='ZTF Field Survey Pipeline'
        )
    except Exception as e:
        logger.error(f"Error loading ZTF survey page: {e}", exc_info=True)
        return render_template('error.html', error=str(e)), 500
    finally:
        db.close()


@admin_bp.route('/ztf-survey/jobs/<int:job_id>')
@login_required
@admin_required('admin')
def ztf_survey_job_detail(job_id):
    """Pagina dettaglio job con tabella risultati e promozione."""
    db = SessionLocal()
    try:
        job = db.query(ZtfSurveyJob).get(job_id)
        if not job:
            flash(f'Job #{job_id} non trovato.', 'warning')
            return redirect(url_for('admin.ztf_survey_jobs_page'))

        # Scoping associazione
        if current_user.role != 'superuser':
            if job.association_id != current_user.association_id:
                flash('Accesso negato a questo job.', 'danger')
                return redirect(url_for('admin.ztf_survey_jobs_page'))

        # BATCH: controlla quali stelle sono già in agata_star
        star_gaia_ids = set()
        if job.results:
            gaia_ids = [str(r.gaia_source_id) for r in job.results if r.gaia_source_id]
            if gaia_ids:
                placeholders = ','.join([f':gid{i}' for i in range(len(gaia_ids))])
                rows = db.execute(
                    text(f"SELECT gaia_id FROM agata_star WHERE gaia_id IN ({placeholders})"),
                    {f'gid{i}': gid for i, gid in enumerate(gaia_ids)}
                ).fetchall()
                star_gaia_ids = {str(row[0]) for row in rows}

        for result in job.results:
            result.in_agata_star = (
                str(result.gaia_source_id) in star_gaia_ids
                if result.gaia_source_id else False
            )

        return render_template(
            'admin/ztf_survey/job_detail.html',
            job=job,
            page_title=f'ZTF Survey Job {job.job_code}'
        )
    except Exception as e:
        logger.error(f"Error loading ZTF survey job detail: {e}", exc_info=True)
        return render_template('error.html', error=str(e)), 500
    finally:
        db.close()


# =========================================================================
# API JSON
# =========================================================================

@admin_bp.route('/api/ztf-survey/jobs', methods=['POST'])
@login_required
@admin_required('admin')
def api_create_ztf_survey_job():
    """
    Crea nuovo job ZTF survey e avvia pipeline in background thread.

    Request JSON:
        target_name (str): Nome descrittivo del campo
        ra_center (float): RA centro campo (gradi)
        dec_center (float): Dec centro campo (gradi, deve essere > -30)
        radius_deg (float): Raggio ricerca (0.01 - 3.0 gradi)
        ztf_filter (str): Filtro ZTF: g, r, i (default: r)
        mag_min (float, opzionale): Limite mag brillante
        mag_max (float, opzionale): Limite mag debole
        min_observations (int): Min punti fotometrici per sorgente (default: 20)

    Response:
        {success, job_id, job_code}
    """
    data = request.get_json() or {}

    # Validazioni base
    required_fields = ['target_name', 'ra_center', 'dec_center', 'radius_deg']
    for field in required_fields:
        if field not in data:
            return jsonify({'success': False, 'error': f'Campo obbligatorio mancante: {field}'}), 400

    try:
        ra_center = float(data['ra_center'])
        dec_center = float(data['dec_center'])
        radius_deg = float(data['radius_deg'])
        ztf_filter = data.get('ztf_filter', 'r')
        mag_min = float(data['mag_min']) if data.get('mag_min') is not None else None
        mag_max = float(data['mag_max']) if data.get('mag_max') is not None else None
        min_observations = int(data.get('min_observations', 20))
    except (ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': f'Valore non valido: {e}'}), 400

    # Scoping associazione
    association_id = None
    if current_user.role != 'superuser':
        association_id = current_user.association_id

    try:
        svc = get_ztf_survey_service()
        job = svc.create_job(
            target_name=data['target_name'],
            ra_center=ra_center,
            dec_center=dec_center,
            radius_deg=radius_deg,
            ztf_filter=ztf_filter,
            mag_min=mag_min,
            mag_max=mag_max,
            min_observations=min_observations,
            user_id=current_user.id,
            user_email=current_user.email,
            association_id=association_id
        )

        # Avvia pipeline in background thread (stesso pattern VAST)
        thread = threading.Thread(
            target=svc.execute_job,
            args=(job.id,),
            daemon=True
        )
        thread.start()
        logger.info(f"Avviato thread background per ZTF survey job {job.job_code}")

        return jsonify({
            'success': True,
            'job_id': job.id,
            'job_code': job.job_code
        }), 201

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Errore creazione ZTF survey job: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/ztf-survey/jobs', methods=['GET'])
@login_required
@admin_required('admin')
def api_list_ztf_survey_jobs():
    """Elenca job ZTF survey (con filtro state opzionale)."""
    try:
        state = request.args.get('state')
        limit = int(request.args.get('limit', 50))

        # Scoping
        association_id = None if current_user.role == 'superuser' else current_user.association_id

        svc = get_ztf_survey_service()
        jobs = svc.list_jobs(limit=limit, state=state, association_id=association_id)

        return jsonify({
            'jobs': [
                {
                    'id': j.id,
                    'job_code': j.job_code,
                    'target_name': j.target_name,
                    'state': j.state,
                    'progress_pct': j.progress_pct,
                    'current_step': j.current_step,
                    'total_sources': j.total_sources,
                    'candidates_found': j.candidates_found,
                    'created_at': j.created_at.isoformat() if j.created_at else None,
                }
                for j in jobs
            ]
        }), 200
    except Exception as e:
        logger.error(f"Errore lista ZTF survey jobs: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/ztf-survey/jobs/<int:job_id>', methods=['GET'])
@login_required
@admin_required('admin')
def api_get_ztf_survey_job(job_id):
    """Stato job (per polling). Ritorna info aggiornate ogni 5s."""
    db = get_clean_session()
    try:
        job = db.query(ZtfSurveyJob).get(job_id)
        if not job:
            return jsonify({'error': 'Job non trovato'}), 404

        # Scoping
        if current_user.role != 'superuser':
            if job.association_id != current_user.association_id:
                return jsonify({'error': 'Accesso negato'}), 403

        response = {
            'id': job.id,
            'job_code': job.job_code,
            'target_name': job.target_name,
            'state': job.state,
            'progress_pct': job.progress_pct,
            'current_step': job.current_step,
            'error_message': job.error_message,
            'total_sources': job.total_sources,
            'promoted_count': job.promoted_count,
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'duration_seconds': job.duration_seconds,
        }

        # If job is completed, read metrics from cagg (faster + fresh)
        if job.state == 'completed':
            try:
                metrics = db.session.execute(text("""
                    SELECT n_total, n_candidates, n_known_vars, n_gaia_matched,
                           mean_stetson_j, mean_chi_squared
                    FROM ztf_job_summary
                    WHERE job_id = :job_id
                """), {'job_id': job_id}).first()

                if metrics:
                    response.update({
                        'candidates_found': metrics[1],
                        'known_variables_found': metrics[2],
                        'gaia_matched': metrics[3],
                        'mean_stetson_j': float(metrics[4]) if metrics[4] else None,
                        'mean_chi_squared': float(metrics[5]) if metrics[5] else None,
                    })
                else:
                    # Fallback to job row if cagg not ready
                    response.update({
                        'candidates_found': job.candidates_found,
                        'known_variables_found': job.known_variables_found,
                    })
            except Exception as e:
                logger.warning(f"Could not read ztf_job_summary cagg: {e}")
                response.update({
                    'candidates_found': job.candidates_found,
                    'known_variables_found': job.known_variables_found,
                })
        else:
            response.update({
                'candidates_found': job.candidates_found,
                'known_variables_found': job.known_variables_found,
            })

        return jsonify(response), 200
    except Exception as e:
        db.rollback()
        logger.error(f"Errore get ZTF survey job {job_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@admin_bp.route('/api/ztf-survey/jobs/<int:job_id>', methods=['DELETE'])
@login_required
@admin_required('admin')
def api_delete_ztf_survey_job(job_id):
    """Elimina job e tutti i suoi risultati."""
    db = SessionLocal()
    try:
        job = db.query(ZtfSurveyJob).get(job_id)
        if not job:
            return jsonify({'error': 'Job non trovato'}), 404

        if job.is_running:
            return jsonify({'error': 'Impossibile eliminare un job in corso'}), 400

        # Scoping
        if current_user.role != 'superuser':
            if job.association_id != current_user.association_id:
                return jsonify({'error': 'Accesso negato'}), 403
    finally:
        db.close()

    try:
        svc = get_ztf_survey_service()
        result = svc.delete_job(job_id, current_user.id, current_user.email)

        return jsonify({
            'success': True,
            'message': f"Job eliminato. {result['results_deleted']} risultati cancellati.",
            **result
        }), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Errore eliminazione ZTF survey job {job_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/ztf-survey/jobs/<int:job_id>/promote', methods=['POST'])
@login_required
@admin_required('admin')
def api_promote_ztf_survey_job(job_id):
    """
    Avvia promozione in background thread.
    Risponde subito con {success, status: 'started'}.
    Usa /promote/status per monitorare il progresso.
    """
    data = request.get_json() or {}

    db = SessionLocal()
    try:
        job = db.query(ZtfSurveyJob).get(job_id)
        if not job:
            return jsonify({'success': False, 'error': 'Job non trovato'}), 404
        if current_user.role != 'superuser' and job.association_id != current_user.association_id:
            return jsonify({'success': False, 'error': 'Accesso negato'}), 403
        # Evita promozioni parallele (con timeout anti-stale: se running da >15min, permetti rilancio)
        import time as _time
        promo = job.output_data.get('promotion', {}) if job.output_data else {}
        if promo.get('state') == 'running':
            started_at = promo.get('started_at', 0)
            if _time.time() - started_at < 900:  # 15 minuti
                return jsonify({'success': False, 'error': 'Promozione già in corso'}), 400
            logger.warning(f"Job {job_id}: promozione in stato running da >15min, considero stale e rilancio")
    finally:
        db.close()

    user_id = current_user.id
    user_email = current_user.email

    # Log what the UI is sending
    result_ids = data.get('result_ids')
    logger.info(f"[ztf_promote] Received data: result_ids type={type(result_ids)}, len={len(result_ids) if result_ids else 'None'}, first 5={result_ids[:5] if result_ids and len(result_ids) > 0 else 'empty'}")

    svc = get_ztf_survey_service()
    thread = threading.Thread(
        target=svc.promote_job_results,
        args=(job_id,),
        kwargs={
            'user_id': user_id,
            'user_email': user_email,
            'result_ids': result_ids,
            'exclude_known_variables': bool(data.get('exclude_known_variables', False)),
            'exclude_in_agata': bool(data.get('exclude_in_agata', False)),
        },
        daemon=True
    )
    thread.start()
    logger.info(f"Avviato thread promozione per ZTF survey job {job_id}")

    return jsonify({'success': True, 'status': 'started'}), 202


@admin_bp.route('/api/ztf-survey/jobs/<int:job_id>/promote/status', methods=['GET'])
@login_required
@admin_required('admin')
def api_promote_ztf_survey_status(job_id):
    """Stato promozione corrente (polling). Legge output_data['promotion']."""
    db = get_clean_session()
    try:
        job = db.query(ZtfSurveyJob).get(job_id)
        if not job:
            return jsonify({'error': 'Job non trovato'}), 404
        if current_user.role != 'superuser' and job.association_id != current_user.association_id:
            return jsonify({'error': 'Accesso negato'}), 403

        promo = job.output_data.get('promotion', {}) if job.output_data else {}
        import_id = promo.get('import_id')
        return jsonify({
            'state': promo.get('state', 'idle'),
            'promoted': promo.get('promoted', 0),
            'total': promo.get('total', 0),
            'lightcurve_points': promo.get('lightcurve_points', 0),
            'errors': promo.get('errors', []),
            'import_id': import_id,
            'catalog_link': f'/agata/admin/stars-catalog?adv_filters=import_id%3Aequals%3A{import_id}' if import_id else None,
        }), 200
    except Exception as e:
        db.rollback()
        logger.error(f"Errore promote status ZTF survey job {job_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@admin_bp.route('/api/ztf-survey/results/<int:result_id>/reject', methods=['POST'])
@login_required
@admin_required('admin')
def api_ztf_survey_result_reject(result_id):
    """Toggle is_rejected su un risultato ZTF Survey."""
    db = SessionLocal()
    try:
        db.rollback()  # Pulisci stato transazione in caso di errore precedente
        result = db.query(ZtfSurveyResult).get(result_id)
        if not result:
            return jsonify({'error': 'Risultato non trovato'}), 404
        job = db.query(ZtfSurveyJob).get(result.job_id)
        if current_user.role != 'superuser' and job.association_id != current_user.association_id:
            return jsonify({'error': 'Accesso negato'}), 403
        result.is_rejected = not result.is_rejected
        db.commit()
        return jsonify({'success': True, 'is_rejected': result.is_rejected})
    except Exception as e:
        db.rollback()
        logger.error(f"Errore api_ztf_survey_result_reject: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@admin_bp.route('/api/ztf-survey/results/<int:result_id>/lightcurve', methods=['GET'])
@login_required
@admin_required('admin')
def api_ztf_survey_result_lightcurve(result_id):
    """
    Proxy IRSA: fetcha la curva di luce per una singola sorgente ZTF.
    Usa nph_light_curves?ID=<ztf_object_id> (stabile, ~4s).
    Risponde con {hjd: [...], mag: [...], magerr: [...]}.
    """
    import requests as _req
    import io as _io
    import pandas as _pd

    db = SessionLocal()
    try:
        result = db.query(ZtfSurveyResult).get(result_id)
        if not result:
            return jsonify({'error': 'Risultato non trovato'}), 404
        job = db.query(ZtfSurveyJob).get(result.job_id)
        if not job:
            return jsonify({'error': 'Job non trovato'}), 404
        if current_user.role != 'superuser' and job.association_id != current_user.association_id:
            return jsonify({'error': 'Accesso negato'}), 403
        ztf_oid = result.ztf_object_id
        ztf_filter = job.ztf_filter
    finally:
        db.close()

    if not ztf_oid:
        return jsonify({'error': 'ZTF object ID non disponibile'}), 400

    try:
        resp = _req.get(
            'https://irsa.ipac.caltech.edu/cgi-bin/ZTF/nph_light_curves',
            params={'ID': str(ztf_oid), 'FORMAT': 'csv', 'BAD_CATFLAGS_MASK': '32768'},
            timeout=30
        )
        resp.raise_for_status()
        lines = [l for l in resp.text.splitlines() if not l.startswith('\\')]
        if not lines:
            return jsonify({'error': 'Nessun dato IRSA'}), 404
        df = _pd.read_csv(_io.StringIO('\n'.join(lines)))
        filtercode = {'g': 'zg', 'r': 'zr', 'i': 'zi'}.get(ztf_filter, 'zr')
        if 'filtercode' in df.columns:
            df = df[df['filtercode'] == filtercode]
        if 'catflags' in df.columns:
            df = df[df['catflags'] == 0]
        df = df.dropna(subset=['mag']).sort_values('hjd' if 'hjd' in df.columns else df.columns[0])
        if df.empty:
            return jsonify({'error': 'Nessun punto valido'}), 404
        return jsonify({
            'hjd': df['hjd'].tolist() if 'hjd' in df.columns else [],
            'mag': df['mag'].tolist(),
            'magerr': df['magerr'].tolist() if 'magerr' in df.columns else [],
        }), 200
    except Exception as e:
        logger.error(f"Lightcurve fetch failed for result {result_id}: {e}")
        return jsonify({'error': str(e)}), 500
