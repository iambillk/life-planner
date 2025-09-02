from flask import Blueprint

goals_bp = Blueprint(
    'goals',
    __name__,
    template_folder='../../templates/goals',
    static_folder='../../static'
)

from . import routes