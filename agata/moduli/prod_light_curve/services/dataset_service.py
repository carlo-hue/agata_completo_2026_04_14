from __future__ import annotations

import glob
import math
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.time import Time
from astropy.wcs import WCS
import astropy.units as u

from ..config import settings
from .utils import rounded_or_none, stable_dataset_id

FITS_PATTERNS = (
    "*.fits",
    "*.fit",
    "*.fts",
    "*.fits.gz",
    "*.fit.gz",
    "*.fts.gz",
    "*.fits.fz",
    "*.fit.fz",
    "*.fts.fz",
)


def validate_dataset_path(dataset_path: str) -> Path:
    if not dataset_path:
        raise ValueError("dataset_path mancante")
    path = Path(dataset_path).expanduser()
    if not path.exists():
        raise ValueError("La cartella dataset_path non esiste")
    if not path.is_dir():
        raise ValueError("dataset_path deve indicare una cartella")
    return path.resolve()


def find_fits_files(dataset_path: str) -> list[Path]:
    path = validate_dataset_path(dataset_path)
    matches: set[Path] = set()
    for pattern in FITS_PATTERNS:
        for file_path in glob.glob(str(path / pattern)):
            matches.add(Path(file_path))
        for file_path in glob.glob(str(path / "**" / pattern), recursive=True):
            matches.add(Path(file_path))
    files = sorted(item.resolve() for item in matches if item.is_file())
    if not files:
        raise ValueError("Nessun FITS trovato nella cartella dataset_path")
    return files


def _extract_mid_time_jd(header) -> float | None:
    date_obs = header.get("DATE-OBS")
    exptime = header.get("EXPTIME", header.get("EXPOSURE"))
    if not date_obs:
        return None
    try:
        start = Time(date_obs, format="isot", scale="utc")
    except Exception:
        try:
            start = Time(date_obs)
        except Exception:
            return None
    if exptime in (None, ""):
        return rounded_or_none(start.jd, 8)
    try:
        return rounded_or_none((start + (float(exptime) / 2.0) * u.s).jd, 8)
    except Exception:
        return rounded_or_none(start.jd, 8)


def load_fits_frame(file_path: str | Path) -> dict:
    with fits.open(file_path) as hdul:
        hdu = hdul[0]
        data = np.asarray(hdu.data, dtype=float)
        if data.ndim > 2:
            data = np.squeeze(data)
        if data.ndim != 2:
            raise ValueError(f"FITS non 2D non supportato: {file_path}")
        header = hdu.header.copy()
        try:
            wcs = WCS(header) if header else None
        except Exception:
            wcs = None

    finite = data[np.isfinite(data)]
    if finite.size == 0:
        raise ValueError(f"FITS senza pixel finiti: {file_path}")

    median = float(np.nanmedian(finite))
    scatter = float(np.nanstd(finite))
    p95 = float(np.nanpercentile(finite, 95))
    p99 = float(np.nanpercentile(finite, 99))
    saturated_threshold = float(header.get("SATURATE", np.nanmax(finite)))
    saturated_fraction = float(np.mean(finite >= saturated_threshold)) if math.isfinite(saturated_threshold) else 0.0
    quality_score = (p95 - median) / max(scatter, 1e-6) - (20.0 * saturated_fraction)
    return {
        "path": str(Path(file_path).resolve()),
        "filename": Path(file_path).name,
        "data": data,
        "header": header,
        "wcs": wcs,
        "shape": [int(data.shape[0]), int(data.shape[1])],
        "time_jd": _extract_mid_time_jd(header),
        "metrics": {
            "median": rounded_or_none(median, 4),
            "scatter": rounded_or_none(scatter, 4),
            "p95": rounded_or_none(p95, 4),
            "p99": rounded_or_none(p99, 4),
            "saturated_fraction": rounded_or_none(saturated_fraction, 6),
            "quality_score": rounded_or_none(quality_score, 4),
        },
    }


def build_dataset_summary(dataset_path: str) -> dict:
    files = find_fits_files(dataset_path)
    frames = [load_fits_frame(file_path) for file_path in files]
    first_shape = frames[0]["shape"]
    same_shape = all(frame["shape"] == first_shape for frame in frames)
    reference_index = select_reference_frame_index(frames)
    return {
        "dataset_id": stable_dataset_id(dataset_path),
        "dataset_path": str(validate_dataset_path(dataset_path)),
        "fits_count": len(frames),
        "same_shape": same_shape,
        "shape": first_shape,
        "reference_frame_index": reference_index,
        "frames": frames,
    }


def select_reference_frame_index(frames: list[dict]) -> int:
    if not frames:
        raise ValueError("Sequenza FITS vuota")
    ranked = sorted(
        enumerate(frames),
        key=lambda item: float((item[1].get("metrics") or {}).get("quality_score") or float("-inf")),
        reverse=True,
    )
    return int(ranked[0][0])


def frame_summary_for_client(frame: dict, index: int, *, suspect: bool = False, reasons: list[str] | None = None) -> dict:
    metrics = frame.get("metrics") or {}
    return {
        "index": int(index),
        "filename": frame.get("filename"),
        "time_jd": frame.get("time_jd"),
        "quality_score": metrics.get("quality_score"),
        "median": metrics.get("median"),
        "scatter": metrics.get("scatter"),
        "saturated_fraction": metrics.get("saturated_fraction"),
        "suspect": bool(suspect),
        "suspect_reasons": list(reasons or []),
    }
