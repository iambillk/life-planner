# modules/daily/routes.py
"""
Daily Planner Routes - The Drill Sergeant System
Complete working version with all fixes
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
    
    # Check if user is locked out (hasn't done morning minimums)
    lockout = False
    lockout_message = None
    if human.morning_complete < 2:  # Need 2 of 3 tasks
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
        datetime=datetime,
        active='daily'
    )


# ============ HUMAN MAINTENANCE ============

@daily_bp.route('/human/update', methods=['POST'])
def update_human():
    """Update human maintenance status"""
    human = HumanMaintenance.get_today()
    
    task = request.form.get('task')
    
    if task == 'meds':
        human.meds_taken = True
        human.meds_taken_time = datetime.now().time()
        flash("Finally! Your brain might actually work today.", "success")
    
    elif task == 'shower':
        human.shower_taken = True
        human.last_shower_date = date.today()
        flash("About damn time! You were getting ripe.", "success")
    
    elif task == 'teeth':
        human.teeth_brushed_am = True
        flash("Good. Your breath was becoming a weapon.", "success")
    
    elif task == 'breakfast':
        human.breakfast = True
        flash("Real food! Not just coffee! Progress!", "success")
    
    elif task == 'lunch':
        human.lunch = True
        flash("Look at you, eating like a human!", "success")
    
    elif task == 'dinner':
        human.dinner = True
        flash("Dinner logged. Now don't work until 2 AM.", "warning")
    
    elif task == 'water':
        human.water_glasses += 1
        flash(f"Water glass {human.water_glasses}/8. Keep going!", "info")
    
    db.session.commit()
    
    # Log it
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
    view_type = request.args.get('view', 'week')
    
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
        for i in range(7):
            day = week_start + timedelta(days=i)
            events_by_day[day] = []
        
        for event in events:
            events_by_day[event.event_date].append(event)
        
        return render_template(
            'daily/calendar_week.html',
            events_by_day=events_by_day,
            week_start=week_start,
            week_offset=week_offset,
            today=date.today(),
            timedelta=timedelta,
            active='daily'
        )
    
    else:  # month view
        # Get this month's events
        today = date.today()
        month_start = date(today.year, today.month, 1)
        
        # Parse month parameter if provided
        month_param = request.args.get('month')
        if month_param:
            try:
                year, month = month_param.split('-')
                month_start = date(int(year), int(month), 1)
            except:
                pass  # Use current month if invalid
        
        # Calculate month end
        if month_start.month == 12:
            month_end = date(month_start.year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(month_start.year, month_start.month + 1, 1) - timedelta(days=1)
        
        events = CalendarEvent.query.filter(
            CalendarEvent.event_date >= month_start,
            CalendarEvent.event_date <= month_end
        ).order_by(CalendarEvent.event_date).all()
        
        # Get project deadlines for this month
        project_deadlines = []
        tch_deadlines = TCHProject.query.filter(
            TCHProject.deadline >= month_start,
            TCHProject.deadline <= month_end,
            TCHProject.status != 'completed'
        ).all()
        project_deadlines.extend(tch_deadlines)
        
        return render_template(
            'daily/calendar_month.html',
            events=events,
            project_deadlines=project_deadlines,
            month_start=month_start,
            month_end=month_end,
            today=date.today(),
            timedelta=timedelta,
            active='daily'
        )


@daily_bp.route('/calendar/add', methods=['GET', 'POST'])
def add_event():
    """Add a calendar event"""
    if request.method == 'POST':
        # Get or create event type
        event_type = request.form.get('event_type')
        if event_type:
            EventType.get_or_create(event_type)
        
        # Create event
        event = CalendarEvent(
            event_date=datetime.strptime(request.form.get('event_date'), '%Y-%m-%d').date(),
            event_time=request.form.get('event_time'),
            event_type=event_type,
            who=request.form.get('who'),
            description=request.form.get('description')
        )
        
        db.session.add(event)
        db.session.commit()
        
        flash("Event added to calendar", "success")
        return redirect(url_for('daily.calendar_view'))
    
    # Get event types for dropdown
    event_types = EventType.query.order_by(EventType.usage_count.desc()).all()
    
    return render_template(
        'daily/add_event.html',
        event_types=event_types,
        active='daily'
    )


# ============ EVENING REVIEW ============

@daily_bp.route('/review')
def evening_review():
    """Evening review - forces TimeTree check and tomorrow planning"""
    
    today = date.today()
    human = HumanMaintenance.get_today()
    
    # Calculate metrics
    meals_eaten = sum([human.breakfast, human.lunch, human.dinner])
    
    # Get today's tasks
    daily_tasks = DailyTask.query.filter_by(date=today).all()
    tasks_total = len(daily_tasks)
    tasks_completed = len([t for t in daily_tasks if t.completed])
    
    # Calculate grade
    score = 0
    if human.meds_taken: score += 25
    if human.shower_taken or human.days_since_shower < 2: score += 25
    if meals_eaten >= 2: score += 20
    if human.water_glasses >= 6: score += 15
    if tasks_total > 0 and tasks_completed / tasks_total >= 0.5: score += 15
    
    if score >= 90:
        grade = 'A'
        grade_message = "Excellent! You acted like a human today!"
    elif score >= 80:
        grade = 'B'
        grade_message = "Good job. Room for improvement."
    elif score >= 70:
        grade = 'C'
        grade_message = "Mediocre. You can do better."
    elif score >= 60:
        grade = 'D'
        grade_message = "Poor performance. Get it together."
    else:
        grade = 'F'
        grade_message = "PATHETIC. You failed at basic human maintenance."
    
    # Get task suggestions for tomorrow
    task_suggestions = []
    
    # Get most neglected projects
    tch_projects = TCHProject.query.filter(TCHProject.status != 'completed').all()
    for project in tch_projects[:3]:  # Top 3 TCH
        # Check when last touched
        last_task = DailyTask.query.filter_by(
            project_id=project.id,
            project_type='TCH'
        ).order_by(DailyTask.date.desc()).first()
        
        if not last_task:
            reason = "Never worked on!"
        else:
            days_ago = (today - last_task.date).days
            reason = f"Not touched for {days_ago} days"
        
        task_suggestions.append({
            'project': project,
            'type': 'TCH',
            'reason': reason
        })
    
    # Get review streak (simplified for now)
    review_streak = 1  # TODO: Track this properly
    
    # Generate final message based on performance
    if grade in ['A', 'B']:
        final_message_title = "GOOD WORK SOLDIER"
        final_message_body = "You met most of your obligations today. Keep it up tomorrow."
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
    
    # Save each setting
    settings_to_save = [
        'projects_to_show',
        'harassment_level',
        'lockout_enabled',
        'shower_threshold_days',
        'morning_lockout_tasks',
        'default_view',
        'evening_review_hour',
        'quiet_start',
        'quiet_end'
    ]
    
    for setting in settings_to_save:
        value = request.form.get(setting)
        if value:
            DailyConfig.set(setting, value)
    
    # Save custom messages
    custom_messages = request.form.get('custom_messages', '')
    DailyConfig.set('custom_messages', custom_messages)
    
    flash("Settings saved! The drill sergeant has been reconfigured.", "success")
    return redirect(url_for('daily.settings'))


@daily_bp.route('/settings/reset')
def reset_settings():
    """Reset all settings to defaults"""
    
    defaults = {
        'projects_to_show': '5',
        'harassment_level': 'BRUTAL',
        'lockout_enabled': 'true',
        'shower_threshold_days': '2',
        'morning_lockout_tasks': '2',
        'default_view': 'week',
        'evening_review_hour': '20',
        'quiet_start': '22',
        'quiet_end': '6',
        'custom_messages': ''
    }
    
    for key, value in defaults.items():
        DailyConfig.set(key, value)
    
    flash("Settings reset to brutal defaults!", "warning")
    return redirect(url_for('daily.settings'))


@daily_bp.route('/tasks/clear')
def clear_tasks():
    """Clear all daily tasks for today"""
    DailyTask.query.filter_by(date=date.today()).delete()
    db.session.commit()
    
    flash("All daily tasks cleared. Select new ones!", "warning")
    return redirect(url_for('daily.index'))


# ============ HELPER FUNCTIONS ============

def get_lockout_message(human):
    """Generate appropriately harsh lockout message"""
    messages = []
    
    if not human.meds_taken:
        messages.append("MEDS NOT TAKEN - Your brain is running on fumes!")
    
    if human.days_since_shower >= 2:
        days = human.days_since_shower
        messages.append(f"NO SHOWER FOR {days} DAYS - You smell like a dumpster!")
    
    if not human.teeth_brushed_am:
        messages.append("TEETH NOT BRUSHED - Your breath is toxic!")
    
    completed = human.morning_complete
    messages.append(f"\nYou've only done {completed}/3 morning tasks.")
    messages.append("Complete at least 2 to unlock your projects.")
    messages.append("\nYour projects are locked until you act like a human.")
    
    return "\n".join(messages)


def get_current_harassment(human):
    """Get time-appropriate harassment message"""
    now = datetime.now()
    hour = now.hour
    
    if hour < 9 and not human.meds_taken:
        return "TAKE YOUR MEDS NOW! It's been hours!"
    
    elif hour >= 12 and hour < 13 and not human.lunch:
        return "EAT LUNCH! Coffee is not food!"
    
    elif hour >= 14 and human.water_glasses < 4:
        return f"Only {human.water_glasses} glasses of water? You're dehydrating!"
    
    elif hour >= 18 and not human.dinner:
        return "Eat dinner! Real food! Sit down and eat!"
    
    elif hour >= 21 and human.days_since_shower >= 2:
        return f"SHOWER TONIGHT! {human.days_since_shower} days is disgusting!"
    
    elif hour >= 22:
        return "Wrap it up! Bed by midnight or you'll be useless tomorrow."
    
    return None


def auto_select_tasks():
    """Auto-select tasks for today based on neglect and deadlines"""
    today_tasks = []
    
    # Get settings
    num_to_show = int(DailyConfig.get('projects_to_show', 5))
    
    # Get TCH projects with deadlines soon (excluding completed)
    tch_urgent = TCHProject.query.filter(
        TCHProject.status != 'completed',
        TCHProject.deadline != None,
        TCHProject.deadline <= date.today() + timedelta(days=7)
    ).all()
    
    # Add urgent tasks
    for project in tch_urgent[:3]:  # Max 3 urgent
        task = DailyTask(
            date=date.today(),
            project_id=project.id,
            project_type='TCH',
            project_name=f"{project.name} [{project.status.upper()}]",
            task_description=f"Work on {project.name} - DEADLINE APPROACHING",
            priority=1
        )
        db.session.add(task)
        today_tasks.append(task)
    
    # Fill remaining slots with neglected projects
    remaining_slots = num_to_show - len(today_tasks)
    
    if remaining_slots > 0:
        # Query for neglected projects (simplified for now) - excluding completed
        other_projects = PersonalProject.query.filter(
            PersonalProject.status != 'completed'
        ).limit(remaining_slots).all()
        
        for project in other_projects:
            task = DailyTask(
                date=date.today(),
                project_id=project.id,
                project_type='Personal',
                project_name=f"{project.name} [{project.status.upper()}]",
                task_description=f"Make progress on {project.name}",
                priority=2
            )
            db.session.add(task)
            today_tasks.append(task)
    
    db.session.commit()
    return today_tasks