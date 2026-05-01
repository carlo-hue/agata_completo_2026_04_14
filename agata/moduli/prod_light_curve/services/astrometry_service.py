from __future__ import annotations

import shutil
from pathlib import Path

from astropy.io import fits
import numpy as np

from ..config import settings
from .catalog_service import validate_reference_wcs
from .dataset_service import load_reference_frame
from .reference_service import build_reference_payload_from_frame


def solve_reference_astrometry(reference_path: str) -> dict:
    try:
        from astroquery.astrometry_net import AstrometryNet
    except Exception as err:
        raise ValueError(f"Astrometry.net online non disponibile nell'ambiente Python: {err}") from err

    if not settings.astrometry_net_api_key:
        raise ValueError("Chiave API Astrometry.net non configurata sul server")

    reference_frame = load_reference_frame(reference_path, include_wcs=True)
    source_path = Path(reference_frame["path"])
    output_dir = Path(settings.plate_solve_storage_dir) / source_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    working_input = output_dir / source_path.name
    shutil.copy2(source_path, working_input)

    header = reference_frame["header"]
    ra_center = _header_float(header, "CRVAL1", "RA") or 0.0
    dec_center = _header_float(header, "CRVAL2", "DEC") or 0.0
    scale = _estimate_scale_arcsec_per_px(header)
    solver = AstrometryNet()
    solver.api_key = settings.astrometry_net_api_key

    try:
        wcs_header = solver.solve_from_image(
            str(working_input),
            force_image_upload=True,
            solve_timeout=240,
            verbose=False,
            center_ra=ra_center,
            center_dec=dec_center,
            radius=5.0,
            scale_units="arcsecperpix",
            scale_type="ul",
            scale_lower=max(scale * 0.8, 0.1),
            scale_upper=max(scale * 1.2, 0.2),
            publicly_visible="n",
            allow_commercial_use="d",
            allow_modifications="d",
            tweak_order=2,
        )
    except Exception as err:
        raise ValueError(f"Plate solving online fallito: {err}") from err

    if not wcs_header:
        raise ValueError("Plate solving online fallito: WCS non restituito dal servizio")

    with fits.open(working_input, mode="update") as hdul:
        hdul[0].header.update(wcs_header)
        hdul.flush()

    solved_frame = load_reference_frame(working_input, include_wcs=True)
    wcs_check = validate_reference_wcs(solved_frame)
    if not wcs_check["valid"]:
        raise ValueError(
            "Plate solving completato ma WCS ancora insufficiente: "
            + ", ".join(wcs_check["missing"])
        )

    reference_payload = build_reference_payload_from_frame(
        solved_frame,
        frame_index=0,
        mode="astrometry.net",
        message="Reference image aggiornata con WCS risolto tramite Astrometry.net.",
        solved=True,
    )
    return {
        "status": "ok",
        "message": "Plate solving completato con successo.",
        "reference": reference_payload,
        "astrometry": {
            "solved": True,
            "source_path": reference_frame["path"],
            "solved_path": solved_frame["path"],
            "command": "astroquery.astrometry_net",
        },
    }


def _header_float(header, *keys: str) -> float | None:
    for key in keys:
        try:
            value = header.get(key)
            if value is None:
                continue
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _estimate_scale_arcsec_per_px(header) -> float:
    cd11 = _header_float(header, "CD1_1") or 0.0
    cd12 = _header_float(header, "CD1_2") or 0.0
    if cd11 or cd12:
        scale = np.sqrt(cd11 ** 2 + cd12 ** 2) * 3600.0
        if scale > 0:
            return float(scale)

    focal_len = _header_float(header, "FOCALLEN")
    xpixsz = _header_float(header, "XPIXSZ")
    binning = _header_float(header, "XBINNING") or 1.0
    if focal_len and xpixsz:
        pixel_um = xpixsz * binning
        return float(206.265 * pixel_um / focal_len)

    return 2.0
