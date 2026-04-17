from __future__ import annotations

from flask import Blueprint, current_app, request
from flask_login import current_user

mappe_stelle_bp = Blueprint(
    "mappe_stelle",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/agata/field-star-map",
)


@mappe_stelle_bp.before_request
def require_analyst_role():
    """Protezione globale: richiede ruolo minimo analyst."""
    if current_app.config.get("LOCAL_DEV_BYPASS_AUTH", False):
        return None
    if request.endpoint and "static" in request.endpoint:
        return None
    if not current_user.is_authenticated:
        return "Access denied: Authentication required", 401
    if not current_user.is_active:
        return "Access denied: Account disabled", 403
    allowed_roles = {"analyst", "reviewer", "admin", "superuser"}
    if current_user.role not in allowed_roles:
        return f"Access denied: Role '{current_user.role}' not permitted", 403
    return None


from . import routes  # noqa: E402,F401
