"""
tpf - Modulo Target Pixel File (TESS)

Analisi di TPF TESS via Gaia source ID e settore:
- Download da MAST via lightkurve
- Visualizzazione frame e light curve
- Pipeline TPF con maschere custom

Endpoint:
- /agata/tpf/          - Homepage (UI)
- /agata/tpf/health    - Health check
- /agata/tpf/api/run   - Pipeline TPF
- /agata/tpf/api/frames - Frame window
- /agata/tpf/api/mast/sectors        - Settori MAST
- /agata/tpf/api/mast/local-sectors  - Settori locali
- /agata/tpf/api/mast/download       - Download da MAST
- /agata/tpf/api/save  - Salvataggio stub
"""

from __future__ import annotations

from flask import current_app, request
from flask_login import current_user

# ============================================================================
# BLUEPRINT INITIALIZATION
# ============================================================================

# Import blueprint from routes (already fully configured with routes and url_prefix)
from .routes import bp as tpf_bp


# ============================================================================
# PROTEZIONE GLOBALE BLUEPRINT (attaccato dopo l'import)
# ============================================================================


@tpf_bp.before_request
def require_analyst_role():
    """
    Protezione globale per tutto il blueprint tpf.

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


# (Routes already imported above as "tpf_bp from .routes")
