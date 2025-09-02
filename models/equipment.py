from datetime import datetime
from .base import db

class Equipment(db.Model):
    __tablename__ = 'equipment'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    make = db.Column(db.String(50))
    model = db.Column(db.String(50))
    year = db.Column(db.Integer)
    serial_number = db.Column(db.String(100))
    purchase_date = db.Column(db.Date)
    purchase_price = db.Column(db.Float)
    
    # Current status
    hours = db.Column(db.Float, default=0)
    mileage = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), default='active')
    location = db.Column(db.String(100))
    
    # Photos
    profile_photo = db.Column(db.String(200))
    
    # Metadata
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    maintenance_records = db.relationship('MaintenanceRecord', backref='equipment', cascade='all, delete-orphan')
    photos = db.relationship('EquipmentPhoto', backref='equipment', cascade='all, delete-orphan')
    reminders = db.relationship('MaintenanceReminder', backref='equipment', cascade='all, delete-orphan')
    maintenance_records = db.relationship('MaintenanceRecord', backref='equipment', cascade='all, delete-orphan')
    photos = db.relationship('EquipmentPhoto', backref='equipment', cascade='all, delete-orphan')
    reminders = db.relationship('MaintenanceReminder', backref='equipment', cascade='all, delete-orphan')
    fuel_logs = db.relationship('FuelLog', backref='equipment', cascade='all, delete-orphan')
    consumable_logs = db.relationship('ConsumableLog', backref='equipment', cascade='all, delete-orphan')
    wash_logs = db.relationship('CarWashLog', backref='equipment', cascade='all, delete-orphan')

class MaintenanceRecord(db.Model):
    __tablename__ = 'maintenance_records'
    
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id'), nullable=False)
    
    service_type = db.Column(db.String(100), nullable=False)
    service_date = db.Column(db.Date, default=datetime.utcnow)
    
    hours_at_service = db.Column(db.Float)
    mileage_at_service = db.Column(db.Integer)
    
    cost = db.Column(db.Float)
    parts_used = db.Column(db.Text)
    notes = db.Column(db.Text)
    performed_by = db.Column(db.String(100))
    
    next_service_date = db.Column(db.Date)
    next_service_hours = db.Column(db.Float)
    next_service_mileage = db.Column(db.Integer)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    photos = db.relationship('MaintenancePhoto', backref='maintenance_record', cascade='all, delete-orphan')

class MaintenanceReminder(db.Model):
    __tablename__ = 'maintenance_reminders'
    
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id'), nullable=False)
    
    reminder_type = db.Column(db.String(50))
    service_type = db.Column(db.String(100))
    
    trigger_date = db.Column(db.Date)
    trigger_mileage = db.Column(db.Integer)
    trigger_hours = db.Column(db.Float)
    trigger_season = db.Column(db.String(20))
    
    is_active = db.Column(db.Boolean, default=True)
    last_reminded = db.Column(db.DateTime)
    completed = db.Column(db.Boolean, default=False)
    
    notes = db.Column(db.Text)

class EquipmentPhoto(db.Model):
    __tablename__ = 'equipment_photos'
    
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id'), nullable=False)
    
    filename = db.Column(db.String(200), nullable=False)
    caption = db.Column(db.String(200))
    photo_type = db.Column(db.String(50))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

class MaintenancePhoto(db.Model):
    __tablename__ = 'maintenance_photos'
    
    id = db.Column(db.Integer, primary_key=True)
    maintenance_id = db.Column(db.Integer, db.ForeignKey('maintenance_records.id'), nullable=False)
    
    filename = db.Column(db.String(200), nullable=False)
    caption = db.Column(db.String(200))
    photo_type = db.Column(db.String(50))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

# ========== NEW MODELS ==========

class FuelLog(db.Model):
    __tablename__ = 'fuel_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id'), nullable=False)
    
    # Fuel purchase details
    date = db.Column(db.DateTime, default=datetime.utcnow)
    station_name = db.Column(db.String(100))
    station_location = db.Column(db.String(200))
    
    # Fuel data
    gallons = db.Column(db.Float, nullable=False)
    price_per_gallon = db.Column(db.Float, nullable=False)
    total_cost = db.Column(db.Float, nullable=False)
    fuel_type = db.Column(db.String(20))  # Regular, Premium, Diesel
    
    # Mileage tracking
    odometer = db.Column(db.Integer)
    trip_miles = db.Column(db.Float)  # Calculated from last fill-up
    mpg = db.Column(db.Float)  # Calculated
    
    # Additional
    trip_purpose = db.Column(db.String(50))  # Personal, Business, Mixed
    notes = db.Column(db.Text)
    receipt_photo = db.Column(db.String(200))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ConsumableLog(db.Model):
    __tablename__ = 'consumable_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id'), nullable=False)
    
    # Item details
    item_type = db.Column(db.String(50), nullable=False)  # Oil, Washer Fluid, Wipers, etc.
    brand = db.Column(db.String(50))
    quantity = db.Column(db.Float)
    unit = db.Column(db.String(20))  # quarts, gallons, each
    
    # Cost
    cost = db.Column(db.Float)
    
    # When/Where
    date = db.Column(db.Date, default=datetime.utcnow)
    vendor = db.Column(db.String(100))
    
    # Tracking
    odometer = db.Column(db.Integer)
    notes = db.Column(db.Text)
    receipt_photo = db.Column(db.String(200))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CarWashLog(db.Model):
    __tablename__ = 'car_wash_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id'), nullable=False)
    
    date = db.Column(db.Date, default=datetime.utcnow)
    wash_type = db.Column(db.String(50))  # Self-serve, Automatic, Detail
    location = db.Column(db.String(100))
    cost = db.Column(db.Float)
    services = db.Column(db.Text)  # What was included
    notes = db.Column(db.Text)
    photo = db.Column(db.String(200))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Receipt(db.Model):
    __tablename__ = 'receipts'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Link to source
    module = db.Column(db.String(50))  # equipment, projects, etc.
    record_type = db.Column(db.String(50))  # maintenance, fuel, consumable
    record_id = db.Column(db.Integer)  # ID in the source table
    
    # Receipt data
    filename = db.Column(db.String(200), nullable=False)
    vendor = db.Column(db.String(100))
    amount = db.Column(db.Float)
    date = db.Column(db.Date)
    
    # OCR data
    ocr_text = db.Column(db.Text)  # Full extracted text
    ocr_processed = db.Column(db.Boolean, default=False)
    
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
