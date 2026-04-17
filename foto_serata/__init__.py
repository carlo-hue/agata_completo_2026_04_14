from flask import Blueprint

foto_serata_bp = Blueprint('foto_serata', __name__,
                    template_folder='templates',
                    static_folder='static',
                    static_url_path='/static/foto_serata',
				    url_prefix='/foto_serata'
)

from . import foto_serata
