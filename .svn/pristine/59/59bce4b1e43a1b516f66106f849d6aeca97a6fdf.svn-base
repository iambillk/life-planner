# models/daily_planner.py
"""
Daily Planner Database Models
The Drill Sergeant Life Management System
"""

from datetime import datetime, date
from models.base import db

# ============ CONFIGURATION ============

class DailyConfig(db.Model):
    """System configuration settings"""
    __tablename__ = 'daily_config'
    
    setting_name = db.Column(db.String(50), primary_key=True)
    setting_value = db.Column(db.Text)
    
    @classmethod
    def get(cls, key, default=None):
        """Get a config value"""
        config = cls.query.get(key)
        return config.setting_value if config else default
    
    @classmethod
    def set(cls, key, value):
        """Set a config value"""
        config = cls.query.get(key)
        if config:
            config.setting_value = str(value)
        else:
            config = cls(setting_name=key, setting_value=str(value))
            db.session.add(config)
        db.session.commit()


# ============ CALENDAR SYSTEM ============

class CalendarEvent(db.Model):
    """Calendar events - appointments, family stuff, etc"""
    __tablename__ = 'calendar_events'
    
    id = db.Column(db.Integer, primary_key=True)
    event_date = db.Column(db.Date, nullable=False, index=True)
    event_time = db.Column(db.String(20))  # "2:00 PM" or "Morning"
    event_type = db.Column(db.String(50))  # Soccer, Dentist, etc
    who = db.Column(db.String(20))  # Me/Wife/Tommy/Sarah/Family
    description = db.Column(db.Text)
    category = db.Column(db.String(30))  # Work, Errands, Health, Social, Family
    location = db.Column(db.String(50))  # Office, Home, DC, etc
    was_planned = db.Column(db.Boolean, default=True)  # False = emergency/urgent
    recurring_id = db.Column(db.Integer, db.ForeignKey('recurring_events.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    recurring = db.relationship('RecurringEvent', backref='events')


class EventType(db.Model):
    """Growing list of event types for quick selection"""
    __tablename__ = 'event_types'
    
    id = db.Column(db.Integer, primary_key=True)
    type_name = db.Column(db.String(50), unique=True, nullable=False)
    usage_count = db.Column(db.Integer, default=0)  # Track most used
    
    @classmethod
    def get_or_create(cls, type_name):
        """Get existing or create new event type"""
        event_type = cls.query.filter_by(type_name=type_name).first()
        if not event_type:
            event_type = cls(type_name=type_name)
            db.session.add(event_type)
            db.session.commit()
        else:
            event_type.usage_count += 1
            db.session.commit()
        return event_type


class RecurringEvent(db.Model):
    """Recurring event patterns with multiple recurrence types"""
    __tablename__ = 'recurring_events'
    
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50))
    
    # Recurrence pattern fields
    recurrence_type = db.Column(db.String(20))  # 'daily', 'weekly', 'monthly_date', 'monthly_day', 'yearly'
    
    # For daily recurrence
    daily_interval = db.Column(db.Integer, default=1)  # Every X days
    
    # For weekly recurrence (existing)
    days_of_week = db.Column(db.String(50))  # "Mon,Wed,Fri"
    weekly_interval = db.Column(db.Integer, default=1)  # Every X weeks
    
    # For monthly recurrence by date
    monthly_date = db.Column(db.Integer)  # Day of month (1-31)
    monthly_interval = db.Column(db.Integer, default=1)  # Every X months
    
    # For monthly recurrence by day
    monthly_week = db.Column(db.Integer)  # 1=first, 2=second, 3=third, 4=fourth, -1=last
    monthly_weekday = db.Column(db.Integer)  # 0=Monday, 6=Sunday
    
    # For yearly recurrence
    yearly_month = db.Column(db.Integer)  # 1-12
    yearly_day = db.Column(db.Integer)  # 1-31
    
    # Common fields
    time = db.Column(db.String(20))
    who = db.Column(db.String(20))
    description = db.Column(db.Text)
    category = db.Column(db.String(30))  # NEW - Work, Errands, Health, Social, Family
    location = db.Column(db.String(50))  # NEW - Office, Home, DC, etc
    until_date = db.Column(db.Date)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    


# ============ PROJECT INTEGRATION ============

class DailyTask(db.Model):
    """Tasks selected from projects for daily execution"""
    __tablename__ = 'daily_tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True, default=date.today)
    project_id = db.Column(db.Integer)
    project_type = db.Column(db.String(10))  # 'TCH' or 'Personal'
    project_name = db.Column(db.String(100))  # Denormalized for speed
    task_description = db.Column(db.Text, nullable=False)
    priority = db.Column(db.Integer, default=0)  # For ordering
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def complete(self):
        """Mark task as complete"""
        self.completed = True
        self.completed_at = datetime.utcnow()
        db.session.commit()


# ============ HUMAN MAINTENANCE ============

class HumanMaintenance(db.Model):
    """Daily tracking of biological necessities"""
    __tablename__ = 'human_maintenance'
    
    date = db.Column(db.Date, primary_key=True, default=date.today)
    
    # Morning essentials
    meds_taken = db.Column(db.Boolean, default=False)
    meds_taken_time = db.Column(db.Time)
    shower_taken = db.Column(db.Boolean, default=False)
    teeth_brushed_am = db.Column(db.Boolean, default=False)
    teeth_brushed_pm = db.Column(db.Boolean, default=False)
    
    # Food/water
    breakfast = db.Column(db.Boolean, default=False)
    lunch = db.Column(db.Boolean, default=False)
    dinner = db.Column(db.Boolean, default=False)
    water_glasses = db.Column(db.Integer, default=0)
    
    # Tracking
    last_shower_date = db.Column(db.Date)
    
    @classmethod
    def get_today(cls):
        """Get or create today's record"""
        today = date.today()
        record = cls.query.get(today)
        if not record:
            # Find last shower date
            last_record = cls.query.filter(
                cls.shower_taken == True
            ).order_by(cls.date.desc()).first()
            
            record = cls(
                date=today,
                last_shower_date=last_record.date if last_record else None
            )
            db.session.add(record)
            db.session.commit()
        return record
    
    @property
    def days_since_shower(self):
        """Calculate days since last shower"""
        if self.shower_taken:
            return 0
        if self.last_shower_date:
            return (self.date - self.last_shower_date).days
        return 999  # Unknown but probably bad
    
    @property
    def morning_complete(self):
        """Check if morning minimums are done"""
        completed = 0
        if self.meds_taken: completed += 1
        if self.shower_taken or self.days_since_shower < 2: completed += 1
        if self.teeth_brushed_am: completed += 1
        return completed


# ============ NOTE CAPTURE ============

class CapturedNote(db.Model):
    """Quick capture for random thoughts/tasks"""
    __tablename__ = 'captured_notes'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=date.today, index=True)
    category = db.Column(db.String(20))  # Work/Personal/Kids/Crisis/Random
    note = db.Column(db.Text, nullable=False)
    resolved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ============ DRILL SERGEANT ============

class HarassmentLog(db.Model):
    """Track what we yelled about and when"""
    __tablename__ = 'harassment_log'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=date.today)
    time = db.Column(db.Time, default=datetime.now().time)
    message = db.Column(db.Text)
    severity = db.Column(db.String(20))  # 'warning', 'critical', 'lockout'
    acknowledged = db.Column(db.Boolean, default=False)
    
    @classmethod
    def add(cls, message, severity='warning'):
        """Add a harassment entry"""
        entry = cls(
            message=message,
            severity=severity
        )
        db.session.add(entry)
        db.session.commit()
        return entry


class ProjectRotation(db.Model):
    """Track which projects were shown when"""
    __tablename__ = 'project_rotation'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=date.today)
    project_id = db.Column(db.Integer)
    project_type = db.Column(db.String(10))  # 'TCH' or 'Personal'
    last_shown = db.Column(db.Date)
    last_touched = db.Column(db.Date)
    times_ignored = db.Column(db.Integer, default=0)
    priority_score = db.Column(db.Integer, default=0)


# ============ INITIALIZATION ============

def init_daily_planner():
    """Initialize daily planner with default settings"""
    
    # Default config
    defaults = {
        'projects_to_show': '5',
        'harassment_level': 'BRUTAL',
        'lockout_enabled': 'true',
        'shower_threshold_days': '2',
        'morning_lockout_tasks': '2',  # Must complete 2 of 3
        'default_view': 'week',
    }
    
    for key, value in defaults.items():
        if not DailyConfig.query.get(key):
            DailyConfig.set(key, value)
    
    # Default event types
    default_types = [
        'Soccer', 'Dentist', 'Doctor', 'Meeting', 'School Event',
        'Dance', 'Book Club', 'Client Call', 'Appointment',
        'Family Event', 'Deadline', 'Birthday'
    ]
    
    for type_name in default_types:
        EventType.get_or_create(type_name)
    
    db.session.commit()
    print("Daily Planner initialized with defaults")