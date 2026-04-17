"""
Help Blueprint - Sistema di aiuto online per AGATA

Routes:
- GET /agata/help/                       - Help center (lista articoli per modulo)
- GET /agata/help/article/<help_id>      - Pagina intera singolo articolo
- GET /agata/help/api/article/<help_id>  - Frammento HTML per offcanvas AJAX
- POST /agata/help/api/cache/clear       - Invalida cache in-memory (superuser only)
"""
from flask import Blueprint

help_bp = Blueprint(
    'help',
    __name__,
    url_prefix='/agata/help',
    template_folder='templates',
    static_folder='static'
)

from . import routes  # noqa: F401, E402
