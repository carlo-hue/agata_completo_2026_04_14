from __future__ import annotations

import math

import numpy as np
from scipy.ndimage import maximum_filter

from ..config import settings
from .utils import rounded_or_none


def detect_reference_sources(reference_frame: dict) -> list[dict]:
    data = np.asarray(reference_frame["data"], dtype=float)
    finite = data[np.isfinite(data)]
    median = float(np.nanmedian(finite))
    scatter = float(np.nanstd(finite))
    threshold = median + max(4.0 * scatter, 1.0)
    filtered = maximum_filter(np.nan_to_num(data, nan=median), size=5, mode="nearest")
    local_maxima = (data == filtered) & np.isfinite(data) & (data > threshold)
    source_indices = np.argwhere(local_maxima)
    if source_indices.size == 0:
        return []

    rows, cols = data.shape
    saturated_level = float(reference_frame["header"].get("SATURATE", np.nanmax(finite)))
    sources = []
    for row_index, col_index in source_indices:
        x = float(col_index)
        y = float(row_index)
        peak = float(data[row_index, col_index])
        flux_proxy = peak - median
        edge_distance = float(min(col_index, row_index, cols - 1 - col_index, rows - 1 - row_index))
        stamp = _extract_stamp(data, x, y, radius=5)
        snr = float(flux_proxy / max(np.nanstd(stamp), 1e-6))
        fwhm_proxy = _estimate_fwhm_proxy(stamp)
        source = {
            "source_id": f"ref-{int(row_index)}-{int(col_index)}",
            "x": rounded_or_none(x, 3),
            "y": rounded_or_none(y, 3),
            "peak": rounded_or_none(peak, 3),
            "flux_proxy": rounded_or_none(flux_proxy, 3),
            "snr": rounded_or_none(snr, 3),
            "edge_distance_px": rounded_or_none(edge_distance, 3),
            "saturated": bool(peak >= saturated_level) if math.isfinite(saturated_level) else False,
            "fwhm_proxy": rounded_or_none(fwhm_proxy, 3),
        }
        sources.append(source)

    _attach_nearest_neighbor_metrics(sources)
    sources.sort(key=lambda item: item.get("flux_proxy") or 0.0, reverse=True)
    return sources[: settings.max_detected_sources]


def choose_auto_target(reference_payload: dict, detected_sources: list[dict], target_candidates: list[dict]) -> dict | None:
    if target_candidates:
        selected = sorted(
            target_candidates,
            key=lambda item: (
                item.get("distance_from_center_px") if item.get("distance_from_center_px") is not None else float("inf"),
                item.get("priority_rank") if item.get("priority_rank") is not None else 9999,
            ),
        )[0]
        return {
            "mode": "catalog-candidate",
            "x": selected.get("x"),
            "y": selected.get("y"),
            "label": selected.get("label"),
            "catalog_type": selected.get("catalog_type"),
        }

    if not detected_sources:
        return None

    center = reference_payload.get("center_pixel") or {"x": 0.0, "y": 0.0}
    ranked = sorted(
        detected_sources,
        key=lambda item: (
            abs(float(item.get("x") or 0.0) - float(center["x"])) + abs(float(item.get("y") or 0.0) - float(center["y"])),
            -(float(item.get("snr") or 0.0)),
        ),
    )
    chosen = ranked[0]
    return {
        "mode": "auto-detected",
        "x": chosen.get("x"),
        "y": chosen.get("y"),
        "label": "Auto target",
        "catalog_type": None,
    }


def build_comparison_candidates(detected_sources: list[dict], target_position: dict | None, max_items: int | None = None) -> list[dict]:
    max_items = max_items or settings.max_preview_sources
    candidates = []
    for source in detected_sources:
        score, reasons = _comparison_score(source, target_position)
        entry = {
            **source,
            "score": rounded_or_none(score, 3),
            "auto_selected": False,
            "selection_reasons": reasons,
        }
        candidates.append(entry)

    candidates.sort(key=lambda item: float(item.get("score") or float("-inf")), reverse=True)
    for entry in candidates[: min(5, len(candidates))]:
        entry["auto_selected"] = True
    return candidates[:max_items]


def _comparison_score(source: dict, target_position: dict | None) -> tuple[float, list[str]]:
    score = 0.0
    reasons = []
    snr = float(source.get("snr") or 0.0)
    edge_distance = float(source.get("edge_distance_px") or 0.0)
    nearest_neighbor = float(source.get("nearest_neighbor_distance_px") or 9999.0)
    saturated = bool(source.get("saturated"))

    if saturated:
        reasons.append("esclusa: saturata")
        return -1000.0, reasons
    if snr < 4.0:
        reasons.append("penalita: troppo debole")
        score -= 50.0
    else:
        reasons.append("ok: snr utile")
        score += min(25.0, snr)
    if edge_distance < 12.0:
        reasons.append("penalita: vicina al bordo")
        score -= 20.0
    else:
        reasons.append("ok: lontana dai bordi")
        score += 10.0
    if nearest_neighbor < 8.0:
        reasons.append("penalita: possibile contaminazione")
        score -= 20.0
    else:
        reasons.append("ok: isolata")
        score += 8.0
    if target_position is not None:
        distance_to_target = math.hypot(
            float(source.get("x") or 0.0) - float(target_position.get("x") or 0.0),
            float(source.get("y") or 0.0) - float(target_position.get("y") or 0.0),
        )
        if distance_to_target < 10.0:
            reasons.append("penalita: troppo vicina al target")
            score -= 25.0
        else:
            score += min(15.0, distance_to_target / 15.0)
    return score, reasons


def _extract_stamp(data: np.ndarray, x: float, y: float, radius: int) -> np.ndarray:
    x0 = int(round(x))
    y0 = int(round(y))
    y1 = max(0, y0 - radius)
    y2 = min(data.shape[0], y0 + radius + 1)
    x1 = max(0, x0 - radius)
    x2 = min(data.shape[1], x0 + radius + 1)
    return np.asarray(data[y1:y2, x1:x2], dtype=float)


def _estimate_fwhm_proxy(stamp: np.ndarray) -> float:
    if stamp.size < 9:
        return float("nan")
    stamp = np.asarray(stamp, dtype=float)
    stamp = stamp - np.nanmedian(stamp)
    stamp[stamp < 0] = 0
    total = np.nansum(stamp)
    if total <= 0:
        return float("nan")
    yy, xx = np.indices(stamp.shape)
    xbar = np.nansum(xx * stamp) / total
    ybar = np.nansum(yy * stamp) / total
    varx = np.nansum((xx - xbar) ** 2 * stamp) / total
    vary = np.nansum((yy - ybar) ** 2 * stamp) / total
    return float(2.355 * math.sqrt(max(0.0, 0.5 * (varx + vary))))


def _attach_nearest_neighbor_metrics(sources: list[dict]) -> None:
    for source in sources:
        nearest_distance = None
        for other in sources:
            if source is other:
                continue
            distance = math.hypot(
                float(source["x"]) - float(other["x"]),
                float(source["y"]) - float(other["y"]),
            )
            if nearest_distance is None or distance < nearest_distance:
                nearest_distance = distance
        source["nearest_neighbor_distance_px"] = rounded_or_none(nearest_distance, 3)

