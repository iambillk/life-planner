from flask import render_template, request, redirect, url_for, flash, send_file, current_app
from werkzeug.utils import secure_filename
from datetime import date, datetime
from models import db, Equipment, MaintenanceRecord, MaintenanceReminder, EquipmentPhoto, MaintenancePhoto
from .utils import generate_maintenance_pdf, allowed_file, save_uploaded_photo, get_maintenance_alerts
from .constants import EQUIPMENT_CATEGORIES, SERVICE_TYPES
from models import FuelLog, ConsumableLog, CarWashLog, Receipt
from sqlalchemy import func
from collections import defaultdict
import os
from . import equipment_bp  # Import the blueprint from __init__.py


@equipment_bp.route('/')
def index():
    """Equipment dashboard with alerts"""
    equipment_list = Equipment.query.all()
    overdue, upcoming = get_maintenance_alerts(equipment_list)
    
    # Get seasonal reminders
    current_month = datetime.now().month
    season = 'spring' if current_month in [3, 4] else 'fall' if current_month in [10, 11] else None
    
    seasonal_reminders = []
    if season:
        seasonal_reminders = MaintenanceReminder.query.filter_by(
            trigger_season=season, is_active=True, completed=False
        ).all()
    
    return render_template('equipment/dashboard.html',
                         equipment=equipment_list,
                         overdue=overdue,
                         upcoming=upcoming,
                         seasonal_reminders=seasonal_reminders,
                         categories=EQUIPMENT_CATEGORIES,
                         active='equipment')


@equipment_bp.route('/add', methods=['GET', 'POST'])
def add():
    """Add new equipment"""
    if request.method == 'POST':
        # Parse ownership fields
        pd_str = request.form.get('purchase_date')
        pp_str = request.form.get('purchase_price')

        equipment = Equipment(
            name=request.form.get('name'),
            category=request.form.get('category'),
            make=request.form.get('make'),
            model=request.form.get('model'),
            year=int(request.form.get('year')) if request.form.get('year') else None,
            serial_number=request.form.get('serial_number'),
            location=request.form.get('location'),
            notes=request.form.get('notes'),
            purchase_date=datetime.strptime(pd_str, '%Y-%m-%d').date() if pd_str else None,
            purchase_price=float(pp_str) if pp_str not in (None, '',) else None,
        )
        
        # Handle photo upload
        if 'profile_photo' in request.files:
            file = request.files['profile_photo']
            if file and allowed_file(file.filename):
                filename = save_uploaded_photo(file, 'equipment_profiles', equipment.name)
                equipment.profile_photo = filename
        
        db.session.add(equipment)
        db.session.commit()
        
        flash(f'{equipment.name} added successfully!', 'success')
        return redirect(url_for('equipment.detail', id=equipment.id))
    
    return render_template('add_equipment.html', 
                         categories=EQUIPMENT_CATEGORIES,
                         active='equipment')


@equipment_bp.route('/<int:id>')
def detail(id):
    """View equipment details"""
    equipment = Equipment.query.get_or_404(id)
    maintenance_records = MaintenanceRecord.query.filter_by(
        equipment_id=id
    ).order_by(MaintenanceRecord.service_date.desc()).all()
    
    photos = EquipmentPhoto.query.filter_by(equipment_id=id).all()
    
    # Calculate ALL upcoming/overdue maintenance items
    upcoming_maintenance = []
    today = datetime.now().date()
    current_mileage = equipment.mileage or 0
    
    # Check all maintenance records for their next service dates/mileage
    seen_services = set()  # Track which service types we've seen
    for record in maintenance_records:
        if record.service_type not in seen_services:
            # Check if there's a date OR mileage threshold
            if record.next_service_date or record.next_service_mileage:
                days_until = None
                miles_until = None
                
                if record.next_service_date:
                    days_until = (record.next_service_date - today).days
                
                if record.next_service_mileage and current_mileage:
                    miles_until = record.next_service_mileage - current_mileage
                
                # Determine overall status based on both date and mileage
                status = 'good'
                if days_until is not None:
                    if days_until < 0:
                        status = 'overdue'
                    elif days_until <= 30:
                        status = 'upcoming'
                
                # Override with mileage status if it's more urgent
                if miles_until is not None:
                    if miles_until < 0:
                        status = 'overdue'
                    elif miles_until <= 500:  # Within 500 miles
                        if status != 'overdue':
                            status = 'upcoming'
                
                upcoming_maintenance.append({
                    'service': record.service_type,
                    'date': record.next_service_date,
                    'days': days_until,
                    'next_mileage': record.next_service_mileage,
                    'miles_until': miles_until,
                    'status': status,
                    'last_service_date': record.service_date,
                    'last_service_mileage': record.mileage_at_service
                })
                seen_services.add(record.service_type)
    
    # Sort by urgency (overdue first, then by whichever is sooner - date or mileage)
    def sort_key(item):
        # Overdue items first
        if item['status'] == 'overdue':
            return (0, item['days'] if item['days'] is not None else 999999)
        elif item['status'] == 'upcoming':
            return (1, item['days'] if item['days'] is not None else 999999)
        else:
            return (2, item['days'] if item['days'] is not None else 999999)
    
    upcoming_maintenance.sort(key=sort_key)
    
    # For backward compatibility, keep next_due as the first/most urgent one
    next_due = upcoming_maintenance[0] if upcoming_maintenance else None
    
    return render_template('equipment_detail.html',
                         equipment=equipment,
                         maintenance_records=maintenance_records,
                         photos=photos,
                         next_due=next_due,
                         upcoming_maintenance=upcoming_maintenance,
                         active='equipment')


@equipment_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit(id):
    """Edit equipment"""
    equipment = Equipment.query.get_or_404(id)
    
    if request.method == 'POST':
        # ----- core fields -----
        equipment.name = request.form.get('name')
        equipment.category = request.form.get('category')
        equipment.make = request.form.get('make')
        equipment.model = request.form.get('model')
        equipment.year = int(request.form.get('year')) if request.form.get('year') else None
        equipment.serial_number = request.form.get('serial_number')
        equipment.mileage = int(request.form.get('mileage')) if request.form.get('mileage') else None
        equipment.hours = float(request.form.get('hours')) if request.form.get('hours') else None
        equipment.location = request.form.get('location')
        equipment.status = request.form.get('status')
        equipment.notes = request.form.get('notes')

        # ----- ownership fields (persist on edit) -----
        pd_str = request.form.get('purchase_date')
        equipment.purchase_date = datetime.strptime(pd_str, '%Y-%m-%d').date() if pd_str else None

        pp_str = request.form.get('purchase_price')
        equipment.purchase_price = float(pp_str) if pp_str not in (None, '',) else None

        equipment.updated_at = datetime.utcnow()
        
        # ----- profile photo replacement -----
        new_file = request.files.get('profile_photo')
        old_filename = equipment.profile_photo
        new_filename = None

        if new_file and new_file.filename and allowed_file(new_file.filename):
            # Save new image to same folder & update DB field
            new_filename = save_uploaded_photo(new_file, 'equipment_profiles', equipment.name)
            equipment.profile_photo = new_filename

        # Commit changes (including possibly new profile photo filename)
        db.session.commit()

        # Optional: remove old file after commit
        if new_filename and old_filename and old_filename != new_filename:
            try:
                old_path = os.path.join(
                    current_app.config['UPLOAD_FOLDER'], 'equipment_profiles', old_filename
                )
                if os.path.exists(old_path):
                    os.remove(old_path)
            except Exception as e:
                current_app.logger.warning(f'Could not delete old profile photo {old_filename}: {e}')
        
        flash(f'{equipment.name} updated successfully!', 'success')
        return redirect(url_for('equipment.detail', id=id))
    
    return render_template('edit_equipment.html', 
                         equipment=equipment,
                         categories=EQUIPMENT_CATEGORIES,
                         active='equipment')


@equipment_bp.route('/<int:id>/photos/upload', methods=['POST'])
def upload_photo(id):
    """Upload photos for equipment (detail page slab) — single photo"""
    equipment = Equipment.query.get_or_404(id)
    
    if 'photo' in request.files:
        file = request.files['photo']
        if file and allowed_file(file.filename):
            filename = save_uploaded_photo(file, 'equipment_profiles', equipment.name)
            
            photo = EquipmentPhoto(
                equipment_id=id,
                filename=filename,
                caption=request.form.get('caption'),
                photo_type=request.form.get('photo_type', 'detail')
            )
            db.session.add(photo)
            db.session.commit()
            
            flash('Photo uploaded successfully!', 'success')
    
    return redirect(url_for('equipment.detail', id=id))


@equipment_bp.route('/<int:id>/maintenance/add', methods=['GET', 'POST'])
def add_maintenance(id):
    """Add maintenance record (supports multi-photo groups with captions)"""
    equipment = Equipment.query.get_or_404(id)
    
    if request.method == 'POST':
        record = MaintenanceRecord(
            equipment_id=id,
            service_type=request.form.get('service_type'),
            service_date=datetime.strptime(request.form.get('service_date'), '%Y-%m-%d').date(),
            mileage_at_service=int(request.form.get('mileage_at_service')) if request.form.get('mileage_at_service') else None,
            hours_at_service=float(request.form.get('hours_at_service')) if request.form.get('hours_at_service') else None,
            cost=float(request.form.get('cost')) if request.form.get('cost') else None,
            parts_used=request.form.get('parts_used'),
            notes=request.form.get('notes'),
            performed_by=request.form.get('performed_by', 'Self')
        )
        
        # Set next service date
        if request.form.get('next_service_months'):
            from dateutil.relativedelta import relativedelta
            months = int(request.form.get('next_service_months'))
            record.next_service_date = record.service_date + relativedelta(months=months)

        # ADD THIS - Set next service mileage
        if request.form.get('next_service_mileage'):
            record.next_service_mileage = int(request.form.get('next_service_mileage'))

        db.session.add(record)
        db.session.commit()
        
        # --------- MULTI-PHOTO GROUPS (Before/After/Receipts) ---------
        groups = [
            ('before', 'before_photos', 'before_captions'),
            ('after', 'after_photos', 'after_captions'),
            ('receipt', 'receipt_photos', 'receipt_captions'),
        ]
        for group_name, files_field, caps_field in groups:
            files = request.files.getlist(files_field)
            captions = request.form.getlist(caps_field)
            for idx, f in enumerate(files):
                if not (f and allowed_file(f.filename)):
                    continue
                filename = save_uploaded_photo(
                    f,
                    'maintenance_photos',
                    f"{equipment.name}_{record.service_type}_{group_name}"
                )
                caption = captions[idx] if idx < len(captions) else None
                photo = MaintenancePhoto(
                    maintenance_id=record.id,
                    filename=filename,
                    photo_type=group_name,
                    caption=caption
                )
                db.session.add(photo)

        # --------- BACK-COMPAT: single-file fields (if present) ---------
        legacy = [
            ('before', 'before_photo', 'before_photo_caption'),
            ('after', 'after_photo', 'after_photo_caption'),
            ('receipt', 'receipt_photo', 'receipt_photo_caption'),
        ]
        for group_name, file_field, cap_field in legacy:
            f = request.files.get(file_field)
            if f and allowed_file(f.filename):
                filename = save_uploaded_photo(
                    f,
                    'maintenance_photos',
                    f"{equipment.name}_{record.service_type}_{group_name}"
                )
                photo = MaintenancePhoto(
                    maintenance_id=record.id,
                    filename=filename,
                    photo_type=group_name,
                    caption=request.form.get(cap_field)
                )
                db.session.add(photo)
        
        # Update equipment mileage/hours
        if record.mileage_at_service:
            equipment.mileage = record.mileage_at_service
        if record.hours_at_service:
            equipment.hours = record.hours_at_service
        
        db.session.commit()
        flash('Maintenance record added successfully!', 'success')
        return redirect(url_for('equipment.detail', id=id))
    
    # NOTE: keep your existing template name; swap to 'maintenance_add.html' if you moved it
    return render_template('maintenance_log.html',
                         equipment=equipment,
                         service_types=SERVICE_TYPES,
                         active='equipment')


@equipment_bp.route('/<int:id>/export-pdf')
def export_pdf(id):
    """Export maintenance history as PDF"""
    equipment = Equipment.query.get_or_404(id)
    maintenance_records = MaintenanceRecord.query.filter_by(
        equipment_id=id
    ).order_by(MaintenanceRecord.service_date.desc()).all()
    
    pdf_buffer = generate_maintenance_pdf(equipment, maintenance_records)
    
    filename = f"{equipment.name}_maintenance_{datetime.now().strftime('%Y%m%d')}.pdf"
    return send_file(pdf_buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')


@equipment_bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    """Delete equipment"""
    equipment = Equipment.query.get_or_404(id)
    name = equipment.name
    
    # Delete profile photo from filesystem
    if equipment.profile_photo:
        try:
            photo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'equipment_profiles', equipment.profile_photo)
            os.remove(photo_path)
        except Exception:
            pass
    
    db.session.delete(equipment)
    db.session.commit()
    
    flash(f'{name} deleted successfully!', 'success')
    return redirect(url_for('equipment.index'))


@equipment_bp.route('/category/<category>')
def by_category(category):
    """View equipment by category"""
    if category == 'all':
        equipment = Equipment.query.all()
    else:
        equipment = Equipment.query.filter_by(category=category).all()
    
    return render_template('equipment_list.html',
                         equipment=equipment,
                         category=category,
                         categories=EQUIPMENT_CATEGORIES,
                         active='equipment')


@equipment_bp.route('/<int:id>/fuel')
def fuel_history(id):
    """View fuel history for equipment"""
    equipment = Equipment.query.get_or_404(id)
    fuel_logs = FuelLog.query.filter_by(equipment_id=id).order_by(FuelLog.date.desc()).all()
    
    # Calculate statistics
    stats = {}
    if fuel_logs:
        stats['total_gallons'] = sum(log.gallons for log in fuel_logs)
        stats['total_cost'] = sum(log.total_cost for log in fuel_logs)
        stats['avg_price'] = stats['total_cost'] / stats['total_gallons'] if stats['total_gallons'] > 0 else 0
        
        # MPG stats for vehicles
        mpg_logs = [log.mpg for log in fuel_logs if log.mpg]
        if mpg_logs:
            stats['avg_mpg'] = sum(mpg_logs) / len(mpg_logs)
            stats['best_mpg'] = max(mpg_logs)
            stats['worst_mpg'] = min(mpg_logs)
    
    return render_template('equipment/fuel_history.html',
                         equipment=equipment,
                         fuel_logs=fuel_logs,
                         stats=stats,
                         active='equipment')


@equipment_bp.route('/<int:id>/fuel/add', methods=['GET', 'POST'])
def add_fuel(id):
    """Add fuel purchase"""
    equipment = Equipment.query.get_or_404(id)
    
    if request.method == 'POST':
        # Get the last fuel log to calculate MPG
        last_log = FuelLog.query.filter_by(equipment_id=id).order_by(FuelLog.date.desc()).first()
        
        fuel_log = FuelLog(
            equipment_id=id,
            station_name=request.form.get('station_name'),
            station_location=request.form.get('station_location'),
            gallons=float(request.form.get('gallons')),
            price_per_gallon=float(request.form.get('price_per_gallon')),
            total_cost=float(request.form.get('total_cost')),
            fuel_type=request.form.get('fuel_type'),
            odometer=int(request.form.get('odometer')) if request.form.get('odometer') else None,
            trip_purpose=request.form.get('trip_purpose'),
            notes=request.form.get('notes')
        )
        
        # Calculate MPG if we have previous odometer reading
        if fuel_log.odometer and last_log and last_log.odometer:
            fuel_log.trip_miles = fuel_log.odometer - last_log.odometer
            if fuel_log.trip_miles > 0:
                fuel_log.mpg = fuel_log.trip_miles / fuel_log.gallons
        
        # Handle receipt upload
        if 'receipt' in request.files:
            file = request.files['receipt']
            if file and allowed_file(file.filename):
                filename = save_uploaded_photo(file, 'receipts', f"fuel_{equipment.name}")
                fuel_log.receipt_photo = filename
        
        # Update equipment mileage
        if fuel_log.odometer:
            equipment.mileage = fuel_log.odometer
        
        db.session.add(fuel_log)
        db.session.commit()
        
        flash('Fuel purchase logged!', 'success')
        return redirect(url_for('equipment.fuel_history', id=id))
    
    # Get last odometer reading for pre-fill
    last_log = FuelLog.query.filter_by(equipment_id=id).order_by(FuelLog.date.desc()).first()
    last_odometer = last_log.odometer if last_log else equipment.mileage
    
    return render_template('equipment/add_fuel.html',
                         equipment=equipment,
                         last_odometer=last_odometer,
                         active='equipment')


@equipment_bp.route('/equipment/<int:id>/consumables')
def consumables_history(id):
    equipment = Equipment.query.get_or_404(id)
    consumables = ConsumableLog.query.filter_by(equipment_id=id).order_by(ConsumableLog.date.desc()).all()
    
    # Calculate summary statistics
    total_cost = sum(c.cost for c in consumables if c.cost)
    
    # Get unique item types for filter
    item_types = list(set(c.item_type for c in consumables if c.item_type))
    
    # Calculate months tracked
    if consumables:
        earliest = min(c.date for c in consumables)
        latest = max(c.date for c in consumables)
        months_tracked = ((latest.year - earliest.year) * 12 + latest.month - earliest.month) + 1
    else:
        months_tracked = 0
    
    # Calculate average monthly cost
    avg_monthly = total_cost / months_tracked if months_tracked > 0 else 0
    
    # Calculate cost by type
    cost_by_type = {}
    for c in consumables:
        if c.item_type and c.cost:
            if c.item_type not in cost_by_type:
                cost_by_type[c.item_type] = 0
            cost_by_type[c.item_type] += c.cost
    
    return render_template('equipment/consumables_history.html',
                         equipment=equipment,
                         consumables=consumables,
                         total_cost=total_cost,
                         item_types=item_types,
                         months_tracked=months_tracked,
                         avg_monthly=avg_monthly,
                         cost_by_type=cost_by_type)


@equipment_bp.route('/<int:id>/consumables/add', methods=['GET', 'POST'])
def add_consumable(id):
    """Add consumable item"""
    equipment = Equipment.query.get_or_404(id)
    
    if request.method == 'POST':
        consumable = ConsumableLog(
            equipment_id=id,
            item_type=request.form.get('item_type'),
            brand=request.form.get('brand'),
            quantity=float(request.form.get('quantity')) if request.form.get('quantity') else None,
            unit=request.form.get('unit'),
            cost=float(request.form.get('cost')) if request.form.get('cost') else None,
            vendor=request.form.get('vendor'),
            odometer=int(request.form.get('odometer')) if request.form.get('odometer') else None,
            notes=request.form.get('notes')
        )
        
        # Handle receipt upload
        if 'receipt' in request.files:
            file = request.files['receipt']
            if file and allowed_file(file.filename):
                filename = save_uploaded_photo(file, 'receipts', f"consumable_{equipment.name}")
                consumable.receipt_photo = filename
        
        db.session.add(consumable)
        db.session.commit()
        
        flash(f'{consumable.item_type} added!', 'success')
        return redirect(url_for('equipment.consumables_history', id=id))
    
    # Common consumables for quick select
    common_items = ['Engine Oil', 'Washer Fluid', 'Wiper Blades', 'Air Filter', 
                    'Cabin Filter', 'Battery', 'Coolant', 'Brake Fluid', 'Power Steering Fluid']
    
    return render_template('equipment/add_consumable.html',
                         equipment=equipment,
                         common_items=common_items,
                         active='equipment')


@equipment_bp.route('/<int:id>/carwash/add', methods=['GET', 'POST'])
def add_carwash(id):
    """Log car wash"""
    equipment = Equipment.query.get_or_404(id)
    
    if request.method == 'POST':
        wash = CarWashLog(
            equipment_id=id,
            wash_type=request.form.get('wash_type'),
            location=request.form.get('location'),
            cost=float(request.form.get('cost')) if request.form.get('cost') else None,
            services=request.form.get('services'),
            notes=request.form.get('notes')
        )
        
        if 'photo' in request.files:
            file = request.files['photo']
            if file and allowed_file(file.filename):
                filename = save_uploaded_photo(file, 'carwash', f"{equipment.name}_clean")
                wash.photo = filename
        
        db.session.add(wash)
        db.session.commit()
        
        flash('Car wash logged!', 'success')
        return redirect(url_for('equipment.detail', id=id))
    
    return render_template('equipment/add_carwash.html',
                         equipment=equipment,
                         active='equipment')


@equipment_bp.route('/<int:id>/cost-analysis')
def cost_analysis(id):
    """Total cost of ownership analysis"""
    equipment = Equipment.query.get_or_404(id)
    
    # Get ongoing costs (exclude purchase by design)
    maintenance_cost = db.session.query(func.sum(MaintenanceRecord.cost)).filter_by(equipment_id=id).scalar() or 0
    fuel_cost = db.session.query(func.sum(FuelLog.total_cost)).filter_by(equipment_id=id).scalar() or 0
    consumables_cost = db.session.query(func.sum(ConsumableLog.cost)).filter_by(equipment_id=id).scalar() or 0
    
    # Only get car wash costs for Auto category vehicles
    if equipment.category == 'Auto':
        wash_cost = db.session.query(func.sum(CarWashLog.cost)).filter_by(equipment_id=id).scalar() or 0
    else:
        wash_cost = 0
    
    total_cost_excl_purchase = maintenance_cost + fuel_cost + consumables_cost + wash_cost
    upfront_cost = float(equipment.purchase_price or 0)
    tco_including_purchase = total_cost_excl_purchase + upfront_cost
    
    # Cost per mile/hour from ongoing costs
    cost_per_mile = None
    cost_per_hour = None
    
    if equipment.mileage:
        first_fuel = FuelLog.query.filter_by(equipment_id=id).order_by(FuelLog.date).first()
        start_mileage = first_fuel.odometer if first_fuel and first_fuel.odometer else 0
        miles_driven = equipment.mileage - start_mileage
        if miles_driven > 0:
            cost_per_mile = total_cost_excl_purchase / miles_driven
    
    if equipment.hours and total_cost_excl_purchase > 0:
        cost_per_hour = total_cost_excl_purchase / equipment.hours
    
    # Monthly breakdown (SQLite-friendly strftime)
    monthly_costs = db.session.query(
        func.strftime('%Y-%m', MaintenanceRecord.service_date).label('month'),
        func.sum(MaintenanceRecord.cost).label('cost')
    ).filter_by(equipment_id=id).group_by('month').all()
    
    return render_template('equipment/cost_analysis.html',
                         equipment=equipment,
                         maintenance_cost=maintenance_cost,
                         fuel_cost=fuel_cost,
                         consumables_cost=consumables_cost,
                         wash_cost=wash_cost,
                         total_cost=total_cost_excl_purchase,           # keep legacy name if template expects it
                         total_cost_excl_purchase=total_cost_excl_purchase,
                         upfront_cost=upfront_cost,
                         tco_including_purchase=tco_including_purchase,
                         cost_per_mile=cost_per_mile,
                         cost_per_hour=cost_per_hour,
                         monthly_costs=monthly_costs,
                         active='equipment')


@equipment_bp.route('/<int:id>/maintenance/<int:record_id>/edit', methods=['GET', 'POST'])
def edit_maintenance(id, record_id):
    """Edit maintenance record with photo management"""
    equipment = Equipment.query.get_or_404(id)
    record = MaintenanceRecord.query.get_or_404(record_id)
    
    # Verify this record belongs to this equipment - FIX: ensure both are integers
    if int(record.equipment_id) != int(id):
        flash('Invalid maintenance record', 'error')
        return redirect(url_for('equipment.detail', id=id))
    
    if request.method == 'POST':
        # Update the record fields
        record.service_type = request.form.get('service_type')
        record.service_date = datetime.strptime(request.form.get('service_date'), '%Y-%m-%d').date()
        record.mileage_at_service = int(request.form.get('mileage_at_service')) if request.form.get('mileage_at_service') else None
        record.hours_at_service = float(request.form.get('hours_at_service')) if request.form.get('hours_at_service') else None
        record.cost = float(request.form.get('cost')) if request.form.get('cost') else None
        record.parts_used = request.form.get('parts_used')
        record.notes = request.form.get('notes')
        record.performed_by = request.form.get('performed_by', 'Self')
        
        # Update next service date - only if a new value is provided
        if request.form.get('next_service_months'):
            from dateutil.relativedelta import relativedelta
            months = int(request.form.get('next_service_months'))
            record.next_service_date = record.service_date + relativedelta(months=months)
        # Don't set to None if no value provided - preserve existing

        # Update next service mileage - only if a new value is provided
        if request.form.get('next_service_mileage'):
            record.next_service_mileage = int(request.form.get('next_service_mileage'))
        # Don't set to None if no value provided - preserve existing

        # Handle photo deletions
        photos_to_delete = request.form.get('photos_to_delete')
        if photos_to_delete:
            photo_ids = [int(pid) for pid in photos_to_delete.split(',') if pid]
            for photo_id in photo_ids:
                photo = MaintenancePhoto.query.get(photo_id)
                if photo and photo.maintenance_id == record.id:
                    # Delete file from filesystem
                    try:
                        photo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'maintenance_photos', photo.filename)
                        if os.path.exists(photo_path):
                            os.remove(photo_path)
                    except Exception as e:
                        print(f"Error deleting photo file: {e}")
                    # Delete from database
                    db.session.delete(photo)
        
        # Handle new photo uploads (same as add_maintenance)
        groups = [
            ('before', 'before_photos', 'before_captions'),
            ('after', 'after_photos', 'after_captions'),
            ('receipt', 'receipt_photos', 'receipt_captions'),
        ]
        for group_name, files_field, caps_field in groups:
            files = request.files.getlist(files_field)
            captions = request.form.getlist(caps_field)
            for idx, f in enumerate(files):
                if not (f and allowed_file(f.filename)):
                    continue
                filename = save_uploaded_photo(
                    f,
                    'maintenance_photos',
                    f"{equipment.name}_{record.service_type}_{group_name}"
                )
                caption = captions[idx] if idx < len(captions) else None
                photo = MaintenancePhoto(
                    maintenance_id=record.id,
                    filename=filename,
                    photo_type=group_name,
                    caption=caption
                )
                db.session.add(photo)
        
        # Update equipment mileage/hours if this is the most recent record
        latest_record = MaintenanceRecord.query.filter_by(
            equipment_id=id
        ).order_by(MaintenanceRecord.service_date.desc()).first()
        
        if latest_record and latest_record.id == record.id:
            if record.mileage_at_service:
                equipment.mileage = record.mileage_at_service
            if record.hours_at_service:
                equipment.hours = record.hours_at_service
        
        db.session.commit()
        flash('Maintenance record updated successfully!', 'success')
        return redirect(url_for('equipment.detail', id=id))
    
    # GET request - show the edit form
    return render_template('equipment/edit_maintenance.html',
                         equipment=equipment,
                         record=record,
                         service_types=SERVICE_TYPES,
                         active='equipment')


@equipment_bp.route('/<int:id>/maintenance/<int:record_id>/delete', methods=['POST'])
def delete_maintenance(id, record_id):
    """Delete maintenance record"""
    equipment = Equipment.query.get_or_404(id)
    record = MaintenanceRecord.query.get_or_404(record_id)
    
    # Verify this record belongs to this equipment
    if record.equipment_id != id:
        flash('Invalid maintenance record', 'error')
        return redirect(url_for('equipment.detail', id=id))
    
    # Delete associated photos from filesystem
    for photo in record.photos:
        try:
            photo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'maintenance_photos', photo.filename)
            if os.path.exists(photo_path):
                os.remove(photo_path)
        except Exception:
            pass
    
    # Delete the record from database
    db.session.delete(record)
    db.session.commit()
    
    flash('Maintenance record deleted successfully!', 'success')
    return redirect(url_for('equipment.detail', id=id))


# CAR WASH ROUTES

@equipment_bp.route('/<int:id>/car_wash/add', methods=['GET', 'POST'])
def add_car_wash(id):
    equipment = Equipment.query.get_or_404(id)
    
    if request.method == 'POST':
        wash = CarWashLog(
            equipment_id=id,
            date=datetime.strptime(request.form.get('date'), '%Y-%m-%d').date(),
            wash_type=request.form.get('wash_type'),
            location=request.form.get('location'),
            cost=float(request.form.get('cost', 0)),
            services=', '.join(request.form.getlist('services')),  # Combine checkboxes
            notes=request.form.get('notes')
        )
        
        # Handle photo upload if provided
        if 'photo' in request.files:
            photo = request.files['photo']
            if photo and photo.filename:
                filename = secure_filename(f"wash_{id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
                upload_dir = os.path.join(current_app.root_path, 'static', 'uploads')
                if not os.path.exists(upload_dir):
                    os.makedirs(upload_dir)
                photo_path = os.path.join(upload_dir, filename)
                photo.save(photo_path)
                wash.photo = filename
        
        db.session.add(wash)
        db.session.commit()
        flash('Car wash recorded successfully!', 'success')
        return redirect(url_for('equipment.car_wash_history', id=id))
    
    return render_template('equipment/add_car_wash.html',
                         equipment=equipment,
                         today=date.today())


@equipment_bp.route('/<int:id>/car_wash')
def car_wash_history(id):
    equipment = Equipment.query.get_or_404(id)
    washes = CarWashLog.query.filter_by(equipment_id=id).order_by(CarWashLog.date.desc()).all()
    
    # Calculate statistics
    total_spent = sum(w.cost for w in washes if w.cost)
    avg_cost = total_spent / len(washes) if washes else 0
    
    # Days since last wash
    if washes:
        last_wash = washes[0].date
        days_since_last = (date.today() - last_wash).days
    else:
        days_since_last = 'N/A'
    
    # Get unique wash types
    wash_types = list(set(w.wash_type for w in washes if w.wash_type))
    
    # Calculate type statistics
    type_stats = {}
    for wash_type in wash_types:
        type_washes = [w for w in washes if w.wash_type == wash_type]
        type_total = sum(w.cost for w in type_washes if w.cost)
        type_stats[wash_type] = {
            'count': len(type_washes),
            'total': type_total,
            'avg': type_total / len(type_washes) if type_washes else 0
        }
    
    # Calculate monthly spending
    monthly_spending = defaultdict(float)
    for wash in washes:
        if wash.cost:
            month_key = wash.date.strftime('%b %y')
            monthly_spending[month_key] += wash.cost
    
    # Get max for chart scaling
    max_monthly = max(monthly_spending.values()) if monthly_spending else 0
    
    return render_template('equipment/car_wash_history.html',
                         equipment=equipment,
                         washes=washes,
                         total_spent=total_spent,
                         avg_cost=avg_cost,
                         days_since_last=days_since_last,
                         wash_types=wash_types,
                         type_stats=type_stats,
                         monthly_spending=dict(monthly_spending),
                         max_monthly=max_monthly)


@equipment_bp.route('/car_wash/<int:id>/edit', methods=['GET', 'POST'])
def edit_car_wash(id):
    wash = CarWashLog.query.get_or_404(id)
    
    if request.method == 'POST':
        wash.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
        wash.wash_type = request.form.get('wash_type')
        wash.location = request.form.get('location')
        wash.cost = float(request.form.get('cost', 0))
        wash.services = ', '.join(request.form.getlist('services'))
        wash.notes = request.form.get('notes')
        
        db.session.commit()
        flash('Car wash updated successfully!', 'success')
        return redirect(url_for('equipment.car_wash_history', id=wash.equipment_id))
    
    # For GET request, render edit form (reuse add_car_wash.html with wash data)
    return render_template('equipment/add_car_wash.html',
                         equipment=wash.equipment,
                         wash=wash,
                         today=wash.date)


@equipment_bp.route('/car_wash/<int:id>/delete', methods=['POST'])
def delete_car_wash(id):
    wash = CarWashLog.query.get_or_404(id)
    equipment_id = wash.equipment_id
    
    db.session.delete(wash)
    db.session.commit()
    flash('Car wash record deleted.', 'success')
    
    return redirect(url_for('equipment.car_wash_history', id=equipment_id))


@equipment_bp.route('/<int:equipment_id>/photo/<int:photo_id>/delete', methods=['POST'])  
def delete_photo(equipment_id, photo_id):
    """Delete an equipment photo"""
    equipment = Equipment.query.get_or_404(equipment_id)
    photo = EquipmentPhoto.query.get_or_404(photo_id)
    
    # Verify this photo belongs to this equipment
    if photo.equipment_id != equipment_id:
        flash('Invalid photo', 'error')
        return redirect(url_for('equipment.detail', id=equipment_id))
    
    # Delete the file from filesystem
    try:
        photo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'equipment_profiles', photo.filename)
        if os.path.exists(photo_path):
            os.remove(photo_path)
    except Exception as e:
        print(f"Error deleting file: {e}")
    
    # Delete from database
    db.session.delete(photo)
    db.session.commit()
    
    flash('Photo deleted successfully', 'success')
    return redirect(url_for('equipment.detail', id=equipment_id))


@equipment_bp.route('/fuel/<int:fuel_id>/edit', methods=['GET', 'POST'])  
def edit_fuel(fuel_id):
    """Edit fuel record"""
    fuel_log = FuelLog.query.get_or_404(fuel_id)
    equipment = Equipment.query.get_or_404(fuel_log.equipment_id)
    
    if request.method == 'POST':
        # Update fuel log
        fuel_log.station_name = request.form.get('station_name')
        fuel_log.station_location = request.form.get('station_location')
        fuel_log.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
        fuel_log.fuel_type = request.form.get('fuel_type')
        fuel_log.gallons = float(request.form.get('gallons'))
        fuel_log.price_per_gallon = float(request.form.get('price_per_gallon'))
        fuel_log.total_cost = float(request.form.get('total_cost'))
        fuel_log.odometer = int(request.form.get('odometer')) if request.form.get('odometer') else None
        fuel_log.trip_purpose = request.form.get('trip_purpose')
        fuel_log.notes = request.form.get('notes')
        
        # Recalculate MPG if odometer changed
        if fuel_log.odometer:
            prev_log = FuelLog.query.filter(
                FuelLog.equipment_id == fuel_log.equipment_id,
                FuelLog.date < fuel_log.date,
                FuelLog.odometer.isnot(None)
            ).order_by(FuelLog.date.desc()).first()
            
            if prev_log and prev_log.odometer:
                fuel_log.trip_miles = fuel_log.odometer - prev_log.odometer
                if fuel_log.trip_miles > 0:
                    fuel_log.mpg = fuel_log.trip_miles / fuel_log.gallons
        
        # Update equipment mileage if this is the most recent log
        latest_log = FuelLog.query.filter_by(
            equipment_id=fuel_log.equipment_id
        ).order_by(FuelLog.date.desc()).first()
        
        if latest_log.id == fuel_log.id and fuel_log.odometer:
            equipment.mileage = fuel_log.odometer
        
        db.session.commit()
        flash('Fuel record updated successfully!', 'success')
        return redirect(url_for('equipment.fuel_history', id=fuel_log.equipment_id))
    
    return render_template('equipment/edit_fuel.html',
                         fuel_log=fuel_log,
                         equipment=equipment)


@equipment_bp.route('/fuel/<int:fuel_id>/delete', methods=['POST'])
def delete_fuel(fuel_id):
    """Delete fuel record"""
    fuel_log = FuelLog.query.get_or_404(fuel_id)
    equipment_id = fuel_log.equipment_id
    
    # Delete receipt photo if exists
    if fuel_log.receipt_photo:
        try:
            photo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'receipts', fuel_log.receipt_photo)
            if os.path.exists(photo_path):
                os.remove(photo_path)
        except Exception:
            pass
    
    # Recalculate MPG for next record if needed
    next_log = FuelLog.query.filter(
        FuelLog.equipment_id == equipment_id,
        FuelLog.date > fuel_log.date
    ).order_by(FuelLog.date).first()
    
    if next_log and next_log.odometer and fuel_log.odometer:
        # Find the previous log before the one being deleted
        prev_log = FuelLog.query.filter(
            FuelLog.equipment_id == equipment_id,
            FuelLog.date < fuel_log.date,
            FuelLog.odometer.isnot(None)
        ).order_by(FuelLog.date.desc()).first()
        
        if prev_log:
            next_log.trip_miles = next_log.odometer - prev_log.odometer
            if next_log.trip_miles > 0 and next_log.gallons > 0:
                next_log.mpg = next_log.trip_miles / next_log.gallons
    
    db.session.delete(fuel_log)
    db.session.commit()
    
    flash('Fuel record deleted successfully!', 'success')
    return redirect(url_for('equipment.fuel_history', id=equipment_id))