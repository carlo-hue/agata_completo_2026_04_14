from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any


@dataclass
class DensityMapsResult:
    counts: list[list[int]]
    z_map: list[list[float]]
    ra_edges: list[float]
    dec_edges: list[float]
    mean_bg: float
    shape: tuple[int, int]

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["shape"] = list(self.shape)
        return out


def make_density_maps(
    sources: list[dict[str, Any]],
    *,
    cell_arcmin: float = 1.0,
    pad_frac: float = 0.02,
) -> DensityMapsResult:
    if not sources:
        return DensityMapsResult([], [], [], [], 0.0, (0, 0))

    ras = [float(s["ra"]) for s in sources]
    decs = [float(s["dec"]) for s in sources]
    ra_min, ra_max = min(ras), max(ras)
    dec_min, dec_max = min(decs), max(decs)

    dra = ra_max - ra_min
    ddec = dec_max - dec_min
    ra_pad = dra * pad_frac if dra > 0 else 0.01
    dec_pad = ddec * pad_frac if ddec > 0 else 0.01
    ra_min -= ra_pad
    ra_max += ra_pad
    dec_min -= dec_pad
    dec_max += dec_pad

    cell_deg = max(cell_arcmin / 60.0, 1e-6)
    nbins_ra = max(2, math.ceil((ra_max - ra_min) / cell_deg))
    nbins_dec = max(2, math.ceil((dec_max - dec_min) / cell_deg))

    counts = [[0 for _ in range(nbins_ra)] for _ in range(nbins_dec)]

    for ra, dec in zip(ras, decs):
        i = min(nbins_ra - 1, max(0, int((ra - ra_min) / (ra_max - ra_min) * nbins_ra)))
        j = min(nbins_dec - 1, max(0, int((dec - dec_min) / (dec_max - dec_min) * nbins_dec)))
        counts[j][i] += 1

    flat = [v for row in counts for v in row]
    mean_bg = sum(flat) / len(flat) if flat else 0.0
    denom = math.sqrt(mean_bg) if mean_bg > 0 else 1.0
    z_map = [[(v - mean_bg) / denom for v in row] for row in counts]

    ra_edges = [ra_min + (ra_max - ra_min) * k / nbins_ra for k in range(nbins_ra + 1)]
    dec_edges = [dec_min + (dec_max - dec_min) * k / nbins_dec for k in range(nbins_dec + 1)]

    return DensityMapsResult(
        counts=counts,
        z_map=z_map,
        ra_edges=ra_edges,
        dec_edges=dec_edges,
        mean_bg=mean_bg,
        shape=(nbins_dec, nbins_ra),
    )

