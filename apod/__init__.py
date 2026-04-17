from flask import Blueprint

apod_bp = Blueprint('apod', __name__,
                    template_folder='templates',
                    static_folder='static',
                    static_url_path='/static/apod',
				    url_prefix='/apod'
)

from . import apod