# modules/admin_system/file_handler.py
"""
File Handler - Safe Python Constants File Editor
=================================================

This module provides safe read/write operations for Python constants files.
Uses AST (Abstract Syntax Tree) parsing to understand Python code structure
and modify only the specific constants we want to change.

FILE: modules/admin_system/file_handler.py
VERSION: 1.0.0
CREATED: 2025-01-10
AUTHOR: Billas

CHANGELOG:
----------
v1.0.0 (2025-01-10)
- Initial file handler creation
- AST-based parsing for safe file reading
- Automatic backup before any write operation
- Support for simple list constants (strings)
- Support for tuple constants (value, display_name)
- Preserves file formatting and comments where possible
- Backup rotation (keeps last 20 backups)

SAFETY FEATURES:
----------------
1. Always creates backup before writing
2. Validates Python syntax before saving
3. Only modifies specific constants, leaves rest of file intact
4. Rollback capability via backup restoration
5. Keeps audit trail of all changes

SUPPORTED CONSTANT FORMATS:
---------------------------
1. Simple string lists:
   CATEGORIES = ['Category1', 'Category2', 'Category3']

2. Tuple lists (value, display):
   STATUSES = [
       ('planning', 'Planning'),
       ('active', 'Active')
   ]

3. Multi-line formatted lists (preserves formatting)

LIMITATIONS:
------------
- Only works with simple list constants
- Comments inside the list may be lost on write
- Complex expressions not supported
- Dictionary constants not supported (yet)

USAGE EXAMPLE:
--------------
from modules.admin_system.file_handler import FileHandler

# Read a constant
categories = FileHandler.read_constant('modules/projects/constants.py', 'PROJECT_CATEGORIES')

# Modify it
categories.append('New Category')

# Write it back (creates backup automatically)
FileHandler.write_constant('modules/projects/constants.py', 'PROJECT_CATEGORIES', categories)

# List available backups
backups = FileHandler.list_backups('modules/projects/constants.py')

# Restore from backup if needed
FileHandler.restore_backup(backup_path)
"""

import ast
import os
import shutil
from datetime import datetime
from pathlib import Path
import re


# =============================================================================
# FILE HANDLER - MAIN CLASS
# =============================================================================

class FileHandler:
    """
    Safe handler for reading/writing Python constants files
    Uses AST for parsing and validation
    """
    
    # Maximum number of backups to keep per file
    MAX_BACKUPS = 20
    
    
    @staticmethod
    def read_constant(file_path, constant_name):
        """
        Read a list constant from a Python file
        
        Args:
            file_path: Path to Python file (e.g., 'modules/projects/constants.py')
            constant_name: Name of constant to read (e.g., 'PROJECT_CATEGORIES')
            
        Returns:
            list: Values from the constant
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If constant not found or not a list
            SyntaxError: If file has invalid Python syntax
            
        Example:
            categories = FileHandler.read_constant('modules/projects/constants.py', 'PROJECT_CATEGORIES')
            # Returns: ['Marketing', 'Coding', 'Sales', ...]
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse into AST
            tree = ast.parse(content, filename=file_path)
            
            # Find the constant assignment
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    # Check if this is the constant we're looking for
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == constant_name:
                            # Found it! Extract the value
                            return FileHandler._extract_list_value(node.value)
            
            # Constant not found
            raise ValueError(f"Constant '{constant_name}' not found in {file_path}")
            
        except SyntaxError as e:
            raise SyntaxError(f"Invalid Python syntax in {file_path}: {str(e)}")
    
    
    @staticmethod
    def _extract_list_value(node):
        """
        Extract values from an AST List node
        Handles both simple strings and tuples
        
        Args:
            node: AST node (should be ast.List)
            
        Returns:
            list: Extracted values
        """
        if not isinstance(node, ast.List):
            raise ValueError("Constant is not a list")
        
        values = []
        for element in node.elts:
            if isinstance(element, ast.Constant):
                # Simple string value
                values.append(element.value)
            elif isinstance(element, ast.Str):
                # Old-style string (Python < 3.8)
                values.append(element.s)
            elif isinstance(element, ast.Tuple):
                # Tuple like ('value', 'Display Name')
                tuple_values = []
                for item in element.elts:
                    if isinstance(item, ast.Constant):
                        tuple_values.append(item.value)
                    elif isinstance(item, ast.Str):
                        tuple_values.append(item.s)
                values.append(tuple(tuple_values))
            else:
                # Unknown type - try to get value anyway
                try:
                    values.append(ast.literal_eval(element))
                except:
                    pass
        
        return values
    
    
    @staticmethod
    def write_constant(file_path, constant_name, values):
        """
        Write a list constant to a Python file
        Creates backup before modifying
        
        Args:
            file_path: Path to Python file
            constant_name: Name of constant to write
            values: List of values to write
            
        Returns:
            dict: {
                'success': bool,
                'backup_path': str,
                'message': str
            }
            
        Example:
            result = FileHandler.write_constant(
                'modules/projects/constants.py',
                'PROJECT_CATEGORIES',
                ['Marketing', 'Coding', 'Sales', 'Consulting']
            )
        """
        if not os.path.exists(file_path):
            return {
                'success': False,
                'message': f"File not found: {file_path}"
            }
        
        try:
            # Step 1: Create backup
            backup_path = FileHandler.create_backup(file_path)
            
            # Step 2: Read current file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Step 3: Find and replace the constant
            new_content = FileHandler._replace_constant_in_content(
                content, constant_name, values
            )
            
            # Step 4: Validate new content (make sure it's valid Python)
            try:
                ast.parse(new_content)
            except SyntaxError as e:
                return {
                    'success': False,
                    'message': f"Generated invalid Python syntax: {str(e)}",
                    'backup_path': backup_path
                }
            
            # Step 5: Write new content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return {
                'success': True,
                'backup_path': backup_path,
                'message': f'Successfully updated {constant_name} in {file_path}'
            }
            
        except Exception as e:
            # Try to restore from backup if write failed
            if 'backup_path' in locals() and os.path.exists(backup_path):
                try:
                    shutil.copy2(backup_path, file_path)
                except:
                    pass
            
            return {
                'success': False,
                'message': f"Error writing file: {str(e)}"
            }
    
    
    @staticmethod
    def _replace_constant_in_content(content, constant_name, values):
        """
        Replace a constant definition in file content
        Attempts to preserve formatting
        
        Args:
            content: Full file content as string
            constant_name: Constant to replace
            values: New values
            
        Returns:
            str: Modified content
        """
        # Format the new list
        new_list = FileHandler._format_list(values)
        
        # Pattern to match the constant assignment
        # Matches: CONSTANT_NAME = [ ... ]
        # Handles multi-line lists
        pattern = rf'^{re.escape(constant_name)}\s*=\s*\[.*?\]'
        
        # Try to find and replace
        # Use MULTILINE and DOTALL flags to match across lines
        new_content = re.sub(
            pattern,
            f'{constant_name} = {new_list}',
            content,
            count=1,
            flags=re.MULTILINE | re.DOTALL
        )
        
        # Check if replacement happened
        if new_content == content:
            # Pattern didn't match - might be formatted differently
            # Fall back to line-by-line search
            lines = content.split('\n')
            in_constant = False
            start_line = -1
            bracket_count = 0
            
            for i, line in enumerate(lines):
                if not in_constant and constant_name in line and '=' in line:
                    in_constant = True
                    start_line = i
                    # Count brackets on this line
                    bracket_count += line.count('[') - line.count(']')
                    if bracket_count == 0:
                        # Single line constant
                        lines[i] = f'{constant_name} = {new_list}'
                        break
                elif in_constant:
                    bracket_count += line.count('[') - line.count(']')
                    if bracket_count == 0:
                        # End of constant - replace entire block
                        lines[start_line:i+1] = [f'{constant_name} = {new_list}']
                        break
            
            new_content = '\n'.join(lines)
        
        return new_content
    
    
    @staticmethod
    def _format_list(values, indent=4):
        """
        Format a list of values as Python code
        Creates clean, readable list format
        
        Args:
            values: List of values (strings or tuples)
            indent: Spaces for indentation
            
        Returns:
            str: Formatted list string
        """
        if not values:
            return '[]'
        
        # Check if values are tuples or simple strings
        has_tuples = any(isinstance(v, tuple) for v in values)
        
        if has_tuples:
            # Format tuples
            formatted_items = []
            for v in values:
                if isinstance(v, tuple):
                    # Format as ('value', 'Display')
                    tuple_str = '(' + ', '.join(f"'{item}'" for item in v) + ')'
                    formatted_items.append(tuple_str)
                else:
                    formatted_items.append(f"'{v}'")
        else:
            # Simple strings
            formatted_items = [f"'{v}'" for v in values]
        
        # Short list (< 5 items) - single line
        if len(formatted_items) <= 4 and not has_tuples:
            return '[' + ', '.join(formatted_items) + ']'
        
        # Long list - multi-line with proper indentation
        indent_str = ' ' * indent
        items_str = ',\n'.join(f'{indent_str}{item}' for item in formatted_items)
        
        return f'[\n{items_str}\n]'
    
    
    @staticmethod
    def create_backup(file_path):
        """
        Create timestamped backup of file
        
        Args:
            file_path: Path to file to backup
            
        Returns:
            str: Path to backup file
            
        Example:
            backup_path = FileHandler.create_backup('modules/projects/constants.py')
            # Returns: 'modules/projects/constants.py.backup.20250110_143022'
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"{file_path}.backup.{timestamp}"
        
        # Copy file
        shutil.copy2(file_path, backup_path)
        
        # Clean up old backups (keep only last MAX_BACKUPS)
        FileHandler._cleanup_old_backups(file_path)
        
        return backup_path
    
    
    @staticmethod
    def _cleanup_old_backups(file_path):
        """
        Keep only the most recent MAX_BACKUPS backup files
        
        Args:
            file_path: Original file path to find backups for
        """
        # Find all backup files
        directory = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        pattern = f"{filename}.backup.*"
        
        backup_files = []
        for f in os.listdir(directory) if directory else os.listdir('.'):
            if f.startswith(f"{filename}.backup."):
                backup_path = os.path.join(directory, f) if directory else f
                backup_files.append({
                    'path': backup_path,
                    'mtime': os.path.getmtime(backup_path)
                })
        
        # Sort by modification time (newest first)
        backup_files.sort(key=lambda x: x['mtime'], reverse=True)
        
        # Delete old backups beyond MAX_BACKUPS
        for backup_file in backup_files[FileHandler.MAX_BACKUPS:]:
            try:
                os.remove(backup_file['path'])
            except:
                pass  # Ignore errors during cleanup
    
    
    @staticmethod
    def list_backups(file_path):
        """
        List all backup files for a given file
        
        Args:
            file_path: Original file path
            
        Returns:
            list: List of dicts with backup info:
                [{
                    'path': str,
                    'timestamp': str,
                    'size': int,
                    'created': datetime
                }, ...]
                
        Example:
            backups = FileHandler.list_backups('modules/projects/constants.py')
            for backup in backups:
                print(f"{backup['timestamp']} - {backup['size']} bytes")
        """
        directory = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        
        backup_files = []
        search_dir = directory if directory else '.'
        
        for f in os.listdir(search_dir):
            if f.startswith(f"{filename}.backup."):
                backup_path = os.path.join(directory, f) if directory else f
                
                # Extract timestamp from filename
                timestamp_str = f.split('.backup.')[1] if '.backup.' in f else ''
                
                # Get file info
                stat = os.stat(backup_path)
                
                backup_files.append({
                    'path': backup_path,
                    'timestamp': timestamp_str,
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_mtime),
                    'filename': f
                })
        
        # Sort by creation time (newest first)
        backup_files.sort(key=lambda x: x['created'], reverse=True)
        
        return backup_files
    
    
    @staticmethod
    def restore_backup(backup_path, target_path=None):
        """
        Restore a file from backup
        
        Args:
            backup_path: Path to backup file
            target_path: Where to restore (default: original file location)
            
        Returns:
            dict: {
                'success': bool,
                'message': str
            }
            
        Example:
            result = FileHandler.restore_backup(
                'modules/projects/constants.py.backup.20250110_143022'
            )
        """
        if not os.path.exists(backup_path):
            return {
                'success': False,
                'message': f'Backup file not found: {backup_path}'
            }
        
        try:
            # Determine target path
            if target_path is None:
                # Remove .backup.timestamp from filename
                target_path = re.sub(r'\.backup\.\d{8}_\d{6}$', '', backup_path)
            
            # Create a backup of current file before restoring
            if os.path.exists(target_path):
                current_backup = FileHandler.create_backup(target_path)
            
            # Restore from backup
            shutil.copy2(backup_path, target_path)
            
            return {
                'success': True,
                'message': f'Successfully restored {target_path} from backup'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error restoring backup: {str(e)}'
            }
    
    
    @staticmethod
    def validate_file(file_path):
        """
        Validate that a file contains valid Python syntax
        
        Args:
            file_path: Path to Python file
            
        Returns:
            dict: {
                'valid': bool,
                'message': str,
                'errors': list (if invalid)
            }
        """
        if not os.path.exists(file_path):
            return {
                'valid': False,
                'message': f'File not found: {file_path}'
            }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Try to parse
            ast.parse(content, filename=file_path)
            
            return {
                'valid': True,
                'message': 'File contains valid Python syntax'
            }
            
        except SyntaxError as e:
            return {
                'valid': False,
                'message': f'Syntax error: {str(e)}',
                'errors': [{
                    'line': e.lineno,
                    'column': e.offset,
                    'message': e.msg
                }]
            }
        except Exception as e:
            return {
                'valid': False,
                'message': f'Error reading file: {str(e)}'
            }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_file_info(file_path):
    """
    Get information about a constants file
    
    Returns:
        dict: File metadata and statistics
    """
    if not os.path.exists(file_path):
        return {'exists': False}
    
    stat = os.stat(file_path)
    
    # Count lines
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Count constants
    constant_count = len([line for line in lines if '=' in line and not line.strip().startswith('#')])
    
    return {
        'exists': True,
        'path': file_path,
        'size': stat.st_size,
        'modified': datetime.fromtimestamp(stat.st_mtime),
        'line_count': len(lines),
        'constant_count': constant_count,
        'backup_count': len(FileHandler.list_backups(file_path))
    }