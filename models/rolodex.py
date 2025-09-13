# models/rolodex.py
from datetime import datetime
from models.base import db  # import your SQLAlchemy instance


class Company(db.Model):
    __tablename__ = 'companies'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    website = db.Column(db.String(255))
    phone = db.Column(db.String(64))
    tags = db.Column(db.String(255), default='')          # comma-separated
    notes = db.Column(db.Text, default='')
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
    tags = db.Column(db.String(255), default='')          # comma-separated
    notes = db.Column(db.Text, default='')
    archived = db.Column(db.Boolean, default=False, index=True)

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
