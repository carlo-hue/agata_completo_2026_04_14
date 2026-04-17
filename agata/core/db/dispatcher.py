from agata.db import SessionLocal
from .registry import get_handler


def dispatch(route: str, payload: dict = None):
    """
    Chiama l'handler registrato per 'route', gestendo sessione e commit/rollback.

    Args:
        route: Nome della route nel formato 'entity/azione' (es. 'stars/upsert')
        payload: Dizionario con i parametri per l'handler

    Returns:
        Il valore restituito dall'handler

    Raises:
        KeyError: Se la route non è registrata
        Exception: Qualsiasi eccezione sollevata dall'handler (dopo rollback)
    """
    payload = payload or {}
    handler = get_handler(route)
    db = SessionLocal()
    try:
        result = handler(payload, db)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
