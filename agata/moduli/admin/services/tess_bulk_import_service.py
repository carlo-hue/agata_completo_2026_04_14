# agata/admin/services/tess_bulk_import_service.py
"""
TESS Bulk Import Service

Orchestrator pipeline per import massivo di curve di luce TESS QLP da curl script MAST.

Pipeline:
1. Parsing curl script → estrazione TIC ID, settore, URL FITS
2. Download FITS da MAST per N stelle selezionate
3. Ingest QLP FITS via ingest_qlp_core + calcolo indici variabilita'
4. Identificazione candidati (soglie Stetson J / chi2)
5. Cross-match VSX (AAVSO) + ATLAS + flag variabilita' Gaia (pattern VAST tre cataloghi)
6. Cross-match TIC→Gaia DR3 per identificazione univoca
7. Salvataggio risultati in agata_tess_import_results
8. Promozione candidati in agata_star_photometry (su richiesta)

Riusa:
- _compute_variability_indices da ztf_survey_service (8 indici)
- Pattern VSX/ATLAS/Gaia da vast_service (tre cataloghi)
- ingest_qlp_core per parsing FITS TESS QLP
- insert_catalog_data / create_import_record per promozione
"""
import os
import re
import logging
import random
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import numpy as np
import pandas as pd
import requests

from agata.db import SessionLocal
from agata.auth_models.tess_import_job import TessImportJob, TessImportResult
from agata.moduli.admin.services.audit_service import log_audit
from agata.moduli.admin.services.ztf_survey_service import _compute_variability_indices
from agata.moduli.admin.services.catalog_common_service import (
    insert_catalog_data, create_import_record,
    finalize_import, update_import_with_results
)
from agata.moduli.admin.services.star_service import upsert_star_photometry as _upsert_star_photometry
from agata.moduli.admin.services.cagg_refresh_helper import CaggRefreshMixin

logger = logging.getLogger(__name__)

# =========================================================================
# Costanti
# =========================================================================
MAST_DOWNLOAD_TIMEOUT = int(os.getenv('TESS_MAST_DOWNLOAD_TIMEOUT', 120))
MAX_PARALLEL_GAIA_WORKERS = 8
MAX_FILES_HARD_CAP = 500  # mai più di 500 file per job
LC_PREVIEW_MAX_POINTS = 200
PER_FILE_TOTAL_TIMEOUT = int(os.getenv('TESS_PER_FILE_TOTAL_TIMEOUT', 180))

# Regex per estrarre TIC ID e settore dal filename/path del curl script
# Match: s0084-0000000012632720_tess  →  settore=84, tic_padded='0000000012632720'
_TIC_FROM_PATH_RE = re.compile(r's(\d{4})-(\d{16})_tess')
# Match della riga curl: --output 'path' ... 'url'  (oppure -o 'path')
_CURL_LINE_OUTPUT_RE = re.compile(r'(?:--output|-o)\s+[\'"]([^\'"]+)[\'"]')
# Match URL MAST — supporta doppi apici (default MAST), apici singoli, e unquoted
# Cerca in questo ordine: "https://..." > 'https://...' > https://...
_CURL_LINE_URL_RE_DOUBLE = re.compile(r'"(https://[^"]+)"')
_CURL_LINE_URL_RE_SINGLE = re.compile(r"'(https://[^']+)'")
_CURL_LINE_URL_RE_UNQUOTED = re.compile(r'(https://\S+)')


# =========================================================================
# Worker top-level per ThreadPoolExecutor (DEVE essere fuori dalla classe per pickling)
# =========================================================================
def _tess_tic_to_gaia_worker(params):
    """
    Risolve TIC ID → Gaia DR3 source_id per una singola stella TESS.

    Stage 1: Vizier IV/38/tic catalogo → colonna GAIA (TIC v8.2, ~85% coverage)
    Stage 2: fallback → Gaia DR3 cone search 10" su RA/Dec (pattern ZTF)
             (marca is_ambiguous=True se stage 2 usato)

    params: tuple (result_idx, tic_id, ra, dec)
    Returns: dict {result_idx, gaia_source_id, is_ambiguous, status}
    """
    import logging as _logging
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    import astropy.coordinates as coord

    worker_logger = _logging.getLogger(__name__)
    result_idx, tic_id, ra, dec = params

    # Stage 1: TIC catalogo Vizier → colonna GAIA
    if tic_id is not None:
        try:
            from astroquery.vizier import Vizier
            v = Vizier(columns=['TIC', 'GAIA'], row_limit=5)
            t = v.query_constraints(catalog='IV/38/tic', TIC=str(int(tic_id)))
            if t and len(t) > 0 and len(t[0]) > 0:
                gaia_val = t[0][0]['GAIA']
                # La colonna GAIA può essere mascherata (masked array) se NULL
                if gaia_val is not None and not (hasattr(gaia_val, 'mask') and gaia_val.mask):
                    gaia_int = int(gaia_val)
                    if gaia_int > 0:
                        return {
                            'result_idx': result_idx,
                            'gaia_source_id': gaia_int,
                            'is_ambiguous': False,
                            'status': 'tic_match'
                        }
        except Exception as e:
            worker_logger.debug(f"Stage 1 TIC→Gaia failed for TIC {tic_id}: {e}")

    # Stage 2: fallback → cone search Gaia DR3 su RA/Dec
    if ra is not None and dec is not None:
        try:
            from astroquery.vizier import Vizier
            gaia_catalog = "I/355/gaiadr3"
            gaia_cols = ['Source', 'RA_ICRS', 'DE_ICRS']
            Vizier.ROW_LIMIT = 20

            tess_coord = SkyCoord(ra=ra * u.deg, dec=dec * u.deg)

            result = Vizier(columns=gaia_cols).query_region(
                coord.SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame='icrs'),
                radius=10 * u.arcsec,
                catalog=gaia_catalog
            )
            if result and len(result) > 0 and len(result[0]) > 0:
                cat = result[0]
                gaia_coords = SkyCoord(
                    ra=cat['RA_ICRS'].data * u.deg,
                    dec=cat['DE_ICRS'].data * u.deg
                )
                seps = tess_coord.separation(gaia_coords).arcsec
                best_idx = int(np.argmin(seps))
                return {
                    'result_idx': result_idx,
                    'gaia_source_id': int(cat['Source'][best_idx]),
                    'is_ambiguous': True,  # fallback = ambiguous
                    'status': 'radec_match'
                }
        except Exception as e:
            worker_logger.debug(f"Stage 2 RA/Dec→Gaia failed for TIC {tic_id} (ra={ra:.4f}, dec={dec:.4f}): {e}")

    return {
        'result_idx': result_idx,
        'gaia_source_id': None,
        'is_ambiguous': False,
        'status': 'no_match'
    }


# =========================================================================
# Funzioni helper top-level
# =========================================================================
def _parse_curl_script(script_text: str) -> list:
    """
    Parsa un curl script MAST ed estrae metadati per ogni riga curl.

    Gestisce sia --output che -o come flag del path di output.
    Supporta URL con doppi apici (default MAST), apici singoli, o unquoted.

    Args:
        script_text: Contenuto testuale del curl script .sh

    Returns:
        Lista di dict: [{tic_id, sector, url, relative_path}]
    """
    results = []
    for line in script_text.splitlines():
        line = line.strip()
        if not line.startswith('curl'):
            continue

        # Estrai path di output
        output_match = _CURL_LINE_OUTPUT_RE.search(line)
        if not output_match:
            continue
        rel_path = output_match.group(1)

        # Estrai URL MAST — prova in ordine: doppi apici > apici singoli > unquoted
        url_matches = _CURL_LINE_URL_RE_DOUBLE.findall(line)
        if not url_matches:
            url_matches = _CURL_LINE_URL_RE_SINGLE.findall(line)
        if not url_matches:
            url_matches = _CURL_LINE_URL_RE_UNQUOTED.findall(line)

        if not url_matches:
            continue
        url = url_matches[-1]  # ultima URL = quella da scaricare

        # Estrai settore e TIC ID dal path
        tic_match = _TIC_FROM_PATH_RE.search(rel_path)
        if not tic_match:
            continue

        sector = int(tic_match.group(1))
        tic_padded = tic_match.group(2)  # '0000000012632720'
        tic_id = int(tic_padded)         # 12632720

        results.append({
            'tic_id': tic_id,
            'sector': sector,
            'url': url,
            'relative_path': rel_path,
        })

    return results


def _build_preview_json(times: np.ndarray, mags: np.ndarray, max_points: int = LC_PREVIEW_MAX_POINTS) -> dict:
    """
    Crea JSON downsampled per sparkline UI (max 200 punti, sampling uniforme).

    Args:
        times: Array HJD
        mags:  Array magnitudini
        max_points: Massimo punti da includere

    Returns:
        dict {hjd: [...], mag: [...]}
    """
    n = len(times)
    if n <= max_points:
        return {'hjd': times.tolist(), 'mag': mags.tolist()}
    step = n // max_points
    idx = np.arange(0, n, step)[:max_points]
    return {'hjd': times[idx].tolist(), 'mag': mags[idx].tolist()}


def _build_full_json(times: np.ndarray, mags: np.ndarray, mag_errs: np.ndarray) -> dict:
    """
    Crea JSON completo per promozione (tutti i punti).

    Returns:
        dict {hjd: [...], mag: [...], mag_err: [...]}
    """
    return {
        'hjd': times.tolist(),
        'mag': mags.tolist(),
        'mag_err': mag_errs.tolist(),
    }


# =========================================================================
# Classe servizio principale
# =========================================================================
class TessBulkImportService(CaggRefreshMixin):
    """Orchestrator pipeline TESS Bulk Import da curl script MAST."""

    def create_job(
        self,
        job_name: str,
        user_id: str,
        user_email: str,
        association_id: Optional[int] = None,
        curl_script_text: Optional[str] = None,
        curl_script_filename: Optional[str] = None,
        files_selected: int = 500,
        selection_strategy: str = 'first_n',
        # New path: script library
        curl_script_id: Optional[int] = None,
        script_offset: int = 0,
        # Thresholds
        min_observations: int = 20,
        stetson_j_threshold: float = 0.5,
        chi2_threshold: float = 3.0,
        mast_download_timeout: int = MAST_DOWNLOAD_TIMEOUT,
    ) -> TessImportJob:
        """
        Crea un job TESS bulk import. Supporta due path:

        PATH A (LEGACY): multipart curl_script_text (backward compatible)
            job_name, curl_script_text, curl_script_filename, files_selected, selection_strategy, ...

        PATH B (NEW - Script Library): curl_script_id + offset (no re-upload)
            job_name, curl_script_id, script_offset, files_selected, ...

        Raises:
            ValueError: se parametri non validi
        """
        if not job_name.strip():
            raise ValueError("Nome job obbligatorio")

        if min_observations < 5:
            raise ValueError("min_observations deve essere almeno 5")

        files_selected = min(int(files_selected), MAX_FILES_HARD_CAP)
        if files_selected < 1:
            raise ValueError("files_selected deve essere almeno 1")

        # Determina path (legacy vs script library)
        if curl_script_id is not None:
            # PATH B: Script library path
            from agata.moduli.admin.services.tess_curl_script_service import get_next_batch, get_script_status
            from agata.auth_models import TessCurlScript

            db_temp = SessionLocal()
            try:
                script = db_temp.query(TessCurlScript).get(curl_script_id)
                if not script:
                    raise ValueError(f"Script {curl_script_id} non trovato")
                if script.parse_state != 'ready':
                    raise ValueError(f"Script non pronto (state: {script.parse_state})")

                # Fetch next batch of entries starting from script_offset
                entries = get_next_batch(curl_script_id, batch_size=files_selected, offset=script_offset)
                if not entries:
                    raise ValueError("Nessun entry non processato disponibile in questo script")

                # Prepara selected list nel formato standard
                selected = entries
                total_files = script.total_entries
                n = len(entries)

                # Usa script_code come filename per audit
                curl_script_filename = script.original_filename

            finally:
                db_temp.close()

        else:
            # PATH A: Legacy multipart upload path
            if not curl_script_text:
                raise ValueError("curl_script_text obbligatorio (legacy path)")
            if not curl_script_filename:
                raise ValueError("curl_script_filename obbligatorio (legacy path)")

            if selection_strategy not in ('first_n', 'random_n'):
                raise ValueError("selection_strategy deve essere first_n o random_n")

            # Parsa script
            all_entries = _parse_curl_script(curl_script_text)
            if not all_entries:
                raise ValueError("Nessun file FITS trovato nel curl script (formato non riconosciuto)")

            total_files = len(all_entries)

            # Selezione N file
            n = min(files_selected, total_files)
            if selection_strategy == 'random_n':
                selected = random.sample(all_entries, n)
            else:
                selected = all_entries[:n]

        db = SessionLocal()
        try:
            # Genera job_code univoco basato su settore + progressivo sequenziale
            # Es. TESS_IMPORT-S84-00001, TESS_IMPORT-S84-00002, TESS_IMPORT-S85-00001
            sector = selected[0]['sector'] if selected else 0

            # Trova l'ultimo job con lo stesso settore
            last_job = db.query(TessImportJob).filter(
                TessImportJob.job_code.like(f"TESS_IMPORT-S{sector}-%")
            ).order_by(TessImportJob.job_code.desc()).first()

            if last_job:
                # Estrai il numero progressivo dall'ultimo job (es. "TESS_IMPORT-S84-00005" → 5)
                last_num = int(last_job.job_code.split('-')[-1])
                next_num = last_num + 1
            else:
                next_num = 1

            job_code = f"TESS_IMPORT-S{sector}-{next_num:05d}"

            job = TessImportJob(
                job_code=job_code,
                job_name=job_name.strip(),
                association_id=association_id,
                curl_script_filename=curl_script_filename,
                curl_script_id=curl_script_id,  # Set if script library path
                script_offset=script_offset,    # Offset for script library batching
                total_files_in_script=total_files,
                files_selected=n,
                selection_strategy=selection_strategy if curl_script_id is None else 'first_n',
                mast_download_timeout=mast_download_timeout,
                min_observations=min_observations,
                stetson_j_threshold=stetson_j_threshold,
                chi2_threshold=chi2_threshold,
                created_by=user_id,
                state='pending',
                progress_pct=0,
                output_data={'selected_files': selected},
            )

            db.add(job)
            db.commit()
            db.refresh(job)

            log_audit(
                user_id=user_id,
                user_email=user_email,
                association_id=association_id,
                action='tess_bulk_import_created',
                entity_type='tess_import_job',
                entity_id=str(job.id),
                new_value=job_code,
                description=(
                    f"Creato job TESS bulk import {job_code} '{job_name}': "
                    f"{n}/{total_files} file selezionati ({selection_strategy})"
                )
            )

            logger.info(f"Created TESS bulk import job {job_code} (ID: {job.id}, {n} files)")
            return job

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create TESS bulk import job: {e}", exc_info=True)
            raise
        finally:
            db.close()

    # =========================================================================
    # Orchestratore pipeline (eseguito in background thread)
    # =========================================================================

    def execute_job(self, job_id: int):
        """
        Orchestratore pipeline completa. Chiamato in background thread.

        Checkpoint: ogni file viene salvato in DB subito dopo download+variabilita'.
        Resume: i file già in DB (tic_id+sector) vengono saltati al riavvio.

        Bands di progresso:
            0-5%   : init / caricamento checkpoint
            5-60%  : download FITS + ingest + variabilita' (per ogni file)
            60-65% : identificazione candidati
            65-78% : VSX + ATLAS cross-match (bounding box area query)
            78-95% : Gaia cross-match TIC→Gaia (ThreadPoolExecutor)
            95-99% : aggiornamento campi cross-match in DB
            100%   : completato
        """
        db = SessionLocal()
        try:
            job = db.query(TessImportJob).get(job_id)
            if not job:
                logger.error(f"TESS bulk import job {job_id} not found")
                return

            logger.info(f"Starting TESS bulk import job {job.job_code}")
            job.state = 'downloading'
            if not job.started_at:
                job.started_at = datetime.utcnow()
            job.progress_pct = 5
            job.current_step = 'Inizializzazione pipeline TESS'
            db.commit()

            selected_files = (job.output_data or {}).get('selected_files', [])
            if not selected_files:
                self._fail_job(db, job, "Nessun file selezionato nel job (output_data mancante)")
                return

            n = len(selected_files)
            progress_per_file = 55.0 / max(n, 1)  # da 5% a 60%

            # --- Resume: carica (tic_id, sector) già salvati in DB per questo job ---
            already_done = set()
            existing_rows = db.query(TessImportResult).filter(
                TessImportResult.job_id == job_id
            ).with_entities(TessImportResult.tic_id, TessImportResult.sector).all()
            for row in existing_rows:
                already_done.add((row.tic_id, row.sector))
            if already_done:
                logger.info(
                    f"[{job.job_code}] Resume: {len(already_done)} file già in DB, saranno saltati"
                )

            # Step 1: Per-file download + ingest + variabilita' + checkpoint immediato
            results_list = []
            n_skipped = 0
            for i, file_entry in enumerate(selected_files):
                tic_id = file_entry.get('tic_id')
                sector = file_entry.get('sector')
                url = file_entry.get('url')
                rel_path = file_entry.get('relative_path')

                job.current_step = f'Download file {i+1}/{n}: TIC {tic_id} settore {sector}'
                job.progress_pct = int(5 + i * progress_per_file)
                db.commit()

                # Skip se già elaborato (resume)
                if (tic_id, sector) in already_done:
                    existing_r = db.query(TessImportResult).filter_by(
                        job_id=job_id, tic_id=tic_id, sector=sector
                    ).first()
                    if existing_r:
                        results_list.append(self._result_to_dict(existing_r))
                    n_skipped += 1
                    continue

                # Esegui con timeout per file (download + parse + variabilita')
                with ThreadPoolExecutor(max_workers=1) as _ex:
                    _future = _ex.submit(
                        self._process_single_file,
                        tic_id=tic_id,
                        sector=sector,
                        url=url,
                        rel_path=rel_path,
                        job=job
                    )
                    try:
                        result_data = _future.result(timeout=PER_FILE_TOTAL_TIMEOUT)
                    except Exception:
                        result_data = {
                            'tic_id': tic_id, 'sector': sector,
                            'fits_url': url, 'fits_filename': rel_path,
                            'download_failed': True,
                            'download_error': f'Timeout totale {PER_FILE_TOTAL_TIMEOUT}s per TIC {tic_id}',
                            'ra': None, 'decl': None, 'tess_mag': None, 'curve_used': None,
                            'n_points': 0, 'n_points_used': 0,
                            'mean_mag': None, 'std_dev': None, 'mag_err_median': None,
                            'stetson_j': None, 'stetson_k': None, 'chi_squared': None,
                            'mad': None, 'iqr': None,
                            'is_candidate': False, 'is_known_variable': False,
                            'is_valid': False, 'is_ambiguous': False,
                            'gaia_source_id': None, 'vsx_match': None, 'atlas_match': None,
                            'gaia_variability_flags': None, 'catalog_matches': None,
                            'variable_type': None,
                            'lc_preview_json': None, 'lc_full_json': None,
                        }
                        logger.warning(
                            f"[{job.job_code}] Timeout per TIC {tic_id} settore {sector}"
                        )

                # Checkpoint: salva subito in DB
                saved = self._save_single_result(result_data, job, db)
                result_data['db_id'] = saved.id
                results_list.append(result_data)

                # Pausa cortesia tra download MAST
                if i < n - 1:
                    time.sleep(0.3)

            # Aggiorna totale processati
            job.total_processed = sum(1 for r in results_list if not r.get('download_failed', False))
            job.total_failed_downloads = sum(1 for r in results_list if r.get('download_failed', False))
            logger.info(
                f"[{job.job_code}] Download completato: {job.total_processed}/{n} OK, "
                f"{job.total_failed_downloads} falliti, {n_skipped} saltati (resume)"
            )

            # Step 2: Identificazione candidati
            job.state = 'analyzing'
            job.progress_pct = 60
            job.current_step = 'Identificazione candidati variabili'
            db.commit()

            results_list = self._identify_candidates(results_list, job)
            n_candidates = sum(1 for r in results_list if r.get('is_candidate', False))
            logger.info(f"[{job.job_code}] Candidati: {n_candidates}/{n}")

            # Step 3: VSX + ATLAS cross-match (area query bounding box)
            job.state = 'crossmatching'
            job.progress_pct = 65
            job.current_step = 'Cross-match VSX e ATLAS (variabili note)'
            db.commit()

            try:
                results_list = self._crossmatch_known_variables(results_list, job)
            except Exception as e:
                logger.warning(f"[{job.job_code}] VSX/ATLAS cross-match error (continuo): {e}", exc_info=True)

            # Step 4: Gaia cross-match TIC→Gaia DR3
            job.progress_pct = 78
            job.current_step = f'Cross-match Gaia DR3 per {n} stelle (TIC→Gaia)'
            db.commit()

            try:
                results_list = self._crossmatch_gaia(results_list, job)
            except Exception as e:
                logger.warning(f"[{job.job_code}] Gaia cross-match error (continuo): {e}", exc_info=True)

            # Step 5: Aggiorna campi cross-match in DB (le righe sono già presenti dal checkpoint)
            job.progress_pct = 95
            job.current_step = 'Aggiornamento cross-match nel database'
            db.commit()

            self._update_crossmatch_fields(results_list, job, db)

            # Aggiorna statistiche finali
            job.candidates_found = sum(1 for r in results_list if r.get('is_candidate', False))
            job.known_variables_found = sum(1 for r in results_list if r.get('is_known_variable', False))
            job.state = 'completed'
            job.progress_pct = 100
            job.current_step = 'Completato'
            job.completed_at = datetime.utcnow()
            db.commit()

            # Force refresh cagg immediately (Phase 3 optimization)
            self.refresh_cagg_for_table(db, 'agata_tess_import_results', 'tess_job_summary')

            # Mark entries as processed if this job came from script library
            if job.curl_script_id is not None:
                self._mark_job_entries_processed(job)

            logger.info(
                f"[{job.job_code}] Pipeline completata: {job.total_processed} stelle, "
                f"{job.candidates_found} candidati, {job.known_variables_found} variabili note"
            )

        except Exception as e:
            db.rollback()
            try:
                job = db.query(TessImportJob).get(job_id)
                if job:
                    self._fail_job(db, job, f"Errore pipeline: {e}")
            except Exception:
                pass
            logger.error(f"TESS bulk import job {job_id} crashed: {e}", exc_info=True)
        finally:
            db.close()

    def _mark_job_entries_processed(self, job: TessImportJob) -> None:
        """
        Mark entries as processed in script library after job completes.

        Called when job.curl_script_id is not None (script library path).
        Calculates entry_indices from script_offset + files_selected.

        Args:
            job: TessImportJob object with curl_script_id and script_offset set
        """
        try:
            from agata.moduli.admin.services.tess_curl_script_service import mark_entries_processed

            # Calculate which entries were processed by this job
            entry_indices = list(range(job.script_offset, job.script_offset + job.files_selected))

            # Call script service to update is_processed and denorm count
            mark_entries_processed(job.curl_script_id, entry_indices)

            logger.info(
                f"[{job.job_code}] Marked {len(entry_indices)} entries as processed "
                f"in script {job.curl_script_id} (offset {job.script_offset})"
            )

        except Exception as e:
            logger.warning(
                f"[{job.job_code}] Failed to mark entries processed in script library: {e}"
            )
            # Non-fatal: job is already completed, this is just bookkeeping

    def _fail_job(self, db, job: TessImportJob, error_message: str):
        """Porta il job allo stato failed con messaggio di errore."""
        try:
            job.state = 'failed'
            job.error_message = str(error_message)[:2000]
            job.completed_at = datetime.utcnow()
            db.commit()
            logger.error(f"[{job.job_code}] Job failed: {error_message}")
        except Exception as e:
            logger.error(f"Failed to mark job as failed: {e}")
            db.rollback()

    def _result_to_dict(self, r: TessImportResult) -> dict:
        """Converte TessImportResult ORM → dict compatibile con results_list."""
        return {
            'db_id': r.id,
            'tic_id': r.tic_id,
            'sector': r.sector,
            'fits_url': r.fits_url,
            'fits_filename': r.fits_filename,
            'ra': r.ra,
            'decl': r.decl,
            'tess_mag': r.tess_mag,
            'curve_used': r.curve_used,
            'n_points': r.n_points,
            'n_points_used': r.n_points_used,
            'mean_mag': r.mean_mag,
            'std_dev': r.std_dev,
            'mag_err_median': r.mag_err_median,
            'stetson_j': r.stetson_j,
            'stetson_k': r.stetson_k,
            'chi_squared': r.chi_squared,
            'mad': r.mad,
            'iqr': r.iqr,
            'is_candidate': r.is_candidate,
            'is_known_variable': r.is_known_variable,
            'is_valid': r.is_valid,
            'is_ambiguous': r.is_ambiguous,
            'download_failed': r.download_failed,
            'download_error': r.download_error,
            'gaia_source_id': r.gaia_source_id,
            'vsx_match': r.vsx_match,
            'atlas_match': r.atlas_match,
            'gaia_variability_flags': r.gaia_variability_flags,
            'catalog_matches': r.catalog_matches,
            'variable_type': r.variable_type,
            'lc_preview_json': r.lc_preview_json,
            'lc_full_json': r.lc_full_json,
        }

    def _save_single_result(self, result_data: dict, job: TessImportJob, db) -> TessImportResult:
        """
        Salva un singolo risultato in DB subito dopo il download (prima del cross-match).
        Checkpoint granulare: se il job crasha, i dati già scaricati non vanno persi.
        I campi cross-match restano NULL e vengono popolati da _update_crossmatch_fields().
        """
        def _sf(val):
            try:
                return float(val) if val is not None else None
            except (TypeError, ValueError):
                return None

        def _si(val):
            try:
                return int(val) if val is not None else None
            except (TypeError, ValueError):
                return None

        result = TessImportResult(
            job_id=job.id,
            tic_id=_si(result_data.get('tic_id')),
            sector=_si(result_data.get('sector')),
            fits_url=result_data.get('fits_url'),
            fits_filename=result_data.get('fits_filename'),
            ra=_sf(result_data.get('ra')),
            decl=_sf(result_data.get('decl')),
            tess_mag=_sf(result_data.get('tess_mag')),
            curve_used=result_data.get('curve_used'),
            n_points=int(result_data.get('n_points', 0)),
            n_points_used=int(result_data.get('n_points_used', 0)),
            mean_mag=_sf(result_data.get('mean_mag')),
            std_dev=_sf(result_data.get('std_dev')),
            mag_err_median=_sf(result_data.get('mag_err_median')),
            stetson_j=_sf(result_data.get('stetson_j')),
            stetson_k=_sf(result_data.get('stetson_k')),
            chi_squared=_sf(result_data.get('chi_squared')),
            mad=_sf(result_data.get('mad')),
            iqr=_sf(result_data.get('iqr')),
            is_candidate=bool(result_data.get('is_candidate', False)),
            is_known_variable=False,   # popolato da _update_crossmatch_fields
            is_valid=False,            # popolato da _update_crossmatch_fields
            is_ambiguous=False,
            download_failed=bool(result_data.get('download_failed', False)),
            download_error=result_data.get('download_error'),
            lc_preview_json=result_data.get('lc_preview_json'),
            lc_full_json=result_data.get('lc_full_json'),
        )
        db.add(result)
        db.commit()
        db.expire(result)
        return result

    def _update_crossmatch_fields(self, results_list: list, job: TessImportJob, db):
        """
        Aggiorna i campi cross-match su righe già salvate in DB dopo _save_single_result().
        Usato al posto di _save_results() nella nuova pipeline con checkpoint.
        """
        batch_size = 20
        updated = 0
        for r in results_list:
            db_id = r.get('db_id')
            if not db_id:
                continue
            db_result = db.get(TessImportResult, db_id)
            if not db_result:
                continue
            db_result.is_candidate = bool(r.get('is_candidate', False))
            db_result.is_known_variable = bool(r.get('is_known_variable', False))
            db_result.is_valid = bool(r.get('is_valid', False))
            db_result.is_ambiguous = bool(r.get('is_ambiguous', False))
            db_result.gaia_source_id = r.get('gaia_source_id')
            db_result.vsx_match = r.get('vsx_match')
            db_result.atlas_match = r.get('atlas_match')
            db_result.gaia_variability_flags = r.get('gaia_variability_flags')
            db_result.catalog_matches = r.get('catalog_matches')
            db_result.variable_type = r.get('variable_type')
            updated += 1
            if updated % batch_size == 0:
                db.commit()
        if updated % batch_size != 0:
            db.commit()
        logger.info(f"[{job.job_code}] Aggiornati {updated} risultati con dati cross-match")

    def resume_job(self, job_id: int, user_id: str, user_email: str) -> TessImportJob:
        """
        Riprende un job in stato failed o bloccato (downloading/analyzing/crossmatching).
        Resetta lo stato a 'downloading' e prepara il job per un nuovo execute_job().
        I file già salvati in agata_tess_import_results verranno saltati nel loop.

        Raises:
            ValueError: se il job non è resumable
        """
        db = SessionLocal()
        try:
            job = db.query(TessImportJob).get(job_id)
            if not job:
                raise ValueError(f"Job {job_id} non trovato")
            if job.state == 'completed':
                raise ValueError("Il job è già completato, non serve riprenderlo")
            if job.state == 'cancelled':
                raise ValueError("Impossibile riprendere un job cancellato")
            if job.state == 'pending':
                raise ValueError("Il job non è ancora stato avviato")
            if job.is_running:
                raise ValueError("Il job è già in esecuzione")

            n_done = db.query(TessImportResult).filter(
                TessImportResult.job_id == job_id
            ).count()

            job.state = 'downloading'
            job.error_message = None
            job.progress_pct = 5
            job.current_step = f'Ripresa pipeline (già elaborati: {n_done} file)'
            job.completed_at = None
            db.commit()

            log_audit(
                user_id=user_id,
                user_email=user_email,
                association_id=job.association_id,
                action='tess_bulk_import_resumed',
                entity_type='tess_import_job',
                entity_id=str(job.id),
                description=(
                    f"Ripreso job TESS bulk import {job.job_code} "
                    f"({n_done} file già elaborati, saranno saltati)"
                )
            )
            logger.info(
                f"[{job.job_code}] Job ripreso da {user_email} "
                f"({n_done} file già in DB, saranno saltati)"
            )

            db.refresh(job)
            return job

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # =========================================================================
    # Step 1: Download singolo file FITS + ingest + variabilita'
    # =========================================================================

    def _process_single_file(
        self,
        tic_id: int,
        sector: int,
        url: str,
        rel_path: str,
        job: TessImportJob
    ) -> dict:
        """
        Scarica un file FITS TESS QLP da MAST, lo parsa e calcola gli indici.

        Returns:
            dict con tutti i campi necessari per TessImportResult
            (sempre restituisce un dict, anche in caso di errore con download_failed=True)
        """
        base_result = {
            'tic_id': tic_id,
            'sector': sector,
            'fits_url': url,
            'fits_filename': rel_path,
            'download_failed': False,
            'download_error': None,
            'ra': None,
            'decl': None,
            'tess_mag': None,
            'curve_used': None,
            'n_points': 0,
            'n_points_used': 0,
            'mean_mag': None,
            'std_dev': None,
            'mag_err_median': None,
            'stetson_j': None,
            'stetson_k': None,
            'chi_squared': None,
            'mad': None,
            'iqr': None,
            'is_candidate': False,
            'is_known_variable': False,
            'is_valid': False,
            'is_ambiguous': False,
            'gaia_source_id': None,
            'vsx_match': None,
            'atlas_match': None,
            'gaia_variability_flags': None,
            'catalog_matches': None,
            'variable_type': None,
            'lc_preview_json': None,
            'lc_full_json': None,
        }

        # Download FITS
        try:
            resp = requests.get(
                url,
                timeout=job.mast_download_timeout,
                stream=False,
                headers={'User-Agent': 'AGATA/2.0 (Astronomical research)'}
            )
            resp.raise_for_status()
            fits_bytes = resp.content
        except requests.exceptions.Timeout:
            base_result['download_failed'] = True
            base_result['download_error'] = f"Timeout ({job.mast_download_timeout}s) per TIC {tic_id}"
            logger.warning(f"TESS download timeout: TIC {tic_id} settore {sector}")
            return base_result
        except Exception as e:
            base_result['download_failed'] = True
            base_result['download_error'] = str(e)[:400]
            logger.warning(f"TESS download failed: TIC {tic_id} settore {sector}: {e}")
            return base_result

        # Ingest FITS via qlp_core
        try:
            from agata.moduli.admin.services.tess.qlp_core import ingest_qlp_core
            lc_set, warnings_list = ingest_qlp_core(
                fits_bytes,
                origin="mast_bulk_import",
                compute_magnitude=True,
            )
        except Exception as e:
            base_result['download_failed'] = True
            base_result['download_error'] = f"FITS parse error: {str(e)[:350]}"
            logger.warning(f"TESS FITS parse failed: TIC {tic_id}: {e}")
            return base_result

        # Estrai metadati dal FITS
        meta = lc_set.get('meta', {})
        base_result['ra'] = meta.get('ra_obj') or meta.get('ra')
        base_result['decl'] = meta.get('dec_obj') or meta.get('dec')
        base_result['tess_mag'] = meta.get('tessmag') or meta.get('tess_mag')

        # Seleziona curva: corrected (KSPSAP) > raw (SAP)
        curves = lc_set.get('curves', {})
        curve_name = None
        curve_data = None
        for preferred in ('corrected', 'raw'):
            if preferred in curves and curves[preferred]:
                curve_name = preferred
                curve_data = curves[preferred]
                break
        if curve_name is None and curves:
            curve_name = next(iter(curves))
            curve_data = curves[curve_name]

        if not curve_data:
            base_result['download_failed'] = True
            base_result['download_error'] = "Nessuna curva di luce estratta dal FITS"
            return base_result

        base_result['curve_used'] = curve_name

        # Converti in array
        try:
            times = np.array(curve_data.get('time', curve_data.get('hjd', [])), dtype=float)
            mags = np.array(curve_data.get('mag', []), dtype=float)
            mag_errs_raw = curve_data.get('mag_err', curve_data.get('err', []))
            if mag_errs_raw:
                mag_errs = np.array(mag_errs_raw, dtype=float)
            else:
                mag_errs = np.full_like(mags, 0.01)
        except Exception as e:
            base_result['download_failed'] = True
            base_result['download_error'] = f"Conversione array fallita: {e}"
            return base_result

        # Pulizia NaN
        valid_mask = np.isfinite(times) & np.isfinite(mags)
        times = times[valid_mask]
        mags = mags[valid_mask]
        mag_errs = mag_errs[valid_mask]

        n_total = len(times)
        base_result['n_points'] = n_total

        # Filtro minimo osservazioni
        if n_total < job.min_observations:
            base_result['n_points_used'] = n_total
            base_result['download_error'] = f"Troppo pochi punti: {n_total} < {job.min_observations}"
            # Non fail completo, ma senza indici
            return base_result

        base_result['n_points_used'] = n_total

        # Calcola indici variabilita' (stessi 8 del pipeline ZTF)
        indices = _compute_variability_indices(mags, mag_errs)
        if indices:
            base_result.update({
                'mean_mag': indices.get('mean_mag'),
                'std_dev': indices.get('std_dev'),
                'mag_err_median': indices.get('mag_err_median'),
                'stetson_j': indices.get('stetson_j'),
                'stetson_k': indices.get('stetson_k'),
                'chi_squared': indices.get('chi_squared'),
                'mad': indices.get('mad'),
                'iqr': indices.get('iqr'),
            })

        # Ordina per tempo
        sort_idx = np.argsort(times)
        times = times[sort_idx]
        mags = mags[sort_idx]
        mag_errs = mag_errs[sort_idx]

        # Storage curva di luce
        base_result['lc_preview_json'] = _build_preview_json(times, mags)
        base_result['lc_full_json'] = _build_full_json(times, mags, mag_errs)

        return base_result

    # =========================================================================
    # Step 2: Identificazione candidati
    # =========================================================================

    def _identify_candidates(self, results_list: list, job: TessImportJob) -> list:
        """
        Marca is_candidate=True dove stetson_j > soglia OR chi_squared > soglia.
        """
        for r in results_list:
            if r.get('download_failed') or r.get('n_points_used', 0) < job.min_observations:
                continue
            sj = r.get('stetson_j')
            chi2 = r.get('chi_squared')
            is_cand = False
            if sj is not None and sj > job.stetson_j_threshold:
                is_cand = True
            if chi2 is not None and chi2 > job.chi2_threshold:
                is_cand = True
            r['is_candidate'] = is_cand
        return results_list

    # =========================================================================
    # Step 3: Cross-match VSX + ATLAS (pattern VAST tre cataloghi)
    # =========================================================================

    def _crossmatch_known_variables(self, results_list: list, job: TessImportJob) -> list:
        """
        Cross-match con VSX (AAVSO) e ATLAS via Vizier, bounding box delle stelle processate.

        Pattern VAST:
        - VSX OR Gaia variability flag → is_known_variable = True
        - ATLAS → atlas_match JSON ma NON imposta is_known_variable
        """
        try:
            import astropy.units as u
            import astropy.coordinates as coord
            from astropy.coordinates import match_coordinates_sky
            from astroquery.vizier import Vizier
        except ImportError:
            logger.warning("astroquery non disponibile, skip VSX/ATLAS cross-match")
            return results_list

        # Raccogli coordinate delle stelle con RA/Dec valido
        valid_coords = [
            (i, r['ra'], r['decl'])
            for i, r in enumerate(results_list)
            if r.get('ra') is not None and r.get('decl') is not None
        ]

        if not valid_coords:
            logger.info(f"[{job.job_code}] Nessuna stella con coordinate valide per cross-match")
            return results_list

        ras = np.array([c[1] for c in valid_coords])
        decs = np.array([c[2] for c in valid_coords])
        result_indices = [c[0] for c in valid_coords]

        # Bounding box con 1° di padding
        ra_min, ra_max = float(np.min(ras)) - 1.0, float(np.max(ras)) + 1.0
        dec_min, dec_max = float(np.min(decs)) - 1.0, float(np.max(decs)) + 1.0
        ra_center = (ra_min + ra_max) / 2
        dec_center = (dec_min + dec_max) / 2
        search_radius = max(
            np.sqrt(((ra_max - ra_min) / 2) ** 2 + ((dec_max - dec_min) / 2) ** 2),
            0.5
        )

        center_coord = coord.SkyCoord(ra=ra_center * u.deg, dec=dec_center * u.deg)
        tess_coords = coord.SkyCoord(ra=ras * u.deg, dec=decs * u.deg)

        Vizier.ROW_LIMIT = 100000
        max_sep = 25 * u.arcsec

        # ---- VSX cross-match ----
        try:
            vsx_result = Vizier(columns=['OID', 'RAJ2000', 'DEJ2000', 'Name', 'Type']).query_region(
                center_coord,
                radius=search_radius * u.deg,
                catalog='B/vsx/vsx'
            )
            if vsx_result and len(vsx_result) > 0:
                vsx_cat = vsx_result[0]
                logger.info(f"[{job.job_code}] VSX: {len(vsx_cat)} variabili nell'area")

                vsx_coords = coord.SkyCoord(
                    ra=vsx_cat['RAJ2000'].data * u.deg,
                    dec=vsx_cat['DEJ2000'].data * u.deg
                )
                idx, d2d, _ = match_coordinates_sky(tess_coords, vsx_coords)
                matched_mask = d2d < max_sep

                for j, (is_matched, vsx_idx) in enumerate(zip(matched_mask, idx)):
                    if is_matched:
                        ri = result_indices[j]
                        vsx_row = vsx_cat[int(vsx_idx)]
                        results_list[ri]['is_known_variable'] = True
                        results_list[ri]['variable_type'] = str(vsx_row['Type']) if vsx_row['Type'] else None
                        results_list[ri]['vsx_match'] = {
                            'oid': str(vsx_row['OID']),
                            'name': str(vsx_row['Name']) if 'Name' in vsx_cat.colnames else None,
                            'type': str(vsx_row['Type']) if vsx_row['Type'] else None,
                        }
                        results_list[ri]['catalog_matches'] = 'AAVSO'

                n_vsx = int(matched_mask.sum())
                logger.info(f"[{job.job_code}] VSX: {n_vsx} sorgenti matchate")
            else:
                logger.info(f"[{job.job_code}] VSX: nessun risultato nell'area")

        except Exception as e:
            logger.warning(f"[{job.job_code}] VSX cross-match error: {e}", exc_info=True)

        # ---- ATLAS cross-match (J/AJ/156/241/table4) ----
        try:
            atlas_result = Vizier(columns=['ATOID', 'RAJ2000', 'DEJ2000', 'Class']).query_region(
                center_coord,
                radius=search_radius * u.deg,
                catalog='J/AJ/156/241/table4'
            )
            if atlas_result and len(atlas_result) > 0:
                atlas_cat = atlas_result[0]
                logger.info(f"[{job.job_code}] ATLAS: {len(atlas_cat)} variabili nell'area")

                atlas_coords = coord.SkyCoord(
                    ra=atlas_cat['RAJ2000'].data * u.deg,
                    dec=atlas_cat['DEJ2000'].data * u.deg
                )
                idx_a, d2d_a, _ = match_coordinates_sky(tess_coords, atlas_coords)
                matched_a = d2d_a < max_sep

                for j, (is_matched, atlas_idx) in enumerate(zip(matched_a, idx_a)):
                    if is_matched:
                        ri = result_indices[j]
                        atlas_row = atlas_cat[int(atlas_idx)]
                        results_list[ri]['atlas_match'] = {
                            'atoid': str(atlas_row['ATOID']) if 'ATOID' in atlas_cat.colnames else None,
                            'class': str(atlas_row['Class']) if 'Class' in atlas_cat.colnames else None,
                        }
                        # Aggiorna catalog_matches
                        existing = results_list[ri].get('catalog_matches') or ''
                        if 'Atlas' not in existing:
                            results_list[ri]['catalog_matches'] = (existing + ',Atlas').lstrip(',')

                n_atlas = int(matched_a.sum())
                logger.info(f"[{job.job_code}] ATLAS: {n_atlas} sorgenti matchate")
            else:
                logger.info(f"[{job.job_code}] ATLAS: nessun risultato nell'area")

        except Exception as e:
            logger.warning(f"[{job.job_code}] ATLAS cross-match error (non critico): {e}", exc_info=True)

        return results_list

    # =========================================================================
    # Step 4: Gaia cross-match TIC→Gaia DR3
    # =========================================================================

    def _crossmatch_gaia(self, results_list: list, job: TessImportJob) -> list:
        """
        Cross-match TIC→Gaia DR3 in parallelo via _tess_tic_to_gaia_worker.

        Recupera anche flag variabilita' Gaia (VRRLyr, VCep, ecc.)
        is_valid = gaia_source_id IS NOT NULL AND NOT is_ambiguous
        """
        n = len(results_list)
        logger.info(f"[{job.job_code}] Gaia cross-match per {n} stelle")

        params_list = [
            (i, r.get('tic_id'), r.get('ra'), r.get('decl'))
            for i, r in enumerate(results_list)
        ]

        gaia_results = {}
        max_workers = min(MAX_PARALLEL_GAIA_WORKERS, n)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_tess_tic_to_gaia_worker, p): p[0] for p in params_list}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    gaia_results[result['result_idx']] = result
                except Exception as e:
                    result_idx = futures[future]
                    logger.warning(f"[{job.job_code}] Gaia worker {result_idx} exception: {e}")
                    gaia_results[result_idx] = {
                        'result_idx': result_idx,
                        'gaia_source_id': None,
                        'is_ambiguous': False,
                        'status': 'error'
                    }

        # Aggiorna results_list con risultati Gaia
        matched = 0
        for idx, gaia_res in gaia_results.items():
            if idx >= len(results_list):
                continue
            gaia_id = gaia_res.get('gaia_source_id')
            is_ambiguous = gaia_res.get('is_ambiguous', False)
            results_list[idx]['gaia_source_id'] = gaia_id
            results_list[idx]['is_ambiguous'] = is_ambiguous
            results_list[idx]['is_valid'] = (gaia_id is not None and not is_ambiguous)

            if gaia_id is not None:
                matched += 1
                existing = results_list[idx].get('catalog_matches') or ''
                if 'Gaia' not in existing:
                    results_list[idx]['catalog_matches'] = ('Gaia,' + existing).rstrip(',')

        logger.info(f"[{job.job_code}] Gaia: {matched}/{n} stelle matchate")

        # Recupera flag variabilita' Gaia per le stelle con Gaia ID
        self._fetch_gaia_variability_flags(results_list, job)

        return results_list

    def _fetch_gaia_variability_flags(self, results_list: list, job: TessImportJob):
        """
        Recupera flag variabilita' Gaia DR3 per le stelle con gaia_source_id.
        Aggiorna is_known_variable se il flag e' presente (pattern VAST).

        Flag Gaia controllati: VCR, VRRLyr, VCep, VEA, VEM, VGS, VRotBE, VPer, VEB, VLPV
        """
        gaia_stars = [(i, r) for i, r in enumerate(results_list) if r.get('gaia_source_id')]
        if not gaia_stars:
            return

        # Per semplicita', query Vizier con source_id list non e' supportata natively
        # Usiamo invece i flag da gaiadr3 variability catalog (gaiadr3.vari_classifier_result)
        # tramite Vizier I/358/vclassre
        try:
            from astroquery.vizier import Vizier
            import astropy.units as u
            import astropy.coordinates as coord

            # Raccogliamo RA/Dec per query area
            ras = [r.get('ra') for _, r in gaia_stars if r.get('ra') is not None]
            decs = [r.get('decl') for _, r in gaia_stars if r.get('decl') is not None]
            if not ras:
                return

            ra_c = float(np.mean(ras))
            dec_c = float(np.mean(decs))
            radius = max(float(np.max(np.abs(np.array(ras) - ra_c))) + 0.5,
                        float(np.max(np.abs(np.array(decs) - dec_c))) + 0.5, 0.5)

            center = coord.SkyCoord(ra=ra_c * u.deg, dec=dec_c * u.deg)

            # Catalogo Gaia DR3 variability classifier
            Vizier.ROW_LIMIT = 50000
            var_result = Vizier(columns=['Source', 'Class']).query_region(
                center,
                radius=radius * u.deg,
                catalog='I/358/vclassre'
            )

            if not var_result or len(var_result) == 0:
                return

            var_cat = var_result[0]
            # Costruisci dict source_id → class
            gaia_var_map = {}
            for row in var_cat:
                src = int(row['Source'])
                cls = str(row['Class']) if row['Class'] else None
                if cls:
                    gaia_var_map[src] = cls

            if not gaia_var_map:
                return

            # Aggiorna risultati
            for i, r in results_list:
                gid = r.get('gaia_source_id')
                if gid and int(gid) in gaia_var_map:
                    var_class = gaia_var_map[int(gid)]
                    results_list[i]['gaia_variability_flags'] = var_class
                    # Flag Gaia → is_known_variable = True (pattern VAST)
                    results_list[i]['is_known_variable'] = True
                    # Aggiorna variable_type se non già impostato da VSX
                    if not results_list[i].get('variable_type'):
                        results_list[i]['variable_type'] = var_class
                    # Aggiorna catalog_matches
                    existing = results_list[i].get('catalog_matches') or ''
                    if 'Gaia_var' not in existing:
                        results_list[i]['catalog_matches'] = (existing + ',Gaia_var').lstrip(',')

            logger.info(f"[{job.job_code}] Gaia variability flags: {len(gaia_var_map)} stelle con classificazione")

        except Exception as e:
            logger.warning(f"[{job.job_code}] Gaia variability flags error (non critico): {e}", exc_info=True)

    # =========================================================================
    # Step 5: Salvataggio risultati DB
    # =========================================================================

    def _save_results(self, results_list: list, job: TessImportJob, db):
        """
        Salva i risultati in agata_tess_import_results (batch da 5).
        Batch piccolo perché lc_full_json può essere ~500KB per record:
        100 record = ~50MB per INSERT, supera max_allowed_packet di MySQL.
        5 record = ~2.5MB per INSERT, sicuro sotto il limite di 16MB.
        """
        batch = []
        n_saved = 0

        def _safe_float(val):
            try:
                return float(val) if val is not None else None
            except (TypeError, ValueError):
                return None

        def _safe_int(val):
            try:
                return int(val) if val is not None else None
            except (TypeError, ValueError):
                return None

        for r in results_list:
            result = TessImportResult(
                job_id=job.id,
                tic_id=_safe_int(r.get('tic_id')),
                sector=_safe_int(r.get('sector')),
                fits_url=r.get('fits_url'),
                fits_filename=r.get('fits_filename'),
                ra=_safe_float(r.get('ra')),
                decl=_safe_float(r.get('decl')),
                tess_mag=_safe_float(r.get('tess_mag')),
                curve_used=r.get('curve_used'),
                n_points=int(r.get('n_points', 0)),
                n_points_used=int(r.get('n_points_used', 0)),
                mean_mag=_safe_float(r.get('mean_mag')),
                std_dev=_safe_float(r.get('std_dev')),
                mag_err_median=_safe_float(r.get('mag_err_median')),
                stetson_j=_safe_float(r.get('stetson_j')),
                stetson_k=_safe_float(r.get('stetson_k')),
                chi_squared=_safe_float(r.get('chi_squared')),
                mad=_safe_float(r.get('mad')),
                iqr=_safe_float(r.get('iqr')),
                is_candidate=bool(r.get('is_candidate', False)),
                is_known_variable=bool(r.get('is_known_variable', False)),
                is_valid=bool(r.get('is_valid', False)),
                is_ambiguous=bool(r.get('is_ambiguous', False)),
                download_failed=bool(r.get('download_failed', False)),
                download_error=r.get('download_error'),
                gaia_source_id=_safe_int(r.get('gaia_source_id')),
                vsx_match=r.get('vsx_match'),
                atlas_match=r.get('atlas_match'),
                gaia_variability_flags=r.get('gaia_variability_flags'),
                catalog_matches=r.get('catalog_matches'),
                variable_type=r.get('variable_type'),
                lc_preview_json=r.get('lc_preview_json'),
                lc_full_json=r.get('lc_full_json'),
            )
            batch.append(result)

            if len(batch) >= 5:
                db.add_all(batch)
                db.commit()
                db.expire_all()
                n_saved += len(batch)
                logger.debug(f"[{job.job_code}] Salvati {n_saved} risultati...")
                batch = []

        if batch:
            db.add_all(batch)
            db.commit()
            n_saved += len(batch)

        logger.info(f"[{job.job_code}] Salvati {n_saved} risultati totali")

    # =========================================================================
    # Promozione candidati in agata_star_photometry
    # =========================================================================

    def promote_job_results(
        self,
        job_id: int,
        user_id: str,
        user_email: str,
        result_ids: Optional[list] = None,
        exclude_known_variables: bool = False
    ) -> dict:
        """
        Promuove i risultati TESS validati in agata_star_photometry.

        Legge lc_full_json dalla riga TessImportResult (nessun re-download da MAST).
        Pattern VAST: stored LC → calibrate → insert.

        Returns:
            dict {promoted, lightcurve_points, skipped_no_gaia, skipped_known,
                  skipped_no_lc, import_id, errors}
        """
        db = SessionLocal()
        stats = {
            'promoted': 0,
            'lightcurve_points': 0,
            'skipped_no_gaia': 0,
            'skipped_known': 0,
            'skipped_no_lc': 0,
            'errors': [],
            'import_id': None,
        }

        try:
            job = db.query(TessImportJob).get(job_id)
            if not job:
                raise ValueError(f"Job {job_id} non trovato")

            if job.state != 'completed':
                raise ValueError(f"Il job deve essere completato per promuovere (stato: {job.state})")

            results = db.query(TessImportResult).filter(TessImportResult.job_id == job_id).all()
            if not results:
                raise ValueError("Nessun risultato trovato per questo job")

            # Filtra eligible (pattern ZTF/VAST)
            eligible = []
            stats['skipped_rejected'] = 0
            for r in results:
                if not r.gaia_source_id:
                    stats['skipped_no_gaia'] += 1
                    continue
                if not r.is_valid:
                    continue
                if r.download_failed:
                    continue
                # Richiedi almeno preview o full lightcurve (not both empty)
                if not r.lc_full_json and not r.lc_preview_json:
                    stats['skipped_no_lc'] += 1
                    continue
                if exclude_known_variables and r.is_known_variable:
                    stats['skipped_known'] += 1
                    continue
                if r.is_rejected:
                    stats['skipped_rejected'] += 1
                    continue
                if result_ids is not None and r.id not in result_ids:
                    continue
                eligible.append(r)

            logger.info(
                f"[{job.job_code}] Promozione: {len(eligible)} eligible "
                f"(skip no_gaia={stats['skipped_no_gaia']}, skip known={stats['skipped_known']}, "
                f"skip no_lc={stats['skipped_no_lc']}, skip rejected={stats.get('skipped_rejected', 0)})"
            )

            if not eligible:
                raise ValueError("Nessuna stella eligible per la promozione")

            # Crea CatalogImport record
            import_record = create_import_record(
                db=db,
                catalog_name=f"TESS-QLP Bulk {job.job_code}",
                search_type='file',
                search_value=job.job_code,
                ra=None,
                dec=None,
                radius_arcsec=None,
                gaia_id=None,
                user_id=user_id,
                state='importing'
            )
            logger.info(f"[{job.job_code}] CatalogImport #{import_record.id} creato")

            # Promuovi ogni stella
            for r in eligible:
                gaia_id_str = str(r.gaia_source_id)
                sector = r.sector
                catalog_name = f"TESS-QLP" + (f"_s{sector:04d}" if sector else "")

                try:
                    # Ricostruisci DataFrame: preferisci full, fallback a preview
                    lc_data = r.lc_full_json if r.lc_full_json else r.lc_preview_json
                    if not lc_data:
                        stats['errors'].append(f"LC non disponibile per TIC {r.tic_id}")
                        continue

                    hjd_arr = lc_data.get('hjd', [])
                    mag_arr = lc_data.get('mag', [])

                    if not hjd_arr or not mag_arr:
                        stats['errors'].append(f"LC vuota per TIC {r.tic_id}")
                        continue

                    lc_df = pd.DataFrame({'hjd': hjd_arr, 'mag': mag_arr})
                    lc_df = lc_df.dropna(subset=['hjd', 'mag']).sort_values('hjd').reset_index(drop=True)

                    if lc_df.empty:
                        stats['errors'].append(f"LC vuota dopo pulizia per TIC {r.tic_id}")
                        continue

                    points = insert_catalog_data(
                        db=db,
                        gaia_id=gaia_id_str,
                        catalog_name=catalog_name,
                        data=lc_df,
                        association_id_owner=job.association_id,
                        catalog_import_id=import_record.id
                    )
                    stats['lightcurve_points'] += points

                    if points > 0:
                        _upsert_star_photometry(db, gaia_id_str)
                        stats['promoted'] += 1

                except Exception as e:
                    error_msg = f"Errore promozione TIC {r.tic_id}: {e}"
                    logger.error(error_msg, exc_info=True)
                    stats['errors'].append(error_msg)

            # Aggiorna stats job
            job.promoted_count = stats['promoted']
            db.commit()

            # Finalizza CatalogImport
            update_import_with_results(
                db=db,
                import_record=import_record,
                catalog_name="TESS-QLP Bulk",
                success=True,
                point_count=stats['lightcurve_points'],
            )
            finalize_import(
                db=db,
                import_record=import_record,
                points_imported=stats['lightcurve_points'],
                user_id=user_id,
                user_email=user_email,
                association_id=job.association_id,
                auto_create_project=False,
                catalog_name="TESS-QLP Bulk"
            )

            stats['import_id'] = import_record.id

            log_audit(
                user_id=user_id,
                user_email=user_email,
                association_id=job.association_id,
                action='tess_bulk_import_promoted',
                entity_type='tess_import_job',
                entity_id=str(job.id),
                new_value=f"{stats['promoted']} stelle, {stats['lightcurve_points']} punti, import #{import_record.id}",
                description=(
                    f"Promosso TESS bulk import {job.job_code}: {stats['promoted']} stelle, "
                    f"{stats['lightcurve_points']} punti fotometrici (import #{import_record.id})"
                )
            )

            logger.info(
                f"[{job.job_code}] Promozione completata: {stats['promoted']} stelle, "
                f"{stats['lightcurve_points']} punti (import #{import_record.id})"
            )
            return stats

        except Exception as e:
            db.rollback()
            logger.error(f"Promozione fallita per job {job_id}: {e}", exc_info=True)
            raise
        finally:
            db.close()

    # =========================================================================
    # Utility: list jobs, delete job, get job status
    # =========================================================================

    def list_jobs(
        self,
        user_id: str,
        association_id: Optional[int],
        is_superuser: bool
    ) -> list:
        """
        Restituisce la lista dei job TESS. Superuser vede tutti, admin solo i propri.
        """
        db = SessionLocal()
        try:
            q = db.query(TessImportJob).order_by(TessImportJob.created_at.desc())
            if not is_superuser and association_id:
                q = q.filter(TessImportJob.association_id == association_id)
            jobs = q.all()
            return [self._job_to_dict(j) for j in jobs]
        finally:
            db.close()

    def get_job(self, job_id: int) -> Optional[dict]:
        """Restituisce lo stato di un singolo job come dict."""
        db = SessionLocal()
        try:
            job = db.query(TessImportJob).get(job_id)
            if not job:
                return None
            return self._job_to_dict(job)
        finally:
            db.close()

    def delete_job(self, job_id: int, user_id: str, user_email: str) -> bool:
        """Elimina un job (e relativi risultati via CASCADE). Non eliminabile se in corso."""
        db = SessionLocal()
        try:
            job = db.query(TessImportJob).get(job_id)
            if not job:
                raise ValueError(f"Job {job_id} non trovato")
            if job.is_running:
                raise ValueError("Impossibile eliminare un job in corso")

            job_code = job.job_code
            db.delete(job)
            db.commit()

            log_audit(
                user_id=user_id,
                user_email=user_email,
                association_id=job.association_id,
                action='tess_bulk_import_deleted',
                entity_type='tess_import_job',
                entity_id=str(job_id),
                description=f"Eliminato job TESS bulk import {job_code}"
            )
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _job_to_dict(self, job: TessImportJob) -> dict:
        """Serializza TessImportJob → dict (per API polling)."""
        return {
            'id': job.id,
            'job_code': job.job_code,
            'job_name': job.job_name,
            'association_id': job.association_id,
            'curl_script_filename': job.curl_script_filename,
            'total_files_in_script': job.total_files_in_script,
            'files_selected': job.files_selected,
            'selection_strategy': job.selection_strategy,
            'state': job.state,
            'progress_pct': job.progress_pct,
            'current_step': job.current_step,
            'error_message': job.error_message,
            'total_processed': job.total_processed,
            'total_failed_downloads': job.total_failed_downloads,
            'candidates_found': job.candidates_found,
            'known_variables_found': job.known_variables_found,
            'promoted_count': job.promoted_count,
            'is_running': job.is_running,
            'is_failed': job.is_failed,
            'duration_seconds': job.duration_seconds,
            'created_at': job.created_at.isoformat() if job.created_at else None,
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'creator_email': job.creator.email if job.creator else None,
        }
