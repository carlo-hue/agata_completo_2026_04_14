from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..config import settings
from .tpf_service import build_tpf_metadata_payload
from .utils import validate_gaia_source_id, validate_sector


class JobNotFoundError(ValueError):
    pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _jobs_dir() -> Path:
    path = Path(settings.job_storage_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _job_path(job_id: str) -> Path:
    return _jobs_dir() / f"{job_id}.json"


def _write_json(path: Path, payload: dict) -> None:
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def _write_job_state(job_id: str, payload: dict) -> None:
    _write_json(_job_path(job_id), payload)


def _read_job_state(job_id: str) -> dict:
    path = _job_path(job_id)
    if not path.exists():
        raise JobNotFoundError("job_id non trovato")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        raise RuntimeError("stato job temporaneamente non leggibile") from err


def _set_job_running(job_id: str, message: str, percent: float | None = None) -> None:
    state = _read_job_state(job_id)
    progress = {
        "stage": "running",
        "message": message,
        "updated_at_utc": _utc_now_iso(),
    }
    if percent is not None:
        progress["percent"] = round(float(percent), 1)
    state["status"] = "running"
    state["progress"] = progress
    _write_job_state(job_id, state)


def _run_metadata_job(job_id: str, gaia_source_id: str, sector: int) -> None:
    try:
        _set_job_running(job_id, "Risoluzione metadata Gaia e overlay in corso...", 10.0)
        result = build_tpf_metadata_payload(gaia_source_id, sector)
        state = _read_job_state(job_id)
        state["status"] = "completed"
        state["progress"] = {
            "stage": "completed",
            "message": "Metadata completato.",
            "current": 1,
            "total": 1,
            "percent": 100.0,
            "updated_at_utc": _utc_now_iso(),
        }
        state["result"] = result
        _write_job_state(job_id, state)
    except Exception as err:
        state = _read_job_state(job_id)
        state["status"] = "failed"
        state["error"] = str(err)
        state["progress"] = {
            "stage": "failed",
            "message": str(err),
            "updated_at_utc": _utc_now_iso(),
        }
        _write_job_state(job_id, state)


def start_metadata_job(gaia_source_id: str, sector) -> dict:
    normalized_gaia_source_id = validate_gaia_source_id(gaia_source_id)
    normalized_sector = validate_sector(sector)
    job_id = uuid.uuid4().hex
    state = {
        "job_id": job_id,
        "job_type": "metadata",
        "gaia_source_id": normalized_gaia_source_id,
        "sector": normalized_sector,
        "status": "queued",
        "created_at_utc": _utc_now_iso(),
        "progress": {
            "stage": "queued",
            "message": "Job metadata accodato.",
            "updated_at_utc": _utc_now_iso(),
        },
    }
    _write_job_state(job_id, state)
    worker = threading.Thread(
        target=_run_metadata_job,
        args=(job_id, normalized_gaia_source_id, normalized_sector),
        daemon=True,
    )
    worker.start()
    return {
        "status": "accepted",
        "job_id": job_id,
        "message": "Risoluzione metadata e overlay avviata.",
    }


def get_job_status(job_id: str) -> dict:
    state = _read_job_state(job_id)
    return {
        "status": "ok",
        "job_id": job_id,
        "job_status": state.get("status"),
        "progress": state.get("progress") or {},
        "error": state.get("error"),
    }


def get_job_result(job_id: str) -> dict:
    state = _read_job_state(job_id)
    job_status = state.get("status")
    if job_status == "failed":
        raise ValueError(state.get("error") or "Job fallito")
    if job_status != "completed":
        return {
            "status": "pending",
            "job_id": job_id,
            "job_status": job_status,
            "progress": state.get("progress") or {},
        }
    result = dict(state.get("result") or {})
    result["job_id"] = job_id
    return result
