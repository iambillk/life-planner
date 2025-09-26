# modules/vault/routes.py
"""
Document Vault Routes - Enhanced version
Handles document upload, search, viewing, and organization
"""

from flask import render_template, request, redirect, url_for, flash, jsonify, send_file, current_app
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from sqlalchemy import or_, func, desc, and_
import os
import mimetypes
import json

from models.base import db
from models.vault import (
    VaultDocument, VaultFolder, VaultTag, VaultLink, 
    VaultVersion, VaultSearch, vault_document_tags
)
from . import vault_bp  # THIS IS THE CRITICAL IMPORT YOU NEED


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
    """Enhanced vault dashboard with stats, all tags, and filters"""
    
    # ==================== BASIC DATA ====================
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
    
    # ==================== COMPREHENSIVE STATS ====================
    # Total document count
    total_documents = db.session.query(VaultDocument).filter_by(
        archived=False
    ).count()
    
    # Calculate total storage used (in MB)
    total_size_bytes = db.session.query(
        func.sum(VaultDocument.file_size)
    ).filter_by(archived=False).scalar() or 0
    total_size_mb = round(total_size_bytes / (1024 * 1024), 2)
    
    # Average file size (in KB)
    if total_documents > 0:
        avg_file_size = round((total_size_bytes / total_documents) / 1024, 1)
    else:
        avg_file_size = 0
    
    # Pinned count
    pinned_count = len(pinned_docs)
    
    # Documents added this week
    week_ago = datetime.utcnow() - timedelta(days=7)
    new_this_week = db.session.query(VaultDocument).filter(
        VaultDocument.archived == False,
        VaultDocument.created_at >= week_ago
    ).count()
    
    # Documents expiring soon (within 30 days)
    thirty_days_later = datetime.utcnow() + timedelta(days=30)
    expiring_soon = db.session.query(VaultDocument).filter(
        VaultDocument.archived == False,
        VaultDocument.expires_at != None,
        VaultDocument.expires_at <= thirty_days_later
    ).count()
    
    # Documents accessed today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    accessed_today = db.session.query(VaultDocument).filter(
        VaultDocument.archived == False,
        VaultDocument.accessed_at >= today_start
    ).count()
    
    # ==================== DOCUMENT TYPE BREAKDOWN ====================
    # Count documents by type for filters
    type_counts_raw = db.session.query(
        VaultDocument.doc_type,
        func.count(VaultDocument.id).label('count')
    ).filter_by(archived=False).group_by(
        VaultDocument.doc_type
    ).all()
    
    # Convert to dict for easy template access
    type_counts = {doc_type: count for doc_type, count in type_counts_raw}
    
    # Find most common type
    if type_counts:
        most_common_type = max(type_counts, key=type_counts.get)
        most_common_type = most_common_type.title() if most_common_type else 'Note'
    else:
        most_common_type = 'Note'
    
    # ==================== COMPLETE TAGS CLOUD ====================
    # Get ALL tags with their usage counts (not just top 10)
    all_tags = db.session.query(
        VaultTag.name,
        VaultTag.color,
        func.count(vault_document_tags.c.document_id).label('count')
    ).join(
        vault_document_tags
    ).group_by(
        VaultTag.id, VaultTag.name, VaultTag.color
    ).order_by(
        desc('count')  # Order by usage, most used first
    ).all()
    
    # Also keep popular_tags for backward compatibility
    popular_tags = all_tags[:10] if all_tags else []
    
    # ==================== RECENT SEARCHES ====================
    recent_searches = db.session.query(VaultSearch).order_by(
        desc(VaultSearch.created_at)
    ).limit(5).all()
    
    # ==================== RECENT ACTIVITY TIMELINE ====================
    # Build activity timeline (last 10 activities)
    recent_activity = []
    
    # Get recent uploads (created documents)
    recent_uploads = db.session.query(VaultDocument).filter_by(
        archived=False
    ).order_by(desc(VaultDocument.created_at)).limit(5).all()
    
    for doc in recent_uploads:
        time_diff = datetime.utcnow() - doc.created_at
        if time_diff.days > 0:
            time_str = f"{time_diff.days}d ago"
        elif time_diff.seconds > 3600:
            time_str = f"{time_diff.seconds // 3600}h ago"
        else:
            time_str = f"{time_diff.seconds // 60}m ago"
        
        recent_activity.append({
            'icon': '📤',
            'text': f"Uploaded {doc.title[:30]}{'...' if len(doc.title) > 30 else ''}",
            'time': time_str
        })
    
    # Get recent edits (updated documents)
    recent_edits = db.session.query(VaultDocument).filter(
        VaultDocument.archived == False,
        VaultDocument.updated_at != VaultDocument.created_at  # Only edited docs
    ).order_by(desc(VaultDocument.updated_at)).limit(5).all()
    
    for doc in recent_edits:
        time_diff = datetime.utcnow() - doc.updated_at
        if time_diff.days > 0:
            time_str = f"{time_diff.days}d ago"
        elif time_diff.seconds > 3600:
            time_str = f"{time_diff.seconds // 3600}h ago"
        else:
            time_str = f"{time_diff.seconds // 60}m ago"
        
        recent_activity.append({
            'icon': '✏️',
            'text': f"Edited {doc.title[:30]}{'...' if len(doc.title) > 30 else ''}",
            'time': time_str
        })
    
    # Sort activity by time and limit to 5 most recent
    recent_activity.sort(key=lambda x: x['time'])
    recent_activity = recent_activity[:5]
    
    # ==================== RENDER TEMPLATE WITH ALL DATA ====================
    return render_template('vault/index.html',
        # Basic data (original variables preserved)
        pinned_docs=pinned_docs,
        recent_docs=recent_docs,
        folders=folders,
        recent_searches=recent_searches,
        popular_tags=popular_tags,  # Keep for backward compatibility
        
        # Stats dashboard data (all new)
        total_documents=total_documents,
        total_size_mb=total_size_mb,
        avg_file_size=avg_file_size,
        pinned_count=pinned_count,
        new_this_week=new_this_week,
        expiring_soon=expiring_soon,
        accessed_today=accessed_today,
        most_common_type=most_common_type,
        
        # Type counts for filters
        type_counts=type_counts,
        
        # Complete tags cloud
        all_tags=all_tags,
        
        # Activity timeline
        recent_activity=recent_activity
    )


# Keep ALL your existing routes below this point unchanged
# Just copy them as they are from your original file

@vault_bp.route('/search')
def search():
    """Enhanced search with date filtering"""
    query = request.args.get('q', '').strip()
    folder_id = request.args.get('folder')
    tag = request.args.get('tag')
    doc_type = request.args.get('type')
    date_range = request.args.get('date_range')  # New parameter
    
    if not query and not folder_id and not tag and not doc_type and not date_range:
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
    
    # Date range filter (new)
    if date_range:
        today = datetime.utcnow()
        if date_range == 'today':
            start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
            documents = documents.filter(VaultDocument.updated_at >= start_date)
        elif date_range == 'week':
            start_date = today - timedelta(days=7)
            documents = documents.filter(VaultDocument.updated_at >= start_date)
        elif date_range == 'month':
            start_date = today - timedelta(days=30)
            documents = documents.filter(VaultDocument.updated_at >= start_date)
        elif date_range == 'year':
            start_date = today - timedelta(days=365)
            documents = documents.filter(VaultDocument.updated_at >= start_date)
    
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
        doc_type=doc_type,
        date_range=date_range
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
# Add these routes to your routes.py file after the create_document route
# These are all the missing routes that the template references

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
    """Enhanced quick search API with better results"""
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify([])
    
    # Search with more context
    documents = db.session.query(VaultDocument).filter(
        VaultDocument.archived == False,
        or_(
            VaultDocument.title.ilike(f'%{query}%'),
            VaultDocument.content.ilike(f'%{query}%'),
            VaultDocument.search_text.ilike(f'%{query}%'),
            VaultDocument.file_name.ilike(f'%{query}%')
        )
    ).limit(10).all()
    
    results = []
    for doc in documents:
        # Build preview text
        preview = ''
        if doc.content:
            preview = doc.content[:100] + '...' if len(doc.content) > 100 else doc.content
        elif doc.file_name:
            preview = f"File: {doc.file_name}"
        
        results.append({
            'id': doc.id,
            'title': doc.title,
            'type': doc.doc_type,
            'icon': get_file_icon(doc.doc_type),
            'url': url_for('vault.view_document', id=doc.id),
            'preview': preview,
            'folder': doc.folder.name if doc.folder else None
        })
    
    return jsonify(results)


# Enhanced API search is already in your file above


# ==================== NEW API ENDPOINTS ====================

@vault_bp.route('/api/stats')
def api_stats():
    """API endpoint to get vault statistics"""
    # This can be called via AJAX for live updates
    
    stats = {
        'total_documents': db.session.query(VaultDocument).filter_by(archived=False).count(),
        'total_size_mb': round(
            (db.session.query(func.sum(VaultDocument.file_size)).scalar() or 0) / (1024 * 1024), 
            2
        ),
        'pinned_count': db.session.query(VaultDocument).filter_by(
            pinned=True, archived=False
        ).count(),
        'folders_count': db.session.query(VaultFolder).count(),
        'tags_count': db.session.query(VaultTag).count(),
        'accessed_today': db.session.query(VaultDocument).filter(
            VaultDocument.archived == False,
            VaultDocument.accessed_at >= datetime.utcnow().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        ).count()
    }
    
    return jsonify(stats)


@vault_bp.route('/api/activity')
def api_activity():
    """API endpoint for recent activity timeline"""
    activities = []
    
    # Get recent document activities
    recent_docs = db.session.query(VaultDocument).filter_by(
        archived=False
    ).order_by(desc(VaultDocument.updated_at)).limit(10).all()
    
    for doc in recent_docs:
        if doc.updated_at == doc.created_at:
            action = 'created'
            icon = '📤'
        else:
            action = 'updated'
            icon = '✏️'
        
        activities.append({
            'id': doc.id,
            'action': action,
            'icon': icon,
            'title': doc.title,
            'timestamp': doc.updated_at.isoformat(),
            'url': url_for('vault.view_document', id=doc.id)
        })
    
    return jsonify(activities)


@vault_bp.route('/filter')
def filter_documents():
    """Filter documents by various criteria"""
    # This route handles the date filter links
    date_range = request.args.get('date')
    
    if date_range:
        return redirect(url_for('vault.search', date_range=date_range))
    
    return redirect(url_for('vault.index'))