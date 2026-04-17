# agata/admin/services/ztf_survey_service.py
"""
ZTF Field Survey Service

Orchestrator pipeline per survey fotometrico ZTF su area di cielo.
Analogo alla pipeline VAST ma usa dati ZTF da IRSA invece di immagini FITS.

Pipeline:
1. Download dati ZTF da IRSA (area query)
2. Calcolo indici di variabilita' per ogni sorgente
3. Identificazione candidati (soglie Stetson J / chi2)
4. Cross-match VSX (AAVSO) per variabili note
5. Cross-match Gaia DR3 per identificazione sorgenti
6. Salvataggio risultati in agata_ztf_survey_results
7. Promozione candidati in agata_star_photometry (su richiesta)
"""
import io
import logging
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from typing import Optional

import numpy as np
import pandas as pd
import requests

try:
    from astroquery.ipac.irsa import Irsa as _IrsaClient
    _IRSA_CLIENT_AVAILABLE = True
except ImportError:
    _IRSA_CLIENT_AVAILABLE = False

from sqlalchemy import text
from agata.db import SessionLocal
from agata.auth_models.ztf_survey_job import ZtfSurveyJob, ZtfSurveyResult
from agata.auth_models.catalog_import import CatalogImport
from agata.moduli.admin.services.audit_service import log_audit
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
IRSA_LIGHTCURVES_URL = "https://irsa.ipac.caltech.edu/cgi-bin/ZTF/nph_light_curves"
IRSA_TIMEOUT = int(os.getenv('ZTF_IRSA_TIMEOUT', 60))
MJD_TO_HJD_OFFSET = 2400000.5  # MJD → HJD (Julian Date) approssimato

ZTF_FILTER_MAP = {
    'g': 'zg',
    'r': 'zr',
    'i': 'zi',
}

CATALOG_NAME_MAP = {
    'zg': 'ZTFg',
    'zr': 'ZTFr',
    'zi': 'ZTFi',
}


# =========================================================================
# Worker top-level per ThreadPoolExecutor (DEVE essere fuori dalla classe per pickling)
# =========================================================================
def _ztf_gaia_worker(params):
    """
    Query Gaia DR3 per una singola sorgente ZTF. Top-level per compatibilita' pickling.

    Usa two-stage approach:
    - Stage 1: cone 10" (match esatto)
    - Stage 2: cone 100" fallback (is_ambiguous=True)

    Nota: NON fa calibrazione magnitudine perche' ZTF ha gia' magnitudini calibrate.

    params: tuple (source_idx, ra, dec)
    Returns: dict {source_idx, gaia_source_id, is_ambiguous, status}
    """
    import logging as _logging
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    worker_logger = _logging.getLogger(__name__)
    source_idx, ra, dec = params

    try:
        from astroquery.vizier import Vizier
        import astropy.coordinates as coord

        ztf_coord = SkyCoord(ra=ra * u.deg, dec=dec * u.deg)
        gaia_catalog = "I/355/gaiadr3"
        gaia_cols = ['Source', 'RA_ICRS', 'DE_ICRS']

        Vizier.ROW_LIMIT = 20

        # Stage 1: 10 arcsec
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
            seps = ztf_coord.separation(gaia_coords).arcsec
            best_idx = int(np.argmin(seps))
            return {
                'source_idx': source_idx,
                'gaia_source_id': int(cat['Source'][best_idx]),
                'is_ambiguous': False,
                'status': 'match'
            }

        # Stage 2: 100 arcsec fallback
        result2 = Vizier(columns=gaia_cols).query_region(
            coord.SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame='icrs'),
            radius=100 * u.arcsec,
            catalog=gaia_catalog
        )

        if result2 and len(result2) > 0 and len(result2[0]) > 0:
            cat2 = result2[0]
            gaia_coords2 = SkyCoord(
                ra=cat2['RA_ICRS'].data * u.deg,
                dec=cat2['DE_ICRS'].data * u.deg
            )
            seps2 = ztf_coord.separation(gaia_coords2).arcsec
            best_idx2 = int(np.argmin(seps2))
            return {
                'source_idx': source_idx,
                'gaia_source_id': int(cat2['Source'][best_idx2]),
                'is_ambiguous': True,
                'status': 'ambiguous'
            }

        return {
            'source_idx': source_idx,
            'gaia_source_id': None,
            'is_ambiguous': False,
            'status': 'no_match'
        }

    except Exception as e:
        worker_logger.warning(f"Gaia worker failed for source {source_idx} (ra={ra:.4f}, dec={dec:.4f}): {e}")
        return {
            'source_idx': source_idx,
            'gaia_source_id': None,
            'is_ambiguous': False,
            'status': 'error'
        }


# =========================================================================
# Funzione di calcolo indici (top-level per riusabilita')
# =========================================================================
def _compute_variability_indices(mags: np.ndarray, magerrs: np.ndarray) -> Optional[dict]:
    """
    Calcola indici di variabilita' per una singola sorgente.

    Args:
        mags: Array magnitudini (gia' filtrate, catflags==0)
        magerrs: Array errori fotometrici corrispondenti

    Returns:
        dict con indici, oppure None se N < 3
    """
    N = len(mags)
    if N < 3:
        return None

    # Errori sicuri (evita divisione per zero)
    errs = np.maximum(np.abs(magerrs), 1e-6)

    # Magnitudine media pesata
    weights = 1.0 / errs ** 2
    mean_mag = float(np.average(mags, weights=weights))

    # Standard deviation (RMS)
    std_dev = float(np.std(mags))

    # Chi-quadrato ridotto
    chi_sq = float(np.sum(((mags - mean_mag) / errs) ** 2) / (N - 1))

    # MAD (Median Absolute Deviation)
    mad = float(np.median(np.abs(mags - np.median(mags))))

    # IQR (Interquartile Range)
    iqr = float(np.percentile(mags, 75) - np.percentile(mags, 25))

    # Residui normalizzati per Stetson
    delta = np.sqrt(float(N) / (N - 1)) * (mags - mean_mag) / errs

    # Stetson J (coppie consecutive - approssimazione efficiente per LC ordinate per tempo)
    if N >= 2:
        P = delta[:-1] * delta[1:]
        stetson_j = float(np.sum(np.sign(P) * np.sqrt(np.abs(P))) / N)
    else:
        stetson_j = 0.0

    # Stetson K
    sum_abs_delta = np.sum(np.abs(delta))
    sum_sq_delta = np.sum(delta ** 2)
    if sum_sq_delta > 0:
        stetson_k = float((sum_abs_delta / N) / np.sqrt(sum_sq_delta / N))
    else:
        stetson_k = 0.0

    return {
        'mean_mag': mean_mag,
        'std_dev': std_dev,
        'chi_squared': chi_sq,
        'mad': mad,
        'iqr': iqr,
        'stetson_j': stetson_j,
        'stetson_k': stetson_k,
        'n_points_used': N,
        'mag_err_median': float(np.median(errs)),
    }


# =========================================================================
# Classe servizio principale
# =========================================================================
class ZtfSurveyService(CaggRefreshMixin):
    """Orchestrator pipeline ZTF Field Survey."""

    def create_job(
        self,
        target_name: str,
        ra_center: float,
        dec_center: float,
        radius_deg: float,
        ztf_filter: str,
        mag_min: Optional[float],
        mag_max: Optional[float],
        min_observations: int,
        user_id: str,
        user_email: str,
        association_id: Optional[int] = None
    ) -> ZtfSurveyJob:
        """
        Valida i parametri, genera job_code univoco, persiste ZtfSurveyJob.

        Raises:
            ValueError: se parametri non validi
        """
        # Validazioni
        if dec_center < -30:
            raise ValueError("ZTF non copre Dec < -30 gradi (emisfero sud)")
        if radius_deg <= 0 or radius_deg > 2.0:
            raise ValueError("Raggio deve essere tra 0.001 e 2.0 gradi")
        if ztf_filter not in ('g', 'r', 'i'):
            raise ValueError("Filtro ZTF deve essere g, r, o i")
        if min_observations < 5:
            raise ValueError("min_observations deve essere almeno 5")

        db = SessionLocal()
        try:
            # Genera job_code univoco (stesso pattern di VastService)
            timestamp = int(time.time() * 1000) % 100000
            job_code = f"ZSURVEY-{datetime.now().year}-{timestamp:05d}"

            max_attempts = 10
            attempt = 0
            while db.query(ZtfSurveyJob).filter(ZtfSurveyJob.job_code == job_code).first() and attempt < max_attempts:
                timestamp = (timestamp + 1) % 100000
                job_code = f"ZSURVEY-{datetime.now().year}-{timestamp:05d}"
                attempt += 1

            if attempt >= max_attempts:
                job_count = db.query(ZtfSurveyJob).count()
                job_code = f"ZSURVEY-{datetime.now().year}-{job_count + 1:05d}"

            job = ZtfSurveyJob(
                job_code=job_code,
                target_name=target_name,
                association_id=association_id,
                ra_center=ra_center,
                dec_center=dec_center,
                radius_deg=radius_deg,
                ztf_filter=ztf_filter,
                mag_min=mag_min,
                mag_max=mag_max,
                min_observations=min_observations,
                created_by=user_id,
                state='pending',
                progress_pct=0,
            )

            db.add(job)
            db.commit()
            db.refresh(job)

            log_audit(
                user_id=user_id,
                user_email=user_email,
                association_id=association_id,
                action='ztf_survey_job_created',
                entity_type='ztf_survey_job',
                entity_id=str(job.id),
                new_value=job_code,
                description=f"Created ZTF survey job {job_code} for '{target_name}' (RA={ra_center:.4f}, Dec={dec_center:.4f}, r={radius_deg:.2f}°, filter={ztf_filter})"
            )

            logger.info(f"Created ZTF survey job {job_code} (ID: {job.id})")
            return job

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create ZTF survey job: {e}", exc_info=True)
            raise
        finally:
            db.close()

    # =========================================================================
    # Orchestratore pipeline (eseguito in background thread)
    # =========================================================================

    def execute_job(self, job_id: int):
        """
        Orchestratore pipeline completa. Chiamato in background thread.

        Bands di progresso:
            0-5%   : init
            5-40%  : download dati IRSA
            40-65% : calcolo indici variabilita'
            65-70% : identificazione candidati
            70-83% : VSX cross-match
            83-95% : Gaia cross-match
            95-99% : salvataggio risultati DB
            100%   : completato
        """
        db = SessionLocal()
        try:
            job = db.query(ZtfSurveyJob).get(job_id)
            if not job:
                logger.error(f"ZTF survey job {job_id} not found")
                return

            logger.info(f"Starting ZTF survey job {job.job_code}")
            job.state = 'downloading'
            job.started_at = datetime.utcnow()
            job.progress_pct = 5
            job.current_step = 'Inizializzazione'
            db.commit()

            # Step 1: Query ztf_objects_dr24 (indici già precalcolati dal DR)
            job.current_step = f'Query ztf_objects_dr24 via TAP (RA={job.ra_center:.2f}, Dec={job.dec_center:.2f}, r={job.radius_deg:.2f}°, filtro={job.ztf_filter})'
            db.commit()

            try:
                sources_df = self._download_ztf_field(job)
            except Exception as e:
                self._fail_job(db, job, f"Query ZTF fallita: {e}")
                return

            if sources_df is None or sources_df.empty:
                self._fail_job(db, job, "Nessuna sorgente ZTF trovata nel campo specificato (controlla coordinate e raggio)")
                return

            job.total_sources = len(sources_df)
            job.progress_pct = 60
            job.state = 'analyzing'
            job.current_step = f'{len(sources_df)} sorgenti ZTF trovate. Identificazione candidati...'
            db.commit()
            logger.info(f"[{job.job_code}] Found {len(sources_df)} sources from ztf_objects_dr24")

            # Step 2: Identificazione candidati (indici già presenti dal DR)
            sources_df = self._identify_candidates(sources_df, job)
            candidates_count = int(sources_df['is_candidate'].sum())
            job.candidates_found = candidates_count
            job.progress_pct = 65
            job.current_step = f'{candidates_count} candidati identificati. Cross-match VSX...'
            db.commit()
            logger.info(f"[{job.job_code}] {candidates_count} candidates identified")

            # Step 4: VSX cross-match
            job.state = 'crossmatching'
            db.commit()
            try:
                sources_df = self._crossmatch_vsx(sources_df, job)
            except Exception as e:
                logger.warning(f"[{job.job_code}] VSX cross-match failed (continuing): {e}")
                sources_df['vsx_match'] = None
                sources_df['is_known_variable'] = False
                sources_df['variable_type'] = None

            known_count = int(sources_df['is_known_variable'].sum())
            job.known_variables_found = known_count
            job.progress_pct = 83
            job.current_step = f'{known_count} variabili note VSX trovate. Cross-match Gaia...'
            db.commit()
            logger.info(f"[{job.job_code}] {known_count} known variables from VSX")

            # Step 5: Gaia cross-match
            try:
                sources_df = self._crossmatch_gaia(sources_df, job, db)
            except Exception as e:
                logger.warning(f"[{job.job_code}] Gaia cross-match failed (continuing): {e}")
                sources_df['gaia_source_id'] = None
                sources_df['is_ambiguous'] = False

            job.progress_pct = 95
            job.current_step = 'Salvataggio risultati in database...'
            db.commit()

            # Step 6: Salvataggio risultati
            try:
                self._save_results(sources_df, job, db)
            except Exception as e:
                self._fail_job(db, job, f"Salvataggio risultati fallito: {e}")
                return

            # Completamento
            job.state = 'completed'
            job.completed_at = datetime.utcnow()
            job.progress_pct = 100
            job.current_step = 'Analisi completata'
            db.commit()

            # Force refresh cagg immediately (Phase 3 optimization)
            self.refresh_cagg_for_table(db, 'agata_ztf_survey_results', 'ztf_job_summary')

            logger.info(
                f"ZTF survey job {job.job_code} completed: "
                f"{job.total_sources} sorgenti, {job.candidates_found} candidati, "
                f"{job.known_variables_found} variabili note VSX"
            )

        except Exception as e:
            logger.error(f"ZTF survey job {job_id} failed: {e}", exc_info=True)
            try:
                job.state = 'failed'
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                db.commit()
            except Exception:
                pass
        finally:
            db.close()

    def _fail_job(self, db, job: ZtfSurveyJob, message: str):
        """Imposta job in stato failed con messaggio errore."""
        job.state = 'failed'
        job.error_message = message
        job.completed_at = datetime.utcnow()
        db.commit()
        logger.error(f"[{job.job_code}] FAILED: {message}")

    # =========================================================================
    # Step 1: Query ztf_objects_dr24 via TAP (indici già precalcolati dal DR)
    # =========================================================================

    def _download_ztf_field(self, job: ZtfSurveyJob) -> Optional[pd.DataFrame]:
        """
        Query ztf_objects_dr24 via IRSA TAP.

        La tabella ztf_objects_dr24 contiene un record per sorgente per filtro con
        gli indici di variabilità già precalcolati (magrms, chisq, medianabsdev, ecc.).
        Evita il download di lightcurve raw epoch-level, che causa timeout su area queries.

        Returns:
            DataFrame con colonne: ztf_object_id, ra, dec, n_points, n_points_used,
                                   mean_mag, std_dev, chi_squared, mad, mag_err_median,
                                   stetson_j (None), stetson_k (None), iqr (None)
            oppure None se nessuna sorgente trovata
        Raises:
            RuntimeError se astroquery non disponibile o TAP irraggiungibile
        """
        if not _IRSA_CLIENT_AVAILABLE:
            raise RuntimeError("astroquery non disponibile - installa con: pip install astroquery")

        filtercode = ZTF_FILTER_MAP.get(job.ztf_filter, 'zr')

        mag_filter = ""
        if job.mag_min is not None:
            mag_filter += f"\nAND medianmag >= {job.mag_min}"
        if job.mag_max is not None:
            mag_filter += f"\nAND medianmag <= {job.mag_max}"

        query = f"""SELECT oid, ra, dec, ngoodobs, medianmag, magrms, chisq, medianabsdev, medmagerr
FROM ztf_objects_dr24
WHERE CONTAINS(
    POINT('ICRS', ra, dec),
    CIRCLE('ICRS', {job.ra_center}, {job.dec_center}, {job.radius_deg})
)=1
AND filtercode = '{filtercode}'
AND ngoodobs >= {job.min_observations}{mag_filter}"""

        logger.info(
            f"[{job.job_code}] Querying ztf_objects_dr24 via TAP: "
            f"RA={job.ra_center}, Dec={job.dec_center}, r={job.radius_deg}°, filter={filtercode}"
        )

        result = _IrsaClient.query_tap(query)
        df = result.to_table().to_pandas()

        if df.empty:
            logger.warning(f"[{job.job_code}] ztf_objects_dr24: nessuna sorgente trovata")
            return None

        logger.info(f"[{job.job_code}] ztf_objects_dr24 returned {len(df)} sorgenti")

        # Rinomina colonne per compatibilità con il resto della pipeline
        df = df.rename(columns={
            'oid': 'ztf_object_id',
            'ngoodobs': 'n_points_used',
            'medianmag': 'mean_mag',
            'magrms': 'std_dev',
            'chisq': 'chi_squared',
            'medianabsdev': 'mad',
            'medmagerr': 'mag_err_median',
        })
        df['n_points'] = df['n_points_used']
        # Stetson J/K e IQR non sono disponibili in ztf_objects_dr24 (richiedono lightcurve raw)
        df['stetson_j'] = None
        df['stetson_k'] = None
        df['iqr'] = None

        return df

    # =========================================================================
    # Step 2: Identificazione candidati
    # =========================================================================

    # Soglie default per identificazione candidati (non configurabili dall'utente al momento
    # della creazione: si applicano sempre, l'utente poi filtra/seleziona dalla UI)
    CHI2_THRESHOLD = 3.0

    def _identify_candidates(self, sources_df: pd.DataFrame, job: ZtfSurveyJob) -> pd.DataFrame:
        """
        Marca is_candidate=True dove chi_squared > CHI2_THRESHOLD.

        Usa chi_squared ridotto precalcolato da ztf_objects_dr24.
        chi_squared > 3 indica variabilità significativa rispetto al rumore fotometrico.
        Stetson J non è disponibile senza lightcurve raw epoch-level.
        Le soglie sono default di pipeline; l'utente filtra ulteriormente dalla UI.
        """
        has_chi2 = 'chi_squared' in sources_df.columns and sources_df['chi_squared'].notna().any()

        if has_chi2:
            sources_df['is_candidate'] = sources_df['chi_squared'] > self.CHI2_THRESHOLD
        else:
            sources_df['is_candidate'] = False

        return sources_df

    # =========================================================================
    # Step 4: VSX Cross-match
    # =========================================================================

    def _crossmatch_vsx(self, sources_df: pd.DataFrame, job: ZtfSurveyJob) -> pd.DataFrame:
        """
        Cross-match con VSX (AAVSO) via astroquery Vizier.

        Singola query conica centrata sul campo, poi match posizionale a 25".
        Riusa pattern da vast_service._crossmatch_vizier.
        """
        try:
            import astropy.units as u
            import astropy.coordinates as coord
            from astropy.coordinates import match_coordinates_sky
            from astroquery.vizier import Vizier
        except ImportError:
            logger.warning("astroquery non disponibile, skip VSX cross-match")
            sources_df['is_known_variable'] = False
            sources_df['variable_type'] = None
            sources_df['vsx_match'] = None
            sources_df['catalog_matches'] = None
            return sources_df

        # Init colonne
        sources_df = sources_df.copy()
        sources_df['is_known_variable'] = False
        sources_df['variable_type'] = None
        sources_df['vsx_match'] = None
        sources_df['catalog_matches'] = None

        try:
            Vizier.ROW_LIMIT = -1
            center = coord.SkyCoord(
                ra=job.ra_center * u.deg,
                dec=job.dec_center * u.deg
            )

            # Cerca VSX nell'intera area del campo
            search_radius = max(job.radius_deg, 0.5) * u.deg
            vsx_result = Vizier(columns=['OID', 'RAJ2000', 'DEJ2000', 'Name', 'Type']).query_region(
                center,
                radius=search_radius,
                catalog='B/vsx/vsx'
            )

            if not vsx_result or len(vsx_result) == 0:
                logger.info(f"[{job.job_code}] Nessun risultato VSX nell'area")
                return sources_df

            vsx_cat = vsx_result[0]
            logger.info(f"[{job.job_code}] VSX: {len(vsx_cat)} variabili nel campo")

            # Coordinate sorgenti ZTF
            ztf_coords = coord.SkyCoord(
                ra=sources_df['ra'].values * u.deg,
                dec=sources_df['dec'].values * u.deg
            )

            # Coordinate VSX
            vsx_coords = coord.SkyCoord(
                ra=vsx_cat['RAJ2000'].data * u.deg,
                dec=vsx_cat['DEJ2000'].data * u.deg
            )

            # Match posizionale
            max_sep = 25 * u.arcsec
            idx, d2d, _ = match_coordinates_sky(ztf_coords, vsx_coords)

            matched_mask = d2d < max_sep

            for i, (is_matched, vsx_idx) in enumerate(zip(matched_mask, idx)):
                if is_matched:
                    vsx_row = vsx_cat[int(vsx_idx)]
                    sources_df.at[sources_df.index[i], 'is_known_variable'] = True
                    sources_df.at[sources_df.index[i], 'variable_type'] = str(vsx_row['Type']) if vsx_row['Type'] else None
                    sources_df.at[sources_df.index[i], 'vsx_match'] = {
                        'oid': str(vsx_row['OID']),
                        'name': str(vsx_row['Name']) if 'Name' in vsx_cat.colnames else None,
                        'type': str(vsx_row['Type']) if vsx_row['Type'] else None,
                    }
                    sources_df.at[sources_df.index[i], 'catalog_matches'] = 'AAVSO'

            n_vsx = int(matched_mask.sum())
            logger.info(f"[{job.job_code}] VSX: {n_vsx} sorgenti matchate")

        except Exception as e:
            logger.warning(f"[{job.job_code}] VSX cross-match error: {e}", exc_info=True)

        return sources_df

    # =========================================================================
    # Step 5: Gaia Cross-match
    # =========================================================================

    def _crossmatch_gaia(self, sources_df: pd.DataFrame, job: ZtfSurveyJob, db) -> pd.DataFrame:
        """
        Cross-match con Gaia DR3 in parallelo usando _ztf_gaia_worker.

        Nessuna calibrazione magnitudine (ZTF gia' calibrato).
        is_valid = gaia_source_id IS NOT NULL AND NOT is_ambiguous
        """
        sources_df = sources_df.copy()
        n = len(sources_df)

        logger.info(f"[{job.job_code}] Gaia cross-match per {n} sorgenti")

        # Prepara parametri per i worker
        params_list = [
            (int(i), float(row['ra']), float(row['dec']))
            for i, (_, row) in enumerate(sources_df.iterrows())
        ]

        # Mappa idx → posizione nel DataFrame
        idx_to_df_idx = {
            int(i): df_idx
            for i, (df_idx, _) in enumerate(sources_df.iterrows())
        }

        gaia_results = {}
        max_workers = min(8, n)
        completed_count = 0
        UPDATE_EVERY = max(1, n // 20)  # aggiorna ogni ~5%

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_ztf_gaia_worker, p): p[0] for p in params_list}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    gaia_results[result['source_idx']] = result
                except Exception as e:
                    source_idx = futures[future]
                    logger.warning(f"[{job.job_code}] Worker {source_idx} exception: {e}")
                    gaia_results[source_idx] = {
                        'source_idx': source_idx,
                        'gaia_source_id': None,
                        'is_ambiguous': False,
                        'status': 'error'
                    }

                completed_count += 1
                if completed_count % UPDATE_EVERY == 0 or completed_count == n:
                    pct = 83 + int(12 * completed_count / n)  # 83% → 95%
                    job.progress_pct = pct
                    job.current_step = f'Cross-match Gaia: {completed_count}/{n} sorgenti processate...'
                    db.commit()

        # Aggiorna DataFrame con risultati Gaia
        sources_df['gaia_source_id'] = None
        sources_df['is_ambiguous'] = False
        sources_df['is_valid'] = False

        matched = 0
        for source_idx, gaia_result in gaia_results.items():
            df_idx = idx_to_df_idx.get(source_idx)
            if df_idx is None:
                continue
            gaia_id = gaia_result.get('gaia_source_id')
            is_ambiguous = gaia_result.get('is_ambiguous', False)
            sources_df.at[df_idx, 'gaia_source_id'] = gaia_id
            sources_df.at[df_idx, 'is_ambiguous'] = is_ambiguous
            sources_df.at[df_idx, 'is_valid'] = (gaia_id is not None and not is_ambiguous)

            if gaia_id is not None:
                matched += 1
                # Aggiorna catalog_matches
                existing = sources_df.at[df_idx, 'catalog_matches']
                if existing and 'Gaia' not in existing:
                    sources_df.at[df_idx, 'catalog_matches'] = f"Gaia,{existing}"
                elif not existing:
                    sources_df.at[df_idx, 'catalog_matches'] = 'Gaia'

        logger.info(f"[{job.job_code}] Gaia: {matched}/{n} sorgenti matchate")
        return sources_df

    # =========================================================================
    # Step 6: Salvataggio risultati
    # =========================================================================

    def _mark_duplicates(self, sources_df: pd.DataFrame) -> pd.DataFrame:
        """
        Per ogni gaia_source_id con più OID ZTF: il vincitore (max n_points_used,
        tie-break chi_squared minore) rimane is_valid invariato; gli altri
        ottengono is_duplicate=True, is_valid=False.

        Causa tipica: artefatti ZTF DR (stessa stella fisica estratta con due OID
        distinti per differenze di processing interno o sovrapposizione di PSF).
        """
        sources_df = sources_df.copy()
        sources_df['is_duplicate'] = False

        has_gaia = sources_df['gaia_source_id'].notna()
        if not has_gaia.any():
            return sources_df

        for gaia_id, group in sources_df[has_gaia].groupby('gaia_source_id'):
            if len(group) <= 1:
                continue
            sorted_group = group.sort_values(
                by=['n_points_used', 'chi_squared'],
                ascending=[False, True],
                na_position='last'
            )
            loser_idxs = sorted_group.index[1:]
            sources_df.loc[loser_idxs, 'is_duplicate'] = True
            sources_df.loc[loser_idxs, 'is_valid'] = False

        n_dup = int(sources_df['is_duplicate'].sum())
        if n_dup > 0:
            logger.info(f"Deduplicazione Gaia: {n_dup} sorgenti marcate is_duplicate=True")
        return sources_df

    def _save_results(self, sources_df: pd.DataFrame, job: ZtfSurveyJob, db):
        """
        Salva i risultati in agata_ztf_survey_results (batch da 100).
        Prima del salvataggio deduplica per gaia_source_id.
        """
        sources_df = self._mark_duplicates(sources_df)

        batch = []
        n_saved = 0

        for _, row in sources_df.iterrows():
            result = ZtfSurveyResult(
                job_id=job.id,
                ztf_object_id=int(row['ztf_object_id']) if row.get('ztf_object_id') is not None else None,
                ra=float(row['ra']),
                decl=float(row['dec']),
                n_points=int(row.get('n_points', 0)),
                n_points_used=int(row.get('n_points_used', 0)),
                mean_mag=float(row['mean_mag']) if 'mean_mag' in row and row['mean_mag'] is not None else None,
                std_dev=float(row['std_dev']) if 'std_dev' in row and row['std_dev'] is not None else None,
                mag_err_median=float(row['mag_err_median']) if 'mag_err_median' in row and row['mag_err_median'] is not None else None,
                stetson_j=float(row['stetson_j']) if 'stetson_j' in row and row['stetson_j'] is not None else None,
                stetson_k=float(row['stetson_k']) if 'stetson_k' in row and row['stetson_k'] is not None else None,
                chi_squared=float(row['chi_squared']) if 'chi_squared' in row and row['chi_squared'] is not None else None,
                mad=float(row['mad']) if 'mad' in row and row['mad'] is not None else None,
                iqr=float(row['iqr']) if 'iqr' in row and row['iqr'] is not None else None,
                is_candidate=bool(row.get('is_candidate', False)),
                is_known_variable=bool(row.get('is_known_variable', False)),
                is_valid=bool(row.get('is_valid', False)),
                is_ambiguous=bool(row.get('is_ambiguous', False)),
                is_duplicate=bool(row.get('is_duplicate', False)),
                gaia_source_id=int(row['gaia_source_id']) if row.get('gaia_source_id') is not None else None,
                vsx_match=row.get('vsx_match'),
                catalog_matches=row.get('catalog_matches'),
                variable_type=row.get('variable_type'),
            )
            batch.append(result)

            if len(batch) >= 100:
                db.add_all(batch)
                db.commit()
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
        exclude_known_variables: bool = False,
        exclude_in_agata: bool = False
    ) -> dict:
        """
        Promuove i risultati ZTF Survey validati in agata_star_photometry.

        Per ogni risultato eligible (is_valid=True, gaia_source_id presente):
        1. Re-query IRSA per il singolo oid (stessa sintassi di ztf.py)
        2. Inserisce dati in agata_star_photometry (catalog_name = 'ZTFr'/'ZTFg'/'ZTFi')
        3. Aggiorna cache agata_star via _upsert_star_photometry

        Nota: NON crea progetti automaticamente (workflow a due step come VAST).

        Returns:
            dict {promoted, lightcurve_points, skipped_no_gaia, skipped_known, import_id, errors}
        """
        from agata.db import engine
        db = SessionLocal()
        stats = {
            'promoted': 0,
            'lightcurve_points': 0,
            'skipped_no_gaia': 0,
            'skipped_known': 0,
            'errors': [],
            'import_id': None,
        }

        promo_started_at = time.time()

        def _save_promo_state(state_str, total=0):
            """Scrive lo stato promozione in output_data['promotion'] per il polling UI."""
            db2 = None
            try:
                import json as _json
                promo_data = {
                    'state': state_str,
                    'started_at': promo_started_at,
                    'promoted': stats['promoted'],
                    'total': total,
                    'lightcurve_points': stats['lightcurve_points'],
                    'errors': stats['errors'][-5:],
                    'import_id': stats['import_id'],
                }
                db2 = SessionLocal()
                full_data = _json.dumps({'promotion': promo_data})
                db2.execute(
                    text("UPDATE agata_ztf_survey_jobs SET output_data = :od WHERE id = :jid"),
                    {'od': full_data, 'jid': job_id}
                )
                db2.commit()
            except Exception as ex:
                logger.warning(f"_save_promo_state failed: {ex}")
                if db2:
                    try:
                        db2.rollback()
                    except:
                        pass
            finally:
                if db2:
                    db2.close()

        try:
            job = db.query(ZtfSurveyJob).get(job_id)
            if not job:
                raise ValueError(f"Job {job_id} non trovato")

            if job.state != 'completed':
                raise ValueError(f"Il job deve essere completato per promuovere (stato: {job.state})")

            # Carica risultati
            try:
                results = db.query(ZtfSurveyResult).filter(ZtfSurveyResult.job_id == job_id).all()
            except Exception as e:
                logger.error(f"Errore loading results per job {job_id}: {e}", exc_info=True)
                db.rollback()
                raise

            if not results:
                raise ValueError("Nessun risultato trovato per questo job")

            # Batch check: quali Gaia ID hanno già dati ZTF in agata_star_photometry?
            gaia_ids_in_db = set()
            if exclude_in_agata:
                all_gaia_ids = [str(r.gaia_source_id) for r in results if r.gaia_source_id]
                if all_gaia_ids:
                    placeholders = ','.join([f':gid{i}' for i in range(len(all_gaia_ids))])
                    rows_in_db = db.execute(
                        text(f"SELECT DISTINCT source_id::text FROM agata_star_photometry WHERE catalogo IN ('ZTFr','ZTFg','ZTFi') AND source_id IN ({placeholders})"),
                        {f'gid{i}': int(gid) for i, gid in enumerate(all_gaia_ids)}
                    ).fetchall()
                    gaia_ids_in_db = {str(row[0]) for row in rows_in_db}
                    logger.info(f"[{job.job_code}] Gaia ID già in AGATA con dati ZTF: {len(gaia_ids_in_db)}")

            # Filtra eligible
            eligible = []
            stats['skipped_in_agata'] = 0
            stats['skipped_not_valid'] = 0
            stats['skipped_result_ids'] = 0

            # Se result_ids è specificato, ignora exclude_in_agata
            # (l'utente sta selezionando stelle specifiche da promuovere)
            use_exclude_in_agata = exclude_in_agata and (result_ids is None or len(result_ids) == 0)

            logger.info(
                f"[{job.job_code}] Starting eligibility filter: result_ids={result_ids}, "
                f"use_exclude_in_agata={use_exclude_in_agata}, total_results={len(results)}"
            )

            for r in results:
                if not r.gaia_source_id:
                    stats['skipped_no_gaia'] += 1
                    continue
                if exclude_known_variables and r.is_known_variable:
                    stats['skipped_known'] += 1
                    continue
                if use_exclude_in_agata and str(r.gaia_source_id) in gaia_ids_in_db:
                    stats['skipped_in_agata'] += 1
                    continue
                if not r.is_valid:
                    stats['skipped_not_valid'] += 1
                    if result_ids and r.id in result_ids:
                        logger.warning(f"[{job.job_code}] SELECTED but not valid: result_id {r.id}, gaia_id {r.gaia_source_id}, is_valid={r.is_valid}")
                    continue
                # Se result_ids è passato, filtrare per result.id (non gaia_source_id)
                # L'UI passa result IDs dalla tabella agata_ztf_survey_results
                if result_ids is not None and len(result_ids) > 0:
                    if r.id in result_ids:
                        logger.info(f"[{job.job_code}] SELECTED: result_id {r.id}, gaia_id {r.gaia_source_id}, is_valid={r.is_valid}")
                    else:
                        stats['skipped_result_ids'] += 1
                        continue

                eligible.append(r)

            logger.info(
                f"[{job.job_code}] Promozione: {len(eligible)} eligible "
                f"(skip no_gaia={stats['skipped_no_gaia']}, skip known={stats['skipped_known']}, "
                f"skip in_agata={stats.get('skipped_in_agata',0)}, skip not_valid={stats['skipped_not_valid']}, "
                f"skip result_ids={stats['skipped_result_ids']})"
            )

            if not eligible:
                raise ValueError(
                    f"Nessuna stella eligible per la promozione. "
                    f"Results: {len(results)}, skipped: no_gaia={stats['skipped_no_gaia']}, "
                    f"known={stats['skipped_known']}, in_agata={stats.get('skipped_in_agata',0)}, "
                    f"not_valid={stats['skipped_not_valid']}, result_ids={stats['skipped_result_ids']}"
                )

            _save_promo_state('running', total=len(eligible))

            # Crea CatalogImport record per tracciabilita'
            import_record = create_import_record(
                db=db,
                catalog_name=f"ZTF-{job.ztf_filter.upper()} Survey",
                search_type='file',
                search_value=job.job_code,
                ra=job.ra_center,
                dec=job.dec_center,
                radius_arcsec=job.radius_deg * 3600,
                gaia_id=None,
                user_id=user_id,
                state='importing'
            )
            logger.info(f"[{job.job_code}] CatalogImport #{import_record.id} creato")

            catalog_name = job.catalog_name  # 'ZTFr', 'ZTFg', 'ZTFi'
            filtercode = job.filtercode       # 'zr', 'zg', 'zi'

            # Promuovi ogni stella (salva stato ogni 5 per il polling)
            for idx, r in enumerate(eligible):
                gaia_id_str = str(r.gaia_source_id)
                try:
                    lc_df = self._fetch_single_source_lc_by_oid(r.ztf_object_id, filtercode)
                    if lc_df is None or lc_df.empty:
                        stats['errors'].append(f"Nessun dato IRSA per oid {r.ztf_object_id}")
                        continue

                    points = insert_catalog_data(
                        db=db,
                        gaia_id=gaia_id_str,
                        catalog_name=catalog_name,
                        data=lc_df,
                        association_id_owner=None,
                        catalog_import_id=import_record.id
                    )
                    stats['lightcurve_points'] += points

                    if points > 0:
                        _upsert_star_photometry(db, gaia_id_str)
                        stats['promoted'] += 1

                except Exception as e:
                    error_msg = f"Errore promozione oid {r.ztf_object_id}: {e}"
                    logger.error(error_msg, exc_info=True)
                    stats['errors'].append(error_msg)

                # Aggiorna progresso ogni 5 stelle
                if (idx + 1) % 5 == 0:
                    _save_promo_state('running', total=len(eligible))

            # Aggiorna stats job
            job.promoted_count = stats['promoted']
            try:
                db.commit()
            except Exception as e:
                logger.error(f"Errore commit stats job: {e}")
                db.rollback()
                # Ricrea sessione se commit fallisce
                db.close()
                engine.dispose()
                db = SessionLocal()

            # Finalizza CatalogImport con sessione fresca per evitare oggetti stale
            # (insert_catalog_data fa commit sulla stessa sessione durante il loop)
            import_id_to_finalize = import_record.id
            db.close()
            engine.dispose()  # Scarta pool prima di ricrearlo
            db = SessionLocal()

            import_record_fresh = db.query(CatalogImport).get(import_id_to_finalize)
            update_import_with_results(
                db=db,
                import_record=import_record_fresh,
                catalog_name=catalog_name,
                success=True,
                point_count=stats['lightcurve_points'],
            )
            finalize_import(
                db=db,
                import_record=import_record_fresh,
                points_imported=stats['lightcurve_points'],
                user_id=user_id,
                user_email=user_email,
                association_id=None,
                auto_create_project=False,
                catalog_name=catalog_name
            )

            stats['import_id'] = import_id_to_finalize
            _save_promo_state('completed', total=len(eligible))

            log_audit(
                user_id=user_id,
                user_email=user_email,
                association_id=None,
                action='ztf_survey_promoted',
                entity_type='ztf_survey_job',
                entity_id=str(job_id),
                new_value=f"{stats['promoted']} stelle, {stats['lightcurve_points']} punti, import #{import_id_to_finalize}",
                description=(
                    f"Promosso ZTF survey job {job_id}: {stats['promoted']} stelle, "
                    f"{stats['lightcurve_points']} punti fotometrici (import #{import_id_to_finalize})"
                )
            )

            logger.info(
                f"[job {job_id}] Promozione completata: {stats['promoted']} stelle, "
                f"{stats['lightcurve_points']} punti (import #{import_id_to_finalize})"
            )
            return stats

        except Exception as e:
            try:
                db.rollback()
            except:
                pass

            # Scarta tutte le connessioni dal pool se qualcosa è andato storto
            # Questo evita che una connessione "aborted" contamini le richieste successive
            from agata.db import engine
            engine.dispose()

            _save_promo_state('failed')
            logger.error(f"Promozione fallita per job {job_id}: {e}", exc_info=True)
            raise
        finally:
            db.close()

    def _fetch_single_source_lc_by_oid(self, ztf_object_id: int, filtercode: str) -> Optional[pd.DataFrame]:
        """
        Fetcha la curva di luce per un oid ZTF specifico via ID= (stabile, ~4s).

        Usa nph_light_curves?ID=<oid> invece di POS=CIRCLE (che va in timeout).
        Ritorna DataFrame con colonne [hjd, mag].
        """
        params = {
            "ID": str(ztf_object_id),
            "FORMAT": "csv",
            "BAD_CATFLAGS_MASK": "32768",
        }

        try:
            resp = requests.get(IRSA_LIGHTCURVES_URL, params=params, timeout=30)
            resp.raise_for_status()
            content = resp.text.strip()
        except Exception as e:
            logger.warning(f"Re-query IRSA by oid={ztf_object_id} failed: {e}")
            return None

        if not content or 'No data found' in content or content.startswith('<!DOCTYPE'):
            return None

        lines = [l for l in content.splitlines() if not l.startswith('\\')]
        if not lines:
            return None

        try:
            df = pd.read_csv(io.StringIO('\n'.join(lines)))
        except Exception:
            return None

        if df.empty:
            return None

        if 'catflags' in df.columns:
            df = df[df['catflags'] == 0]
        if 'filtercode' in df.columns:
            df = df[df['filtercode'] == filtercode]

        if df.empty:
            return None

        if 'hjd' in df.columns:
            hjd_col = df['hjd']
        elif 'mjd' in df.columns:
            hjd_col = df['mjd'] + MJD_TO_HJD_OFFSET
        else:
            return None

        result = pd.DataFrame({'hjd': hjd_col, 'mag': df['mag']})
        return result.dropna(subset=['hjd', 'mag']).sort_values('hjd').reset_index(drop=True)

    def _fetch_single_source_lc(self, ra: float, dec: float, filtercode: str) -> Optional[pd.DataFrame]:
        """
        Re-query IRSA per una singola sorgente (cono stretto di 0.001 gradi ~3.6").

        Riusa la stessa sintassi di _query_ztf_lightcurve in ztf.py.
        Ritorna DataFrame con colonne [hjd, mag].
        """
        params = {
            "POS": f"CIRCLE {ra} {dec} 0.001",
            "BANDNAME": filtercode[-1],  # 'r', 'g', 'i' dal filtercode 'zr'/'zg'/'zi'
            "FORMAT": "csv",
        }

        try:
            resp = requests.get(IRSA_LIGHTCURVES_URL, params=params, timeout=60)
            resp.raise_for_status()
            content = resp.text.strip()
        except Exception as e:
            logger.warning(f"Re-query IRSA failed (ra={ra:.4f}, dec={dec:.4f}): {e}")
            return None

        if not content or 'No data found' in content or content.startswith('<!DOCTYPE'):
            return None

        lines = [l for l in content.splitlines() if not l.startswith('#')]
        if not lines:
            return None

        try:
            df = pd.read_csv(io.StringIO('\n'.join(lines)))
        except Exception:
            return None

        if df.empty:
            return None

        if 'catflags' in df.columns:
            df = df[df['catflags'] == 0]

        if 'filtercode' in df.columns:
            df = df[df['filtercode'] == filtercode]

        if df.empty:
            return None

        if 'hjd' in df.columns:
            hjd_col = df['hjd']
        elif 'mjd' in df.columns:
            hjd_col = df['mjd'] + MJD_TO_HJD_OFFSET
        else:
            return None

        result = pd.DataFrame({
            'hjd': hjd_col,
            'mag': df['mag'],
        })
        return result.dropna(subset=['hjd', 'mag']).sort_values('hjd').reset_index(drop=True)

    # =========================================================================
    # Metodi ausiliari
    # =========================================================================

    def get_job(self, job_id: int) -> Optional[ZtfSurveyJob]:
        """Carica un job dal DB."""
        db = SessionLocal()
        try:
            return db.query(ZtfSurveyJob).get(job_id)
        finally:
            db.close()

    def list_jobs(
        self,
        limit: int = 100,
        state: Optional[str] = None,
        association_id: Optional[int] = None
    ) -> list:
        """Lista job con filtri opzionali."""
        db = SessionLocal()
        try:
            query = db.query(ZtfSurveyJob).order_by(ZtfSurveyJob.created_at.desc())
            if state:
                query = query.filter(ZtfSurveyJob.state == state)
            if association_id is not None:
                query = query.filter(ZtfSurveyJob.association_id == association_id)
            return query.limit(limit).all()
        finally:
            db.close()

    def delete_job(self, job_id: int, user_id: str, user_email: str) -> dict:
        """Elimina job e tutti i suoi risultati."""
        db = SessionLocal()
        try:
            job = db.query(ZtfSurveyJob).get(job_id)
            if not job:
                raise ValueError(f"Job {job_id} non trovato")

            results_count = db.query(ZtfSurveyResult).filter(ZtfSurveyResult.job_id == job_id).count()
            job_code = job.job_code

            db.delete(job)
            db.commit()

            log_audit(
                user_id=user_id,
                user_email=user_email,
                association_id=None,
                action='ztf_survey_job_deleted',
                entity_type='ztf_survey_job',
                entity_id=str(job_id),
                description=f"Deleted ZTF survey job {job_code} ({results_count} results)"
            )

            return {'deleted': True, 'results_deleted': results_count}
        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()
