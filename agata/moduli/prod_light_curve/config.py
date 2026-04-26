from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile

MODULE_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = Path(tempfile.gettempdir()) / "agata_prod_light_curve_runtime"


@dataclass(frozen=True)
class ProdLightCurveSettings:
    module_title: str = "AGATA - Ground-Based Photometry"
    placeholder_message: str = "Modulo pronto per l'analisi di sequenze FITS ground-based."
    default_dataset_root: str = r"C:\Users\CarloMarino\Documents\carlo\programmi\esopianeti"
    max_detected_sources: int = 150
    max_preview_sources: int = 80
    preview_percentile_low: float = 5.0
    preview_percentile_high: float = 99.5
    default_aperture_radius: float = 6.0
    default_annulus_inner_radius: float = 10.0
    default_annulus_outer_radius: float = 16.0
    reference_selection_mode: str = "auto-best-frame"
    session_storage_dir: str = str(RUNTIME_DIR / "sessions")
    job_storage_dir: str = str(RUNTIME_DIR / "jobs")


settings = ProdLightCurveSettings()
