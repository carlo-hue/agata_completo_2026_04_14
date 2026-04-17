# agata/admin/services/vast_service.py
"""
VAST Automation Service

Orchestrator principale per pipeline analisi immagini VAST.
Include: parsing VAST output, conversione WCS, cross-match Gaia/VSX/ATLAS,
rilevamento variabili note.
"""
import os
import tempfile
import logging
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

from sqlalchemy import text

from agata.db import SessionLocal
from agata.auth_models import VastJob, VastResult, User, Project
from agata.moduli.admin.services.vast_executor import VastExecutor
from agata.moduli.admin.services.google_drive_service import GoogleDriveService
from agata.moduli.admin.services.audit_service import log_audit
from agata.moduli.admin.services.catalog_common_service import (
    insert_catalog_data, generate_project_code, create_import_record,
    finalize_import, update_import_with_results
)
from agata.moduli.admin.services.star_service import upsert_star_photometry as _upsert_star_photometry
from agata.moduli.admin.services.cagg_refresh_helper import CaggRefreshMixin

logger = logging.getLogger(__name__)

# Nomi colonne vast_lightcurve_statistics.log (30 colonne)
VAST_STAT_COLUMNS = [
    'Median_magnitude', 'idx00_STD', 'x', 'y', 'name',
    'idx01_wSTD', 'idx02_skew', 'idx03_kurt', 'idx04_I', 'idx05_J',
    'idx06_K', 'idx07_L', 'idx08_Npts', 'idx09_MAD', 'idx10_lag1',
    'idx11_RoMS', 'idx12_rCh2', 'idx13_Isgn', 'idx14_Vp2p', 'idx15_Jclp',
    'idx16_Lclp', 'idx17_Jtim', 'idx18_Ltim', 'idx19_N3', 'idx20_excr',
    'idx21_eta', 'idx22_E_A', 'idx23_S_B', 'idx24_NXS', 'idx25_IQR'
]

# Solo le colonne degli indici di variabilita'
VARIABILITY_INDEX_COLUMNS = [c for c in VAST_STAT_COLUMNS if c.startswith('idx')]

# Directory persistente per file .dat VAST (curve di luce strumentali)
VAST_DAT_STORAGE = '/var/www/astrogen/data/vast_dat_files'

# Flag variabilita' Gaia DR3
GAIA_VAR_FLAGS = [
    'VCR', 'VRRLyr', 'VCep', 'VPN', 'VST', 'VLPV',
    'VEB', 'VRM', 'VMSO', 'VAGN', 'Vmicro', 'VCC'
]


# =========================================================================
# Worker function for ProcessPoolExecutor (MUST be top-level for pickling)
# =========================================================================
# =========================================================================
# Worker function for ProcessPoolExecutor (MUST be top-level for pickling)
# =========================================================================
def _gaia_worker_query_single_star(params):
    """
    Query UNA stella Gaia via Vizier con two-stage approach + magnitude calibration.

    Algoritmo (PASSI 1-8+):
    1-6: PRE-PHASE (fatto in _calculate_magnitude_offset_from_sample):
        - Prendi primi 5 VAST candidati
        - Query Vizier 10" per ognuno
        - Ordina per Gmag, prendi brightest
        - Calcola Vmag EDR3
        - offset = mean(Vmag)
        - Verifica differenze VAST_raw - Gmag siano simili (std_dev <= 2.0)
        - calibration_diff = mean(differenze)

    7: CALIBRAZIONE (in questo worker):
        - VAST_calibrated = VAST_raw + calibration_diff
        - Verifica: |VAST_calibrated - offset| <= 2.0
        - Se fallisce: no_match, STOP

    8: STAGE 1 - Query 10":
        - Query Vizier 10" per questa stella
        - Per ogni candidato: confronta |VAST_cal - Vmag| <= 2.0
        - Se compatibili: prendi più vicino, ritorna match
        - Se no: Stage 2 fallback

    FALLBACK Stage 2: Query 100" con stessi controlli

    params: tuple (name, ra, dec, match_radius_arcsec, vast_mag, offset, calibration_diff)
    return: dict con risultato
    """
    import logging
    from agata.catalog.services.vizier_client import VizierClient
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    logger_worker = logging.getLogger(__name__)
    name, ra, dec, match_radius_arcsec, vast_mag, offset, calibration_diff = params

    def process_candidates(candidates_list, radius_desc, global_offset, calibration_diff_val, is_stage2=False):
        """Helper per processare candidati (Stage 1 o Stage 2).

        Usa offset e calibration_diff pre-calcolati.

        Ritorna:
        - dict con risultato se successo
        - None se non trova candidati ma può continuare a Stage 2
        - 'no_match' se controllo coerenza fallisce (blocca completamente)
        """
        if len(candidates_list) == 0:
            return None

        # STEP 7: Calibra VAST usando calibration_diff (non offset!)
        vast_mag_calibrated = vast_mag + calibration_diff_val

        logger_worker.warning(
            f"[{radius_desc}] Star {name}: "
            f"VAST_raw={vast_mag:.2f}, calibration_diff={calibration_diff_val:.2f}, "
            f"VAST_calibrated={vast_mag_calibrated:.2f}"
        )

        # NOTE: Pre-phase ha già verificato che calibration_diff è coerente
        # (ha calcolato MEDIANA da sample rappresentativo)
        # Qui non è necessario un ulteriore check: procediamo direttamente al match

        # Confronta con TUTTI i candidati: |VAST_calibrated - Vmag_gaia| <= 2.5 mag
        # Increased from 2.0 to 3.0 to account for stars with anomalous BP-RP colors (>3.0)
        # which can have inaccurate Vmag calculations from Gaia EDR3 formula
        mag_tolerance = 3.0
        compatible = [
            c for c in candidates_list
            if c['vmag'] is not None and abs(vast_mag_calibrated - c['vmag']) <= mag_tolerance
        ]

        logger_worker.warning(
            f"[{radius_desc}] Star {name}: {len(compatible)}/{len(candidates_list)} compatible "
            f"(|VAST_cal - Vmag| <= {mag_tolerance})"
        )

        if len(compatible) == 0:
            return None

        # Ordina per distanza e prendi il più vicino
        compatible.sort(key=lambda x: x['distance'])
        selected = compatible[0]

        is_ambiguous = is_stage2  # Stage 2 è sempre ambiguous
        status = 'ambiguous' if is_ambiguous else 'match'

        logger_worker.info(
            f"[{radius_desc} RESULT] Star {name}: Gaia {selected['source_id']} @ {selected['distance']:.2f}\" "
            f"(Vmag={selected['vmag']:.2f}) {status}"
        )

        return {
            'name': name,
            'gaia_source_id': selected['source_id'],  # Sempre il migliore trovato, anche se ambiguous
            'gaia_ra': selected['ra'],
            'gaia_dec': selected['dec'],
            'gaia_gmag': selected['gmag'],
            'gaia_bp_rp': selected['bp_rp'],
            'gaia_vmag': selected['vmag'],
            'status': status,
            'is_ambiguous': is_ambiguous,
            'gaia_candidates': candidates_list[:10]
        }

    try:
        # Setup
        vizier_client = VizierClient(timeout_s=20)
        vast_coord = SkyCoord(ra=ra*u.deg, dec=dec*u.deg)
        catalog_id = "I/355/gaiadr3"
        columns = ['Source', 'RA_ICRS', 'DE_ICRS', 'Gmag', 'BP-RP']

        logger_worker.warning(f"[WORKER] Star {name} @ RA={ra:.6f}, Dec={dec:.6f}, VAST_mag_strumentale={vast_mag:.2f}")

        # ===== STAGE 1: Query 10" =====
        logger_worker.warning(f"[STAGE 1] Star {name}: querying 10\" radius")

        logger_worker.warning(f"[STAGE 1] Star {name}: querying with gmag_max=18 (will pass gmag_max parameter)")

        # Round coordinates to 4 decimals (~0.01 arcsec precision, sufficient for astronomy, avoids numeric issues)
        ra_rounded = round(ra, 4)
        dec_rounded = round(dec, 4)

        rows_10 = vizier_client.query_cone(
            catalog_id=catalog_id,
            ra_deg=ra_rounded,
            dec_deg=dec_rounded,
            radius_arcsec=10,
            columns=columns,
            gmag_max=18  # Solo stelle brillanti (Gmag < 18)
        )

        logger_worker.warning(f"[STAGE 1] Star {name}: got {len(rows_10)} candidates in 10\" (Gmag < 18 filter applied)")

        # Converti in lista con distanza e Vmag
        candidates_10 = []
        for row in rows_10:
            gaia_id = int(row.values.get('Source', 0))
            gaia_ra = float(row.values.get('RA_ICRS', 0))
            gaia_dec = float(row.values.get('DE_ICRS', 0))
            gmag = float(row.values.get('Gmag', 99))
            bp_rp_val = row.values.get('BP-RP')
            bp_rp = float(bp_rp_val) if bp_rp_val is not None else None

            vmag = _calculate_vmag_from_gaia(gmag, bp_rp)
            gaia_coord = SkyCoord(ra=gaia_ra*u.deg, dec=gaia_dec*u.deg)
            distance = vast_coord.separation(gaia_coord).to(u.arcsec).value

            candidates_10.append({
                'source_id': gaia_id,
                'ra': gaia_ra,
                'dec': gaia_dec,
                'gmag': gmag,
                'bp_rp': bp_rp,
                'vmag': vmag,
                'distance': distance
            })

        # Process Stage 1
        logger_worker.info(f"[STAGE 1 PROCESS] Star {name}: calling process_candidates with {len(candidates_10)} candidates")
        result_s1 = process_candidates(candidates_10, "STAGE 1", global_offset=offset, calibration_diff_val=calibration_diff, is_stage2=False)
        logger_worker.info(f"[STAGE 1 RESULT] Star {name}: result_s1={result_s1}")

        if result_s1 == 'no_match':
            # Controllo coerenza fallito in Stage 1 → blocca completamente
            logger_worker.warning(f"[STAGE 1] Star {name}: coherence check failed, no fallback to Stage 2")
            return {'name': name, 'status': 'no_match'}
        if result_s1 is not None and result_s1 != 'no_match':
            logger_worker.info(f"[STAGE 1 MATCH] Star {name}: found match in Stage 1, returning")
            return result_s1

        # ===== STAGE 2: Query 100" fallback =====
        logger_worker.warning(f"[STAGE 2 ENTERING] Star {name}: Stage 1 returned None, proceeding to Stage 2...")
        logger_worker.warning(f"[STAGE 2 FALLBACK] Star {name}: no match in 10\", trying 100\" with gmag_max=18...")
        logger_worker.warning(f"[STAGE 2 PARAMS] catalog={catalog_id}, RA={ra:.6f}, Dec={dec:.6f}, radius=100\", gmag_max=18, columns={columns}")

        # Round coordinates to 4 decimals (~0.01 arcsec precision, sufficient for astronomy, avoids numeric issues)
        ra_rounded = round(ra, 4)
        dec_rounded = round(dec, 4)

        rows_100 = vizier_client.query_cone(
            catalog_id=catalog_id,
            ra_deg=ra_rounded,
            dec_deg=dec_rounded,
            radius_arcsec=100,
            columns=columns,
            gmag_max=18  # Solo stelle brillanti (Gmag < 18)
        )

        logger_worker.warning(f"[STAGE 2 RESULT] Star {name}: got {len(rows_100)} candidates in 100\" (Gmag < 18 filter applied)")
        if len(rows_100) > 0:
            logger_worker.warning(f"[STAGE 2 DETAILS] Candidates Gmag: {[float(r.values.get('Gmag', 99)) for r in rows_100[:5]]}")

        # Converti in lista
        candidates_100 = []
        for row in rows_100:
            gaia_id = int(row.values.get('Source', 0))
            gaia_ra = float(row.values.get('RA_ICRS', 0))
            gaia_dec = float(row.values.get('DE_ICRS', 0))
            gmag = float(row.values.get('Gmag', 99))
            bp_rp_val = row.values.get('BP-RP')
            bp_rp = float(bp_rp_val) if bp_rp_val is not None else None

            vmag = _calculate_vmag_from_gaia(gmag, bp_rp)

            # Log ALL Stage 2 candidates with their Vmag for debugging
            vmag_str = f"{vmag:.2f}" if vmag is not None else "None"
            logger_worker.warning(f"[STAGE 2 CANDIDATE] {name}: Gaia {gaia_id} Gmag={gmag:.2f}, BP-RP={bp_rp}, Vmag={vmag_str}")

            gaia_coord = SkyCoord(ra=gaia_ra*u.deg, dec=gaia_dec*u.deg)
            distance = vast_coord.separation(gaia_coord).to(u.arcsec).value

            candidates_100.append({
                'source_id': gaia_id,
                'ra': gaia_ra,
                'dec': gaia_dec,
                'gmag': gmag,
                'bp_rp': bp_rp,
                'vmag': vmag,
                'distance': distance
            })

        # Process Stage 2
        result_s2 = process_candidates(candidates_100, "STAGE 2", global_offset=offset, calibration_diff_val=calibration_diff, is_stage2=True)
        if result_s2 == 'no_match':
            # Controllo coerenza fallito in Stage 2 → no_match
            logger_worker.warning(f"[STAGE 2] Star {name}: coherence check failed")
            return {'name': name, 'status': 'no_match'}
        if result_s2 is not None and result_s2 != 'no_match':
            return result_s2

        logger_worker.warning(f"[NO MATCH] Star {name}: no match in Stage 1 or Stage 2")
        return {'name': name, 'status': 'no_match'}

    except Exception as e:
        logger_worker.warning(f"[GAIA ERROR] Star {name}: {e}", exc_info=True)
        return {'name': name, 'status': 'error', 'error': str(e)}


def _calculate_vmag_from_gaia(gmag: float, bp_rp: Optional[float]) -> Optional[float]:
    """
    Calcola Vmag dalla formula di conversione Gaia EDR3.

    Formula: Vmag = gmag + 0.02704 - 0.01424*BP_RP + 0.2156*BP_RP^2 - 0.01426*BP_RP^3

    Source: Gaia EDR3 documentation

    Args:
        gmag: G-magnitude da Gaia
        bp_rp: BP-RP color from Gaia (optional)

    Returns:
        V-magnitude (use Gmag as fallback if bp_rp not available)
    """
    if bp_rp is None or np.isnan(bp_rp):
        # Fallback: use Gmag as proxy for Vmag (they are similar for most stars)
        return float(gmag)

    # CRITICAL: For stars with anomalous BP-RP colors (>2.0), the Gaia EDR3 formula becomes unreliable
    # Red giants and cool stars with BP-RP > 2.0 should use Gmag as Vmag proxy instead
    if bp_rp > 2.0:
        return float(gmag)

    try:
        vmag = gmag + 0.02704 - 0.01424 * bp_rp + 0.2156 * (bp_rp ** 2) - 0.01426 * (bp_rp ** 3)
        return float(vmag)
    except Exception as e:
        logger.warning(f"Failed to calculate Vmag: {e}")
        # Fallback: use Gmag if calculation fails
        return float(gmag)


def _validate_gaia_match_magnitude(vast_mag: Optional[float], gaia_gmag: float, tolerance_mag: float = 2.5) -> bool:
    """
    Valida se il match Gaia è coerente con la magnitudine VAST.

    Logica: la magnitudine strumentale VAST dovrebbe essere "simile" a quella Gaia
    (considerando che VAST è magnitudine strumentale e Gaia è standard).

    Un match è valido se:
    - VAST magnitude è disponibile
    - Differenza |VAST_mag - Gaia_gmag| < tolerance (default 2.5 mag)

    Argomenti:
        vast_mag: Magnitudine strumentale VAST (Median_magnitude)
        gaia_gmag: G-magnitude Gaia
        tolerance_mag: Tolleranza massima differenza magnitudini (mag)

    Returns:
        True se match è coerente, False altrimenti
    """
    if vast_mag is None or np.isnan(vast_mag):
        return False  # Non posso validare senza magnitudine VAST

    if gaia_gmag is None or np.isnan(gaia_gmag):
        return False  # Non posso validare senza magnitudine Gaia

    try:
        mag_diff = abs(vast_mag - gaia_gmag)
        is_valid = mag_diff < tolerance_mag

        if not is_valid:
            logger.debug(
                f"Magnitude mismatch: VAST={vast_mag:.2f}, Gaia Gmag={gaia_gmag:.2f}, "
                f"diff={mag_diff:.2f} mag (tolerance={tolerance_mag})"
            )

        return is_valid

    except Exception as e:
        logger.warning(f"Magnitude validation failed: {e}")
        return False


class VastService(CaggRefreshMixin):
    """Orchestrator pipeline VAST."""

    def __init__(self):
        self.vast_executor = VastExecutor()
        self.drive_service = GoogleDriveService()

    def create_job(
        self,
        target_name: str,
        source_type: str,
        source_location: str,
        processing_params: dict,
        user_id: str,
        user_email: str
    ) -> VastJob:
        """
        Crea nuovo job VAST.

        Args:
            target_name: Nome target astronomico
            source_type: 'drive_folder', 'local_path'
            source_location: Google Drive folder ID o local path
            processing_params: Parametri VAST
            user_id: User ID richiedente
            user_email: Email utente

        Returns:
            VastJob creato
        """
        db = SessionLocal()

        try:
            # Genera codice job (con timestamp per garantire unicità)
            import time
            timestamp = int(time.time() * 1000) % 100000  # ultimi 5 digit del timestamp
            job_code = f"VAST-{datetime.now().year}-{timestamp:05d}"

            # Verifica che sia univoco (fallback a contatore se collision)
            max_attempts = 10
            attempt = 0
            while db.query(VastJob).filter(VastJob.job_code == job_code).first() and attempt < max_attempts:
                timestamp = (timestamp + 1) % 100000
                job_code = f"VAST-{datetime.now().year}-{timestamp:05d}"
                attempt += 1

            if attempt >= max_attempts:
                # Fallback: usa contatore classico
                job_count = db.query(VastJob).count()
                job_code = f"VAST-{datetime.now().year}-{job_count+1:04d}"

            # Crea record job
            job = VastJob(
                job_code=job_code,
                target_name=target_name,
                source_type=source_type,
                source_location=source_location,
                processing_params=processing_params or {},
                requested_by=user_id,
                state='pending',
                progress_pct=0
            )

            db.add(job)
            db.commit()
            db.refresh(job)

            # Audit log
            log_audit(
                user_id=user_id,
                user_email=user_email,
                association_id=None,  # Operazione superuser
                action='vast_job_created',
                entity_type='vast_job',
                entity_id=str(job.id),
                new_value=job_code,
                description=f"Created VAST job {job_code} for {target_name}"
            )

            logger.info(f"Created VAST job {job_code} (ID: {job.id})")
            return job

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create VAST job: {e}", exc_info=True)
            raise
        finally:
            db.close()

    def execute_job(self, job_id: int):
        """
        Esecuzione job VAST completa.

        Workflow:
        1. Download immagini (0-30%)
        2. Validazione WCS (30-40%)
        3. Esecuzione VAST (40-60%)
        4. Parse output VAST (60-65%)
        5. Conversione WCS pixel->sky (65-70%)
        6. Cross-match Gaia DR2/DR3 (70-80%)
        7. Cross-match Vizier VSX+ATLAS (80-85%)
        8. Detect variabili note (85-88%)
        9. Upload risultati (88-95%)
        10. Completamento (100%)

        Args:
            job_id: ID del job da eseguire
        """
        db = SessionLocal()

        try:
            job = db.query(VastJob).get(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")

            logger.info(f"Starting VAST job {job.job_code}")

            # Update stato
            job.state = 'downloading'
            job.started_at = datetime.utcnow()
            db.commit()

            # Initialize reference_frame (may be set later)
            reference_frame = None

            # Workspace temporaneo
            with tempfile.TemporaryDirectory(prefix=f'vast_job_{job_id}_') as tmpdir:
                try:
                    # Step 1: Download immagini
                    logger.info(f"[{job.job_code}] Step 1: Download images")
                    image_paths = self._download_images(job, tmpdir, db)

                    # Step 2: Validazione WCS
                    logger.info(f"[{job.job_code}] Step 2: WCS validation")
                    job.state = 'validating'
                    job.current_step = 'Validating WCS in FITS headers'
                    db.commit()
                    self._validate_wcs(image_paths, db, job)

                    # Check skip_vast flag
                    skip_vast = bool(
                        job.processing_params
                        and job.processing_params.get('skip_vast')
                    )

                    if skip_vast:
                        # SKIP MODE: VAST già lanciato fuori dall'app
                        logger.info(f"[{job.job_code}] SKIP MODE: Skipping plate solve and VAST execution")
                        job.state = 'vast_analysis'
                        job.current_step = 'Validating existing VAST output (skip mode)'
                        db.commit()

                        # Valida che l'output VAST esista
                        vast_result = self.vast_executor.validate_existing_output(
                            image_dir=job.source_location if job.source_type == 'local_path' else tmpdir,
                            reference_frame=image_paths[0] if image_paths else None
                        )

                        # Estrai reference_frame da vast_result (aggiunto in validate_existing_output)
                        reference_frame = vast_result.get('reference_frame')

                        logger.info(
                            f"[{job.job_code}] Existing VAST output validated successfully, "
                            f"reference_frame: {os.path.basename(reference_frame) if reference_frame else 'None'}"
                        )
                        job.progress_pct = 50
                        db.commit()
                    else:
                        # NORMAL MODE: Plate solve + VAST execution

                        # Step 2.5: Plate solve reference frame PRIMA di VAST
                        logger.info(f"[{job.job_code}] Step 2.5: Plate solve reference frame (BEFORE VAST)")
                        job.current_step = 'Plate solving reference frame with Astrometry.net'
                        db.commit()

                        # Seleziona reference frame (prima immagine)
                        if job.source_type == 'local_path':
                            reference_frame = image_paths[0]
                        else:
                            reference_frame = image_paths[0]

                        reference_frame_solved = self._plate_solve_reference_frame(
                            reference_frame, job, db
                        )
                        logger.info(
                            f"Reference frame plate-solved: {os.path.basename(reference_frame)} → "
                            f"{os.path.basename(reference_frame_solved)}"
                        )
                        job.progress_pct = 40
                        db.commit()

                        # Step 3: VAST analysis (con reference frame plate-solved)
                        logger.info(f"[{job.job_code}] Step 3: VAST analysis (with corrected WCS)")
                        job.state = 'vast_analysis'
                        job.current_step = 'Running VAST photometry'
                        db.commit()
                        vast_result = self._run_vast(tmpdir, image_paths, job, db)
                        vast_result['reference_frame'] = reference_frame_solved

                        job.progress_pct = 50
                        db.commit()

                    # Step 4: Parse output VAST (SOLO candidate VAST)
                    logger.info(f"[{job.job_code}] Step 4: Parse VAST output (candidates only)")
                    job.current_step = 'Parsing VAST candidates'
                    db.commit()
                    parsed = self._parse_vast_output(vast_result, job)
                    stars_df = parsed['stars_df']
                    job.candidates_found = parsed['total_candidates']
                    job.progress_pct = 65
                    db.commit()

                    if stars_df.empty:
                        logger.warning("No candidates parsed from VAST output")
                        job.state = 'completed'
                        job.completed_at = datetime.utcnow()
                        job.progress_pct = 100
                        job.current_step = 'Analysis complete (no candidates found)'
                        job.stars_uploaded = 0
                        db.commit()
                        return

                    # Step 4.5: Skipped - use WCS conversion directly
                    logger.info(f"[{job.job_code}] Step 4.5: Skipping magnitude calibration (using WCS conversion)")
                    job.progress_pct = 68
                    db.commit()

                    # Step 5: Convert pixel coordinates to celestial using WCS
                    logger.info(f"[{job.job_code}] Step 5: Converting pixel coordinates to celestial")
                    job.current_step = 'Converting coordinates to celestial frame'
                    db.commit()
                    reference_frame = vast_result.get('reference_frame')
                    if reference_frame and os.path.exists(reference_frame):
                        stars_df = self._convert_pixel_to_sky(stars_df, reference_frame, job)
                        logger.info(f"Converted {len(stars_df)} star coordinates using WCS")
                    else:
                        logger.error(f"[{job.job_code}] Reference frame not found: {reference_frame}")
                        job.state = 'failed'
                        job.error_message = f"Cannot convert coordinates: reference frame not found"
                        job.completed_at = datetime.utcnow()
                        db.commit()
                        return
                    job.progress_pct = 70
                    db.commit()

                    # Step 6: Cross-match Gaia DR2/DR3 (optional for now - known timeout issues)
                    logger.info(f"[{job.job_code}] Step 6: Gaia cross-match (optional)")
                    job.state = 'crossmatching'
                    job.current_step = 'Cross-matching with Gaia DR2/DR3'
                    db.commit()
                    try:
                        stars_df = self._crossmatch_gaia(stars_df, job, db)
                        logger.info(f"Gaia cross-match succeeded")
                    except Exception as gaia_error:
                        logger.warning(f"Gaia cross-match failed (will continue without): {gaia_error}")
                        # Initialize gaia columns with null values so pipeline doesn't break
                        if 'gaia_source_id' not in stars_df.columns:
                            stars_df['gaia_source_id'] = None
                        if 'gaia_vmag' not in stars_df.columns:
                            stars_df['gaia_vmag'] = None
                        if 'gaia_bp_rp' not in stars_df.columns:
                            stars_df['gaia_bp_rp'] = None
                    job.progress_pct = 80
                    db.commit()

                    # Step 7: Cross-match Vizier (VSX + ATLAS)
                    logger.info(f"[{job.job_code}] Step 7: Vizier cross-match")
                    job.current_step = 'Cross-matching with VSX and ATLAS'
                    db.commit()
                    stars_df = self._crossmatch_vizier(stars_df, job, db)
                    job.progress_pct = 85
                    db.commit()

                    # Step 8: Detect variabili note
                    logger.info(f"[{job.job_code}] Step 8: Detect known variables")
                    job.current_step = 'Detecting known variables'
                    db.commit()
                    stars_df = self._detect_known_variables(stars_df)
                    job.progress_pct = 88
                    db.commit()

                    # Step 9: Build candidates list e upload
                    logger.info(f"[{job.job_code}] Step 9: Upload results")
                    job.state = 'uploading'
                    job.current_step = 'Uploading results to database'
                    db.commit()
                    candidates = self._build_candidates_list(
                        stars_df, parsed['vast_dir']
                    )
                    self._upload_results(
                        {'candidates': candidates},
                        job, db
                    )

                    # Step 10: Preserve .dat files for later promotion
                    logger.info(f"[{job.job_code}] Step 10: Preserving .dat files")
                    job.current_step = 'Preserving lightcurve data files'
                    db.commit()
                    self._preserve_dat_files(
                        stars_df, parsed['vast_dir'], job
                    )

                    # Save reference_frame info for debugging
                    if reference_frame and job.output_files:
                        job.output_files['reference_frame'] = os.path.basename(reference_frame)
                        db.commit()

                    # Step 11: Complete
                    job.state = 'completed'
                    job.completed_at = datetime.utcnow()
                    job.progress_pct = 100
                    job.current_step = 'Analysis complete'
                    db.commit()

                    # Force refresh cagg immediately (Phase 3 optimization)
                    self.refresh_cagg_for_table(db, 'agata_vast_results', 'vast_job_summary')

                    logger.info(f"VAST job {job.job_code} completed successfully")

                except Exception as e:
                    logger.error(f"VAST job {job.job_code} failed: {e}", exc_info=True)
                    job.state = 'failed'
                    job.error_message = str(e)
                    job.completed_at = datetime.utcnow()
                    db.commit()
                    raise

        except Exception as e:
            logger.error(f"Critical error in execute_job: {e}", exc_info=True)
            raise
        finally:
            db.close()

    # =========================================================================
    # STEP 1: Download
    # =========================================================================

    def _download_images(
        self,
        job: VastJob,
        tmpdir: str,
        db
    ) -> List[str]:
        """Download immagini da sorgente a directory temporaneo."""

        if job.source_type == 'drive_folder':
            logger.info(f"Downloading from Google Drive folder: {job.source_location}")

            folder_id = job.source_location

            # Check spazio disco
            try:
                folder_size = self.drive_service.calculate_folder_size(folder_id)
                required_space = folder_size * 1.5  # Margine di sicurezza

                disk_usage = shutil.disk_usage(tmpdir)
                if disk_usage.free < required_space:
                    raise RuntimeError(
                        f"Insufficient disk space: need {required_space/1024**3:.2f} GB, "
                        f"have {disk_usage.free/1024**3:.2f} GB"
                    )
            except Exception as e:
                logger.error(f"Disk space check failed: {e}")
                raise

            # Download
            def progress_callback(current, total):
                job.progress_pct = int((current / total) * 30)  # 0-30% per download
                job.images_downloaded = current
                db.commit()

            try:
                logger.info(f"[{job.job_code}] Downloading FITS files from folder {folder_id}...")

                # Download FITS files (.fit or .fits)
                image_paths = self.drive_service.download_folder(
                    folder_id=folder_id,
                    destination_dir=tmpdir,
                    file_extensions=['.fit', '.fits'],
                    progress_callback=progress_callback
                )

                logger.info(f"[{job.job_code}] Downloaded {len(image_paths)} FITS files")

                if not image_paths:
                    logger.warning(f"[{job.job_code}] No FITS files found in folder {folder_id}")
                    all_files = self.drive_service.list_folder_contents(folder_id)
                    logger.info(f"[{job.job_code}] Files in folder: {[f['name'] for f in all_files[:10]]}")
            except Exception as e:
                logger.error(f"Google Drive download failed: {e}", exc_info=True)
                raise

            job.downloaded_files = {'paths': image_paths, 'count': len(image_paths)}
            db.commit()

            logger.info(f"Downloaded {len(image_paths)} images")
            return image_paths

        elif job.source_type == 'local_path':
            logger.info(f"Reading from local path: {job.source_location}")

            image_dir = Path(job.source_location)
            if not image_dir.exists():
                raise FileNotFoundError(f"Source directory not found: {job.source_location}")

            image_paths = list(image_dir.glob('*.fit*'))
            if not image_paths:
                raise ValueError(f"No FITS files found in {job.source_location}")

            job.images_downloaded = len(image_paths)
            db.commit()

            logger.info(f"Found {len(image_paths)} images in local path")
            return [str(p) for p in image_paths]

        else:
            raise ValueError(f"Unsupported source type: {job.source_type}")

    # =========================================================================
    # STEP 2: WCS Validation
    # =========================================================================

    def _validate_wcs(
        self,
        image_paths: List[str],
        db,
        job: VastJob
    ):
        """
        Validazione WCS (World Coordinate System) con Astropy.

        Nota: VAST puo' elaborare immagini senza WCS.
        Questa validazione e' solo informativa.
        """
        try:
            from astropy.io import fits
            from astropy.wcs import WCS
        except ImportError:
            logger.warning("Astropy not installed, skipping WCS validation")
            job.images_solved = len(image_paths)
            job.progress_pct = 40
            db.commit()
            return

        valid_wcs_count = 0
        missing_wcs = []

        for img_path in image_paths:
            try:
                with fits.open(img_path) as hdul:
                    header = hdul[0].header
                    wcs = WCS(header)

                    # Check WCS valido
                    if wcs.has_celestial:
                        valid_wcs_count += 1
                    else:
                        missing_wcs.append(img_path)
                        logger.debug(f"Image missing valid WCS: {os.path.basename(img_path)}")

            except Exception as e:
                logger.debug(f"Cannot validate WCS for {img_path}: {e}")
                missing_wcs.append(img_path)

        job.images_solved = valid_wcs_count
        job.progress_pct = 40
        db.commit()

        logger.info(
            f"WCS validation: {valid_wcs_count}/{len(image_paths)} have valid WCS, "
            f"{len(missing_wcs)} missing"
        )

    # =========================================================================
    # STEP 2.5: Astrometry.net Plate Solving
    # =========================================================================

    def _plate_solve_reference_frame(
        self,
        reference_frame: str,
        job: VastJob,
        db
    ) -> str:
        """
        Plate solve il reference frame con Astrometry.net (solve-field).

        Astrometry.net fornisce WCS accurato per la ricerca Gaia corretta,
        essenziale per il cross-matching stellare.

        Args:
            reference_frame: Path al FITS file di riferimento
            job: VastJob object
            db: Database session

        Returns:
            Path al FITS plate-solved (o path originale se solve-field fallisce)
        """
        try:
            import subprocess
            from astropy.io import fits

            basename = os.path.basename(reference_frame)

            # Estrae WCS da FITS header per suggerimento a solve-field
            try:
                with fits.open(reference_frame) as hdul:
                    header = hdul[0].header
                    ra_center = header.get('CRVAL1', 45.93)
                    dec_center = header.get('CRVAL2', 44.07)

                    # Stima scale in arcsec/pixel
                    cd11 = header.get('CD1_1', 0.0)
                    cd12 = header.get('CD1_2', 0.0)
                    scale = np.sqrt(cd11**2 + cd12**2) * 3600.0
                    if scale < 0.1:
                        scale = 20.0  # Default TESS ~20 arcsec/pixel

                    logger.info(
                        f"FITS header: RA={ra_center:.4f}, Dec={dec_center:.4f}, "
                        f"scale~{scale:.2f} arcsec/pixel"
                    )
            except Exception as e:
                logger.warning(f"Could not read FITS header: {e}")
                ra_center = 45.93
                dec_center = 44.07
                scale = 20.0

            # Comando solve-field (astrometry.net)
            # --overwrite: sovrascrivi FITS header con WCS
            # --tweak-order 2: polinomio TAN-SIP distortion (ordine 2)
            # --downsample: riduce risoluzione per velocità
            # --scale-low/high: vincola stima scale
            # --ra/dec/radius: suggerimento posizione
            # --no-plots: no output plots
            cmd = [
                'solve-field',
                '--overwrite',
                '--tweak-order', '2',
                '--downsample', '4',
                '--scale-units', 'arcsecperpix',
                '--scale-low', str(max(scale * 0.9, 1.0)),
                '--scale-high', str(scale * 1.1),
                '--ra', str(ra_center),
                '--dec', str(dec_center),
                '--radius', '5',
                '--no-plots',
                reference_frame
            ]

            logger.info(f"Plate solving reference frame with astrometry.net")
            logger.info(f"Command: {' '.join(cmd[:5])}... {basename}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minuti max (solve-field è più lento)
            )

            logger.info(f"solve-field return code: {result.returncode}")

            # Log output ridotto
            if result.stdout:
                # Log solo le linee importanti
                for line in result.stdout.split('\n'):
                    if 'solved' in line.lower() or 'match' in line.lower() or 'log-odds' in line.lower():
                        logger.info(f"solve-field: {line}")

            if result.stderr:
                logger.warning(f"solve-field stderr: {result.stderr[:300]}")

            # Verifica se plate solving ha successo
            # solve-field crea: .solved (marker), .new (FITS with updated WCS)
            solved_marker = reference_frame.replace('.fits', '.solved')
            solved_fits = reference_frame.replace('.fits', '.new')

            if result.returncode == 0 and os.path.exists(solved_marker):
                if os.path.exists(solved_fits):
                    # solve-field ha creato il file .new con WCS aggiornato
                    # Copia .new sopra il file originale
                    import shutil
                    try:
                        shutil.copy(solved_fits, reference_frame)
                        logger.info(f"✅ Plate solving successful: updated {basename}")
                        job.current_step = 'Plate solving successful (Astrometry.net)'
                        db.commit()
                        return reference_frame
                    except Exception as e:
                        logger.error(f"Failed to copy .new file: {e}")
                        job.current_step = f'Plate solving copy failed: {e}'
                        db.commit()
                        return reference_frame
                else:
                    logger.info(f"✅ Plate solving successful but .new not found, using original")
                    job.current_step = 'Plate solving successful (Astrometry.net)'
                    db.commit()
                    return reference_frame
            else:
                logger.warning(
                    f"⚠️  Plate solving failed or no solution found (return code {result.returncode}), "
                    f"using original WCS"
                )
                job.current_step = 'Plate solving failed, using original WCS'
                db.commit()
                return reference_frame

        except Exception as e:
            logger.error(f"❌ Plate solving error: {e}", exc_info=True)
            job.current_step = 'Plate solving error, using original WCS'
            db.commit()
            return reference_frame

    # =========================================================================
    # STEP 3: VAST Execution
    # =========================================================================

    def _run_vast(
        self,
        tmpdir: str,
        image_paths: List[str],
        job: VastJob,
        db
    ) -> dict:
        """Esecuzione VAST (singola, senza crop). Ritorna risultato executor."""

        # Per local_path, i file sono gia' nei loro path originali
        # Per drive, i file sono stati copiati a tmpdir
        if job.source_type == 'local_path':
            image_dir = job.source_location
        else:
            image_dir = tmpdir

        # Esecuzione VAST su tutte le immagini
        result = self.vast_executor.run_vast_analysis(
            image_dir=image_dir,
            output_dir=tmpdir,
            reference_frame=None,  # Auto-seleziona prima immagine
            options=job.processing_params
        )

        if not result['success']:
            raise RuntimeError(f"VAST analysis failed:\n{result['stderr']}")

        job.progress_pct = 60
        db.commit()

        return result

    # =========================================================================
    # STEP 4: Parse VAST Output
    # =========================================================================

    def _parse_vast_output(self, vast_result: dict, job: 'VastJob' = None) -> dict:
        """
        Parse output VAST SOLO le candidate VAST.

        Legge:
        - vast_lightcurve_statistics.log: tutti i 31 indici di variabilita'
        - vast_autocandidates.log: top candidates (primary)
        - vast_autocandidates_details.log: all stars with flags (fallback or explicit selection)

        Logica:
        - Se use_details_file=True (user flag): usa SOLO details file con filtering stretto
          (FRACTION_OF + ID-only rows)
        - Altrimenti: usa priority system (autocandidates → details fallback)
          (FRACTION_OF solo in fallback mode)

        Args:
            vast_result: Output dict from VAST execution
            job: VastJob object to read processing_params

        Returns:
            dict con 'stars_df' (DataFrame), 'total_candidates', 'vast_dir'
        """
        vast_dir = vast_result.get('vast_dir')
        stats_log = vast_result.get('stats_log')
        candidates_details = vast_result.get('candidates_details_log')
        candidates_log = vast_result.get('output_csv')

        # Check user preference for details file
        use_details_file = job.processing_params.get('use_details_file', False) if (job and job.processing_params) else False

        if not stats_log or not os.path.exists(stats_log):
            logger.warning("vast_lightcurve_statistics.log not found")
            return {
                'stars_df': pd.DataFrame(),
                'total_candidates': 0,
                'vast_dir': vast_dir
            }

        try:
            # 1. Leggi statistiche per TUTTE le stelle
            all_stars = pd.read_csv(
                stats_log, sep=r'\s+', header=None,
                names=VAST_STAT_COLUMNS
            )
            logger.info(f"Parsed {len(all_stars)} total stars from statistics log")

            # 2. Leggi SOLO i nomi dei candidati
            candidate_names = set()

            if use_details_file:
                # User explicitly requested details file mode (stricter filtering)
                if not candidates_details or not os.path.exists(candidates_details):
                    raise FileNotFoundError(
                        f"Detailed candidates file not found: {candidates_details}\n"
                        f"Cannot use details file mode when file is missing."
                    )

                logger.info("Using vast_autocandidates_details.log (user selected)")
                with open(candidates_details, 'r') as f:
                    for line in f:
                        if line.strip():
                            # Fixed-width: nome in colonne 0-12, flags da colonna 13
                            name = line[0:12].strip()
                            candidate_flag = line[13:].strip() if len(line) > 13 else ''

                            # Filter 1: Exclude FRACTION_OF rows (calibration stars)
                            if 'FRACTION_OF' in candidate_flag:
                                continue

                            # Filter 2: Exclude ID-only rows (no flags or data after ID)
                            if not candidate_flag:
                                continue

                            candidate_names.add(name)

                logger.info(f"Found {len(candidate_names)} candidates from details file (FRACTION_OF + ID-only filtered)")

            else:
                # Default behavior: priority system
                if candidates_log and os.path.exists(candidates_log):
                    # PRIMARY: Read top candidates list (simple list of names)
                    with open(candidates_log, 'r') as f:
                        candidate_names = set(line.strip() for line in f if line.strip())
                    logger.info(f"Found {len(candidate_names)} candidates from vast_autocandidates.log")

                elif candidates_details and os.path.exists(candidates_details):
                    # FALLBACK: Read all stars with flags, discard FRACTION_OF
                    with open(candidates_details, 'r') as f:
                        for line in f:
                            if line.strip():
                                # Fixed-width: nome in colonne 0-12
                                name = line[0:12].strip()
                                candidate_flag = line[13:].strip() if len(line) > 13 else ''
                                # Scarta FRACTION_OF in fallback mode
                                if 'FRACTION_OF' not in candidate_flag:
                                    candidate_names.add(name)
                    logger.info(f"Found {len(candidate_names)} valid candidates from vast_autocandidates_details.log (fallback, FRACTION_OF filtered)")

                else:
                    logger.warning("No candidates file found, will process all stars")
                    # Se nessun file candidate, non filtrare
                    candidate_names = set(all_stars['name'].tolist())

            # 3. Filtra per soli candidati
            candidates_df = all_stars[all_stars['name'].isin(candidate_names)].copy()

            logger.info(
                f"Selected {len(candidates_df)} candidates from {len(all_stars)} total stars"
            )

            return {
                'stars_df': candidates_df,
                'total_candidates': len(candidates_df),
                'vast_dir': vast_dir
            }

        except Exception as e:
            logger.error(f"Failed to parse VAST output: {e}", exc_info=True)
            return {
                'stars_df': pd.DataFrame(),
                'total_candidates': 0,
                'vast_dir': vast_dir
            }

    # =========================================================================
    # STEP 5: WCS Coordinate Conversion
    # =========================================================================

    def _convert_pixel_to_sky(
        self,
        stars_df: pd.DataFrame,
        reference_frame: str,
        job: VastJob
    ) -> pd.DataFrame:
        """
        Converte coordinate pixel (x, y) in coordinate celesti (ra, dec) usando WCS.

        Gestisce TESS (HDU 1) vs ground-based (HDU 0).
        Memory-safe: apre FITS con memmap=True.
        """
        try:
            from astropy.io import fits
            from astropy.wcs import WCS
        except ImportError:
            logger.error("Astropy required for WCS conversion but not installed")
            stars_df['ra'] = 0.0
            stars_df['dec'] = 0.0
            return stars_df

        # Determina HDU number - Try HDU 1 first (TESS), fallback to HDU 0
        is_tess = 'tess' in (job.target_name or '').lower()
        hdu_number = 1 if is_tess else 0

        if job.processing_params and 'hdu_number' in job.processing_params:
            hdu_number = int(job.processing_params['hdu_number'])

        logger.info(
            f"WCS conversion: reference={os.path.basename(reference_frame)}, "
            f"is_tess={is_tess}, trying HDU={hdu_number}"
        )

        try:
            with fits.open(reference_frame, memmap=True) as hdul:
                # Fallback: if requested HDU doesn't exist, try HDU 0
                if hdu_number >= len(hdul):
                    logger.warning(
                        f"HDU {hdu_number} not found ({len(hdul)} HDUs total), "
                        f"falling back to HDU 0"
                    )
                    hdu_number = 0

                header = hdul[hdu_number].header
                wcs = WCS(header)

                if not wcs.has_celestial:
                    logger.warning("Reference frame has no celestial WCS")
                    stars_df['ra'] = 0.0
                    stars_df['dec'] = 0.0
                    stars_df['_ra_center'] = 0.0
                    stars_df['_dec_center'] = 0.0
                    return stars_df

                # Centro campo per query Vizier
                ra_center = header.get('CRVAL1', 0.0)
                dec_center = header.get('CRVAL2', 0.0)

                # Conversione vettorizzata di tutte le coordinate (DENTRO il with block!)
                # VAST outputs: X (column), Y (row) in SExtractor 0-indexed convention
                # WCS origin=1: FITS convention (1-indexed)
                # Using origin=1 is correct for converting 0-indexed pixel coords to celestial
                # NO Y-flip needed - FITS WCS handles coordinate system correctly
                # This matches the working approach from vastAnalisys.py

                ra_arr, dec_arr = wcs.all_pix2world(
                    np.float64(stars_df['x']),
                    np.float64(stars_df['y']),
                    1  # origin=1 (FITS convention)
                )

                stars_df['ra'] = ra_arr
                stars_df['dec'] = dec_arr
                stars_df['_ra_center'] = ra_center
                stars_df['_dec_center'] = dec_center

                logger.info(
                    f"WCS conversion complete: {len(stars_df)} stars, "
                    f"center=({ra_center:.4f}, {dec_center:.4f})"
                )

        except Exception as e:
            logger.error(f"WCS conversion failed: {e}", exc_info=True)
            stars_df['ra'] = 0.0
            stars_df['dec'] = 0.0
            stars_df['_ra_center'] = 0.0
            stars_df['_dec_center'] = 0.0

        return stars_df

    def _calculate_magnitude_offset_from_sample(
        self,
        stars_valid: pd.DataFrame,
        match_radius_arcsec: int
    ) -> tuple:
        """
        Calcola offset (media Vmag Gaia) e calibration_diff dalle prime 10 stelle VAST.

        Algoritmo (PASSI 1-7):
        1. Prendi i primi 10 candidati VAST (per garantire >= 3 con Gaia match)
        2. Per ogni stella: Query Vizier 10"
        3. Ordina per Gmag, prendi brightest
        4. Calcola Vmag con formula EDR3
        5. offset = mean(Vmag)
        6. Calcola differenze VAST_raw - Gmag per ogni stella
        7. Usa MEDIANA per identificare outliers (deviation > 2.0 da median)
           Se >= 3 stelle buone: calibration_diff = median(good_diffs)
           Se < 3 stelle buone: return (None, None) → BLOCCA tutto

        Args:
            stars_valid: DataFrame con colonne [ra, dec, name, Median_magnitude]
            match_radius_arcsec: Raggio di ricerca (10")

        Returns:
            tuple: (offset, calibration_diff)
            Se qualcosa fallisce: (None, None)
        """
        try:
            from agata.catalog.services.vizier_client import VizierClient

            vizier_client = VizierClient(timeout_s=20)
            catalog_id = "I/355/gaiadr3"
            columns = ['Source', 'RA_ICRS', 'DE_ICRS', 'Gmag', 'BP-RP']

            # STEP 1: Prendi i primi 10 candidati (per garantire >= 3 con Gaia match)
            num_sample = min(10, len(stars_valid))
            sample_stars = stars_valid.head(num_sample)

            logger.info(f"Calculating offset and calibration_diff from {num_sample} sample stars (10\" radius)...")

            vmags = []
            diffs = []
            sample_details = []  # Store all 10 stars (even if some have no Gaia match)

            for idx, (_, star_row) in enumerate(sample_stars.iterrows()):
                star_name = star_row['name']
                star_ra = round(star_row['ra'], 4)  # Round to 4 decimals (~0.01 arcsec precision, sufficient for astronomy)
                star_dec = round(star_row['dec'], 4)  # Round to 4 decimals
                vast_raw = star_row['Median_magnitude']  # VAST strumentale

                gmag = None
                vmag = None
                diff = None

                try:
                    # STEP 2: Query Vizier 100" (with Gmag filter) - wide search for sample stars
                    rows = vizier_client.query_cone(
                        catalog_id=catalog_id,
                        ra_deg=star_ra,
                        dec_deg=star_dec,
                        radius_arcsec=100,
                        columns=columns,
                        gmag_max=18  # Filter to exclude faint candidates
                    )

                    if len(rows) > 0:
                        # STEP 3: Ordina per Gmag (più brillante = più piccolo), prendi primo
                        rows_sorted = sorted(rows, key=lambda r: float(r.values.get('Gmag', 99)))
                        first_candidate = rows_sorted[0]
                        gmag = float(first_candidate.values.get('Gmag', 99))
                        bp_rp_val = first_candidate.values.get('BP-RP')
                        bp_rp = float(bp_rp_val) if bp_rp_val is not None else None

                        # STEP 4: Calcola Vmag usando formula EDR3
                        vmag = _calculate_vmag_from_gaia(gmag, bp_rp)

                        if vmag is not None:
                            # STEP 6: Calcola DIFFERENZA tra VAST_raw e Gmag
                            diff = abs(vast_raw - gmag)
                            vmags.append(vmag)
                            diffs.append(diff)

                except Exception as e:
                    logger.warning(f"  {star_name}: error during offset calculation: {e}")

                # Salva dettagli per TUTTI i 5 (anche se uno non ha Gaia match)
                sample_details.append({
                    'name': star_name,
                    'ra': star_ra,
                    'dec': star_dec,
                    'vast_raw': vast_raw,
                    'gmag': gmag,
                    'vmag': vmag,
                    'diff': diff,
                    'has_match': vmag is not None
                })

            # Verifica che abbiamo almeno 3 valori buoni
            if len(vmags) < 3:
                print(f"\n❌ NOT ENOUGH GAIA MATCHES: only {len(vmags)} out of {num_sample} sample stars\n", flush=True)
                return (None, None)

            # STEP 5: Calcola offset come media Vmag
            offset = float(np.mean(vmags))
            logger.info(f"Offset (mean Vmag): {offset:.2f} mag (from {len(vmags)}/{num_sample} stars)")

            # Log completo dei 10 candidati (anche quelli senza Gaia match)
            print(f"\n{'='*100}", flush=True)
            print(f"PRE-PHASE CALIBRATION - All {len(sample_details)} sample stars:", flush=True)
            print(f"{'='*100}", flush=True)
            for i, detail in enumerate(sample_details, 1):
                if detail['has_match']:
                    print(
                        f"  {i}. {detail['name']:15s} ({detail['ra']:10.5f}, {detail['dec']:10.5f}): "
                        f"VAST_raw={detail['vast_raw']:7.2f}, Gmag={detail['gmag']:6.2f}, "
                        f"Vmag={detail['vmag']:6.2f}, diff={detail['diff']:6.2f}",
                        flush=True
                    )
                else:
                    print(
                        f"  {i}. {detail['name']:15s} ({detail['ra']:10.5f}, {detail['dec']:10.5f}): "
                        f"VAST_raw={detail['vast_raw']:7.2f}, NO GAIA MATCH",
                        flush=True
                    )

            # PASSO CRITICO: Calcola MEDIANA dei diffs per identificare outliers
            print(f"\nStatistics:", flush=True)
            print(f"  All differences: {[f'{d:.2f}' for d in diffs]}", flush=True)

            # Calcola mediana (valore centrale, robusto agli outliers)
            diffs_sorted = sorted(diffs)
            median_diff = float(np.median(diffs_sorted))
            print(f"  Median difference: {median_diff:.2f} mag", flush=True)

            # STEP 7: Scarta gli outliers (quelli che differiscono > 2 mag dalla MEDIANA)
            outlier_tolerance = 2.0
            good_diffs = []
            good_vmags = []
            good_indices = []
            removed_details = []

            print(f"\n⚠️  OUTLIER DETECTION (tolerance: ±{outlier_tolerance} mag from median {median_diff:.2f}):", flush=True)

            for i, diff in enumerate(diffs):
                deviation = abs(diff - median_diff)
                if deviation <= outlier_tolerance:
                    good_diffs.append(diff)
                    good_vmags.append(vmags[i])
                    good_indices.append(i)
                    print(
                        f"   ✓ {sample_details[i]['name']:15s}: diff={diff:6.2f} (deviation {deviation:5.2f}) KEEP",
                        flush=True
                    )
                else:
                    removed_details.append((i, sample_details[i], deviation))
                    print(
                        f"   ❌ {sample_details[i]['name']:15s}: diff={diff:6.2f} (deviation {deviation:5.2f}) REMOVE",
                        flush=True
                    )

            # Verifica: se rimangono < 3 stelle buone, blocca tutto
            if len(good_diffs) < 3:
                print(
                    f"\n❌ NOT ENOUGH GOOD STARS: only {len(good_diffs)} remaining (need >= 3)\n"
                    f"   All diffs: {[f'{d:.2f}' for d in diffs]}\n"
                    f"   Good diffs: {[f'{d:.2f}' for d in good_diffs]}\n"
                    f"   → BLOCKING ALL {len(stars_valid)} STARS\n",
                    flush=True
                )
                return (None, None)

            # Calcola offset e calibration_diff SOLO dalle stelle buone
            offset = float(np.mean(good_vmags))  # Media dei Vmag buoni
            calibration_diff = float(np.median(good_diffs))  # Mediana dei diffs buoni

            print(f"\n{'='*100}", flush=True)
            print(f"FINAL RESULT (using MEDIAN for robustness):", flush=True)
            print(f"  Kept {len(good_diffs)} good stars (out of {len(sample_details)} total)", flush=True)
            if len(good_diffs) < len(sample_details):
                print(f"  Removed {len(sample_details) - len(good_diffs)} outlier(s)", flush=True)
            print(f"\n  Good stars Vmags: {[f'{v:.2f}' for v in good_vmags]}", flush=True)
            print(f"  Good stars diffs: {sorted(good_diffs)} → median={calibration_diff:.2f}", flush=True)
            print(f"\n  offset (mean of good Vmags): {offset:.2f} mag", flush=True)
            print(f"  calibration_diff (median of good diffs): {calibration_diff:.2f} mag", flush=True)
            print(f"\n✅ Calibration READY: Will apply to {len(stars_valid)} stars", flush=True)
            print(f"{'='*100}\n", flush=True)

            return (offset, calibration_diff)

        except Exception as e:
            logger.error(f"Error calculating offset/calibration_diff: {e}", exc_info=True)
            return (None, None)

    # =========================================================================
    # STEP 6: Gaia Cross-Match (TAP Upload)
    # =========================================================================

    def _crossmatch_gaia(
        self,
        stars_df: pd.DataFrame,
        job: VastJob,
        db
    ) -> pd.DataFrame:
        """
        Cross-match con Gaia DR3 - Parallelo con una stella per volta (PROVEN approach).

        Approccio OTTIMIZZATO e TESTED:
        1. ProcessPoolExecutor con 4 worker
        2. Per ogni stella: CONTAINS + CIRCLE query (server-side filtering)
        3. Prende il primo match (più vicino)
        4. Recupera gaia_source_id, gmag, bp_rp (per Vmag)
        5. Scala magnitudini VAST usando Vmag come riferimento

        Vantaggi PROVEN:
        - 95%+ match rate (testato con 689 stelle)
        - NO timeout Gaia TAP server
        - Login nel worker (connessione persistente per process)
        - Parallelo veloce (~0.1s per stella)
        - Recupera bp_rp per calcolo Vmag

        Testato: test/test_vast_gaia_upload.py, Session 12 memory notes
        """
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
        except ImportError:
            logger.warning("concurrent.futures not installed, skipping Gaia cross-match")
            return stars_df

        # Verifica che le coordinate siano valide
        if stars_df['ra'].eq(0.0).all():
            logger.warning("All RA=0, skipping Gaia cross-match (WCS failed?)")
            return stars_df

        job.current_step = 'Cross-matching with Gaia DR3'
        db.commit()

        try:
            # Filtra stelle con coordinate valide (non 0.0)
            valid_mask = (stars_df['ra'] != 0.0) & (stars_df['dec'] != 0.0)
            stars_valid = stars_df[valid_mask][['ra', 'dec', 'name', 'Median_magnitude']].copy()

            if len(stars_valid) == 0:
                logger.warning("No stars with valid coordinates, skipping Gaia cross-match")
                return stars_df

            logger.info(f"Gaia cross-match: {len(stars_valid)}/{len(stars_df)} stars with valid coordinates")

            # Match radius: 30 arcsec (standardized for all instruments)
            match_radius_arcsec = 30
            logger.info(f"Gaia cross-matching with Vizier (two-stage: 10\" + 100\" fallback)")

            # === CALCOLA OFFSET E CALIBRATION_DIFF da prime 5 stelle ===
            logger.info(f"Calculating offset and calibration_diff from first 5 stars...")
            offset, calibration_diff = self._calculate_magnitude_offset_from_sample(stars_valid, match_radius_arcsec)

            # Se il calcolo fallisce, blocca tutto
            if offset is None or calibration_diff is None:
                logger.error("Offset/calibration_diff calculation failed - differences in sample stars were NOT coherent")
                stars_df['gaia_source_id'] = None
                stars_df['gaia_gmag'] = None
                stars_df['gaia_bp_rp'] = None
                stars_df['gaia_vmag'] = None
                return stars_df

            logger.info(f"Offset (mean Vmag): {offset:.2f} mag, Calibration diff: {calibration_diff:.2f} mag")

            # Salva i valori di calibrazione nel job (per retry successivi)
            job.calibration_offset = offset
            job.calibration_diff = calibration_diff
            db.commit()

            # === PARALLELO: ProcessPoolExecutor con 4 worker ===
            all_matches = []
            logger.info(f"Starting parallel Gaia queries (4 workers, {len(stars_valid)} stars)")

            with ThreadPoolExecutor(max_workers=4) as executor:
                # Submit tutti i job ai worker
                # Parametri: (name, ra, dec, match_radius_arcsec, vast_mag, offset, calibration_diff)
                futures = {
                    executor.submit(_gaia_worker_query_single_star, (row['name'], row['ra'], row['dec'], match_radius_arcsec, row['Median_magnitude'], offset, calibration_diff)): idx
                    for idx, (_, row) in enumerate(stars_valid.iterrows())
                }

                # Raccogli risultati man mano che arrivano
                completed = 0
                for future in as_completed(futures):
                    completed += 1
                    try:
                        result = future.result()
                        if result['status'] == 'match':
                            all_matches.append(result)
                            logger.debug(f"[{completed}/{len(stars_valid)}] {result['name']} → Gaia match")
                        elif result['status'] == 'ambiguous':
                            # Aggiungi il match ambiguo (gaia_source_id sarà None, è_ambiguous=True)
                            all_matches.append(result)
                            logger.debug(f"[{completed}/{len(stars_valid)}] {result['name']} → Gaia AMBIGUOUS (Stage 2 fallback)")
                        elif result['status'] == 'no_match':
                            logger.debug(f"[{completed}/{len(stars_valid)}] {result['name']} → no match")
                        else:  # error
                            logger.debug(f"[{completed}/{len(stars_valid)}] {result['name']} → error: {result.get('error', 'unknown')}")

                    except Exception as e:
                        logger.warning(f"Worker exception: {e}")

            # === MERGE RISULTATI ===
            if len(all_matches) > 0:
                gaia_match_df = pd.DataFrame(all_matches)
                # Seleziona colonne di interesse (incluso is_ambiguous e gaia_candidates)
                gaia_columns = ['name', 'gaia_source_id', 'gaia_ra', 'gaia_dec', 'gaia_gmag', 'gaia_bp_rp', 'gaia_vmag', 'is_ambiguous', 'gaia_candidates']
                # Prendi solo le colonne che esistono
                gaia_columns = [col for col in gaia_columns if col in gaia_match_df.columns]
                gaia_match_df = gaia_match_df[gaia_columns]
                # Assicura che gaia_source_id sia INT64 (non float), per stelle ambiguous sarà None
                gaia_match_df['gaia_source_id'] = gaia_match_df['gaia_source_id'].astype('Int64')
                # Assicura che is_ambiguous sia bool
                if 'is_ambiguous' in gaia_match_df.columns:
                    gaia_match_df['is_ambiguous'] = gaia_match_df['is_ambiguous'].astype(bool)

                # IMPORTANTE: Normalizza i nomi per il merge!
                # Il dataframe principale ha nomi come 'out31321.dat'
                # Il gaia_match_df ha nomi come 'out31321.dat' (ricevuti dai worker)
                # Ma devi assicurare che siano identici
                stars_df = pd.merge(stars_df, gaia_match_df, how='left', on='name')
                match_rate = 100 * len(gaia_match_df) / len(stars_valid)
                logger.info(f"🔗 Gaia cross-match: {len(gaia_match_df)}/{len(stars_valid)} matches found ({match_rate:.1f}%)")

                # DEBUG: Check out31321
                out31321_row = stars_df[stars_df['name'] == 'out31321']
                if not out31321_row.empty:
                    out31321_gaia = out31321_row['gaia_source_id'].iloc[0]
                    debug_msg = f"[CROSSMATCH DEBUG] out31321 after merge: gaia_source_id={out31321_gaia}"
                    logger.info(debug_msg)
                    with open('/tmp/vast_debug.log', 'a') as f:
                        f.write(debug_msg + '\n')

                # === MAGNITUDE SCALING ===
                # Scala magnitudini VAST usando Vmag come riferimento
                logger.info("🔄 Scaling VAST magnitudes using Gaia Vmag as reference...")
                self._scale_vast_magnitudes(stars_df)

            else:
                logger.warning("Gaia cross-match: 0 matches found")
                stars_df['gaia_source_id'] = None
                stars_df['gaia_gmag'] = None
                stars_df['gaia_bp_rp'] = None
                stars_df['gaia_vmag'] = None

        except Exception as e:
            logger.error(f"Gaia cross-match failed: {e}", exc_info=True)
            stars_df['gaia_source_id'] = None
            stars_df['gaia_gmag'] = None
            stars_df['gaia_bp_rp'] = None
            stars_df['gaia_vmag'] = None

        return stars_df

    def _scale_vast_magnitudes(self, stars_df: pd.DataFrame) -> None:
        """
        Scala magnitudini VAST usando Gaia Vmag come riferimento.

        VAST riporta magnitudini strumentali (negative, dipendenti da calibrazione).
        Questo metodo:
        1. Calcola offset medio: avg(VAST_mag - Gaia_Vmag) per stelle con match Gaia
        2. Applica offset a TUTTE le stelle: mag_calibrated = mag - avg_offset
        3. Valida coerenza tra magnitudini calibrate e Gaia Vmag

        Args:
            stars_df: DataFrame con colonne 'Median_magnitude' e 'gaia_vmag'
        """
        try:
            # Filtra stelle con match Gaia e Vmag valido
            matched = stars_df[
                (stars_df['gaia_vmag'].notna()) &
                (stars_df['Median_magnitude'].notna())
            ].copy()

            if len(matched) == 0:
                logger.warning("No matched stars with valid Vmag, skipping magnitude scaling")
                return

            # Calcola offset medio
            matched['offset'] = matched['Median_magnitude'] - matched['gaia_vmag']
            mean_offset = matched['offset'].mean()
            std_offset = matched['offset'].std()

            logger.info(
                f"Magnitude offset (VAST - Gaia Vmag): "
                f"mean={mean_offset:.4f}, std={std_offset:.4f} ({len(matched)} stars)"
            )

            # Applica offset a tutte le stelle
            stars_df['mag_calibrated'] = (
                stars_df['Median_magnitude'] - mean_offset
            )

            # Sostituisci magnitudini strumentali con calibrate
            stars_df['Median_magnitude'] = stars_df['mag_calibrated']
            stars_df = stars_df.drop(columns=['mag_calibrated'])

            logger.info(f"✅ Magnitude scaling applied to {len(stars_df)} stars")

            # === VALIDAZIONE POST-CALIBRAZIONE ===
            # Verifica coerenza tra magnitudini calibrate VAST e Gaia Vmag
            valid_matches = 0
            inconsistent_matches = 0
            tolerance_mag = 0.5  # Tolleranza post-calibrazione (più stretta)

            for idx, row in matched.iterrows():
                if pd.notna(row['Median_magnitude']) and pd.notna(row['gaia_vmag']):
                    mag_diff = abs(row['Median_magnitude'] - row['gaia_vmag'])

                    if mag_diff < tolerance_mag:
                        valid_matches += 1
                    else:
                        inconsistent_matches += 1
                        logger.debug(
                            f"Magnitude inconsistency for {row['name']}: "
                            f"VAST_cal={row['Median_magnitude']:.2f}, Gaia_Vmag={row['gaia_vmag']:.2f}, "
                            f"diff={mag_diff:.2f} mag"
                        )

            if inconsistent_matches > 0:
                consistency_pct = 100 * valid_matches / (valid_matches + inconsistent_matches)
                logger.warning(
                    f"Magnitude consistency check: {valid_matches} consistent, "
                    f"{inconsistent_matches} inconsistent ({consistency_pct:.1f}% match rate)"
                )
            else:
                logger.info(f"✅ All {valid_matches} calibrated magnitudes are consistent with Gaia")

        except Exception as e:
            logger.error(f"Magnitude scaling failed: {e}", exc_info=True)

    # =========================================================================
    # STEP 7: Vizier Cross-Match (VSX + ATLAS)
    # =========================================================================

    def _crossmatch_vizier(
        self,
        stars_df: pd.DataFrame,
        job: VastJob,
        db
    ) -> pd.DataFrame:
        """
        Cross-match con VSX (B/vsx/vsx) e ATLAS (J/AJ/156/241/table4) via Vizier.

        Cone search attorno al centro campo, poi match posizionale.
        """
        try:
            import astropy.units as u
            import astropy.coordinates as coord
            from astropy.coordinates import match_coordinates_sky, Angle
            from astroquery.vizier import Vizier
        except ImportError:
            logger.warning("astroquery not installed, skipping Vizier cross-match")
            return stars_df

        # Verifica coordinate campo
        ra_center = stars_df['_ra_center'].iloc[0] if '_ra_center' in stars_df.columns else 0
        dec_center = stars_df['_dec_center'].iloc[0] if '_dec_center' in stars_df.columns else 0

        if ra_center == 0 and dec_center == 0:
            logger.warning("No field center coordinates, skipping Vizier cross-match")
            return stars_df

        # Verifica coordinate stelle
        if stars_df['ra'].eq(0.0).all():
            logger.warning("All RA=0, skipping Vizier cross-match")
            return stars_df

        job.current_step = 'Cross-matching with VSX and ATLAS'
        db.commit()

        # TESS ha campo piu' ampio
        is_tess = 'tess' in (job.target_name or '').lower()
        search_angle = 8 * u.deg if is_tess else 1 * u.deg
        max_sep = (125 if is_tess else 25) * u.arcsec

        Vizier.ROW_LIMIT = -1

        try:
            center = coord.SkyCoord(
                ra=ra_center, dec=dec_center, unit=(u.deg, u.deg)
            )

            catalogs = Vizier.query_region(
                center,
                radius=Angle(search_angle),
                catalog=["B/vsx/vsx", "J/AJ/156/241/table4"]
            )

            if catalogs is None or len(catalogs) == 0:
                logger.info("No Vizier catalogs returned for this field")
                return stars_df

            # Crea SkyCoord con unità esplicite (DEG, not radians!)
            coo_all = coord.SkyCoord(
                ra=stars_df['ra'].values * u.deg,
                dec=stars_df['dec'].values * u.deg
            )

            for cat in catalogs:
                cat_name = cat.meta.get('name', '')

                coo = coord.SkyCoord(
                    ra=cat['RAJ2000'], dec=cat['DEJ2000'],
                    unit=(u.deg, u.deg), frame='icrs'
                )
                idx, d2d, _ = match_coordinates_sky(coo_all, coo, 1)
                mask = d2d < max_sep

                matched_cat = cat[idx[mask]]
                matched_cat['name'] = stars_df[mask]['name'].values
                df_cat = matched_cat.to_pandas()

                if 'B/vsx/vsx' in cat_name or cat_name == 'B/vsx/vsx':
                    # VSX catalog matching
                    stars_df = pd.merge(
                        stars_df,
                        df_cat[['OID', 'name', 'Type']],
                        how='left', on='name'
                    )
                    logger.info(f"VSX: {mask.sum()} matches")

                elif 'table4' in cat_name or 'J/AJ/156/241' in cat_name:
                    # ATLAS catalog matching
                    stars_df = pd.merge(
                        stars_df,
                        df_cat[['ATOID', 'name', 'Class']],
                        how='left', on='name'
                    )
                    logger.info(f"ATLAS: {mask.sum()} matches")

        except Exception as e:
            logger.error(f"Vizier cross-match failed: {e}", exc_info=True)
            # Non-fatal

        return stars_df

    # =========================================================================
    # STEP 4.5: Magnitude Calibration using VAST utilities
    # =========================================================================

    def _run_magnitude_calibration(
        self,
        vast_dir: str,
        job: VastJob,
        db
    ) -> str:
        """
        Esegue magnitude_calibration.sh V da /opt/vast.

        Returns:
            Path al file .cat.ucac5 se trovato, altrimenti None
        """
        try:
            import subprocess

            vast_home = '/opt/vast'
            logger.info(f"Running magnitude calibration from {vast_home}")

            # Lancia util/magnitude_calibration.sh V
            cmd = 'util/magnitude_calibration.sh V'

            result = subprocess.run(
                cmd,
                shell=True,
                cwd=vast_home,
                capture_output=True,
                text=True,
                timeout=3600
            )

            logger.info(f"magnitude_calibration.sh return code: {result.returncode}")

            # Se il file è stato creato, lo usiamo indipendentemente dal return code
            # (PGPLOT error al fine non importa se il file esiste)
            logger.info(f"Searching for .cat.ucac5 files in {vast_home}")

            ucac5_file = None
            files_found = []
            for file_name in os.listdir(vast_home):
                if '.cat.ucac5' in file_name:
                    files_found.append(file_name)
                if file_name.endswith('.cat.ucac5'):
                    ucac5_file = os.path.join(vast_home, file_name)
                    logger.info(f"Found UCAC5 catalog: {os.path.basename(ucac5_file)}")
                    return ucac5_file

            logger.warning(f"No UCAC5 catalog file found. Files with .cat.ucac5: {files_found}")
            return None

        except subprocess.TimeoutExpired:
            logger.error("magnitude_calibration.sh timed out")
            return None
        except Exception as e:
            logger.error(f"Magnitude calibration failed: {e}", exc_info=True)
            return None

    def _read_vast_catalog_ucac5(
        self,
        ucac5_catalog: str,
        stars_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Legge il file .cat.ucac5 prodotto da VAST magnitude_calibration.sh.

        Formato: spazi separati con colonne:
        ID RA Dec MAG_other_columns...

        Aggiunge/aggiorna RA e Dec nel DataFrame stella da coordinate
        già calibrate da VAST.
        """
        try:
            import re

            logger.info(f"Reading VAST UCAC5 catalog: {ucac5_catalog}")

            # Leggi il file .cat.ucac5
            # Formato: space-separated, prima colonna = ID stella
            catalog_data = {}

            with open(ucac5_catalog, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    parts = line.split()
                    if len(parts) < 3:
                        continue

                    try:
                        # Prima colonna = ID numerico (1, 33245, 17950, ...)
                        star_id_num = int(parts[0])
                        # Converte a formato VAST: "out" + numero zero-padded (out00001, out33245, ...)
                        star_name = f"out{star_id_num:05d}"
                        ra = float(parts[1])
                        dec = float(parts[2])

                        catalog_data[star_name] = {
                            'ra': ra,
                            'dec': dec
                        }
                    except (ValueError, IndexError) as e:
                        logger.debug(f"Skipping line {line_num}: {e}")
                        continue

            logger.info(f"Loaded {len(catalog_data)} stars from UCAC5 catalog")

            # DEBUG: Show sample of loaded data
            if catalog_data:
                sample_ids = list(catalog_data.keys())[:3]
                for sample_id in sample_ids:
                    logger.debug(f"Sample catalog entry: id={sample_id}, data={catalog_data[sample_id]}")

            # DEBUG: Show sample of DataFrame names
            if len(stars_df) > 0:
                sample_names = stars_df['name'].head(3).tolist()
                logger.debug(f"Sample DataFrame names: {sample_names}")

            # Mergia i dati nel DataFrame
            # Map from VAST star ID to RA/Dec from UCAC5
            ra_values = []
            dec_values = []

            matched_count = 0

            for idx, row in stars_df.iterrows():
                star_name = row['name']
                # Rimuovi .dat dalla fine se presente (es: out43507.dat -> out43507)
                star_name_clean = star_name.replace('.dat', '') if star_name.endswith('.dat') else star_name

                if star_name_clean in catalog_data:
                    ra_values.append(catalog_data[star_name_clean]['ra'])
                    dec_values.append(catalog_data[star_name_clean]['dec'])
                    matched_count += 1
                else:
                    # Se non trovato nel catalog, mantieni i valori precedenti (0.0 default)
                    ra_values.append(row.get('ra', 0.0))
                    dec_values.append(row.get('dec', 0.0))

            stars_df['ra'] = ra_values
            stars_df['dec'] = dec_values

            # Conta quanti match hanno trovato coordinate valide
            valid_coords = (stars_df['ra'] != 0.0) & (stars_df['dec'] != 0.0)
            logger.info(
                f"UCAC5 mapping: {matched_count} direct name matches, "
                f"{valid_coords.sum()}/{len(stars_df)} total with valid coordinates"
            )

            return stars_df

        except Exception as e:
            logger.error(f"Failed to read UCAC5 catalog: {e}", exc_info=True)
            # Ritorna il DataFrame originale con fallback
            return stars_df

    # =========================================================================
    # STEP 8: Detect Known Variables
    # =========================================================================

    def _detect_known_variables(self, stars_df: pd.DataFrame) -> pd.DataFrame:
        """
        Determina variabili note da flag Gaia e match VSX.

        Logica (da analisiVastEstesa):
        1. Costruisce stringa catalogo con cataloghi matchati
        2. Verifica flag variabilita' Gaia (VCR, VRRLyr, VCep, etc.)
        3. Se flag Gaia attivo, sovrascrive Type con nome flag
        4. Se Type valorizzato, sovrascrive Class con Type
        """
        # Costruisci stringa catalogo
        stars_df['catalog_matches'] = ''

        if 'Source' in stars_df.columns:
            stars_df['catalog_matches'] = np.where(
                stars_df['Source'].notna(), 'Gaia', ''
            )
        if 'ATOID' in stars_df.columns:
            stars_df['catalog_matches'] = np.where(
                stars_df['ATOID'].notna(),
                stars_df['catalog_matches'] + ',Atlas',
                stars_df['catalog_matches']
            )
        if 'OID' in stars_df.columns:
            stars_df['catalog_matches'] = np.where(
                stars_df['OID'].notna(),
                stars_df['catalog_matches'] + ',AAVSO',
                stars_df['catalog_matches']
            )
        # Pulisci virgole iniziali
        stars_df['catalog_matches'] = stars_df['catalog_matches'].str.lstrip(',')

        # Flag variabilita' Gaia -> variable_type
        stars_df['_var_type_gaia'] = pd.NA
        for var_flag in GAIA_VAR_FLAGS:
            if var_flag in stars_df.columns:
                stars_df.loc[
                    stars_df[var_flag].eq(1), '_var_type_gaia'
                ] = var_flag

        # Combina: VSX Type ha precedenza, poi Gaia variability
        stars_df['variable_type'] = pd.NA
        if 'Type' in stars_df.columns:
            stars_df['variable_type'] = stars_df['Type']
        # Gaia variability come fallback dove Type manca
        mask_no_type = stars_df['variable_type'].isna()
        mask_has_gaia = stars_df['_var_type_gaia'].notna()
        stars_df.loc[mask_no_type & mask_has_gaia, 'variable_type'] = (
            stars_df.loc[mask_no_type & mask_has_gaia, '_var_type_gaia']
        )

        # is_known_variable: True se matchato in VSX o ha flag variabilita' Gaia (esclude ATLAS)
        has_vsx = stars_df['OID'].notna() if 'OID' in stars_df.columns else pd.Series(False, index=stars_df.index)
        has_gaia_var = stars_df['_var_type_gaia'].notna()
        # ATLAS (ATOID) NON conta per "variabili note"
        stars_df['is_known_variable'] = has_vsx | has_gaia_var

        known_count = stars_df['is_known_variable'].sum()
        logger.info(f"Known variables detected: {known_count}")

        # Cleanup colonne temporanee
        stars_df.drop(columns=['_var_type_gaia'], inplace=True, errors='ignore')

        return stars_df

    # =========================================================================
    # STEP 9a: Build Candidates List
    # =========================================================================

    def _build_candidates_list(
        self, stars_df: pd.DataFrame, vast_dir: str
    ) -> list:
        """
        Converte DataFrame arricchito in lista di dict per upload.

        Per ogni stella:
        - Pack tutti gli indici idx* in un JSON dict
        - Conta osservazioni dal file .dat
        - Costruisce JSON per gaia_match, vsx_match, atlas_match
        """
        candidates = []

        for _, row in stars_df.iterrows():

            # Pack tutti i 31 indici di variabilita' in JSON
            var_indices = {}
            for col in VARIABILITY_INDEX_COLUMNS:
                if col in row.index and pd.notna(row[col]):
                    var_indices[col] = float(row[col])

            # Conta osservazioni dal file .dat
            dat_file = os.path.join(vast_dir, row['name'])
            num_obs = 0
            if os.path.exists(dat_file):
                with open(dat_file, 'r') as f:
                    num_obs = sum(1 for line in f if line.strip())

            # Gaia match JSON (dalle colonne di cross-match Gaia)
            gaia_match = None
            if 'gaia_source_id' in row.index and pd.notna(row.get('gaia_source_id')):
                gaia_match = {
                    'source_id': int(row['gaia_source_id']) if pd.notna(row.get('gaia_source_id')) else None,
                    'ra': float(row['gaia_ra']) if pd.notna(row.get('gaia_ra')) else None,
                    'dec': float(row['gaia_dec']) if pd.notna(row.get('gaia_dec')) else None,
                    'gmag': float(row['gaia_gmag']) if pd.notna(row.get('gaia_gmag')) else None,
                    'bp_rp': float(row['gaia_bp_rp']) if pd.notna(row.get('gaia_bp_rp')) else None,
                }

            # VSX match JSON
            vsx_match = None
            if 'OID' in row.index and pd.notna(row.get('OID')):
                vsx_match = {
                    'oid': str(row['OID']),
                    'type': str(row['Type']) if pd.notna(row.get('Type')) else None,
                }

            # ATLAS match JSON
            atlas_match = None
            if 'ATOID' in row.index and pd.notna(row.get('ATOID')):
                atlas_match = {
                    'atoid': str(row['ATOID']),
                    'class': str(row['Class']) if pd.notna(row.get('Class')) else None,
                }

            # Gaia source ID per campo dedicato (dalle colonne di cross-match Gaia)
            gaia_source_id = None
            if 'gaia_source_id' in row.index and pd.notna(row.get('gaia_source_id')):
                # Converti da Int64 (pandas nullable) a Python int se necessario
                val = row['gaia_source_id']
                if pd.notna(val):
                    gaia_source_id = int(val)

            # DEBUG for out31321
            star_name = row['name'].replace('.dat', '')
            if star_name == 'out31321':
                debug_msg = f"[DEBUG] out31321: gaia_source_id={gaia_source_id}, gaia_vmag={row.get('gaia_vmag')}, ra={row.get('ra'):.7f}, dec={row.get('dec'):.7f}"
                logger.info(debug_msg)
                # Scrivi su file per verificare
                with open('/tmp/vast_debug.log', 'a') as f:
                    f.write(debug_msg + '\n')

            candidate = {
                'vast_id': star_name,
                'ra': float(row.get('ra', 0.0)),
                'dec': float(row.get('dec', 0.0)),
                'x_pix': float(row.get('x', 0.0)),
                'y_pix': float(row.get('y', 0.0)),
                'mean_mag': float(row.get('Median_magnitude', 0.0)),
                'std_dev': float(row.get('idx00_STD', 0.0)),
                'num_obs': num_obs,
                'variability_index': (
                    float(row['idx04_I']) if pd.notna(row.get('idx04_I')) else None
                ),
                'chi_squared': (
                    float(row['idx12_rCh2']) if pd.notna(row.get('idx12_rCh2')) else None
                ),
                'variability_indices': var_indices if var_indices else None,
                'is_valid': True,  # Tutti i candidati caricati sono validi (FRACTION_OF già scartati)
                'is_known_variable': bool(row.get('is_known_variable', False)),
                'variable_type': (
                    str(row['variable_type'])
                    if pd.notna(row.get('variable_type')) else None
                ),
                'catalog_matches': (
                    str(row['catalog_matches'])
                    if row.get('catalog_matches') else None
                ),
                'candidate_flag': 'vast_candidate',  # Flag che indica provenienza VAST
                'vmag': (
                    float(row['gaia_vmag']) if pd.notna(row.get('gaia_vmag')) else None
                ),
                'gaia_source_id': gaia_source_id,
                # is_ambiguous deve essere False se non c'è gaia_source_id (no match, non ambiguous)
                'is_ambiguous': bool(row.get('is_ambiguous', False)) if gaia_source_id is not None else False,
                'gaia_match': gaia_match,
                'vsx_match': vsx_match,
                'atlas_match': atlas_match,
            }

            candidates.append(candidate)

        logger.info(f"Built {len(candidates)} candidate records for upload")
        return candidates

    # =========================================================================
    # STEP 9b: Upload Results to DB
    # =========================================================================

    def _upload_results(
        self,
        vast_results: dict,
        job: VastJob,
        db
    ):
        """Upload tutte le stelle nel database."""

        candidates = vast_results.get('candidates', [])

        if not candidates:
            logger.info(f"No candidates to upload for job {job.job_code}")
            job.stars_uploaded = 0
            job.progress_pct = 95
            db.commit()
            return

        logger.info(f"Uploading {len(candidates)} stars for job {job.job_code}")

        try:
            for idx, candidate in enumerate(candidates):
                result = VastResult(
                    job_id=job.id,
                    vast_id=candidate.get('vast_id'),
                    gaia_source_id=candidate.get('gaia_source_id'),
                    ra=float(candidate.get('ra', 0)),
                    decl=float(candidate.get('dec', 0)),
                    x_pix=candidate.get('x_pix'),
                    y_pix=candidate.get('y_pix'),
                    mean_mag=candidate.get('mean_mag'),
                    mag_err=candidate.get('mag_err'),
                    std_dev=candidate.get('std_dev'),
                    num_observations=candidate.get('num_obs'),
                    variability_index=candidate.get('variability_index'),
                    chi_squared=candidate.get('chi_squared'),
                    period=candidate.get('period'),
                    # Nuovi campi
                    variability_indices=candidate.get('variability_indices'),
                    is_valid=candidate.get('is_valid', True),
                    is_known_variable=candidate.get('is_known_variable', False),
                    is_ambiguous=candidate.get('is_ambiguous', False),
                    variable_type=candidate.get('variable_type'),
                    catalog_matches=candidate.get('catalog_matches'),
                    vmag=candidate.get('vmag'),
                    candidate_flag=candidate.get('candidate_flag'),
                    # Cross-match JSON
                    gaia_match=candidate.get('gaia_match'),
                    vsx_match=candidate.get('vsx_match'),
                    atlas_match=candidate.get('atlas_match'),
                )

                db.add(result)

                # Commit in batch per performance
                if (idx + 1) % 100 == 0:
                    db.commit()
                    logger.debug(f"Committed {idx + 1} results")

            db.commit()

            job.stars_uploaded = len(candidates)
            job.progress_pct = 95
            db.commit()

            # Batch UPDATE agata_star VAST fields for all uploaded stars (best-effort)
            try:
                vast_gaia_ids = [
                    str(c.get('gaia_source_id'))
                    for c in candidates
                    if c.get('gaia_source_id') is not None
                ]
                if vast_gaia_ids:
                    for gid in vast_gaia_ids:
                        db.execute(text("""
                            UPDATE agata_star SET
                                is_known_variable = (
                                    SELECT COALESCE(MAX(is_known_variable), 0)
                                    FROM agata_vast_results
                                    WHERE gaia_source_id::text = :gid AND is_valid = 1
                                ),
                                variable_types = (
                                    SELECT STRING_AGG(DISTINCT variable_type, ',')
                                    FROM agata_vast_results
                                    WHERE gaia_source_id::text = :gid AND is_valid = 1
                                ),
                                catalog_matches = (
                                    SELECT STRING_AGG(DISTINCT catalog_matches, ',')
                                    FROM agata_vast_results
                                    WHERE gaia_source_id::text = :gid AND is_valid = 1
                                ),
                                updated_at = NOW()
                            WHERE gaia_id = :gid
                        """), {'gid': gid})
                    db.commit()
            except Exception as _vast_err:
                logger.warning(f"agata_star VAST fields update failed: {_vast_err}")

            logger.info(f"Uploaded {len(candidates)} stars for job {job.job_code}")

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to upload results: {e}", exc_info=True)
            raise

    # =========================================================================
    # STEP 10: Preserve .dat files
    # =========================================================================

    def _preserve_dat_files(
        self,
        stars_df: pd.DataFrame,
        vast_dir: str,
        job: VastJob
    ):
        """
        Copia i file .dat (curve di luce strumentali) dalla directory VAST
        a una directory persistente per permettere la promozione successiva.

        I file .dat vengono sovrascritti ad ogni esecuzione VAST, quindi devono
        essere preservati subito dopo il completamento dell'analisi.
        """
        dest_dir = os.path.join(VAST_DAT_STORAGE, job.job_code)
        os.makedirs(dest_dir, exist_ok=True)

        copied = 0
        for _, row in stars_df.iterrows():
            dat_name = row.get('name', '')
            if not dat_name:
                continue

            src = os.path.join(vast_dir, dat_name)
            if os.path.exists(src):
                dst = os.path.join(dest_dir, dat_name)
                shutil.copy2(src, dst)
                copied += 1

        # Salva info nel job
        if job.output_files:
            job.output_files['dat_dir'] = dest_dir
            job.output_files['dat_count'] = copied
        else:
            job.output_files = {'dat_dir': dest_dir, 'dat_count': copied}

        logger.info(f"Preserved {copied} .dat files to {dest_dir}")

    # =========================================================================
    # PROMOTION: Transfer to agata_star_photometry + Create Projects
    # =========================================================================

    def promote_job_results(
        self,
        job_id: int,
        association_id: int,
        user_id: str,
        user_email: str,
        only_known_variables: bool = False,
        only_candidates: bool = False,
        result_ids: list = None
    ) -> dict:
        """
        Promuove i risultati VAST a agata_star_photometry (import bulk).
        Legge i file .dat e inserisce le curve di luce, rendendo i dati
        disponibili per l'assegnazione alle associazioni.

        Per ogni stella valida con Gaia source ID:
        1. Legge il file .dat (JD + magnitudine strumentale)
        2. Calibra la magnitudine usando l'offset Vmag
        3. Inserisce i dati in agata_star_photometry (VAST catalog)

        NOTA: NON crea progetti automaticamente.
        Le associazioni riceveranno le stelle e potranno creare progetti
        quando decideranno di analizzarle (workflow a due step).

        Args:
            job_id: ID del job VAST completato
            association_id: IGNORATO (legacy parameter, kept for API compatibility)
            user_id: ID utente che promuove
            user_email: Email utente per audit
            only_known_variables: Se True, promuove solo variabili note
            only_candidates: Se True, promuove solo candidate VAST
            result_ids: Se specificato, promuove solo questi result IDs. Se None, promuove tutti gli eligible.

        Returns:
            dict con statistiche: stars_promoted, lightcurve_points, errors
        """
        db = SessionLocal()
        stats = {
            'stars_promoted': 0,
            'lightcurve_points': 0,
            'skipped_no_gaia': 0,
            'skipped_known_variables': 0,
            'errors': []
        }

        try:
            job = db.query(VastJob).get(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")

            if job.state != 'completed':
                raise ValueError(
                    f"Job must be completed to promote (current state: {job.state})"
                )

            # Directory con i .dat preservati
            dat_dir = None
            if job.output_files:
                dat_dir = job.output_files.get('dat_dir')

            if not dat_dir or not os.path.isdir(dat_dir):
                raise FileNotFoundError(
                    f"Preserved .dat files not found. "
                    f"Expected at: {dat_dir or 'not set'}"
                )

            # Carica risultati dal DB
            results = db.query(VastResult).filter(
                VastResult.job_id == job_id
            ).all()

            if not results:
                raise ValueError("No results found for this job")

            # Filtra in base alle opzioni
            eligible = []
            skipped_known = 0
            for r in results:
                if not r.is_valid:
                    continue  # Skip FRACTION_OF
                if not r.gaia_source_id:
                    stats['skipped_no_gaia'] += 1
                    continue
                if only_known_variables and r.is_known_variable:
                    # Esclude variabili note (skip)
                    skipped_known += 1
                    continue
                if only_candidates and not r.candidate_flag:
                    continue
                # Se specificati result_ids, limita solo a quelli
                if result_ids is not None and r.id not in result_ids:
                    continue
                eligible.append(r)

            stats['skipped_known_variables'] = skipped_known

            logger.info(
                f"Promoting {len(eligible)} stars from job {job.job_code} "
                f"(total results: {len(results)}, "
                f"skipped no gaia: {stats['skipped_no_gaia']}, "
                f"skipped known vars: {skipped_known})"
            )

            # Crea record CatalogImport per tracciabilità
            # Nome catalogo: usa target_name se disponibile, altrimenti job_code (senza prefisso VAST)
            catalog_display_name = job.target_name if job.target_name else job.job_code

            import_record = create_import_record(
                db=db,
                catalog_name=catalog_display_name,
                search_type='file',  # Enum: coordinates, gaia_id, name, file
                search_value=job.job_code,  # Job code as identifier
                ra=None,
                dec=None,
                radius_arcsec=0,
                gaia_id=None,
                user_id=user_id,
                state='importing'  # Enum: pending, searching, preview, importing, completed, failed, cancelled
            )
            logger.info(f"Created CatalogImport #{import_record.id} for VAST job {job.job_code}")

            # Calcola offset calibrazione magnitudine
            # IMPORTANTE: mean_mag nel DB è già calibrato, ma i .dat files hanno magnitudini strumentali
            # Dobbiamo calcolare l'offset leggendo i valori ORIGINALI dai .dat files
            mag_offsets = []
            for r in eligible:
                if r.vmag:
                    # Leggi magnitudine strumentale dal .dat file
                    dat_name = (r.vast_id or '').strip()
                    if not dat_name.endswith('.dat'):
                        dat_name += '.dat'
                    dat_path = os.path.join(dat_dir, dat_name)

                    if os.path.exists(dat_path):
                        try:
                            # Leggi prima riga del .dat per ottenere mag strumentale
                            with open(dat_path, 'r') as f:
                                first_line = f.readline().strip()
                                if first_line:
                                    parts = first_line.split()
                                    if len(parts) >= 2:
                                        instrumental_mag = float(parts[1])
                                        mag_offsets.append(instrumental_mag - r.vmag)
                        except (ValueError, IOError) as e:
                            logger.debug(f"Could not read instrumental mag from {dat_name}: {e}")

            if mag_offsets:
                mag_offset = np.mean(mag_offsets)
                logger.info(
                    f"Magnitude calibration offset: {mag_offset:.4f} "
                    f"(from {len(mag_offsets)} stars with Vmag)"
                )
            else:
                mag_offset = 0.0
                logger.warning(
                    "No stars with Vmag for calibration, using zero offset"
                )

            # Promuovi ogni stella
            for r in eligible:
                try:
                    gaia_id_str = str(r.gaia_source_id)

                    # 1. Leggi .dat file e calibra magnitudini
                    dat_name = (r.vast_id or '').strip()
                    if not dat_name.endswith('.dat'):
                        dat_name += '.dat'

                    dat_path = os.path.join(dat_dir, dat_name)
                    points_inserted = 0

                    if os.path.exists(dat_path):
                        lc_data = self._read_dat_file(dat_path, mag_offset)
                        if not lc_data.empty:
                            # Usa il nome del catalogo dall'import_record
                            catalog_name = (
                                import_record.selected_catalogs[0]
                                if import_record.selected_catalogs else 'VAST'
                            )
                            points_inserted = insert_catalog_data(
                                db=db,
                                gaia_id=gaia_id_str,
                                catalog_name=catalog_name,
                                data=lc_data,
                                association_id_owner=None,  # Dati centrali
                                catalog_import_id=import_record.id  # Tracciamento
                            )
                            stats['lightcurve_points'] += points_inserted

                            # HOOK: Populate agata_star cache with new photometry
                            if points_inserted > 0:
                                _upsert_star_photometry(db, gaia_id_str)
                    else:
                        logger.warning(
                            f"DAT file not found: {dat_path} "
                            f"for star {r.vast_id}"
                        )

                    # Stella promossa (NON creiamo progetti automaticamente)
                    stats['stars_promoted'] += 1

                except Exception as e:
                    error_msg = f"Error promoting star {r.vast_id}: {e}"
                    logger.error(error_msg, exc_info=True)
                    stats['errors'].append(error_msg)

            # Aggiorna job con info promozione
            if job.output_files:
                job.output_files['promotion'] = {
                    'promoted_at': datetime.utcnow().isoformat(),
                    'promoted_by': user_email,
                    'association_id': association_id,
                    'stats': {
                        k: v for k, v in stats.items() if k != 'errors'
                    }
                }
            db.commit()

            # Aggiorna CatalogImport con risultati della ricerca
            update_import_with_results(
                db=db,
                import_record=import_record,
                catalog_name='VAST',
                success=True,
                point_count=stats['lightcurve_points'],
                error_message=None
            )
            logger.info(f"Updated CatalogImport #{import_record.id} with {stats['lightcurve_points']} points")

            # Finalizza CatalogImport
            finalize_import(
                db=db,
                import_record=import_record,
                points_imported=stats['lightcurve_points'],
                user_id=user_id,
                user_email=user_email,
                association_id=None,  # Non creiamo progetti automaticamente
                auto_create_project=False,
                catalog_name='VAST'
            )
            logger.info(f"Finalized CatalogImport #{import_record.id}")

            # Audit log
            log_audit(
                user_id=user_id,
                user_email=user_email,
                association_id=None,  # Promotion è globale, non di un'associazione
                action='vast_results_promoted',
                entity_type='vast_job',
                entity_id=str(job.id),
                new_value=f"{stats['stars_promoted']} stelle, "
                          f"{stats['lightcurve_points']} punti luce, "
                          f"import #{import_record.id}",
                description=(
                    f"Promoted VAST job {job.job_code} results to agata_star_photometry (import #{import_record.id}): "
                    f"{stats['stars_promoted']} stars, "
                    f"{stats['lightcurve_points']} lightcurve points"
                )
            )

            logger.info(
                f"Promotion complete for job {job.job_code}: "
                f"{stats['stars_promoted']} stars promoted to agata_star_photometry (import #{import_record.id}), "
                f"{stats['lightcurve_points']} lightcurve points"
            )

            # Aggiungi import_id al response
            stats['import_id'] = import_record.id
            return stats

        except Exception as e:
            db.rollback()
            logger.error(f"Promotion failed: {e}", exc_info=True)
            raise
        finally:
            db.close()

    def _read_dat_file(
        self, dat_path: str, mag_offset: float
    ) -> pd.DataFrame:
        """
        Legge un file .dat VAST (JD + magnitudine strumentale)
        e calibra le magnitudini.

        Formato .dat: space-separated
        - col 0: JD (Julian Date heliocentric)
        - col 1: magnitudine strumentale
        - cols 2+: errori, coordinate pixel, percorso FITS, etc. (ignorati)

        Args:
            dat_path: Percorso file .dat
            mag_offset: Offset da sottrarre (instrumental - Vmag)

        Returns:
            DataFrame con colonne [hjd, mag]
        """
        try:
            # read_csv con space separator, leggi solo le prime 2 colonne
            df = pd.read_csv(
                dat_path,
                sep=r'\s+',  # Qualsiasi whitespace
                header=None,
                usecols=[0, 1],
                names=['hjd', 'mag'],
                dtype={'hjd': float, 'mag': float},
                engine='python'
            )

            # Rimuovi righe non valide
            df = df.dropna(subset=['hjd', 'mag'])
            df = df[df['hjd'] > 0]

            # Calibra: magnitudine_calibrata = strumentale - offset
            if mag_offset != 0:
                df['mag'] = df['mag'] - mag_offset

            logger.debug(f"Read {len(df)} photometric points from {dat_path}")
            return df

        except Exception as e:
            logger.error(f"Error reading .dat file {dat_path}: {e}", exc_info=True)
            return pd.DataFrame(columns=['hjd', 'mag'])

    def _create_project_for_star(
        self,
        db,
        result: VastResult,
        association_id: int,
        user_id: str,
        user_email: str,
        job: VastJob
    ) -> Optional[Project]:
        """
        Crea un progetto agata_projects per una stella VAST se non esiste.

        Args:
            db: Sessione database
            result: VastResult con dati stella
            association_id: ID associazione
            user_id: ID utente
            user_email: Email utente
            job: VastJob padre

        Returns:
            Project creato o None se gia' esiste
        """
        gaia_id_str = str(result.gaia_source_id)

        # Verifica duplicati
        existing = db.query(Project).filter(
            Project.gaia_id == gaia_id_str,
            Project.association_id == association_id,
            Project.state != 'cancelled'
        ).first()

        if existing:
            logger.debug(
                f"Project already exists for Gaia ID {gaia_id_str}: "
                f"{existing.project_code}"
            )
            return None

        # Genera codice progetto
        project_code = generate_project_code(db)

        # Parametri stella da Gaia match
        teff = None
        radius = None
        color_bprp = None
        if result.gaia_match:
            teff = result.gaia_match.get('teff')
            radius = result.gaia_match.get('rad')
            color_bprp = result.gaia_match.get('bp_rp')

        project = Project(
            project_code=project_code,
            gaia_id=gaia_id_str,
            association_id=association_id,
            title=f"VAST: {job.target_name} - {gaia_id_str}",
            source='VAST',
            ra=result.ra if result.ra != 0 else None,
            dec_deg=result.decl if result.decl != 0 else None,
            magnitude=result.vmag,
            variable_type=result.variable_type,
            teff=teff,
            radius=radius,
            color_bprp=color_bprp,
            state='incoming'
        )

        db.add(project)
        db.flush()

        # Audit log
        log_audit(
            user_id=user_id,
            user_email=user_email,
            association_id=association_id,
            action='project_created_from_vast',
            entity_type='project',
            entity_id=str(project.id),
            new_value=project_code,
            description=(
                f"Project {project_code} created from VAST job "
                f"{job.job_code}, Gaia ID {gaia_id_str}"
            )
        )

        logger.info(
            f"Created project {project_code} for Gaia ID {gaia_id_str} "
            f"from VAST job {job.job_code}"
        )

        return project

    # =========================================================================
    # Query Methods (read-only)
    # =========================================================================

    def get_job_status(self, job_id: int) -> dict:
        """Get current job status."""
        db = SessionLocal()

        try:
            job = db.query(VastJob).get(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")

            response = {
                'job_code': job.job_code,
                'target_name': job.target_name,
                'state': job.state,
                'progress_pct': job.progress_pct,
                'current_step': job.current_step,
                'images_downloaded': job.images_downloaded,
                'images_solved': job.images_solved,
                'stars_uploaded': job.stars_uploaded,
                'error_message': job.error_message,
                'created_at': job.created_at.isoformat(),
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'duration_seconds': job.duration_seconds
            }

            # If job is completed, read metrics from cagg (faster + fresh)
            if job.state == 'completed':
                try:
                    metrics = db.session.execute(text("""
                        SELECT n_total, n_candidates, n_gaia_matched, n_vsx_matched,
                               mean_chi_squared, mean_variability_index
                        FROM vast_job_summary
                        WHERE job_id = :job_id
                    """), {'job_id': job_id}).first()

                    if metrics:
                        response.update({
                            'candidates_found': metrics[1],
                            'gaia_matched': metrics[2],
                            'vsx_matched': metrics[3],
                            'mean_chi_squared': float(metrics[4]) if metrics[4] else None,
                            'mean_variability_index': float(metrics[5]) if metrics[5] else None,
                        })
                    else:
                        # Fallback to job row if cagg not ready
                        response['candidates_found'] = job.candidates_found
                except Exception as e:
                    logger.warning(f"Could not read vast_job_summary cagg: {e}")
                    response['candidates_found'] = job.candidates_found
            else:
                response['candidates_found'] = job.candidates_found

            return response
        finally:
            db.close()

    def list_jobs(self, limit: int = 50, state: str = None) -> List[dict]:
        """
        Elenca job con filtri opzionali.

        Args:
            limit: Massimo numero di job da restituire
            state: Filtro stato opzionale

        Returns:
            Lista dict job
        """
        db = SessionLocal()

        try:
            query = db.query(VastJob).order_by(VastJob.created_at.desc())

            if state:
                query = query.filter(VastJob.state == state)

            jobs = query.limit(limit).all()

            return [
                {
                    'id': job.id,
                    'job_code': job.job_code,
                    'target_name': job.target_name,
                    'state': job.state,
                    'progress_pct': job.progress_pct,
                    'candidates_found': job.candidates_found,
                    'created_at': job.created_at.isoformat(),
                    'completed_at': job.completed_at.isoformat() if job.completed_at else None
                }
                for job in jobs
            ]

        finally:
            db.close()

    def retry_gaia_matching(
        self,
        job_id: int,
        result_ids: list,
        user_id: str,
        user_email: str
    ) -> dict:
        """
        Retry Gaia cross-matching for specific VastResult records.

        User requirement: Only calibrate newly matched stars, leave others unchanged.

        Args:
            job_id: VAST job ID
            result_ids: List of VastResult IDs to retry
            user_id: ID of user requesting retry
            user_email: Email of user (for logging)

        Returns:
            dict with stats: {retried_count, new_matches, still_unmatched}
        """
        db = SessionLocal()

        try:
            logger.info(
                f"[retry_gaia] Starting Gaia retry for job {job_id}, "
                f"{len(result_ids)} results, requested by {user_email}"
            )

            # 1. Validate job exists and is completed
            job = db.query(VastJob).filter(VastJob.id == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found")

            if job.state != 'completed':
                raise ValueError(f"Job {job_id} is not completed (state: {job.state})")

            # 2. Fetch VastResult records to retry
            results_to_retry = db.query(VastResult).filter(
                VastResult.id.in_(result_ids),
                VastResult.job_id == job_id,
                VastResult.gaia_source_id.is_(None)  # Only retry unmatched stars
            ).all()

            if not results_to_retry:
                logger.warning(f"[retry_gaia] No unmatched results found for IDs: {result_ids}")
                return {
                    'retried_count': 0,
                    'new_matches': 0,
                    'still_unmatched': 0
                }

            logger.info(f"[retry_gaia] Retrying {len(results_to_retry)} stars")

            # 3. Determine match radius (TESS vs ground-based)
            match_radius = 125  # Default TESS
            if job.target_name and 'tess' not in job.target_name.lower():
                match_radius = 25  # Ground-based

            # 4. Get calibration parameters from job
            if job.calibration_offset is None or job.calibration_diff is None:
                raise ValueError(
                    f"Job {job_id} does not have calibration parameters. "
                    f"Must retry after successful pre-phase calibration."
                )
            offset = job.calibration_offset
            calibration_diff = job.calibration_diff
            logger.info(f"[retry_gaia] Using saved calibration: offset={offset:.2f}, calibration_diff={calibration_diff:.2f}")

            # 5. Execute parallel Gaia queries
            new_matches = 0
            still_unmatched = 0

            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(
                        _gaia_worker_query_single_star,
                        # CRITICAL: For retry, mean_mag is already calibrated, so pass calibration_diff=0 to skip re-calibration
                        (r.vast_id, r.ra, r.decl, match_radius, r.mean_mag, offset, 0.0)
                    ): r
                    for r in results_to_retry
                }

                for future in as_completed(futures):
                    result = futures[future]
                    try:
                        match = future.result()

                        if match['status'] in ('match', 'ambiguous'):  # Accept both Stage 1 and Stage 2 matches
                            # Update result with Gaia data
                            result.gaia_source_id = match['gaia_source_id']
                            result.gaia_match = {
                                'source_id': match['gaia_source_id'],
                                'ra': match['gaia_ra'],
                                'dec': match['gaia_dec'],
                                'gmag': match['gaia_gmag'],
                                'bp_rp': match.get('gaia_bp_rp'),
                                'vmag': match.get('gaia_vmag'),
                                'distance_arcsec': match.get('d2d_arcsec', 0)
                            }

                            # Calculate Vmag for this star (if BP-RP available)
                            if match.get('gaia_vmag'):
                                result.vmag = match['gaia_vmag']

                                # Calibrate ONLY this star's magnitude
                                # User requirement: don't touch other stars
                                if result.mean_mag and result.vmag:
                                    offset = result.mean_mag - result.vmag
                                    result.mean_mag = result.vmag  # Set to Gaia Vmag
                                    logger.debug(
                                        f"[retry_gaia] {result.vast_id}: "
                                        f"Calibrated mag {result.mean_mag:.3f} (offset: {offset:.3f})"
                                    )

                            # Update catalog_matches string
                            if result.catalog_matches:
                                if 'Gaia' not in result.catalog_matches:
                                    result.catalog_matches += ',Gaia'
                            else:
                                result.catalog_matches = 'Gaia'

                            new_matches += 1
                            logger.info(
                                f"[retry_gaia] {result.vast_id}: NEW MATCH "
                                f"Gaia {match['gaia_source_id']} at {match.get('d2d_arcsec', 0):.1f}\""
                            )

                        else:
                            still_unmatched += 1
                            logger.warning(
                                f"[retry_gaia] {result.vast_id}: Still no match "
                                f"(RA={result.ra:.6f}, Dec={result.decl:.6f})"
                            )

                    except Exception as e:
                        still_unmatched += 1
                        logger.error(
                            f"[retry_gaia] {result.vast_id}: Error during retry: {e}",
                            exc_info=True
                        )

            # 6. Commit all changes
            db.commit()

            stats = {
                'retried_count': len(results_to_retry),
                'new_matches': new_matches,
                'still_unmatched': still_unmatched
            }

            logger.info(
                f"[retry_gaia] Complete for job {job_id}: "
                f"{new_matches} new matches, {still_unmatched} still unmatched"
            )

            return stats

        except Exception as e:
            logger.error(f"Error in retry_gaia_matching: {e}", exc_info=True)
            raise

        finally:
            db.close()
