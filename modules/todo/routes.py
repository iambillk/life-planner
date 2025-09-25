# modules/todo/routes.py
from flask import render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
from . import todo_bp
from models import db, TodoList, TodoItem, TCHProject, PersonalProject
from .integration import TaskAggregator, UnifiedTask  # NEW IMPORT

# ==================== EXISTING ROUTES ====================

@todo_bp.route('/')
def index():
    """All todo lists dashboard"""
    standalone_lists = TodoList.query.filter_by(module=None, is_archived=False).order_by(TodoList.is_pinned.desc(), TodoList.created_at.desc()).all()
    archived_lists = TodoList.query.filter_by(is_archived=True).all()
    
    return render_template('todo/index.html', 
                         lists=standalone_lists,
                         archived_lists=archived_lists,
                         active='todo')

# ==================== NEW UNIFIED VIEW ROUTES ====================

@todo_bp.route('/unified')
def unified():
    """Unified task view aggregating all sources"""
    # Get filter parameters
    include_completed = request.args.get('completed', 'false').lower() == 'true'
    source_filter = request.args.getlist('source')  # Can be multiple
    date_filter = request.args.get('date_filter')  # today, week, overdue, no_date
    
    # Get aggregated tasks
    tasks = TaskAggregator.get_all_tasks(
        include_completed=include_completed,
        source_filter=source_filter if source_filter else None,
        date_filter=date_filter
    )
    
    # Count tasks by status for stats
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.completed])
    overdue_tasks = len([t for t in tasks if not t.completed and t.due_date and t.due_date < datetime.now().date()])
    
    # Group tasks by category for organized display
    tasks_by_priority = {
        'critical': [],
        'high': [],
        'medium': [],
        'low': []
    }
    
    for task in tasks:
        priority = task.priority or 'medium'
        if priority in tasks_by_priority:
            tasks_by_priority[priority].append(task)
    
    return render_template('todo/unified.html',
                         tasks=tasks,
                         tasks_by_priority=tasks_by_priority,
                         total_tasks=total_tasks,
                         completed_tasks=completed_tasks,
                         overdue_tasks=overdue_tasks,
                         include_completed=include_completed,
                         source_filter=source_filter,
                         date_filter=date_filter,
                         active='todo')

@todo_bp.route('/api/tasks')
def api_get_tasks():
    """API endpoint to get all tasks as JSON"""
    include_completed = request.args.get('completed', 'false').lower() == 'true'
    source_filter = request.args.getlist('source')
    date_filter = request.args.get('date_filter')
    
    tasks = TaskAggregator.get_all_tasks(
        include_completed=include_completed,
        source_filter=source_filter if source_filter else None,
        date_filter=date_filter
    )
    
    return jsonify({
        'success': True,
        'tasks': [task.to_dict() for task in tasks],
        'count': len(tasks)
    })

@todo_bp.route('/api/task/<task_id>/complete', methods=['POST'])
def api_complete_task(task_id):
    """API endpoint to mark a task as complete"""
    success = TaskAggregator.complete_task(task_id)
    
    if success:
        return jsonify({'success': True, 'message': 'Task completed'})
    else:
        return jsonify({'success': False, 'message': 'Failed to complete task'}), 400

@todo_bp.route('/api/task/<task_id>/uncomplete', methods=['POST'])
def api_uncomplete_task(task_id):
    """API endpoint to mark a task as incomplete"""
    success = TaskAggregator.uncomplete_task(task_id)
    
    if success:
        return jsonify({'success': True, 'message': 'Task marked incomplete'})
    else:
        return jsonify({'success': False, 'message': 'Failed to update task'}), 400

# ==================== ORIGINAL ROUTES CONTINUE BELOW ====================

@todo_bp.route('/create', methods=['GET', 'POST'])
def create():
    """Create new todo list"""
    if request.method == 'POST':
        todo_list = TodoList(
            title=request.form.get('title'),
            description=request.form.get('description'),
            color=request.form.get('color', 'yellow'),
            is_pinned=request.form.get('is_pinned') == 'on'
        )
        
        # Check if attaching to a project
        if request.form.get('attach_to'):
            attach_parts = request.form.get('attach_to').split('-')
            if len(attach_parts) == 2:
                todo_list.module = attach_parts[0]
                todo_list.module_id = int(attach_parts[1])
        
        db.session.add(todo_list)
        db.session.commit()
        
        # Add initial items if provided
        items = request.form.getlist('initial_items[]')
        for idx, item_content in enumerate(items):
            if item_content.strip():
                item = TodoItem(
                    list_id=todo_list.id,
                    content=item_content.strip(),
                    order_num=idx
                )
                db.session.add(item)
        
        db.session.commit()
        flash(f'Todo list "{todo_list.title}" created!', 'success')
        return redirect(url_for('todo.view_list', id=todo_list.id))
    
    # Get projects for attachment dropdown
    tch_projects = TCHProject.query.filter_by(status='active').all()
    personal_projects = PersonalProject.query.filter_by(status='active').all()
    
    return render_template('todo/create.html',
                         tch_projects=tch_projects,
                         personal_projects=personal_projects,
                         active='todo')

@todo_bp.route('/list/<int:id>')
def view_list(id):
    """View and manage a specific todo list"""
    todo_list = TodoList.query.get_or_404(id)
    return render_template('todo/view_list.html',
                         todo_list=todo_list,
                         active='todo')

@todo_bp.route('/list/<int:id>/add-item', methods=['POST'])
def add_item(id):
    """Add item to todo list"""
    todo_list = TodoList.query.get_or_404(id)
    
    item = TodoItem(
        list_id=id,
        content=request.form.get('content'),
        priority=request.form.get('priority') == 'on',
        due_date=datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date() if request.form.get('due_date') else None
    )
    
    # Set order number
    max_order = db.session.query(db.func.max(TodoItem.order_num)).filter_by(list_id=id).scalar()
    item.order_num = (max_order or 0) + 1
    
    db.session.add(item)
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'id': item.id})
    
    flash('Item added!', 'success')
    return redirect(url_for('todo.view_list', id=id))

@todo_bp.route('/item/<int:item_id>/toggle', methods=['POST'])
def toggle_item(item_id):
    """Toggle item completion"""
    item = TodoItem.query.get_or_404(item_id)
    item.completed = not item.completed
    
    if item.completed:
        item.completed_at = datetime.utcnow()
    else:
        item.completed_at = None
    
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'completed': item.completed})
    
    return redirect(url_for('todo.view_list', id=item.list_id))

@todo_bp.route('/item/<int:item_id>/delete', methods=['POST'])
def delete_item(item_id):
    """Delete todo item"""
    item = TodoItem.query.get_or_404(item_id)
    list_id = item.list_id
    db.session.delete(item)
    db.session.commit()
    
    flash('Item deleted!', 'success')
    return redirect(url_for('todo.view_list', id=list_id))

@todo_bp.route('/list/<int:id>/archive', methods=['POST'])
def archive_list(id):
    """Archive/unarchive todo list"""
    todo_list = TodoList.query.get_or_404(id)
    todo_list.is_archived = not todo_list.is_archived
    db.session.commit()
    
    flash(f'List {"archived" if todo_list.is_archived else "unarchived"}!', 'success')
    return redirect(url_for('todo.index'))

@todo_bp.route('/list/<int:id>/pin', methods=['POST'])
def pin_list(id):
    """Pin/unpin todo list"""
    todo_list = TodoList.query.get_or_404(id)
    todo_list.is_pinned = not todo_list.is_pinned
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'pinned': todo_list.is_pinned})
    
    return redirect(url_for('todo.view_list', id=id))

@todo_bp.route('/list/<int:id>/delete', methods=['POST'])
def delete_list(id):
    """Delete todo list"""
    todo_list = TodoList.query.get_or_404(id)
    db.session.delete(todo_list)
    db.session.commit()
    
    flash('Todo list deleted!', 'success')
    return redirect(url_for('todo.index'))

@todo_bp.route('/quick-create', methods=['POST'])
def quick_create():
    """Quick create from project page"""
    module = request.form.get('module')
    module_id = request.form.get('module_id')
    
    todo_list = TodoList(
        title=request.form.get('title'),
        module=module,
        module_id=int(module_id),
        color=request.form.get('color', 'yellow')
    )
    
    db.session.add(todo_list)
    db.session.commit()
    
    # Add items from the quick form
    items = request.form.get('items', '').split('\n')
    for idx, item_content in enumerate(items):
        if item_content.strip():
            item = TodoItem(
                list_id=todo_list.id,
                content=item_content.strip(),
                order_num=idx
            )
            db.session.add(item)
    
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'list_id': todo_list.id,
            'title': todo_list.title
        })
    
    flash(f'Todo list "{todo_list.title}" created!', 'success')
    
    # Redirect back to the project
    if module == 'tch_project':
        return redirect(url_for('projects.tch_detail', id=module_id))
    elif module == 'personal_project':
        return redirect(url_for('projects.personal_detail', id=module_id))
    
    return redirect(url_for('todo.index'))

# Add these new routes to modules/todo/routes.py after the existing routes

# ==================== PHASE 2: ENHANCED API ROUTES ====================

@todo_bp.route('/api/quick-add', methods=['POST'])
def api_quick_add():
    """Quick add a task with smart parsing"""
    data = request.get_json()
    
    try:
        title = data.get('title', '').strip()
        if not title:
            return jsonify({'success': False, 'message': 'Task title is required'}), 400
        
        source = data.get('source', 'todo')
        priority = data.get('priority', 'medium')
        due_date = data.get('due_date')
        project_id = data.get('project_id')
        
        # Parse due date if provided as string
        if due_date and isinstance(due_date, str):
            try:
                due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
            except:
                due_date = None
        
        # Route to appropriate creation method based on source
        if source == 'tch':
            # Create TCH task - need to find or create a project
            if not project_id:
                # Find first active TCH project or create a default one
                project = TCHProject.query.filter_by(status='active').first()
                if not project:
                    project = TCHProject(
                        name='Quick Tasks',
                        description='Tasks created via quick add',
                        status='active',
                        priority='medium'
                    )
                    db.session.add(project)
                    db.session.flush()
                project_id = project.id
            
            task = TCHTask(
                project_id=project_id,
                title=title,
                priority=priority,
                due_date=due_date,
                category='General',
                created_at=datetime.utcnow()
            )
            db.session.add(task)
            
        elif source == 'personal':
            # Create Personal task
            if not project_id:
                project = PersonalProject.query.filter_by(status='active').first()
                if not project:
                    project = PersonalProject(
                        name='Quick Tasks',
                        description='Tasks created via quick add',
                        status='active',
                        priority='medium'
                    )
                    db.session.add(project)
                    db.session.flush()
                project_id = project.id
            
            task = PersonalTask(
                project_id=project_id,
                content=title,  # PersonalTask uses 'content' not 'title'
                category='General',
                created_at=datetime.utcnow()
            )
            db.session.add(task)
            
        else:  # Default to todo
            # Create or find a quick-add todo list
            todo_list = TodoList.query.filter_by(title='Quick Tasks', is_archived=False).first()
            if not todo_list:
                todo_list = TodoList(
                    title='Quick Tasks',
                    description='Tasks created via quick add',
                    color='blue',
                    is_pinned=True
                )
                db.session.add(todo_list)
                db.session.flush()
            
            # Get max order number
            max_order = db.session.query(db.func.max(TodoItem.order_num)).filter_by(list_id=todo_list.id).scalar()
            
            item = TodoItem(
                list_id=todo_list.id,
                content=title,
                priority=(priority in ['high', 'critical']),
                due_date=due_date,
                order_num=(max_order or 0) + 1,
                created_at=datetime.utcnow()
            )
            db.session.add(item)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Task added successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@todo_bp.route('/api/task/<task_id>/update', methods=['POST'])
def api_update_task(task_id):
    """Update task title inline"""
    data = request.get_json()
    new_title = data.get('title', '').strip()
    
    if not new_title:
        return jsonify({'success': False, 'message': 'Title cannot be empty'}), 400
    
    try:
        source, source_id = task_id.split('_', 1)
        source_id = int(source_id)
        
        if source == 'tch':
            task = TCHTask.query.get(source_id)
            if task:
                task.title = new_title
        
        elif source == 'personal':
            task = PersonalTask.query.get(source_id)
            if task:
                task.content = new_title  # PersonalTask uses 'content'
        
        elif source == 'todo':
            item = TodoItem.query.get(source_id)
            if item:
                item.content = new_title
        
        elif source == 'daily':
            # Daily tasks typically shouldn't be edited, but we'll allow it
            task = DailyTask.query.get(source_id)
            if task:
                task.task_description = new_title
        else:
            return jsonify({'success': False, 'message': 'Invalid task source'}), 400
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@todo_bp.route('/api/task/<task_id>/delete', methods=['POST'])
def api_delete_task(task_id):
    """Delete a single task"""
    try:
        source, source_id = task_id.split('_', 1)
        source_id = int(source_id)
        
        if source == 'tch':
            task = TCHTask.query.get(source_id)
            if task:
                db.session.delete(task)
        
        elif source == 'personal':
            task = PersonalTask.query.get(source_id)
            if task:
                db.session.delete(task)
        
        elif source == 'todo':
            item = TodoItem.query.get(source_id)
            if item:
                db.session.delete(item)
        
        elif source == 'daily':
            task = DailyTask.query.get(source_id)
            if task:
                db.session.delete(task)
        else:
            return jsonify({'success': False, 'message': 'Invalid task source'}), 400
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@todo_bp.route('/api/bulk-complete', methods=['POST'])
def api_bulk_complete():
    """Mark multiple tasks as complete"""
    data = request.get_json()
    task_ids = data.get('task_ids', [])
    
    if not task_ids:
        return jsonify({'success': False, 'message': 'No tasks provided'}), 400
    
    completed_count = 0
    
    for task_id in task_ids:
        if TaskAggregator.complete_task(task_id):
            completed_count += 1
    
    return jsonify({
        'success': True,
        'message': f'Completed {completed_count} of {len(task_ids)} tasks'
    })


@todo_bp.route('/api/bulk-priority', methods=['POST'])
def api_bulk_priority():
    """Update priority for multiple tasks"""
    data = request.get_json()
    task_ids = data.get('task_ids', [])
    new_priority = data.get('priority', 'medium')
    
    if not task_ids:
        return jsonify({'success': False, 'message': 'No tasks provided'}), 400
    
    updated_count = 0
    
    try:
        for task_id in task_ids:
            source, source_id = task_id.split('_', 1)
            source_id = int(source_id)
            
            if source == 'tch':
                task = TCHTask.query.get(source_id)
                if task:
                    task.priority = new_priority
                    updated_count += 1
            
            elif source == 'personal':
                # Personal projects have priority, not individual tasks
                task = PersonalTask.query.get(source_id)
                if task and task.project:
                    task.project.priority = new_priority
                    updated_count += 1
            
            elif source == 'todo':
                item = TodoItem.query.get(source_id)
                if item:
                    # TodoItem priority is boolean, so map accordingly
                    item.priority = new_priority in ['high', 'critical']
                    updated_count += 1
            
            elif source == 'daily':
                task = DailyTask.query.get(source_id)
                if task:
                    # Map text priority to numeric for DailyTask
                    priority_map = {'critical': 1, 'high': 2, 'medium': 3, 'low': 4}
                    task.priority = priority_map.get(new_priority, 3)
                    updated_count += 1
        
        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'Updated priority for {updated_count} of {len(task_ids)} tasks'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@todo_bp.route('/api/bulk-delete', methods=['POST'])
def api_bulk_delete():
    """Delete multiple tasks"""
    data = request.get_json()
    task_ids = data.get('task_ids', [])
    
    if not task_ids:
        return jsonify({'success': False, 'message': 'No tasks provided'}), 400
    
    deleted_count = 0
    
    try:
        for task_id in task_ids:
            source, source_id = task_id.split('_', 1)
            source_id = int(source_id)
            
            if source == 'tch':
                task = TCHTask.query.get(source_id)
                if task:
                    db.session.delete(task)
                    deleted_count += 1
            
            elif source == 'personal':
                task = PersonalTask.query.get(source_id)
                if task:
                    db.session.delete(task)
                    deleted_count += 1
            
            elif source == 'todo':
                item = TodoItem.query.get(source_id)
                if item:
                    db.session.delete(item)
                    deleted_count += 1
            
            elif source == 'daily':
                task = DailyTask.query.get(source_id)
                if task:
                    db.session.delete(task)
                    deleted_count += 1
        
        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'Deleted {deleted_count} of {len(task_ids)} tasks'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# Add these Phase 3 routes to modules/todo/routes.py after Phase 2 routes

# ==================== PHASE 3: ADVANCED INTEGRATION ROUTES ====================

# Import the advanced integration modules at the top of routes.py
# from .advanced_integration import (
#     DependencyManager, RecurringTaskManager, TimeTracker,
#     TemplateManager, MetadataManager
# )

# --- Dependency Routes ---

@todo_bp.route('/api/dependencies/<task_id>')
def api_get_dependencies(task_id):
    """Get dependencies for a task"""
    deps = DependencyManager.get_dependencies(task_id)
    
    # Enrich with task details
    enriched = {
        'prerequisites': [],
        'dependents': [],
        'can_complete': True
    }
    
    # Get details for prerequisites
    for prereq_id in deps['prerequisites']:
        task = TaskAggregator.get_single_task(prereq_id)
        if task:
            enriched['prerequisites'].append({
                'id': prereq_id,
                'title': task.title,
                'completed': task.completed
            })
            if not task.completed and prereq_id in deps['blocked_by']:
                enriched['can_complete'] = False
    
    # Get details for dependents
    for dep_id in deps['dependents']:
        task = TaskAggregator.get_single_task(dep_id)
        if task:
            enriched['dependents'].append({
                'id': dep_id,
                'title': task.title,
                'completed': task.completed
            })
    
    return jsonify(enriched)


@todo_bp.route('/api/dependencies/add', methods=['POST'])
def api_add_dependency():
    """Add a dependency between tasks"""
    data = request.get_json()
    dependent_id = data.get('dependent_id')
    prerequisite_id = data.get('prerequisite_id')
    dep_type = data.get('type', 'blocks')
    
    if not dependent_id or not prerequisite_id:
        return jsonify({'success': False, 'message': 'Both task IDs required'}), 400
    
    if dependent_id == prerequisite_id:
        return jsonify({'success': False, 'message': 'Task cannot depend on itself'}), 400
    
    success = DependencyManager.add_dependency(dependent_id, prerequisite_id, dep_type)
    
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': 'Dependency already exists or error occurred'}), 400


@todo_bp.route('/api/dependencies/remove', methods=['POST'])
def api_remove_dependency():
    """Remove a dependency between tasks"""
    data = request.get_json()
    dependent_id = data.get('dependent_id')
    prerequisite_id = data.get('prerequisite_id')
    
    if not dependent_id or not prerequisite_id:
        return jsonify({'success': False, 'message': 'Both task IDs required'}), 400
    
    success = DependencyManager.remove_dependency(dependent_id, prerequisite_id)
    
    return jsonify({'success': success})


# --- Time Tracking Routes ---

@todo_bp.route('/api/time/start', methods=['POST'])
def api_start_timer():
    """Start time tracking for a task"""
    data = request.get_json()
    task_id = data.get('task_id')
    task_title = data.get('task_title', 'Task')
    
    if not task_id:
        return jsonify({'success': False, 'message': 'Task ID required'}), 400
    
    log = TimeTracker.start_timer(task_id, task_title)
    
    return jsonify({
        'success': True,
        'start_time': log.start_time.isoformat(),
        'log_id': log.id
    })


@todo_bp.route('/api/time/stop', methods=['POST'])
def api_stop_timer():
    """Stop time tracking for a task"""
    data = request.get_json()
    task_id = data.get('task_id')
    
    if not task_id:
        return jsonify({'success': False, 'message': 'Task ID required'}), 400
    
    log = TimeTracker.stop_timer(task_id)
    
    if log:
        return jsonify({
            'success': True,
            'duration_minutes': log.duration_minutes,
            'total_minutes': TimeTracker.get_total_time(task_id)
        })
    else:
        return jsonify({'success': False, 'message': 'No active timer found'}), 404
