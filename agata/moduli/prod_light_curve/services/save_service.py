from __future__ import annotations

from pathlib import Path

from ..config import settings
from .pipeline_service import run_ground_photometry
from .utils import decode_json, encode_json, ensure_directory, stable_dataset_id, utc_now_iso


def _session_dir() -> Path:
    return ensure_directory(settings.session_storage_dir)


def _session_path(session_id: str) -> Path:
    return _session_dir() / f"{session_id}.json"


def _build_session_id(dataset_path: str) -> str:
    return f"prodlc-{stable_dataset_id(dataset_path)}-{utc_now_iso().replace(':', '').replace('-', '')}"


def save_prod_session(payload: dict) -> dict:
    dataset = payload.get("dataset") if isinstance(payload.get("dataset"), dict) else {}
    dataset_path = str(payload.get("dataset_path") or dataset.get("dataset_path") or "").strip()
    if not dataset_path:
        raise ValueError("dataset_path mancante nel payload di salvataggio")

    technical_session = payload.get("technical_session") if isinstance(payload.get("technical_session"), dict) else {}
    session_id = str(technical_session.get("update_session_id") or "").strip() or _build_session_id(dataset_path)
    session_payload = {
        "session_id": session_id,
        "saved_at_utc": utc_now_iso(),
        "dataset_path": dataset_path,
        "payload": payload,
    }
    _session_path(session_id).write_text(encode_json(session_payload), encoding="utf-8")
    return {
        "status": "ok",
        "message": "Sessione tecnica salvata.",
        "saved": True,
        "mode": "file",
        "session": {
            "session_id": session_id,
            "saved_at_utc": session_payload["saved_at_utc"],
            "dataset_path": dataset_path,
        },
    }


def list_prod_sessions(dataset_path: str) -> dict:
    target_dataset_id = stable_dataset_id(dataset_path)
    sessions = []
    for file_path in sorted(_session_dir().glob("prodlc-*.json"), reverse=True):
        try:
            payload = decode_json(file_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        current_dataset_path = str(payload.get("dataset_path") or "").strip()
        if not current_dataset_path:
            continue
        if stable_dataset_id(current_dataset_path) != target_dataset_id:
            continue
        sessions.append({
            "session_id": payload.get("session_id"),
            "saved_at_utc": payload.get("saved_at_utc"),
            "dataset_path": current_dataset_path,
        })
    return {
        "status": "ok",
        "dataset_path": str(Path(dataset_path).resolve()),
        "sessions": sessions,
    }


def restore_prod_session(session_id: str) -> dict:
    file_path = _session_path(session_id)
    if not file_path.exists():
        raise ValueError(f"Sessione {session_id} non trovata")
    payload = decode_json(file_path.read_text(encoding="utf-8"))
    stored_payload = payload.get("payload")
    if not isinstance(stored_payload, dict):
        raise ValueError("Payload sessione non valido")
    result = run_ground_photometry(stored_payload)
    result["restored_session"] = {
        "session_id": session_id,
        "saved_at_utc": payload.get("saved_at_utc"),
    }
    result["message"] = f"Sessione {session_id} ripristinata."
    return result


def delete_prod_session(session_id: str) -> dict:
    file_path = _session_path(session_id)
    if not file_path.exists():
        raise ValueError(f"Sessione {session_id} non trovata")
    file_path.unlink()
    return {
        "status": "ok",
        "deleted": True,
        "session_id": session_id,
        "message": f"Sessione {session_id} eliminata.",
    }

