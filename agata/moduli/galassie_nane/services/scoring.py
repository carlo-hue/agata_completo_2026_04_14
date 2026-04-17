from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any


@dataclass
class TileScoreResult:
    s_spatial: float
    f_cluster: float
    s_counts: float
    score: float
    n_core: int
    n_ctrl: int
    alpha: float
    zthr: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_tile_score(
    sources: list[dict[str, Any]],
    z_map: list[list[float]],
    *,
    ra0: float,
    dec0: float,
    r_core: float,
    r_in: float,
    r_out: float,
    zthr: float = 3.0,
) -> TileScoreResult:
    s_spatial = _nanmax_2d(z_map)
    f_cluster = _largest_blob_fraction(z_map, zthr=zthr)
    n_core, n_ctrl, alpha, s_counts = _core_control_counts_stats(
        sources, ra0=ra0, dec0=dec0, r_core=r_core, r_in=r_in, r_out=r_out
    )
    score = 0.5 * math.tanh(s_spatial / 3.0) + 0.3 * f_cluster + 0.2 * math.tanh(s_counts / 3.0)
    return TileScoreResult(
        s_spatial=s_spatial,
        f_cluster=f_cluster,
        s_counts=s_counts,
        score=score,
        n_core=n_core,
        n_ctrl=n_ctrl,
        alpha=alpha,
        zthr=zthr,
    )


def _nanmax_2d(grid: list[list[float]]) -> float:
    vals = [v for row in grid for v in row if v is not None]
    return max(vals) if vals else 0.0


def _largest_blob_fraction(z_map: list[list[float]], zthr: float = 3.0) -> float:
    if not z_map:
        return 0.0
    h = len(z_map)
    w = len(z_map[0]) if h else 0
    mask = [[z_map[i][j] >= zthr for j in range(w)] for i in range(h)]
    total = h * w
    if total == 0:
        return 0.0

    visited = [[False for _ in range(w)] for _ in range(h)]
    max_size = 0
    for i in range(h):
        for j in range(w):
            if not mask[i][j] or visited[i][j]:
                continue
            size = 0
            stack = [(i, j)]
            visited[i][j] = True
            while stack:
                x, y = stack.pop()
                size += 1
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    xx, yy = x + dx, y + dy
                    if 0 <= xx < h and 0 <= yy < w and mask[xx][yy] and not visited[xx][yy]:
                        visited[xx][yy] = True
                        stack.append((xx, yy))
            max_size = max(max_size, size)
    return max_size / total


def _core_control_counts_stats(
    sources: list[dict[str, Any]],
    *,
    ra0: float,
    dec0: float,
    r_core: float,
    r_in: float,
    r_out: float,
) -> tuple[int, int, float, float]:
    if not sources:
        return 0, 0, 0.0, 0.0

    n_core = 0
    n_ctrl = 0
    for s in sources:
        sep = _angular_sep_deg(ra0, dec0, float(s["ra"]), float(s["dec"]))
        if sep <= r_core:
            n_core += 1
        if r_in <= sep <= r_out:
            n_ctrl += 1

    a_core = math.pi * (r_core**2)
    a_ctrl = math.pi * max(r_out**2 - r_in**2, 0.0)
    alpha = a_core / a_ctrl if a_ctrl > 0 else 0.0
    if n_ctrl > 0 and alpha > 0:
        mu = alpha * n_ctrl
        s_counts = (n_core - mu) / math.sqrt(mu + 1.0)
    else:
        s_counts = 0.0

    return n_core, n_ctrl, alpha, s_counts


def _angular_sep_deg(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    r1 = math.radians(ra1)
    d1 = math.radians(dec1)
    r2 = math.radians(ra2)
    d2 = math.radians(dec2)
    sd = math.sin((d2 - d1) / 2.0)
    sr = math.sin((r2 - r1) / 2.0)
    a = sd * sd + math.cos(d1) * math.cos(d2) * sr * sr
    a = min(1.0, max(0.0, a))
    return math.degrees(2.0 * math.asin(math.sqrt(a)))

