# modules/admin_system/category_service.py
"""
Category Service - Unified Category Management Abstraction Layer
=================================================================

This service provides a single interface for managing categories regardless of
storage backend (Python files vs database). It routes operations to the correct
handler based on the category registry configuration.

FILE: modules/admin_system/category_service.py
VERSION: 1.0.0
CREATED: 2025-01-10
AUTHOR: Billas

CHANGELOG:
----------
v1.0.0 (2025-01-10)
- Initial service creation
- Unified interface for file and database categories
- Smart backend routing based on registry
- Usage counting across all storage types
- Validation and safety checks
- Support for both string lists and tuples (for categories with display names)

ARCHITECTURE:
-------------
CategoryService acts as a facade that:
1. Accepts high-level commands (get, add, edit, delete)
2. Consults the registry to determine storage type
3. Routes to appropriate handler (FileHandler or DatabaseHandler)
4. Returns unified response format
5. Handles errors gracefully

USAGE EXAMPLE:
--------------
from modules.admin_system.category_service import CategoryService

# Get all categories (works for both file and DB)
categories = CategoryService.get_categories('projects', 'project_categories')

# Add new category (automatically handles backend)
result = CategoryService.add_category('projects', 'project_categories', 'Consulting')

# Check usage before deleting
usage = CategoryService.get_usage_count('equipment', 'equipment_categories', 'Auto')
if usage == 0:
    CategoryService.delete_category('equipment', 'equipment_categories', 'Auto')
"""

from sqlalchemy import text
from models.base import db
from models.daily_planner import EventType
from models.financial import SpendingCategory
from .category_registry import (
    get_category_config,
    is_database_backed,
    CATEGORY_REGISTRY
)
from .file_handler import FileHandler  # We'll build this next
import re


# =============================================================================
# CATEGORY SERVICE - MAIN INTERFACE
# =============================================================================

class CategoryService:
    """
    Unified category management service
    Routes operations to correct backend transparently
    """
    
    @staticmethod
    def get_categories(module_key, category_key):
        """
        Get list of all categories for a given type
        
        Args:
            module_key: Module identifier (e.g., 'projects', 'equipment')
            category_key: Category type (e.g., 'project_categories')
            
        Returns:
            dict: {
                'success': bool,
                'categories': list of str,
                'storage_type': 'file' or 'database',
                'metadata': dict (optional, for DB categories with extra data)
            }
            
        Example:
            result = CategoryService.get_categories('projects', 'project_categories')
            # Returns: {
            #     'success': True,
            #     'categories': ['Marketing', 'Coding', 'Sales', ...],
            #     'storage_type': 'file'
            # }
        """
        try:
            config = get_category_config(module_key, category_key)
            
            if config['storage'] == 'database':
                return CategoryService._get_database_categories(config)
            else:
                return CategoryService._get_file_categories(config)
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'categories': []
            }
    
    
    @staticmethod
    def _get_database_categories(config):
        """Get categories from database table"""
        try:
            model_name = config['model']
            name_column = config['name_column']
            
            # Get the model class
            if model_name == 'EventType':
                model = EventType
            elif model_name == 'SpendingCategory':
                model = SpendingCategory
            else:
                raise ValueError(f"Unknown model: {model_name}")
            
            # Query all categories
            records = model.query.order_by(getattr(model, name_column)).all()
            
            # Extract just the names
            categories = [getattr(record, name_column) for record in records]
            
            # Include metadata if available
            metadata = {}
            if config.get('has_metadata'):
                for record in records:
                    metadata[getattr(record, name_column)] = {
                        'id': record.id,
                        'icon': getattr(record, 'icon', None),
                        'color': getattr(record, 'color', None),
                        'is_custom': getattr(record, 'is_custom', False),
                        'usage_count': getattr(record, 'usage_count', 0)
                    }
            
            return {
                'success': True,
                'categories': categories,
                'storage_type': 'database',
                'metadata': metadata if metadata else None
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Database error: {str(e)}",
                'categories': []
            }
    
    
    @staticmethod
    def _get_file_categories(config):
        """Get categories from Python constants file"""
        try:
            file_path = config['file_path']
            constant_name = config['constant_name']
            
            # Use FileHandler to read the constant
            categories = FileHandler.read_constant(file_path, constant_name)
            
            # Handle tuple format (value, display_name)
            if categories and isinstance(categories[0], tuple):
                # Extract just the values
                categories = [cat[0] if isinstance(cat, tuple) else cat for cat in categories]
            
            return {
                'success': True,
                'categories': categories,
                'storage_type': 'file',
                'file_path': file_path,
                'constant_name': constant_name
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"File read error: {str(e)}",
                'categories': []
            }
    
    
    @staticmethod
    def add_category(module_key, category_key, name):
        """
        Add a new category
        
        Args:
            module_key: Module identifier
            category_key: Category type
            name: Name of new category
            
        Returns:
            dict: {
                'success': bool,
                'message': str,
                'needs_restart': bool (only for file-based)
            }
        """
        try:
            # Validate name first
            is_valid, validation_msg = CategoryService._validate_category_name(name)
            if not is_valid:
                return {
                    'success': False,
                    'message': validation_msg
                }
            
            # Check for duplicates
            existing = CategoryService.get_categories(module_key, category_key)
            if existing['success']:
                # Case-insensitive check
                existing_lower = [cat.lower() for cat in existing['categories']]
                if name.lower() in existing_lower:
                    return {
                        'success': False,
                        'message': f'Category "{name}" already exists'
                    }
            
            # Get config and route to appropriate handler
            config = get_category_config(module_key, category_key)
            
            if config['storage'] == 'database':
                return CategoryService._add_database_category(config, name)
            else:
                return CategoryService._add_file_category(config, name)
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Error adding category: {str(e)}'
            }
    
    
    @staticmethod
    def _add_database_category(config, name):
        """Add category to database"""
        try:
            model_name = config['model']
            name_column = config['name_column']
            
            # Get the model class
            if model_name == 'EventType':
                model = EventType
                # EventType has special get_or_create method
                event_type = EventType.get_or_create(name)
                return {
                    'success': True,
                    'message': f'Event type "{name}" added successfully',
                    'needs_restart': False
                }
                
            elif model_name == 'SpendingCategory':
                model = SpendingCategory
                category = SpendingCategory(
                    name=name,
                    is_custom=True,
                    icon='📁',
                    color='#6ea8ff'
                )
                db.session.add(category)
                db.session.commit()
                
                return {
                    'success': True,
                    'message': f'Spending category "{name}" added successfully',
                    'needs_restart': False
                }
            else:
                raise ValueError(f"Unknown model: {model_name}")
                
        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'message': f'Database error: {str(e)}'
            }
    
    
    @staticmethod
    def _add_file_category(config, name):
        """Add category to constants file"""
        try:
            file_path = config['file_path']
            constant_name = config['constant_name']
            
            # Read current categories
            current = FileHandler.read_constant(file_path, constant_name)
            
            # Append new category
            current.append(name)
            
            # Write back to file
            FileHandler.write_constant(file_path, constant_name, current)
            
            return {
                'success': True,
                'message': f'Category "{name}" added to {constant_name}',
                'needs_restart': True,  # File changes require restart
                'file_path': file_path
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'File write error: {str(e)}'
            }
    
    
    @staticmethod
    def edit_category(module_key, category_key, old_name, new_name):
        """
        Edit an existing category name
        
        Args:
            module_key: Module identifier
            category_key: Category type
            old_name: Current name
            new_name: New name
            
        Returns:
            dict: {
                'success': bool,
                'message': str,
                'needs_restart': bool (only for file-based)
            }
        """
        try:
            # Validate new name
            is_valid, validation_msg = CategoryService._validate_category_name(new_name)
            if not is_valid:
                return {
                    'success': False,
                    'message': validation_msg
                }
            
            # Check if old name exists
            existing = CategoryService.get_categories(module_key, category_key)
            if existing['success'] and old_name not in existing['categories']:
                return {
                    'success': False,
                    'message': f'Category "{old_name}" not found'
                }
            
            # Check if new name already exists (and is different from old)
            if new_name.lower() != old_name.lower():
                existing_lower = [cat.lower() for cat in existing['categories']]
                if new_name.lower() in existing_lower:
                    return {
                        'success': False,
                        'message': f'Category "{new_name}" already exists'
                    }
            
            # Get config and route
            config = get_category_config(module_key, category_key)
            
            if config['storage'] == 'database':
                return CategoryService._edit_database_category(config, old_name, new_name)
            else:
                return CategoryService._edit_file_category(config, old_name, new_name)
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Error editing category: {str(e)}'
            }
    
    
    @staticmethod
    def _edit_database_category(config, old_name, new_name):
        """Edit category in database"""
        try:
            model_name = config['model']
            name_column = config['name_column']
            
            # Get the model class
            if model_name == 'EventType':
                model = EventType
            elif model_name == 'SpendingCategory':
                model = SpendingCategory
            else:
                raise ValueError(f"Unknown model: {model_name}")
            
            # Find and update the record
            record = model.query.filter_by(**{name_column: old_name}).first()
            if not record:
                return {
                    'success': False,
                    'message': f'Category "{old_name}" not found in database'
                }
            
            setattr(record, name_column, new_name)
            db.session.commit()
            
            return {
                'success': True,
                'message': f'Category renamed from "{old_name}" to "{new_name}"',
                'needs_restart': False
            }
            
        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'message': f'Database error: {str(e)}'
            }
    
    
    @staticmethod
    def _edit_file_category(config, old_name, new_name):
        """Edit category in constants file"""
        try:
            file_path = config['file_path']
            constant_name = config['constant_name']
            
            # Read current categories
            current = FileHandler.read_constant(file_path, constant_name)
            
            # Replace old name with new name
            if old_name in current:
                index = current.index(old_name)
                current[index] = new_name
            else:
                return {
                    'success': False,
                    'message': f'Category "{old_name}" not found in file'
                }
            
            # Write back
            FileHandler.write_constant(file_path, constant_name, current)
            
            return {
                'success': True,
                'message': f'Category renamed from "{old_name}" to "{new_name}"',
                'needs_restart': True,
                'file_path': file_path
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'File write error: {str(e)}'
            }
    
    
    @staticmethod
    def delete_category(module_key, category_key, name):
        """
        Delete a category (with safety checks)
        
        Args:
            module_key: Module identifier
            category_key: Category type
            name: Name of category to delete
            
        Returns:
            dict: {
                'success': bool,
                'message': str,
                'usage_count': int (if deletion blocked),
                'needs_restart': bool (only for file-based)
            }
        """
        try:
            # Check usage first - NEVER delete categories in use
            usage_count, usage_details = CategoryService.get_usage_count(
                module_key, category_key, name
            )
            
            if usage_count > 0:
                # Format usage details for message
                details = ', '.join([f"{count} in {table}" for table, count in usage_details])
                return {
                    'success': False,
                    'message': f'Cannot delete "{name}" - currently used by {usage_count} items ({details})',
                    'usage_count': usage_count,
                    'usage_details': usage_details
                }
            
            # Safe to delete
            config = get_category_config(module_key, category_key)
            
            if config['storage'] == 'database':
                return CategoryService._delete_database_category(config, name)
            else:
                return CategoryService._delete_file_category(config, name)
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Error deleting category: {str(e)}'
            }
    
    
    @staticmethod
    def _delete_database_category(config, name):
        """Delete category from database"""
        try:
            model_name = config['model']
            name_column = config['name_column']
            
            # Get the model class
            if model_name == 'EventType':
                model = EventType
            elif model_name == 'SpendingCategory':
                model = SpendingCategory
            else:
                raise ValueError(f"Unknown model: {model_name}")
            
            # Find and delete the record
            record = model.query.filter_by(**{name_column: name}).first()
            if not record:
                return {
                    'success': False,
                    'message': f'Category "{name}" not found in database'
                }
            
            db.session.delete(record)
            db.session.commit()
            
            return {
                'success': True,
                'message': f'Category "{name}" deleted successfully',
                'needs_restart': False
            }
            
        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'message': f'Database error: {str(e)}'
            }
    
    
    @staticmethod
    def _delete_file_category(config, name):
        """Delete category from constants file"""
        try:
            file_path = config['file_path']
            constant_name = config['constant_name']
            
            # Read current categories
            current = FileHandler.read_constant(file_path, constant_name)
            
            # Remove category
            if name in current:
                current.remove(name)
            else:
                return {
                    'success': False,
                    'message': f'Category "{name}" not found in file'
                }
            
            # Write back
            FileHandler.write_constant(file_path, constant_name, current)
            
            return {
                'success': True,
                'message': f'Category "{name}" deleted from {constant_name}',
                'needs_restart': True,
                'file_path': file_path
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'File write error: {str(e)}'
            }
    
    
    @staticmethod
    def get_usage_count(module_key, category_key, name):
        """
        Count how many items use this category
        
        Args:
            module_key: Module identifier
            category_key: Category type
            name: Category name to check
            
        Returns:
            tuple: (total_count: int, details: list of (table, count) tuples)
            
        Example:
            count, details = CategoryService.get_usage_count('equipment', 'equipment_categories', 'Auto')
            # Returns: (8, [('equipment', 8)])
        """
        try:
            config = get_category_config(module_key, category_key)
            usage_checks = config.get('usage_checks', [])
            
            total_count = 0
            details = []
            
            for check in usage_checks:
                table = check['table']
                column = check['column']
                is_fk = check.get('is_fk', False)
                
                if is_fk:
                    # Foreign key relationship - need to look up category ID first
                    # Get the model to find the category record
                    model_name = config['model']
                    name_column = config['name_column']
                    id_column = config['id_column']
                    
                    # Get the model class
                    if model_name == 'EventType':
                        model = EventType
                    elif model_name == 'SpendingCategory':
                        model = SpendingCategory
                    else:
                        # Unknown model, skip this check
                        continue
                    
                    # Find the category record by name
                    category_record = model.query.filter_by(**{name_column: name}).first()
                    
                    if category_record:
                        category_id = getattr(category_record, id_column)
                        
                        # Now count foreign key references using the ID
                        query = text(f"SELECT COUNT(*) FROM {table} WHERE {column} = :category_id")
                        result = db.session.execute(query, {'category_id': category_id})
                        count = result.scalar() or 0
                        
                        if count > 0:
                            details.append((check.get('label', table), count))
                            total_count += count
                    else:
                        # Category not found in database, skip
                        continue
                        
                else:
                    # Direct string comparison (for non-FK columns)
                    query = text(f"SELECT COUNT(*) FROM {table} WHERE {column} = :name")
                    result = db.session.execute(query, {'name': name})
                    count = result.scalar() or 0
                    
                    if count > 0:
                        details.append((check.get('label', table), count))
                        total_count += count
            
            return total_count, details
            
        except Exception as e:
            # If we can't count usage, be safe and return a high number to prevent deletion
            return 999, [('error', f'Could not check usage: {str(e)}')]
    
    
    @staticmethod
    def _validate_category_name(name):
        """
        Validate category name for safety
        
        Args:
            name: Proposed category name
            
        Returns:
            tuple: (is_valid: bool, message: str)
        """
        # Check length
        if not name or len(name.strip()) < 2:
            return False, "Category name must be at least 2 characters"
        
        if len(name) > 50:
            return False, "Category name must be 50 characters or less"
        
        # Check for dangerous characters that could break Python or SQL
        forbidden_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', "'", '\n', '\t', ';', '--']
        for char in forbidden_chars:
            if char in name:
                return False, f'Category name cannot contain: {char}'
        
        # Must start with letter or number
        if not name[0].isalnum():
            return False, "Category name must start with a letter or number"
        
        # No leading/trailing spaces
        if name != name.strip():
            return False, "Category name cannot have leading or trailing spaces"
        
        return True, "Valid"


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_all_modules_with_categories():
    """
    Get list of all modules that have categories
    
    Returns:
        list: Dicts with module info and category counts
    """
    modules = []
    
    for module_key, module_config in CATEGORY_REGISTRY.items():
        category_count = len(module_config['categories'])
        
        modules.append({
            'key': module_key,
            'name': module_config['display_name'],
            'icon': module_config['icon'],
            'description': module_config.get('description', ''),
            'category_count': category_count
        })
    
    return modules


def get_category_summary(module_key, category_key):
    """
    Get complete summary of a category including usage stats
    
    Returns:
        dict: Complete category information
    """
    config = get_category_config(module_key, category_key)
    result = CategoryService.get_categories(module_key, category_key)
    
    if not result['success']:
        return result
    
    # Add usage counts for each category
    categories_with_usage = []
    for cat_name in result['categories']:
        usage_count, usage_details = CategoryService.get_usage_count(
            module_key, category_key, cat_name
        )
        
        categories_with_usage.append({
            'name': cat_name,
            'usage_count': usage_count,
            'usage_details': usage_details,
            'can_delete': usage_count == 0
        })
    
    return {
        'success': True,
        'label': config['label'],
        'description': config.get('description', ''),
        'storage_type': result['storage_type'],
        'categories': categories_with_usage,
        'metadata': result.get('metadata')
    }