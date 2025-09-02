from flask import render_template
from datetime import datetime, timedelta
from . import weekly_bp
from models import DailyTask

@weekly_bp.route('/')
def index():
    """Weekly view"""
    today = datetime.utcnow().date()
    start_week = today - timedelta(days=today.weekday())
    end_week = start_week + timedelta(days=6)
    
    tasks = DailyTask.query.filter(
        DailyTask.date.between(start_week, end_week)
    ).all()
    
    # Organize tasks by day
    week_tasks = {}
    for i in range(7):
        day = start_week + timedelta(days=i)
        week_tasks[day] = [t for t in tasks if t.date == day]
    
    return render_template('weekly.html', 
                         week_tasks=week_tasks,
                         start_week=start_week,
                         active='weekly')

@weekly_bp.route('/monthly')
def monthly():
    """Monthly view"""
    today = datetime.utcnow().date()
    start_month = today.replace(day=1)
    
    # Get next month
    if today.month == 12:
        end_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        end_month = today.replace(month=today.month + 1, day=1)
    
    tasks = DailyTask.query.filter(
        DailyTask.date >= start_month,
        DailyTask.date < end_month
    ).all()
    
    return render_template('monthly.html',
                         tasks=tasks,
                         current_month=today.strftime('%B %Y'),
                         active='weekly')