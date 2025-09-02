from flask import Blueprint

equipment_bp = Blueprint(
    'equipment', 
    __name__,
    template_folder='../../templates/equipment',
    static_folder='../../static'
)

from . import routes  # This imports the routes.py file in the same folder