from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path

from ..config import settings
from .pipeline_service import inspect_ground_dataset
from .utils import decode_json, encode_json, ensure_directory, utc_now_iso


def _jobs_dir() -> Path:
    return ensure_directory(settings.job_storage_dir)


def _job_path(job_id: str) -> Path:
    return _jobs_dir() / f"{job_id}.json"


class JobNotFoundError(ValueError):
    pass


def _write_job_state(job_id: str, payload: dict) -> None:
    target = _job_path(job_id)
    temp_path = target.with_suffix(".tmp")
    temp_path.write_text(encode_json(payload), encoding="utf-8")
    temp_path.replace(target)


def _read_job_state(job_id: str) -> dict:
    path = _job_path(job_id)
    if not path.exists():
        raise JobNotFoundError("job_id non trovato")
    try:
        return decode_json(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        raise RuntimeError("stato job temporaneamente non leggibile") from err


def _update_job_progress(
    job_id: str,
    *,
    stage: str,
    message: str,
    current: int | None = None,
    total: int | None = None,
) -> None:
    state = _read_job_state(job_id)
    progress = {
        "stage": stage,
        "message": message,
        "current": current,
        "total": total,
        "updated_at_utc": utc_now_iso(),
    }
    if current is not None and total:
        progress["percent"] = round((float(current) / float(total)) * 100.0, 1)
    state["status"] = "running"
    state["progress"] = progress
    _write_job_state(job_id, state)


def _run_inspect_job(job_id: str, dataset_path: str) -> None:
    try:
        _update_job_progress(
            job_id,
            stage="scan",
            message="Scansione dataset FITS in corso...",
            current=0,
            total=None,
        )
        result = inspect_ground_dataset(
            dataset_path,
            progress_callback=lambda **kwargs: _update_job_progress(job_id, **kwargs),
        )
        state = _read_job_state(job_id)
        state["status"] = "completed"
        state["progress"] = {
            "stage": "completed",
            "message": "Reference image pronta.",
            "current": 1,
            "total": 1,
            "percent": 100.0,
            "updated_at_utc": utc_now_iso(),
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
            "updated_at_utc": utc_now_iso(),
        }
        _write_job_state(job_id, state)


def start_inspect_job(dataset_path: str) -> dict:
    job_id = uuid.uuid4().hex
    state = {
        "job_id": job_id,
        "job_type": "inspect",
        "dataset_path": dataset_path,
        "status": "queued",
        "created_at_utc": utc_now_iso(),
        "progress": {
            "stage": "queued",
            "message": "Job di ispezione accodato.",
            "updated_at_utc": utc_now_iso(),
        },
    }
    _write_job_state(job_id, state)
    worker = threading.Thread(target=_run_inspect_job, args=(job_id, dataset_path), daemon=True)
    worker.start()
    return {
        "status": "accepted",
        "job_id": job_id,
        "message": "Ispezione reference image avviata.",
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
