# modules/admin_tools/routes.py
"""
Admin Tools Routes
All routes for diagnostic tools and knowledge base
Version: 1.0.0
Created: 2025-01-08
"""

from flask import render_template, request, redirect, url_for, flash, jsonify, send_file, current_app
from datetime import datetime, timedelta
from sqlalchemy import func, desc
import json
import os

from . import live_routes  

from models.base import db
from models.admin_tools import (
    ToolExecution, KnowledgeItem, KnowledgeCategory, 
    KnowledgeTag, KnowledgeRelation, knowledge_item_tags
)
from . import admin_tools_bp
from .utils import (
    execute_tool, parse_tool_output, save_knowledge_file,
    allowed_file, format_file_size, get_file_icon,
    create_tool_history_summary, get_tool_config
)
from .constants import (
    TOOLS, TOOL_CATEGORIES, CONTENT_TYPES, SUGGESTED_TAGS,
    DOC_TEMPLATES, HISTORY_FILTERS
)

from models.ssh_logs import SSHSession, SSHCommand, SSHScanLog
from .ssh_scanner import scan_ssh_logs, get_scan_history, parse_single_log


# ==================== MAIN DASHBOARD ====================

@admin_tools_bp.route('/')
@admin_tools_bp.route('/dashboard')
def dashboard():
    """Main admin tools dashboard"""
    
    # Get recent tool executions
    recent_executions = ToolExecution.get_recent(limit=10)
    
    # Get pinned knowledge items
    pinned_items = KnowledgeItem.get_pinned()
    
    # Get recently accessed knowledge items
    recent_items = KnowledgeItem.get_recent(limit=5)
    
    # Get categories with item counts
    categories = KnowledgeCategory.query.all()
    category_stats = []
    for cat in categories:
        category_stats.append({
            'category': cat,
            'item_count': cat.items.count()
        })
    
    # Get tool usage stats (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    all_executions = ToolExecution.query.filter(
        ToolExecution.executed_at >= thirty_days_ago
    ).all()
    
    stats = create_tool_history_summary(all_executions)
    
    return render_template('admin_tools/dashboard.html',
                         tools=TOOLS,
                         tool_categories=TOOL_CATEGORIES,
                         recent_executions=recent_executions,
                         pinned_items=pinned_items,
                         recent_items=recent_items,
                         category_stats=category_stats,
                         stats=stats,
                         active='admin_tools')


# ==================== TOOL EXECUTION ====================

@admin_tools_bp.route('/tools')
def tools_list():
    """List all available tools"""
    return render_template('admin_tools/tools_list.html',
                         tools=TOOLS,
                         tool_categories=TOOL_CATEGORIES,
                         active='admin_tools')


@admin_tools_bp.route('/tool/execute/<tool_name>', methods=['GET', 'POST'])
def execute_tool_route(tool_name):
    """Execute a diagnostic tool"""
    
    tool_config = get_tool_config(tool_name)
    if not tool_config:
        flash(f'Unknown tool: {tool_name}', 'danger')
        return redirect(url_for('admin_tools.tools_list'))
    
    if request.method == 'POST':
        target = request.form.get('target', '').strip()
        notes = request.form.get('notes', '').strip()
        
        # Validate target if required
        if tool_config['accepts_target'] and not target:
            flash('Target is required for this tool', 'warning')
            return redirect(url_for('admin_tools.execute_tool_route', tool_name=tool_name))
        
        # Gather parameters
        parameters = {}
        for param in tool_config.get('parameters', []):
            param_name = param['name']
            if param['type'] == 'checkbox':
                parameters[param_name] = param_name in request.form
            else:
                value = request.form.get(param_name)
                if value:
                    parameters[param_name] = value
        
        # Execute the tool
        result = execute_tool(tool_name, target, parameters)
        
        # Parse output if parser available
        parsed_data = None
        if result['success']:
            parsed_data = parse_tool_output(tool_name, result['output'])
        
        # Get parsed_data from result if it exists (for DNS health check)
        if 'parsed_data' in result:
            parsed_data = result['parsed_data']
        
        # Save to database
        execution = ToolExecution(
            tool_name=tool_name,
            target=target,
            parameters=json.dumps(parameters),
            output=result['output'],
            exit_code=result['exit_code'],
            execution_time=result['execution_time'],
            notes=notes
        )
        db.session.add(execution)
        db.session.commit()
        
        flash(f'Tool executed: {tool_config["name"]}', 'success' if result['success'] else 'warning')

        # Use special template for Port Scanner results
        if tool_name == 'port_scan':
            return render_template('admin_tools/port_scan_result.html',
                                 tool_name=tool_name,
                                 tool_config=tool_config,
                                 execution=execution,
                                 result=result,
                                 parsed_data=parsed_data,
                                 active='admin_tools')
        
        # Use special template for DNS Health Check
        if tool_name == 'dns_health':
            return render_template('admin_tools/dns_health_result.html',
                                 tool_name=tool_name,
                                 tool_config=tool_config,
                                 execution=execution,
                                 result=result,
                                 parsed_data=parsed_data,
                                 active='admin_tools')
        
        # Default execution result template for other tools
        return render_template('admin_tools/execution_result.html',
                             tool_name=tool_name,
                             tool_config=tool_config,
                             execution=execution,
                             result=result,
                             parsed_data=parsed_data,
                             active='admin_tools')
    
    # GET request - show tool form with recent executions
    recent_executions = ToolExecution.query.filter_by(tool_name=tool_name)\
                                           .order_by(desc(ToolExecution.executed_at))\
                                           .limit(10)\
                                           .all()

    return render_template('admin_tools/tool_form.html',
                         tool_name=tool_name,
                         tool_config=tool_config,
                         recent_executions=recent_executions,
                         active='admin_tools')# GET request - show tool form
    return render_template('admin_tools/tool_form.html',
                         tool_name=tool_name,
                         tool_config=tool_config,
                         active='admin_tools')


@admin_tools_bp.route('/tool/rerun/<int:execution_id>')
def rerun_tool(execution_id):
    """Re-run a tool with same parameters"""
    execution = ToolExecution.query.get_or_404(execution_id)
    
    # Parse stored parameters
    parameters = json.loads(execution.parameters) if execution.parameters else {}
    
    # Execute again
    result = execute_tool(execution.tool_name, execution.target, parameters)
    
    # Save new execution
    new_execution = ToolExecution(
        tool_name=execution.tool_name,
        target=execution.target,
        parameters=execution.parameters,
        output=result['output'],
        exit_code=result['exit_code'],
        execution_time=result['execution_time'],
        notes=f"Re-run of execution #{execution_id}"
    )
    db.session.add(new_execution)
    db.session.commit()
    
    flash('Tool re-executed', 'success')
    return redirect(url_for('admin_tools.view_execution', execution_id=new_execution.id))


# ==================== TOOL HISTORY ====================

@admin_tools_bp.route('/history')
def tool_history():
    """View tool execution history"""
    
    # Filters
    tool_name = request.args.get('tool')
    target = request.args.get('target')
    filter_period = request.args.get('period', 'all')
    
    # Build query
    query = ToolExecution.query
    
    if tool_name:
        query = query.filter_by(tool_name=tool_name)
    
    if target:
        query = query.filter(ToolExecution.target.ilike(f'%{target}%'))
    
    # Apply time filter
    if filter_period in HISTORY_FILTERS:
        days = HISTORY_FILTERS[filter_period]['days']
        if days:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = query.filter(ToolExecution.executed_at >= cutoff)
    
    # Get results
    executions = query.order_by(desc(ToolExecution.executed_at)).limit(100).all()
    
    # Generate stats for filtered results
    stats = create_tool_history_summary(executions)
    
    return render_template('admin_tools/history.html',
                         executions=executions,
                         stats=stats,
                         tools=TOOLS,
                         tool_categories=TOOL_CATEGORIES,
                         history_filters=HISTORY_FILTERS,
                         current_filter=filter_period,
                         active='admin_tools')


@admin_tools_bp.route('/execution/<int:execution_id>')
def view_execution(execution_id):
    """View details of a specific execution"""
    execution = ToolExecution.query.get_or_404(execution_id)
    
    tool_config = get_tool_config(execution.tool_name)
    parsed_data = parse_tool_output(execution.tool_name, execution.output)
    
    return render_template('admin_tools/execution_detail.html',
                         execution=execution,
                         tool_config=tool_config,
                         parsed_data=parsed_data,
                         active='admin_tools')


@admin_tools_bp.route('/execution/<int:execution_id>/delete', methods=['POST'])
def delete_execution(execution_id):
    """Delete a tool execution"""
    execution = ToolExecution.query.get_or_404(execution_id)
    db.session.delete(execution)
    db.session.commit()
    
    flash('Execution deleted', 'success')
    return redirect(url_for('admin_tools.tool_history'))


# ==================== KNOWLEDGE BASE ====================

@admin_tools_bp.route('/knowledge')
def knowledge_base():
    """Knowledge base main page"""
    
    # Filters
    category_id = request.args.get('category', type=int)
    search_query = request.args.get('q', '').strip()
    tag_filter = request.args.get('tag', '').strip()
    
    # Get all categories
    categories = KnowledgeCategory.query.all()
    
    # Build query
    if search_query or category_id or tag_filter:
        tags = [tag_filter] if tag_filter else None
        items = KnowledgeItem.search(search_query, category_id, tags)
    else:
        # Show all items, most recent first
        items = KnowledgeItem.query.order_by(desc(KnowledgeItem.updated_at)).all()
    
    # Get all tags for filter
    all_tags = KnowledgeTag.query.order_by(KnowledgeTag.name).all()
    
    # Get pinned items
    pinned = KnowledgeItem.get_pinned()
    
    return render_template('admin_tools/knowledge_base.html',
                         items=items,
                         categories=categories,
                         all_tags=all_tags,
                         pinned=pinned,
                         search_query=search_query,
                         active='admin_tools')


@admin_tools_bp.route('/knowledge/add', methods=['GET', 'POST'])
def add_knowledge_item():
    """Add new knowledge base item"""
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        content_type = request.form.get('content_type', 'text')
        category_id = request.form.get('category_id', type=int)
        tags_input = request.form.get('tags', '').strip()
        is_pinned = 'is_pinned' in request.form
        
        if not title:
            flash('Title is required', 'warning')
            return redirect(url_for('admin_tools.add_knowledge_item'))
        
        # Create item
        item = KnowledgeItem(
            title=title,
            description=description,
            content_type=content_type,
            category_id=category_id,
            is_pinned=is_pinned
        )
        
        # Handle content based on type
        if content_type == 'text':
            item.content_text = request.form.get('content_text', '')
        
        elif content_type == 'file':
            if 'file' in request.files:
                file = request.files['file']
                if file and allowed_file(file.filename):
                    try:
                        category = KnowledgeCategory.query.get(category_id)
                        cat_name = category.name if category else 'misc'
                        
                        filename, filepath, file_size, mime_type = save_knowledge_file(file, cat_name)
                        
                        item.file_path = filepath
                        item.file_size = file_size
                        item.mime_type = mime_type
                    except Exception as e:
                        flash(f'Error uploading file: {str(e)}', 'danger')
                        return redirect(url_for('admin_tools.add_knowledge_item'))
        
        elif content_type == 'url':
            item.content_text = request.form.get('url', '')
        
        db.session.add(item)
        db.session.flush()  # Get item ID
        
        # Add tags
        if tags_input:
            tag_names = [t.strip() for t in tags_input.split(',') if t.strip()]
            for tag_name in tag_names:
                tag = KnowledgeTag.get_or_create(tag_name)
                item.tags.append(tag)
        
        db.session.commit()
        
        flash(f'Knowledge item added: {title}', 'success')
        return redirect(url_for('admin_tools.view_knowledge_item', item_id=item.id))
    
    # GET - show form
    categories = KnowledgeCategory.query.all()
    
    return render_template('admin_tools/add_knowledge_item.html',
                         categories=categories,
                         content_types=CONTENT_TYPES,
                         suggested_tags=SUGGESTED_TAGS,
                         active='admin_tools')


@admin_tools_bp.route('/knowledge/<int:item_id>')
def view_knowledge_item(item_id):
    """View knowledge base item"""
    item = KnowledgeItem.query.get_or_404(item_id)
    
    # Increment access counter
    item.increment_access()
    
    # Get related items
    related = []
    for relation in item.related_from:
        if relation.related_item_id:
            related_item = KnowledgeItem.query.get(relation.related_item_id)
            if related_item:
                related.append(related_item)
        elif relation.tool_execution_id:
            execution = ToolExecution.query.get(relation.tool_execution_id)
            if execution:
                related.append({'type': 'execution', 'data': execution})
    
    return render_template('admin_tools/knowledge_item.html',
                         item=item,
                         related=related,
                         format_file_size=format_file_size,
                         get_file_icon=get_file_icon,
                         active='admin_tools')


@admin_tools_bp.route('/knowledge/<int:item_id>/edit', methods=['GET', 'POST'])
def edit_knowledge_item(item_id):
    """Edit knowledge base item"""
    item = KnowledgeItem.query.get_or_404(item_id)
    
    if request.method == 'POST':
        item.title = request.form.get('title', '').strip()
        item.description = request.form.get('description', '').strip()
        item.is_pinned = 'is_pinned' in request.form
        
        # Update content based on type
        if item.content_type == 'text':
            item.content_text = request.form.get('content_text', '')
        elif item.content_type == 'url':
            item.content_text = request.form.get('url', '')
        
        # Update tags
        tags_input = request.form.get('tags', '').strip()
        item.tags.clear()
        if tags_input:
            tag_names = [t.strip() for t in tags_input.split(',') if t.strip()]
            for tag_name in tag_names:
                tag = KnowledgeTag.get_or_create(tag_name)
                item.tags.append(tag)
        
        item.updated_at = datetime.utcnow()
        item.version += 1
        
        db.session.commit()
        
        flash('Knowledge item updated', 'success')
        return redirect(url_for('admin_tools.view_knowledge_item', item_id=item.id))
    
    # GET - show edit form
    categories = KnowledgeCategory.query.all()
    tag_string = ', '.join([tag.name for tag in item.tags])
    
    return render_template('admin_tools/edit_knowledge_item.html',
                         item=item,
                         categories=categories,
                         tag_string=tag_string,
                         suggested_tags=SUGGESTED_TAGS,
                         active='admin_tools')


@admin_tools_bp.route('/knowledge/<int:item_id>/delete', methods=['POST'])
def delete_knowledge_item(item_id):
    """Delete knowledge base item"""
    item = KnowledgeItem.query.get_or_404(item_id)
    
    # Delete file if exists
    if item.file_path:
        try:
            file_full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], item.file_path)
            if os.path.exists(file_full_path):
                os.remove(file_full_path)
        except Exception as e:
            flash(f'Warning: Could not delete file: {str(e)}', 'warning')
    
    db.session.delete(item)
    db.session.commit()
    
    flash('Knowledge item deleted', 'success')
    return redirect(url_for('admin_tools.knowledge_base'))


@admin_tools_bp.route('/knowledge/<int:item_id>/download')
def download_knowledge_file(item_id):
    """Download knowledge base file"""
    item = KnowledgeItem.query.get_or_404(item_id)
    
    if not item.file_path:
        flash('No file available for download', 'warning')
        return redirect(url_for('admin_tools.view_knowledge_item', item_id=item.id))
    
    file_full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], item.file_path)
    
    if not os.path.exists(file_full_path):
        flash('File not found', 'danger')
        return redirect(url_for('admin_tools.view_knowledge_item', item_id=item.id))
    
    # Extract original filename
    original_filename = os.path.basename(item.file_path).split('_', 1)[1] if '_' in os.path.basename(item.file_path) else os.path.basename(item.file_path)
    
    return send_file(file_full_path, as_attachment=True, download_name=original_filename)


@admin_tools_bp.route('/knowledge/<int:item_id>/toggle_pin', methods=['POST'])
def toggle_pin(item_id):
    """Toggle pinned status"""
    item = KnowledgeItem.query.get_or_404(item_id)
    item.is_pinned = not item.is_pinned
    db.session.commit()
    
    status = 'pinned' if item.is_pinned else 'unpinned'
    flash(f'Item {status}', 'success')
    
    return redirect(request.referrer or url_for('admin_tools.knowledge_base'))


# ==================== CATEGORIES & TAGS ====================

@admin_tools_bp.route('/categories')
def manage_categories():
    """Manage knowledge base categories"""
    categories = KnowledgeCategory.query.all()
    
    return render_template('admin_tools/categories.html',
                         categories=categories,
                         active='admin_tools')


@admin_tools_bp.route('/category/add', methods=['POST'])
def add_category():
    """Add new category"""
    name = request.form.get('name', '').strip()
    icon = request.form.get('icon', '📁').strip()
    description = request.form.get('description', '').strip()
    
    if not name:
        flash('Category name is required', 'warning')
        return redirect(url_for('admin_tools.manage_categories'))
    
    category = KnowledgeCategory(name=name, icon=icon, description=description)
    db.session.add(category)
    db.session.commit()
    
    flash(f'Category added: {name}', 'success')
    return redirect(url_for('admin_tools.manage_categories'))


# ==================== API ENDPOINTS ====================

@admin_tools_bp.route('/api/quick-execute', methods=['POST'])
def api_quick_execute():
    """Quick tool execution via AJAX"""
    data = request.get_json()
    
    tool_name = data.get('tool_name')
    target = data.get('target')
    
    if not tool_name:
        return jsonify({'success': False, 'error': 'Tool name required'}), 400
    
    result = execute_tool(tool_name, target)
    
    # Save to database
    execution = ToolExecution(
        tool_name=tool_name,
        target=target,
        output=result['output'],
        exit_code=result['exit_code'],
        execution_time=result['execution_time']
    )
    db.session.add(execution)
    db.session.commit()
    
    return jsonify({
        'success': result['success'],
        'output': result['output'],
        'execution_id': execution.id,
        'execution_time': result['execution_time']
    })

# ==================== SSH SESSION LOGS ====================

@admin_tools_bp.route('/ssh-logs')
def ssh_logs_dashboard():
    """SSH logs main dashboard"""
    
    # Get statistics
    stats = SSHSession.get_stats(days=30)
    
    # Get recent sessions
    recent_sessions = SSHSession.get_recent(limit=20)
    
    # Get unique hosts for filter
    unique_hosts = SSHSession.get_unique_hosts()
    
    # Get last scan info
    last_scan = SSHScanLog.get_last_scan()
    
    # Get top commands
    top_commands = SSHCommand.get_top_commands(limit=10)
    
    return render_template('admin_tools/ssh_logs_dashboard.html',
                         stats=stats,
                         recent_sessions=recent_sessions,
                         unique_hosts=unique_hosts,
                         last_scan=last_scan,
                         top_commands=top_commands,
                         active='admin_tools')


@admin_tools_bp.route('/ssh-logs/sessions')
def ssh_logs_sessions():
    """Browse all SSH sessions with filtering"""
    
    # Filters
    host_filter = request.args.get('host')
    user_filter = request.args.get('user')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    # Build query
    query = SSHSession.query
    
    if host_filter:
        query = query.filter_by(hostname=host_filter)
    
    if user_filter:
        query = query.filter_by(username=user_filter)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(SSHSession.session_start >= date_from_obj)
        except:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            query = query.filter(SSHSession.session_start <= date_to_obj)
        except:
            pass
    
    if search_query:
        sessions = SSHSession.search(search_query)
        # Manual pagination for search results
        total = len(sessions)
        start = (page - 1) * per_page
        end = start + per_page
        sessions = sessions[start:end]
        has_next = end < total
        has_prev = page > 1
    else:
        # Use SQLAlchemy pagination
        query = query.order_by(SSHSession.session_start.desc())
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        sessions = paginated.items
        has_next = paginated.has_next
        has_prev = paginated.has_prev
        total = paginated.total
    
    # Get filter options
    unique_hosts = SSHSession.get_unique_hosts()
    unique_users = db.session.query(SSHSession.username).distinct().filter(SSHSession.username.isnot(None)).all()
    unique_users = [u[0] for u in unique_users]
    
    return render_template('admin_tools/ssh_logs_sessions.html',
                         sessions=sessions,
                         unique_hosts=unique_hosts,
                         unique_users=unique_users,
                         host_filter=host_filter,
                         user_filter=user_filter,
                         date_from=date_from,
                         date_to=date_to,
                         search_query=search_query,
                         page=page,
                         has_next=has_next,
                         has_prev=has_prev,
                         total=total,
                         active='admin_tools')


@admin_tools_bp.route('/ssh-logs/session/<int:session_id>')
def ssh_logs_session_detail(session_id):
    """View detailed information about a specific SSH session"""
    
    session = SSHSession.query.get_or_404(session_id)
    
    # Get all commands for this session
    commands = SSHCommand.query.filter_by(session_id=session_id)\
                               .order_by(SSHCommand.sequence_number)\
                               .all()
    
    # Get related sessions (same host, around same time)
    related_sessions = SSHSession.query.filter(
        SSHSession.hostname == session.hostname,
        SSHSession.id != session.id
    ).order_by(SSHSession.session_start.desc()).limit(5).all()
    
    # Read full log file if it exists
    log_content = None
    if session.file_path and os.path.exists(session.file_path):
        try:
            with open(session.file_path, 'r', encoding='utf-8', errors='replace') as f:
                log_content = f.read()
        except Exception as e:
            log_content = f"Error reading log file: {e}"
    
    return render_template('admin_tools/ssh_logs_session_detail.html',
                         session=session,
                         commands=commands,
                         related_sessions=related_sessions,
                         log_content=log_content,
                         active='admin_tools')


@admin_tools_bp.route('/ssh-logs/session/<int:session_id>/edit', methods=['GET', 'POST'])
def ssh_logs_session_edit(session_id):
    """Edit session metadata (notes, tags, flagged status)"""
    
    session = SSHSession.query.get_or_404(session_id)
    
    if request.method == 'POST':
        session.notes = request.form.get('notes', '').strip()
        session.tags = request.form.get('tags', '').strip()
        session.is_flagged = 'is_flagged' in request.form
        
        db.session.commit()
        flash('Session updated', 'success')
        return redirect(url_for('admin_tools.ssh_logs_session_detail', session_id=session_id))
    
    return render_template('admin_tools/ssh_logs_session_edit.html',
                         session=session,
                         active='admin_tools')


@admin_tools_bp.route('/ssh-logs/session/<int:session_id>/delete', methods=['POST'])
def ssh_logs_session_delete(session_id):
    """Delete a session from database (does not delete log file)"""
    
    session = SSHSession.query.get_or_404(session_id)
    
    # Confirmation check
    if request.form.get('confirm') != 'yes':
        flash('Deletion cancelled - confirmation required', 'warning')
        return redirect(url_for('admin_tools.ssh_logs_session_detail', session_id=session_id))
    
    db.session.delete(session)
    db.session.commit()
    
    flash('Session deleted from database', 'success')
    return redirect(url_for('admin_tools.ssh_logs_sessions'))


@admin_tools_bp.route('/ssh-logs/scan', methods=['GET', 'POST'])
def ssh_logs_scan():
    """Scan NAS directory for new SSH logs"""
    
    if request.method == 'POST':
        # Get scan path from form or use default from config
        scan_path = request.form.get('scan_path') or current_app.config.get('SSH_LOG_PATH')
        
        if not scan_path:
            flash('No scan path configured. Please set SSH_LOG_PATH in config.py', 'danger')
            return redirect(url_for('admin_tools.ssh_logs_scan'))
        
        try:
            # Run the scan
            stats = scan_ssh_logs(scan_path)
            
            flash(f'Scan completed! Found {stats["files_found"]} files. '
                  f'New: {stats["files_new"]}, Updated: {stats["files_updated"]}, '
                  f'Skipped: {stats["files_skipped"]}, Errors: {stats["files_error"]}', 
                  'success')
            
            return redirect(url_for('admin_tools.ssh_logs_dashboard'))
            
        except Exception as e:
            flash(f'Scan error: {str(e)}', 'danger')
            return redirect(url_for('admin_tools.ssh_logs_scan'))
    
    # GET - show scan form
    scan_history = get_scan_history(limit=10)
    default_path = current_app.config.get('SSH_LOG_PATH', '')
    
    return render_template('admin_tools/ssh_logs_scan.html',
                         scan_history=scan_history,
                         default_path=default_path,
                         active='admin_tools')


@admin_tools_bp.route('/ssh-logs/analytics')
def ssh_logs_analytics():
    """SSH logs analytics and insights"""
    
    # Get stats for different time periods
    stats_7d = SSHSession.get_stats(days=7)
    stats_30d = SSHSession.get_stats(days=30)
    stats_all = SSHSession.get_stats(days=None)  # All time
    
    # Get top commands
    top_commands = SSHCommand.get_top_commands(limit=20, days=30)
    
    # Get session frequency by day of week
    from sqlalchemy import func, extract
    sessions_by_dow = db.session.query(
        extract('dow', SSHSession.session_start).label('dow'),
        func.count(SSHSession.id).label('count')
    ).group_by('dow').order_by('dow').all()
    
    # Convert dow numbers to day names
    day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    dow_data = {day_names[int(dow)]: count for dow, count in sessions_by_dow}
    
    # Get sessions by hour of day
    sessions_by_hour = db.session.query(
        extract('hour', SSHSession.session_start).label('hour'),
        func.count(SSHSession.id).label('count')
    ).group_by('hour').order_by('hour').all()
    
    hour_data = {int(hour): count for hour, count in sessions_by_hour}
    
    # Get host activity breakdown
    host_activity = db.session.query(
        SSHSession.hostname,
        SSHSession.friendly_name,
        func.count(SSHSession.id).label('session_count'),
        func.sum(SSHSession.duration_seconds).label('total_duration'),
        func.avg(SSHSession.duration_seconds).label('avg_duration')
    ).filter(SSHSession.hostname.isnot(None))\
     .group_by(SSHSession.hostname, SSHSession.friendly_name)\
     .order_by(func.count(SSHSession.id).desc())\
     .limit(10)\
     .all()
    
    # Get command type distribution
    command_type_dist = db.session.query(
        SSHCommand.command_type,
        func.count(SSHCommand.id).label('count')
    ).group_by(SSHCommand.command_type)\
     .order_by(func.count(SSHCommand.id).desc())\
     .all()
    
    return render_template('admin_tools/ssh_logs_analytics.html',
                         stats_7d=stats_7d,
                         stats_30d=stats_30d,
                         stats_all=stats_all,
                         top_commands=top_commands,
                         dow_data=dow_data,
                         hour_data=hour_data,
                         host_activity=host_activity,
                         command_type_dist=command_type_dist,
                         active='admin_tools')


@admin_tools_bp.route('/ssh-logs/host/<hostname>')
def ssh_logs_host_profile(hostname):
    """View all sessions and stats for a specific host"""
    
    # Get all sessions for this host
    sessions = SSHSession.get_by_host(hostname)
    
    if not sessions:
        flash(f'No sessions found for host: {hostname}', 'warning')
        return redirect(url_for('admin_tools.ssh_logs_dashboard'))
    
    # Calculate host-specific stats
    total_sessions = len(sessions)
    total_duration = sum(s.duration_seconds or 0 for s in sessions)
    avg_duration = total_duration / total_sessions if total_sessions > 0 else 0
    
    # Get most common commands on this host
    host_commands = db.session.query(
        SSHCommand.command_text,
        func.count(SSHCommand.id).label('count')
    ).join(SSHSession)\
     .filter(SSHSession.hostname == hostname)\
     .group_by(SSHCommand.command_text)\
     .order_by(func.count(SSHCommand.id).desc())\
     .limit(10)\
     .all()
    
    # Get most active user on this host
    user_activity = db.session.query(
        SSHSession.username,
        func.count(SSHSession.id).label('count')
    ).filter(SSHSession.hostname == hostname)\
     .filter(SSHSession.username.isnot(None))\
     .group_by(SSHSession.username)\
     .order_by(func.count(SSHSession.id).desc())\
     .all()
    
    friendly_name = sessions[0].friendly_name if sessions else hostname
    
    return render_template('admin_tools/ssh_logs_host_profile.html',
                         hostname=hostname,
                         friendly_name=friendly_name,
                         sessions=sessions,
                         total_sessions=total_sessions,
                         total_duration=total_duration,
                         avg_duration=avg_duration,
                         host_commands=host_commands,
                         user_activity=user_activity,
                         active='admin_tools')


@admin_tools_bp.route('/ssh-logs/search-commands')
def ssh_logs_search_commands():
    """Search across all commands"""
    
    search_query = request.args.get('q', '').strip()
    command_type_filter = request.args.get('type')
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    if not search_query and not command_type_filter:
        return render_template('admin_tools/ssh_logs_search_commands.html',
                             commands=[],
                             search_query='',
                             command_type_filter=None,
                             active='admin_tools')
    
    # Build query
    query = SSHCommand.query.join(SSHSession)
    
    if search_query:
        search_term = f'%{search_query}%'
        query = query.filter(SSHCommand.command_text.ilike(search_term))
    
    if command_type_filter:
        query = query.filter(SSHCommand.command_type == command_type_filter)
    
    # Paginate
    query = query.order_by(SSHCommand.timestamp.desc())
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Get available command types for filter
    command_types = db.session.query(SSHCommand.command_type)\
                              .distinct()\
                              .filter(SSHCommand.command_type.isnot(None))\
                              .all()
    command_types = [ct[0] for ct in command_types]
    
    return render_template('admin_tools/ssh_logs_search_commands.html',
                         commands=paginated.items,
                         search_query=search_query,
                         command_type_filter=command_type_filter,
                         command_types=command_types,
                         page=page,
                         has_next=paginated.has_next,
                         has_prev=paginated.has_prev,
                         total=paginated.total,
                         active='admin_tools')


# ==================== API ENDPOINTS FOR SSH LOGS ====================

@admin_tools_bp.route('/api/ssh-logs/quick-stats')
def api_ssh_logs_quick_stats():
    """Quick stats API for dashboard widgets"""
    
    stats = SSHSession.get_stats(days=7)
    
    return jsonify({
        'success': True,
        'stats': stats
    })


@admin_tools_bp.route('/api/ssh-logs/recent-sessions')
def api_ssh_logs_recent_sessions():
    """Get recent sessions as JSON"""
    
    limit = request.args.get('limit', 10, type=int)
    sessions = SSHSession.get_recent(limit=limit)
    
    sessions_data = []
    for s in sessions:
        sessions_data.append({
            'id': s.id,
            'hostname': s.hostname,
            'friendly_name': s.friendly_name,
            'username': s.username,
            'session_start': s.session_start.isoformat() if s.session_start else None,
            'duration': s.duration_formatted,
            'command_count': s.command_count
        })
    
    return jsonify({
        'success': True,
        'sessions': sessions_data
    })