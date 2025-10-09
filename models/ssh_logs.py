# models/ssh_logs.py
"""
SSH Session Log Models
Database models for tracking and analyzing SSH session logs from MobaXterm

Version: 1.0.0
Created: 2025-10-08
Author: Billas + AI
"""

from models.base import db
from datetime import datetime
from sqlalchemy import Index


class SSHSession(db.Model):
    """SSH session metadata extracted from MobaXterm logs"""
    __tablename__ = 'ssh_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # File Information
    filename = db.Column(db.String(500), unique=True, nullable=False)  # Original log filename
    file_path = db.Column(db.String(1000), nullable=False)  # Full path on NAS
    file_size = db.Column(db.Integer)  # Size in bytes
    file_modified = db.Column(db.DateTime)  # Last modified timestamp from file system
    
    # Session Metadata (parsed from filename)
    protocol = db.Column(db.String(20))  # ssh, sftp, shell
    username = db.Column(db.String(100))  # admin, root, etc.
    hostname = db.Column(db.String(255))  # server name or IP
    ip_address = db.Column(db.String(50))  # IP address
    friendly_name = db.Column(db.String(255))  # "DLI PDU", "NetMon", etc.
    
    # Session Timing
    session_start = db.Column(db.DateTime, nullable=False, index=True)
    session_end = db.Column(db.DateTime)
    duration_seconds = db.Column(db.Integer)
    
    # Session Details (parsed from log content)
    authentication_method = db.Column(db.String(100))  # "public key", "password"
    last_login_info = db.Column(db.String(500))  # From "Last login:" line
    mobaterm_version = db.Column(db.String(50))  # e.g. "v24.2"
    ssh_compression = db.Column(db.Boolean)
    x11_forwarding = db.Column(db.Boolean)
    
    # Session Statistics
    line_count = db.Column(db.Integer, default=0)
    command_count = db.Column(db.Integer, default=0)
    
    # Session Status
    status = db.Column(db.String(20), default='completed')  # completed, timeout, error, active
    exit_clean = db.Column(db.Boolean)  # Did user type 'exit' or was it disconnected?
    
    # Metadata
    notes = db.Column(db.Text)  # User-added notes
    tags = db.Column(db.String(500))  # Comma-separated tags
    is_flagged = db.Column(db.Boolean, default=False)  # Important sessions
    
    # Timestamps
    imported_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    commands = db.relationship('SSHCommand', backref='session', lazy='dynamic', cascade='all, delete-orphan')
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_hostname', 'hostname'),
        Index('idx_username', 'username'),
        Index('idx_session_start', 'session_start'),
        Index('idx_friendly_name', 'friendly_name'),
        Index('idx_status', 'status'),
    )
    
    def __repr__(self):
        return f'<SSHSession {self.username}@{self.hostname} on {self.session_start}>'
    
    @property
    def duration_formatted(self):
        """Return formatted duration string"""
        if not self.duration_seconds:
            return "Unknown"
        
        hours, remainder = divmod(self.duration_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    @classmethod
    def get_recent(cls, limit=50):
        """Get most recent sessions"""
        return cls.query.order_by(cls.session_start.desc()).limit(limit).all()
    
    @classmethod
    def get_by_host(cls, hostname):
        """Get all sessions for a specific host"""
        return cls.query.filter_by(hostname=hostname).order_by(cls.session_start.desc()).all()
    
    @classmethod
    def get_by_date_range(cls, start_date, end_date):
        """Get sessions within date range"""
        return cls.query.filter(
            cls.session_start >= start_date,
            cls.session_start <= end_date
        ).order_by(cls.session_start.desc()).all()
    
    @classmethod
    def search(cls, query_text):
        """Search across sessions"""
        search_term = f'%{query_text}%'
        return cls.query.filter(
            db.or_(
                cls.hostname.ilike(search_term),
                cls.username.ilike(search_term),
                cls.friendly_name.ilike(search_term),
                cls.ip_address.ilike(search_term),
                cls.notes.ilike(search_term)
            )
        ).order_by(cls.session_start.desc()).all()
    
    @classmethod
    def get_unique_hosts(cls):
        """Get list of all unique hostnames"""
        return db.session.query(cls.hostname, cls.friendly_name)\
            .distinct()\
            .filter(cls.hostname.isnot(None))\
            .order_by(cls.hostname)\
            .all()
    
    @classmethod
    @classmethod
    def get_stats(cls, days=30):
        """Get statistics for dashboard"""
        from sqlalchemy import func
        from datetime import timedelta
        
        # Only apply date filter if days is specified
        if days is not None:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            query_filter = cls.query.filter(cls.session_start >= cutoff_date)
        else:
            query_filter = cls.query  # All time
        
        stats = {
            'total_sessions': cls.query.count(),
            'recent_sessions': query_filter.count(),
            'unique_hosts': db.session.query(func.count(func.distinct(cls.hostname))).scalar(),
            'total_commands': db.session.query(func.sum(cls.command_count)).scalar() or 0,
            'avg_duration': db.session.query(func.avg(cls.duration_seconds)).scalar(),
        }
        
        # Most accessed host
        most_accessed = db.session.query(
            cls.hostname, 
            cls.friendly_name,
            func.count(cls.id).label('count')
        ).group_by(cls.hostname, cls.friendly_name)\
         .order_by(func.count(cls.id).desc())\
         .first()
        
        if most_accessed:
            stats['most_accessed_host'] = {
                'hostname': most_accessed[0],
                'friendly_name': most_accessed[1],
                'count': most_accessed[2]
            }
        else:
            stats['most_accessed_host'] = None
        
        return stats


class SSHCommand(db.Model):
    """Individual commands executed within SSH sessions"""
    __tablename__ = 'ssh_commands'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('ssh_sessions.id'), nullable=False)
    
    # Command Details
    sequence_number = db.Column(db.Integer, nullable=False)  # Order within session
    timestamp = db.Column(db.DateTime, nullable=False)
    command_text = db.Column(db.Text, nullable=False)
    output_preview = db.Column(db.Text)  # First 1000 chars of output
    
    # Command Classification
    command_type = db.Column(db.String(50))  # system_info, file_ops, network, package_mgmt, custom
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index('idx_session_sequence', 'session_id', 'sequence_number'),
        Index('idx_command_type', 'command_type'),
        Index('idx_timestamp', 'timestamp'),
    )
    
    def __repr__(self):
        return f'<SSHCommand #{self.sequence_number}: {self.command_text[:50]}>'
    
    @classmethod
    def classify_command(cls, command_text):
        """Auto-classify command based on content"""
        cmd_lower = command_text.lower().strip()
        
        # System info commands
        if any(cmd in cmd_lower for cmd in ['top', 'ps', 'htop', 'uptime', 'free', 'df', 'du', 'vmstat', 'iostat']):
            return 'system_info'
        
        # File operations
        if any(cmd in cmd_lower for cmd in ['ls', 'cd', 'cp', 'mv', 'rm', 'mkdir', 'touch', 'cat', 'nano', 'vi', 'vim']):
            return 'file_ops'
        
        # Network commands
        if any(cmd in cmd_lower for cmd in ['ping', 'traceroute', 'netstat', 'ss', 'ip', 'ifconfig', 'curl', 'wget', 'ssh', 'scp']):
            return 'network'
        
        # Package management
        if any(cmd in cmd_lower for cmd in ['apt', 'yum', 'dnf', 'pacman', 'npm', 'pip', 'brew']):
            return 'package_mgmt'
        
        # Service management
        if any(cmd in cmd_lower for cmd in ['systemctl', 'service', 'systemd', 'restart', 'start', 'stop', 'reload']):
            return 'service_mgmt'
        
        # User/permission management
        if any(cmd in cmd_lower for cmd in ['chmod', 'chown', 'useradd', 'usermod', 'passwd', 'su', 'sudo']):
            return 'user_mgmt'
        
        # Exit/logout
        if cmd_lower in ['exit', 'logout', 'quit']:
            return 'session_control'
        
        return 'custom'
    
    @classmethod
    def get_top_commands(cls, limit=20, days=30):
        """Get most frequently used commands"""
        from sqlalchemy import func
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        return db.session.query(
            cls.command_text,
            func.count(cls.id).label('count')
        ).join(SSHSession)\
         .filter(SSHSession.session_start >= cutoff_date)\
         .group_by(cls.command_text)\
         .order_by(func.count(cls.id).desc())\
         .limit(limit)\
         .all()


class SSHScanLog(db.Model):
    """Track when NAS directories were scanned for new logs"""
    __tablename__ = 'ssh_scan_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    scan_path = db.Column(db.String(1000), nullable=False)  # Directory that was scanned
    scan_started = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    scan_completed = db.Column(db.DateTime)
    
    # Results
    files_found = db.Column(db.Integer, default=0)
    files_new = db.Column(db.Integer, default=0)
    files_updated = db.Column(db.Integer, default=0)
    files_skipped = db.Column(db.Integer, default=0)
    files_error = db.Column(db.Integer, default=0)
    
    # Status
    status = db.Column(db.String(20), default='running')  # running, completed, error
    error_message = db.Column(db.Text)
    
    # Performance
    duration_seconds = db.Column(db.Float)
    
    def __repr__(self):
        return f'<SSHScanLog {self.scan_path} at {self.scan_started}>'
    
    @classmethod
    def get_last_scan(cls):
        """Get most recent scan log"""
        return cls.query.order_by(cls.scan_started.desc()).first()


def init_ssh_logs():
    """Initialize SSH logs module (if needed)"""
    # Currently no initialization needed, but keeping for consistency
    print("✅ SSH Logs module initialized")