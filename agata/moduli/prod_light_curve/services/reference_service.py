from __future__ import annotations

from astropy.coordinates import SkyCoord
import astropy.units as u
from astropy.wcs.utils import proj_plane_pixel_scales
import numpy as np

from ..config import settings
from .utils import render_preview_base64, rounded_or_none


def build_reference_payload(dataset_summary: dict) -> dict:
    reference_index = int(dataset_summary["reference_frame_index"])
    reference_frame = dataset_summary["frames"][reference_index]
    data = reference_frame["data"]
    header = reference_frame["header"]
    wcs = reference_frame.get("wcs")
    height, width = data.shape
    center_pixel = {"x": round((width - 1) / 2.0, 3), "y": round((height - 1) / 2.0, 3)}

    center_sky = None
    center_circles_arcmin = []
    if wcs is not None:
        try:
            sky = wcs.pixel_to_world(center_pixel["x"], center_pixel["y"])
            center_sky = {
                "ra_deg": rounded_or_none(sky.ra.deg, 6),
                "dec_deg": rounded_or_none(sky.dec.deg, 6),
                "ra_hms": sky.ra.to_string(unit=u.hourangle, sep=":", precision=2, pad=True),
                "dec_dms": sky.dec.to_string(unit=u.deg, sep=":", precision=2, alwayssign=True, pad=True),
            }
        except Exception:
            center_sky = None
        try:
            pixel_scales = proj_plane_pixel_scales(wcs.celestial) * u.deg
            arcsec_per_pixel = float(np.mean(pixel_scales.to(u.arcsec).value))
            if arcsec_per_pixel > 0:
                for radius_arcmin in (10.0, 20.0):
                    radius_px = (radius_arcmin * 60.0) / arcsec_per_pixel
                    center_circles_arcmin.append({
                        "label": f"{int(radius_arcmin)}'",
                        "center_x": center_pixel["x"],
                        "center_y": center_pixel["y"],
                        "radius_px": rounded_or_none(radius_px, 3),
                        "diameter_px": rounded_or_none(radius_px * 2.0, 3),
                        "radius_arcmin": radius_arcmin,
                        "arcsec_per_pixel": rounded_or_none(arcsec_per_pixel, 4),
                    })
        except Exception:
            center_circles_arcmin = []

    return {
        "available": True,
        "mode": settings.reference_selection_mode,
        "message": "Reference image costruita dal backend su un frame della sequenza.",
        "frame_index": reference_index,
        "source": {
            "path": reference_frame["path"],
            "filename": reference_frame["filename"],
        },
        "shape": [int(height), int(width)],
        "center_pixel": center_pixel,
        "center_sky": center_sky,
        "center_circles_arcmin": center_circles_arcmin,
        "header": {
            "object": header.get("OBJECT"),
            "filter": header.get("FILTER"),
            "date_obs": header.get("DATE-OBS"),
            "exptime": header.get("EXPTIME", header.get("EXPOSURE")),
            "observer": header.get("OBSERVER"),
            "instrume": header.get("INSTRUME"),
            "telescop": header.get("TELESCOP"),
        },
        "preview_png_base64": render_preview_base64(
            data,
            settings.preview_percentile_low,
            settings.preview_percentile_high,
        ),
    }
