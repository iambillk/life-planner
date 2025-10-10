# modules/admin_system/routes.py
"""
Admin System Health Routes
Complete application monitoring and management

FILE: modules/admin_system/routes.py
VERSION: 2.0.0
UPDATED: 2025-01-10
AUTHOR: Billas

CHANGELOG:
----------
v2.0.0 (2025-01-10)
- MAJOR UPDATE: Integrated CategoryService for unified category management
- Added new routes for category CRUD operations
- Added API endpoints for category management
- Improved category_manager view with usage stats
- Added backup management routes
- Better error handling and user feedback

v1.0.0 (2025-01-10)
- Main dashboard with system health overview
- Database explorer with table stats
- Category manager for viewing constants
- Storage browser for file management
- Activity timeline
- Real-time API endpoints
"""

from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from datetime import datetime, timedelta
from sqlalchemy import func, text, inspect
from collections import defaultdict
import os

from models.base import db
from . import admin_system_bp

# Import our new services
from .category_service import CategoryService, get_all_modules_with_categories, get_category_summary
from .category_registry import CATEGORY_REGISTRY, get_module_categories
from .file_handler import FileHandler

# Import utilities
from .utils import (
    get_database_stats,
    get_table_sizes,
    get_storage_stats,
    get_module_activity,
    get_recent_activity,
    format_bytes
)

# Import models for health checks
from models import (
    Equipment, MaintenanceRecord, TCHProject, PersonalProject,
    CalendarEvent, WeightEntry, Transaction, Property,
    TodoList, Goal, Contact, Company
)


# =============================================================================
# DASHBOARD
# =============================================================================

@admin_system_bp.route('/')
@admin_system_bp.route('/dashboard')
def dashboard():
    """
    Main System Health Dashboard
    The cockpit view of your entire application
    """
    
    # Database Stats
    db_stats = get_database_stats()
    
    # Table breakdown with record counts
    table_stats = get_table_sizes()
    
    # Storage stats
    storage_stats = get_storage_stats()
    
    # Module activity (last 30 days)
    module_activity = get_module_activity()
    
    # Recent activity timeline
    recent_activity = get_recent_activity(limit=15)
    
    # System health checks
    health_checks = []
    
    # Check if weight logged today
    today = datetime.now().date()
    weight_today = WeightEntry.query.filter_by(date=today).first()
    health_checks.append({
        'module': 'Health',
        'status': 'success' if weight_today else 'warning',
        'message': 'Weight logged today' if weight_today else 'No weight entry today',
        'icon': '✅' if weight_today else '⚠️'
    })
    
    # Check for overdue projects
    overdue_projects = TCHProject.query.filter(
        TCHProject.deadline < today,
        TCHProject.status.in_(['active', 'planning'])
    ).count()
    health_checks.append({
        'module': 'Projects',
        'status': 'error' if overdue_projects > 0 else 'success',
        'message': f'{overdue_projects} overdue projects' if overdue_projects > 0 else 'No overdue projects',
        'icon': '❌' if overdue_projects > 0 else '✅'
    })
    
    # Check for stale equipment (no maintenance in 90 days)
    cutoff_90d = datetime.now() - timedelta(days=90)
    stale_equipment = []
    for eq in Equipment.query.all():
        last_maintenance = MaintenanceRecord.query.filter_by(
            equipment_id=eq.id
        ).order_by(MaintenanceRecord.service_date.desc()).first()
        
        if last_maintenance and last_maintenance.service_date < cutoff_90d.date():
            stale_equipment.append(eq)
        elif not last_maintenance:
            stale_equipment.append(eq)
    
    health_checks.append({
        'module': 'Equipment',
        'status': 'warning' if len(stale_equipment) > 0 else 'success',
        'message': f'{len(stale_equipment)} items need maintenance' if len(stale_equipment) > 0 else 'All equipment up to date',
        'icon': '⚠️' if len(stale_equipment) > 0 else '✅'
    })
    
    # Check for recent financial activity
    last_transaction = Transaction.query.order_by(
        Transaction.date.desc()
    ).first()
    
    if last_transaction:
        days_since = (today - last_transaction.date).days
        health_checks.append({
            'module': 'Financial',
            'status': 'warning' if days_since > 7 else 'success',
            'message': f'Last transaction {days_since} days ago' if days_since > 0 else 'Transaction logged today',
            'icon': '⚠️' if days_since > 7 else '✅'
        })
    
    return render_template('admin_system/dashboard.html',
                         db_stats=db_stats,
                         table_stats=table_stats[:10],  # Top 10 tables
                         storage_stats=storage_stats,
                         module_activity=module_activity,
                         recent_activity=recent_activity,
                         health_checks=health_checks,
                         active='admin_system')


# =============================================================================
# DATABASE EXPLORER
# =============================================================================

@admin_system_bp.route('/database')
def database_explorer():
    """
    Database Explorer
    Browse all tables, view schemas, see row counts
    """
    
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    table_info = []
    for table_name in sorted(tables):
        # Get row count
        try:
            result = db.session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            row_count = result.scalar()
        except:
            row_count = 0
        
        # Get columns
        columns = inspector.get_columns(table_name)
        
        # Format column info
        column_details = []
        for col in columns:
            column_details.append({
                'name': col['name'],
                'type': str(col['type']),
                'nullable': col['nullable'],
                'primary_key': col.get('primary_key', False)
            })
        
        table_info.append({
            'name': table_name,
            'row_count': row_count,
            'column_count': len(columns),
            'columns': column_details
        })
    
    # Sort by row count descending
    table_info.sort(key=lambda x: x['row_count'], reverse=True)
    
    return render_template('admin_system/database.html',
                         tables=table_info,
                         active='admin_system')


# =============================================================================
# CATEGORY MANAGER - NEW IMPLEMENTATION
# =============================================================================

@admin_system_bp.route('/categories')
def category_manager():
    """
    Category Manager - Main View
    Shows all modules and their categories with usage stats
    Uses new CategoryService for unified management
    """
    
    # Get all modules from registry
    modules = get_all_modules_with_categories()
    
    # Build category data for each module
    module_data = []
    
    for module in modules:
        module_key = module['key']
        module_config = CATEGORY_REGISTRY[module_key]
        
        # Get all category types for this module
        category_types = []
        for cat_key, cat_config in module_config['categories'].items():
            
            # Get categories and usage
            summary = get_category_summary(module_key, cat_key)
            
            if summary['success']:
                category_types.append({
                    'key': cat_key,
                    'label': cat_config['label'],
                    'description': cat_config.get('description', ''),
                    'storage_type': summary['storage_type'],
                    'categories': summary['categories'],
                    'total_count': len(summary['categories']),
                    'used_count': sum(1 for c in summary['categories'] if c['usage_count'] > 0)
                })
        
        module_data.append({
            'key': module_key,
            'name': module['name'],
            'icon': module['icon'],
            'description': module['description'],
            'category_types': category_types
        })
    
    return render_template('admin_system/categories_new.html',
                         modules=module_data,
                         active='admin_system')


@admin_system_bp.route('/categories/<module_key>/<category_key>')
def category_detail(module_key, category_key):
    """
    Detailed view of a specific category type
    Shows all categories with usage stats and management options
    """
    
    try:
        # Get category summary
        summary = get_category_summary(module_key, category_key)
        
        if not summary['success']:
            flash(f"Error loading categories: {summary.get('message', 'Unknown error')}", 'error')
            return redirect(url_for('admin_system.category_manager'))
        
        # Get module info
        module_config = CATEGORY_REGISTRY[module_key]
        category_config = module_config['categories'][category_key]
        
        return render_template('admin_system/category_detail.html',
                             module_key=module_key,
                             module_name=module_config['display_name'],
                             module_icon=module_config['icon'],
                             category_key=category_key,
                             category_label=category_config['label'],
                             category_description=category_config.get('description', ''),
                             storage_type=summary['storage_type'],
                             categories=summary['categories'],
                             metadata=summary.get('metadata'),
                             active='admin_system')
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin_system.category_manager'))


# =============================================================================
# CATEGORY CRUD OPERATIONS
# =============================================================================

@admin_system_bp.route('/categories/<module_key>/<category_key>/add', methods=['POST'])
def add_category(module_key, category_key):
    """
    Add a new category
    Works for both file-based and database-based categories
    """
    
    category_name = request.form.get('name', '').strip()
    
    if not category_name:
        flash('Category name is required', 'error')
        return redirect(url_for('admin_system.category_detail', 
                               module_key=module_key, category_key=category_key))
    
    # Use CategoryService to add
    result = CategoryService.add_category(module_key, category_key, category_name)
    
    if result['success']:
        if result.get('needs_restart'):
            flash(f"✅ Category '{category_name}' added! ⚠️ Restart application to see changes.", 'warning')
        else:
            flash(f"✅ Category '{category_name}' added successfully!", 'success')
    else:
        flash(f"❌ {result['message']}", 'error')
    
    return redirect(url_for('admin_system.category_detail', 
                           module_key=module_key, category_key=category_key))


@admin_system_bp.route('/categories/<module_key>/<category_key>/edit', methods=['POST'])
def edit_category(module_key, category_key):
    """
    Edit an existing category name
    """
    
    old_name = request.form.get('old_name', '').strip()
    new_name = request.form.get('new_name', '').strip()
    
    if not old_name or not new_name:
        flash('Both old and new names are required', 'error')
        return redirect(url_for('admin_system.category_detail', 
                               module_key=module_key, category_key=category_key))
    
    # Use CategoryService to edit
    result = CategoryService.edit_category(module_key, category_key, old_name, new_name)
    
    if result['success']:
        if result.get('needs_restart'):
            flash(f"✅ Category renamed! ⚠️ Restart application to see changes.", 'warning')
        else:
            flash(f"✅ Category '{old_name}' renamed to '{new_name}'!", 'success')
    else:
        flash(f"❌ {result['message']}", 'error')
    
    return redirect(url_for('admin_system.category_detail', 
                           module_key=module_key, category_key=category_key))


@admin_system_bp.route('/categories/<module_key>/<category_key>/delete', methods=['POST'])
def delete_category(module_key, category_key):
    """
    Delete a category (with safety checks)
    """
    
    category_name = request.form.get('name', '').strip()
    
    if not category_name:
        flash('Category name is required', 'error')
        return redirect(url_for('admin_system.category_detail', 
                               module_key=module_key, category_key=category_key))
    
    # Use CategoryService to delete
    result = CategoryService.delete_category(module_key, category_key, category_name)
    
    if result['success']:
        if result.get('needs_restart'):
            flash(f"✅ Category '{category_name}' deleted! ⚠️ Restart application to see changes.", 'warning')
        else:
            flash(f"✅ Category '{category_name}' deleted successfully!", 'success')
    else:
        flash(f"❌ {result['message']}", 'error')
    
    return redirect(url_for('admin_system.category_detail', 
                           module_key=module_key, category_key=category_key))


# =============================================================================
# BACKUP MANAGEMENT
# =============================================================================

@admin_system_bp.route('/categories/backups/<path:file_path>')
def view_backups(file_path):
    """
    View available backups for a constants file
    """
    
    try:
        backups = FileHandler.list_backups(file_path)
        
        return render_template('admin_system/backups.html',
                             file_path=file_path,
                             backups=backups,
                             active='admin_system')
        
    except Exception as e:
        flash(f'Error listing backups: {str(e)}', 'error')
        return redirect(url_for('admin_system.category_manager'))


@admin_system_bp.route('/categories/backups/restore', methods=['POST'])
def restore_backup():
    """
    Restore a file from backup
    """
    
    backup_path = request.form.get('backup_path')
    
    if not backup_path:
        flash('Backup path is required', 'error')
        return redirect(url_for('admin_system.category_manager'))
    
    # Restore using FileHandler
    result = FileHandler.restore_backup(backup_path)
    
    if result['success']:
        flash(f"✅ {result['message']} ⚠️ Restart application to see changes.", 'warning')
    else:
        flash(f"❌ {result['message']}", 'error')
    
    return redirect(url_for('admin_system.category_manager'))


# =============================================================================
# API ENDPOINTS
# =============================================================================

@admin_system_bp.route('/api/categories/<module_key>/<category_key>')
def api_get_categories(module_key, category_key):
    """
    API endpoint to get categories
    Returns JSON for AJAX requests
    """
    
    try:
        result = CategoryService.get_categories(module_key, category_key)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@admin_system_bp.route('/api/categories/<module_key>/<category_key>/usage/<name>')
def api_get_usage(module_key, category_key, name):
    """
    API endpoint to get usage count for a specific category
    """
    
    try:
        count, details = CategoryService.get_usage_count(module_key, category_key, name)
        return jsonify({
            'success': True,
            'category': name,
            'usage_count': count,
            'usage_details': [{'table': table, 'count': cnt} for table, cnt in details]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


# =============================================================================
# STORAGE BROWSER
# =============================================================================

@admin_system_bp.route('/storage')
def storage_browser():
    """
    Storage Browser
    View all uploaded files, identify orphans, bulk cleanup
    """
    
    upload_folder = current_app.config['UPLOAD_FOLDER']
    
    # Scan all upload directories
    file_inventory = []
    
    subdirs = [
        'equipment_profiles',
        'maintenance_photos',
        'property_profiles',
        'property_maintenance',
        'personal_project_files',
        'receipts',
        'vault_files',
        'admin_tools'
    ]
    
    for subdir in subdirs:
        dir_path = os.path.join(upload_folder, subdir)
        if not os.path.exists(dir_path):
            continue
        
        for root, dirs, files in os.walk(dir_path):
            for filename in files:
                filepath = os.path.join(root, filename)
                try:
                    file_size = os.path.getsize(filepath)
                    file_modified = datetime.fromtimestamp(os.path.getmtime(filepath))
                    
                    file_inventory.append({
                        'name': filename,
                        'category': subdir,
                        'size': file_size,
                        'size_formatted': format_bytes(file_size),
                        'modified': file_modified,
                        'path': filepath.replace(upload_folder, ''),
                        'ext': os.path.splitext(filename)[1]
                    })
                except:
                    pass
    
    # Sort by size descending
    file_inventory.sort(key=lambda x: x['size'], reverse=True)
    
    # Calculate totals
    total_files = len(file_inventory)
    total_size = sum(f['size'] for f in file_inventory)
    
    # Group by category
    by_category = defaultdict(lambda: {'count': 0, 'size': 0})
    for f in file_inventory:
        by_category[f['category']]['count'] += 1
        by_category[f['category']]['size'] += f['size']
    
    storage_summary = {
        'total_files': total_files,
        'total_size': format_bytes(total_size),
        'by_category': {k: {'count': v['count'], 'size': format_bytes(v['size'])} 
                        for k, v in by_category.items()}
    }
    
    return render_template('admin_system/storage.html',
                         files=file_inventory[:500],  # Limit display to 500
                         storage_summary=storage_summary,
                         active='admin_system')


# =============================================================================
# ACTIVITY TIMELINE
# =============================================================================

@admin_system_bp.route('/activity')
def activity_timeline():
    """
    Activity Timeline
    Chronological view of all system activity
    """
    
    # Get filter parameters
    module_filter = request.args.get('module', 'all')
    days = int(request.args.get('days', 7))
    
    # Get activity
    activities = get_recent_activity(limit=100)
    
    # Filter by module if specified
    if module_filter != 'all':
        activities = [a for a in activities if a['module'].lower() == module_filter.lower()]
    
    # Filter by days
    cutoff = datetime.now() - timedelta(days=days)
    activities = [a for a in activities if a['timestamp'] >= cutoff]
    
    # Get available modules for filter
    all_modules = sorted(set(a['module'] for a in get_recent_activity(limit=100)))
    
    return render_template('admin_system/activity.html',
                         activities=activities,
                         module_filter=module_filter,
                         days=days,
                         all_modules=all_modules,
                         active='admin_system')


# =============================================================================
# REAL-TIME API ENDPOINTS
# =============================================================================

@admin_system_bp.route('/api/stats')
def api_stats():
    """Real-time stats API for dashboard refresh"""
    db_stats = get_database_stats()
    storage_stats = get_storage_stats()
    module_activity = get_module_activity()
    
    return jsonify({
        'success': True,
        'database': db_stats,
        'storage': storage_stats,
        'modules': module_activity,
        'timestamp': datetime.now().isoformat()
    })


@admin_system_bp.route('/api/table/<table_name>')
def api_table_details(table_name):
    """Get detailed info about a specific table"""
    inspector = inspect(db.engine)
    
    try:
        # Get row count
        result = db.session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        row_count = result.scalar()
        
        # Get columns
        columns = inspector.get_columns(table_name)
        
        # Get recent records (last 10)
        recent = db.session.execute(
            text(f"SELECT * FROM {table_name} ORDER BY rowid DESC LIMIT 10")
        ).fetchall()
        
        return jsonify({
            'success': True,
            'table': table_name,
            'row_count': row_count,
            'columns': [{'name': c['name'], 'type': str(c['type'])} for c in columns],
            'recent_count': len(recent)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400