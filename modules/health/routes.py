# modules/health/routes.py
"""
Enhanced Health Tracking Routes - The Accountability System
Complete routes with drill sergeant features and AI integration
Version: 2.0.0
"""

from flask import render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, date, timedelta
from sqlalchemy import func, and_
from . import health_bp
from models.base import db
from models.health import (
    WeightEntry, WeightGoal, WeightFailure, 
    HealthHarassment, HealthConfig, init_health_configs
)
from models.daily_planner import DailyConfig, HarassmentLog
import random
import json


# ==================== MAIN DASHBOARD ====================

@health_bp.route('/weight')
def weight_index():
    """Weight tracking dashboard with accountability"""
    
    # Initialize configs on first load
    if HealthConfig.query.count() == 0:
        init_health_configs()
    
    # Get today's entry
    today_entry = WeightEntry.get_today()
    
    # Get recent entries for trend
    entries = WeightEntry.query.order_by(WeightEntry.date.desc()).limit(30).all()
    
    # Get active goal
    goal = WeightGoal.get_active()
    if not goal and entries:
        # Create default goal if none exists
        goal = WeightGoal(
            start_weight=entries[-1].weight,
            current_weight=entries[0].weight,
            goal_weight=float(HealthConfig.get('weight_goal', '180'))
        )
        db.session.add(goal)
        db.session.commit()
    
    # Update current weight in goal
    if goal and entries:
        goal.current_weight = entries[0].weight
        db.session.commit()
    
    # Calculate stats
    stats = calculate_weight_stats(entries)
    
    # Get failure patterns for AI harassment
    patterns = WeightFailure.get_patterns(days=7)
    
    # Generate harassment message based on current state
    harassment = generate_harassment(today_entry, stats, patterns, goal)
    
    # Check for streaks
    streaks = check_streaks(entries)
    
    # Get today's failures
    today_failures = WeightFailure.query.filter_by(date=date.today()).all()
    
    return render_template(
        'health/weight_dashboard.html',
        today_entry=today_entry,
        entries=entries,
        stats=stats,
        goal=goal,
        harassment=harassment,
        streaks=streaks,
        patterns=patterns,
        today_failures=today_failures,
        active='weight'
    )


# ==================== WEIGHT LOGGING ====================

@health_bp.route('/weight/log', methods=['GET', 'POST'])
def log_weight():
    """Log daily weight with accountability questions"""
    
    if request.method == 'POST':
        today_entry = WeightEntry.get_today()
        
        # Update weight
        today_entry.weight = float(request.form.get('weight'))
        today_entry.time_logged = datetime.now().time()
        today_entry.is_morning = datetime.now().hour < 10
        
        # Update bad habits
        today_entry.had_soda = request.form.get('had_soda') == 'yes'
        today_entry.soda_count = int(request.form.get('soda_count', 0))
        today_entry.had_candy = request.form.get('had_candy') == 'yes'
        today_entry.had_junk_food = request.form.get('had_junk') == 'yes'
        today_entry.had_fast_food = request.form.get('had_fast_food') == 'yes'
        today_entry.had_alcohol = request.form.get('had_alcohol') == 'yes'
        
        # Exercise and water
        today_entry.exercised = request.form.get('exercised') == 'yes'
        today_entry.exercise_minutes = int(request.form.get('exercise_minutes', 0))
        today_entry.water_intake = int(request.form.get('water_glasses', 0))
        
        # Notes and excuses
        today_entry.excuse = request.form.get('excuse')
        today_entry.notes = request.form.get('notes')
        
        # Log failures with context
        if today_entry.had_soda:
            WeightFailure.log_failure(
                'soda', 
                f"Had {today_entry.soda_count} soda(s)",
                trigger=request.form.get('soda_trigger'),
                excuse=request.form.get('soda_excuse')
            )
        
        if today_entry.had_candy:
            WeightFailure.log_failure(
                'candy',
                "Ate candy like a child",
                trigger=request.form.get('candy_trigger'),
                excuse=request.form.get('candy_excuse')
            )
        
        if today_entry.had_junk_food:
            WeightFailure.log_failure(
                'junk',
                "Ate junk food",
                trigger=request.form.get('junk_trigger')
            )
        
        # Calculate weight change
        previous = WeightEntry.query.filter(
            WeightEntry.date < today_entry.date
        ).order_by(WeightEntry.date.desc()).first()
        
        # Generate response based on performance
        if previous:
            change = today_entry.weight - previous.weight
            if change > 0:
                if today_entry.had_soda or today_entry.had_candy:
                    flash(f"UP {change:.1f} lbs! Of course you gained weight, you moron! Soda and candy? Really?", "danger")
                else:
                    flash(f"UP {change:.1f} lbs! What's your excuse this time?", "danger")
            elif change < 0:
                if abs(change) < 0.5:
                    flash(f"Down {abs(change):.1f} lbs. That's nothing. Try harder.", "warning")
                else:
                    flash(f"Down {abs(change):.1f} lbs. Don't get cocky. Keep going.", "success")
            else:
                flash("No change. You're stagnating. Step it up!", "warning")
        
        # Update streaks
        update_streaks()
        
        db.session.commit()
        
        # Log to harassment system
        if today_entry.failure_count > 0:
            HarassmentLog.add(
                f"Weight: {today_entry.failure_count} failures today. Pathetic.",
                severity='critical'
            )
        
        return redirect(url_for('health.weight_index'))
    
    # GET request - show the form
    today_entry = WeightEntry.get_today()
    
    # Get yesterday's weight for reference
    yesterday = WeightEntry.query.filter(
        WeightEntry.date < date.today()
    ).order_by(WeightEntry.date.desc()).first()
    
    return render_template(
        'health/log_weight.html',
        today_entry=today_entry,
        yesterday=yesterday,
        active='weight'
    )


# ==================== QUICK FAILURE LOGGING ====================

@health_bp.route('/weight/fail', methods=['POST'])
def log_failure():
    """Quick failure logging from dashboard"""
    
    failure_type = request.form.get('type')
    today_entry = WeightEntry.get_today()
    
    messages = {
        'soda': [
            "Soda? REALLY? You know that's liquid diabetes, right?",
            "Another soda. You're literally drinking your failure.",
            "Congratulations on choosing diabetes. Moron.",
            "Every soda is 10 minutes on the treadmill. Enjoy.",
        ],
        'candy': [
            "Candy? What are you, five years old?",
            "Sugar addict strikes again. Pathetic.",
            "Candy. Because you have the self-control of a toddler.",
            "That candy is going straight to your gut. Happy now?",
        ],
        'junk': [
            "Junk food. Of course. Why would you eat real food?",
            "Processed garbage. Your body must hate you.",
            "Junk food again. You're better than this. Act like it.",
            "That junk is why you're here. Stop it.",
        ],
        'fast_food': [
            "Fast food? More like fast track to obesity.",
            "Drive-thru? More like drive to diabetes.",
            "Fast food. Slow death. Your choice.",
            "McDonald's shareholders thank you for your weakness.",
        ]
    }
    
    # Log the failure
    if failure_type == 'soda':
        today_entry.had_soda = True
        today_entry.soda_count += 1
        message = random.choice(messages['soda'])
    elif failure_type == 'candy':
        today_entry.had_candy = True
        message = random.choice(messages['candy'])
    elif failure_type == 'junk':
        today_entry.had_junk_food = True
        message = random.choice(messages['junk'])
    elif failure_type == 'fast_food':
        today_entry.had_fast_food = True
        message = random.choice(messages['fast_food'])
    else:
        message = "Failure logged. Do better."
    
    # Create failure record
    WeightFailure.log_failure(
        failure_type,
        f"Quick log: {failure_type}",
        trigger=request.form.get('trigger', 'weakness')
    )
    
    # Add harassment log
    HealthHarassment.add(message, severity='brutal', category=failure_type)
    
    db.session.commit()
    
    flash(message, "danger")
    return redirect(url_for('health.weight_index'))


# ==================== AI HARASSMENT GENERATION ====================

def generate_harassment(today_entry, stats, patterns, goal):
    """Generate personalized harassment based on data"""
    
    harassment_level = HealthConfig.get('harassment_level', 'BRUTAL')
    
    if harassment_level == 'OFF':
        return None
    
    messages = []
    severity = 'brutal'
    
    # Check if weight was logged today
    if today_entry.date == date.today() and today_entry.time_logged:
        # Weight change harassment
        if stats and 'change_day' in stats:
            if stats['change_day'] > 0:
                messages.append(f"UP {stats['change_day']:.1f} LBS! What did you eat, a whole cake?")
                severity = 'savage'
            elif stats['change_day'] == 0:
                messages.append("No change. Stagnation is failure.")
    else:
        # Not logged yet
        hour = datetime.now().hour
        if hour > 10:
            messages.append("Still haven't weighed yourself? Scared of the truth?")
            severity = 'savage'
    
    # Bad habit harassment
    if today_entry.had_soda:
        if today_entry.soda_count > 1:
            messages.append(f"{today_entry.soda_count} SODAS?! Are you TRYING to get diabetes?")
        else:
            messages.append("You had soda. You know better. Weak.")
    
    if today_entry.had_candy:
        messages.append("Candy? Grow up. You're not a child.")
    
    if today_entry.had_junk_food:
        messages.append("Junk food is why you're here. STOP IT.")
    
    # Pattern-based harassment
    if patterns and patterns['total'] > 0:
        if patterns.get('worst_habit'):
            messages.append(f"Your worst habit: {patterns['worst_habit']}. Fix it or stay fat.")
        
        if patterns.get('worst_time'):
            messages.append(f"You always fail in the {patterns['worst_time']}. Plan better.")
        
        if patterns.get('worst_trigger') == 'stress':
            messages.append("Stress eating? Find a better coping mechanism, weakling.")
    
    # Goal-based harassment
    if goal:
        if goal.required_daily_loss and stats.get('change_day', 0) > -goal.required_daily_loss:
            messages.append(f"You need to lose {goal.required_daily_loss:.2f} lbs/day to hit your goal. You're failing.")
        
        if goal.days_remaining and goal.days_remaining < 30:
            messages.append(f"Only {goal.days_remaining} days left. You're running out of time!")
    
    # Water harassment
    if today_entry.water_intake < 8:
        messages.append(f"Only {today_entry.water_intake} glasses of water? You're dehydrated AND fat.")
    
    # Exercise harassment
    if not today_entry.exercised:
        messages.append("No exercise today? Your body is rotting.")
    elif today_entry.exercise_minutes < 30:
        messages.append(f"Only {today_entry.exercise_minutes} minutes? That's not exercise, that's a warm-up.")
    
    if messages:
        # Store the harassment
        message = " ".join(messages[:3])  # Limit to 3 messages
        HealthHarassment.add(message, severity=severity)
        return message
    
    return None


# ==================== STATISTICS CALCULATION ====================

def calculate_weight_stats(entries):
    """Calculate comprehensive weight statistics"""
    
    if not entries:
        return {}
    
    stats = {
        'current': entries[0].weight,
        'entries_count': len(entries)
    }
    
    # Daily change
    if len(entries) > 1:
        stats['change_day'] = entries[0].weight - entries[1].weight
    
    # Weekly change
    week_ago = date.today() - timedelta(days=7)
    week_entry = WeightEntry.query.filter_by(date=week_ago).first()
    if week_entry:
        stats['change_week'] = entries[0].weight - week_entry.weight
    
    # Monthly change
    month_ago = date.today() - timedelta(days=30)
    month_entry = WeightEntry.query.filter(
        WeightEntry.date <= month_ago
    ).order_by(WeightEntry.date.desc()).first()
    if month_entry:
        stats['change_month'] = entries[0].weight - month_entry.weight
    
    # Averages
    stats['average_7d'] = sum(e.weight for e in entries[:7]) / min(7, len(entries))
    stats['average_30d'] = sum(e.weight for e in entries) / len(entries)
    
    # Trends
    if len(entries) >= 7:
        first_week = sum(e.weight for e in entries[-7:]) / 7
        last_week = sum(e.weight for e in entries[:7]) / 7
        stats['trend'] = 'down' if last_week < first_week else 'up' if last_week > first_week else 'flat'
    
    # Failure stats
    total_failures = 0
    soda_days = 0
    candy_days = 0
    no_exercise_days = 0
    
    for entry in entries:
        if entry.had_soda: soda_days += 1
        if entry.had_candy: candy_days += 1
        if not entry.exercised: no_exercise_days += 1
        total_failures += entry.failure_count
    
    stats['failure_rate'] = (total_failures / (len(entries) * 7)) * 100 if entries else 0
    stats['soda_days'] = soda_days
    stats['candy_days'] = candy_days
    stats['no_exercise_days'] = no_exercise_days
    
    # Best and worst
    stats['lowest'] = min(e.weight for e in entries)
    stats['highest'] = max(e.weight for e in entries)
    
    return stats


# ==================== STREAK MANAGEMENT ====================

def check_streaks(entries):
    """Check and update streaks"""
    
    if not entries:
        return {}
    
    goal = WeightGoal.get_active()
    if not goal:
        return {}
    
    streaks = {
        'logged': 0,
        'no_soda': 0,
        'no_junk': 0,
        'exercise': 0,
        'water_goal': 0
    }
    
    # Check consecutive days
    expected_date = date.today()
    
    for entry in entries:
        if entry.date != expected_date:
            break  # Gap in entries
        
        # Logging streak
        streaks['logged'] += 1
        
        # No soda streak
        if not entry.had_soda:
            streaks['no_soda'] += 1
        else:
            if goal.days_no_soda_streak > goal.best_no_soda_streak:
                goal.best_no_soda_streak = goal.days_no_soda_streak
            goal.days_no_soda_streak = 0
            if streaks['no_soda'] == 0:
                break  # Streak broken today
        
        # No junk streak
        if not entry.had_junk_food and not entry.had_candy and not entry.had_fast_food:
            streaks['no_junk'] += 1
        else:
            if goal.days_no_junk_streak > goal.best_no_junk_streak:
                goal.best_no_junk_streak = goal.days_no_junk_streak
            goal.days_no_junk_streak = 0
            if streaks['no_junk'] == 0:
                break
        
        # Exercise streak
        if entry.exercised:
            streaks['exercise'] += 1
        else:
            if goal.days_exercised_streak > goal.best_exercise_streak:
                goal.best_exercise_streak = goal.days_exercised_streak
            goal.days_exercised_streak = 0
            if streaks['exercise'] == 0:
                break
        
        # Water goal streak
        if entry.water_intake >= 8:
            streaks['water_goal'] += 1
        
        expected_date = expected_date - timedelta(days=1)
    
    # Update goal streaks
    if goal:
        goal.days_logged_streak = streaks['logged']
        goal.days_no_soda_streak = streaks['no_soda']
        goal.days_no_junk_streak = streaks['no_junk']
        goal.days_exercised_streak = streaks['exercise']
        db.session.commit()
    
    return streaks


def update_streaks():
    """Update streak counters after daily entry"""
    goal = WeightGoal.get_active()
    if goal:
        entries = WeightEntry.query.order_by(WeightEntry.date.desc()).limit(30).all()
        check_streaks(entries)


# ==================== CHARTS AND ANALYTICS ====================

@health_bp.route('/weight/chart-data')
def weight_chart_data():
    """Get weight data for charts"""
    
    days = int(request.args.get('days', 30))
    start_date = date.today() - timedelta(days=days)
    
    entries = WeightEntry.query.filter(
        WeightEntry.date >= start_date
    ).order_by(WeightEntry.date).all()
    
    data = {
        'labels': [e.date.strftime('%m/%d') for e in entries],
        'weights': [e.weight for e in entries],
        'soda_days': [1 if e.had_soda else 0 for e in entries],
        'exercise_days': [1 if e.exercised else 0 for e in entries],
        'water': [e.water_intake for e in entries]
    }
    
    return jsonify(data)


@health_bp.route('/weight/analytics')
def weight_analytics():
    """Advanced analytics and insights"""
    
    # Get all data for analysis
    entries = WeightEntry.query.order_by(WeightEntry.date.desc()).limit(90).all()
    failures = WeightFailure.query.order_by(WeightFailure.date.desc()).limit(100).all()
    
    # Pattern analysis
    patterns = WeightFailure.get_patterns(days=30)
    
    # Weekly averages
    weekly_stats = []
    for i in range(0, min(84, len(entries)), 7):
        week_entries = entries[i:i+7]
        if week_entries:
            weekly_stats.append({
                'week': week_entries[0].date.strftime('%m/%d'),
                'avg_weight': sum(e.weight for e in week_entries) / len(week_entries),
                'failures': sum(e.failure_count for e in week_entries),
                'exercise_days': sum(1 for e in week_entries if e.exercised)
            })
    
    # Correlation analysis
    correlations = analyze_correlations(entries)
    
    # AI insights
    insights = generate_ai_insights(entries, failures, patterns)
    
    return render_template(
        'health/analytics.html',
        patterns=patterns,
        weekly_stats=weekly_stats,
        correlations=correlations,
        insights=insights,
        active='weight'
    )


def analyze_correlations(entries):
    """Analyze correlations between behaviors and weight change"""
    
    correlations = {
        'soda_impact': 0,
        'exercise_impact': 0,
        'water_impact': 0,
        'weekend_impact': 0
    }
    
    if len(entries) < 2:
        return correlations
    
    # Calculate average weight change for different conditions
    soda_changes = []
    no_soda_changes = []
    exercise_changes = []
    no_exercise_changes = []
    
    for i in range(len(entries) - 1):
        change = entries[i].weight - entries[i + 1].weight
        
        if entries[i].had_soda:
            soda_changes.append(change)
        else:
            no_soda_changes.append(change)
        
        if entries[i].exercised:
            exercise_changes.append(change)
        else:
            no_exercise_changes.append(change)
    
    # Calculate impacts
    if soda_changes and no_soda_changes:
        correlations['soda_impact'] = sum(soda_changes) / len(soda_changes) - sum(no_soda_changes) / len(no_soda_changes)
    
    if exercise_changes and no_exercise_changes:
        correlations['exercise_impact'] = sum(exercise_changes) / len(exercise_changes) - sum(no_exercise_changes) / len(no_exercise_changes)
    
    return correlations


def generate_ai_insights(entries, failures, patterns):
    """Generate AI-powered insights and recommendations"""
    
    insights = []
    
    # Analyze failure patterns
    if patterns['total'] > 0:
        if patterns.get('worst_time') == 'evening':
            insights.append({
                'type': 'pattern',
                'title': 'Evening Weakness Detected',
                'message': 'You fail most often in the evening. Plan your dinner better and go to bed earlier.',
                'severity': 'warning'
            })
        
        if patterns.get('worst_trigger') == 'stress':
            insights.append({
                'type': 'trigger',
                'title': 'Stress Eating Pattern',
                'message': 'Stress is your #1 trigger. Find a therapist or take up boxing. Stop eating your feelings.',
                'severity': 'danger'
            })
    
    # Analyze weight trends
    if entries:
        recent_trend = sum(e.weight for e in entries[:7]) / min(7, len(entries))
        older_trend = sum(e.weight for e in entries[7:14]) / min(7, len(entries[7:14])) if len(entries) > 7 else recent_trend
        
        if recent_trend > older_trend:
            insights.append({
                'type': 'trend',
                'title': 'Wrong Direction!',
                'message': f'Your weight is trending UP by {recent_trend - older_trend:.1f} lbs/week. Turn this around NOW.',
                'severity': 'danger'
            })
    
    # Analyze streaks
    goal = WeightGoal.get_active()
    if goal:
        if goal.days_no_soda_streak == 0 and goal.best_no_soda_streak > 7:
            insights.append({
                'type': 'streak',
                'title': 'Streak Broken!',
                'message': f'You broke a {goal.best_no_soda_streak}-day no-soda streak. Pathetic. Start over.',
                'severity': 'danger'
            })
    
    return insights


# ==================== GOAL MANAGEMENT ====================

@health_bp.route('/weight/goals', methods=['GET', 'POST'])
def manage_goals():
    """Set and manage weight goals"""
    
    if request.method == 'POST':
        goal = WeightGoal.get_active()
        
        if not goal:
            # Get current weight
            latest = WeightEntry.query.order_by(WeightEntry.date.desc()).first()
            goal = WeightGoal(
                start_weight=latest.weight if latest else 200,
                current_weight=latest.weight if latest else 200
            )
        
        goal.goal_weight = float(request.form.get('goal_weight'))
        goal.target_date = datetime.strptime(request.form.get('target_date'), '%Y-%m-%d').date() if request.form.get('target_date') else None
        goal.weekly_loss_target = float(request.form.get('weekly_target', 2))
        
        db.session.add(goal)
        db.session.commit()
        
        # Calculate requirements
        if goal.days_remaining and goal.days_remaining > 0:
            daily_required = (goal.current_weight - goal.goal_weight) / goal.days_remaining
            flash(f"Goal set! You need to lose {daily_required:.2f} lbs per day. Better get moving!", "warning")
        else:
            flash("Goal updated!", "success")
        
        return redirect(url_for('health.weight_index'))
    
    goal = WeightGoal.get_active()
    return render_template(
        'health/goals.html',
        goal=goal,
        active='weight'
    )


# ==================== SETTINGS ====================

@health_bp.route('/weight/settings', methods=['GET', 'POST'])
def health_settings():
    """Health module settings"""
    
    if request.method == 'POST':
        settings = [
            'harassment_level',
            'morning_weigh_time',
            'soda_limit',
            'water_goal',
            'exercise_minimum',
            'weight_goal',
            'weekly_loss_goal',
            'ai_harassment'
        ]
        
        for setting in settings:
            if setting in request.form:
                HealthConfig.set(setting, request.form.get(setting))
        
        flash("Settings updated. The drill sergeant has been recalibrated.", "success")
        return redirect(url_for('health.health_settings'))
    
    # Get current settings
    settings = {
        'harassment_level': HealthConfig.get('harassment_level', 'BRUTAL'),
        'morning_weigh_time': HealthConfig.get('morning_weigh_time', '10:00'),
        'soda_limit': HealthConfig.get('soda_limit', '0'),
        'water_goal': HealthConfig.get('water_goal', '8'),
        'exercise_minimum': HealthConfig.get('exercise_minimum', '30'),
        'weight_goal': HealthConfig.get('weight_goal', '180'),
        'weekly_loss_goal': HealthConfig.get('weekly_loss_goal', '2'),
        'ai_harassment': HealthConfig.get('ai_harassment', 'true')
    }
    
    return render_template(
        'health/settings.html',
        settings=settings,
        active='weight'
    )


# ==================== INTEGRATION WITH DAILY PLANNER ====================

@health_bp.route('/weight/daily-check')
def daily_weight_check():
    """Check weight status for daily planner integration"""
    
    today_entry = WeightEntry.get_today()
    
    status = {
        'logged': today_entry.time_logged is not None,
        'weight': today_entry.weight,
        'failures': today_entry.failure_count,
        'message': None
    }
    
    # Generate message for daily planner
    if not status['logged'] and datetime.now().hour > 10:
        status['message'] = "Haven't weighed yourself yet. Scared?"
    elif today_entry.had_soda:
        status['message'] = f"Had {today_entry.soda_count} soda(s) today. Weak."
    elif today_entry.failure_count > 2:
        status['message'] = f"{today_entry.failure_count} failures today. Pathetic."
    
    return jsonify(status)