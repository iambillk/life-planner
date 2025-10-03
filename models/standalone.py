# models/standalone.py
from datetime import datetime
from models.base import db

class StandaloneTask(db.Model):
    __tablename__ = 'standalone_tasks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    priority = db.Column(db.String(20), default='medium', nullable=False)
    due_date = db.Column(db.Date)
    notes = db.Column(db.Text)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)