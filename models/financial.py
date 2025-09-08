# models/financial.py
"""
Financial Tracking Models
Version: 1.0.0
Created: 2025-01-07

Simple but effective spending tracker for credit card transactions.
Tracks transactions across two cards with customizable categories.
"""

from datetime import datetime
from models.base import db

class SpendingCategory(db.Model):
    """Spending categories - both predefined and custom"""
    __tablename__ = 'spending_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    is_custom = db.Column(db.Boolean, default=False)  # True if user-added
    color = db.Column(db.String(7), default='#6ea8ff')  # For charts
    icon = db.Column(db.String(10), default='💰')  # Fun visual
    usage_count = db.Column(db.Integer, default=0)  # Track popularity
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    transactions = db.relationship('Transaction', backref='category', lazy='dynamic')
    
    def __repr__(self):
        return f'<SpendingCategory {self.name}>'


class Transaction(db.Model):
    """Individual credit card transactions"""
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    amount = db.Column(db.Float, nullable=False)
    merchant = db.Column(db.String(100), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('spending_categories.id'))
    card = db.Column(db.String(20), nullable=False)  # 'Amex' or 'Other'
    notes = db.Column(db.Text)
    receipt_photo = db.Column(db.String(255))  # Optional receipt image
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Transaction ${self.amount} at {self.merchant}>'
    
    @property
    def month_year(self):
        """Helper for grouping by month"""
        return self.date.strftime('%B %Y')
    
    @property
    def formatted_amount(self):
        """Display amount as currency"""
        return f"${self.amount:,.2f}"


class MerchantAlias(db.Model):
    """Map different merchant names to a canonical name"""
    __tablename__ = 'merchant_aliases'
    
    id = db.Column(db.Integer, primary_key=True)
    alias = db.Column(db.String(100), nullable=False)  # What appears on statement
    canonical_name = db.Column(db.String(100), nullable=False)  # What we display
    default_category_id = db.Column(db.Integer, db.ForeignKey('spending_categories.id'))
    
    def __repr__(self):
        return f'<MerchantAlias {self.alias} -> {self.canonical_name}>'