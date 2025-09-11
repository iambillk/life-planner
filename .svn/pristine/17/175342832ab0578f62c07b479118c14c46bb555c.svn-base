# modules/daily/__init__.py
"""
Daily Planner Module - The Drill Sergeant System
"""

from flask import Blueprint

daily_bp = Blueprint(
    'daily',
    __name__,
    template_folder='../../templates/daily',
    static_folder='../../static',
    url_prefix='/daily'
)

from . import routes