from __future__ import annotations

import base64
import hashlib
import json
import math
import struct
import zlib
from datetime import UTC, datetime
from pathlib import Path

import numpy as np


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def ensure_directory(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def stable_dataset_id(dataset_path: str) -> str:
    normalized = str(Path(dataset_path).resolve()).lower()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def rounded_or_none(value, digits: int = 4):
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return round(numeric, digits)


def encode_json(value) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2)


def decode_json(text_value: str):
    return json.loads(text_value)


def normalize_preview_image(data: np.ndarray, low_percentile: float, high_percentile: float) -> np.ndarray:
    finite = np.asarray(data, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return np.zeros((8, 8), dtype=np.uint8)
    vmin, vmax = np.percentile(finite, [low_percentile, high_percentile])
    if not np.isfinite(vmin):
        vmin = float(np.nanmin(finite))
    if not np.isfinite(vmax):
        vmax = float(np.nanmax(finite))
    if vmax <= vmin:
        vmax = vmin + 1.0
    clipped = np.clip(np.asarray(data, dtype=float), vmin, vmax)
    normalized = (clipped - vmin) / max(vmax - vmin, 1e-9)
    # A gentle asinh stretch keeps faint stars visible while avoiding
    # the harsh, noisy look of a purely linear 8-bit preview.
    stretch_factor = 8.0
    normalized = np.arcsinh(normalized * stretch_factor) / np.arcsinh(stretch_factor)
    return np.asarray(np.nan_to_num(np.flipud(normalized) * 255.0, nan=0.0), dtype=np.uint8)


def encode_grayscale_png(image_array: np.ndarray) -> bytes:
    height, width = image_array.shape
    raw_rows = b"".join(b"\x00" + image_array[row].tobytes() for row in range(height))
    compressed = zlib.compress(raw_rows, level=9)

    def chunk(chunk_type: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(chunk_type + payload) & 0xFFFFFFFF
        return struct.pack("!I", len(payload)) + chunk_type + payload + struct.pack("!I", crc)

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack("!IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return signature + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")


_PREVIEW_MAX_PX = 1024


def _downsample_preview(arr: np.ndarray) -> np.ndarray:
    h, w = arr.shape
    if max(h, w) <= _PREVIEW_MAX_PX:
        return arr
    scale = _PREVIEW_MAX_PX / max(h, w)
    new_h = max(1, int(h * scale))
    new_w = max(1, int(w * scale))
    from scipy.ndimage import zoom
    return np.asarray(zoom(arr.astype(np.float32), (new_h / h, new_w / w), order=1, prefilter=False), dtype=np.uint8)


def render_preview_base64(data: np.ndarray, low_percentile: float, high_percentile: float) -> str:
    preview_array = normalize_preview_image(data, low_percentile, high_percentile)
    preview_array = _downsample_preview(preview_array)
    return base64.b64encode(encode_grayscale_png(preview_array)).decode("ascii")
