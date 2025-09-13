import os
from datetime import timedelta

class Config:
    # Basic Flask config
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///planner.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # File uploads
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'static/equipment_photos')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 50 * 1024 * 1024))  # 50MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'webp'}

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # Use the shared-link integration (skip album-page scraping)
    IMMICH_ALBUM_URL = None

    # Your Immich shared link details:
    IMMICH_BASE_URL  = "https://media.wtr.network"
    IMMICH_SHARE_KEY = "yzC-TwNGQA3tq_-8cMvTgjS95n3ZDLNQhtMuwZuJglMZorkJXz-l7OMWN5vLZs5D6GM"

    # TLS verification: set to False only if your Immich cert is self-signed
    IMMICH_VERIFY_TLS = True

    # App settings
    APP_NAME = os.environ.get('APP_NAME', 'Billas Planner 1.0 Beta')
    ITEMS_PER_PAGE = int(os.environ.get('ITEMS_PER_PAGE', 20))
