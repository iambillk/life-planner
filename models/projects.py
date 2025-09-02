from datetime import datetime
from .base import db

class TCHProject(db.Model):
    __tablename__ = 'tch_projects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='active')
    deadline = db.Column(db.Date)
    progress = db.Column(db.Integer, default=0)

class PersonalProject(db.Model):
    __tablename__ = 'personal_projects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='active')
    deadline = db.Column(db.Date)
    progress = db.Column(db.Integer, default=0)