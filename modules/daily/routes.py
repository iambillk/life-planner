from flask import render_template, request, redirect, url_for
from datetime import datetime
from . import daily_bp
from models import db, DailyTask

@daily_bp.route('/')
def index():
    """Daily planner main page"""
    tasks = DailyTask.query.filter_by(date=datetime.utcnow().date()).all()
    return render_template('daily.html', tasks=tasks, active='daily')

@daily_bp.route('/add', methods=['POST'])
def add_task():
    """Add daily task"""
    task = DailyTask(
        task=request.form.get('task'),
        priority=request.form.get('priority', 'medium')
    )
    db.session.add(task)
    db.session.commit()
    return redirect(url_for('daily.index'))

@daily_bp.route('/toggle/<int:id>')
def toggle_task(id):
    """Toggle task completion"""
    task = DailyTask.query.get_or_404(id)
    task.completed = not task.completed
    db.session.commit()
    return redirect(url_for('daily.index'))