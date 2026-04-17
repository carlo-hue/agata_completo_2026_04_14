from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any
from uuid import uuid4


def save_named_run(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    clean_name = _sanitize_name(name)
    if not clean_name:
        raise ValueError("Nome salvataggio non valido")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
    target_dir = _storage_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / f"{run_id}_{clean_name}.json"

    doc = {
        "id": run_id,
        "name": name.strip(),
        "saved_at_utc": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    file_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "id": run_id,
        "name": doc["name"],
        "saved_at_utc": doc["saved_at_utc"],
        "file_name": file_path.name,
        "file_path": str(file_path),
    }


def list_saved_runs(limit: int = 100) -> list[dict[str, Any]]:
    target_dir = _storage_dir()
    if not target_dir.exists():
        return []

    items: list[dict[str, Any]] = []
    for path in sorted(target_dir.glob("*.json"), reverse=True):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        items.append(
            {
                "id": doc.get("id") or _id_from_filename(path.name),
                "name": doc.get("name") or path.stem,
                "saved_at_utc": doc.get("saved_at_utc"),
                "n_sources": _extract_n_sources(doc),
                "total_ms": _extract_total_ms(doc),
                "file_name": path.name,
            }
        )
        if len(items) >= max(1, int(limit)):
            break
    return items


def load_saved_run(run_id: str) -> dict[str, Any]:
    rid = (run_id or "").strip()
    if not rid:
        raise ValueError("run_id mancante")

    target_dir = _storage_dir()
    if not target_dir.exists():
        raise FileNotFoundError("Nessuna run salvata")

    matches = sorted(target_dir.glob(f"{rid}_*.json"))
    if not matches:
        raise FileNotFoundError(f"Run non trovata: {rid}")
    path = matches[0]
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Impossibile leggere la run salvata: {exc}") from exc
    return doc


def _storage_dir() -> Path:
    configured = os.getenv("GALASSIE_NANE_RUNS_DIR")
    if configured:
        return Path(configured)
    # default locale dentro il package attivo (facile da trovare durante le prove)
    return Path(__file__).resolve().parents[2] / "_runtime_data" / "galassie_nane_runs"


def _sanitize_name(value: str) -> str:
    text = (value or "").strip()
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^A-Za-z0-9._-]", "", text)
    return text[:80]


def _id_from_filename(file_name: str) -> str:
    stem = Path(file_name).stem
    return stem.split("_", 1)[0]


def _extract_n_sources(doc: dict[str, Any]) -> int | None:
    try:
        return int(doc.get("payload", {}).get("result", {}).get("summary", {}).get("n_sources"))
    except Exception:
        return None


def _extract_total_ms(doc: dict[str, Any]) -> float | None:
    try:
        value = doc.get("payload", {}).get("result", {}).get("timing", {}).get("total_ms")
        if value is None:
            return None
        return float(value)
    except Exception:
        return None
