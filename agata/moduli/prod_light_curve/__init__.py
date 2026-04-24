"""
prod_light_curve - Modulo AGATA per fotometria ground-based da sequenze FITS.

Endpoint principali:
- /agata/prod-light-curve/                - UI modulo
- /agata/prod-light-curve/health          - Health check
- /agata/prod-light-curve/api/inspect     - Ispezione dataset e reference image
- /agata/prod-light-curve/api/run         - Fotometria server-side
- /agata/prod-light-curve/api/save        - Salvataggio sessione tecnica
- /agata/prod-light-curve/api/sessions    - Elenco sessioni tecniche
- /agata/prod-light-curve/api/restore     - Ripristino sessione tecnica
- /agata/prod-light-curve/api/delete      - Eliminazione sessione tecnica
"""

from __future__ import annotations

from flask import current_app, request
from flask_login import current_user

from .routes import bp as prod_light_curve_bp


@prod_light_curve_bp.before_request
def require_analyst_role():
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

