# modules/projects/routes.py - Enhanced version
from flask import render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
from . import projects_bp
from models import db, TCHProject, TCHTask, TCHIdea, TCHMilestone, TCHProjectNote, PersonalProject

# ==================== TCH PROJECTS ====================

@projects_bp.route('/tch')
def tch_index():
    """TCH Projects dashboard"""
    status_filter = request.args.get('status', 'active')
    
    if status_filter == 'all':
        projects = TCHProject.query.order_by(TCHProject.priority.desc(), TCHProject.deadline).all()
    else:
        projects = TCHProject.query.filter_by(status=status_filter).order_by(TCHProject.priority.desc(), TCHProject.deadline).all()
    
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
    
    return render_template('tch_projects.html', 
                         projects=projects, 
                         status_filter=status_filter,
                         status_counts=status_counts,
                         active='tch')

@projects_bp.route('/tch/add', methods=['GET', 'POST'])
def add_tch():
    """Add new TCH project"""
    if request.method == 'POST':
        project = TCHProject(
            name=request.form.get('name'),
            description=request.form.get('description'),
            goal=request.form.get('goal'),
            motivation=request.form.get('motivation'),
            strategy=request.form.get('strategy'),
            priority=request.form.get('priority', 'medium'),
            status=request.form.get('status', 'planning'),
            start_date=datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date() if request.form.get('start_date') else datetime.utcnow().date(),
            deadline=datetime.strptime(request.form.get('deadline'), '%Y-%m-%d').date() if request.form.get('deadline') else None
        )
        db.session.add(project)
        db.session.commit()
        
        flash(f'Project "{project.name}" created!', 'success')
        return redirect(url_for('projects.tch_detail', id=project.id))
    
    return render_template('tch_add_project.html', active='tch')

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
    
    # Get attached todo lists - THIS IS THE NEW PART
    from models import TodoList
    project_todos = TodoList.query.filter_by(
        module='tch_project',
        module_id=id,
        is_archived=False
    ).order_by(TodoList.is_pinned.desc(), TodoList.created_at.desc()).all()
    
    return render_template('tch_project_detail.html', 
                         project=project,
                         tasks_by_category=tasks_by_category,
                         project_todos=project_todos,  # MAKE SURE THIS IS HERE
                         module_type='tch_project',
                         active='tch')

@projects_bp.route('/tch/<int:id>/edit', methods=['GET', 'POST'])
def edit_tch(id):
    """Edit TCH project"""
    project = TCHProject.query.get_or_404(id)
    
    if request.method == 'POST':
        project.name = request.form.get('name')
        project.description = request.form.get('description')
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
        
        project.updated_at = datetime.utcnow()
        db.session.commit()
        
        flash('Project updated successfully!', 'success')
        return redirect(url_for('projects.tch_detail', id=id))
    
    return render_template('tch_edit_project.html', project=project, active='tch')

@projects_bp.route('/tch/<int:id>/delete', methods=['POST'])
def delete_tch(id):
    """Delete TCH project"""
    project = TCHProject.query.get_or_404(id)
    name = project.name
    db.session.delete(project)
    db.session.commit()
    flash(f'Project "{name}" deleted!', 'success')
    return redirect(url_for('projects.tch_index'))

# ==================== TASK MANAGEMENT ====================

@projects_bp.route('/tch/<int:project_id>/task/add', methods=['POST'])
def add_tch_task(project_id):
    """Add task to project"""
    project = TCHProject.query.get_or_404(project_id)
    
    task = TCHTask(
        project_id=project_id,
        title=request.form.get('title'),
        description=request.form.get('description'),
        category=request.form.get('category'),
        priority=request.form.get('priority', 'medium'),
        due_date=datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date() if request.form.get('due_date') else None,
        assigned_to=request.form.get('assigned_to')
    )
    
    # Set order number
    max_order = db.session.query(db.func.max(TCHTask.order_num)).filter_by(project_id=project_id).scalar()
    task.order_num = (max_order or 0) + 1
    
    db.session.add(task)
    db.session.commit()
    
    flash('Task added!', 'success')
    return redirect(url_for('projects.tch_detail', id=project_id))

@projects_bp.route('/tch/task/<int:task_id>/toggle', methods=['POST'])
def toggle_tch_task(task_id):
    """Toggle task completion"""
    task = TCHTask.query.get_or_404(task_id)
    task.completed = not task.completed
    
    if task.completed:
        task.completed_date = datetime.utcnow()
    else:
        task.completed_date = None
    
    db.session.commit()
    
    # Return JSON for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'completed': task.completed})
    
    return redirect(url_for('projects.tch_detail', id=task.project_id))

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

# ==================== PERSONAL PROJECTS (unchanged) ====================

@projects_bp.route('/personal')
def personal_index():
    """Personal Projects list"""
    projects = PersonalProject.query.all()
    return render_template('personal_projects.html', projects=projects, active='personal')

@projects_bp.route('/personal/add', methods=['POST'])
def add_personal():
    """Add personal project"""
    project = PersonalProject(
        name=request.form.get('name'),
        description=request.form.get('description'),
        deadline=datetime.strptime(request.form.get('deadline'), '%Y-%m-%d').date() if request.form.get('deadline') else None
    )
    db.session.add(project)
    db.session.commit()
    flash(f'Personal Project "{project.name}" added!', 'success')
    return redirect(url_for('projects.personal_index'))

@projects_bp.route('/personal/<int:id>/update-progress', methods=['POST'])
def update_personal_progress(id):
    """Update personal project progress"""
    project = PersonalProject.query.get_or_404(id)
    project.progress = int(request.form.get('progress', 0))
    db.session.commit()
    return redirect(url_for('projects.personal_index'))