from datetime import datetime
from .base import db

class DailyTask(db.Model):
    __tablename__ = 'daily_tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    task = db.Column(db.String(200), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    date = db.Column(db.Date, default=datetime.utcnow)
    priority = db.Column(db.String(20), default='medium')