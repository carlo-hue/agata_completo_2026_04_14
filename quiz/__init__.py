from flask import Blueprint

quiz_bp = Blueprint('quiz', __name__,
                    template_folder='templates',
                    static_folder='static',
                    static_url_path='/static/quiz')

from . import routes
