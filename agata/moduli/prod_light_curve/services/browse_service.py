from __future__ import annotations

from pathlib import Path

from ..config import settings

FITS_SUFFIXES = {
    ".fits",
    ".fit",
    ".fts",
    ".gz",
    ".fz",
}


def _root_path() -> Path:
    return Path(settings.default_dataset_root).expanduser().resolve()


def _resolve_browse_path(requested_path: str | None = None) -> Path:
    root = _root_path()
    target = Path(requested_path).expanduser() if requested_path else root
    resolved = target.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as err:
        raise ValueError("Il path richiesto e' fuori dalla root consentita") from err
    if not resolved.exists():
        raise ValueError("La cartella richiesta non esiste")
    if not resolved.is_dir():
        raise ValueError("Il path richiesto non e' una cartella")
    return resolved


def _is_fits_file(path: Path) -> bool:
    if not path.is_file():
        return False
    suffixes = {suffix.lower() for suffix in path.suffixes}
    return any(suffix in FITS_SUFFIXES for suffix in suffixes) or path.suffix.lower() in FITS_SUFFIXES


def _count_direct_fits_files(path: Path) -> int:
    count = 0
    for child in path.iterdir():
        if _is_fits_file(child):
            count += 1
    return count


def browse_dataset_directories(requested_path: str | None = None) -> dict:
    root = _root_path()
    current_path = _resolve_browse_path(requested_path)
    directories = []
    for child in sorted(current_path.iterdir(), key=lambda item: item.name.lower()):
        if not child.is_dir():
            continue
        direct_fits_count = _count_direct_fits_files(child)
        directories.append({
            "name": child.name,
            "path": str(child.resolve()),
            "has_fits_files": direct_fits_count > 0,
            "direct_fits_count": direct_fits_count,
        })

    parent_path = None
    if current_path != root:
        parent = current_path.parent.resolve()
        try:
            parent.relative_to(root)
            parent_path = str(parent)
        except ValueError:
            parent_path = None

    return {
        "status": "ok",
        "root_path": str(root),
        "current_path": str(current_path),
        "parent_path": parent_path,
        "current_path_direct_fits_count": _count_direct_fits_files(current_path),
        "current_path_has_fits_files": _count_direct_fits_files(current_path) > 0,
        "directories": directories,
    }
