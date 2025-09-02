from datetime import datetime
from .base import db

class Goal(db.Model):
    __tablename__ = 'goals'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    target_date = db.Column(db.Date)
    progress = db.Column(db.Integer, default=0)
    category = db.Column(db.String(50))