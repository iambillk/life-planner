# modules/admin_system/routes.py
"""
Admin System Health Routes
Complete application monitoring and management

CHANGELOG:
v1.0.0 (2025-01-10)
- Main dashboard with system health overview
- Database explorer with table stats
- Category manager for editing constants
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
from .utils import (
    get_database_stats,
    get_table_sizes,
    get_storage_stats,
    get_module_activity,
    get_recent_activity,
    format_bytes
)

# Import all models
from models import (
    Equipment, MaintenanceRecord, TCHProject, PersonalProject,
    CalendarEvent, WeightEntry, Transaction, Property,
    TodoList, Goal, Contact, Company
)


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


@admin_system_bp.route('/categories')
def category_manager():
    """
    Category Manager
    View all category constants across modules
    """
    
    # Gather all categories from different modules
    from modules.projects.constants import PROJECT_CATEGORIES as TCH_CATEGORIES
    from modules.persprojects.constants import PERSONAL_PROJECT_CATEGORIES
    from modules.equipment.constants import EQUIPMENT_CATEGORIES
    from modules.realestate.constants import PROPERTY_TYPES, MAINTENANCE_CATEGORIES
    from models.daily_planner import EventType
    from models.financial import SpendingCategory
    
    # Network categories
    NETWORK_ROLES = [
        "NAS", "Switch", "Router", "AP", "Server", "IoT", "UPS", "Camera",
        "Printer", "IPS", "Workstation", "Hypervisor"
    ]
    NETWORK_STATUS = ["active", "retired", "lab", "spare"]
    NETWORK_LOCATIONS = [
        "Bedroom", "Closet", "Server Rack", "Upstairs Den", "Music Room",
        "Pool Room", "Garage", "Kids Game Desk", "Front Room",
        "Barn", "TCH SFJ"
    ]
    
    # Get event types from database
    event_types = [et.type_name for et in EventType.query.order_by(EventType.type_name).all()]
    event_type_usage = {et.type_name: et.usage_count for et in EventType.query.all()}
    
    # Get spending categories from database
    spending_cats = SpendingCategory.query.order_by(SpendingCategory.name).all()
    spending_cat_names = [cat.name for cat in spending_cats]
    spending_cat_usage = {cat.name: cat.usage_count for cat in spending_cats}
    
    # Get usage stats for each category
    categories = {
        'TCH Projects': {
            'category_list': TCH_CATEGORIES,
            'usage': _get_category_usage('tch_projects', 'category', TCH_CATEGORIES),
            'module': 'projects'
        },
        'Personal Projects': {
            'category_list': PERSONAL_PROJECT_CATEGORIES,
            'usage': _get_category_usage('personal_projects', 'category', PERSONAL_PROJECT_CATEGORIES),
            'module': 'persprojects'
        },
        'Equipment': {
            'category_list': EQUIPMENT_CATEGORIES,
            'usage': _get_category_usage('equipment', 'category', EQUIPMENT_CATEGORIES),
            'module': 'equipment'
        },
        'Property Types': {
            'category_list': PROPERTY_TYPES,
            'usage': _get_category_usage('properties', 'property_type', PROPERTY_TYPES),
            'module': 'realestate'
        },
        'Maintenance Categories': {
            'category_list': MAINTENANCE_CATEGORIES,
            'usage': _get_category_usage('property_maintenance', 'category', MAINTENANCE_CATEGORIES),
            'module': 'realestate'
        },
        'Network Device Roles': {
            'category_list': NETWORK_ROLES,
            'usage': _get_category_usage('devices', 'role', NETWORK_ROLES),
            'module': 'network'
        },
        'Network Device Status': {
            'category_list': NETWORK_STATUS,
            'usage': _get_category_usage('devices', 'status', NETWORK_STATUS),
            'module': 'network'
        },
        'Network Locations': {
            'category_list': NETWORK_LOCATIONS,
            'usage': _get_category_usage('devices', 'location', NETWORK_LOCATIONS),
            'module': 'network'
        },
        'Spending Categories': {
            'category_list': spending_cat_names,
            'usage': spending_cat_usage,
            'module': 'financial (database)'
        },
        'Calendar Event Types': {
            'category_list': event_types,
            'usage': event_type_usage,
            'module': 'daily (database)'
        }
    }
    
    return render_template('admin_system/categories.html',
                         categories=categories,
                         active='admin_system')


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


# ==================== HELPER FUNCTIONS ====================

def _get_category_usage(table_name, column_name, categories):
    """Count how many records use each category"""
    usage = {}
    for cat in categories:
        try:
            count = db.session.execute(
                text(f"SELECT COUNT(*) FROM {table_name} WHERE {column_name} = :cat"),
                {'cat': cat}
            ).scalar()
            usage[cat] = count or 0
        except:
            usage[cat] = 0
    return usage


# ==================== API ENDPOINTS ====================

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