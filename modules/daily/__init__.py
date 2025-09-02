from flask import Blueprint

daily_bp = Blueprint(
    'daily',
    __name__,
    template_folder='../../templates/daily',
    static_folder='../../static'
)

from . import routes