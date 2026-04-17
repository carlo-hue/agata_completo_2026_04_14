# agata/admin/routes/vast_automation.py
"""
VAST Automation Routes (Superuser Only)
"""
import logging
import threading
from flask import render_template, jsonify, request, redirect, url_for, flash
from flask_login import login_required, current_user

from agata.moduli.admin import admin_bp
from agata.moduli.admin.decorators import superuser_required, audit_action
from agata.db import SessionLocal
from agata.auth_models import VastJob, Association

logger = logging.getLogger(__name__)

# Lazy-load service (avoid initialization errors if files missing)
_vast_service = None

def get_vast_service():
    global _vast_service
    if _vast_service is None:
        from agata.moduli.admin.services.vast_service import VastService
        _vast_service = VastService()
    return _vast_service


@admin_bp.route('/vast')
@login_required
@superuser_required
def vast_automation_page():
    """Pagina gestione job VAST."""
    db = SessionLocal()

    try:
        # Carica job recenti
        jobs = db.query(VastJob).order_by(VastJob.created_at.desc()).limit(50).all()

        return render_template(
            'admin/vast/jobs.html',
            jobs=jobs,
            page_title='VAST Automation'
        )
    except Exception as e:
        logger.error(f"Error loading VAST page: {e}", exc_info=True)
        return render_template('error.html', error=str(e)), 500
    finally:
        db.close()


@admin_bp.route('/api/vast/jobs', methods=['POST'])
@login_required
@superuser_required
@audit_action('vast_job_created', 'vast_job')
def api_create_vast_job():
    """Crea nuovo job VAST."""
    data = request.json

    try:
        # Validazione input
        if not data.get('target_name'):
            return jsonify({'success': False, 'error': 'target_name is required'}), 400
        if not data.get('source_type'):
            return jsonify({'success': False, 'error': 'source_type is required'}), 400
        if not data.get('source_location'):
            return jsonify({'success': False, 'error': 'source_location is required'}), 400

        # Crea job
        vast_service = get_vast_service()
        job = vast_service.create_job(
            target_name=data['target_name'],
            source_type=data['source_type'],
            source_location=data['source_location'],
            processing_params=data.get('processing_params', {}),
            user_id=current_user.id,
            user_email=current_user.email
        )

        # Avvia job in background thread
        thread = threading.Thread(
            target=vast_service.execute_job,
            args=(job.id,),
            daemon=True
        )
        thread.start()
        logger.info(f"Started background thread for job {job.job_code}")

        return jsonify({
            'success': True,
            'job_id': job.id,
            'job_code': job.job_code
        }), 201

    except Exception as e:
        logger.error(f"Failed to create VAST job: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@admin_bp.route('/api/vast/jobs/<int:job_id>')
@login_required
@superuser_required
def api_get_vast_job(job_id):
    """Get job status (per polling)."""
    try:
        vast_service = get_vast_service()
        status = vast_service.get_job_status(job_id)
        return jsonify(status), 200
    except ValueError:
        return jsonify({'error': 'Job not found'}), 404
    except Exception as e:
        logger.error(f"Error getting job status: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/vast/jobs')
@login_required
@superuser_required
def api_list_vast_jobs():
    """Elenca job VAST."""
    try:
        state = request.args.get('state')
        limit = int(request.args.get('limit', 50))

        vast_service = get_vast_service()
        jobs = vast_service.list_jobs(limit=limit, state=state)
        return jsonify({'jobs': jobs}), 200

    except Exception as e:
        logger.error(f"Error listing VAST jobs: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/vast/analysis-folders')
@login_required
@superuser_required
def api_list_analysis_folders():
    """Elenca sottocartelle analisi da VAST_DRIVE_FOLDER_ID in .env"""
    try:
        import os
        from agata.moduli.admin.services.google_drive_service import GoogleDriveService

        # Leggi folder ID da .env
        parent_folder_id = os.getenv('VAST_DRIVE_FOLDER_ID')
        if not parent_folder_id:
            return jsonify({
                'success': False,
                'error': 'VAST_DRIVE_FOLDER_ID not configured in .env'
            }), 400

        drive_service = GoogleDriveService()
        subfolders = drive_service.list_subfolders(parent_folder_id=parent_folder_id)

        logger.info(f"Listing {len(subfolders)} analysis folders in {parent_folder_id}")

        return jsonify({
            'success': True,
            'subfolders': subfolders
        }), 200

    except Exception as e:
        logger.error(f"Error listing analysis folders: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_bp.route('/vast/jobs/<int:job_id>')
@login_required
@superuser_required
def vast_job_detail(job_id):
    """Pagina dettaglio job con risultati."""
    db = SessionLocal()

    try:
        job = db.query(VastJob).get(job_id)
        if not job:
            flash(f'Job #{job_id} non trovato.', 'warning')
            return redirect(url_for('admin.vast_automation_page'))

        # Carica associazioni attive per la promozione
        associations = db.query(Association).filter(
            Association.is_active == True
        ).order_by(Association.name).all()

        # Verifica se il job è già stato promosso
        is_promoted = bool(
            job.output_files
            and job.output_files.get('promotion')
        )

        # BATCH: Check which stars are already in agata_star (for badge display)
        # This is a single query that loads all gaia_ids at once
        star_gaia_ids = set()
        if job.results:
            gaia_ids_to_check = [
                str(r.gaia_source_id) for r in job.results
                if r.gaia_source_id
            ]
            if gaia_ids_to_check:
                from sqlalchemy import text
                rows = db.execute(
                    text(f"SELECT gaia_id FROM agata_star WHERE gaia_id IN ({','.join([':gid' + str(i) for i in range(len(gaia_ids_to_check))])})")
                    ,
                    {f'gid{i}': gid for i, gid in enumerate(gaia_ids_to_check)}
                ).fetchall()
                star_gaia_ids = {str(row[0]) for row in rows}

        # Mark each result with in_agata_star flag for template display
        for result in job.results:
            result.in_agata_star = (
                str(result.gaia_source_id) in star_gaia_ids
                if result.gaia_source_id else False
            )

        return render_template(
            'admin/vast/job_detail.html',
            job=job,
            associations=associations,
            is_promoted=is_promoted,
            page_title=f'VAST Job {job.job_code}'
        )

    except Exception as e:
        logger.error(f"Error loading job detail: {e}", exc_info=True)
        return render_template('error.html', error=str(e)), 500
    finally:
        db.close()


@admin_bp.route('/api/vast/jobs/<int:job_id>/promote', methods=['POST'])
@login_required
@superuser_required
@audit_action('vast_results_promoted', 'vast_job')
def api_promote_vast_job(job_id):
    """
    Promuove i risultati VAST a agata_star_photometry (import bulk).

    NON crea progetti automaticamente. I dati vengono inseriti come
    "bacino centrale" e le associazioni possono assegnarli a se stesse
    quando creano progetti.

    Body JSON:
        exclude_known_variables: bool (optional) - Esclude variabili note
        result_ids: list (optional) - Se specificato, promuove solo questi result IDs
    """
    data = request.json or {}

    try:
        exclude_known = data.get('exclude_known_variables', False)
        result_ids = data.get('result_ids', None)

        vast_service = get_vast_service()
        stats = vast_service.promote_job_results(
            job_id=job_id,
            association_id=None,  # Non serve, legacy parameter
            user_id=current_user.id,
            user_email=current_user.email,
            only_known_variables=exclude_known,  # Se True, esclude note (skip in loop)
            only_candidates=True,  # Sempre True: promuoviamo solo VAST candidates
            result_ids=result_ids  # Se None, promuove tutti gli eligible
        )

        return jsonify({
            'success': True,
            'stats': stats
        }), 200

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except FileNotFoundError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404
    except Exception as e:
        logger.error(f"Failed to promote VAST job: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_bp.route('/api/vast/jobs/<int:job_id>/retry-gaia', methods=['POST'])
@login_required
@superuser_required
@audit_action('vast_retry_gaia', 'vast_job')
def api_retry_gaia_matching(job_id):
    """
    Retry Gaia cross-matching for selected stars in a VAST job.

    Body JSON:
        result_ids: list[int] - IDs of VastResult records to retry
    """
    data = request.get_json()
    result_ids = data.get('result_ids', [])

    if not result_ids:
        return jsonify({
            'success': False,
            'error': 'No result IDs provided'
        }), 400

    if not isinstance(result_ids, list):
        return jsonify({
            'success': False,
            'error': 'result_ids must be an array'
        }), 400

    try:
        vast_service = get_vast_service()

        # Execute retry
        stats = vast_service.retry_gaia_matching(
            job_id=job_id,
            result_ids=result_ids,
            user_id=current_user.id,
            user_email=current_user.email
        )

        return jsonify({
            'success': True,
            'stats': stats
        }), 200

    except ValueError as e:
        logger.error(f"Validation error in retry_gaia: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

    except Exception as e:
        logger.error(f"Error in retry_gaia: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f"Internal error: {str(e)}"
        }), 500


@admin_bp.route('/api/vast/jobs/<int:job_id>/result-count', methods=['GET'])
@login_required
@superuser_required
def api_get_vast_job_result_count(job_id):
    """
    Ritorna il numero preciso di VAST results associati a un job.
    Usato per mostrare il count esatto prima della cancellazione.
    """
    db = SessionLocal()
    try:
        from agata.auth_models import VastResult

        job = db.query(VastJob).filter(VastJob.id == job_id).first()
        if not job:
            return jsonify({'success': False, 'error': 'Job not found'}), 404

        result_count = db.query(VastResult).filter(
            VastResult.job_id == job_id
        ).count()

        return jsonify({
            'success': True,
            'result_count': result_count,
            'job_code': job.job_code
        }), 200

    except Exception as e:
        logger.error(f"Error getting result count for job {job_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        db.close()


@admin_bp.route('/api/vast/jobs/<int:job_id>', methods=['DELETE'])
@login_required
@superuser_required
@audit_action('vast_job_deleted', 'vast_job')
def api_delete_vast_job(job_id):
    """
    Cancella un VAST job e tutti i dati associati (VAST results + file su disco).

    Superuser only. Cancella:
    - agata_vast_jobs record
    - Tutti gli agata_vast_results associati
    - File temporanei se ancora presenti (temp_dir)
    - Cartella .dat files: /var/www/astrogen/data/vast_dat_files/{job_code}/

    Returns:
        {success: true, message: "..."}
    """
    db = SessionLocal()

    try:
        # Trova il job
        job = db.query(VastJob).filter(VastJob.id == job_id).first()
        if not job:
            return jsonify({
                'success': False,
                'error': f'Job {job_id} not found'
            }), 404

        job_code = job.job_code
        logger.info(f"Deleting VAST job {job_id} ({job_code}): {job.target_name}")

        # Conta VAST results da cancellare
        from agata.auth_models import VastResult
        result_count = db.query(VastResult).filter(
            VastResult.job_id == job_id
        ).count()

        logger.info(f"Job {job_code}: {result_count} VAST results to delete")

        # === STEP 1: Delete all VAST results ===
        db.query(VastResult).filter(
            VastResult.job_id == job_id
        ).delete(synchronize_session=False)

        logger.info(f"Deleted {result_count} VAST results for job {job_code}")

        # === STEP 2: Delete files on disk ===
        import os
        import shutil

        # Temp directory (download/processing files)
        if hasattr(job, 'temp_dir') and job.temp_dir:
            try:
                if os.path.exists(job.temp_dir):
                    shutil.rmtree(job.temp_dir)
                    logger.info(f"Deleted temp directory: {job.temp_dir}")
            except Exception as e:
                logger.warning(f"Could not delete temp directory {job.temp_dir}: {e}")

        # DAT files directory: /var/www/astrogen/data/vast_dat_files/{job_code}/
        dat_files_dir = os.path.join('/var/www/astrogen/data/vast_dat_files', job_code)
        if os.path.exists(dat_files_dir):
            try:
                shutil.rmtree(dat_files_dir)
                logger.info(f"Deleted DAT files directory: {dat_files_dir}")
            except Exception as e:
                logger.warning(f"Could not delete DAT files directory {dat_files_dir}: {e}")

        # === STEP 3: Delete the job record ===
        db.delete(job)
        db.commit()

        logger.info(f"VAST job {job_code} successfully deleted")

        return jsonify({
            'success': True,
            'message': f"VAST job '{job_code}' eliminato. Rimossi {result_count} risultati e file associati."
        }), 200

    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting VAST job {job_id}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f"Failed to delete job: {str(e)}"
        }), 500

    finally:
        db.close()


# ============================================================================
# Manual Gaia Match Correction
# ============================================================================

@admin_bp.route('/api/vast/results/<int:result_id>/search-gaia', methods=['POST'])
@login_required
@superuser_required
def search_gaia_for_result(result_id):
    """
    Search for Gaia matches for a specific VAST result.
    User can manually correct matches.
    """
    from agata.auth_models import VastResult
    from agata.catalog.services.vizier_client import VizierClient
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    db = SessionLocal()

    try:
        result = db.query(VastResult).filter(VastResult.id == result_id).first()
        if not result:
            return jsonify({'success': False, 'error': 'Result not found'}), 404

        data = request.get_json()
        radius_arcsec = data.get('radius', 100)

        # Query Vizier for Gaia sources
        vizier_client = VizierClient(timeout_s=20)
        catalog_id = "I/355/gaiadr3"
        columns = ['Source', 'RA_ICRS', 'DE_ICRS', 'Gmag', 'BP-RP']

        rows = vizier_client.query_cone(
            catalog_id=catalog_id,
            ra_deg=result.ra,
            dec_deg=result.decl,
            radius_arcsec=radius_arcsec,
            columns=columns,
            gmag_max=18
        )

        # Build results list
        candidates = []
        for row in rows:
            # CRITICAL: Keep gaia_id as STRING, never convert to int/float
            # Large 19-digit Gaia IDs lose precision when converted to numeric types
            # This gets serialized to JSON where JS will lose trailing digits
            gaia_id = str(row.values.get('Source', '0')).strip()
            gaia_ra = float(row.values.get('RA_ICRS', 0))
            gaia_dec = float(row.values.get('DE_ICRS', 0))
            gmag = float(row.values.get('Gmag', 99))

            # Calculate distance
            vast_coord = SkyCoord(ra=result.ra*u.deg, dec=result.decl*u.deg)
            gaia_coord = SkyCoord(ra=gaia_ra*u.deg, dec=gaia_dec*u.deg)
            distance_arcsec = vast_coord.separation(gaia_coord).to(u.arcsec).value

            candidates.append({
                'source_id': gaia_id,  # STRING, not int!
                'ra': gaia_ra,
                'dec': gaia_dec,
                'gmag': gmag,
                'distance': distance_arcsec
            })

        # Sort by magnitude (brightest first)
        candidates.sort(key=lambda x: x['gmag'])

        return jsonify({
            'success': True,
            'candidates': candidates,
            'vast_id': result.vast_id,
            'vast_ra': result.ra,
            'vast_dec': result.decl,
            'vast_mag': result.mean_mag,
            'current_gaia_id': result.gaia_source_id
        })

    except Exception as e:
        logger.error(f"Error searching Gaia for result {result_id}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f"Search failed: {str(e)}"
        }), 500

    finally:
        db.close()


@admin_bp.route('/api/vast/results/<int:result_id>/update-gaia', methods=['PUT'])
@login_required
@superuser_required
def update_gaia_match(result_id):
    """
    Manually update Gaia match for a specific VAST result.
    """
    from agata.auth_models import VastResult

    db = SessionLocal()

    try:
        result = db.query(VastResult).filter(VastResult.id == result_id).first()
        if not result:
            return jsonify({'success': False, 'error': 'Result not found'}), 404

        data = request.get_json()
        new_gaia_id = data.get('gaia_source_id')

        # CRITICAL: Ensure gaia_source_id is stored as STRING (prevent BigInt precision loss)
        # Large 19-digit Gaia IDs lose precision if converted to numeric type
        if new_gaia_id is not None:
            new_gaia_id = str(new_gaia_id).strip()

        # Update the result
        result.gaia_source_id = new_gaia_id
        if new_gaia_id:
            result.is_ambiguous = False  # Manually selected = not ambiguous

        db.commit()

        return jsonify({
            'success': True,
            'message': f'Updated {result.vast_id} with Gaia {new_gaia_id}'
        })

    except Exception as e:
        db.rollback()
        logger.error(f"Error updating Gaia match for result {result_id}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f"Update failed: {str(e)}"
        }), 500

    finally:
        db.close()
