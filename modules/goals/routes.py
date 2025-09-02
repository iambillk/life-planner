from flask import render_template, request, redirect, url_for, flash
from datetime import datetime
from . import goals_bp
from models import db, Goal

@goals_bp.route('/')
def index():
    """Goals list"""
    goals = Goal.query.all()
    categories = ['career', 'health', 'financial', 'personal', 'education']
    return render_template('goals.html', goals=goals, categories=categories, active='goals')

@goals_bp.route('/add', methods=['POST'])
def add():
    """Add new goal"""
    goal = Goal(
        title=request.form.get('title'),
        description=request.form.get('description'),
        category=request.form.get('category'),
        target_date=datetime.strptime(request.form.get('target_date'), '%Y-%m-%d').date() if request.form.get('target_date') else None
    )
    db.session.add(goal)
    db.session.commit()
    flash(f'Goal "{goal.title}" added!', 'success')
    return redirect(url_for('goals.index'))

@goals_bp.route('/<int:id>/update-progress', methods=['POST'])
def update_progress(id):
    """Update goal progress"""
    goal = Goal.query.get_or_404(id)
    goal.progress = int(request.form.get('progress', 0))
    db.session.commit()
    flash(f'Progress updated for "{goal.title}"!', 'success')
    return redirect(url_for('goals.index'))

@goals_bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    """Delete goal"""
    goal = Goal.query.get_or_404(id)
    title = goal.title
    db.session.delete(goal)
    db.session.commit()
    flash(f'Goal "{title}" deleted!', 'success')
    return redirect(url_for('goals.index'))