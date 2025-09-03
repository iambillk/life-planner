# modules/todo/routes.py
from flask import render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
from . import todo_bp
from models import db, TodoList, TodoItem, TCHProject, PersonalProject

@todo_bp.route('/')
def index():
    """All todo lists dashboard"""
    standalone_lists = TodoList.query.filter_by(module=None, is_archived=False).order_by(TodoList.is_pinned.desc(), TodoList.created_at.desc()).all()
    archived_lists = TodoList.query.filter_by(is_archived=True).all()
    
    return render_template('todo/index.html', 
                         lists=standalone_lists,
                         archived_lists=archived_lists,
                         active='todo')

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
        
        # Redirect based on where it's attached
        if todo_list.module == 'tch_project':
            return redirect(url_for('projects.tch_detail', id=todo_list.module_id))
        elif todo_list.module == 'personal_project':
            return redirect(url_for('projects.personal_detail', id=todo_list.module_id))
        else:
            return redirect(url_for('todo.view', id=todo_list.id))
    
    # Get projects for attachment dropdown
    tch_projects = TCHProject.query.filter_by(status='active').all()
    personal_projects = PersonalProject.query.filter_by(status='active').all()
    
    return render_template('todo/create.html',
                         tch_projects=tch_projects,
                         personal_projects=personal_projects,
                         active='todo')

@todo_bp.route('/<int:id>')
def view(id):
    """View/edit a todo list"""
    todo_list = TodoList.query.get_or_404(id)
    
    # Get parent project if attached
    parent_project = None
    if todo_list.module == 'tch_project':
        parent_project = TCHProject.query.get(todo_list.module_id)
    elif todo_list.module == 'personal_project':
        parent_project = PersonalProject.query.get(todo_list.module_id)
    
    return render_template('todo/view.html',
                         todo_list=todo_list,
                         parent_project=parent_project,
                         active='todo')

@todo_bp.route('/<int:id>/add-item', methods=['POST'])
def add_item(id):
    """Add item to todo list"""
    todo_list = TodoList.query.get_or_404(id)
    
    # Get the highest order number
    max_order = db.session.query(db.func.max(TodoItem.order_num)).filter_by(list_id=id).scalar()
    
    item = TodoItem(
        list_id=id,
        content=request.form.get('content'),
        priority=request.form.get('priority') == 'on',
        order_num=(max_order or 0) + 1
    )
    
    if request.form.get('due_date'):
        item.due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date()
    
    db.session.add(item)
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'id': item.id})
    
    flash('Item added!', 'success')
    return redirect(url_for('todo.view', id=id))

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
        return jsonify({
            'completed': item.completed,
            'completion_percentage': item.todo_list.completion_percentage
        })
    
    return redirect(url_for('todo.view', id=item.list_id))

@todo_bp.route('/item/<int:item_id>/delete', methods=['POST'])
def delete_item(item_id):
    """Delete a todo item"""
    item = TodoItem.query.get_or_404(item_id)
    list_id = item.list_id
    db.session.delete(item)
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    
    flash('Item deleted!', 'success')
    return redirect(url_for('todo.view', id=list_id))

@todo_bp.route('/<int:id>/archive', methods=['POST'])
def archive(id):
    """Archive/unarchive a todo list"""
    todo_list = TodoList.query.get_or_404(id)
    todo_list.is_archived = not todo_list.is_archived
    db.session.commit()
    
    flash(f'List {"archived" if todo_list.is_archived else "unarchived"}!', 'success')
    return redirect(url_for('todo.index'))

@todo_bp.route('/<int:id>/pin', methods=['POST'])
def pin(id):
    """Pin/unpin a todo list"""
    todo_list = TodoList.query.get_or_404(id)
    todo_list.is_pinned = not todo_list.is_pinned
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'pinned': todo_list.is_pinned})
    
    return redirect(url_for('todo.view', id=id))

@todo_bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    """Delete a todo list"""
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