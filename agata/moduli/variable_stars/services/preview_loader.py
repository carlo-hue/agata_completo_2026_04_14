# preview_loader.py
"""
Caricamento lightcurve per preview da job pipeline (ZTF / TESS / VAST)
senza promozione in agata_star_photometry.

Fonti supportate:
- tess:  usa lc_full_json già stored in TessImportResult
- ztf:   re-fetch da IRSA via oid + filtercode
- vast:  legge agata_star_photometry via gaia_source_id (uploadati durante job)
"""
import logging
import os
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from agata.auth_models.ztf_survey_job import ZtfSurveyResult
from agata.auth_models.tess_import_job import TessImportResult
from agata.auth_models.vast_job import VastResult
from agata.moduli.variable_stars.services.db_loader import load_lightcurve_from_db
from agata.moduli.admin.services.ztf_survey_service import ZtfSurveyService as _ZtfService

logger = logging.getLogger(__name__)

# Istanza singleton del service ZTF usata solo per il fetch IRSA
_ztf_service = _ZtfService()


@dataclass
class PreviewLoadResult:
    sessions: list          # lista di {session_id, session_name, jd, mag}
    label: str              # etichetta display (es. "ZTF-R | OID 123456")
    source: str             # 'ztf' | 'tess' | 'vast'
    result_id: int
    error: Optional[str] = None


def load_preview(db: Session, source: str, result_id: int) -> PreviewLoadResult:
    """
    Carica la lightcurve di un risultato job pipeline per preview.

    Args:
        db:         sessione SQLAlchemy aperta dal chiamante
        source:     'ztf' | 'tess' | 'vast'
        result_id:  PK della riga nel modello risultato

    Returns:
        PreviewLoadResult con sessions nel formato standard del variable_stars editor.

    Raises:
        ValueError:  source o result_id non validi
        LookupError: riga non trovata in DB
    """
    source = source.lower()
    if source not in ("ztf", "tess", "vast"):
        raise ValueError(f"Source non valido: {source!r}. Valori accettati: ztf, tess, vast")

    if source == "tess":
        return _load_tess(db, result_id)
    if source == "ztf":
        return _load_ztf(db, result_id)
    # vast
    return _load_vast(db, result_id)


# ---------------------------------------------------------------------------
# TESS: usa lc_full_json già stored in TessImportResult
# ---------------------------------------------------------------------------

def _load_tess(db: Session, result_id: int) -> PreviewLoadResult:
    row: Optional[TessImportResult] = db.get(TessImportResult, result_id)
    if row is None:
        raise LookupError(f"TessImportResult id={result_id} non trovato")

    label = f"TESS | TIC {row.tic_id} Sec {row.sector}"

    if row.download_failed or row.lc_full_json is None:
        return PreviewLoadResult(
            sessions=[], label=label, source="tess", result_id=result_id,
            error="Curva di luce TESS non disponibile (download fallito o dati assenti)"
        )

    lc = row.lc_full_json  # {hjd: [...], mag: [...], mag_err: [...]}
    hjd = np.asarray(lc.get("hjd", []), dtype=np.float64)
    mag = np.asarray(lc.get("mag", []), dtype=np.float64)

    if hjd.size == 0:
        return PreviewLoadResult(
            sessions=[], label=label, source="tess", result_id=result_id,
            error="Curva di luce TESS vuota"
        )

    sessions = [{"session_id": 0, "session_name": "TESS", "jd": hjd, "mag": mag}]
    logger.info(f"TESS preview: TIC {row.tic_id} sec {row.sector} → {hjd.size} punti")
    return PreviewLoadResult(sessions=sessions, label=label, source="tess", result_id=result_id)


# ---------------------------------------------------------------------------
# ZTF: re-fetch da IRSA via oid
# ---------------------------------------------------------------------------

def _load_ztf(db: Session, result_id: int) -> PreviewLoadResult:
    row: Optional[ZtfSurveyResult] = db.get(ZtfSurveyResult, result_id)
    if row is None:
        raise LookupError(f"ZtfSurveyResult id={result_id} non trovato")

    filtercode = row.job.filtercode  # 'zg' | 'zr' | 'zi'
    label = f"ZTF-{row.job.ztf_filter.upper()} | OID {row.ztf_object_id}"

    if row.ztf_object_id is None:
        return PreviewLoadResult(
            sessions=[], label=label, source="ztf", result_id=result_id,
            error="OID ZTF assente per questa sorgente"
        )

    df = _ztf_service._fetch_single_source_lc_by_oid(row.ztf_object_id, filtercode)
    if df is None or df.empty:
        return PreviewLoadResult(
            sessions=[], label=label, source="ztf", result_id=result_id,
            error="IRSA non ha restituito dati per questo OID (servizio temporaneamente non disponibile o OID sconosciuto)"
        )

    hjd = df["hjd"].to_numpy(dtype=np.float64)
    mag = df["mag"].to_numpy(dtype=np.float64)
    catalog_name = f"ZTF{row.job.ztf_filter}"
    sessions = [{"session_id": 0, "session_name": catalog_name, "jd": hjd, "mag": mag}]
    logger.info(f"ZTF preview: oid={row.ztf_object_id} filter={filtercode} → {hjd.size} punti")
    return PreviewLoadResult(sessions=sessions, label=label, source="ztf", result_id=result_id)


# ---------------------------------------------------------------------------
# VAST: legge .dat file preservato dal job, con fallback su agata_star_photometry
# ---------------------------------------------------------------------------

def _load_vast(db: Session, result_id: int) -> PreviewLoadResult:
    row: Optional[VastResult] = db.get(VastResult, result_id)
    if row is None:
        raise LookupError(f"VastResult id={result_id} non trovato")

    label = f"VAST | {row.job.job_code} ({row.vast_id or 'no-id'})"

    # Prima scelta: leggi direttamente il file .dat preservato dal job
    dat_dir = (row.job.output_files or {}).get("dat_dir")
    if dat_dir and row.vast_id:
        dat_name = row.vast_id.strip()
        if not dat_name.endswith(".dat"):
            dat_name += ".dat"
        dat_path = os.path.join(dat_dir, dat_name)
        sessions = _read_dat_file_as_sessions(dat_path, row.vmag)
        if sessions:
            logger.info(f"VAST preview: .dat {dat_path} → {len(sessions[0]['jd'])} punti")
            return PreviewLoadResult(sessions=sessions, label=label, source="vast", result_id=result_id)
        logger.warning(f"VAST preview: .dat non leggibile ({dat_path}), provo agata_star_photometry")

    # Fallback: agata_star_photometry (stelle già promosse)
    if row.gaia_source_id is not None:
        gaia_id = str(row.gaia_source_id)
        sessions = load_lightcurve_from_db(gaia_id)
        if sessions:
            logger.info(f"VAST preview (fallback DB): gaia_id={gaia_id} → {len(sessions)} sessioni")
            return PreviewLoadResult(sessions=sessions, label=label, source="vast", result_id=result_id)

    return PreviewLoadResult(
        sessions=[], label=label, source="vast", result_id=result_id,
        error="Curva di luce non disponibile: file .dat del job non trovato e stella non ancora promossa in catalogo."
    )


def _read_dat_file_as_sessions(dat_path: str, vmag: Optional[float]) -> list:
    """
    Legge un file .dat VAST (JD + magnitudine strumentale) e restituisce
    la lista sessioni nel formato standard dell'editor.

    Il file .dat ha magnitudini strumentali. Se vmag è disponibile,
    si usa come riferimento per la calibrazione (come nel promote_job_results).
    In mancanza di vmag, si usano le magnitudini strumentali così come sono.

    Formato .dat: spazio-separato, col0=JD, col1=mag_strumentale
    """
    if not os.path.exists(dat_path):
        return []

    try:
        df = pd.read_csv(
            dat_path,
            sep=r"\s+",
            header=None,
            usecols=[0, 1],
            names=["hjd", "mag"],
            dtype={"hjd": float, "mag": float},
            engine="python",
        )
    except Exception as e:
        logger.warning(f"Errore lettura .dat {dat_path}: {e}")
        return []

    df = df.dropna(subset=["hjd", "mag"])
    df = df[df["hjd"] > 0]

    if df.empty:
        return []

    hjd = df["hjd"].to_numpy(dtype=np.float64)
    mag = df["mag"].to_numpy(dtype=np.float64)

    return [{"session_id": 0, "session_name": "VAST", "jd": hjd, "mag": mag}]
