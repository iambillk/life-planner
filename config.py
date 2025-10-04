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
    
    # Session - ADD THESE LINES
    SESSION_TYPE = 'filesystem'
    SESSION_FILE_DIR = 'flask_session'  # Will create a folder in your project directory
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    SESSION_KEY_PREFIX = 'myapp:'
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

    # LibreNMS Integration (local lab)
    LIBRENMS_BASE_URL = "http://192.168.1.250"
    LIBRENMS_API_TOKEN = "9c323b0b9ce872f007041870b5c2d248"
    LIBRENMS_CACHE_TTL = 60
    LIBRENMS_TIMEOUT = 15

    # MikroTik CRS354 Switch Integration
    MIKROTIK_HOST = "192.168.1.252"   # Replace XX with your switch IP
    MIKROTIK_USER = "tchnoc"          # Your RouterOS username
    MIKROTIK_PASS = "stUP66ey"        # Your RouterOS password
