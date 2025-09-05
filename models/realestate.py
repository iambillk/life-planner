# models/realestate.py
"""
Real Estate Management Models
Version: 1.0.0
Created: 2025-01-03
Author: Life Management System

This module contains all database models for the Real Estate Management system,
including properties, maintenance records, vendors, and related entities.

CHANGELOG:
v1.0.0 (2025-01-03)
- Initial creation with Property, PropertyMaintenance, PropertyVendor models
- Added PropertyMaintenancePhoto for maintenance documentation
- Implemented maintenance categories and quick-task templates
- Added spend tracking by category
"""

from datetime import datetime, timedelta
from .base import db

# ==================== PROPERTY MODEL ====================
class Property(db.Model):
    """
    Main property entity - represents a house, cottage, rental, etc.
    Tracks basic info, key equipment details, and maintenance metadata
    """
    __tablename__ = 'properties'
    
    # ========== Primary Fields ==========
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # "Main House", "Lake Cottage", etc.
    address = db.Column(db.String(200))
    city = db.Column(db.String(100))
    state = db.Column(db.String(50))
    zip_code = db.Column(db.String(20))
    
    # ========== Property Details ==========
    property_type = db.Column(db.String(50), default='house')  # house, cottage, condo, rental, land
    square_footage = db.Column(db.Integer)
    lot_size_acres = db.Column(db.Float)
    year_built = db.Column(db.Integer)
    purchase_date = db.Column(db.Date)
    purchase_price = db.Column(db.Float)
    
    # ========== Key Equipment Info (Quick Reference) ==========
    # HVAC
    hvac_filter_size = db.Column(db.String(50))  # "20x25x1"
    hvac_filter_type = db.Column(db.String(50))  # "MERV 11"
    furnace_model = db.Column(db.String(100))
    ac_model = db.Column(db.String(100))
    
    # Generator
    generator_make = db.Column(db.String(50))
    generator_model = db.Column(db.String(100))
    generator_serial = db.Column(db.String(100))
    generator_install_date = db.Column(db.Date)
    
    # Water Systems
    water_heater_type = db.Column(db.String(50))  # "Gas", "Electric", "Tankless"
    water_heater_year = db.Column(db.Integer)
    water_softener_model = db.Column(db.String(100))
    water_filter_model = db.Column(db.String(100))
    septic_tank_size_gallons = db.Column(db.Integer)
    well_pump_model = db.Column(db.String(100))
    
    # ========== Photos & Documentation ==========
    profile_photo = db.Column(db.String(200))
    
    # ========== Status & Metadata ==========
    is_active = db.Column(db.Boolean, default=True)
    is_primary_residence = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # ========== Relationships ==========
    maintenance_records = db.relationship('PropertyMaintenance', 
                                         backref='property', 
                                         cascade='all, delete-orphan',
                                         order_by='PropertyMaintenance.date_completed.desc()')
    vendors = db.relationship('PropertyVendor', 
                            backref='property', 
                            cascade='all, delete-orphan')
    
    # ========== Calculated Properties ==========
    @property
    def days_since_last_maintenance(self):
        """Calculate days since last maintenance activity"""
        if self.maintenance_records:
            last_date = self.maintenance_records[0].date_completed
            return (datetime.utcnow().date() - last_date).days
        return None
    
    @property
    def upcoming_maintenance_count(self):
        """Count of maintenance tasks due in next 30 days"""
        count = 0
        for record in self.maintenance_records:
            if record.is_recurring and record.next_due_date:
                days_until = (record.next_due_date - datetime.utcnow().date()).days
                if 0 <= days_until <= 30:
                    count += 1
        return count
    
    @property
    def overdue_maintenance_count(self):
        """Count of overdue maintenance tasks"""
        count = 0
        for record in self.maintenance_records:
            if record.is_recurring and record.next_due_date:
                if record.next_due_date < datetime.utcnow().date():
                    count += 1
        return count


# ==================== MAINTENANCE RECORD MODEL ====================
class PropertyMaintenance(db.Model):
    """
    Tracks all maintenance activities for a property
    Includes both one-time and recurring tasks
    """
    __tablename__ = 'property_maintenance'
    
    # ========== Primary Fields ==========
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('properties.id'), nullable=False)
    
    # ========== Task Information ==========
    category = db.Column(db.String(50), nullable=False)  # HVAC, Plumbing, Lawn, Generator, etc.
    task = db.Column(db.String(200), nullable=False)  # "Changed AC Filter", "Mowed Lawn"
    description = db.Column(db.Text)  # Detailed notes about what was done
    
    # ========== When ==========
    date_completed = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    duration_minutes = db.Column(db.Integer)  # How long it took
    
    # ========== Who ==========
    performed_by = db.Column(db.String(100), default='Self')  # Self, vendor name, etc.
    vendor_id = db.Column(db.Integer, db.ForeignKey('property_vendors.id'))
    
    # ========== Cost Tracking ==========
    cost = db.Column(db.Float, default=0)
    cost_category = db.Column(db.String(50))  # 'DIY', 'Professional', 'Materials', 'Service'
    
    # ========== Supplies/Parts Used ==========
    supplies_used = db.Column(db.Text)  # JSON or comma-separated list
    part_number = db.Column(db.String(100))  # For filters, parts, etc.
    
    # ========== Recurring Task Fields ==========
    is_recurring = db.Column(db.Boolean, default=False)
    interval_days = db.Column(db.Integer)  # How often this should be done
    interval_months = db.Column(db.Integer)  # Alternative to days
    next_due_date = db.Column(db.Date)  # When it's due again
    
    # ========== Conditions (for lawn care, exterior work) ==========
    weather_conditions = db.Column(db.String(50))  # Sunny, Rainy, etc.
    temperature = db.Column(db.Integer)  # Temperature when work was done
    
    # ========== Documentation ==========
    notes = db.Column(db.Text)
    warranty_info = db.Column(db.Text)
    warranty_expiration = db.Column(db.Date)
    
    # ========== Metadata ==========
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # ========== Relationships ==========
    photos = db.relationship('PropertyMaintenancePhoto', 
                            backref='maintenance', 
                            cascade='all, delete-orphan')
    
    # ========== Helper Methods ==========
    def calculate_next_due(self):
        """Calculate next due date based on interval"""
        if not self.is_recurring:
            return None
            
        if self.interval_days:
            self.next_due_date = self.date_completed + timedelta(days=self.interval_days)
        elif self.interval_months:
            # Handle month intervals (approximate as 30 days per month)
            self.next_due_date = self.date_completed + timedelta(days=self.interval_months * 30)
        
        return self.next_due_date
    
    @property
    def is_overdue(self):
        """Check if this recurring task is overdue"""
        if self.is_recurring and self.next_due_date:
            return self.next_due_date < datetime.utcnow().date()
        return False
    
    @property
    def days_until_due(self):
        """Calculate days until this task is due"""
        if self.is_recurring and self.next_due_date:
            return (self.next_due_date - datetime.utcnow().date()).days
        return None


# ==================== VENDOR/CONTRACTOR MODEL ====================
class PropertyVendor(db.Model):
    """
    Stores vendor/contractor information for each property
    Simple contact management - "who's my plumber?" etc.
    """
    __tablename__ = 'property_vendors'
    
    # ========== Primary Fields ==========
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('properties.id'), nullable=False)
    
    # ========== Company Information ==========
    company_name = db.Column(db.String(100), nullable=False)
    contact_name = db.Column(db.String(100))  # Specific person at company
    service_type = db.Column(db.String(50), nullable=False)  # Plumber, Electrician, HVAC, etc.
    
    # ========== Contact Information ==========
    phone_primary = db.Column(db.String(20))
    phone_secondary = db.Column(db.String(20))  # Emergency/cell
    email = db.Column(db.String(100))
    website = db.Column(db.String(200))
    address = db.Column(db.String(200))
    
    # ========== Account Information ==========
    account_number = db.Column(db.String(50))  # Your account # with them
    
    # ========== Service Details ==========
    is_preferred = db.Column(db.Boolean, default=False)  # Your go-to vendor
    is_emergency = db.Column(db.Boolean, default=False)  # Available for emergencies
    hourly_rate = db.Column(db.Float)
    
    # ========== Notes & Rating ==========
    notes = db.Column(db.Text)  # "Expensive but reliable", "Cash discount", etc.
    rating = db.Column(db.Integer)  # 1-5 stars
    
    # ========== Metadata ==========
    last_service_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # ========== Relationships ==========
    maintenance_records = db.relationship('PropertyMaintenance', 
                                         backref='vendor', 
                                         foreign_keys='PropertyMaintenance.vendor_id')


# ==================== MAINTENANCE PHOTO MODEL ====================
class PropertyMaintenancePhoto(db.Model):
    """
    Stores photos for maintenance records
    Before/after photos, equipment labels, damage documentation, etc.
    """
    __tablename__ = 'property_maintenance_photos'
    
    id = db.Column(db.Integer, primary_key=True)
    maintenance_id = db.Column(db.Integer, 
                             db.ForeignKey('property_maintenance.id'), 
                             nullable=False)
    
    filename = db.Column(db.String(200), nullable=False)
    caption = db.Column(db.String(200))
    photo_type = db.Column(db.String(50))  # 'before', 'after', 'receipt', 'damage', 'parts'
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


# ==================== QUICK TASK TEMPLATE MODEL ====================
class MaintenanceTemplate(db.Model):
    """
    Pre-defined maintenance tasks for quick entry
    Builds a library of common tasks as you use the system
    """
    __tablename__ = 'maintenance_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # ========== Task Definition ==========
    category = db.Column(db.String(50), nullable=False)
    task_name = db.Column(db.String(200), nullable=False)
    
    # ========== Default Values ==========
    default_interval_days = db.Column(db.Integer)
    typical_duration_minutes = db.Column(db.Integer)
    typical_cost = db.Column(db.Float)
    
    # ========== Instructions/Notes ==========
    instructions = db.Column(db.Text)
    supplies_needed = db.Column(db.Text)
    
    # ========== Usage Tracking ==========
    times_used = db.Column(db.Integer, default=0)
    last_used = db.Column(db.DateTime)
    
    # ========== Metadata ==========
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ==================== MAINTENANCE CATEGORIES ====================
# These will be used in forms and dropdowns
MAINTENANCE_CATEGORIES = [
    'HVAC',
    'Plumbing',
    'Electrical',
    'Generator',
    'Lawn & Yard',
    'Exterior',
    'Interior',
    'Roof & Gutters',
    'Appliances',
    'Pool/Spa',
    'Septic/Sewer',
    'Security',
    'Seasonal',
    'Other'
]

# Common cost categories for spend tracking
COST_CATEGORIES = [
    'DIY Materials',
    'Professional Service',
    'Parts & Supplies',
    'Emergency Repair',
    'Routine Maintenance',
    'Major Repair',
    'Upgrade/Improvement'
]

# Service types for vendors
VENDOR_SERVICE_TYPES = [
    'Plumber',
    'Electrician',
    'HVAC',
    'Lawn Care',
    'Tree Service',
    'Handyman',
    'Roofer',
    'Painter',
    'Generator Service',
    'Septic Service',
    'Pest Control',
    'Pool Service',
    'Snow Removal',
    'Gutter Service',
    'Appliance Repair',
    'General Contractor',
    'Other'
]