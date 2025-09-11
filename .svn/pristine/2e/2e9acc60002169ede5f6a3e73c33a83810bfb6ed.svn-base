from flask import Blueprint

# All Real Estate URLs will live under /property
realestate_bp = Blueprint("realestate", __name__, url_prefix="/property")

# Import routes so they register with the blueprint
from . import routes  # noqa: E402,F401

