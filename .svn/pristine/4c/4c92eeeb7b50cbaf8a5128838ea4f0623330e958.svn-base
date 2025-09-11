# models/todo.py
from datetime import datetime
from .base import db

class TodoList(db.Model):
    """A todo list that can be standalone or attached to a project"""
    __tablename__ = 'todo_lists'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
    # Attachment fields - can link to different modules
    module = db.Column(db.String(50))  # 'tch_project', 'personal_project', or None for standalone
    module_id = db.Column(db.Integer)  # ID of the linked item
    
    # List properties
    color = db.Column(db.String(20), default='yellow')  # Like sticky note colors
    is_pinned = db.Column(db.Boolean, default=False)
    is_archived = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    items = db.relationship('TodoItem', backref='todo_list', cascade='all, delete-orphan', order_by='TodoItem.order_num')
    
    @property
    def completion_percentage(self):
        if not self.items:
            return 0
        completed = sum(1 for item in self.items if item.completed)
        return int((completed / len(self.items)) * 100)
    
    @property
    def completed_count(self):
        return sum(1 for item in self.items if item.completed)
    
    @property
    def total_count(self):
        return len(self.items)

class TodoItem(db.Model):
    """Individual items in a todo list"""
    __tablename__ = 'todo_items'
    
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey('todo_lists.id'), nullable=False)
    
    content = db.Column(db.String(500), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)
    
    # Organization
    order_num = db.Column(db.Integer, default=0)
    priority = db.Column(db.Boolean, default=False)  # High priority flag
    
    # Optional fields
    due_date = db.Column(db.Date)
    note = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)