# agata/admin/services/saved_query_service.py
"""
Saved Query Service

Gestione query personali salvate e preset superuser.
Funzioni pure Python, nessun import Flask.
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from agata.auth_models.saved_query import SavedQuery, QueryPreset

logger = logging.getLogger(__name__)


# =============================================================================
# QUERY PERSONALI
# =============================================================================

def list_user_queries(db: Session, user_id: str, context: str) -> list[SavedQuery]:
    """Lista query salvate dall'utente per un contesto."""
    return (
        db.query(SavedQuery)
        .filter(SavedQuery.user_id == user_id, SavedQuery.context == context)
        .order_by(SavedQuery.is_default.desc(), SavedQuery.updated_at.desc())
        .all()
    )


def create_user_query(
    db: Session,
    user_id: str,
    context: str,
    name: str,
    filter_params: dict,
    description: Optional[str] = None,
) -> SavedQuery:
    """Crea una nuova query salvata per l'utente."""
    q = SavedQuery(
        user_id=user_id,
        context=context,
        name=name.strip(),
        description=description.strip() if description else None,
        filter_params=filter_params,
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    logger.info(f"SavedQuery {q.id} creata da utente {user_id} (context={context})")
    return q


def update_user_query(
    db: Session,
    query_id: int,
    user_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    filter_params: Optional[dict] = None,
    is_default: Optional[bool] = None,
) -> Optional[SavedQuery]:
    """Aggiorna una query salvata. Verifica che appartenga all'utente."""
    q = db.query(SavedQuery).filter(SavedQuery.id == query_id, SavedQuery.user_id == user_id).first()
    if not q:
        return None
    if name is not None:
        q.name = name.strip()
    if description is not None:
        q.description = description.strip() or None
    if filter_params is not None:
        q.filter_params = filter_params
    if is_default is not None:
        q.is_default = is_default
    db.commit()
    db.refresh(q)
    return q


def delete_user_query(db: Session, query_id: int, user_id: str) -> bool:
    """Elimina una query salvata. Verifica che appartenga all'utente."""
    q = db.query(SavedQuery).filter(SavedQuery.id == query_id, SavedQuery.user_id == user_id).first()
    if not q:
        return False
    db.delete(q)
    db.commit()
    logger.info(f"SavedQuery {query_id} eliminata da utente {user_id}")
    return True


# =============================================================================
# PRESET (superuser)
# =============================================================================

def list_presets(
    db: Session,
    context: str,
    association_id: Optional[int],
    is_superuser: bool,
) -> list[QueryPreset]:
    """
    Lista preset visibili all'utente.
    - Superuser vede tutti.
    - Altri vedono: globali (association_id IS NULL) + propria associazione.
    """
    q = db.query(QueryPreset).filter(
        QueryPreset.context == context,
        QueryPreset.is_active == True,
    )
    if not is_superuser:
        from sqlalchemy import or_
        q = q.filter(
            or_(
                QueryPreset.association_id == None,
                QueryPreset.association_id == association_id,
            )
        )
    return q.order_by(QueryPreset.sort_order.asc(), QueryPreset.name.asc()).all()


def create_preset(
    db: Session,
    context: str,
    name: str,
    filter_params: dict,
    created_by: str,
    description: Optional[str] = None,
    association_id: Optional[int] = None,
    sort_order: int = 0,
) -> QueryPreset:
    """Crea un nuovo preset (solo superuser)."""
    p = QueryPreset(
        context=context,
        name=name.strip(),
        description=description.strip() if description else None,
        filter_params=filter_params,
        association_id=association_id,
        created_by=created_by,
        sort_order=sort_order,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    scope = f"assoc {association_id}" if association_id else "globale"
    logger.info(f"QueryPreset {p.id} creato da {created_by} (context={context}, scope={scope})")
    return p


def update_preset(
    db: Session,
    preset_id: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
    filter_params: Optional[dict] = None,
    association_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    sort_order: Optional[int] = None,
) -> Optional[QueryPreset]:
    """Aggiorna un preset (solo superuser)."""
    p = db.query(QueryPreset).filter(QueryPreset.id == preset_id).first()
    if not p:
        return None
    if name is not None:
        p.name = name.strip()
    if description is not None:
        p.description = description.strip() or None
    if filter_params is not None:
        p.filter_params = filter_params
    if association_id is not None:
        p.association_id = association_id if association_id != 0 else None
    if is_active is not None:
        p.is_active = is_active
    if sort_order is not None:
        p.sort_order = sort_order
    db.commit()
    db.refresh(p)
    return p


def delete_preset(db: Session, preset_id: int) -> bool:
    """Elimina un preset (solo superuser)."""
    p = db.query(QueryPreset).filter(QueryPreset.id == preset_id).first()
    if not p:
        return False
    db.delete(p)
    db.commit()
    logger.info(f"QueryPreset {preset_id} eliminato")
    return True
