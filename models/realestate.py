# models/realestate.py
from datetime import datetime
from models.base import db


class Property(db.Model):
    __tablename__ = "properties"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)

    # Location
    address = db.Column(db.String(255))
    city = db.Column(db.String(120))
    state = db.Column(db.String(120))
    zip_code = db.Column(db.String(20))
    country = db.Column(db.String(120))
    county = db.Column(db.String(120))
    township = db.Column(db.String(120))

    # Type & size
    property_type = db.Column(db.String(50))
    square_footage = db.Column(db.Integer)
    lot_size_acres = db.Column(db.Float)
    year_built = db.Column(db.Integer)

    # Purchase info
    purchase_date = db.Column(db.Date)
    purchase_price = db.Column(db.Float)

    # Media & notes
    profile_photo = db.Column(db.String(255))
    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class PropertyVendor(db.Model):
    __tablename__ = "property_vendors"

    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(
        db.Integer, db.ForeignKey("properties.id"), nullable=False
    )
    company_name = db.Column(db.String(120), nullable=False)
    service_type = db.Column(db.String(120))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(120))
    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    property = db.relationship(
        "Property", backref=db.backref("vendors", lazy=True)
    )


class PropertyMaintenance(db.Model):
    __tablename__ = "property_maintenance"

    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(
        db.Integer, db.ForeignKey("properties.id"), nullable=False
    )
    category = db.Column(db.String(120), nullable=False)
    task = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    date_completed = db.Column(db.Date)
    performed_by = db.Column(db.String(120))
    cost = db.Column(db.Float)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    property = db.relationship(
        "Property", backref=db.backref("maintenance", lazy=True)
    )


class PropertyMaintenancePhoto(db.Model):
    __tablename__ = "property_maintenance_photos"

    id = db.Column(db.Integer, primary_key=True)
    maintenance_id = db.Column(
        db.Integer, db.ForeignKey("property_maintenance.id"), nullable=False
    )
    filename = db.Column(db.String(255), nullable=False)
    photo_type = db.Column(db.String(50), default="general")  # general | receipt
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    maintenance = db.relationship(
        "PropertyMaintenance", backref=db.backref("photos", lazy=True)
    )


class MaintenanceTemplate(db.Model):
    __tablename__ = "maintenance_templates"

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(120), nullable=False)
    task_name = db.Column(db.String(255), nullable=False)
    default_interval_days = db.Column(db.Integer)
    typical_cost = db.Column(db.Float)
    times_used = db.Column(db.Integer, default=0)
    last_used = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


# ---------------- NEW: Outbuildings ----------------

class PropertyOutbuilding(db.Model):
    __tablename__ = "property_outbuildings"

    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(
        db.Integer, db.ForeignKey("properties.id"), nullable=False
    )

    name = db.Column(db.String(120), nullable=False)  # e.g., "Pole Barn"
    type = db.Column(db.String(50))                   # Garage, MIL Suite, Pole Barn, Shed, Coop, Greenhouse, Other
    square_footage = db.Column(db.Integer)
    year_built = db.Column(db.Integer)
    notes = db.Column(db.Text)

    profile_photo = db.Column(db.String(255))         # optional thumbnail

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    property = db.relationship(
        "Property", backref=db.backref("outbuildings", lazy=True)
    )
