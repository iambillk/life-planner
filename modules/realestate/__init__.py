# modules/realestate/__init__.py
"""
Real Estate Management Blueprint Initialization
Version: 1.0.0
Created: 2025-01-03

This module provides comprehensive property maintenance tracking,
vendor management, and cost analysis across multiple properties.

CHANGELOG:
v1.0.0 (2025-01-03)
- Initial blueprint creation
- Mobile-first responsive design
- Support for multiple properties
- Maintenance tracking with categories
- Vendor contact management
"""

from flask import Blueprint

# Create the blueprint with proper template and static paths
realestate_bp = Blueprint(
    'realestate',
    __name__,
    template_folder='../../templates/realestate',
    static_folder='../../static'
)

# Import routes to register them with the blueprint
from . import routes