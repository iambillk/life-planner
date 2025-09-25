# models/todo_advanced.py
"""
Advanced models for the enhanced todo system
Adds support for dependencies, recurring tasks, time tracking, and templates
"""

from datetime import datetime, date, timedelta
from models.base import db

class TaskDependency(db.Model):
    """Links tasks that depend on each other"""
    __tablename__ = 'task_dependencies'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Task that depends on another (unified IDs like 'tch_123')
    dependent_task_id = db.Column(db.String(50), nullable=False, index=True)
    dependent_task_type = db.Column(db.String(20))  # Source type for quick filtering
    
    # Task that must be completed first
    prerequisite_task_id = db.Column(db.String(50), nullable=False, index=True)
    prerequisite_task_type = db.Column(db.String(20))
    
    # Dependency type
    dependency_type = db.Column(db.String(20), default='blocks')  # blocks, related, parent
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Unique constraint to prevent duplicate dependencies
    __table_args__ = (
        db.UniqueConstraint('dependent_task_id', 'prerequisite_task_id', name='unique_dependency'),
    )


class RecurringTaskTemplate(db.Model):
    """Templates for recurring tasks"""
    __tablename__ = 'recurring_task_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Template details
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Where to create the task
    target_type = db.Column(db.String(20), nullable=False)  # tch, personal, todo
    target_project_id = db.Column(db.Integer)  # Optional specific project
    
    # Recurrence pattern
    recurrence_type = db.Column(db.String(20), nullable=False)  # daily, weekly, monthly, custom
    recurrence_days = db.Column(db.String(50))  # For weekly: "1,3,5" (Mon, Wed, Fri)
    recurrence_day_of_month = db.Column(db.Integer)  # For monthly: 15 = 15th of each month
    recurrence_interval = db.Column(db.Integer, default=1)  # Every X days/weeks/months
    
    # Task properties
    priority = db.Column(db.String(20), default='medium')
    category = db.Column(db.String(50))
    estimated_minutes = db.Column(db.Integer)  # Time estimate
    
    # Active period
    start_date = db.Column(db.Date, default=date.today)
    end_date = db.Column(db.Date)  # Optional end date
    is_active = db.Column(db.Boolean, default=True)
    
    # Last execution tracking
    last_created = db.Column(db.Date)
    next_due = db.Column(db.Date)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def calculate_next_due(self):
        """Calculate when this task should next be created"""
        if not self.last_created:
            return self.start_date
        
        if self.recurrence_type == 'daily':
            return self.last_created + timedelta(days=self.recurrence_interval)
        
        elif self.recurrence_type == 'weekly':
            # Parse days of week (0=Monday, 6=Sunday)
            if self.recurrence_days:
                days = [int(d) for d in self.recurrence_days.split(',')]
                current_day = self.last_created.weekday()
                
                # Find next occurrence
                for offset in range(1, 8):
                    check_date = self.last_created + timedelta(days=offset)
                    if check_date.weekday() in days:
                        return check_date
            
            # Fallback to simple weekly
            return self.last_created + timedelta(weeks=self.recurrence_interval)
        
        elif self.recurrence_type == 'monthly':
            # Next month on specified day
            next_month = self.last_created.month + self.recurrence_interval
            next_year = self.last_created.year
            
            if next_month > 12:
                next_month -= 12
                next_year += 1
            
            try:
                return date(next_year, next_month, self.recurrence_day_of_month or self.last_created.day)
            except ValueError:
                # Handle invalid dates (e.g., Feb 31st)
                # Use last day of month
                import calendar
                last_day = calendar.monthrange(next_year, next_month)[1]
                return date(next_year, next_month, last_day)
        
        return None


class TaskTimeLog(db.Model):
    """Track time spent on tasks"""
    __tablename__ = 'task_time_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Task reference (unified ID)
    task_id = db.Column(db.String(50), nullable=False, index=True)
    task_type = db.Column(db.String(20))
    task_title = db.Column(db.String(200))  # Denormalized for quick access
    
    # Time tracking
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    duration_minutes = db.Column(db.Integer)  # Calculated on end
    
    # Work session details
    notes = db.Column(db.Text)
    was_interrupted = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def is_running(self):
        """Check if this time log is currently running"""
        return self.end_time is None
    
    def stop(self):
        """Stop the timer and calculate duration"""
        if not self.is_running:
            return False
        
        self.end_time = datetime.utcnow()
        delta = self.end_time - self.start_time
        self.duration_minutes = int(delta.total_seconds() / 60)
        return True


class TaskTemplate(db.Model):
    """Reusable task templates for common workflows"""
    __tablename__ = 'task_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Template info
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))  # Group templates
    
    # Template content (JSON string for flexibility)
    # Will store: {"tasks": [{"title": "...", "priority": "...", "estimated_minutes": ...}]}
    template_data = db.Column(db.Text, nullable=False)
    
    # Usage tracking
    times_used = db.Column(db.Integer, default=0)
    last_used = db.Column(db.DateTime)
    
    # Template properties
    is_public = db.Column(db.Boolean, default=False)  # Could be shared in future
    target_type = db.Column(db.String(20))  # Preferred target: tch, personal, todo
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TaskMetadata(db.Model):
    """Additional metadata for any task type without modifying original schemas"""
    __tablename__ = 'task_metadata'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Task reference (unified ID)
    task_id = db.Column(db.String(50), nullable=False, unique=True, index=True)
    task_type = db.Column(db.String(20), nullable=False)
    
    # Extended properties
    estimated_minutes = db.Column(db.Integer)
    actual_minutes = db.Column(db.Integer)  # Calculated from time logs
    
    # Tags (comma-separated for simplicity)
    tags = db.Column(db.String(500))
    
    # Energy level required (for energy-based scheduling)
    energy_level = db.Column(db.String(20))  # low, medium, high
    
    # Best time to do this task
    preferred_time = db.Column(db.String(20))  # morning, afternoon, evening, anytime
    
    # Location context
    context = db.Column(db.String(50))  # home, office, errands, calls
    
    # Review/reflection
    completion_notes = db.Column(db.Text)
    difficulty_rating = db.Column(db.Integer)  # 1-5 scale
    satisfaction_rating = db.Column(db.Integer)  # 1-5 scale
    
    # Stats
    times_snoozed = db.Column(db.Integer, default=0)
    times_rescheduled = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def add_tag(self, tag):
        """Add a tag to this task"""
        current_tags = set(self.tags.split(',')) if self.tags else set()
        current_tags.add(tag.strip())
        self.tags = ','.join(sorted(current_tags))
    
    def remove_tag(self, tag):
        """Remove a tag from this task"""
        if not self.tags:
            return
        current_tags = set(self.tags.split(','))
        current_tags.discard(tag.strip())
        self.tags = ','.join(sorted(current_tags)) if current_tags else None
    
    def has_tag(self, tag):
        """Check if task has a specific tag"""
        if not self.tags:
            return False
        return tag.strip() in self.tags.split(',')


class TaskUserPreferences(db.Model):
    """Store user preferences for the unified todo view"""
    __tablename__ = 'task_user_preferences'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # View preferences
    default_view = db.Column(db.String(50), default='priority')  # priority, timeline, matrix, kanban
    default_sources = db.Column(db.String(100))  # Comma-separated: tch,personal,todo,daily
    default_date_filter = db.Column(db.String(20))  # today, week, month, all
    show_completed_by_default = db.Column(db.Boolean, default=False)
    
    # Display preferences
    compact_mode = db.Column(db.Boolean, default=False)
    show_task_numbers = db.Column(db.Boolean, default=True)
    show_time_estimates = db.Column(db.Boolean, default=True)
    group_by = db.Column(db.String(20), default='priority')  # priority, source, project, date
    
    # Productivity preferences
    daily_task_limit = db.Column(db.Integer, default=10)
    enable_time_tracking = db.Column(db.Boolean, default=True)
    enable_pomodoro = db.Column(db.Boolean, default=False)
    pomodoro_duration = db.Column(db.Integer, default=25)  # minutes
    
    # Notification preferences (for future)
    notify_overdue = db.Column(db.Boolean, default=True)
    notify_deadline_days = db.Column(db.Integer, default=1)  # Days before deadline
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)