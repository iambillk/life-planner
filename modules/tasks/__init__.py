# ============================== 1) modules/tasks/__init__.py ==============================
from flask import Blueprint


tasks_bp = Blueprint('tasks', __name__, template_folder='../../templates/tasks')


from . import routes # noqa: E402,F401