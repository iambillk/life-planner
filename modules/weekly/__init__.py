from flask import Blueprint

weekly_bp = Blueprint(
    'weekly',
    __name__,
    template_folder='../../templates/weekly',
    static_folder='../../static'
)

from . import routes