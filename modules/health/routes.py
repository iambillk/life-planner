from flask import render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, timedelta
from . import health_bp
from models import db, WeightEntry

@health_bp.route('/weight')
def weight_index():
    """Weight tracking main page"""
    entries = WeightEntry.query.order_by(WeightEntry.date.desc()).limit(30).all()
    
    # Calculate stats
    stats = {}
    if entries:
        stats['current'] = entries[0].weight
        if len(entries) > 1:
            stats['change_week'] = entries[0].weight - entries[min(7, len(entries)-1)].weight
            stats['change_month'] = entries[0].weight - entries[-1].weight
            stats['average'] = sum(e.weight for e in entries) / len(entries)
    
    return render_template('weight.html', entries=entries, stats=stats, active='weight')

@health_bp.route('/weight/add', methods=['POST'])
def add_weight():
    """Add weight entry"""
    entry = WeightEntry(
        weight=float(request.form.get('weight')),
        date=datetime.strptime(request.form.get('date'), '%Y-%m-%d').date() if request.form.get('date') else datetime.utcnow().date(),
        notes=request.form.get('notes')
    )
    db.session.add(entry)
    db.session.commit()
    flash('Weight entry added!', 'success')
    return redirect(url_for('health.weight_index'))

@health_bp.route('/weight/chart-data')
def weight_chart_data():
    """Get weight data for chart"""
    days = int(request.args.get('days', 30))
    start_date = datetime.now() - timedelta(days=days)
    
    entries = WeightEntry.query.filter(
        WeightEntry.date >= start_date
    ).order_by(WeightEntry.date).all()
    
    data = {
        'labels': [e.date.strftime('%m/%d') for e in entries],
        'weights': [e.weight for e in entries]
    }
    
    return jsonify(data)

@health_bp.route('/weight/<int:id>/delete', methods=['POST'])
def delete_weight(id):
    """Delete weight entry"""
    entry = WeightEntry.query.get_or_404(id)
    db.session.delete(entry)
    db.session.commit()
    flash('Weight entry deleted!', 'success')
    return redirect(url_for('health.weight_index'))