# app.py - Updated with Real Estate Management
"""
Life Management System - Application Factory
Version: 1.3.1
Updated: 2025-09-05

CHANGELOG:
v1.3.1 (2025-09-05)
- Register real estate blueprint without an extra url_prefix
  (the blueprint provides url_prefix="/property" itself)

v1.3.0 (2025-01-03)
- Added Real Estate Management blueprint
- Added property photo upload directories

v1.2.0 (Previous)
- Original application with all existing modules
"""

from flask import Flask, redirect, url_for
from config import Config
from models.base import db
from datetime import datetime
import os

def create_app():
    """Application factory pattern"""
    app = Flask(__name__)
    app.config.from_object(Config)
    app.jinja_env.globals.update(abs=abs)
    
    # Initialize database
    db.init_app(app)
    
    # Create upload directories
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'equipment_profiles'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'maintenance_photos'), exist_ok=True)
    
    # ========== Real Estate upload directories ==========
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'property_profiles'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'property_maintenance'), exist_ok=True)

    # In app.py, in the create_app() function where other directories are created, add:
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'personal_project_files'), exist_ok=True)

    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'receipts'), exist_ok=True) 
    
    # Context processors
    @app.context_processor
    def inject_datetime():
        return {'datetime': datetime}
    
    # Register blueprints
    register_blueprints(app)
    
    # Root route
    @app.route('/')
    def index():
        return redirect(url_for('daily.index'))
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    return app

def register_blueprints(app):
    """Register all module blueprints"""
    from modules.daily import daily_bp
    from modules.equipment import equipment_bp
    from modules.projects import projects_bp
    from modules.persprojects import persprojects_bp
    from modules.health import health_bp
    from modules.weekly import weekly_bp
    from modules.goals import goals_bp
    from modules.todo import todo_bp
    from modules.realestate import realestate_bp
    from modules.financial import financial_bp
        
    app.register_blueprint(daily_bp, url_prefix='/daily')
    app.register_blueprint(equipment_bp, url_prefix='/equipment')
    app.register_blueprint(projects_bp, url_prefix='/projects')
    app.register_blueprint(persprojects_bp, url_prefix='/personal')
    app.register_blueprint(health_bp, url_prefix='/health')
    app.register_blueprint(weekly_bp, url_prefix='/weekly')
    app.register_blueprint(goals_bp, url_prefix='/goals')
    app.register_blueprint(todo_bp, url_prefix='/todo')
    app.register_blueprint(financial_bp, url_prefix='/financial')
    
    # Important: do NOT pass url_prefix again here
    app.register_blueprint(realestate_bp)

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
