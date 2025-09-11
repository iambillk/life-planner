import os
from datetime import timedelta

class Config:
    # Basic Flask config
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database
    SQLALCHEMY_DATABASE_URI = 'sqlite:///planner.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # File uploads
    UPLOAD_FOLDER = 'static/equipment_photos'
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB max (increased from 16MB)
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'webp'}  # added webp
    
    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # App settings
    APP_NAME = 'Billas Planner 1.0 Beta'
    ITEMS_PER_PAGE = 20
