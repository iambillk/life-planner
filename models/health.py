from datetime import datetime
from .base import db

class WeightEntry(db.Model):
    __tablename__ = 'weight_entries'
    
    id = db.Column(db.Integer, primary_key=True)
    weight = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow)
    notes = db.Column(db.Text)