# modules/vault/__init__.py
"""
Document Vault Module
Digital filing cabinet for code, configs, contracts, and reference materials
"""

from flask import Blueprint

vault_bp = Blueprint(
    'vault',
    __name__,
    template_folder='../../templates/vault',
    static_folder='../../static',
    url_prefix='/vault'
)

from . import routes  # noqa: E402, F401