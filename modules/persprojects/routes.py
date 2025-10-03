# modules/persprojects/routes.py - COMPLETE FILE WITH NFS ATTACHMENTS
from flask import render_template, request, redirect, url_for, flash, current_app, send_file
from datetime import datetime
import os
from urllib.parse import unquote_plus
from werkzeug.utils import secure_filename
from sqlalchemy import or_
from . import persprojects_bp
from .constants import PERSONAL_PROJECT_CATEGORIES, PROJECT_STATUSES, PRIORITY_LEVELS, IDEA_STATUSES, NOTE_CATEGORIES
from models import db, PersonalProject, PersonalTask, PersonalIdea, PersonalMilestone, PersonalProjectNote, PersonalProjectFile

# ADD VAULT IMPORTS
from modules.vault.vault_service import (
    create_document_for_entity,
    get_entity_documents
)



@persprojects_bp.route('/')
def index():
    """Personal projects dashboard"""
    status_filter = request.args.get('status', 'active')
    
    # Get ALL projects first for counting
    all_projects = PersonalProject.query.order_by(PersonalProject.created_at.desc()).all()
    
    # Calculate status counts from ALL projects
    status_counts = {
        'planning': len([p for p in all_projects if p.status == 'planning']),
        'active': len([p for p in all_projects if p.status == 'active']),
        'on_hold': len([p for p in all_projects if p.status == 'on_hold']),
        'completed': len([p for p in all_projects if p.status == 'completed'])
    }
    
    # Filter projects for display
    if status_filter != 'all':
        projects = [p for p in all_projects if p.status == status_filter]
    else:
        projects = all_projects
    
    # Calculate progress based on tasks
    for project in projects:
        if project.tasks:
            completed_tasks = sum(1 for task in project.tasks if task.completed)
            project.progress = int((completed_tasks / len(project.tasks)) * 100)
        else:
            project.progress = 0
    
    return render_template('persprojects/index.html',
                         projects=projects,
                         status_counts=status_counts,
                         status_filter=status_filter,
                         categories=PERSONAL_PROJECT_CATEGORIES)

@persprojects_bp.route('/add', methods=['GET', 'POST'])
def add():
    """Add new personal project"""
    if request.method == 'POST':
        project = PersonalProject(
            name=request.form.get('name'),
            description=request.form.get('description'),
            category=request.form.get('category'),
            status=request.form.get('status', 'planning'),
            priority=request.form.get('priority', 'medium'),
            goal=request.form.get('goal'),
            motivation=request.form.get('motivation'),
            strategy=request.form.get('strategy'),
            deadline=datetime.strptime(request.form.get('deadline'), '%Y-%m-%d').date() if request.form.get('deadline') else None
        )
        
        db.session.add(project)
        db.session.commit()
        
        flash(f'Project "{project.name}" created successfully!', 'success')
        return redirect(url_for('persprojects.detail', id=project.id))
    
    return render_template('persprojects/add.html',
                         categories=PERSONAL_PROJECT_CATEGORIES,
                         statuses=PROJECT_STATUSES,
                         priorities=PRIORITY_LEVELS)

@persprojects_bp.route('/<int:id>')
def detail(id):
    """View personal project details"""
    project = PersonalProject.query.get_or_404(id)
    
    # Calculate progress
    if project.tasks:
        completed_tasks = sum(1 for task in project.tasks if task.completed)
        project.progress = int((completed_tasks / len(project.tasks)) * 100)
    else:
        project.progress = 0
    
    # Get vault documents for this project
    from models.vault import VaultDocument, VaultFolder
    
    # Find the folder for this personal project
    # The vault service creates folders like "Personal Project #ID" or uses the project name
    folder = VaultFolder.query.filter(
        or_(
            VaultFolder.name == project.name,
            VaultFolder.name == f"Personal Project #{project.id}"
        )
    ).first()
    
    vault_documents = []
    if folder:
        vault_documents = VaultDocument.query.filter_by(
            folder_id=folder.id,
            archived=False
        ).order_by(VaultDocument.pinned.desc(), VaultDocument.created_at.desc()).all()
    
    return render_template('persprojects/detail.html',
                       project=project,
                       vault_documents=vault_documents,
                       categories=PERSONAL_PROJECT_CATEGORIES,
                       statuses=PROJECT_STATUSES,
                       priorities=[p[0] for p in PRIORITY_LEVELS],  # pass just keys
                       idea_statuses=[s[0] for s in IDEA_STATUSES],
                       note_categories=NOTE_CATEGORIES,
    )


# ==================== EMAIL CAPTURE (PERSONAL) ====================

def _clean_msgid(raw: str | None) -> str | None:
    if not raw:
        return None
    # raw may come like "<abc@ex>", sometimes URL-encoded
    try:
        raw = unquote_plus(raw)
    except Exception:
        pass
    raw = raw.strip()
    # strip angle brackets if present
    if raw.startswith("<") and raw.endswith(">"):
        raw = raw[1:-1]
    return raw.strip().lower()

def _clean_subject(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        s = unquote_plus(raw).strip()
    except Exception:
        s = raw.strip()
    # light cleanup for nicer titles
    for prefix in ("Re: ", "RE: ", "Fwd: ", "FWD: ", "[EXT] "):
        if s.startswith(prefix):
            s = s[len(prefix):]
    return s.strip()

def save_email_attachment_reference(project_id, attach_path, filename):
    """Save a reference to the file on the NFS drive without copying"""
    # Create database record pointing to NFS location
    file_record = PersonalProjectFile(
        project_id=project_id,
        filename=os.path.join(attach_path, filename),  # Store full path like Z:\test123\test.txt
        original_name=filename
    )
    db.session.add(file_record)
    return file_record

@persprojects_bp.route('/capture/email/personal', methods=['GET'])
def capture_personal_get():
    """
    Confirm form for capturing a Personal Project from an email.
    Expects query params: msgid, from, subject (best-effort).
    Example hotkey URL (from The Bat! filter):
      /capture/email/personal?msgid=%OMSGID&from=%FROMADDR&subject=%SUBJECT
    """
    msgid_raw = request.args.get('msgid', '')
    from_addr = request.args.get('from', '')
    subject_raw = request.args.get('subject', '')
    
    msgid = _clean_msgid(msgid_raw)
    title_suggest = _clean_subject(subject_raw)
    
    # Pull ALL projects for the "Add to Existing" dropdown (per your preference)
    all_projects = PersonalProject.query.order_by(PersonalProject.created_at.desc()).all()
    
    # Optional soft dedupe check: look for any note that mentions this Message-ID
    dup = None
    if msgid:
        dup = (db.session.query(PersonalProjectNote, PersonalProject)
               .join(PersonalProject, PersonalProject.id == PersonalProjectNote.project_id)
               .filter(PersonalProjectNote.content.ilike(f"%Message-ID:%{msgid}%"))
               .first())
    
    # Check for attachments
    attach_path = request.args.get('attach_path', '')
    attachments = []
    
    if attach_path and os.path.exists(attach_path):
        for filename in os.listdir(attach_path):
            filepath = os.path.join(attach_path, filename)
            file_size = os.path.getsize(filepath)
            attachments.append({
                'name': filename,
                'size': file_size,
                'size_mb': round(file_size / (1024 * 1024), 2)
            })
    
    return render_template(
        'persprojects/capture_personal.html',
        msgid=msgid,
        from_addr=from_addr,
        subject_raw=unquote_plus(subject_raw) if subject_raw else '',
        title_suggest=title_suggest,
        categories=PERSONAL_PROJECT_CATEGORIES,
        projects=all_projects,
        duplicate=dup,
        attachments=attachments,
        attach_path=attach_path
    )

@persprojects_bp.route('/capture/email/personal', methods=['POST'])
def capture_personal_post():
    """
    Handle form submit from the capture page.
    Creates either a NEW PersonalProject or a TASK in an existing one.
    Stores a first note with From/Subject/Message-ID for traceability.
    """
    mode = request.form.get('mode', 'new')  # 'new' or 'existing'
    title = (request.form.get('title') or '').strip()
    category = request.form.get('category') or None
    due_date_str = request.form.get('due_date') or ''
    existing_id = request.form.get('existing_id') or ''
    from_addr = (request.form.get('from_addr') or '').strip()
    subject_raw = (request.form.get('subject_raw') or '').strip()
    msgid = _clean_msgid(request.form.get('msgid'))
    
    # Get attachment selections
    attach_path = request.form.get('attach_path', '')
    keep_files = request.form.getlist('keep_files')  # Gets list of checked files

    # Parse due date (optional)
    due_date = None
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        except Exception:
            due_date = None

    # Build a small structured note body for provenance
    provenance_lines = []
    if from_addr:
        provenance_lines.append(f"From: {from_addr}")
    if subject_raw:
        provenance_lines.append(f"Subject: {subject_raw}")
    if msgid:
        provenance_lines.append(f"Message-ID: {msgid}")
    provenance_lines.append(f"Captured: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%SZ')} via The Bat!")
    provenance = "\n".join(provenance_lines)

    # Soft dedupe: if user didn't override and we already have a note with this msgid, nudge them
    if request.form.get('dedupe_override') != '1' and msgid:
        dup = (db.session.query(PersonalProjectNote, PersonalProject)
               .join(PersonalProject, PersonalProject.id == PersonalProjectNote.project_id)
               .filter(PersonalProjectNote.content.ilike(f"%Message-ID:%{msgid}%"))
               .first())
        if dup:
            note, project = dup
            flash('Looks like you already captured this email.', 'warning')
            # Re-render confirm with a banner + option to continue anyway
            all_projects = PersonalProject.query.order_by(PersonalProject.created_at.desc()).all()
            return render_template(
                'persprojects/capture_personal.html',
                msgid=msgid,
                from_addr=from_addr,
                subject_raw=subject_raw,
                title_suggest=title or _clean_subject(subject_raw),
                categories=PERSONAL_PROJECT_CATEGORIES,
                projects=all_projects,
                duplicate=dup,
                dedupe_can_override=True
            )

    if mode == 'existing' and existing_id:
        # Add a TASK to an existing project
        project = PersonalProject.query.get(int(existing_id))
        if not project:
            flash('Selected project not found.', 'error')
            return redirect(url_for('persprojects.index'))

        task = PersonalTask(
            project_id=project.id,
            content=title or _clean_subject(subject_raw),
            category=category or 'general',
        )
        db.session.add(task)
        db.session.flush()  # Get the task ID
        
        # Handle attachments for existing project (just save references)
        if attach_path and keep_files:
            for filename in keep_files:
                try:
                    save_email_attachment_reference(project.id, attach_path, filename)
                except Exception as e:
                    flash(f'Error saving reference to {filename}: {str(e)}', 'warning')
        
        db.session.commit()
        flash('Task created from email.', 'success')
        return redirect(url_for('persprojects.detail', id=project.id))
    else:
        # Default: create NEW Personal Project
        project = PersonalProject(
            name=title or _clean_subject(subject_raw) or 'New Personal Project',
            description='',  # can be edited later
            category=category or None,
            status='planning',
            priority='medium',
            deadline=due_date
        )
        db.session.add(project)
        db.session.flush()

        # First note with provenance (email context)
        note = PersonalProjectNote(
            project_id=project.id,
            content=provenance,
            category='reference'
        )
        db.session.add(note)
        
        # Handle attachments for new project (just save references)
        if attach_path and keep_files:
            for filename in keep_files:
                try:
                    save_email_attachment_reference(project.id, attach_path, filename)
                except Exception as e:
                    flash(f'Error saving reference to {filename}: {str(e)}', 'warning')
        
        db.session.commit()
        flash(f'Project "{project.name}" created from email.', 'success')
        return redirect(url_for('persprojects.detail', id=project.id))

# ==================== TASKS ====================

@persprojects_bp.route('/<int:project_id>/task/add', methods=['POST'])
def add_task(project_id):
    """Add task to project"""
    from .constants import PERSONAL_PROJECT_CATEGORIES, PRIORITY_LEVELS
    def _coerce(v, allowed, default):
        v = (v or '').strip()
        return v if v in allowed else default

    content   = (request.form.get('content') or '').strip()
    category  = _coerce(request.form.get('category'), PERSONAL_PROJECT_CATEGORIES, 'Other')
    priority  = _coerce(request.form.get('priority'), [p[0] for p in PRIORITY_LEVELS], 'medium')
    due_str   = request.form.get('due_date') or ''
    notes     = (request.form.get('notes') or '').strip()

    due_date = None
    if due_str:
        try:
            from datetime import datetime
            due_date = datetime.strptime(due_str, '%Y-%m-%d').date()
        except Exception:
            due_date = None

    task = PersonalTask(
        project_id=project_id,
        content=content,
        category=category,
        priority=priority,
        due_date=due_date,
        notes=notes
    )
    db.session.add(task)
    db.session.commit()
    flash('Task added!', 'success')
    return redirect(url_for('persprojects.detail', id=project_id))


@persprojects_bp.route('/task/<int:task_id>/toggle', methods=['POST'])
def toggle_task(task_id):
    """Toggle task completion"""
    task = PersonalTask.query.get_or_404(task_id)
    task.completed = not task.completed
    if task.completed:
        task.completed_at = datetime.utcnow()
    else:
        task.completed_at = None
    db.session.commit()
    return redirect(url_for('persprojects.detail', id=task.project_id))

@persprojects_bp.route('/task/<int:task_id>/delete', methods=['POST'])
def delete_task(task_id):
    """Delete task"""
    task = PersonalTask.query.get_or_404(task_id)
    project_id = task.project_id
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted!', 'success')
    return redirect(url_for('persprojects.detail', id=project_id))

@persprojects_bp.route('/task/<int:task_id>/edit', methods=['GET', 'POST'])
def edit_task(task_id):
    """Edit a personal project task"""
    task = PersonalTask.query.get_or_404(task_id)
    project = PersonalProject.query.get_or_404(task.project_id)
    
    if request.method == 'POST':
        # Update task fields
        task.content = request.form.get('content')
        task.category = request.form.get('category')
        task.priority = request.form.get('priority', 'medium')
        task.due_date_str = request.form.get('due_date')
        
        # Handle due date
        if task.due_date_str:
            try:
                task.due_date = datetime.strptime(task.due_date_str, '%Y-%m-%d').date()
            except:
                task.due_date = None
        else:
            task.due_date = None
        
        # Update notes if provided
        task.notes = request.form.get('notes', '')
        
        db.session.commit()
        flash('Task updated successfully!', 'success')
        return redirect(url_for('persprojects.detail', id=project.id))
    
    # GET request - show edit form
    return render_template('persprojects/edit_task.html', 
                         task=task, 
                         project=project,
                         categories=['planning', 'research', 'development', 
                                   'testing', 'documentation', 'other'],
                         priorities=['low', 'medium', 'high'])

# ==================== IDEAS ====================

@persprojects_bp.route('/<int:project_id>/idea/add', methods=['POST'])
def add_idea(project_id):
    """Add idea to project"""
    idea = PersonalIdea(
        project_id=project_id,
        content=request.form.get('content'),
        status='new'
    )
    db.session.add(idea)
    db.session.commit()
    flash('Idea added!', 'success')
    return redirect(url_for('persprojects.detail', id=project_id))

@persprojects_bp.route('/idea/<int:idea_id>/status', methods=['POST'])
def update_idea_status(idea_id):
    """Update idea status"""
    idea = PersonalIdea.query.get_or_404(idea_id)
    idea.status = request.form.get('status')
    db.session.commit()
    return redirect(url_for('persprojects.detail', id=idea.project_id))

@persprojects_bp.route('/idea/<int:idea_id>/delete', methods=['POST'])
def delete_idea(idea_id):
    """Delete idea"""
    idea = PersonalIdea.query.get_or_404(idea_id)
    project_id = idea.project_id
    db.session.delete(idea)
    db.session.commit()
    flash('Idea deleted!', 'success')
    return redirect(url_for('persprojects.detail', id=project_id))

@persprojects_bp.route('/idea/<int:idea_id>/edit', methods=['GET', 'POST'])
def edit_idea(idea_id):
    """Edit a personal project idea"""
    idea = PersonalIdea.query.get_or_404(idea_id)
    project = PersonalProject.query.get_or_404(idea.project_id)
    
    if request.method == 'POST':
        # Update idea fields
        idea.content = request.form.get('content')
        idea.status = request.form.get('status', 'new')
        
        db.session.commit()
        flash('Idea updated successfully!', 'success')
        return redirect(url_for('persprojects.detail', id=project.id))
    
    # GET request - show edit form
    return render_template('persprojects/edit_idea.html', 
                         idea=idea, 
                         project=project,
                         statuses=['new', 'considering', 'planned', 'rejected'])

# ==================== MILESTONES ====================

@persprojects_bp.route('/<int:project_id>/milestone/add', methods=['POST'])
def add_milestone(project_id):
    """Add milestone to project"""
    milestone = PersonalMilestone(
        project_id=project_id,
        title=request.form.get('title'),
        description=request.form.get('description'),
        target_date=datetime.strptime(request.form.get('target_date'), '%Y-%m-%d').date() if request.form.get('target_date') else None
    )
    db.session.add(milestone)
    db.session.commit()
    flash('Milestone added!', 'success')
    return redirect(url_for('persprojects.detail', id=project_id))

@persprojects_bp.route('/milestone/<int:milestone_id>/complete', methods=['POST'])
def complete_milestone(milestone_id):
    """Mark milestone as complete"""
    milestone = PersonalMilestone.query.get_or_404(milestone_id)
    milestone.completed = not milestone.completed
    if milestone.completed:
        milestone.completed_date = datetime.utcnow().date()
    else:
        milestone.completed_date = None
    db.session.commit()
    flash('Milestone updated!', 'success')
    return redirect(url_for('persprojects.detail', id=milestone.project_id))

@persprojects_bp.route('/milestone/<int:milestone_id>/delete', methods=['POST'])
def delete_milestone(milestone_id):
    """Delete milestone"""
    milestone = PersonalMilestone.query.get_or_404(milestone_id)
    project_id = milestone.project_id
    db.session.delete(milestone)
    db.session.commit()
    flash('Milestone deleted!', 'success')
    return redirect(url_for('persprojects.detail', id=project_id))

@persprojects_bp.route('/milestone/<int:milestone_id>/edit', methods=['GET', 'POST'])
def edit_milestone(milestone_id):
    """Edit a personal project milestone"""
    milestone = PersonalMilestone.query.get_or_404(milestone_id)
    project = PersonalProject.query.get_or_404(milestone.project_id)
    
    if request.method == 'POST':
        # Update milestone fields
        milestone.title = request.form.get('title')
        milestone.description = request.form.get('description', '')
        
        # Handle target date
        target_date_str = request.form.get('target_date')
        if target_date_str:
            milestone.target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        else:
            milestone.target_date = None
        
        db.session.commit()
        flash('Milestone updated successfully!', 'success')
        return redirect(url_for('persprojects.detail', id=project.id))
    
    # GET request - show edit form
    return render_template('persprojects/edit_milestone.html', 
                         milestone=milestone, 
                         project=project)

# ==================== NOTES ====================

@persprojects_bp.route('/<int:project_id>/note/add', methods=['POST'])
def add_note(project_id):
    """Add note to project"""
    note = PersonalProjectNote(
        project_id=project_id,
        content=request.form.get('content'),
        category=request.form.get('category', 'general')
    )
    db.session.add(note)
    db.session.commit()
    flash('Note added!', 'success')
    return redirect(url_for('persprojects.detail', id=project_id))

@persprojects_bp.route('/note/<int:note_id>/delete', methods=['POST'])
def delete_note(note_id):
    """Delete note"""
    note = PersonalProjectNote.query.get_or_404(note_id)
    project_id = note.project_id
    db.session.delete(note)
    db.session.commit()
    flash('Note deleted!', 'success')
    return redirect(url_for('persprojects.detail', id=project_id))

@persprojects_bp.route('/note/<int:note_id>/edit', methods=['GET', 'POST'])
def edit_note(note_id):
    """Edit a personal project note"""
    note = PersonalProjectNote.query.get_or_404(note_id)
    project = PersonalProject.query.get_or_404(note.project_id)
    
    if request.method == 'POST':
        note.content = request.form.get('content')
        note.category = request.form.get('category', 'general')
        
        db.session.commit()
        flash('Note updated successfully!', 'success')
        return redirect(url_for('persprojects.detail', id=project.id))
    
    return render_template('persprojects/edit_note.html', 
                         note=note, 
                         project=project,
                         categories=['general', 'progress', 'issue', 'research', 'reference'])

# ==================== Edit ====================

@persprojects_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit(id):
    """Edit personal project"""
    project = PersonalProject.query.get_or_404(id)
    
    if request.method == 'POST':
        # Update project fields
        project.name = request.form.get('name')
        project.description = request.form.get('description')
        project.category = request.form.get('category')
        project.status = request.form.get('status')
        project.priority = request.form.get('priority')
        project.goal = request.form.get('goal')
        project.motivation = request.form.get('motivation')
        project.strategy = request.form.get('strategy')
        
        # Handle deadline
        deadline_str = request.form.get('deadline')
        if deadline_str:
            project.deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date()
        else:
            project.deadline = None
        
        project.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash(f'Project "{project.name}" updated successfully!', 'success')
        return redirect(url_for('persprojects.detail', id=project.id))
    
    return render_template('persprojects/edit.html',
                         project=project,
                         categories=PERSONAL_PROJECT_CATEGORIES,
                         statuses=PROJECT_STATUSES,
                         priorities=PRIORITY_LEVELS)

# ==================== DELETE PROJECT ====================

@persprojects_bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    """Delete personal project"""
    project = PersonalProject.query.get_or_404(id)
    project_name = project.name
    
    db.session.delete(project)
    db.session.commit()
    
    flash(f'Project "{project_name}" has been deleted.', 'success')
    return redirect(url_for('persprojects.index'))

# ==================== FILE ATTACHMENTS ====================

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'zip'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@persprojects_bp.route('/<int:project_id>/file/upload', methods=['POST'])
def upload_file(project_id):
    """Upload file to project"""
    project = PersonalProject.query.get_or_404(project_id)
    
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('persprojects.detail', id=project_id))
    
    file = request.files['file']
    
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('persprojects.detail', id=project_id))
    
    if file and allowed_file(file.filename):
        # Create unique filename
        original_name = file.filename
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = secure_filename(f"{project_id}_{timestamp}_{original_name}")
        
        # Save file
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], 'personal_project_files', filename)
        file.save(filepath)
        
        # Create database record
        file_record = PersonalProjectFile(
            project_id=project_id,
            filename=filename,
            original_name=original_name
        )
        db.session.add(file_record)
        db.session.commit()
        
        flash(f'File "{original_name}" uploaded successfully!', 'success')
    else:
        flash('Invalid file type. Allowed types: pdf, images, doc, xls, txt, zip', 'error')
    
    return redirect(url_for('persprojects.detail', id=project_id))

@persprojects_bp.route('/file/<int:file_id>/download')
def download_file(file_id):
    """Download project file from NFS"""
    file_record = PersonalProjectFile.query.get_or_404(file_id)
    
    # File path is already the full NFS path (Z:\...)
    if os.path.exists(file_record.filename):
        return send_file(file_record.filename, as_attachment=True, download_name=file_record.original_name)
    else:
        flash('File not found on NFS drive', 'error')
        return redirect(url_for('persprojects.detail', id=file_record.project_id))

@persprojects_bp.route('/file/<int:file_id>/delete', methods=['POST'])
def delete_file(file_id):
    """Delete project file reference (doesn't delete from NFS)"""
    file_record = PersonalProjectFile.query.get_or_404(file_id)
    project_id = file_record.project_id
    
    # Just delete database record, leave file on NFS
    db.session.delete(file_record)
    db.session.commit()
    
    flash('File reference removed from project', 'success')
    return redirect(url_for('persprojects.detail', id=project_id))

@persprojects_bp.route('/<int:project_id>/vault/upload', methods=['POST'])
def upload_to_vault(project_id):
    """Upload file to vault for this project"""
    project = PersonalProject.query.get_or_404(project_id)
    
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('persprojects.detail', id=project_id))
    
    file = request.files['file']
    
    if file and file.filename:
        # Create vault document for this personal project
        doc = create_document_for_entity(
            file=file,
            entity_type='personal_project',
            entity_id=project_id,
            entity_name=project.name,
            title=request.form.get('title', file.filename),
            doc_type=request.form.get('doc_type', 'document'),
            tags=request.form.getlist('tags')
        )
        
        db.session.commit()
        flash(f'Document uploaded to vault successfully!', 'success')
    
    return redirect(url_for('persprojects.detail', id=project_id))

@persprojects_bp.route('/file/<int:file_id>/view')
def view_file(file_id):
    file_record = PersonalProjectFile.query.get_or_404(file_id)
    path = file_record.filename  # UNC ok if the service account can read it

    if not os.path.exists(path):
        flash('File not found on NFS drive', 'error')
        return redirect(url_for('persprojects.detail', id=file_record.project_id))

    import mimetypes
    mt, _ = mimetypes.guess_type(file_record.original_name or path)
    mt = mt or 'application/octet-stream'
    # Serve inline so <iframe> / <img> can render it
    return send_file(path, as_attachment=False, download_name=file_record.original_name, mimetype=mt)