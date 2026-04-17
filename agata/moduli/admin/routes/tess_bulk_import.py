# agata/admin/routes/tess_bulk_import.py
"""
TESS Bulk Import Pipeline Routes

Gestione pipeline import massivo di curve di luce TESS QLP da curl script MAST:
- Lista job con form di upload curl script
- Dettaglio job con tabella risultati e promozione
- API JSON per UI dinamica (polling, creazione, eliminazione, promozione)
"""
import logging
import threading
from flask import render_template, jsonify, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import text
from sqlalchemy.orm import joinedload, defer

from agata.moduli.admin import admin_bp
from agata.moduli.admin.decorators import admin_required
from agata.db import SessionLocal
from agata.auth_models.tess_import_job import TessImportJob, TessImportResult

logger = logging.getLogger(__name__)

# Lazy-load service (evita errori di init se dipendenze mancanti)
_tess_bulk_import_service = None


def get_tess_bulk_import_service():
    global _tess_bulk_import_service
    if _tess_bulk_import_service is None:
        from agata.moduli.admin.services.tess_bulk_import_service import TessBulkImportService
        _tess_bulk_import_service = TessBulkImportService()
    return _tess_bulk_import_service


# =========================================================================
# UI PAGES
# =========================================================================

@admin_bp.route('/tess-bulk-import/jobs')
@login_required
@admin_required('admin')
def tess_bulk_import_jobs_page():
    """Pagina lista job TESS Bulk Import con form di upload curl script."""
    db = SessionLocal()
    try:
        query = db.query(TessImportJob).order_by(TessImportJob.created_at.desc())
        if current_user.role != 'superuser':
            query = query.filter(
                TessImportJob.association_id == current_user.association_id
            )
        jobs = query.limit(100).all()

        return render_template(
            'admin/tess_bulk_import/jobs.html',
            jobs=jobs,
            page_title='TESS Bulk Import'
        )
    except Exception as e:
        logger.error(f"Error loading TESS bulk import page: {e}", exc_info=True)
        return render_template('error.html', error=str(e)), 500
    finally:
        db.close()


@admin_bp.route('/tess-bulk-import/jobs/<int:job_id>')
@login_required
@admin_required('admin')
def tess_bulk_import_job_detail(job_id):
    """Pagina dettaglio job con tabella risultati, filtri e promozione."""
    db = SessionLocal()
    try:
        job = (
            db.query(TessImportJob)
            .options(joinedload(TessImportJob.creator))
            .filter(TessImportJob.id == job_id)
            .first()
        )
        if not job:
            flash(f'Job #{job_id} non trovato.', 'warning')
            return redirect(url_for('admin.tess_bulk_import_jobs_page'))

        if current_user.role != 'superuser':
            if job.association_id != current_user.association_id:
                flash('Accesso negato a questo job.', 'danger')
                return redirect(url_for('admin.tess_bulk_import_jobs_page'))

        # Carica results escludendo lc_full_json (~490KB/riga, non usato in UI)
        results = (
            db.query(TessImportResult)
            .filter(TessImportResult.job_id == job_id)
            .options(defer(TessImportResult.lc_full_json))
            .all()
        )

        # BATCH: controlla quali stelle sono già in agata_star
        star_gaia_ids = set()
        gaia_ids = [str(r.gaia_source_id) for r in results if r.gaia_source_id]
        if gaia_ids:
            placeholders = ','.join([f':gid{i}' for i in range(len(gaia_ids))])
            rows = db.execute(
                text(f"SELECT gaia_id FROM agata_star WHERE gaia_id IN ({placeholders})"),
                {f'gid{i}': gid for i, gid in enumerate(gaia_ids)}
            ).fetchall()
            star_gaia_ids = {str(row[0]) for row in rows}

        for result in results:
            result.in_agata_star = (
                str(result.gaia_source_id) in star_gaia_ids
                if result.gaia_source_id else False
            )
            result.is_promotable_cached = (
                result.is_valid
                and result.gaia_source_id is not None
                and not result.download_failed
                and result.lc_preview_json is not None
            )

        return render_template(
            'admin/tess_bulk_import/job_detail.html',
            job=job,
            results=results,
            page_title=f'TESS Import {job.job_code}'
        )
    except Exception as e:
        logger.error(f"Error loading TESS bulk import job detail {job_id}: {e}", exc_info=True)
        return render_template('error.html', error=str(e)), 500
    finally:
        db.close()


# =========================================================================
# API JSON
# =========================================================================

@admin_bp.route('/api/tess-bulk-import/jobs', methods=['POST'])
@login_required
@admin_required('admin')
def api_create_tess_bulk_import_job():
    """
    Crea nuovo job TESS bulk import e avvia pipeline in background thread.

    Supporta DUE path:

    PATH A (LEGACY - multipart/form-data):
        curl_script (file): Curl script MAST (.sh o .txt)
        job_name (str): Nome descrittivo
        files_selected (int): N file da elaborare
        selection_strategy (str): first_n o random_n
        min_observations (int): Min punti per curva valida (default 20)
        stetson_j_threshold (float): Soglia Stetson J (default 0.5)
        chi2_threshold (float): Soglia chi2 (default 3.0)

    PATH B (NEW - application/json, Script Library):
        {
            "script_id": int,
            "job_name": str,
            "files_selected": int (default 500),
            "min_observations": int (default 20),
            "stetson_j_threshold": float (default 0.5),
            "chi2_threshold": float (default 3.0)
        }

    Response:
        {success, job_id, job_code, files_selected, total_files_in_script}
    """

    # Scoping associazione (per entrambi i path)
    association_id = None
    if current_user.role != 'superuser':
        association_id = current_user.association_id

    # Detect path: JSON (new script library) vs multipart (legacy)
    if request.is_json:
        # PATH B: Script library path
        data = request.get_json() or {}

        script_id = data.get('script_id')
        if not script_id:
            return jsonify({'success': False, 'error': 'script_id mancante'}), 400

        job_name = data.get('job_name', '').strip()
        if not job_name:
            return jsonify({'success': False, 'error': 'Nome job obbligatorio'}), 400

        try:
            files_selected = int(data.get('files_selected', 500))
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'files_selected non valido'}), 400

        min_observations = int(data.get('min_observations', 20))
        stetson_j_threshold = float(data.get('stetson_j_threshold', 0.5))
        chi2_threshold = float(data.get('chi2_threshold', 3.0))

        # Get script_offset: use explicit value if provided, otherwise calculate
        if 'script_offset' in data and data.get('script_offset') is not None:
            script_offset = int(data.get('script_offset'))
        else:
            # Calculate script_offset: find max(script_offset + files_selected) from previous jobs
            db = SessionLocal()
            try:
                max_end_point = db.query(
                    func.max(TessImportJob.script_offset + TessImportJob.files_selected)
                ).filter(
                    TessImportJob.curl_script_id == script_id
                ).scalar()
                script_offset = max_end_point if max_end_point is not None else 0
            finally:
                db.close()

        try:
            svc = get_tess_bulk_import_service()
            job = svc.create_job(
                job_name=job_name,
                user_id=current_user.id,
                user_email=current_user.email,
                association_id=association_id,
                curl_script_id=script_id,
                script_offset=script_offset,
                files_selected=files_selected,
                min_observations=min_observations,
                stetson_j_threshold=stetson_j_threshold,
                chi2_threshold=chi2_threshold,
            )

            # Avvia pipeline in background thread
            thread = threading.Thread(
                target=svc.execute_job,
                args=(job.id,),
                daemon=True
            )
            thread.start()
            logger.info(f"Avviato thread background per TESS bulk import job {job.job_code} (script library path)")

            return jsonify({
                'success': True,
                'job_id': job.id,
                'job_code': job.job_code,
                'files_selected': job.files_selected,
                'total_files_in_script': job.total_files_in_script,
            }), 201

        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception as e:
            logger.error(f"Errore creazione TESS bulk import job (script path): {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    else:
        # PATH A: Legacy multipart/form-data path
        # Verifica file upload
        if 'curl_script' not in request.files:
            return jsonify({'success': False, 'error': 'File curl_script mancante'}), 400

        curl_file = request.files['curl_script']
        if not curl_file or curl_file.filename == '':
            return jsonify({'success': False, 'error': 'Nessun file selezionato'}), 400

        # Leggi contenuto del file
        try:
            curl_script_text = curl_file.read().decode('utf-8', errors='replace')
        except Exception as e:
            return jsonify({'success': False, 'error': f'Impossibile leggere il file: {e}'}), 400

        job_name = request.form.get('job_name', '').strip()
        if not job_name:
            return jsonify({'success': False, 'error': 'Nome job obbligatorio'}), 400

        try:
            files_selected = int(request.form.get('files_selected', 100))
        except (ValueError, TypeError) as e:
            return jsonify({'success': False, 'error': f'Valore numerico non valido: {e}'}), 400

        selection_strategy = request.form.get('selection_strategy', 'first_n')
        min_observations = int(request.form.get('min_observations', 20))
        stetson_j_threshold = float(request.form.get('stetson_j_threshold', 0.5))
        chi2_threshold = float(request.form.get('chi2_threshold', 3.0))

        try:
            svc = get_tess_bulk_import_service()
            job = svc.create_job(
                job_name=job_name,
                curl_script_text=curl_script_text,
                curl_script_filename=curl_file.filename,
                files_selected=files_selected,
                selection_strategy=selection_strategy,
                user_id=current_user.id,
                user_email=current_user.email,
                association_id=association_id,
                min_observations=min_observations,
                stetson_j_threshold=stetson_j_threshold,
                chi2_threshold=chi2_threshold,
            )

            # Avvia pipeline in background thread
            thread = threading.Thread(
                target=svc.execute_job,
                args=(job.id,),
                daemon=True
            )
            thread.start()
            logger.info(f"Avviato thread background per TESS bulk import job {job.job_code} (legacy multipart path)")

            return jsonify({
                'success': True,
                'job_id': job.id,
                'job_code': job.job_code,
                'files_selected': job.files_selected,
                'total_files_in_script': job.total_files_in_script,
            }), 201

        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception as e:
            logger.error(f"Errore creazione TESS bulk import job (legacy path): {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/tess-bulk-import/parse-script', methods=['POST'])
@login_required
@admin_required('admin')
def api_parse_tess_curl_script():
    """
    Preview del curl script: conta file, mostra prime 10 entry.
    Usato dalla UI per mostrare 'Found N files' prima di creare il job.

    Request: multipart/form-data con file curl_script
    Response: {total_files, first_entries: [{tic_id, sector, ...}]}
    """
    if 'curl_script' not in request.files:
        return jsonify({'success': False, 'error': 'File curl_script mancante'}), 400

    curl_file = request.files['curl_script']
    try:
        curl_script_text = curl_file.read().decode('utf-8', errors='replace')
    except Exception as e:
        return jsonify({'success': False, 'error': f'Impossibile leggere il file: {e}'}), 400

    from agata.moduli.admin.services.tess_bulk_import_service import _parse_curl_script
    entries = _parse_curl_script(curl_script_text)

    return jsonify({
        'success': True,
        'total_files': len(entries),
        'first_entries': [
            {'tic_id': e['tic_id'], 'sector': e['sector'], 'path': e['relative_path']}
            for e in entries[:10]
        ]
    }), 200


@admin_bp.route('/api/tess-bulk-import/jobs', methods=['GET'])
@login_required
@admin_required('admin')
def api_list_tess_bulk_import_jobs():
    """Elenca job TESS bulk import."""
    db = SessionLocal()
    try:
        query = db.query(TessImportJob).order_by(TessImportJob.created_at.desc()).limit(50)
        if current_user.role != 'superuser':
            query = query.filter(TessImportJob.association_id == current_user.association_id)
        jobs = query.all()

        return jsonify({
            'jobs': [
                {
                    'id': j.id,
                    'job_code': j.job_code,
                    'job_name': j.job_name,
                    'state': j.state,
                    'progress_pct': j.progress_pct,
                    'files_selected': j.files_selected,
                    'total_processed': j.total_processed,
                    'candidates_found': j.candidates_found,
                    'created_at': j.created_at.isoformat() if j.created_at else None,
                }
                for j in jobs
            ]
        }), 200
    except Exception as e:
        logger.error(f"Errore lista TESS bulk import jobs: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@admin_bp.route('/api/tess-bulk-import/jobs/<int:job_id>/previews', methods=['GET'])
@login_required
@admin_required('admin')
def api_get_tess_bulk_import_previews(job_id):
    """Restituisce lc_preview_json per una lista di result IDs (caricamento on-demand grafici)."""
    ids_param = request.args.get('ids', '')
    try:
        result_ids = [int(i) for i in ids_param.split(',') if i.strip().isdigit()]
    except ValueError:
        return jsonify({}), 200

    if not result_ids:
        return jsonify({}), 200

    db = SessionLocal()
    try:
        rows = (
            db.query(TessImportResult.id, TessImportResult.lc_preview_json)
            .filter(
                TessImportResult.job_id == job_id,
                TessImportResult.id.in_(result_ids)
            )
            .all()
        )
        return jsonify({str(row.id): row.lc_preview_json for row in rows if row.lc_preview_json}), 200
    except Exception as e:
        logger.error(f"Errore get previews TESS job {job_id}: {e}", exc_info=True)
        return jsonify({}), 500
    finally:
        db.close()


@admin_bp.route('/api/tess-bulk-import/jobs/<int:job_id>', methods=['GET'])
@login_required
@admin_required('admin')
def api_get_tess_bulk_import_job(job_id):
    """Stato job per polling UI (ogni 5s)."""
    db = SessionLocal()
    try:
        job = db.query(TessImportJob).get(job_id)
        if not job:
            return jsonify({'error': 'Job non trovato'}), 404

        if current_user.role != 'superuser':
            if job.association_id != current_user.association_id:
                return jsonify({'error': 'Accesso negato'}), 403

        response = {
            'id': job.id,
            'job_code': job.job_code,
            'job_name': job.job_name,
            'state': job.state,
            'progress_pct': job.progress_pct,
            'current_step': job.current_step,
            'error_message': job.error_message,
            'is_running': job.is_running,
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'duration_seconds': job.duration_seconds,
            'promoted_count': job.promoted_count,
        }

        # If job is completed, read metrics from cagg (faster + fresh)
        if job.state == 'completed':
            try:
                metrics = db.session.execute(text("""
                    SELECT n_total, n_candidates, n_known_vars, n_gaia_matched,
                           mean_stetson_j, mean_chi_squared
                    FROM tess_job_summary
                    WHERE job_id = :job_id
                """), {'job_id': job_id}).first()

                if metrics:
                    response.update({
                        'total_processed': metrics[0],
                        'candidates_found': metrics[1],
                        'known_variables_found': metrics[2],
                        'gaia_matched': metrics[3],
                        'mean_stetson_j': float(metrics[4]) if metrics[4] else None,
                        'mean_chi_squared': float(metrics[5]) if metrics[5] else None,
                    })
                else:
                    # Fallback to job row if cagg not ready
                    response.update({
                        'total_processed': job.total_processed,
                        'candidates_found': job.candidates_found,
                        'known_variables_found': job.known_variables_found,
                        'total_failed_downloads': job.total_failed_downloads,
                    })
            except Exception as e:
                logger.warning(f"Could not read tess_job_summary cagg: {e}")
                # Fallback: always read job row as backup
                response.update({
                    'total_processed': job.total_processed,
                    'candidates_found': job.candidates_found,
                    'known_variables_found': job.known_variables_found,
                    'total_failed_downloads': job.total_failed_downloads,
                })
        else:
            # Job still running: read from job row (always up-to-date)
            response.update({
                'total_processed': job.total_processed,
                'candidates_found': job.candidates_found,
                'known_variables_found': job.known_variables_found,
                'total_failed_downloads': job.total_failed_downloads,
            })

        return jsonify(response), 200
    except Exception as e:
        logger.error(f"Errore get TESS bulk import job {job_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@admin_bp.route('/api/tess-bulk-import/jobs/<int:job_id>', methods=['DELETE'])
@login_required
@admin_required('admin')
def api_delete_tess_bulk_import_job(job_id):
    """Elimina job e tutti i suoi risultati (CASCADE)."""
    db = SessionLocal()
    try:
        job = db.query(TessImportJob).get(job_id)
        if not job:
            return jsonify({'error': 'Job non trovato'}), 404
        if job.is_running:
            return jsonify({'error': 'Impossibile eliminare un job in corso'}), 400
        if current_user.role != 'superuser':
            if job.association_id != current_user.association_id:
                return jsonify({'error': 'Accesso negato'}), 403
    finally:
        db.close()

    try:
        svc = get_tess_bulk_import_service()
        svc.delete_job(job_id, current_user.id, current_user.email)
        return jsonify({'success': True, 'message': 'Job eliminato'}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Errore eliminazione TESS bulk import job {job_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/tess-bulk-import/jobs/<int:job_id>/resume', methods=['POST'])
@login_required
@admin_required('admin')
def api_resume_tess_bulk_import_job(job_id):
    """
    Riprende un job failed o bloccato, saltando i file già elaborati.

    Response: {success, job_id, job_code, message}
    """
    db = SessionLocal()
    try:
        job = db.query(TessImportJob).get(job_id)
        if not job:
            return jsonify({'success': False, 'error': 'Job non trovato'}), 404
        if current_user.role != 'superuser' and job.association_id != current_user.association_id:
            return jsonify({'success': False, 'error': 'Accesso negato'}), 403
        if job.is_running:
            return jsonify({'success': False, 'error': 'Il job è già in esecuzione'}), 400
    finally:
        db.close()

    try:
        svc = get_tess_bulk_import_service()
        job = svc.resume_job(
            job_id=job_id,
            user_id=current_user.id,
            user_email=current_user.email
        )

        thread = threading.Thread(
            target=svc.execute_job,
            args=(job.id,),
            daemon=True
        )
        thread.start()
        logger.info(f"Avviato thread resume per TESS bulk import job {job.job_code}")

        return jsonify({
            'success': True,
            'job_id': job.id,
            'job_code': job.job_code,
            'message': f'Job {job.job_code} ripreso in background',
        }), 200

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Errore resume TESS bulk import job {job_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500



# =========================================================================
# SCRIPT LIBRARY API ENDPOINTS (NEW)
# =========================================================================

@admin_bp.route('/api/tess-bulk-import/scripts', methods=['POST'])
@login_required
@admin_required('admin')
def api_upload_tess_curl_script():
    """
    Upload a new MAST curl script and start background parsing.

    Returns immediately with script_id; parsing happens asynchronously.

    Request: multipart/form-data
        curl_script (file): .sh or .txt file
        job_name_hint (str, optional): descriptive hint

    Response (201):
        {script_id, script_code, parse_state: 'uploading'}
    """
    from agata.moduli.admin.services.tess_curl_script_service import upload_and_create_script

    if 'curl_script' not in request.files:
        return jsonify({'error': 'No curl_script file provided'}), 400

    curl_file = request.files['curl_script']
    if not curl_file or curl_file.filename == '':
        return jsonify({'error': 'Empty file'}), 400

    try:
        script = upload_and_create_script(
            file_storage=curl_file,
            user_id=current_user.id,
            association_id=current_user.association_id if current_user.role != 'superuser' else None,
            job_name_hint=request.form.get('job_name_hint')
        )

        return jsonify({
            'script_id': script.id,
            'script_code': script.script_code,
            'parse_state': script.parse_state,
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Upload curl script failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/tess-bulk-import/scripts', methods=['GET'])
@login_required
@admin_required('admin')
def api_list_tess_curl_scripts():
    """
    List MAST curl scripts visible to the current user.

    Returns:
        {scripts: [{id, script_code, parse_state, total_entries, entries_processed, ...}]}
    """
    from agata.moduli.admin.services.tess_curl_script_service import list_scripts

    try:
        is_superuser = current_user.role == 'superuser'
        scripts = list_scripts(
            association_id=current_user.association_id if not is_superuser else None,
            is_superuser=is_superuser
        )

        return jsonify({'scripts': scripts}), 200

    except Exception as e:
        logger.error(f"List curl scripts failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/tess-bulk-import/scripts/<int:script_id>/status', methods=['GET'])
@login_required
@admin_required('admin')
def api_get_tess_curl_script_status(script_id):
    """
    Poll parse status of a curl script.

    Used during upload modal to show parse progress.

    Returns:
        {script_code, parse_state, total_entries, entries_processed, batches_remaining, parse_error (if failed)}
    """
    from agata.moduli.admin.services.tess_curl_script_service import get_script_status
    from agata.auth_models import TessCurlScript

    try:
        # Verify user has access to this script
        db = SessionLocal()
        try:
            script = db.query(TessCurlScript).get(script_id)
            if not script:
                return jsonify({'error': 'Script not found'}), 404
            if current_user.role != 'superuser' and script.association_id != current_user.association_id:
                return jsonify({'error': 'Access denied'}), 403
        finally:
            db.close()

        status = get_script_status(script_id)
        return jsonify(status), 200

    except Exception as e:
        logger.error(f"Get script status failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/tess-bulk-import/scripts/<int:script_id>/next-batch', methods=['GET'])
@login_required
@admin_required('admin')
def api_get_next_batch_suggestion(script_id):
    """
    Get suggested offset and preview of next batch from a script.

    Intelligently calculates offset as: last_record_from_other_jobs + 1
    This ensures continuous non-overlapping batches.

    Used when user clicks "Create Next Batch" button.

    Query params:
        batch_size: int (default 500, max 500)

    Returns:
        {offset, count, entries: [{tic_id, sector, relative_path, ...}], first 10 only for preview}
    """
    from agata.moduli.admin.services.tess_curl_script_service import get_script_status, get_next_batch
    from agata.auth_models import TessCurlScript, TessImportJob
    from sqlalchemy import func

    try:
        # Verify access
        db = SessionLocal()
        try:
            script = db.query(TessCurlScript).get(script_id)
            if not script:
                return jsonify({'error': 'Script not found'}), 404
            if current_user.role != 'superuser' and script.association_id != current_user.association_id:
                return jsonify({'error': 'Access denied'}), 403

            # Calculate next offset: find job with highest (script_offset + files_selected)
            # This is the furthest point reached across all jobs
            max_end_point = db.query(
                func.max(TessImportJob.script_offset + TessImportJob.files_selected)
            ).filter(
                TessImportJob.curl_script_id == script_id
            ).scalar()

            # If no previous jobs, start from 0. Otherwise use the highest endpoint
            suggested_offset = max_end_point if max_end_point is not None else 0

        finally:
            db.close()

        batch_size = int(request.args.get('batch_size', 500))
        batch_size = min(batch_size, 500)  # Max 500

        # Get entries starting from suggested offset
        entries = get_next_batch(script_id, batch_size=batch_size, offset=suggested_offset)

        # Return offset from calculation + preview (first 10 entries)
        status = get_script_status(script_id)

        return jsonify({
            'offset': suggested_offset,
            'count': len(entries),
            'total_remaining': status['total_entries'] - suggested_offset,
            'preview': entries[:10]  # Only first 10 for UI preview
        }), 200

    except Exception as e:
        logger.error(f"Get next batch suggestion failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/tess-bulk-import/scripts/<int:script_id>', methods=['DELETE'])
@login_required
@admin_required('admin')
def api_delete_tess_curl_script(script_id):
    """
    Delete a curl script and all its entries.

    Blocked if any associated jobs are running.

    Returns:
        {success: true} or {error: '...'}
    """
    from agata.moduli.admin.services.tess_curl_script_service import delete_script
    from agata.auth_models import TessCurlScript

    try:
        # Verify access
        db = SessionLocal()
        try:
            script = db.query(TessCurlScript).get(script_id)
            if not script:
                return jsonify({'error': 'Script not found'}), 404
            if current_user.role != 'superuser' and script.association_id != current_user.association_id:
                return jsonify({'error': 'Access denied'}), 403
        finally:
            db.close()

        delete_script(script_id, check_running=True)
        return jsonify({'success': True}), 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Delete curl script failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/tess-bulk-import/jobs/<int:job_id>/promote', methods=['POST'])
@login_required
@admin_required('admin')
def api_promote_tess_bulk_import_job(job_id):
    """
    Promuove risultati TESS validati in agata_star_photometry.

    Body JSON (opzionali):
        result_ids: list[int] — se specificato, promuove solo questi IDs
        exclude_known_variables: bool — esclude variabili note (VSX o Gaia)

    Response:
        {success, stats: {promoted, lightcurve_points, import_id, ...}}
    """
    data = request.get_json() or {}

    # Scoping
    db = SessionLocal()
    try:
        job = db.query(TessImportJob).get(job_id)
        if not job:
            return jsonify({'success': False, 'error': 'Job non trovato'}), 404
        if current_user.role != 'superuser' and job.association_id != current_user.association_id:
            return jsonify({'success': False, 'error': 'Accesso negato'}), 403
    finally:
        db.close()

    try:
        svc = get_tess_bulk_import_service()
        stats = svc.promote_job_results(
            job_id=job_id,
            user_id=current_user.id,
            user_email=current_user.email,
            result_ids=data.get('result_ids'),
            exclude_known_variables=bool(data.get('exclude_known_variables', False))
        )

        catalog_link = None
        if stats.get('import_id'):
            catalog_link = f'/agata/admin/stars-catalog?adv_filters=import_id%3Aequals%3A{stats["import_id"]}'

        return jsonify({
            'success': True,
            'stats': stats,
            'catalog_link': catalog_link
        }), 200

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Promozione TESS bulk import job {job_id} fallita: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/tess-bulk-import/results/<int:result_id>/reject', methods=['POST'])
@login_required
@admin_required('admin')
def api_tess_bulk_import_result_reject(result_id):
    """Toggle is_rejected su un risultato TESS Bulk Import."""
    db = SessionLocal()
    try:
        db.rollback()  # Pulisci stato transazione in caso di errore precedente
        result = db.query(TessImportResult).get(result_id)
        if not result:
            return jsonify({'error': 'Risultato non trovato'}), 404
        job = db.query(TessImportJob).get(result.job_id)
        if current_user.role != 'superuser' and job.association_id != current_user.association_id:
            return jsonify({'error': 'Accesso negato'}), 403
        result.is_rejected = not result.is_rejected
        db.commit()
        return jsonify({'success': True, 'is_rejected': result.is_rejected})
    except Exception as e:
        db.rollback()
        logger.error(f"Errore api_tess_bulk_import_result_reject: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()
