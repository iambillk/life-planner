# models/health.py
"""
Enhanced Health Tracking Models - The Accountability System
Version: 2.0.0
Updated: 2025-01-07

CHANGELOG:
v2.0.0 (2025-01-07)
- Added drill sergeant accountability features
- Added bad habit tracking (soda, candy, junk food)
- Added failure logging and analysis
- Added weight goals and streak tracking
- Added AI harassment integration points
"""

from datetime import datetime, date, timedelta
from .base import db
from sqlalchemy import func


class WeightEntry(db.Model):
    """Daily weight tracking with accountability"""
    __tablename__ = 'weight_entries'
    
    id = db.Column(db.Integer, primary_key=True)
    weight = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, default=date.today, unique=True, index=True)
    
    # Morning measurement compliance
    time_logged = db.Column(db.Time, default=datetime.now().time)
    is_morning = db.Column(db.Boolean, default=False)  # Logged before 10am
    
    # Bad habits tracking
    had_soda = db.Column(db.Boolean, default=False)
    soda_count = db.Column(db.Integer, default=0)
    had_candy = db.Column(db.Boolean, default=False)
    had_junk_food = db.Column(db.Boolean, default=False)
    had_fast_food = db.Column(db.Boolean, default=False)
    had_alcohol = db.Column(db.Boolean, default=False)
    
    # Exercise tracking
    exercised = db.Column(db.Boolean, default=False)
    exercise_minutes = db.Column(db.Integer, default=0)
    steps = db.Column(db.Integer, default=0)
    
    # Water tracking (glasses)
    water_intake = db.Column(db.Integer, default=0)
    
    # Calorie tracking (optional)
    calories_consumed = db.Column(db.Integer)
    
    # Accountability
    excuse = db.Column(db.Text)  # What's your excuse today?
    notes = db.Column(db.Text)
    
    # Relationships
    failures = db.relationship('WeightFailure', backref='weight_entry', lazy='dynamic')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def weight_change(self):
        """Calculate change from previous entry"""
        previous = WeightEntry.query.filter(
            WeightEntry.date < self.date
        ).order_by(WeightEntry.date.desc()).first()
        
        if previous:
            return self.weight - previous.weight
        return 0
    
    @property
    def failure_count(self):
        """Count failures for the day"""
        count = 0
        if self.had_soda: count += 1
        if self.had_candy: count += 1
        if self.had_junk_food: count += 1
        if self.had_fast_food: count += 1
        if self.had_alcohol: count += 1
        if not self.exercised: count += 1
        if self.water_intake < 8: count += 1
        return count
    
    @classmethod
    def get_today(cls):
        """Get or create today's entry"""
        today = date.today()
        entry = cls.query.filter_by(date=today).first()
        if not entry:
            # Get last weight for reference
            last_entry = cls.query.order_by(cls.date.desc()).first()
            entry = cls(
                date=today,
                weight=last_entry.weight if last_entry else 200.0  # Default starting weight
            )
            db.session.add(entry)
            db.session.commit()
        return entry


class WeightGoal(db.Model):
    """Weight loss goals and tracking"""
    __tablename__ = 'weight_goals'
    
    id = db.Column(db.Integer, primary_key=True)
    start_weight = db.Column(db.Float, nullable=False)
    current_weight = db.Column(db.Float, nullable=False)
    goal_weight = db.Column(db.Float, nullable=False)
    
    start_date = db.Column(db.Date, default=date.today)
    target_date = db.Column(db.Date)
    
    # Weekly targets
    weekly_loss_target = db.Column(db.Float, default=2.0)  # lbs per week
    
    # Streaks
    days_logged_streak = db.Column(db.Integer, default=0)
    days_no_soda_streak = db.Column(db.Integer, default=0)
    days_no_junk_streak = db.Column(db.Integer, default=0)
    days_exercised_streak = db.Column(db.Integer, default=0)
    
    # Best streaks (for shaming when broken)
    best_logged_streak = db.Column(db.Integer, default=0)
    best_no_soda_streak = db.Column(db.Integer, default=0)
    best_no_junk_streak = db.Column(db.Integer, default=0)
    best_exercise_streak = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    @property
    def progress_percentage(self):
        """Calculate progress towards goal"""
        total_to_lose = self.start_weight - self.goal_weight
        lost_so_far = self.start_weight - self.current_weight
        if total_to_lose > 0:
            return (lost_so_far / total_to_lose) * 100
        return 0
    
    @property
    def days_remaining(self):
        """Days until target date"""
        if self.target_date:
            return (self.target_date - date.today()).days
        return None
    
    @property
    def required_daily_loss(self):
        """Required daily loss to meet goal"""
        if self.days_remaining and self.days_remaining > 0:
            remaining_loss = self.current_weight - self.goal_weight
            return remaining_loss / self.days_remaining
        return None
    
    @classmethod
    def get_active(cls):
        """Get the active goal"""
        return cls.query.order_by(cls.created_at.desc()).first()


class WeightFailure(db.Model):
    """Track and analyze failures"""
    __tablename__ = 'weight_failures'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=date.today, index=True)
    weight_entry_id = db.Column(db.Integer, db.ForeignKey('weight_entries.id'))
    
    failure_type = db.Column(db.String(50))  # soda, candy, junk, skipped_weigh, no_exercise
    description = db.Column(db.Text)
    
    # Context for pattern analysis
    time_of_day = db.Column(db.Time, default=datetime.now().time)
    trigger = db.Column(db.String(100))  # stress, boredom, social, craving
    location = db.Column(db.String(100))  # home, work, restaurant, store
    
    # Accountability
    could_have_avoided = db.Column(db.Boolean, default=True)
    excuse = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @classmethod
    def log_failure(cls, failure_type, description, trigger=None, excuse=None):
        """Quick failure logging"""
        today_entry = WeightEntry.get_today()
        failure = cls(
            weight_entry_id=today_entry.id,
            failure_type=failure_type,
            description=description,
            trigger=trigger,
            excuse=excuse
        )
        db.session.add(failure)
        
        # Update weight entry bad habits
        if failure_type == 'soda':
            today_entry.had_soda = True
            today_entry.soda_count += 1
        elif failure_type == 'candy':
            today_entry.had_candy = True
        elif failure_type == 'junk':
            today_entry.had_junk_food = True
        elif failure_type == 'fast_food':
            today_entry.had_fast_food = True
        
        db.session.commit()
        return failure
    
    @classmethod
    def get_patterns(cls, days=30):
        """Analyze failure patterns for AI harassment"""
        since_date = date.today() - timedelta(days=days)
        failures = cls.query.filter(cls.date >= since_date).all()
        
        patterns = {
            'total': len(failures),
            'by_type': {},
            'by_trigger': {},
            'by_time': {'morning': 0, 'afternoon': 0, 'evening': 0, 'night': 0},
            'worst_day': None,
            'worst_time': None
        }
        
        # Analyze patterns
        for failure in failures:
            # By type
            if failure.failure_type not in patterns['by_type']:
                patterns['by_type'][failure.failure_type] = 0
            patterns['by_type'][failure.failure_type] += 1
            
            # By trigger
            if failure.trigger:
                if failure.trigger not in patterns['by_trigger']:
                    patterns['by_trigger'][failure.trigger] = 0
                patterns['by_trigger'][failure.trigger] += 1
            
            # By time of day
            if failure.time_of_day:
                hour = failure.time_of_day.hour
                if hour < 12:
                    patterns['by_time']['morning'] += 1
                elif hour < 17:
                    patterns['by_time']['afternoon'] += 1
                elif hour < 21:
                    patterns['by_time']['evening'] += 1
                else:
                    patterns['by_time']['night'] += 1
        
        # Find worst patterns
        if patterns['by_type']:
            patterns['worst_habit'] = max(patterns['by_type'], key=patterns['by_type'].get)
        if patterns['by_trigger']:
            patterns['worst_trigger'] = max(patterns['by_trigger'], key=patterns['by_trigger'].get)
        if patterns['by_time']:
            patterns['worst_time'] = max(patterns['by_time'], key=patterns['by_time'].get)
        
        return patterns


class HealthHarassment(db.Model):
    """Track harassment messages and responses"""
    __tablename__ = 'health_harassment'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=date.today)
    time = db.Column(db.Time, default=datetime.now().time)
    
    message = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(20))  # gentle, firm, brutal, savage
    category = db.Column(db.String(50))  # weight_gain, soda, candy, no_exercise, etc
    
    # AI-generated insights
    ai_analysis = db.Column(db.Text)
    personalized = db.Column(db.Boolean, default=False)
    
    # User response tracking
    acknowledged = db.Column(db.Boolean, default=False)
    user_response = db.Column(db.Text)
    helped = db.Column(db.Boolean)  # Did this message help?
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @classmethod
    def add(cls, message, severity='brutal', category=None, ai_analysis=None):
        """Add a harassment entry"""
        entry = cls(
            message=message,
            severity=severity,
            category=category,
            ai_analysis=ai_analysis,
            personalized=bool(ai_analysis)
        )
        db.session.add(entry)
        db.session.commit()
        return entry


class HealthConfig(db.Model):
    """Configuration for health module behavior"""
    __tablename__ = 'health_config'
    
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text)
    
    @classmethod
    def get(cls, key, default=None):
        """Get a config value"""
        config = cls.query.get(key)
        return config.value if config else default
    
    @classmethod
    def set(cls, key, value):
        """Set a config value"""
        config = cls.query.get(key)
        if config:
            config.value = str(value)
        else:
            config = cls(key=key, value=str(value))
            db.session.add(config)
        db.session.commit()
        return config


# Initialize default health configs
def init_health_configs():
    """Set default health module configurations"""
    defaults = {
        'harassment_enabled': 'true',
        'harassment_level': 'BRUTAL',
        'morning_weigh_time': '10:00',  # Must weigh before this time
        'soda_limit': '0',  # Zero tolerance
        'water_goal': '8',  # glasses per day
        'exercise_minimum': '30',  # minutes per day
        'weight_goal': '180',  # target weight
        'weekly_loss_goal': '2',  # pounds per week
        'ai_harassment': 'true',  # Use AI for personalized harassment
        'public_shame': 'false',  # Future feature: post failures publicly
    }
    
    for key, value in defaults.items():
        if not HealthConfig.query.get(key):
            HealthConfig.set(key, value)
    
    db.session.commit()