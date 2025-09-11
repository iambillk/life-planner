# models/projects.py - Complete file with file attachments
from datetime import datetime
from .base import db

class TCHProject(db.Model):
    __tablename__ = 'tch_projects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    goal = db.Column(db.Text)  # Main goal/objective
    motivation = db.Column(db.Text)  # Why this project matters
    strategy = db.Column(db.Text)  # How to achieve the goal
    
    # Category field
    category = db.Column(db.String(50), default='General')
    
    # Dates
    start_date = db.Column(db.Date, default=datetime.utcnow)
    deadline = db.Column(db.Date)
    completed_date = db.Column(db.Date)
    
    # Status and Progress
    status = db.Column(db.String(20), default='planning')  # planning, active, on_hold, completed, cancelled
    progress = db.Column(db.Integer, default=0)  # Auto-calculated from tasks
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, critical
    
    # Retrospective
    what_worked = db.Column(db.Text)
    what_was_hard = db.Column(db.Text)
    lessons_learned = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tasks = db.relationship('TCHTask', backref='project', cascade='all, delete-orphan', order_by='TCHTask.order_num')
    ideas = db.relationship('TCHIdea', backref='project', cascade='all, delete-orphan')
    milestones = db.relationship('TCHMilestone', backref='project', cascade='all, delete-orphan', order_by='TCHMilestone.target_date')
    notes = db.relationship('TCHProjectNote', backref='project', cascade='all, delete-orphan')
    files = db.relationship('ProjectFile', 
                           primaryjoin="and_(TCHProject.id==ProjectFile.project_id, ProjectFile.project_type=='tch')",
                           foreign_keys='ProjectFile.project_id',
                           cascade='all, delete-orphan',
                           viewonly=True)

class TCHTask(db.Model):
    __tablename__ = 'tch_tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('tch_projects.id'), nullable=False)
    
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    completed = db.Column(db.Boolean, default=False)
    completed_date = db.Column(db.DateTime)
    
    # Task organization
    category = db.Column(db.String(50))  # To group similar tasks
    order_num = db.Column(db.Integer, default=0)  # For manual ordering
    priority = db.Column(db.String(20), default='medium')
    
    # Optional due date for individual tasks
    due_date = db.Column(db.Date)
    
    # Who's responsible
    assigned_to = db.Column(db.String(100))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Sub-tasks relationship
    parent_id = db.Column(db.Integer, db.ForeignKey('tch_tasks.id'))
    subtasks = db.relationship('TCHTask', backref=db.backref('parent', remote_side=[id]))

class TCHIdea(db.Model):
    __tablename__ = 'tch_ideas'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('tch_projects.id'), nullable=False)
    
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='new')  # new, considered, implemented, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TCHMilestone(db.Model):
    __tablename__ = 'tch_milestones'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('tch_projects.id'), nullable=False)
    
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    target_date = db.Column(db.Date)
    completed = db.Column(db.Boolean, default=False)
    completed_date = db.Column(db.Date)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TCHProjectNote(db.Model):
    __tablename__ = 'tch_project_notes'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('tch_projects.id'), nullable=False)
    
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50))  # general, meeting, technical, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# NEW MODEL FOR FILE ATTACHMENTS
class ProjectFile(db.Model):
    """Simple file attachment for projects"""
    __tablename__ = 'project_files'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, nullable=False)
    project_type = db.Column(db.String(20), nullable=False)  # 'tch' or 'personal'
    filename = db.Column(db.String(255), nullable=False)  # Stored filename
    original_name = db.Column(db.String(255), nullable=False)  # Original filename
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ProjectFile {self.original_name}>'