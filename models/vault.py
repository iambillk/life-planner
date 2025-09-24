# models/vault.py
"""
Document Vault Models
For storing and organizing documents, code snippets, configs, and reference materials
"""

from datetime import datetime
from models.base import db


class VaultFolder(db.Model):
    """Folders for organizing documents"""
    __tablename__ = 'vault_folders'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(10), default='📁')  # emoji icon
    parent_id = db.Column(db.Integer, db.ForeignKey('vault_folders.id'))
    order_num = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    children = db.relationship('VaultFolder', backref=db.backref('parent', remote_side=[id]))
    documents = db.relationship('VaultDocument', backref='folder', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<VaultFolder {self.name}>'


class VaultDocument(db.Model):
    """Main document storage"""
    __tablename__ = 'vault_documents'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    content = db.Column(db.Text)  # For text/code/markdown
    file_path = db.Column(db.String(500))  # For uploaded files
    file_name = db.Column(db.String(255))  # Original filename
    file_size = db.Column(db.Integer)  # Size in bytes
    mime_type = db.Column(db.String(100))  # application/pdf, text/plain, etc.
    
    # Document type for better categorization
    doc_type = db.Column(db.String(50))  # code, config, contract, manual, note, etc.
    
    # Organization
    folder_id = db.Column(db.Integer, db.ForeignKey('vault_folders.id'))
    pinned = db.Column(db.Boolean, default=False, index=True)
    archived = db.Column(db.Boolean, default=False, index=True)
    
    # Metadata
    expires_at = db.Column(db.Date)  # For contracts, warranties, etc.
    
    # Search optimization
    search_text = db.Column(db.Text)  # Combined searchable content
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    accessed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    tags = db.relationship('VaultTag', secondary='vault_document_tags', backref='documents')
    links = db.relationship('VaultLink', backref='document', cascade='all, delete-orphan')
    versions = db.relationship('VaultVersion', backref='document', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<VaultDocument {self.title}>'


class VaultTag(db.Model):
    """Tags for documents"""
    __tablename__ = 'vault_tags'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True, index=True)
    color = db.Column(db.String(7), default='#6ea8ff')  # hex color
    usage_count = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<VaultTag {self.name}>'


# Association table for many-to-many relationship
vault_document_tags = db.Table('vault_document_tags',
    db.Column('document_id', db.Integer, db.ForeignKey('vault_documents.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('vault_tags.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
)


class VaultLink(db.Model):
    """Links between documents and other modules"""
    __tablename__ = 'vault_links'
    
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('vault_documents.id'), nullable=False)
    
    # Link to other modules
    link_type = db.Column(db.String(50))  # contact, company, property, project, etc.
    link_id = db.Column(db.Integer)  # ID in the linked table
    link_title = db.Column(db.String(255))  # Cached title for display
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<VaultLink {self.link_type}:{self.link_id}>'


class VaultVersion(db.Model):
    """Version history for documents"""
    __tablename__ = 'vault_versions'
    
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('vault_documents.id'), nullable=False)
    
    version_number = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text)  # Stored content at this version
    file_path = db.Column(db.String(500))  # Stored file at this version
    change_note = db.Column(db.String(255))  # What changed
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100))  # For future multi-user support
    
    def __repr__(self):
        return f'<VaultVersion {self.document_id}:v{self.version_number}>'


class VaultSearch(db.Model):
    """Recent searches for quick access"""
    __tablename__ = 'vault_searches'
    
    id = db.Column(db.Integer, primary_key=True)
    query = db.Column(db.String(255), nullable=False)
    result_count = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<VaultSearch {self.query}>'