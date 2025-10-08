# modules/admin_tools/__init__.py
"""
Admin Tools Module
Diagnostic tools and knowledge base for system administrators
"""

from flask import Blueprint

admin_tools_bp = Blueprint(
    'admin_tools',
    __name__,
    template_folder='../../templates/admin_tools',
    static_folder='../../static'
)

from . import routes  # noqa: E402, F401