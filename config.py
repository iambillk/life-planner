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

    # DLI Web Power Switch Integration
    # Version: 1.0.0
    # Added: 2025-04-10
    # Description: Configuration for DLI PDU REST API integration
    # Replaces planned APC unit with more flexible REST-based solution
    
    # Primary DLI PDU Configuration
    DLI_PDU_HOST = "192.168.1.238"          # Replace with your DLI PDU IP
    DLI_PDU_USER = "admin"                  # DLI admin username
    DLI_PDU_PASS = "stUP66ey"                   # DLI admin password
    DLI_PDU_NAME = "DLI-PDU-1"              # Friendly name for dashboard
    
    # DLI PDU Settings
    DLI_PDU_TIMEOUT = 10                    # API timeout in seconds
    DLI_PDU_CACHE_TTL = 5                   # Cache TTL in seconds (short for real-time)
    DLI_PDU_MAX_AMPS = 15                   # Maximum amperage for your PDU model
    DLI_PDU_VERIFY_SSL = False              # Set to True if using HTTPS with valid cert
    
    # DLI PDU Features
    DLI_PDU_ENABLE_AUTOPING = True          # Enable AutoPing monitoring features
    DLI_PDU_ENABLE_SCRIPTING = True         # Enable Lua scripting features
    DLI_PDU_ENABLE_SCHEDULING = True        # Enable scheduled operations
    
    # Outlet Configuration (customize based on your setup)
    DLI_PDU_OUTLET_COUNT = 8                # Number of outlets on your PDU
    DLI_PDU_OUTLET_NAMES = {                # Custom outlet names (optional)
        0: "OPNsense Firewall",
        1: "MikroTik Switch",
        2: "Spectrum Modem",
        3: "Frontier Router",
        4: "UniFi AP",
        5: "NAS Server",
        6: "Lab Equipment",
        7: "Spare/Testing"
    }
    
    # Firewalla MSP Integration
    # Version: 1.0.0
    # Added: 2025-01-XX
    # Description: Configuration for Firewalla MSP API v2 integration
    # Provides security monitoring and threat intelligence for ops dashboard
    
    # Primary Firewalla MSP Configuration
    FIREWALLA_MSP_DOMAIN = "totalchoice.firewalla.net"  # Your MSP subdomain
    FIREWALLA_API_TOKEN = "fe7f069d59606cd62b0653a8a417303e"  # Your API token
    
    # Firewalla Settings
    FIREWALLA_TIMEOUT = 10                    # API timeout in seconds
    FIREWALLA_CACHE_TTL = 60                  # Cache TTL in seconds (60 per MVP spec)
    FIREWALLA_VERIFY_SSL = True               # Set to False if using self-signed cert
    
    # Firewalla Feature Flags
    FIREWALLA_ENABLE_FLOWS = True             # Enable network flow analysis
    FIREWALLA_ENABLE_RULES = True             # Enable rule management display
    FIREWALLA_ENABLE_DEVICES = True           # Enable device tracking
    FIREWALLA_ENABLE_ALARMS = True            # Enable security alarm monitoring
    
    # Firewalla Alert Thresholds (for dashboard display)
    FIREWALLA_ALERT_CRITICAL = 10             # Red alert if more than 10 threats/hour
    FIREWALLA_ALERT_WARNING = 5               # Yellow alert if more than 5 threats/hour
    FIREWALLA_ALERT_OK = 2                    # Green if less than 2 threats/hour
    
    # Target List Configuration (if using target lists)
    FIREWALLA_TARGET_LIST_ID = "TL-8a3af152-551a-4355-b61b-f1e494723b2a"  # Example target list ID

    
    # SSH Log Scanner Configuration
    SSH_LOG_PATH = os.environ.get('SSH_LOG_PATH', r'\\192.168.1.196\wtr_shared_folder\Data\SSH log files')
    SSH_LOG_AUTO_SCAN = os.environ.get('SSH_LOG_AUTO_SCAN', 'False').lower() == 'true'
    SSH_LOG_SCAN_INTERVAL = int(os.environ.get('SSH_LOG_SCAN_INTERVAL', 3600))  # seconds