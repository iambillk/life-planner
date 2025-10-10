# modules/admin_system/__init__.py
"""
Admin System Health Module
Provides complete visibility into application health, database, storage, and activity
"""

from flask import Blueprint

admin_system_bp = Blueprint('admin_system', __name__, url_prefix='/admin/system')

from . import routes