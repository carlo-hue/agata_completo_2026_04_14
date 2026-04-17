from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

from .density import make_density_maps
from .gaia_client import GaiaConeQueryParams, query_gaia_cone_sources
from .scoring import compute_tile_score


@dataclass
class SingleRunParams:
    ra: float
    dec: float
    radius: float
    gmax: float = 21.0
    ruwe_max: float | None = 1.6
    no_extragal: bool = False
    use_real_gaia: bool = False
    cell_arcmin: float = 1.0
    max_rows: int | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "SingleRunParams":
        data = payload or {}
        return cls(
            ra=float(data.get("ra", 210.0)),
            dec=float(data.get("dec", 30.0)),
            radius=float(data.get("radius", 0.2)),
            gmax=float(data.get("gmax", 21.0)),
            ruwe_max=_maybe_float(data.get("ruwe_max", 1.6)),
            no_extragal=bool(data.get("no_extragal", False)),
            use_real_gaia=bool(data.get("use_real_gaia", False)),
            cell_arcmin=float(data.get("cell_arcmin", 1.0)),
            max_rows=_maybe_int(data.get("max_rows")),
        )


def run_single_field_analysis(params: SingleRunParams) -> dict[str, Any]:
    t0 = time.perf_counter()
    gaia_params = GaiaConeQueryParams(
        ra_deg=params.ra,
        dec_deg=params.dec,
        radius_deg=params.radius,
        gmax=params.gmax,
        ruwe_max=params.ruwe_max,
        enforce_extragal=(not params.no_extragal),
        max_rows=params.max_rows,
        provider_mode="real" if params.use_real_gaia else "mock",
    )
    tq0 = time.perf_counter()
    sources, meta = query_gaia_cone_sources(gaia_params)
    tq1 = time.perf_counter()

    td0 = time.perf_counter()
    density = make_density_maps(sources, cell_arcmin=params.cell_arcmin)
    td1 = time.perf_counter()
    r_core = min(0.2, 0.5 * params.radius)
    r_in = min(0.3, 0.6 * params.radius)
    r_out = min(0.5, 0.9 * params.radius)
    ts0 = time.perf_counter()
    score = compute_tile_score(
        sources,
        density.z_map,
        ra0=params.ra,
        dec0=params.dec,
        r_core=r_core,
        r_in=r_in,
        r_out=r_out,
        zthr=3.0,
    )
    ts1 = time.perf_counter()
    t1 = time.perf_counter()

    return {
        "mode": meta.provider_mode,
        "input": {
            "ra": params.ra,
            "dec": params.dec,
            "radius": params.radius,
            "gmax": params.gmax,
            "ruwe_max": params.ruwe_max,
            "no_extragal": params.no_extragal,
            "use_real_gaia": params.use_real_gaia,
            "cell_arcmin": params.cell_arcmin,
            "max_rows": params.max_rows,
        },
        "summary": {
            "n_sources": len(sources),
            "density_shape": list(density.shape),
            "mean_bg": density.mean_bg,
            "r_core": r_core,
            "r_ctrl_in": r_in,
            "r_ctrl_out": r_out,
        },
        "tile_score": score.to_dict(),
        "density": {
            "shape": list(density.shape),
            "mean_bg": density.mean_bg,
            "counts": density.counts,
            "z_map": density.z_map,
            "ra_edges": density.ra_edges,
            "dec_edges": density.dec_edges,
        },
        "gaia_meta": meta.to_dict(),
        "timing": {
            "query_ms": round((tq1 - tq0) * 1000.0, 1),
            "density_ms": round((td1 - td0) * 1000.0, 1),
            "score_ms": round((ts1 - ts0) * 1000.0, 1),
            "total_ms": round((t1 - t0) * 1000.0, 1),
        },
        # Manteniamo preview corta per UI/debug senza payload enorme.
        "sources_preview": sources[:10],
    }


def _maybe_float(value: Any) -> float | None:
    if value in (None, "", "null"):
        return None
    return float(value)


def _maybe_int(value: Any) -> int | None:
    if value in (None, "", "null"):
        return None
    return int(value)
