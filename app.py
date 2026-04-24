# app_agata.py
"""
AGATA Flask Application with OAuth 2.0 Authentication

Integra:
- Google OAuth (Workspace + Gmail)
- Slack OAuth (workspace integration)
- GitHub OAuth (optional)
- Flask-Login per session management
- SQLAlchemy per database
"""
from flask import Flask, session, redirect, url_for
from flask_login import LoginManager
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix
import os
import subprocess

# Load environment variables
load_dotenv()



# Compute git info once at startup (not on every request)
def _get_git_info():
    cwd = os.path.dirname(os.path.abspath(__file__))
    try:
        commit = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=cwd, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        commit = 'unknown'
    try:
        tag = subprocess.check_output(
            ['git', 'describe', '--tags'],
            cwd=cwd, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        from agata import __version__
        tag = __version__
    return commit, tag

_GIT_COMMIT, _GIT_TAG = _get_git_info()

# Import blueprints
from quiz import quiz_bp
from apod import apod_bp
from foto_serata import foto_serata_bp
from effemeridi import effemeridi_bp
from agata.moduli.variable_stars import variable_stars_bp
from agata.moduli.exoplanets import exoplanets_bp
from agata.moduli.field_star_map import mappe_stelle_bp as field_star_map_bp
from agata.moduli.galassie_nane import galassie_nane_bp

# Import auth modules
from agata.auth import init_oauth, auth_bp, magic_link_bp
from agata.auth_models import User
from agata.db import SessionLocal

# Import admin blueprint
from agata.moduli.admin import admin_bp
from agata.moduli.admin.routes.project_detail import project_detail_bp

# Import catalog blueprint
from agata.catalog import catalog_bp

# Import help blueprint
from agata.help import help_bp

# Import lightcurve blueprint
from agata.moduli.lightcurve import create_blueprint as create_lightcurve_blueprint

# Import prod_light_curve blueprint
from agata.moduli.prod_light_curve import prod_light_curve_bp

# Import tess_tce blueprint
from agata.moduli.tess_tce import create_blueprint as create_tess_tce_blueprint

# Import tpf blueprint
from agata.moduli.tpf import tpf_bp


# ============================================================================
# APP INITIALIZATION
# ============================================================================

# Get the absolute path to templates directory
import os.path
_root_path = os.path.dirname(os.path.abspath(__file__))
_template_folder = os.path.join(_root_path, 'templates')

app = Flask(__name__, template_folder=_template_folder)

flag = os.getenv("DEV_AUTH_BYPASS", "false")
app.config["DEV_AUTH_BYPASS"] = flag.lower() in ("1", "true", "yes", "on")
print("DEV_AUTH_BYPASS =", app.config["DEV_AUTH_BYPASS"])

# ProxyFix: trust nginx/apache headers for HTTPS
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
    x_host=1,
    x_prefix=1
)

# Configuration
_secret_key = os.getenv('SECRET_KEY')
if not _secret_key and os.getenv('FLASK_ENV') != 'development':
    raise RuntimeError("SECRET_KEY deve essere impostata nelle variabili d'ambiente in produzione")
app.config['SECRET_KEY'] = _secret_key or 'dev-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

flag = os.getenv("DEV_AUTH_BYPASS", "false")
app.config["DEV_AUTH_BYPASS"] = flag.lower() in ("1", "true", "yes", "on")

# Force HTTPS URLs when behind proxy
app.config['PREFERRED_URL_SCHEME'] = 'https'

# Upload size limit: 250 MB for TESS curl script files
app.config['MAX_CONTENT_LENGTH'] = 250 * 1024 * 1024  # 250 MB

# OAuth Configuration
app.config['GOOGLE_CLIENT_ID'] = os.getenv('GOOGLE_CLIENT_ID')
app.config['GOOGLE_CLIENT_SECRET'] = os.getenv('GOOGLE_CLIENT_SECRET')
app.config['SLACK_CLIENT_ID'] = os.getenv('SLACK_CLIENT_ID')
app.config['SLACK_CLIENT_SECRET'] = os.getenv('SLACK_CLIENT_SECRET')
app.config['SLACK_SIGNING_SECRET'] = os.getenv('SLACK_SIGNING_SECRET')
app.config['GITHUB_CLIENT_ID'] = os.getenv('GITHUB_CLIENT_ID')
app.config['GITHUB_CLIENT_SECRET'] = os.getenv('GITHUB_CLIENT_SECRET')

# Session configuration
# Per produzione (HTTPS), abilita SECURE cookie
is_production = os.getenv('BASE_URL', '').startswith('https://')
app.config['SESSION_COOKIE_SECURE'] = is_production
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = int(os.getenv('SESSION_TIMEOUT', 86400))  # 24h default

# ============================================================================
# FLASK-LOGIN SETUP
# ============================================================================

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'index'  # Redirect to homepage with login buttons
login_manager.login_message = None  # Disabilitato: la login page è auto-esplicativa

# Configure Flask-Login session/remember cookie names
login_manager.session_protection = 'strong'  # Protect against session hijacking
app.config['REMEMBER_COOKIE_NAME'] = 'remember'
app.config['REMEMBER_COOKIE_DURATION'] = 86400  # 24 hours
app.config['REMEMBER_COOKIE_SECURE'] = is_production
app.config['REMEMBER_COOKIE_HTTPONLY'] = True
app.config['REMEMBER_COOKIE_SAMESITE'] = 'Lax'


@login_manager.user_loader
def load_user(user_id):
    """
    Flask-Login user loader callback

    Args:
        user_id: User UUID string

    Returns:
        User instance or None
    """
    from sqlalchemy.orm import joinedload

    db = SessionLocal()
    try:
        # Eager load association to avoid DetachedInstanceError
        user = db.query(User).options(
            joinedload(User.association)
        ).filter_by(id=user_id, is_active=True).first()

        if user:
            # Expunge from session to avoid session conflicts
            db.expunge(user)

        return user
    finally:
        db.close()


# ============================================================================
# OAUTH INITIALIZATION
# ============================================================================

oauth = init_oauth(app)


# ============================================================================
# BLUEPRINT REGISTRATION
# ============================================================================

# Auth blueprint (login, callback, logout)
app.register_blueprint(auth_bp)

# Magic Link blueprint (login senza password)
app.register_blueprint(magic_link_bp)

# Admin blueprint (interfaccia amministrativa AGATA)
app.register_blueprint(admin_bp)

# Admin API blueprint (REST API per project detail)
app.register_blueprint(project_detail_bp)

# Existing blueprints
app.register_blueprint(quiz_bp, url_prefix='/quiz')
app.register_blueprint(apod_bp, url_prefix='/apod')
app.register_blueprint(foto_serata_bp, url_prefix='/foto_serata')
app.register_blueprint(effemeridi_bp, url_prefix='/effemeridi')
app.register_blueprint(variable_stars_bp, url_prefix='/agata/variable-stars')
app.register_blueprint(exoplanets_bp, url_prefix='/agata/exoplanets')
app.register_blueprint(field_star_map_bp)  # url_prefix defined in __init__.py
app.register_blueprint(galassie_nane_bp)  # url_prefix defined in __init__.py
app.register_blueprint(catalog_bp)  # url_prefix defined in __init__.py
app.register_blueprint(help_bp)     # url_prefix='/agata/help'
app.register_blueprint(create_lightcurve_blueprint())  # url_prefix='/agata/lightcurve'
app.register_blueprint(prod_light_curve_bp)  # url_prefix defined in __init__.py (/agata/prod-light-curve)
app.register_blueprint(create_tess_tce_blueprint(), url_prefix='/agata/tess-tce')
app.register_blueprint(tpf_bp)  # url_prefix defined in __init__.py (/agata/tpf)


# ============================================================================
# ROUTES
# ============================================================================

@app.route("/")
@app.route("/agata/")
def index():
    """Homepage - mostra dashboard se autenticato, altrimenti reindirizza a login page"""
    from flask_login import current_user

    if current_user.is_authenticated:
        # Utente autenticato: redirect a dashboard
        return redirect(url_for('admin.list_projects'))

    # Utente non autenticato: reindirizza a login page
    return redirect(url_for('auth.login_page'))


@app.route("/health")
def health():
    """Health check endpoint"""
    return {"status": "ok", "service": "AGATA"}


# ============================================================================
# CONTEXT PROCESSORS (pass variables to all templates)
# ============================================================================

@app.context_processor
def inject_app_info():
    """Inject app version and git info into all templates (computed once at startup)."""
    from agata import __version__
    return dict(
        app_version=__version__,
        git_commit=_GIT_COMMIT,
        git_tag=_GIT_TAG
    )


# ============================================================================
# SECURITY HEADERS
# ============================================================================

@app.after_request
def set_security_headers(response):
    """Aggiunge headers di sicurezza standard a tutte le risposte."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    if not app.debug:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(401)
def unauthorized(e):
    """Handle 401 Unauthorized"""
    return redirect(url_for('index'))


@app.errorhandler(403)
def forbidden(e):
    """Handle 403 Forbidden"""
    return {"error": "Accesso negato"}, 403


@app.errorhandler(404)
def not_found(e):
    """Handle 404 Not Found"""
    return {"error": "Risorsa non trovata"}, 404


@app.errorhandler(500)
def internal_error(e):
    """Handle 500 Internal Server Error"""
    app.logger.error(f"Internal error: {e}")
    return {"error": "Errore interno del server"}, 500


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    # Development server
    # In production usa gunicorn/uwsgi
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=os.getenv('FLASK_ENV') == 'development'
    )
