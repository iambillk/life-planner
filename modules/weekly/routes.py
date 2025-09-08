# modules/weekly/routes.py
from flask import redirect, url_for
from . import weekly_bp

@weekly_bp.route('/')
def index():
   """Redirect to daily calendar view"""
   return redirect(url_for('daily.calendar_view'))

@weekly_bp.route('/monthly')
def monthly():
   """Redirect to daily calendar monthly view"""
   return redirect(url_for('daily.calendar_view', view='month'))