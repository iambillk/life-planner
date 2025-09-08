# modules/daily/routes.py
"""
Daily Planner Routes - The Drill Sergeant System
Complete working version with fixed project rotation
"""

from flask import render_template, request, redirect, url_for, jsonify, flash
from datetime import datetime, date, timedelta
from . import daily_bp

# Import from models
from models import (
    db,
    DailyConfig, 
    CalendarEvent, 
    EventType, 
    DailyTask,
    HumanMaintenance, 
    CapturedNote, 
    HarassmentLog,
    ProjectRotation,
    TCHProject,
    PersonalProject
)


# ============ MAIN DASHBOARD ============

@daily_bp.route('/')
def index():
    """Main daily planner view - Command Center"""
    
    # Get today's date
    today = date.today()
    
    # Get human maintenance status
    human = HumanMaintenance.get_today()
    
    # Check if user is locked out (only if lockout is enabled)
    lockout = False
    lockout_message = None
    lockout_enabled = DailyConfig.get('lockout_enabled', 'true') == 'true'
    morning_lockout_tasks = int(DailyConfig.get('morning_lockout_tasks', '2'))
    
    if lockout_enabled and human.morning_complete < morning_lockout_tasks:
        lockout = True
        lockout_message = get_lockout_message(human)
    
    # Get today's calendar events
    today_events = CalendarEvent.query.filter_by(
        event_date=today
    ).order_by(CalendarEvent.event_time).all()
    
    # Get tomorrow's events
    tomorrow_events = CalendarEvent.query.filter_by(
        event_date=today + timedelta(days=1)
    ).order_by(CalendarEvent.event_time).all()
    
    # Get today's project tasks (if not locked out)
    daily_tasks = []
    if not lockout:
        daily_tasks = DailyTask.query.filter_by(
            date=today,
            completed=False
        ).order_by(DailyTask.priority).all()
        
        # Filter out orphaned tasks (where project was deleted)
        valid_tasks = []
        for task in daily_tasks:
            if task.project_type == 'TCH':
                project = TCHProject.query.get(task.project_id)
            else:
                project = PersonalProject.query.get(task.project_id)
            
            if project:  # Only include if project still exists
                valid_tasks.append(task)
            else:
                # Clean up orphaned task
                db.session.delete(task)
        
        db.session.commit()
        daily_tasks = valid_tasks
        
        # If no tasks for today, auto-select some
        if not daily_tasks:
            daily_tasks = auto_select_tasks()
    
    # Get captured notes
    notes = CapturedNote.query.filter_by(
        date=today,
        resolved=False
    ).all()
    
    # Group notes by category
    notes_by_category = {}
    for note in notes:
        if note.category not in notes_by_category:
            notes_by_category[note.category] = []
        notes_by_category[note.category].append(note)
    
    # Get harassment message for current time
    harassment = get_current_harassment(human)
    
    # Get evening review settings - IMPORTANT!
    evening_review_hour = int(DailyConfig.get('evening_review_hour', '20'))
    evening_review_end_hour = int(DailyConfig.get('evening_review_end_hour', '3'))
    
    # Check if it's evening review time (handle midnight crossover)
    current_hour = datetime.now().hour
    if evening_review_end_hour < evening_review_hour:  # Crosses midnight
        show_evening_review = current_hour >= evening_review_hour or current_hour <= evening_review_end_hour
    else:
        show_evening_review = evening_review_hour <= current_hour <= evening_review_end_hour
    
    # Get featured projects for motivation
    featured_projects = get_featured_projects()
    
    return render_template(
        'daily/dashboard.html',
        today=today,
        human=human,
        lockout=lockout,
        lockout_message=lockout_message,
        today_events=today_events,
        tomorrow_events=tomorrow_events,
        daily_tasks=daily_tasks,
        notes_by_category=notes_by_category,
        harassment=harassment,
        show_evening_review=show_evening_review,
        evening_review_hour=evening_review_hour,
        evening_review_end_hour=evening_review_end_hour,
        featured_projects=featured_projects,
        active='daily'
    )


# ============ HELPER FUNCTIONS ============

def get_lockout_message(human):
    """Generate appropriate lockout message based on what's missing"""
    messages = []
    
    messages.append("YOU'RE LOCKED OUT!\n")
    messages.append("You haven't done the bare minimum to be human today:\n")
    
    if not human.meds_taken:
        messages.append("❌ TAKE YOUR MEDS")
    if not human.shower_taken and human.days_since_shower >= 2:
        messages.append(f"❌ SHOWER (it's been {human.days_since_shower} days, that's disgusting)")
    if not human.teeth_brushed_am:
        messages.append("❌ BRUSH YOUR TEETH")
    if not human.breakfast:
        messages.append("❌ EAT BREAKFAST")
    
    messages.append("\nComplete at least 2 to unlock your projects.")
    messages.append("\nYour projects are locked until you act like a human.")
    
    return "\n".join(messages)


def get_current_harassment(human):
    """Get time-appropriate harassment message"""
    
    # Check if harassment is enabled
    harassment_level = DailyConfig.get('harassment_level', 'BRUTAL')
    
    # If harassment is off, return nothing
    if harassment_level == 'OFF':
        return None
    
    now = datetime.now()
    hour = now.hour
    
    # Check quiet hours
    quiet_start = int(DailyConfig.get('quiet_start', '22'))
    quiet_end = int(DailyConfig.get('quiet_end', '6'))
    
    # Handle quiet hours (including midnight wraparound)
    if quiet_start > quiet_end:  # Wraps midnight (e.g., 22:00 to 06:00)
        if hour >= quiet_start or hour < quiet_end:
            return None  # It's quiet time
    else:  # Normal hours (e.g., 06:00 to 22:00)
        if quiet_start <= hour < quiet_end:
            return None  # It's quiet time
    
    # Generate messages based on harassment level
    messages = {
        'BRUTAL': {
            'meds': "TAKE YOUR MEDS NOW! It's been hours, you absolute disaster!",
            'lunch': "EAT LUNCH! Coffee is not food, you're destroying yourself!",
            'water': f"Only {human.water_glasses} glasses of water? You're basically a raisin!",
            'dinner': "Eat dinner NOW! Real food! Stop being pathetic!",
            'shower': f"SHOWER TONIGHT! {human.days_since_shower} days is absolutely revolting!",
            'bedtime': "GET TO BED! You'll be worthless tomorrow if you don't sleep NOW!"
        },
        'MODERATE': {
            'meds': "Don't forget to take your medications soon.",
            'lunch': "Time for lunch - you need proper nutrition.",
            'water': f"You've had {human.water_glasses} glasses of water. Try to drink more.",
            'dinner': "Remember to eat a proper dinner.",
            'shower': f"It's been {human.days_since_shower} days - consider showering tonight.",
            'bedtime': "Getting late - you should head to bed soon."
        },
        'GENTLE': {
            'meds': "Medication reminder when you're ready.",
            'lunch': "Lunch time when you can.",
            'water': f"Water count: {human.water_glasses} glasses so far.",
            'dinner': "Dinner would be good when you're hungry.",
            'shower': "Shower when convenient.",
            'bedtime': "Consider winding down for the evening."
        }
    }
    
    # Select message set based on level
    msg_set = messages.get(harassment_level, messages['MODERATE'])
    
    # Return appropriate message for current time and status
    if hour < 9 and not human.meds_taken:
        return msg_set['meds']
    elif hour >= 12 and hour < 13 and not human.lunch:
        return msg_set['lunch']
    elif hour >= 14 and human.water_glasses < 4:
        return msg_set['water']
    elif hour >= 18 and not human.dinner:
        return msg_set['dinner']
    elif hour >= 21 and human.days_since_shower >= int(DailyConfig.get('shower_threshold_days', '2')):
        return msg_set['shower']
    elif hour >= 22:
        return msg_set['bedtime']
    
    return None


def auto_select_tasks():
    """Auto-select tasks for today based on neglect, deadlines, and rotation"""
    today_tasks = []
    today = date.today()
    
    # Get settings
    num_to_show = int(DailyConfig.get('projects_to_show', 5))
    
    # Collect ALL active projects (not completed)
    all_projects = []
    
    # Get all TCH projects (excluding completed)
    tch_projects = TCHProject.query.filter(
        TCHProject.status != 'completed'
    ).all()
    
    for project in tch_projects:
        # Check when this project was last shown
        last_shown = ProjectRotation.query.filter_by(
            project_id=project.id,
            project_type='TCH'
        ).order_by(ProjectRotation.date.desc()).first()
        
        days_since_shown = 999  # Default for never shown
        if last_shown:
            days_since_shown = (today - last_shown.date).days
        
        # Calculate priority score
        priority_score = 0
        
        # Deadline urgency (highest priority)
        if project.deadline:
            days_until_deadline = (project.deadline - today).days
            if days_until_deadline < 0:  # Overdue
                priority_score += 1000
            elif days_until_deadline <= 3:
                priority_score += 500
            elif days_until_deadline <= 7:
                priority_score += 200
            elif days_until_deadline <= 14:
                priority_score += 100
        
        # Project priority
        if project.priority == 'critical':
            priority_score += 300
        elif project.priority == 'high':
            priority_score += 200
        elif project.priority == 'medium':
            priority_score += 100
        
        # Days since shown (encourage rotation)
        priority_score += min(days_since_shown * 10, 200)  # Cap at 200
        
        # Status boost
        if project.status == 'active':
            priority_score += 50
        
        all_projects.append({
            'project': project,
            'type': 'TCH',
            'priority_score': priority_score,
            'days_since_shown': days_since_shown,
            'deadline': project.deadline
        })
    
    # Get all Personal projects (excluding completed)
    personal_projects = PersonalProject.query.filter(
        PersonalProject.status != 'completed'
    ).all()
    
    for project in personal_projects:
        # Check when this project was last shown
        last_shown = ProjectRotation.query.filter_by(
            project_id=project.id,
            project_type='Personal'
        ).order_by(ProjectRotation.date.desc()).first()
        
        days_since_shown = 999  # Default for never shown
        if last_shown:
            days_since_shown = (today - last_shown.date).days
        
        # Calculate priority score
        priority_score = 0
        
        # Deadline urgency (if personal project has deadline)
        if hasattr(project, 'deadline') and project.deadline:
            days_until_deadline = (project.deadline - today).days
            if days_until_deadline < 0:  # Overdue
                priority_score += 1000
            elif days_until_deadline <= 3:
                priority_score += 500
            elif days_until_deadline <= 7:
                priority_score += 200
            elif days_until_deadline <= 14:
                priority_score += 100
        
        # Project priority
        if project.priority == 'critical':
            priority_score += 300
        elif project.priority == 'high':
            priority_score += 200
        elif project.priority == 'medium':
            priority_score += 100
        
        # Days since shown (encourage rotation)
        priority_score += min(days_since_shown * 10, 200)  # Cap at 200
        
        # Status boost
        if project.status == 'active':
            priority_score += 50
        
        all_projects.append({
            'project': project,
            'type': 'Personal',
            'priority_score': priority_score,
            'days_since_shown': days_since_shown,
            'deadline': getattr(project, 'deadline', None)
        })
    
    # Sort all projects by priority score (highest first)
    all_projects.sort(key=lambda x: x['priority_score'], reverse=True)
    
    # Select top N projects
    selected_projects = all_projects[:num_to_show]
    
    # Create daily tasks for selected projects
    for proj_data in selected_projects:
        project = proj_data['project']
        project_type = proj_data['type']
        
        # Determine task description based on urgency
        task_description = f"Work on {project.name}"
        
        if proj_data['deadline']:
            days_until = (proj_data['deadline'] - today).days
            if days_until < 0:
                task_description = f"⚠️ OVERDUE: {project.name} - was due {abs(days_until)} days ago!"
            elif days_until == 0:
                task_description = f"🔥 DUE TODAY: {project.name}"
            elif days_until <= 3:
                task_description = f"⏰ {project.name} - Due in {days_until} days"
            elif days_until <= 7:
                task_description = f"📅 {project.name} - Due {proj_data['deadline'].strftime('%b %d')}"
            else:
                task_description = f"Work on {project.name}"
        elif proj_data['days_since_shown'] >= 7:
            task_description = f"📌 {project.name} - Neglected for {proj_data['days_since_shown']} days"
        
        # Determine priority for task ordering
        if proj_data['priority_score'] >= 1000:
            task_priority = 1  # Critical/Overdue
        elif proj_data['priority_score'] >= 500:
            task_priority = 2  # Urgent
        elif proj_data['priority_score'] >= 200:
            task_priority = 3  # High
        else:
            task_priority = 4  # Normal
        
        # Create the daily task
        task = DailyTask(
            date=today,
            project_id=project.id,
            project_type=project_type,
            project_name=f"{project.name} [{project.status.upper()}]",
            task_description=task_description,
            priority=task_priority
        )
        db.session.add(task)
        today_tasks.append(task)
        
        # Record in ProjectRotation table
        rotation = ProjectRotation(
            date=today,
            project_id=project.id,
            project_type=project_type,
            priority_score=proj_data['priority_score']
        )
        db.session.add(rotation)
    
    db.session.commit()
    
    # Log what was selected (for debugging)
    if today_tasks:
        selected_names = [t.project_name for t in today_tasks]
        HarassmentLog.add(
            f"Auto-selected {len(today_tasks)} projects: {', '.join(selected_names)}", 
            severity='info'
        )
    
    return today_tasks


def get_featured_projects():
    """Get 3 random projects to display as motivation"""
    # Get active projects
    projects = []
    
    tch = TCHProject.query.filter_by(status='active').limit(2).all()
    personal = PersonalProject.query.filter_by(status='active').limit(1).all()
    
    projects.extend(tch)
    projects.extend(personal)
    
    return projects


# ============ HUMAN MAINTENANCE ============

@daily_bp.route('/human/update', methods=['POST'])
def update_human():
    """Update human maintenance status"""
    human = HumanMaintenance.get_today()
    task = request.form.get('task')
    
    # Get harassment level for appropriate messaging
    harassment_level = DailyConfig.get('harassment_level', 'BRUTAL')
    
    # Message sets based on harassment level
    if harassment_level == 'BRUTAL':
        messages = {
            'meds': "Good. Meds taken. Now do something productive.",
            'shower': "Finally! You don't smell like a dumpster anymore.",
            'teeth_am': "Good. Your breath won't kill anyone now.",
            'breakfast': "Food consumed. You might actually function today.",
            'lunch': "Lunch eaten. Keep the momentum going.",
            'dinner': "Dinner done. You're almost acting like an adult.",
            'teeth_pm': "Night teeth brushed. One less thing to feel guilty about.",
            'water': f"Glass {human.water_glasses} down. Keep hydrating!",
            'unknown': "Unknown task."
        }
    elif harassment_level == 'MODERATE':
        messages = {
            'meds': "Medications taken ✓",
            'shower': "Shower complete ✓",
            'teeth_am': "Morning teeth brushed ✓",
            'breakfast': "Breakfast eaten ✓",
            'lunch': "Lunch complete ✓",
            'dinner': "Dinner finished ✓",
            'teeth_pm': "Evening teeth brushed ✓",
            'water': f"Water: {human.water_glasses} glasses",
            'unknown': "Task not recognized."
        }
    else:  # GENTLE or OFF
        messages = {
            'meds': "✓ Medications",
            'shower': "✓ Shower",
            'teeth_am': "✓ Teeth",
            'breakfast': "✓ Breakfast",
            'lunch': "✓ Lunch",
            'dinner': "✓ Dinner",
            'teeth_pm': "✓ Teeth",
            'water': f"Water: {human.water_glasses}",
            'unknown': "Updated."
        }
    
    # Map task to database field and update
    if task == 'meds':
        human.meds_taken = True
        human.meds_taken_time = datetime.now().time()
        message = messages['meds']
    elif task == 'shower':
        human.shower_taken = True
        human.last_shower_date = date.today()
        message = messages['shower']
    elif task == 'teeth_am':
        human.teeth_brushed_am = True
        message = messages['teeth_am']
    elif task == 'breakfast':
        human.breakfast = True
        message = messages['breakfast']
    elif task == 'lunch':
        human.lunch = True
        message = messages['lunch']
    elif task == 'dinner':
        human.dinner = True
        message = messages['dinner']
    elif task == 'teeth_pm':
        human.teeth_brushed_pm = True
        message = messages['teeth_pm']
    elif task == 'water':
        human.water_glasses += 1
        message = messages['water']
    else:
        message = messages['unknown']
    
    # Check if lockout is enabled before checking morning tasks
    lockout_enabled = DailyConfig.get('lockout_enabled', 'true') == 'true'
    
    if lockout_enabled:
        # Check if enough morning tasks are done to unlock
        morning_lockout_tasks = int(DailyConfig.get('morning_lockout_tasks', '2'))
        if human.morning_complete >= morning_lockout_tasks:
            flash("System unlocked! Now get to work!", "success")
        else:
            remaining = morning_lockout_tasks - human.morning_complete
            flash(f"{message} ({remaining} more morning tasks to unlock)", "info")
    else:
        # Lockout disabled, just show the message
        flash(message, "success")
    
    db.session.commit()
    
    # Log it (only if not OFF)
    if harassment_level != 'OFF':
        HarassmentLog.add(f"User completed: {task}", "positive")
    
    return redirect(url_for('daily.index'))


# ============ PROJECT TASKS ============

@daily_bp.route('/tasks/complete/<int:task_id>')
def complete_task(task_id):
    """Mark a daily task as complete"""
    task = DailyTask.query.get_or_404(task_id)
    task.complete()
    
    flash(f"Task completed! {DailyTask.query.filter_by(date=date.today(), completed=False).count()} remaining.", "success")
    
    return redirect(url_for('daily.index'))


@daily_bp.route('/tasks/select')
def select_tasks():
    """Select which projects to work on today"""
    # Get all projects except completed ones
    tch_projects = TCHProject.query.filter(TCHProject.status != 'completed').all()
    personal_projects = PersonalProject.query.filter(PersonalProject.status != 'completed').all()
    
    # Calculate neglect for each
    projects_data = []
    
    for project in tch_projects:
        last_task = DailyTask.query.filter_by(
            project_id=project.id,
            project_type='TCH'
        ).order_by(DailyTask.date.desc()).first()
        
        days_neglected = 999
        if last_task:
            days_neglected = (date.today() - last_task.date).days
        
        projects_data.append({
            'project': project,
            'type': 'TCH',
            'days_neglected': days_neglected,
            'deadline': project.deadline
        })
    
    for project in personal_projects:
        last_task = DailyTask.query.filter_by(
            project_id=project.id,
            project_type='Personal'
        ).order_by(DailyTask.date.desc()).first()
        
        days_neglected = 999
        if last_task:
            days_neglected = (date.today() - last_task.date).days
        
        projects_data.append({
            'project': project,
            'type': 'Personal',
            'days_neglected': days_neglected,
            'deadline': None
        })
    
    # Sort by neglect
    projects_data.sort(key=lambda x: x['days_neglected'], reverse=True)
    
    return render_template(
        'daily/select_tasks.html',
        projects_data=projects_data,
        today=date.today(),
        active='daily'
    )


@daily_bp.route('/tasks/add', methods=['POST'])
def add_task():
    """Add a task from a project to today"""
    project_id = request.form.get('project_id')
    project_type = request.form.get('project_type')
    task_description = request.form.get('task_description')
    
    # Get project name and status
    if project_type == 'TCH':
        project = TCHProject.query.get(project_id)
    else:
        project = PersonalProject.query.get(project_id)
    
    # Create daily task with status in the name
    task = DailyTask(
        date=date.today(),
        project_id=project_id,
        project_type=project_type,
        project_name=f"{project.name} [{project.status.upper()}]",
        task_description=task_description,
        priority=request.form.get('priority', 0)
    )
    
    db.session.add(task)
    db.session.commit()
    
    flash(f"Added task from {project.name}", "success")
    return redirect(url_for('daily.index'))


@daily_bp.route('/tasks/refresh')
def refresh_tasks():
    """Manually refresh today's project selection"""
    # Clear today's tasks
    DailyTask.query.filter_by(
        date=date.today(),
        completed=False
    ).delete()
    
    # Re-select tasks
    auto_select_tasks()
    
    flash("Projects refreshed! New selection loaded.", "success")
    return redirect(url_for('daily.index'))


@daily_bp.route('/tasks/force-rotate')
def force_rotate():
    """Force a complete rotation - marks all current projects as shown yesterday"""
    yesterday = date.today() - timedelta(days=1)
    
    # Mark all active projects as shown yesterday to trigger rotation
    tch_projects = TCHProject.query.filter(TCHProject.status != 'completed').all()
    for project in tch_projects:
        rotation = ProjectRotation(
            date=yesterday,
            project_id=project.id,
            project_type='TCH',
            priority_score=0
        )
        db.session.add(rotation)
    
    personal_projects = PersonalProject.query.filter(PersonalProject.status != 'completed').all()
    for project in personal_projects:
        rotation = ProjectRotation(
            date=yesterday,
            project_id=project.id,
            project_type='Personal',
            priority_score=0
        )
        db.session.add(rotation)
    
    db.session.commit()
    
    # Now refresh today's selection
    DailyTask.query.filter_by(date=date.today(), completed=False).delete()
    auto_select_tasks()
    
    flash("Forced rotation complete! All projects marked for fresh rotation.", "warning")
    return redirect(url_for('daily.index'))


@daily_bp.route('/tasks/stats')
def task_stats():
    """View project rotation statistics"""
    today = date.today()
    week_ago = today - timedelta(days=7)
    
    # Get rotation history for the past week
    recent_rotations = ProjectRotation.query.filter(
        ProjectRotation.date >= week_ago
    ).order_by(ProjectRotation.date.desc()).all()
    
    # Get all active projects
    all_active = []
    
    tch_projects = TCHProject.query.filter(TCHProject.status != 'completed').all()
    for p in tch_projects:
        last_rotation = ProjectRotation.query.filter_by(
            project_id=p.id,
            project_type='TCH'
        ).order_by(ProjectRotation.date.desc()).first()
        
        all_active.append({
            'name': p.name,
            'type': 'TCH',
            'status': p.status,
            'priority': p.priority,
            'deadline': p.deadline,
            'last_shown': last_rotation.date if last_rotation else None,
            'days_since': (today - last_rotation.date).days if last_rotation else 999
        })
    
    personal_projects = PersonalProject.query.filter(PersonalProject.status != 'completed').all()
    for p in personal_projects:
        last_rotation = ProjectRotation.query.filter_by(
            project_id=p.id,
            project_type='Personal'
        ).order_by(ProjectRotation.date.desc()).first()
        
        all_active.append({
            'name': p.name,
            'type': 'Personal',
            'status': p.status,
            'priority': p.priority,
            'deadline': getattr(p, 'deadline', None),
            'last_shown': last_rotation.date if last_rotation else None,
            'days_since': (today - last_rotation.date).days if last_rotation else 999
        })
    
    # Sort by days since shown (most neglected first)
    all_active.sort(key=lambda x: x['days_since'], reverse=True)
    
    return render_template(
        'daily/task_stats.html',
        projects=all_active,
        recent_rotations=recent_rotations,
        today=today,
        active='daily'
    )


# ============ NOTES ============

@daily_bp.route('/notes/add', methods=['POST'])
def add_note():
    """Quick capture a note"""
    note = CapturedNote(
        category=request.form.get('category', 'Random'),
        note=request.form.get('note')
    )
    
    db.session.add(note)
    db.session.commit()
    
    return redirect(url_for('daily.index'))


@daily_bp.route('/notes/resolve/<int:note_id>')
def resolve_note(note_id):
    """Mark a note as resolved"""
    note = CapturedNote.query.get_or_404(note_id)
    note.resolved = True
    db.session.commit()
    
    return redirect(url_for('daily.index'))


# ============ CALENDAR ============

@daily_bp.route('/calendar')
def calendar_view():
    """Show week and month calendar views"""
    view_type = request.args.get('view')
    if not view_type:
        view_type = DailyConfig.get('default_view', 'week')
    
    if view_type == 'week':
        # Get this week's events
        today = date.today()
        
        # Check if a specific week is requested
        week_offset = request.args.get('week_offset', 0, type=int)
        week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
        week_end = week_start + timedelta(days=6)
        
        events = CalendarEvent.query.filter(
            CalendarEvent.event_date >= week_start,
            CalendarEvent.event_date <= week_end
        ).order_by(CalendarEvent.event_date, CalendarEvent.event_time).all()
        
        # Group by day
        events_by_day = {}
        for day_num in range(7):
            day_date = week_start + timedelta(days=day_num)
            events_by_day[day_date] = []
        
        for event in events:
            if event.event_date in events_by_day:
                events_by_day[event.event_date].append(event)
        
        # Get project deadlines for the week
        tch_deadlines = TCHProject.query.filter(
            TCHProject.deadline >= week_start,
            TCHProject.deadline <= week_end,
            TCHProject.status != 'completed'
        ).all()
        
        personal_deadlines = PersonalProject.query.filter(
            PersonalProject.deadline >= week_start,
            PersonalProject.deadline <= week_end,
            PersonalProject.status != 'completed'
        ).all()
        
        return render_template(
            'daily/calendar_week.html',
            view_type='week',
            week_start=week_start,
            week_end=week_end,
            week_offset=week_offset,
            events_by_day=events_by_day,
            tch_deadlines=tch_deadlines,
            personal_deadlines=personal_deadlines,
            today=today,
            timedelta=timedelta,
            active='daily'
        )
    
    else:  # Month view
        today = date.today()
        
        # Parse month parameter if provided
        month_param = request.args.get('month')
        if month_param:
            try:
                year, month = month_param.split('-')
                month_start = date(int(year), int(month), 1)
            except:
                month_start = date(today.year, today.month, 1)
        else:
            month_start = date(today.year, today.month, 1)
        
        # Get next month for end date
        if month_start.month == 12:
            month_end = date(month_start.year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(month_start.year, month_start.month + 1, 1) - timedelta(days=1)
        
        # Get all events for the month
        events = CalendarEvent.query.filter(
            CalendarEvent.event_date >= month_start,
            CalendarEvent.event_date <= month_end
        ).order_by(CalendarEvent.event_date, CalendarEvent.event_time).all()
        
        # Get project deadlines for the month
        project_deadlines = []
        
        tch_deadlines = TCHProject.query.filter(
            TCHProject.deadline >= month_start,
            TCHProject.deadline <= month_end,
            TCHProject.status != 'completed'
        ).all()
        
        personal_deadlines = PersonalProject.query.filter(
            PersonalProject.deadline >= month_start,
            PersonalProject.deadline <= month_end,
            PersonalProject.status != 'completed'
        ).all()
        
        project_deadlines.extend(tch_deadlines)
        project_deadlines.extend(personal_deadlines)
        
        # Build calendar days list - THIS IS THE KEY PART THAT'S MISSING
        calendar_days = []
        
        # Find the first day of the calendar (Sunday of the week containing month_start)
        first_weekday = month_start.weekday()
        if first_weekday == 6:  # Sunday
            calendar_start = month_start
        else:
            # Python's weekday(): Monday is 0, Sunday is 6
            # We need to go back to the previous Sunday
            days_back = (first_weekday + 1) % 7
            if days_back == 0:
                days_back = 7
            calendar_start = month_start - timedelta(days=days_back)
        
        # Generate 6 weeks of days (42 days)
        current = calendar_start
        for i in range(42):
            day_events = [e for e in events if e.event_date == current]
            day_deadlines = [d for d in project_deadlines if d.deadline == current]
            
            calendar_days.append({
                'date': current,
                'day': current.day,
                'is_current_month': current.month == month_start.month,
                'is_today': current == today,
                'is_weekend': current.weekday() in [5, 6],
                'events': day_events,
                'deadlines': day_deadlines
            })
            current += timedelta(days=1)
        
        return render_template(
            'daily/calendar_month.html',
            view_type='month',
            month_start=month_start,
            month_end=month_end,
            events=events,
            project_deadlines=project_deadlines,
            calendar_days=calendar_days,  # THIS IS WHAT WAS MISSING
            today=today,
            datetime=datetime,
            timedelta=timedelta,
            active='daily'
        )


@daily_bp.route('/events/add', methods=['GET', 'POST'])
def add_event():
    """Add a new calendar event"""
    if request.method == 'POST':
        # Create the event
        event = CalendarEvent(
            event_date=datetime.strptime(request.form.get('event_date'), '%Y-%m-%d').date(),
            event_time=request.form.get('event_time'),
            event_type=request.form.get('event_type'),
            who=request.form.get('who'),
            description=request.form.get('description')
        )
        
        # Add/update event type for quick selection
        EventType.get_or_create(event.event_type)
        
        # Check if this should be recurring
        if request.form.get('recurring_days'):
            # Create recurring pattern
            recurring = RecurringEvent(
                event_type=event.event_type,
                days_of_week=request.form.get('recurring_days'),
                time=event.event_time,
                who=event.who,
                description=event.description,
                until_date=datetime.strptime(request.form.get('until_date'), '%Y-%m-%d').date() if request.form.get('until_date') else None
            )
            db.session.add(recurring)
            db.session.commit()
            
            # Generate instances for next 30 days
            generate_recurring_instances(recurring)
        else:
            db.session.add(event)
            db.session.commit()
        
        flash(f"Event added: {event.event_type} on {event.event_date.strftime('%B %d')}", "success")
        return redirect(url_for('daily.calendar_view'))
    
    # GET request - show form
    default_date = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    
    # Get event types for dropdown
    event_types = EventType.query.order_by(EventType.usage_count.desc()).all()
    
    return render_template(
        'daily/add_event.html',
        default_date=default_date,
        event_types=event_types,
        active='daily'
    )


def generate_recurring_instances(recurring):
    """Generate event instances from recurring pattern"""
    # Parse days of week
    days = recurring.days_of_week.split(',')
    day_map = {'Mon': 0, 'Tue': 1, 'Wed': 2, 'Thu': 3, 'Fri': 4, 'Sat': 5, 'Sun': 6}
    
    # Generate for next 30 days or until end date
    start = date.today()
    end = recurring.until_date if recurring.until_date else start + timedelta(days=30)
    
    current = start
    while current <= end:
        if any(current.weekday() == day_map.get(d.strip()) for d in days):
            # Check if event already exists
            existing = CalendarEvent.query.filter_by(
                event_date=current,
                event_type=recurring.event_type,
                event_time=recurring.time
            ).first()
            
            if not existing:
                event = CalendarEvent(
                    event_date=current,
                    event_time=recurring.time,
                    event_type=recurring.event_type,
                    who=recurring.who,
                    description=recurring.description,
                    recurring_id=recurring.id
                )
                db.session.add(event)
        
        current += timedelta(days=1)
    
    db.session.commit()


# ============ EVENING REVIEW ============

@daily_bp.route('/evening-review')
def evening_review():
    """Evening review and grading"""
    today = date.today()
    human = HumanMaintenance.get_today()
    
    # Calculate grade
    score = 0
    max_score = 0
    
    # Morning essentials (30 points)
    if human.meds_taken: score += 10
    max_score += 10
    
    if human.shower_taken or human.days_since_shower < 2: score += 10
    max_score += 10
    
    if human.teeth_brushed_am: score += 5
    max_score += 5
    
    if human.teeth_brushed_pm: score += 5
    max_score += 5
    
    # Meals (30 points)
    if human.breakfast: score += 10
    max_score += 10
    
    if human.lunch: score += 10
    max_score += 10
    
    if human.dinner: score += 10
    max_score += 10
    
    # Hydration (10 points)
    water_score = min(human.water_glasses * 2, 10)
    score += water_score
    max_score += 10
    
    # Project tasks (30 points)
    daily_tasks = DailyTask.query.filter_by(date=today).all()
    if daily_tasks:
        completed = sum(1 for t in daily_tasks if t.completed)
        task_score = int((completed / len(daily_tasks)) * 30)
        score += task_score
        max_score += 30
    
    # Calculate percentage and grade
    percentage = int((score / max_score * 100)) if max_score > 0 else 0
    
    if percentage >= 90:
        grade = 'A'
        grade_message = "Outstanding! You actually functioned like a human today."
    elif percentage >= 80:
        grade = 'B'
        grade_message = "Good job. You did most of what you needed to."
    elif percentage >= 70:
        grade = 'C'
        grade_message = "Mediocre. You can do better than this."
    elif percentage >= 60:
        grade = 'D'
        grade_message = "Pathetic. You barely scraped by."
    else:
        grade = 'F'
        grade_message = "FAILURE. You wasted this entire day."
    
    # Count streaks
    review_streak = 1  # TODO: Implement streak tracking
    
    # Generate improvement suggestions
    task_suggestions = []
    if not human.meds_taken:
        task_suggestions.append("Take meds FIRST THING tomorrow morning")
    if human.days_since_shower >= 2:
        task_suggestions.append("SHOWER. No excuses.")
    if human.water_glasses < 6:
        task_suggestions.append("Drink more water - aim for 8 glasses")
    if daily_tasks:
        incomplete = [t for t in daily_tasks if not t.completed]
        if incomplete:
            task_suggestions.append(f"Finish {len(incomplete)} incomplete tasks tomorrow")
    
    # Meals eaten count
    meals_eaten = sum([human.breakfast, human.lunch, human.dinner])
    
    # Get task stats
    tasks_total = len(daily_tasks) if daily_tasks else 0
    tasks_completed = sum(1 for t in daily_tasks if t.completed) if daily_tasks else 0
    
    # Final message based on grade
    if grade in ['A', 'B']:
        final_message_title = "ACCEPTABLE PERFORMANCE"
        final_message_body = "You did what was expected. Keep it up tomorrow."
    elif grade in ['C', 'D']:
        final_message_title = "ROOM FOR IMPROVEMENT"
        final_message_body = "You half-assed today. Tomorrow, do better or suffer the consequences."
    else:
        final_message_title = "ABSOLUTELY PATHETIC"
        final_message_body = f"You failed. {human.days_since_shower} days without shower. Skipped meds. Barely ate. Tomorrow you WILL do better or be locked out completely."
    
    return render_template(
        'daily/evening_review.html',
        today=today,
        human=human,
        grade=grade,
        grade_message=grade_message,
        meals_eaten=meals_eaten,
        daily_tasks=daily_tasks,
        tasks_total=tasks_total,
        tasks_completed=tasks_completed,
        task_suggestions=task_suggestions,
        review_streak=review_streak,
        final_message_title=final_message_title,
        final_message_body=final_message_body,
        active='daily'
    )
@daily_bp.route('/tasks/clear', methods=['POST', 'GET'])
def clear_tasks():
    """Clear all tasks for today"""
    # Delete all of today's incomplete tasks
    DailyTask.query.filter_by(
        date=date.today(),
        completed=False
    ).delete()
    
    db.session.commit()
    
    flash("Today's tasks cleared! Use refresh to auto-select new ones.", "warning")
    return redirect(url_for('daily.settings'))    




# ============ SETTINGS ============

@daily_bp.route('/settings')
def settings():
    """Settings page for customizing the drill sergeant"""
    
    # Get all current settings
    settings = {
        'projects_to_show': DailyConfig.get('projects_to_show', '5'),
        'harassment_level': DailyConfig.get('harassment_level', 'BRUTAL'),
        'lockout_enabled': DailyConfig.get('lockout_enabled', 'true'),
        'shower_threshold_days': DailyConfig.get('shower_threshold_days', '2'),
        'morning_lockout_tasks': DailyConfig.get('morning_lockout_tasks', '2'),
        'default_view': DailyConfig.get('default_view', 'week'),
        'evening_review_hour': DailyConfig.get('evening_review_hour', '20'),
        'evening_review_end_hour': DailyConfig.get('evening_review_end_hour', '3'),  # IMPORTANT!
        'quiet_start': DailyConfig.get('quiet_start', '22'),
        'quiet_end': DailyConfig.get('quiet_end', '6'),
    }
    
    # Get custom messages (stored as pipe-separated string)
    custom_messages_str = DailyConfig.get('custom_messages', '')
    custom_messages = custom_messages_str.split('|||') if custom_messages_str else []
    
    return render_template(
        'daily/settings.html',
        settings=settings,
        custom_messages=custom_messages,
        active='daily'
    )


@daily_bp.route('/settings/save', methods=['POST'])
def save_settings():
    """Save all settings"""
    
    # Save each setting - INCLUDING evening_review_end_hour!
    settings_to_save = [
        'projects_to_show',
        'harassment_level',
        'lockout_enabled',
        'shower_threshold_days',
        'morning_lockout_tasks',
        'default_view',
        'evening_review_hour',
        'evening_review_end_hour',  # THIS WAS MISSING!
        'quiet_start',
        'quiet_end'
    ]
    
    for setting in settings_to_save:
        if setting in request.form:
            DailyConfig.set(setting, request.form.get(setting))
    
    # Save custom messages if provided
    if 'custom_messages' in request.form:
        messages = request.form.getlist('custom_messages')
        DailyConfig.set('custom_messages', '|||'.join(messages))
    
    flash("Settings saved! The drill sergeant has been updated.", "success")
    return redirect(url_for('daily.settings'))

@daily_bp.route('/settings/reset', methods=['POST', 'GET'])
def reset_settings():
    """Reset all settings to defaults"""
    
    # Default settings
    defaults = {
        'projects_to_show': '5',
        'harassment_level': 'BRUTAL',
        'lockout_enabled': 'true',
        'shower_threshold_days': '2',
        'morning_lockout_tasks': '2',
        'default_view': 'week',
        'evening_review_hour': '20',
        'evening_review_end_hour': '3',
        'quiet_start': '22',
        'quiet_end': '6',
    }
    
    # Reset each setting to default
    for key, value in defaults.items():
        DailyConfig.set(key, value)
    
    # Clear custom messages
    DailyConfig.set('custom_messages', '')
    
    flash("Settings reset to defaults!", "warning")
    return redirect(url_for('daily.settings'))

# ============ API ENDPOINTS ============

@daily_bp.route('/api/events/<date_str>')
def api_get_events(date_str):
    """API endpoint to get events for a specific date"""
    event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    events = CalendarEvent.query.filter_by(event_date=event_date).all()
    
    # Also get project deadlines
    deadlines = []
    
    tch_deadlines = TCHProject.query.filter(
        TCHProject.deadline == event_date,
        TCHProject.status != 'completed'
    ).all()
    
    for project in tch_deadlines:
        deadlines.append({
            'type': 'deadline',
            'name': f"TCH: {project.name}",
            'priority': project.priority
        })
    
    personal_deadlines = PersonalProject.query.filter(
        PersonalProject.deadline == event_date,
        PersonalProject.status != 'completed'
    ).all()
    
    for project in personal_deadlines:
        deadlines.append({
            'type': 'deadline', 
            'name': f"Personal: {project.name}",
            'priority': project.priority
        })
    
    # Format response
    response = {
        'events': [
            {
                'id': e.id,
                'time': e.event_time or 'All Day',
                'type': e.event_type,
                'who': e.who,
                'description': e.description
            } for e in events
        ],
        'deadlines': deadlines
    }
    
    return jsonify(response)


@daily_bp.route('/api/harassment')
def api_harassment():
    """Get current harassment message"""
    human = HumanMaintenance.get_today()
    message = get_current_harassment(human)
    
    return jsonify({
        'message': message,
        'severity': 'warning' if message else 'none'
    })