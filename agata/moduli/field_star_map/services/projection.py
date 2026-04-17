from __future__ import annotations

from collections.abc import Iterable

import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord


def project_tangent_offsets_arcsec(
    ra_deg: Iterable[float],
    dec_deg: Iterable[float],
    ra0_deg: float,
    dec0_deg: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Project coordinates to tangent-plane offsets in arcsec (x=East, y=North)."""
    center = SkyCoord(ra=ra0_deg * u.deg, dec=dec0_deg * u.deg, frame="icrs")
    coords = SkyCoord(ra=np.asarray(list(ra_deg)) * u.deg, dec=np.asarray(list(dec_deg)) * u.deg, frame="icrs")

    offset_frame = center.skyoffset_frame()
    offsets = coords.transform_to(offset_frame)
    x_arcsec = offsets.lon.to(u.arcsec).value
    y_arcsec = offsets.lat.to(u.arcsec).value
    return x_arcsec, y_arcsec
