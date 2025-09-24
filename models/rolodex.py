# models/rolodex.py
from datetime import datetime, date
from models.base import db  # import your SQLAlchemy instance

class Company(db.Model):
    __tablename__ = 'companies'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    website = db.Column(db.String(255))
    phone = db.Column(db.String(64))
    tags = db.Column(db.String(255), default='')          # comma-separated
    notes = db.Column(db.Text, default='')
    logo = db.Column(db.String(255))
    industry = db.Column(db.String(100))
    size = db.Column(db.String(50))
    address = db.Column(db.String(255))
    linkedin = db.Column(db.String(255))
    twitter = db.Column(db.String(255))
    archived = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    # relationship to contacts
    contacts = db.relationship('Contact', backref='company', lazy='dynamic')
    
    def __repr__(self):
        return f"<Company {self.name}>"


class Contact(db.Model):
    __tablename__ = 'contacts'
    
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(120), default='')
    last_name = db.Column(db.String(120), default='')
    display_name = db.Column(db.String(255), nullable=False, index=True)
    title = db.Column(db.String(120), default='')
    email = db.Column(db.String(255), index=True)
    phone = db.Column(db.String(64), index=True)
    tags = db.Column(db.String(255), default='')
    notes = db.Column(db.Text, default='')
    archived = db.Column(db.Boolean, default=False, index=True)
    profile_photo = db.Column(db.String(255))
    
    # Physical Address
    street_address = db.Column(db.String(255))
    address_line_2 = db.Column(db.String(255))
    city = db.Column(db.String(100))
    state = db.Column(db.String(50))
    zip_code = db.Column(db.String(20))
    country = db.Column(db.String(100))
    
    # Additional Contact Methods
    mobile_phone = db.Column(db.String(64))
    work_phone = db.Column(db.String(64))
    home_phone = db.Column(db.String(64))
    personal_email = db.Column(db.String(255))
    website = db.Column(db.String(255))
    
    # Social/Digital
    linkedin_url = db.Column(db.String(255))
    twitter_url = db.Column(db.String(255))
    facebook_url = db.Column(db.String(255))
    instagram_url = db.Column(db.String(255))
    github_url = db.Column(db.String(255))
    
    # Important Dates
    birthday = db.Column(db.Date)
    anniversary = db.Column(db.Date)
    
    # Personal Details
    spouse_name = db.Column(db.String(120))
    children_names = db.Column(db.Text)  # Can store multiple names separated by commas
    assistant_name = db.Column(db.String(120))
    business_card_photo = db.Column(db.String(255))
    
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    def __repr__(self):
        return f"<Contact {self.display_name}>"