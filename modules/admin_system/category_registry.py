# modules/admin_system/category_registry.py
"""
Category Registry - Central Configuration for Category Management
==================================================================

This registry defines where all categories live (files vs database) and how to manage them.
It's the "brain" that allows the unified Category Manager UI to work seamlessly across
different storage backends.

FILE: modules/admin_system/category_registry.py
VERSION: 1.0.0
CREATED: 2025-01-10
AUTHOR: Billas

CHANGELOG:
----------
v1.0.0 (2025-01-10)
- Initial registry creation
- Mapped all modules: Projects, Equipment, Real Estate, Network, Financial, Daily Planner
- Defined storage types (file vs database)
- Configured usage tracking for each category type
- Added display metadata (icons, labels)

STRUCTURE:
----------
Each module contains category groups, and each category group defines:
- storage: 'file' or 'database'
- file_path: Path to constants file (if file-based)
- constant_name: Name of the constant in the file (if file-based)
- model: SQLAlchemy model name (if database-based)
- table/column: Direct DB access info
- usage_checks: List of tables/columns to count usage
- display metadata: Icon, label, description

ADDING NEW CATEGORIES:
----------------------
To add a new category type to the system:
1. Add entry to appropriate module in CATEGORY_REGISTRY
2. Define storage type and location
3. Define usage_checks (where this category is used)
4. Restart app - new category appears in UI automatically
"""

# =============================================================================
# CATEGORY REGISTRY - THE MASTER CONFIGURATION
# =============================================================================

CATEGORY_REGISTRY = {
    
    # =========================================================================
    # PROJECTS MODULE (TCH Work Projects)
    # =========================================================================
    'projects': {
        'display_name': 'Work Projects (TCH)',
        'icon': '📊',
        'description': 'Business and client project management',
        'categories': {
            
            'project_categories': {
                'label': 'Project Categories',
                'storage': 'file',
                'file_path': 'modules/projects/constants.py',
                'constant_name': 'PROJECT_CATEGORIES',
                'usage_checks': [
                    {'table': 'tch_projects', 'column': 'category', 'label': 'TCH Projects'}
                ],
                'description': 'Types of business projects (Marketing, Coding, etc.)'
            },
            
            'project_statuses': {
                'label': 'Project Statuses',
                'storage': 'file',
                'file_path': 'modules/projects/constants.py',
                'constant_name': 'PROJECT_STATUSES',
                'usage_checks': [
                    {'table': 'tch_projects', 'column': 'status', 'label': 'TCH Projects'}
                ],
                'description': 'Project lifecycle states (planning, active, completed, etc.)'
            },
            
            'priority_levels': {
                'label': 'Priority Levels',
                'storage': 'file',
                'file_path': 'modules/projects/constants.py',
                'constant_name': 'PRIORITY_LEVELS',
                'usage_checks': [
                    {'table': 'tch_projects', 'column': 'priority', 'label': 'TCH Projects'},
                    {'table': 'tch_tasks', 'column': 'priority', 'label': 'TCH Tasks'}
                ],
                'description': 'Urgency levels (low, medium, high, critical)'
            },
            
            'task_categories': {
                'label': 'Task Categories',
                'storage': 'file',
                'file_path': 'modules/projects/constants.py',
                'constant_name': 'TASK_CATEGORIES',
                'usage_checks': [
                    {'table': 'tch_tasks', 'column': 'category', 'label': 'TCH Tasks'}
                ],
                'description': 'Types of tasks within projects (Development, Testing, etc.)'
            }
        }
    },
    
    # =========================================================================
    # PERSONAL PROJECTS MODULE
    # =========================================================================
    'persprojects': {
        'display_name': 'Personal Projects',
        'icon': '🏠',
        'description': 'Personal goals and home improvement projects',
        'categories': {
            
            'project_categories': {
                'label': 'Project Categories',
                'storage': 'file',
                'file_path': 'modules/persprojects/constants.py',
                'constant_name': 'PERSONAL_PROJECT_CATEGORIES',
                'usage_checks': [
                    {'table': 'personal_projects', 'column': 'category', 'label': 'Personal Projects'}
                ],
                'description': 'Types of personal projects (Home Improvement, Hobbies, etc.)'
            },
            
            'project_statuses': {
                'label': 'Project Statuses',
                'storage': 'file',
                'file_path': 'modules/persprojects/constants.py',
                'constant_name': 'PROJECT_STATUSES',
                'usage_checks': [
                    {'table': 'personal_projects', 'column': 'status', 'label': 'Personal Projects'}
                ],
                'description': 'Project lifecycle states',
                'note': 'Stored as tuples: (value, display_name)'
            },
            
            'note_categories': {
                'label': 'Note Categories',
                'storage': 'file',
                'file_path': 'modules/persprojects/constants.py',
                'constant_name': 'NOTE_CATEGORIES',
                'usage_checks': [
                    {'table': 'personal_project_notes', 'column': 'category', 'label': 'Project Notes'}
                ],
                'description': 'Categories for project notes'
            }
        }
    },
    
    # =========================================================================
    # EQUIPMENT MODULE
    # =========================================================================
    'equipment': {
        'display_name': 'Equipment',
        'icon': '🔧',
        'description': 'Vehicles, tools, and equipment tracking',
        'categories': {
            
            'equipment_categories': {
                'label': 'Equipment Categories',
                'storage': 'file',
                'file_path': 'modules/equipment/constants.py',
                'constant_name': 'EQUIPMENT_CATEGORIES',
                'usage_checks': [
                    {'table': 'equipment', 'column': 'category', 'label': 'Equipment Items'}
                ],
                'description': 'Types of equipment (Auto, Lawn, Marine, etc.)'
            },
            
            'service_types': {
                'label': 'Service Types',
                'storage': 'file',
                'file_path': 'modules/equipment/constants.py',
                'constant_name': 'SERVICE_TYPES',
                'usage_checks': [
                    {'table': 'maintenance_records', 'column': 'service_type', 'label': 'Maintenance Records'}
                ],
                'description': 'Types of maintenance services'
            }
        }
    },
    
    # =========================================================================
    # REAL ESTATE MODULE
    # =========================================================================
    'realestate': {
        'display_name': 'Real Estate',
        'icon': '🏡',
        'description': 'Property and maintenance management',
        'categories': {
            
            'property_types': {
                'label': 'Property Types',
                'storage': 'file',
                'file_path': 'modules/realestate/constants.py',
                'constant_name': 'PROPERTY_TYPES',
                'usage_checks': [
                    {'table': 'properties', 'column': 'property_type', 'label': 'Properties'}
                ],
                'description': 'Types of properties (House, Cottage, Condo, etc.)'
            },
            
            'maintenance_categories': {
                'label': 'Maintenance Categories',
                'storage': 'file',
                'file_path': 'modules/realestate/constants.py',
                'constant_name': 'MAINTENANCE_CATEGORIES',
                'usage_checks': [
                    {'table': 'property_maintenance', 'column': 'category', 'label': 'Maintenance Records'}
                ],
                'description': 'Categories for property maintenance (HVAC, Plumbing, etc.)'
            }
        }
    },
    
    # =========================================================================
    # NETWORK MODULE
    # =========================================================================
    'network': {
        'display_name': 'Network',
        'icon': '🌐',
        'description': 'Network device and infrastructure management',
        'categories': {
            
            'device_roles': {
                'label': 'Device Roles',
                'storage': 'code',  # Hardcoded in routes.py
                'file_path': 'modules/network/routes.py',
                'constant_name': 'ROLE_CHOICES',
                'usage_checks': [
                    {'table': 'devices', 'column': 'role', 'label': 'Network Devices'}
                ],
                'description': 'Types of network devices (NAS, Switch, Router, etc.)',
                'note': 'Currently hardcoded in routes.py - consider moving to constants.py'
            },
            
            'device_status': {
                'label': 'Device Status',
                'storage': 'code',
                'file_path': 'modules/network/routes.py',
                'constant_name': 'STATUS_CHOICES',
                'usage_checks': [
                    {'table': 'devices', 'column': 'status', 'label': 'Network Devices'}
                ],
                'description': 'Device operational states (active, retired, lab, spare)'
            },
            
            'locations': {
                'label': 'Device Locations',
                'storage': 'code',
                'file_path': 'modules/network/routes.py',
                'constant_name': 'LOCATION_CHOICES',
                'usage_checks': [
                    {'table': 'devices', 'column': 'location', 'label': 'Network Devices'}
                ],
                'description': 'Physical locations of network devices'
            }
        }
    },
    
    # =========================================================================
    # FINANCIAL MODULE (DATABASE-BASED)
    # =========================================================================
    'financial': {
        'display_name': 'Financial',
        'icon': '💰',
        'description': 'Spending tracking and budgeting',
        'categories': {
            
            'spending_categories': {
                'label': 'Spending Categories',
                'storage': 'database',
                'model': 'SpendingCategory',
                'table': 'spending_categories',
                'name_column': 'name',
                'id_column': 'id',
                'usage_column': 'usage_count',  # Has built-in counter
                'usage_checks': [
                    {'table': 'transactions', 'column': 'category_id', 'label': 'Transactions', 'is_fk': True}
                ],
                'description': 'Categories for spending (Food, Gas, Shopping, etc.)',
                'supports_custom': True,
                'has_metadata': True,  # Has color, icon fields
                'metadata_fields': ['color', 'icon', 'is_custom']
            }
        }
    },
    
    # =========================================================================
    # DAILY PLANNER MODULE (DATABASE-BASED)
    # =========================================================================
    'daily_planner': {
        'display_name': 'Daily Planner',
        'icon': '📅',
        'description': 'Calendar and event management',
        'categories': {
            
            'event_types': {
                'label': 'Event Types',
                'storage': 'database',
                'model': 'EventType',
                'table': 'event_types',
                'name_column': 'type_name',
                'id_column': 'id',
                'usage_column': 'usage_count',  # Has built-in counter
                'usage_checks': [
                    {'table': 'calendar_events', 'column': 'event_type', 'label': 'Calendar Events'}
                ],
                'description': 'Types of calendar events (Soccer, Dentist, Meeting, etc.)',
                'supports_custom': True,
                'has_autocreate': True  # Auto-creates on first use
            }
        }
    }
}


# =============================================================================
# HELPER FUNCTIONS FOR REGISTRY ACCESS
# =============================================================================

def get_all_modules():
    """
    Get list of all modules in the registry
    
    Returns:
        list: Module keys with display info
        
    Example:
        [
            {'key': 'projects', 'name': 'Work Projects (TCH)', 'icon': '📊'},
            {'key': 'equipment', 'name': 'Equipment', 'icon': '🔧'},
            ...
        ]
    """
    modules = []
    for key, config in CATEGORY_REGISTRY.items():
        modules.append({
            'key': key,
            'name': config['display_name'],
            'icon': config['icon'],
            'description': config.get('description', '')
        })
    return modules


def get_module_categories(module_key):
    """
    Get all category types for a specific module
    
    Args:
        module_key: Module identifier (e.g., 'projects', 'equipment')
        
    Returns:
        dict: Category configurations for this module
        
    Raises:
        KeyError: If module not found in registry
    """
    if module_key not in CATEGORY_REGISTRY:
        raise KeyError(f"Module '{module_key}' not found in category registry")
    
    return CATEGORY_REGISTRY[module_key]['categories']


def get_category_config(module_key, category_key):
    """
    Get configuration for a specific category
    
    Args:
        module_key: Module identifier
        category_key: Category identifier within module
        
    Returns:
        dict: Category configuration
        
    Raises:
        KeyError: If module or category not found
    """
    module = CATEGORY_REGISTRY.get(module_key)
    if not module:
        raise KeyError(f"Module '{module_key}' not found")
    
    category = module['categories'].get(category_key)
    if not category:
        raise KeyError(f"Category '{category_key}' not found in module '{module_key}'")
    
    return category


def is_database_backed(module_key, category_key):
    """
    Check if a category is stored in database vs file
    
    Args:
        module_key: Module identifier
        category_key: Category identifier
        
    Returns:
        bool: True if database-backed, False if file-backed
    """
    config = get_category_config(module_key, category_key)
    return config['storage'] == 'database'


def get_storage_info(module_key, category_key):
    """
    Get detailed storage information for a category
    
    Args:
        module_key: Module identifier
        category_key: Category identifier
        
    Returns:
        dict: Storage configuration details
    """
    config = get_category_config(module_key, category_key)
    
    if config['storage'] == 'database':
        return {
            'type': 'database',
            'model': config['model'],
            'table': config['table'],
            'name_column': config['name_column'],
            'supports_custom': config.get('supports_custom', False),
            'has_metadata': config.get('has_metadata', False)
        }
    else:
        return {
            'type': 'file',
            'file_path': config['file_path'],
            'constant_name': config['constant_name']
        }


# =============================================================================
# VALIDATION HELPERS
# =============================================================================

def validate_registry():
    """
    Validate registry configuration on startup
    Checks for required fields and correct structure
    
    Returns:
        tuple: (is_valid: bool, errors: list)
    """
    errors = []
    
    for module_key, module_config in CATEGORY_REGISTRY.items():
        # Check required module fields
        if 'display_name' not in module_config:
            errors.append(f"Module '{module_key}' missing 'display_name'")
        if 'categories' not in module_config:
            errors.append(f"Module '{module_key}' missing 'categories'")
            continue
        
        # Check each category
        for cat_key, cat_config in module_config['categories'].items():
            # Check required fields
            required = ['label', 'storage', 'usage_checks']
            for field in required:
                if field not in cat_config:
                    errors.append(f"Category '{module_key}.{cat_key}' missing '{field}'")
            
            # Check storage-specific fields
            storage = cat_config.get('storage')
            if storage == 'file' or storage == 'code':
                if 'file_path' not in cat_config:
                    errors.append(f"File-based category '{module_key}.{cat_key}' missing 'file_path'")
                if 'constant_name' not in cat_config:
                    errors.append(f"File-based category '{module_key}.{cat_key}' missing 'constant_name'")
            elif storage == 'database':
                if 'model' not in cat_config:
                    errors.append(f"DB category '{module_key}.{cat_key}' missing 'model'")
                if 'table' not in cat_config:
                    errors.append(f"DB category '{module_key}.{cat_key}' missing 'table'")
    
    return len(errors) == 0, errors


# =============================================================================
# MODULE INITIALIZATION
# =============================================================================

# Validate registry on import
_is_valid, _errors = validate_registry()
if not _is_valid:
    import warnings
    warnings.warn(f"Category registry validation failed: {_errors}")