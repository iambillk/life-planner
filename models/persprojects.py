# models/persprojects.py
from datetime import datetime
from models.base import db

class PersonalProject(db.Model):
    __tablename__ = 'personal_projects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, critical
    goal = db.Column(db.Text)
    motivation = db.Column(db.Text)
    strategy = db.Column(db.Text)
    status = db.Column(db.String(20), default='active')  # planning, active, on_hold, completed
    deadline = db.Column(db.Date)
    progress = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tasks = db.relationship('PersonalTask', backref='project', cascade='all, delete-orphan')
    ideas = db.relationship('PersonalIdea', backref='project', cascade='all, delete-orphan')
    milestones = db.relationship('PersonalMilestone', backref='project', cascade='all, delete-orphan')
    notes = db.relationship('PersonalProjectNote', backref='project', cascade='all, delete-orphan')
    files = db.relationship('PersonalProjectFile', backref='project', cascade='all, delete-orphan')

class PersonalTask(db.Model):
    __tablename__ = 'personal_tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('personal_projects.id'), nullable=False)
    content = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50))
    completed = db.Column(db.Boolean, default=False)
    order_num = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

class PersonalIdea(db.Model):
    __tablename__ = 'personal_ideas'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('personal_projects.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='new')  # new, considering, implemented, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PersonalMilestone(db.Model):
    __tablename__ = 'personal_milestones'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('personal_projects.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    target_date = db.Column(db.Date)
    completed = db.Column(db.Boolean, default=False)
    completed_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PersonalProjectNote(db.Model):
    __tablename__ = 'personal_project_notes'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('personal_projects.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default='general')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PersonalProjectFile(db.Model):
    __tablename__ = 'personal_project_files'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('personal_projects.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)  # Stored filename
    original_name = db.Column(db.String(255), nullable=False)  # Original filename
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)