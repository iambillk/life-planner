# modules/persprojects/__init__.py
from flask import Blueprint

persprojects_bp = Blueprint('persprojects', __name__)

from . import routes