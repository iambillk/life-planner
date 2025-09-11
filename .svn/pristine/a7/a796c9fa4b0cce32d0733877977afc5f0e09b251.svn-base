# modules/projects/routes.py - Complete file with file attachments
import os
from flask import render_template, request, redirect, url_for, flash, jsonify, send_file, current_app
from werkzeug.utils import secure_filename
from datetime import datetime
from . import projects_bp
from .constants import PROJECT_CATEGORIES, PROJECT_STATUSES, PRIORITY_LEVELS
from models import db, TCHProject, TCHTask, TCHIdea, TCHMilestone, TCHProjectNote, PersonalProject, ProjectFile

# ==================== TCH PROJECTS ====================

@projects_bp.route('/tch')
def tch_index():
    """TCH Projects dashboard with category and status filters"""
    status_filter = request.args.get('status', 'active')
    category_filter = request.args.get('category', 'all')
    
    # Build query
    query = TCHProject.query
    
    # Apply status filter
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    # Apply category filter
    if category_filter != 'all':
        query = query.filter_by(category=category_filter)
    
    # Get filtered projects
    projects = query.order_by(TCHProject.priority.desc(), TCHProject.deadline).all()
    
    # Calculate actual progress based on tasks
    for project in projects:
        if project.tasks:
            completed_tasks = sum(1 for task in project.tasks if task.completed)
            project.progress = int((completed_tasks / len(project.tasks)) * 100)
        else:
            project.progress = 0
    
    # Get counts for status badges
    status_counts = {
        'planning': TCHProject.query.filter_by(status='planning').count(),
        'active': TCHProject.query.filter_by(status='active').count(),
        'on_hold': TCHProject.query.filter_by(status='on_hold').count(),
        'completed': TCHProject.query.filter_by(status='completed').count()
    }
    
    # Get counts for category badges
    category_counts = {}
    for cat in PROJECT_CATEGORIES:
        category_counts[cat] = TCHProject.query.filter_by(category=cat).count()
    
    return render_template('tch_projects.html', 
                         projects=projects, 
                         status_filter=status_filter,
                         category_filter=category_filter,
                         status_counts=status_counts,
                         category_counts=category_counts,
                         categories=PROJECT_CATEGORIES,
                         active='tch')

@projects_bp.route('/tch/add', methods=['GET', 'POST'])
def add_tch():
    """Add new TCH project with file attachments"""
    if request.method == 'POST':
        # Create the project first
        project = TCHProject(
            name=request.form.get('name'),
            description=request.form.get('description'),
            category=request.form.get('category', 'General'),
            goal=request.form.get('goal'),
            motivation=request.form.get('motivation'),
            strategy=request.form.get('strategy'),
            priority=request.form.get('priority', 'medium'),
            status=request.form.get('status', 'planning'),
            start_date=datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date() if request.form.get('start_date') else datetime.utcnow().date(),
            deadline=datetime.strptime(request.form.get('deadline'), '%Y-%m-%d').date() if request.form.get('deadline') else None
        )
        db.session.add(project)
        db.session.flush()  # This gets us the project.id without committing
        
        # Handle file uploads
        uploaded_files = []
        if 'attachments' in request.files:
            files = request.files.getlist('attachments')
            
            # Create project folder
            upload_folder = os.path.join('static', 'project_files', 'tch', str(project.id))
            os.makedirs(upload_folder, exist_ok=True)
            
            for file in files:
                if file and file.filename:
                    # Secure the filename
                    filename = secure_filename(file.filename)
                    # Make it unique
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    unique_filename = f"{timestamp}_{filename}"
                    
                    # Save the file
                    filepath = os.path.join(upload_folder, unique_filename)
                    file.save(filepath)
                    
                    # Create database record
                    attachment = ProjectFile(
                        project_id=project.id,
                        project_type='tch',
                        filename=unique_filename,
                        original_name=filename
                    )
                    db.session.add(attachment)
                    uploaded_files.append(filename)
        
        db.session.commit()
        
        if uploaded_files:
            flash(f'Project "{project.name}" created with {len(uploaded_files)} files!', 'success')
        else:
            flash(f'Project "{project.name}" created!', 'success')
            
        return redirect(url_for('projects.tch_detail', id=project.id))
    
    return render_template('tch_add_project.html', 
                         categories=PROJECT_CATEGORIES,
                         statuses=PROJECT_STATUSES,
                         priorities=PRIORITY_LEVELS,
                         active='tch')

@projects_bp.route('/tch/<int:id>')
def tch_detail(id):
    """View TCH project details"""
    project = TCHProject.query.get_or_404(id)
    
    # Calculate progress
    if project.tasks:
        completed_tasks = sum(1 for task in project.tasks if task.completed)
        project.progress = int((completed_tasks / len(project.tasks)) * 100)
    else:
        project.progress = 0
    
    # Organize tasks by category
    tasks_by_category = {}
    for task in project.tasks:
        category = task.category or 'Uncategorized'
        if category not in tasks_by_category:
            tasks_by_category[category] = []
        tasks_by_category[category].append(task)
    
    # Get attached todo lists
    from models import TodoList
    project_todos = TodoList.query.filter_by(
        module='tch_project',
        module_id=id,
        is_archived=False
    ).order_by(TodoList.is_pinned.desc(), TodoList.created_at.desc()).all()
    
    # Get files for this project
    files = ProjectFile.query.filter_by(
        project_type='tch',
        project_id=id
    ).order_by(ProjectFile.uploaded_at.desc()).all()
    
    return render_template('tch_project_detail.html', 
                         project=project,
                         tasks_by_category=tasks_by_category,
                         project_todos=project_todos,
                         files=files,
                         module_type='tch_project',
                         active='tch')

@projects_bp.route('/tch/<int:id>/edit', methods=['GET', 'POST'])
def edit_tch(id):
    """Edit TCH project with category"""
    project = TCHProject.query.get_or_404(id)
    
    if request.method == 'POST':
        project.name = request.form.get('name')
        project.description = request.form.get('description')
        project.category = request.form.get('category', 'General')
        project.goal = request.form.get('goal')
        project.motivation = request.form.get('motivation')
        project.strategy = request.form.get('strategy')
        project.priority = request.form.get('priority')
        project.status = request.form.get('status')
        
        if request.form.get('start_date'):
            project.start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        if request.form.get('deadline'):
            project.deadline = datetime.strptime(request.form.get('deadline'), '%Y-%m-%d').date()
        
        # Handle retrospective fields
        project.what_worked = request.form.get('what_worked')
        project.what_was_hard = request.form.get('what_was_hard')
        project.lessons_learned = request.form.get('lessons_learned')
        
        # If marking as completed, set completion date
        if project.status == 'completed' and not project.completed_date:
            project.completed_date = datetime.utcnow().date()
        
        # ADD THIS SECTION: Handle file uploads (same pattern as add_tch)
        uploaded_files = []
        if 'attachments' in request.files:
            files = request.files.getlist('attachments')
            
            # Create project folder if it doesn't exist
            upload_folder = os.path.join('static', 'project_files', 'tch', str(project.id))
            os.makedirs(upload_folder, exist_ok=True)
            
            for file in files:
                if file and file.filename:
                    # Secure the filename
                    filename = secure_filename(file.filename)
                    # Make it unique
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    unique_filename = f"{timestamp}_{filename}"
                    
                    # Save the file
                    filepath = os.path.join(upload_folder, unique_filename)
                    file.save(filepath)
                    
                    # Create database record
                    attachment = ProjectFile(
                        project_id=project.id,
                        project_type='tch',
                        filename=unique_filename,
                        original_name=filename
                    )
                    db.session.add(attachment)
                    uploaded_files.append(filename)
        
        project.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Update flash message to indicate if files were added
        if uploaded_files:
            flash(f'Project updated with {len(uploaded_files)} new files!', 'success')
        else:
            flash('Project updated successfully!', 'success')
            
        return redirect(url_for('projects.tch_detail', id=id))
    
    return render_template('tch_edit_project.html', 
                         project=project,
                         categories=PROJECT_CATEGORIES,
                         statuses=PROJECT_STATUSES,
                         priorities=PRIORITY_LEVELS,
                         active='tch')

@projects_bp.route('/tch/<int:id>/delete', methods=['POST'])
def delete_tch(id):
    """Delete TCH project"""
    project = TCHProject.query.get_or_404(id)
    name = project.name
    
    # Delete project files from filesystem
    import shutil
    project_folder = os.path.join('static', 'project_files', 'tch', str(id))
    if os.path.exists(project_folder):
        shutil.rmtree(project_folder)
    
    db.session.delete(project)
    db.session.commit()
    flash(f'Project "{name}" deleted!', 'success')
    return redirect(url_for('projects.tch_index'))

# ==================== FILE MANAGEMENT ====================

@projects_bp.route('/tch/<int:project_id>/file/<int:file_id>/delete', methods=['POST'])
def delete_file(project_id, file_id):
    """Delete a project file"""
    file = ProjectFile.query.get_or_404(file_id)
    
    # Delete physical file
    try:
        filepath = os.path.join('static', 'project_files', 'tch', str(project_id), file.filename)
        if os.path.exists(filepath):
            os.remove(filepath)
    except:
        pass  # File might already be gone
    
    # Delete database record
    db.session.delete(file)
    db.session.commit()
    
    flash('File deleted', 'success')
    return redirect(url_for('projects.tch_detail', id=project_id))

@projects_bp.route('/tch/<int:project_id>/file/<int:file_id>/download')
def download_file(project_id, file_id):
    """Download a project file"""
    file = ProjectFile.query.get_or_404(file_id)
    filepath = os.path.join('static', 'project_files', 'tch', str(project_id), file.filename)
    
    return send_file(filepath, 
                     as_attachment=True, 
                     download_name=file.original_name)

# ==================== TASKS ====================

@projects_bp.route('/tch/<int:project_id>/task/add', methods=['POST'])
def add_tch_task(project_id):
    """Add task to project"""
    task = TCHTask(
        project_id=project_id,
        title=request.form.get('title'),
        description=request.form.get('description'),
        category=request.form.get('category'),
        priority=request.form.get('priority', 'medium'),
        due_date=datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date() if request.form.get('due_date') else None
    )
    db.session.add(task)
    db.session.commit()
    flash('Task added!', 'success')
    return redirect(url_for('projects.tch_detail', id=project_id))

@projects_bp.route('/tch/task/<int:task_id>/toggle', methods=['POST'])
def toggle_tch_task(task_id):
    """Toggle task completion"""
    task = TCHTask.query.get_or_404(task_id)
    task.completed = not task.completed
    task.completed_date = datetime.utcnow() if task.completed else None
    db.session.commit()
    return jsonify({'success': True, 'completed': task.completed})

@projects_bp.route('/tch/task/<int:task_id>/edit', methods=['GET', 'POST'])
def edit_tch_task(task_id):
    """Edit task"""
    task = TCHTask.query.get_or_404(task_id)
    project = task.project
    
    if request.method == 'POST':
        task.title = request.form.get('title')
        task.description = request.form.get('description')
        task.category = request.form.get('category')
        task.priority = request.form.get('priority', 'medium')
        task.assigned_to = request.form.get('assigned_to')
        
        if request.form.get('due_date'):
            task.due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date()
        
        db.session.commit()
        flash('Task updated!', 'success')
        return redirect(url_for('projects.tch_detail', id=task.project_id))
    
    # Task categories for the dropdown
    task_categories = ['Development', 'Design', 'Testing', 'Documentation', 
                       'Research', 'Meeting', 'Review', 'Deployment', 
                       'Communication', 'Other']
    
    return render_template('tch_edit_task.html', 
                         task=task,
                         project=project,
                         task_categories=task_categories,
                         priorities=['low', 'medium', 'high'],
                         active='tch')

@projects_bp.route('/tch/task/<int:task_id>/delete', methods=['POST'])
def delete_tch_task(task_id):
    """Delete task"""
    task = TCHTask.query.get_or_404(task_id)
    project_id = task.project_id
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted!', 'success')
    return redirect(url_for('projects.tch_detail', id=project_id))

# ==================== IDEAS ====================

@projects_bp.route('/tch/<int:project_id>/idea/add', methods=['POST'])
def add_tch_idea(project_id):
    """Add idea to project"""
    idea = TCHIdea(
        project_id=project_id,
        content=request.form.get('content'),
        status='new'
    )
    db.session.add(idea)
    db.session.commit()
    flash('Idea added!', 'success')
    return redirect(url_for('projects.tch_detail', id=project_id))

@projects_bp.route('/tch/idea/<int:idea_id>/status', methods=['POST'])
def update_idea_status(idea_id):
    """Update idea status"""
    idea = TCHIdea.query.get_or_404(idea_id)
    idea.status = request.form.get('status')
    db.session.commit()
    return redirect(url_for('projects.tch_detail', id=idea.project_id))

@projects_bp.route('/tch/idea/<int:idea_id>/edit', methods=['GET', 'POST'])
def edit_tch_idea(idea_id):
    """Edit a TCH project idea"""
    idea = TCHIdea.query.get_or_404(idea_id)
    project = TCHProject.query.get_or_404(idea.project_id)
    
    if request.method == 'POST':
        idea.content = request.form.get('content')
        idea.status = request.form.get('status', 'new')
        
        db.session.commit()
        flash('Idea updated successfully!', 'success')
        return redirect(url_for('projects.tch_detail', id=project.id))
    
    return render_template('tch_edit_idea.html', 
                         idea=idea, 
                         project=project,
                         statuses=['new', 'considering', 'implemented', 'rejected'])

@projects_bp.route('/tch/idea/<int:idea_id>/delete', methods=['POST'])
def delete_tch_idea(idea_id):
    """Delete TCH idea"""
    idea = TCHIdea.query.get_or_404(idea_id)
    project_id = idea.project_id
    db.session.delete(idea)
    db.session.commit()
    flash('Idea deleted!', 'success')
    return redirect(url_for('projects.tch_detail', id=project_id))

# ==================== MILESTONES ====================

@projects_bp.route('/tch/<int:project_id>/milestone/add', methods=['POST'])
def add_tch_milestone(project_id):
    """Add milestone to project"""
    milestone = TCHMilestone(
        project_id=project_id,
        title=request.form.get('title'),
        description=request.form.get('description'),
        target_date=datetime.strptime(request.form.get('target_date'), '%Y-%m-%d').date() if request.form.get('target_date') else None
    )
    db.session.add(milestone)
    db.session.commit()
    flash('Milestone added!', 'success')
    return redirect(url_for('projects.tch_detail', id=project_id))

@projects_bp.route('/tch/milestone/<int:milestone_id>/complete', methods=['POST'])
def complete_milestone(milestone_id):
    """Mark milestone as complete"""
    milestone = TCHMilestone.query.get_or_404(milestone_id)
    milestone.completed = True
    milestone.completed_date = datetime.utcnow().date()
    db.session.commit()
    flash('Milestone completed!', 'success')
    return redirect(url_for('projects.tch_detail', id=milestone.project_id))

@projects_bp.route('/tch/milestone/<int:milestone_id>/edit', methods=['GET', 'POST'])
def edit_tch_milestone(milestone_id):
    """Edit a TCH project milestone"""
    milestone = TCHMilestone.query.get_or_404(milestone_id)
    project = TCHProject.query.get_or_404(milestone.project_id)
    
    if request.method == 'POST':
        milestone.title = request.form.get('title')
        milestone.description = request.form.get('description', '')
        
        target_date_str = request.form.get('target_date')
        if target_date_str:
            milestone.target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        else:
            milestone.target_date = None
        
        db.session.commit()
        flash('Milestone updated successfully!', 'success')
        return redirect(url_for('projects.tch_detail', id=project.id))
    
    return render_template('tch_edit_milestone.html', 
                         milestone=milestone, 
                         project=project)

@projects_bp.route('/tch/milestone/<int:milestone_id>/delete', methods=['POST'])
def delete_tch_milestone(milestone_id):
    """Delete TCH milestone"""
    milestone = TCHMilestone.query.get_or_404(milestone_id)
    project_id = milestone.project_id
    db.session.delete(milestone)
    db.session.commit()
    flash('Milestone deleted!', 'success')
    return redirect(url_for('projects.tch_detail', id=project_id))

# ==================== NOTES ====================

@projects_bp.route('/tch/<int:project_id>/note/add', methods=['POST'])
def add_tch_note(project_id):
    """Add note to project"""
    note = TCHProjectNote(
        project_id=project_id,
        content=request.form.get('content'),
        category=request.form.get('category', 'general')
    )
    db.session.add(note)
    db.session.commit()
    flash('Note added!', 'success')
    return redirect(url_for('projects.tch_detail', id=project_id))

@projects_bp.route('/tch/note/<int:note_id>/edit', methods=['GET', 'POST'])
def edit_tch_note(note_id):
    """Edit note"""
    note = TCHProjectNote.query.get_or_404(note_id)
    project = note.project
    
    if request.method == 'POST':
        note.content = request.form.get('content')
        note.category = request.form.get('category', 'general')
        
        db.session.commit()
        flash('Note updated!', 'success')
        return redirect(url_for('projects.tch_detail', id=note.project_id))
    
    # Note categories for the dropdown
    note_categories = ['general', 'meeting', 'technical', 'idea']
    
    return render_template('tch_edit_note.html', 
                         note=note,
                         project=project,
                         note_categories=note_categories,
                         active='tch')

@projects_bp.route('/tch/note/<int:note_id>/delete', methods=['POST'])
def delete_tch_note(note_id):
    """Delete note"""
    note = TCHProjectNote.query.get_or_404(note_id)
    project_id = note.project_id
    db.session.delete(note)
    db.session.commit()
    flash('Note deleted!', 'success')
    return redirect(url_for('projects.tch_detail', id=project_id))

# ==================== PERSONAL PROJECTS ====================

@projects_bp.route('/personal')
def personal_index():
    """Personal projects list"""
    projects = PersonalProject.query.filter_by(status='active').all()
    return render_template('personal_projects.html', projects=projects, active='personal')

@projects_bp.route('/personal/add', methods=['POST'])
def add_personal():
    """Add personal project"""
    project = PersonalProject(
        name=request.form.get('name'),
        description=request.form.get('description'),
        status='active',
        deadline=datetime.strptime(request.form.get('deadline'), '%Y-%m-%d').date() if request.form.get('deadline') else None
    )
    db.session.add(project)
    db.session.commit()
    flash('Personal project added!', 'success')
    return redirect(url_for('projects.personal_index'))

@projects_bp.route('/personal/<int:id>/update', methods=['POST'])
def update_personal(id):
    """Update personal project progress"""
    project = PersonalProject.query.get_or_404(id)
    project.progress = int(request.form.get('progress', 0))
    
    if project.progress >= 100:
        project.status = 'completed'
    
    db.session.commit()
    return redirect(url_for('projects.personal_index'))