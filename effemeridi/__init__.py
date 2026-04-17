from flask import Blueprint

effemeridi_bp = Blueprint('effemeridi', __name__,
                    template_folder='templates',
                    static_folder='static',
                    static_url_path='/static/effemeridi',
				    url_prefix='/effemeridi'
)

from . import effemeridi