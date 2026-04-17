"""
galassie_nane - Modulo Ricerca Galassie Nane

Ricerca e valutazione di candidati galassie nane con:
- Analisi singola di campi Gaia
- Heatmap densità e metriche tile
- Salvataggio e riapertura run locali

Endpoint:
- /agata/galassie-nane/ - Homepage (UI)
- /agata/galassie-nane/api/single-run - API analisi singola
"""

from __future__ import annotations

from flask import Blueprint, current_app, request
from flask_login import current_user

# ============================================================================
# BLUEPRINT INITIALIZATION
# ============================================================================

galassie_nane_bp = Blueprint(
    "galassie_nane",
    __name__,
    url_prefix="/agata/galassie-nane",
    template_folder="templates",
    static_folder="static",
)


# ============================================================================
# PROTEZIONE GLOBALE BLUEPRINT
# ============================================================================

@galassie_nane_bp.before_request
def require_analyst_role():
    """
    Protezione globale per tutto il blueprint galassie_nane.

    Richiede ruolo minimo: analyst
    Ruoli ammessi: analyst, reviewer, admin, superuser
    Blocca: viewer e utenti non autenticati

    Supporta LOCAL_DEV_BYPASS_AUTH per sviluppo locale senza autenticazione.
    """
    # Permetti bypass locale in development
    if current_app.config.get("LOCAL_DEV_BYPASS_AUTH", False):
        return None

    # Permetti accesso a file statici senza autenticazione
    if request.endpoint and "static" in request.endpoint:
        return None

    # Verifica autenticazione
    if not current_user.is_authenticated:
        return "Access denied: Authentication required", 401

    # Verifica account attivo
    if not current_user.is_active:
        return "Access denied: Account disabled", 403

    # Verifica ruolo minimo (analyst o superiore)
    allowed_roles = {"analyst", "reviewer", "admin", "superuser"}
    if current_user.role not in allowed_roles:
        return f"Access denied: Role '{current_user.role}' not permitted. Required: {', '.join(sorted(allowed_roles))}", 403

    # Utente autorizzato, procedi
    return None


# ============================================================================
# IMPORT ROUTES
# ============================================================================

from . import routes  # noqa: E402,F401
