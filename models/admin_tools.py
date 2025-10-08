# models/admin_tools.py
"""
Admin Tools Models
Database models for diagnostic tool history and knowledge base
Version: 1.0.0
Created: 2025-01-08
"""

from models.base import db
from datetime import datetime
from sqlalchemy import Index


class ToolExecution(db.Model):
    """History of all diagnostic tool executions"""
    __tablename__ = 'tool_executions'
    
    id = db.Column(db.Integer, primary_key=True)
    tool_name = db.Column(db.String(50), nullable=False)  # ping, traceroute, whois, etc.
    target = db.Column(db.String(255))  # IP, domain, etc.
    parameters = db.Column(db.Text)  # JSON string of all parameters used
    output = db.Column(db.Text)  # Full command output
    exit_code = db.Column(db.Integer)  # 0 = success, non-zero = error
    execution_time = db.Column(db.Float)  # Seconds to execute
    executed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    notes = db.Column(db.Text)  # User's quick notes about this execution
    
    # For linking to knowledge base items
    related_items = db.relationship('KnowledgeRelation', 
                                   foreign_keys='KnowledgeRelation.tool_execution_id',
                                   backref='tool_execution', 
                                   lazy='dynamic',
                                   cascade='all, delete-orphan')
    
    # Indexes for fast searching
    __table_args__ = (
        Index('idx_tool_target', 'tool_name', 'target'),
        Index('idx_executed_at', 'executed_at'),
    )
    
    def __repr__(self):
        return f'<ToolExecution {self.tool_name} → {self.target} at {self.executed_at}>'
    
    @property
    def success(self):
        """Check if execution was successful"""
        return self.exit_code == 0
    
    @classmethod
    def get_recent(cls, tool_name=None, limit=50):
        """Get recent executions, optionally filtered by tool"""
        query = cls.query
        if tool_name:
            query = query.filter_by(tool_name=tool_name)
        return query.order_by(cls.executed_at.desc()).limit(limit).all()
    
    @classmethod
    def search(cls, target=None, tool_name=None, days=30):
        """Search execution history"""
        query = cls.query
        
        if target:
            query = query.filter(cls.target.ilike(f'%{target}%'))
        
        if tool_name:
            query = query.filter_by(tool_name=tool_name)
        
        if days:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = query.filter(cls.executed_at >= cutoff)
        
        return query.order_by(cls.executed_at.desc()).all()


class KnowledgeCategory(db.Model):
    """Categories for organizing knowledge base items"""
    __tablename__ = 'knowledge_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    icon = db.Column(db.String(10), default='📁')
    description = db.Column(db.Text)
    parent_id = db.Column(db.Integer, db.ForeignKey('knowledge_categories.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Self-referential relationship for nested categories
    children = db.relationship('KnowledgeCategory', 
                              backref=db.backref('parent', remote_side=[id]),
                              lazy='dynamic')
    
    items = db.relationship('KnowledgeItem', backref='category', lazy='dynamic')
    
    def __repr__(self):
        return f'<KnowledgeCategory {self.name}>'


class KnowledgeItem(db.Model):
    """Files, configs, cheat sheets, logs, etc."""
    __tablename__ = 'knowledge_items'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    
    # Content can be either stored inline OR as a file
    content_type = db.Column(db.String(20), nullable=False)  # 'text', 'file', 'url'
    content_text = db.Column(db.Text)  # For pasted content
    file_path = db.Column(db.String(500))  # For uploaded files
    file_size = db.Column(db.Integer)  # File size in bytes
    mime_type = db.Column(db.String(100))
    
    # Organization
    category_id = db.Column(db.Integer, db.ForeignKey('knowledge_categories.id'))
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    version = db.Column(db.Integer, default=1)  # For tracking config versions
    is_pinned = db.Column(db.Boolean, default=False)
    access_count = db.Column(db.Integer, default=0)  # Track usage
    last_accessed = db.Column(db.DateTime)
    
    # Relationships
    tags = db.relationship('KnowledgeTag', secondary='knowledge_item_tags', 
                          backref=db.backref('items', lazy='dynamic'))
    
    related_from = db.relationship('KnowledgeRelation', 
                                  foreign_keys='KnowledgeRelation.item_id',
                                  backref='item', 
                                  lazy='dynamic',
                                  cascade='all, delete-orphan')
    
    # Indexes
    __table_args__ = (
        Index('idx_title', 'title'),
        Index('idx_created_at', 'created_at'),
        Index('idx_pinned', 'is_pinned'),
    )
    
    def __repr__(self):
        return f'<KnowledgeItem {self.title}>'
    
    def increment_access(self):
        """Track when item is accessed"""
        self.access_count += 1
        self.last_accessed = datetime.utcnow()
        db.session.commit()
    
    @classmethod
    def get_pinned(cls):
        """Get all pinned items"""
        return cls.query.filter_by(is_pinned=True).order_by(cls.title).all()
    
    @classmethod
    def get_recent(cls, limit=10):
        """Get recently accessed items"""
        return cls.query.filter(cls.last_accessed.isnot(None))\
                       .order_by(cls.last_accessed.desc()).limit(limit).all()
    
    @classmethod
    def search(cls, query_text, category_id=None, tags=None):
        """Full-text search across knowledge base"""
        query = cls.query
        
        if query_text:
            search_term = f'%{query_text}%'
            query = query.filter(
                db.or_(
                    cls.title.ilike(search_term),
                    cls.description.ilike(search_term),
                    cls.content_text.ilike(search_term)
                )
            )
        
        if category_id:
            query = query.filter_by(category_id=category_id)
        
        if tags:
            # Filter by tags (tags is a list of tag names)
            for tag_name in tags:
                query = query.join(cls.tags).filter(KnowledgeTag.name == tag_name)
        
        return query.order_by(cls.updated_at.desc()).all()


class KnowledgeTag(db.Model):
    """Tags for flexible organization"""
    __tablename__ = 'knowledge_tags'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    color = db.Column(db.String(7), default='#6ea8ff')  # Hex color
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<KnowledgeTag {self.name}>'
    
    @classmethod
    def get_or_create(cls, name):
        """Get existing tag or create new one"""
        tag = cls.query.filter_by(name=name.lower().strip()).first()
        if not tag:
            tag = cls(name=name.lower().strip())
            db.session.add(tag)
            db.session.commit()
        return tag


# Association table for many-to-many relationship between items and tags
knowledge_item_tags = db.Table('knowledge_item_tags',
    db.Column('item_id', db.Integer, db.ForeignKey('knowledge_items.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('knowledge_tags.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
)


class KnowledgeRelation(db.Model):
    """Link related items together (e.g., config → related tool execution)"""
    __tablename__ = 'knowledge_relations'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('knowledge_items.id'), nullable=False)
    
    # Can link to either another knowledge item OR a tool execution
    related_item_id = db.Column(db.Integer, db.ForeignKey('knowledge_items.id'))
    tool_execution_id = db.Column(db.Integer, db.ForeignKey('tool_executions.id'))
    
    relation_type = db.Column(db.String(50))  # 'related_to', 'version_of', 'referenced_by', etc.
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<KnowledgeRelation {self.item_id} → {self.related_item_id or self.tool_execution_id}>'


def init_admin_tools():
    """Initialize default categories"""
    
    # Check if categories already exist
    if KnowledgeCategory.query.count() > 0:
        return
    
    categories = [
        {'name': 'Network Documentation', 'icon': '🌐', 'description': 'IP schemas, VLAN maps, network diagrams'},
        {'name': 'Configs & Backups', 'icon': '💾', 'description': 'Switch configs, router backups, firewall rules'},
        {'name': 'Logs', 'icon': '📋', 'description': 'SSH logs, system logs, diagnostic outputs'},
        {'name': 'Cheat Sheets', 'icon': '📝', 'description': 'Command references, quick guides'},
        {'name': 'ISOs & Media', 'icon': '📀', 'description': 'Installation files, license keys'},
        {'name': 'Scripts & Commands', 'icon': '🔧', 'description': 'PowerShell, Bash, one-liners'},
        {'name': 'Vendor Info', 'icon': '🏷️', 'description': 'Model numbers, serials, warranties'},
    ]
    
    for cat_data in categories:
        cat = KnowledgeCategory(**cat_data)
        db.session.add(cat)
    
    db.session.commit()
    print("✅ Admin Tools categories initialized")


# Add this to your models/__init__.py imports later