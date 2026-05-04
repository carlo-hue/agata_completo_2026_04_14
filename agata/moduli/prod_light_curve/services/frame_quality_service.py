from __future__ import annotations

import math

import numpy as np

from .dataset_service import frame_summary_for_client
from .utils import rounded_or_none


def build_frame_quality_summary(dataset_summary: dict) -> dict:
    frames = dataset_summary["frames"]
    scores = np.asarray(
        [float((frame.get("metrics") or {}).get("quality_score") or 0.0) for frame in frames],
        dtype=float,
    )
    med_score = float(np.nanmedian(scores))
    score_scatter = float(np.nanstd(scores))
    frame_items = []
    for index, frame in enumerate(frames):
        reasons = []
        score = float((frame.get("metrics") or {}).get("quality_score") or 0.0)
        saturated_fraction = float((frame.get("metrics") or {}).get("saturated_fraction") or 0.0)
        suspect = False
        if score < med_score - max(2.0, 2.0 * score_scatter):
            suspect = True
            reasons.append("contrasto inferiore al dataset")
        if saturated_fraction > 0.01:
            suspect = True
            reasons.append("frazione saturata elevata")
        frame_items.append(frame_summary_for_client(frame, index, suspect=suspect, reasons=reasons))

    return {
        "available": True,
        "message": "Metriche qualità frame calcolate lato backend.",
        "reference_frame_index": int(dataset_summary["reference_frame_index"]),
        "frames": frame_items,
        "summary": {
            "suspect_count": int(sum(1 for item in frame_items if item["suspect"])),
            "median_quality_score": rounded_or_none(med_score, 4),
            "quality_score_scatter": rounded_or_none(score_scatter, 4),
        },
    }


def enrich_frame_quality_with_photometry(
    frame_quality: dict,
    target_flux: list[float],
    comparison_flux: list[float],
    centroid_shift: list[float],
    fwhm_px: list[float | None] | None = None,
    frame_indices: list[int] | None = None,
) -> dict:
    flux_ratio = np.asarray(target_flux, dtype=float) / np.maximum(np.asarray(comparison_flux, dtype=float), 1e-9)
    ratio_median = float(np.nanmedian(flux_ratio)) if flux_ratio.size else 1.0
    ratio_scatter = float(np.nanstd(flux_ratio)) if flux_ratio.size else 0.0
    shift_arr = np.asarray(centroid_shift, dtype=float)
    shift_median = float(np.nanmedian(shift_arr)) if shift_arr.size else 0.0
    shift_scatter = float(np.nanstd(shift_arr)) if shift_arr.size else 0.0

    fwhm_array = None
    fwhm_median = None
    fwhm_scatter = None
    if fwhm_px:
        finite_fwhm = [v for v in fwhm_px if v is not None and math.isfinite(float(v))]
        if len(finite_fwhm) >= 3:
            fwhm_array = [float(v) if v is not None and math.isfinite(float(v)) else None for v in fwhm_px]
            fwhm_median = float(np.median(finite_fwhm))
            fwhm_scatter = float(np.std(finite_fwhm))

    # Mappa frame_index → posizione negli array di fotometria.
    # Se frame_indices non è fornito si assume corrispondenza posizionale.
    if frame_indices is not None:
        index_to_pos = {int(idx): pos for pos, idx in enumerate(frame_indices)}
    else:
        index_to_pos = {pos: pos for pos in range(len(flux_ratio))}

    frames = []
    for item in frame_quality["frames"]:
        suspect = bool(item.get("suspect"))
        reasons = list(item.get("suspect_reasons") or [])
        pos = index_to_pos.get(item.get("index"))
        if pos is not None:
            ratio = float(flux_ratio[pos]) if pos < len(flux_ratio) else float("nan")
            shift = float(centroid_shift[pos]) if pos < len(centroid_shift) else float("nan")
            if math.isfinite(ratio) and abs(ratio - ratio_median) > max(4.0 * ratio_scatter, 0.2):
                suspect = True
                reasons.append("rapporto target/comparison anomalo")
            if math.isfinite(shift) and shift > shift_median + max(2.0, 3.0 * shift_scatter):
                suspect = True
                reasons.append("centroide instabile")
            if fwhm_array is not None and pos < len(fwhm_array):
                fwhm_val = fwhm_array[pos]
                if fwhm_val is not None and fwhm_val > fwhm_median + max(2.0, 2.0 * fwhm_scatter):
                    suspect = True
                    reasons.append(f"FWHM anomala ({fwhm_val:.1f} px)")
        frames.append({
            **item,
            "suspect": suspect,
            "suspect_reasons": reasons,
            "fwhm_px": (fwhm_array[pos] if fwhm_array and pos is not None and pos < len(fwhm_array) else None),
            "centroid_shift_px": (float(centroid_shift[pos]) if pos is not None and pos < len(centroid_shift) else None),
        })

    return {
        **frame_quality,
        "message": "Metriche qualità frame aggiornate con la fotometria.",
        "frames": frames,
        "summary": {
            **(frame_quality.get("summary") or {}),
            "suspect_count": int(sum(1 for item in frames if item["suspect"])),
        },
    }

