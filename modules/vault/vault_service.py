# modules/vault/vault_service.py - UPDATED VERSION
"""
Vault Service Layer
Bridge between vault and other modules
"""

from models.vault import VaultDocument, VaultLink, VaultTag, VaultFolder, vault_document_tags
from models.base import db
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import mimetypes

UPLOAD_FOLDER = os.path.join('static', 'vault_files')
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_or_create_entity_folder(entity_type, entity_id, entity_name=None):
    """Get or create a folder for a specific entity"""
    
    # First, get or create the parent folder for this entity type
    parent_folder_name = entity_type.capitalize()  # "property" -> "Property"
    parent_folder = VaultFolder.query.filter_by(
        name=parent_folder_name,
        parent_id=None
    ).first()
    
    if not parent_folder:
        # Create parent folder for this module
        parent_folder = VaultFolder(
            name=parent_folder_name,
            icon='🏠' if entity_type == 'property' else '📋' if entity_type == 'project' else '📁'
        )
        db.session.add(parent_folder)
        db.session.flush()
    
    # Now get or create the specific entity folder
    # Use the entity name if provided, otherwise create a generic name
    if entity_name:
        folder_name = entity_name
    else:
        folder_name = f"{parent_folder_name} #{entity_id}"
    
    entity_folder = VaultFolder.query.filter_by(
        name=folder_name,
        parent_id=parent_folder.id
    ).first()
    
    if not entity_folder:
        entity_folder = VaultFolder(
            name=folder_name,
            parent_id=parent_folder.id,
            icon='🏡' if entity_type == 'property' else '📂'
        )
        db.session.add(entity_folder)
        db.session.flush()
    
    return entity_folder  # This returns the child folder, not the parent

def create_document_from_file(file, title=None, doc_type='document', tags=None, folder_id=None):
    """Create a vault document from an uploaded file"""
    if not file or not file.filename:
        return None
    
    if not allowed_file(file.filename):
        raise ValueError(f"File type not allowed: {file.filename}")
    
    # Create upload folder if needed
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # Generate safe filename
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    name_part, ext = os.path.splitext(filename)
    safe_filename = f"{name_part}_{timestamp}{ext}"
    
    # Save file
    filepath = os.path.join(UPLOAD_FOLDER, safe_filename)
    file.save(filepath)
    
    # Create document
    doc = VaultDocument(
        title=title or file.filename,
        file_path=filepath,
        file_name=file.filename,
        file_size=os.path.getsize(filepath),
        mime_type=mimetypes.guess_type(filepath)[0],
        doc_type=doc_type,
        folder_id=folder_id,  # Use the folder
        search_text=f"{title or file.filename}"
    )
    
    db.session.add(doc)
    db.session.flush()  # Get the ID without committing
    
    # Add tags if provided
    if tags:
        for tag_name in tags:
            tag = VaultTag.query.filter_by(name=tag_name.lower()).first()
            if not tag:
                tag = VaultTag(name=tag_name.lower())
                db.session.add(tag)
            doc.tags.append(tag)
    
    return doc

def create_document_for_entity(file, entity_type, entity_id, entity_name=None, title=None, doc_type='document', tags=None):
    """Create a document and automatically place it in the entity's folder"""
    
    # Get or create the folder for this entity
    folder = get_or_create_entity_folder(entity_type, entity_id, entity_name)
    
    # Create the document in that folder
    doc = create_document_from_file(
        file=file,
        title=title,
        doc_type=doc_type,
        tags=tags,
        folder_id=folder.id
    )
    
    # Link to the entity
    if doc:
        link_document_to_entity(
            doc_id=doc.id,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_title=entity_name
        )
    
    return doc

def link_document_to_entity(doc_id, entity_type, entity_id, entity_title=None):
    """Create a link between a document and an entity"""
    # Check if link already exists
    existing = VaultLink.query.filter_by(
        document_id=doc_id,
        link_type=entity_type,
        link_id=entity_id
    ).first()
    
    if existing:
        return existing
    
    link = VaultLink(
        document_id=doc_id,
        link_type=entity_type,
        link_id=entity_id,
        link_title=entity_title
    )
    db.session.add(link)
    return link

def get_entity_documents(entity_type, entity_id):
    """Get all documents linked to an entity"""
    links = VaultLink.query.filter_by(
        link_type=entity_type,
        link_id=entity_id
    ).all()
    
    # Return documents with their link info
    documents = []
    for link in links:
        if link.document and not link.document.archived:
            documents.append(link.document)
    
    return documents

def unlink_document_from_entity(doc_id, entity_type, entity_id):
    """Remove a link between document and entity"""
    link = VaultLink.query.filter_by(
        document_id=doc_id,
        link_type=entity_type,
        link_id=entity_id
    ).first()
    
    if link:
        db.session.delete(link)
        return True
    return False