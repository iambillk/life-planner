from flask import render_template, request, redirect, url_for, flash
from datetime import datetime
from . import projects_bp
from models import db, TCHProject, PersonalProject

@projects_bp.route('/tch')
def tch_index():
    """TCH Projects list"""
    projects = TCHProject.query.all()
    return render_template('tch_projects.html', projects=projects, active='tch')

@projects_bp.route('/tch/add', methods=['POST'])
def add_tch():
    """Add TCH project"""
    project = TCHProject(
        name=request.form.get('name'),
        description=request.form.get('description'),
        deadline=datetime.strptime(request.form.get('deadline'), '%Y-%m-%d').date() if request.form.get('deadline') else None
    )
    db.session.add(project)
    db.session.commit()
    flash(f'TCH Project "{project.name}" added!', 'success')
    return redirect(url_for('projects.tch_index'))

@projects_bp.route('/tch/<int:id>/update-progress', methods=['POST'])
def update_tch_progress(id):
    """Update TCH project progress"""
    project = TCHProject.query.get_or_404(id)
    project.progress = int(request.form.get('progress', 0))
    db.session.commit()
    return redirect(url_for('projects.tch_index'))

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