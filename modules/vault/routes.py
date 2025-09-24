# modules/vault/routes.py
"""
Document Vault Routes - Fixed version
Handles document upload, search, viewing, and organization
"""

from flask import render_template, request, redirect, url_for, flash, jsonify, send_file, current_app
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from sqlalchemy import or_, func, desc
import os
import mimetypes
import json

from models.base import db
from models.vault import (
    VaultDocument, VaultFolder, VaultTag, VaultLink, 
    VaultVersion, VaultSearch, vault_document_tags
)
from . import vault_bp


# File upload configuration
ALLOWED_EXTENSIONS = {
    'txt', 'md', 'pdf', 'doc', 'docx', 'xls', 'xlsx',
    'png', 'jpg', 'jpeg', 'gif', 'svg',
    'py', 'js', 'html', 'css', 'json', 'yaml', 'yml',
    'sh', 'bash', 'ps1', 'sql', 'conf', 'config',
    'log', 'csv', 'xml', 'ini', 'env'
}

UPLOAD_FOLDER = os.path.join('static', 'vault_files')


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def detect_doc_type(filename, mime_type=None):
    """Detect document type from filename or mime type"""
    if not filename:
        return 'note'
    
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    # Code files
    if ext in ['py', 'js', 'html', 'css', 'php', 'java', 'c', 'cpp', 'h', 'sh', 'bash', 'ps1']:
        return 'code'
    
    # Config files
    if ext in ['conf', 'config', 'ini', 'yaml', 'yml', 'json', 'xml', 'env']:
        return 'config'
    
    # Documents
    if ext in ['pdf', 'doc', 'docx', 'txt', 'md']:
        return 'document'
    
    # Data files
    if ext in ['csv', 'xls', 'xlsx', 'sql']:
        return 'data'
    
    # Images
    if ext in ['png', 'jpg', 'jpeg', 'gif', 'svg', 'bmp']:
        return 'image'
    
    # Scripts
    if ext in ['sh', 'bash', 'ps1', 'bat']:
        return 'script'
    
    return 'file'


def get_file_icon(doc_type):
    """Return emoji icon for document type"""
    icons = {
        'code': '💻',
        'config': '⚙️',
        'document': '📄',
        'data': '📊',
        'image': '🖼️',
        'script': '🔧',
        'note': '📝',
        'file': '📎',
        'contract': '📜',
        'manual': '📖'
    }
    return icons.get(doc_type, '📎')


# Custom template filter
@vault_bp.app_template_filter('file_icon')
def file_icon_filter(doc_type):
    """Template filter for file icons"""
    return get_file_icon(doc_type)


@vault_bp.app_template_filter('time_ago')
def time_ago_filter(dt):
    """Convert datetime to time ago string"""
    if not dt:
        return 'Unknown'
    
    now = datetime.utcnow()
    diff = now - dt
    
    seconds = diff.total_seconds()
    minutes = seconds / 60
    hours = minutes / 60
    days = hours / 24
    
    if minutes < 1:
        return 'just now'
    elif minutes < 60:
        return f'{int(minutes)} min ago'
    elif hours < 24:
        return f'{int(hours)} hr ago'
    elif days < 7:
        return f'{int(days)} days ago'
    else:
        return dt.strftime('%b %d, %Y')


# ==================== MAIN VIEWS ====================

@vault_bp.route('/')
def index():
    """Main vault dashboard"""
    # Get pinned documents
    pinned_docs = db.session.query(VaultDocument).filter_by(
        pinned=True, archived=False
    ).all()
    
    # Get recent documents (last 10)
    recent_docs = db.session.query(VaultDocument).filter_by(
        archived=False
    ).order_by(desc(VaultDocument.accessed_at)).limit(10).all()
    
    # Get folders
    folders = db.session.query(VaultFolder).filter_by(
        parent_id=None
    ).order_by(VaultFolder.order_num, VaultFolder.name).all()
    
    # Get popular tags
    popular_tags = db.session.query(
        VaultTag.name,
        VaultTag.color,
        func.count(vault_document_tags.c.document_id).label('count')
    ).join(
        vault_document_tags
    ).group_by(
        VaultTag.id, VaultTag.name, VaultTag.color
    ).order_by(
        desc('count')
    ).limit(10).all()
    
    # Get recent searches
    recent_searches = db.session.query(VaultSearch).order_by(
        desc(VaultSearch.created_at)
    ).limit(5).all()
    
    return render_template('vault/index.html',
        pinned_docs=pinned_docs,
        recent_docs=recent_docs,
        folders=folders,
        popular_tags=popular_tags,
        recent_searches=recent_searches
    )


@vault_bp.route('/search')
def search():
    """Search documents"""
    query = request.args.get('q', '').strip()
    folder_id = request.args.get('folder')
    tag = request.args.get('tag')
    doc_type = request.args.get('type')
    
    if not query and not folder_id and not tag and not doc_type:
        return redirect(url_for('vault.index'))
    
    # Build query
    documents = db.session.query(VaultDocument).filter_by(archived=False)
    
    if query:
        # Save search for history
        search_record = VaultSearch(query=query)
        db.session.add(search_record)
        
        # Search in title, content, and search_text
        search_filter = or_(
            VaultDocument.title.ilike(f'%{query}%'),
            VaultDocument.content.ilike(f'%{query}%'),
            VaultDocument.search_text.ilike(f'%{query}%'),
            VaultDocument.file_name.ilike(f'%{query}%')
        )
        documents = documents.filter(search_filter)
    
    if folder_id:
        documents = documents.filter_by(folder_id=folder_id)
    
    if tag:
        documents = documents.join(vault_document_tags).join(VaultTag).filter(VaultTag.name == tag)
    
    if doc_type:
        documents = documents.filter_by(doc_type=doc_type)
    
    # Execute query
    results = documents.order_by(desc(VaultDocument.updated_at)).all()
    
    # Update search result count
    if query:
        search_record.result_count = len(results)
        db.session.commit()
    
    return render_template('vault/search.html',
        query=query,
        results=results,
        folder_id=folder_id,
        tag=tag,
        doc_type=doc_type
    )


@vault_bp.route('/document/<int:id>')
def view_document(id):
    """View a single document"""
    doc = db.session.query(VaultDocument).get(id)
    if not doc:
        flash('Document not found', 'error')
        return redirect(url_for('vault.index'))
    
    # Update accessed timestamp
    doc.accessed_at = datetime.utcnow()
    db.session.commit()
    
    # Get related documents (same folder or tags)
    related = []
    if doc.folder_id:
        related = db.session.query(VaultDocument).filter(
            VaultDocument.folder_id == doc.folder_id,
            VaultDocument.id != doc.id,
            VaultDocument.archived == False
        ).limit(5).all()
    
    return render_template('vault/document.html',
        doc=doc,
        related=related,
        file_icon=get_file_icon(doc.doc_type)
    )


# ==================== CREATE/EDIT ====================

@vault_bp.route('/create', methods=['GET', 'POST'])
def create_document():
    """Create a new document"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        folder_id = request.form.get('folder_id')
        doc_type = request.form.get('doc_type', 'note')
        tags = request.form.get('tags', '').strip()
        pinned = request.form.get('pinned') == 'on'
        
        if not title:
            flash('Title is required', 'error')
            return redirect(url_for('vault.create_document'))
        
        # Create document
        doc = VaultDocument(
            title=title,
            content=content,
            folder_id=folder_id if folder_id else None,
            doc_type=doc_type,
            pinned=pinned,
            search_text=f"{title} {content}"  # Simple search text
        )
        
        # Handle file upload if present
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename and allowed_file(file.filename):
                # Create upload folder if it doesn't exist
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                
                # Generate secure filename
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                name_part, ext = os.path.splitext(filename)
                filename = f"{name_part}_{timestamp}{ext}"
                
                # Save file
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)
                
                # Update document
                doc.file_path = filepath
                doc.file_name = file.filename
                doc.file_size = os.path.getsize(filepath)
                doc.mime_type = mimetypes.guess_type(filepath)[0]
                
                # Auto-detect type if not set
                if doc_type == 'note':
                    doc.doc_type = detect_doc_type(file.filename, doc.mime_type)
        
        db.session.add(doc)
        db.session.flush()  # Get the ID
        
        # Handle tags
        if tags:
            tag_names = [t.strip() for t in tags.split(',') if t.strip()]
            for tag_name in tag_names:
                # Get or create tag
                tag = db.session.query(VaultTag).filter_by(name=tag_name.lower()).first()
                if not tag:
                    tag = VaultTag(name=tag_name.lower())
                    db.session.add(tag)
                doc.tags.append(tag)
                tag.usage_count += 1
        
        db.session.commit()
        flash('Document created successfully', 'success')
        return redirect(url_for('vault.view_document', id=doc.id))
    
    # GET request
    folders = db.session.query(VaultFolder).order_by(VaultFolder.name).all()
    return render_template('vault/create.html', folders=folders)


@vault_bp.route('/document/<int:id>/edit', methods=['GET', 'POST'])
def edit_document(id):
    """Edit a document"""
    doc = db.session.query(VaultDocument).get(id)
    if not doc:
        flash('Document not found', 'error')
        return redirect(url_for('vault.index'))
    
    if request.method == 'POST':
        # Save current version before updating
        if doc.content != request.form.get('content'):
            version = VaultVersion(
                document_id=doc.id,
                version_number=(len(doc.versions) + 1),
                content=doc.content,
                file_path=doc.file_path,
                change_note=request.form.get('change_note', 'Content updated')
            )
            db.session.add(version)
        
        # Update document
        doc.title = request.form.get('title', '').strip()
        doc.content = request.form.get('content', '').strip()
        doc.folder_id = request.form.get('folder_id') or None
        doc.doc_type = request.form.get('doc_type', 'note')
        doc.pinned = request.form.get('pinned') == 'on'
        doc.updated_at = datetime.utcnow()
        doc.search_text = f"{doc.title} {doc.content}"
        
        # Update tags
        doc.tags.clear()
        tags = request.form.get('tags', '').strip()
        if tags:
            tag_names = [t.strip() for t in tags.split(',') if t.strip()]
            for tag_name in tag_names:
                tag = db.session.query(VaultTag).filter_by(name=tag_name.lower()).first()
                if not tag:
                    tag = VaultTag(name=tag_name.lower())
                    db.session.add(tag)
                doc.tags.append(tag)
        
        db.session.commit()
        flash('Document updated successfully', 'success')
        return redirect(url_for('vault.view_document', id=doc.id))
    
    # GET request
    folders = db.session.query(VaultFolder).order_by(VaultFolder.name).all()
    current_tags = ', '.join([t.name for t in doc.tags])
    
    return render_template('vault/edit.html',
        doc=doc,
        folders=folders,
        current_tags=current_tags
    )


@vault_bp.route('/upload', methods=['POST'])
def upload_file():
    """Quick file upload endpoint"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if not file or not file.filename:
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400
    
    # Create upload folder if it doesn't exist
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # Generate secure filename
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    name_part, ext = os.path.splitext(filename)
    safe_filename = f"{name_part}_{timestamp}{ext}"
    
    # Save file
    filepath = os.path.join(UPLOAD_FOLDER, safe_filename)
    file.save(filepath)
    
    # Create document
    doc = VaultDocument(
        title=file.filename,
        file_path=filepath,
        file_name=file.filename,
        file_size=os.path.getsize(filepath),
        mime_type=mimetypes.guess_type(filepath)[0],
        doc_type=detect_doc_type(file.filename),
        search_text=file.filename
    )
    
    db.session.add(doc)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'id': doc.id,
        'title': doc.title,
        'url': url_for('vault.view_document', id=doc.id)
    })


# ==================== ACTIONS ====================

@vault_bp.route('/document/<int:id>/pin', methods=['POST'])
def toggle_pin(id):
    """Toggle document pin status"""
    doc = db.session.query(VaultDocument).get(id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404
    
    doc.pinned = not doc.pinned
    db.session.commit()
    
    return jsonify({'pinned': doc.pinned})


@vault_bp.route('/document/<int:id>/archive', methods=['POST'])
def archive_document(id):
    """Archive a document"""
    doc = db.session.query(VaultDocument).get(id)
    if not doc:
        flash('Document not found', 'error')
        return redirect(url_for('vault.index'))
    
    doc.archived = True
    db.session.commit()
    
    flash('Document archived', 'success')
    return redirect(url_for('vault.index'))


@vault_bp.route('/document/<int:id>/delete', methods=['POST'])
def delete_document(id):
    """Delete a document"""
    doc = db.session.query(VaultDocument).get(id)
    if not doc:
        flash('Document not found', 'error')
        return redirect(url_for('vault.index'))
    
    # Delete file if exists
    if doc.file_path and os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except:
            pass  # File might be locked or already deleted
    
    # Delete from database
    db.session.delete(doc)
    db.session.commit()
    
    flash('Document deleted', 'success')
    return redirect(url_for('vault.index'))


@vault_bp.route('/document/<int:id>/download')
def download_file(id):
    """Download a document's file"""
    doc = db.session.query(VaultDocument).get(id)
    if not doc:
        flash('Document not found', 'error')
        return redirect(url_for('vault.index'))
    
    if not doc.file_path or not os.path.exists(doc.file_path):
        flash('File not found', 'error')
        return redirect(url_for('vault.view_document', id=id))
    
    return send_file(doc.file_path, as_attachment=True, download_name=doc.file_name)


# ==================== FOLDER MANAGEMENT ====================

@vault_bp.route('/folders')
def manage_folders():
    """Manage folders"""
    folders = db.session.query(VaultFolder).order_by(
        VaultFolder.parent_id, VaultFolder.order_num, VaultFolder.name
    ).all()
    return render_template('vault/folders.html', folders=folders)


@vault_bp.route('/folder/create', methods=['POST'])
def create_folder():
    """Create a new folder"""
    name = request.form.get('name', '').strip()
    icon = request.form.get('icon', '📁')
    parent_id = request.form.get('parent_id')
    
    if not name:
        flash('Folder name is required', 'error')
        return redirect(url_for('vault.manage_folders'))
    
    folder = VaultFolder(
        name=name,
        icon=icon,
        parent_id=parent_id if parent_id else None
    )
    
    db.session.add(folder)
    db.session.commit()
    
    flash('Folder created', 'success')
    return redirect(url_for('vault.manage_folders'))

@vault_bp.route('/folder/<int:id>/delete', methods=['POST'])
def delete_folder(id):
    """Delete an empty folder"""
    folder = db.session.query(VaultFolder).get(id)
    
    if not folder:
        flash('Folder not found', 'error')
        return redirect(url_for('vault.manage_folders'))
    
    # Check if folder has documents
    if folder.documents:
        flash('Cannot delete folder with documents', 'error')
        return redirect(url_for('vault.manage_folders'))
    
    # Check if folder has subfolders
    if db.session.query(VaultFolder).filter_by(parent_id=folder.id).first():
        flash('Cannot delete folder with subfolders', 'error')
        return redirect(url_for('vault.manage_folders'))
    
    # Delete the folder
    db.session.delete(folder)
    db.session.commit()
    
    flash('Folder deleted', 'success')
    return redirect(url_for('vault.manage_folders'))


# ==================== API ENDPOINTS ====================

@vault_bp.route('/api/tags')
def api_tags():
    """Get all tags for autocomplete"""
    tags = db.session.query(VaultTag).order_by(desc(VaultTag.usage_count)).all()
    return jsonify([{'name': t.name, 'count': t.usage_count} for t in tags])


@vault_bp.route('/api/search')
def api_search():
    """Quick search API"""
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify([])
    
    documents = db.session.query(VaultDocument).filter(
        VaultDocument.archived == False,
        or_(
            VaultDocument.title.ilike(f'%{query}%'),
            VaultDocument.search_text.ilike(f'%{query}%')
        )
    ).limit(10).all()
    
    results = []
    for doc in documents:
        results.append({
            'id': doc.id,
            'title': doc.title,
            'type': doc.doc_type,
            'icon': get_file_icon(doc.doc_type),
            'url': url_for('vault.view_document', id=doc.id)
        })
    
    return jsonify(results)