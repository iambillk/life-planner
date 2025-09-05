# modules/realestate/routes.py
"""
Real Estate Management Routes
Version: 1.0.0
Created: 2025-01-03

Handles all routes for property management, maintenance tracking,
vendor management, and cost analysis.

CHANGELOG:
v1.0.0 (2025-01-03)
- Initial route implementation
- Mobile-first dashboard and quick-add
- Property CRUD operations
- Maintenance tracking with photos
- Vendor management
- Cost analysis and reporting
"""

import os
import json
from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from sqlalchemy import extract, func
from . import realestate_bp
from .constants import (
    PROPERTY_TYPES, 
    MAINTENANCE_CATEGORIES, 
    MAINTENANCE_TASKS,
    COST_CATEGORIES, 
    VENDOR_SERVICE_TYPES,
    QUICK_ADD_TASKS,
    WEATHER_CONDITIONS,
    PERFORMED_BY,
    COMMON_INTERVALS
)
from models import (
    db, 
    Property, 
    PropertyMaintenance, 
    PropertyVendor,
    PropertyMaintenancePhoto,
    MaintenanceTemplate
)

# ==================== DASHBOARD & OVERVIEW ====================

@realestate_bp.route('/')
def dashboard():
    """
    Main dashboard - shows property cards with selected property detail view
    Hybrid approach: property cards as selectors + detailed view of selected property
    """
    # Get all active properties
    properties = Property.query.filter_by(is_active=True).order_by(Property.name).all()
    
    # Get selected property from query params (for property switching)
    selected_property_id = request.args.get('property_id', type=int)
    
    if selected_property_id:
        selected_property = Property.query.get(selected_property_id)
    elif properties:
        # Default to primary residence or first property
        primary = next((p for p in properties if p.is_primary_residence), None)
        selected_property = primary or properties[0]
    else:
        selected_property = None
    
    # Initialize dashboard data
    overdue_tasks = []
    upcoming_tasks = []
    recent_maintenance = []
    monthly_costs = {}
    
    if selected_property:
        # Get overdue tasks
        overdue_tasks = PropertyMaintenance.query.filter_by(
            property_id=selected_property.id,
            is_recurring=True
        ).filter(
            PropertyMaintenance.next_due_date < datetime.utcnow().date()
        ).order_by(PropertyMaintenance.next_due_date).all()
        
        # Get upcoming tasks (next 30 days)
        upcoming_tasks = PropertyMaintenance.query.filter_by(
            property_id=selected_property.id,
            is_recurring=True
        ).filter(
            PropertyMaintenance.next_due_date >= datetime.utcnow().date(),
            PropertyMaintenance.next_due_date <= datetime.utcnow().date() + timedelta(days=30)
        ).order_by(PropertyMaintenance.next_due_date).all()
        
        # Get recent maintenance (last 10)
        recent_maintenance = PropertyMaintenance.query.filter_by(
            property_id=selected_property.id
        ).order_by(PropertyMaintenance.date_completed.desc()).limit(10).all()
        
        # Calculate monthly costs for current year
        current_year = datetime.utcnow().year
        monthly_query = db.session.query(
            extract('month', PropertyMaintenance.date_completed).label('month'),
            func.sum(PropertyMaintenance.cost).label('total')
        ).filter(
            PropertyMaintenance.property_id == selected_property.id,
            extract('year', PropertyMaintenance.date_completed) == current_year
        ).group_by(extract('month', PropertyMaintenance.date_completed)).all()
        
        monthly_costs = {month: float(total or 0) for month, total in monthly_query}
    
    # Get quick add templates
    quick_tasks = QUICK_ADD_TASKS[:6]  # Top 6 for mobile
    
    return render_template('realestate/dashboard.html',
                         properties=properties,
                         selected_property=selected_property,
                         overdue_tasks=overdue_tasks,
                         upcoming_tasks=upcoming_tasks,
                         recent_maintenance=recent_maintenance,
                         monthly_costs=monthly_costs,
                         quick_tasks=quick_tasks,
                         active='realestate')


# ==================== PROPERTY MANAGEMENT ====================

@realestate_bp.route('/property/add', methods=['GET', 'POST'])
def add_property():
    """Add a new property to manage"""
    if request.method == 'POST':
        property = Property(
            name=request.form.get('name'),
            address=request.form.get('address'),
            city=request.form.get('city'),
            state=request.form.get('state'),
            zip_code=request.form.get('zip_code'),
            property_type=request.form.get('property_type', 'house'),
            square_footage=request.form.get('square_footage', type=int),
            lot_size_acres=request.form.get('lot_size_acres', type=float),
            year_built=request.form.get('year_built', type=int),
            is_primary_residence=request.form.get('is_primary_residence') == 'on',
            notes=request.form.get('notes')
        )
        
        # Handle purchase info
        if request.form.get('purchase_date'):
            property.purchase_date = datetime.strptime(request.form.get('purchase_date'), '%Y-%m-%d').date()
        property.purchase_price = request.form.get('purchase_price', type=float)
        
        # Equipment details
        property.hvac_filter_size = request.form.get('hvac_filter_size')
        property.generator_make = request.form.get('generator_make')
        property.generator_model = request.form.get('generator_model')
        property.water_heater_type = request.form.get('water_heater_type')
        property.septic_tank_size_gallons = request.form.get('septic_tank_size_gallons', type=int)
        
        # Handle photo upload
        if 'profile_photo' in request.files:
            file = request.files['profile_photo']
            if file and file.filename:
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{filename}"
                
                # Create directory if it doesn't exist
                upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'property_profiles')
                os.makedirs(upload_dir, exist_ok=True)
                
                file.save(os.path.join(upload_dir, filename))
                property.profile_photo = filename
        
        db.session.add(property)
        db.session.commit()
        
        flash(f'Property "{property.name}" added successfully!', 'success')
        return redirect(url_for('realestate.property_detail', id=property.id))
    
    return render_template('realestate/property_form.html',
                         property_types=PROPERTY_TYPES,
                         active='realestate')


@realestate_bp.route('/property/<int:id>')
def property_detail(id):
    """View detailed information about a property"""
    property = Property.query.get_or_404(id)
    
    # Get recent maintenance
    recent_maintenance = PropertyMaintenance.query.filter_by(
        property_id=id
    ).order_by(PropertyMaintenance.date_completed.desc()).limit(20).all()
    
    # Get vendors
    vendors = PropertyVendor.query.filter_by(property_id=id).order_by(PropertyVendor.service_type).all()
    
    # Calculate statistics
    stats = {
        'total_maintenance': PropertyMaintenance.query.filter_by(property_id=id).count(),
        'ytd_cost': db.session.query(func.sum(PropertyMaintenance.cost)).filter(
            PropertyMaintenance.property_id == id,
            extract('year', PropertyMaintenance.date_completed) == datetime.utcnow().year
        ).scalar() or 0,
        'overdue_count': property.overdue_maintenance_count,
        'upcoming_count': property.upcoming_maintenance_count
    }
    
    return render_template('realestate/property_detail.html',
                         property=property,
                         recent_maintenance=recent_maintenance,
                         vendors=vendors,
                         stats=stats,
                         active='realestate')


@realestate_bp.route('/property/<int:id>/edit', methods=['GET', 'POST'])
def edit_property(id):
    """Edit property information"""
    property = Property.query.get_or_404(id)
    
    if request.method == 'POST':
        property.name = request.form.get('name')
        property.address = request.form.get('address')
        property.city = request.form.get('city')
        property.state = request.form.get('state')
        property.zip_code = request.form.get('zip_code')
        property.property_type = request.form.get('property_type')
        property.square_footage = request.form.get('square_footage', type=int)
        property.lot_size_acres = request.form.get('lot_size_acres', type=float)
        property.year_built = request.form.get('year_built', type=int)
        property.is_primary_residence = request.form.get('is_primary_residence') == 'on'
        property.notes = request.form.get('notes')
        
        # Update equipment details
        property.hvac_filter_size = request.form.get('hvac_filter_size')
        property.generator_make = request.form.get('generator_make')
        property.generator_model = request.form.get('generator_model')
        property.water_heater_type = request.form.get('water_heater_type')
        property.septic_tank_size_gallons = request.form.get('septic_tank_size_gallons', type=int)
        
        property.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash(f'Property "{property.name}" updated!', 'success')
        return redirect(url_for('realestate.property_detail', id=id))
    
    return render_template('realestate/property_form.html',
                         property=property,
                         property_types=PROPERTY_TYPES,
                         active='realestate')


# ==================== MAINTENANCE TRACKING ====================

@realestate_bp.route('/property/<int:property_id>/maintenance/add', methods=['GET', 'POST'])
def add_maintenance(property_id):
    """Add a maintenance record - mobile optimized"""
    property = Property.query.get_or_404(property_id)
    
    if request.method == 'POST':
        maintenance = PropertyMaintenance(
            property_id=property_id,
            category=request.form.get('category'),
            task=request.form.get('task'),
            description=request.form.get('description'),
            date_completed=datetime.strptime(request.form.get('date_completed'), '%Y-%m-%d').date(),
            performed_by=request.form.get('performed_by', 'Self'),
            cost=request.form.get('cost', type=float) or 0,
            cost_category=request.form.get('cost_category'),
            notes=request.form.get('notes'),
            is_recurring=request.form.get('is_recurring') == 'on'
        )
        
        # Handle recurring task setup
        if maintenance.is_recurring:
            interval = request.form.get('interval_days', type=int)
            if interval:
                maintenance.interval_days = interval
                maintenance.calculate_next_due()
        
        # Handle supplies used
        if request.form.get('supplies_used'):
            maintenance.supplies_used = request.form.get('supplies_used')
        
        # Handle vendor selection
        vendor_id = request.form.get('vendor_id', type=int)
        if vendor_id:
            maintenance.vendor_id = vendor_id
            vendor = PropertyVendor.query.get(vendor_id)
            if vendor:
                maintenance.performed_by = vendor.company_name
        
        db.session.add(maintenance)
        db.session.flush()  # Get the ID before handling photos
        
        # Handle photo uploads
        if 'photos' in request.files:
            files = request.files.getlist('photos')
            for file in files:
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"{timestamp}_{filename}"
                    
                    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'property_maintenance')
                    os.makedirs(upload_dir, exist_ok=True)
                    
                    file.save(os.path.join(upload_dir, filename))
                    
                    photo = PropertyMaintenancePhoto(
                        maintenance_id=maintenance.id,
                        filename=filename,
                        photo_type=request.form.get('photo_type', 'general')
                    )
                    db.session.add(photo)
        
        # Update or create template for quick access
        template = MaintenanceTemplate.query.filter_by(
            category=maintenance.category,
            task_name=maintenance.task
        ).first()
        
        if template:
            template.times_used += 1
            template.last_used = datetime.utcnow()
        else:
            template = MaintenanceTemplate(
                category=maintenance.category,
                task_name=maintenance.task,
                default_interval_days=maintenance.interval_days,
                typical_cost=maintenance.cost,
                times_used=1,
                last_used=datetime.utcnow()
            )
            db.session.add(template)
        
        db.session.commit()
        
        flash(f'Maintenance record added for {maintenance.task}!', 'success')
        
        # Check if this was a quick add (mobile)
        if request.form.get('quick_add'):
            return redirect(url_for('realestate.dashboard', property_id=property_id))
        
        return redirect(url_for('realestate.property_detail', id=property_id))
    
    # GET request - show form
    # Get categories and tasks for dropdowns
    vendors = PropertyVendor.query.filter_by(property_id=property_id).order_by(PropertyVendor.service_type).all()
    
    # Get frequently used tasks for quick selection
    frequent_tasks = MaintenanceTemplate.query.order_by(
        MaintenanceTemplate.times_used.desc()
    ).limit(10).all()
    
    return render_template('realestate/maintenance_form.html',
                         property=property,
                         categories=MAINTENANCE_CATEGORIES,
                         tasks=MAINTENANCE_TASKS,
                         cost_categories=COST_CATEGORIES,
                         vendors=vendors,
                         frequent_tasks=frequent_tasks,
                         performed_by_options=PERFORMED_BY,
                         weather_conditions=WEATHER_CONDITIONS,
                         common_intervals=COMMON_INTERVALS,
                         active='realestate')