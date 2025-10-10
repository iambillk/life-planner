# modules/admin_system/utils.py
"""
Admin System Utility Functions
Helper functions for gathering system statistics and health metrics
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import text, inspect
from flask import current_app
from models.base import db


def format_bytes(bytes_size):
    """Format bytes to human-readable size"""
    if bytes_size is None or bytes_size == 0:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"


def get_database_stats():
    """Get database size and growth statistics"""
    db_path = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    
    if not os.path.exists(db_path):
        return {
            'size': 0,
            'size_formatted': '0 B',
            'growth_7d': 0,
            'growth_30d': 0,
            'last_modified': None,
            'total_records': 0,
            'table_count': 0
        }
    
    # Current size
    size = os.path.getsize(db_path)
    last_modified = datetime.fromtimestamp(os.path.getmtime(db_path))
    
    # Get total record count
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    total_records = 0
    for table in tables:
        try:
            result = db.session.execute(text(f"SELECT COUNT(*) FROM {table}"))
            total_records += result.scalar() or 0
        except:
            pass
    
    return {
        'size': size,
        'size_formatted': format_bytes(size),
        'path': db_path,
        'last_modified': last_modified,
        'total_records': total_records or 0,
        'table_count': len(tables)
    }


def get_table_sizes():
    """Get row counts for all tables"""
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    table_stats = []
    for table_name in sorted(tables):
        try:
            result = db.session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            row_count = result.scalar() or 0
            
            # Get column count
            columns = inspector.get_columns(table_name)
            
            table_stats.append({
                'name': table_name,
                'row_count': row_count,
                'column_count': len(columns)
            })
        except Exception as e:
            table_stats.append({
                'name': table_name,
                'row_count': 0,
                'column_count': 0,
                'error': str(e)
            })
    
    # Sort by row count descending
    table_stats.sort(key=lambda x: x['row_count'], reverse=True)
    
    return table_stats


def get_storage_stats():
    """Get file storage statistics"""
    upload_folder = current_app.config['UPLOAD_FOLDER']
    
    if not os.path.exists(upload_folder):
        return {
            'total_size': 0,
            'total_size_formatted': '0 B',
            'total_files': 0,
            'categories': {}
        }
    
    categories = {}
    total_size = 0
    total_files = 0
    
    # Subdirectories to scan
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
            categories[subdir] = {
                'size': 0,
                'size_formatted': '0 B',
                'file_count': 0
            }
            continue
        
        dir_size = 0
        file_count = 0
        
        for root, dirs, files in os.walk(dir_path):
            for filename in files:
                filepath = os.path.join(root, filename)
                try:
                    file_size = os.path.getsize(filepath)
                    dir_size += file_size
                    file_count += 1
                except:
                    pass
        
        categories[subdir] = {
            'size': dir_size,
            'size_formatted': format_bytes(dir_size),
            'file_count': file_count
        }
        
        total_size += dir_size
        total_files += file_count
    
    return {
        'total_size': total_size,
        'total_size_formatted': format_bytes(total_size),
        'total_files': total_files,
        'categories': categories
    }


def get_module_activity():
    """Get activity stats for each module"""
    from models import (
        Equipment, MaintenanceRecord, TCHProject, PersonalProject,
        CalendarEvent, WeightEntry, Transaction, Property,
        TodoList, Goal
    )
    
    now = datetime.now()
    cutoff_30d = now - timedelta(days=30)
    cutoff_7d = now - timedelta(days=7)
    
    activity = {
        'equipment': {
            'total': Equipment.query.count(),
            'recent_7d': MaintenanceRecord.query.filter(
                MaintenanceRecord.created_at >= cutoff_7d
            ).count(),
            'recent_30d': MaintenanceRecord.query.filter(
                MaintenanceRecord.created_at >= cutoff_30d
            ).count()
        },
        'projects': {
            'total': TCHProject.query.count(),
            'recent_7d': TCHProject.query.filter(
                TCHProject.created_at >= cutoff_7d
            ).count(),
            'recent_30d': TCHProject.query.filter(
                TCHProject.created_at >= cutoff_30d
            ).count()
        },
        'personal_projects': {
            'total': PersonalProject.query.count(),
            'recent_7d': PersonalProject.query.filter(
                PersonalProject.created_at >= cutoff_7d
            ).count(),
            'recent_30d': PersonalProject.query.filter(
                PersonalProject.created_at >= cutoff_30d
            ).count()
        },
        'calendar': {
            'total': CalendarEvent.query.count(),
            'recent_7d': CalendarEvent.query.filter(
                CalendarEvent.created_at >= cutoff_7d
            ).count(),
            'recent_30d': CalendarEvent.query.filter(
                CalendarEvent.created_at >= cutoff_30d
            ).count()
        },
        'health': {
            'total': WeightEntry.query.count(),
            'recent_7d': WeightEntry.query.filter(
                WeightEntry.date >= cutoff_7d.date()
            ).count(),
            'recent_30d': WeightEntry.query.filter(
                WeightEntry.date >= cutoff_30d.date()
            ).count()
        },
        'financial': {
            'total': Transaction.query.count(),
            'recent_7d': Transaction.query.filter(
                Transaction.date >= cutoff_7d.date()
            ).count(),
            'recent_30d': Transaction.query.filter(
                Transaction.date >= cutoff_30d.date()
            ).count()
        },
        'properties': {
            'total': Property.query.count(),
            'recent_7d': 0,  # Properties don't track creation date well
            'recent_30d': 0
        },
        'todos': {
            'total': TodoList.query.count(),
            'recent_7d': TodoList.query.filter(
                TodoList.created_at >= cutoff_7d
            ).count(),
            'recent_30d': TodoList.query.filter(
                TodoList.created_at >= cutoff_30d
            ).count()
        },
        'goals': {
            'total': Goal.query.count(),
            'recent_7d': 0,
            'recent_30d': 0
        }
    }
    
    return activity


def get_recent_activity(limit=20):
    """Get recent activity across all modules"""
    from models import (
        Equipment, MaintenanceRecord, TCHProject, PersonalProject,
        CalendarEvent, WeightEntry, Transaction
    )
    
    activities = []
    
    # Equipment maintenance
    maintenance = MaintenanceRecord.query.order_by(
        MaintenanceRecord.created_at.desc()
    ).limit(5).all()
    
    for m in maintenance:
        activities.append({
            'timestamp': m.created_at,
            'module': 'Equipment',
            'icon': '🔧',
            'action': f'Added maintenance to {m.equipment.name}',
            'details': m.service_type
        })
    
    # Projects
    projects = TCHProject.query.order_by(
        TCHProject.created_at.desc()
    ).limit(5).all()
    
    for p in projects:
        activities.append({
            'timestamp': p.created_at,
            'module': 'Projects',
            'icon': '📊',
            'action': f'Created project: {p.name}',
            'details': p.category
        })
    
    # Personal Projects
    personal = PersonalProject.query.order_by(
        PersonalProject.created_at.desc()
    ).limit(5).all()
    
    for p in personal:
        activities.append({
            'timestamp': p.created_at,
            'module': 'Personal',
            'icon': '🏠',
            'action': f'Created project: {p.name}',
            'details': p.category
        })
    
    # Calendar events
    events = CalendarEvent.query.order_by(
        CalendarEvent.created_at.desc()
    ).limit(5).all()
    
    for e in events:
        activities.append({
            'timestamp': e.created_at,
            'module': 'Daily',
            'icon': '📅',
            'action': f'Added event: {e.event_type}',
            'details': e.who
        })
    
    # Health entries
    weights = WeightEntry.query.order_by(
        WeightEntry.date.desc()
    ).limit(5).all()
    
    for w in weights:
        activities.append({
            'timestamp': datetime.combine(w.date, datetime.min.time()),
            'module': 'Health',
            'icon': '⚖️',
            'action': f'Logged weight: {w.weight} lbs',
            'details': w.date.strftime('%Y-%m-%d')
        })
    
    # Financial transactions
    transactions = Transaction.query.order_by(
        Transaction.date.desc()
    ).limit(5).all()
    
    for t in transactions:
        activities.append({
            'timestamp': datetime.combine(t.date, datetime.min.time()),
            'module': 'Financial',
            'icon': '💰',
            'action': f'${t.amount:.2f} at {t.merchant}',
            'details': t.card if hasattr(t, 'card') else 'Transaction'
        })
    
    # Sort all activities by timestamp descending
    activities.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return activities[:limit]


def get_orphaned_files():
    """Identify files not referenced in database"""
    # This is a placeholder - implement based on your file tracking
    orphaned = []
    
    upload_folder = current_app.config['UPLOAD_FOLDER']
    
    # Scan equipment photos
    equipment_dir = os.path.join(upload_folder, 'equipment_profiles')
    if os.path.exists(equipment_dir):
        from models import Equipment, EquipmentPhoto
        
        all_files = set(os.listdir(equipment_dir))
        
        # Get referenced files
        referenced = set()
        for eq in Equipment.query.all():
            if eq.profile_photo:
                referenced.add(eq.profile_photo)
        
        for photo in EquipmentPhoto.query.all():
            if photo.filename:
                referenced.add(photo.filename)
        
        orphaned_files = all_files - referenced
        
        for f in orphaned_files:
            filepath = os.path.join(equipment_dir, f)
            orphaned.append({
                'filename': f,
                'category': 'equipment_profiles',
                'size': os.path.getsize(filepath),
                'modified': datetime.fromtimestamp(os.path.getmtime(filepath))
            })
    
    return orphaned