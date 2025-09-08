# modules/financial/routes.py
"""
Financial Tracking Routes
All routes for spending tracking and analytics
"""

from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from datetime import datetime, date, timedelta
from sqlalchemy import func, extract
from collections import defaultdict
import os
import calendar

from models.base import db
from models.financial import Transaction, SpendingCategory, MerchantAlias
from modules.equipment.utils import allowed_file, save_uploaded_photo

from . import financial_bp
from .constants import PREDEFINED_CATEGORIES, CARDS, MERCHANT_PATTERNS


# ==================== INITIALIZATION ====================

def init_categories():
    """Initialize predefined categories if they don't exist"""
    for cat_data in PREDEFINED_CATEGORIES:
        existing = SpendingCategory.query.filter_by(name=cat_data['name']).first()
        if not existing:
            category = SpendingCategory(
                name=cat_data['name'],
                icon=cat_data['icon'],
                color=cat_data['color'],
                is_custom=False
            )
            db.session.add(category)
    db.session.commit()


# ==================== DASHBOARD ====================

@financial_bp.route('/')
def dashboard():
    """Main dashboard with recent transactions and monthly summary"""
    # Initialize categories on first load
    if SpendingCategory.query.count() == 0:
        init_categories()
    
    # Get current month bounds
    today = date.today()
    month_start = date(today.year, today.month, 1)
    if today.month == 12:
        month_end = date(today.year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(today.year, today.month + 1, 1) - timedelta(days=1)
    
    # Get this month's transactions
    month_transactions = Transaction.query.filter(
        Transaction.date >= month_start,
        Transaction.date <= month_end
    ).order_by(Transaction.date.desc(), Transaction.id.desc()).all()
    
    # Calculate monthly total
    monthly_total = sum(t.amount for t in month_transactions)
    
    # Get recent transactions (last 20)
    recent_transactions = Transaction.query.order_by(
        Transaction.date.desc(),
        Transaction.id.desc()
    ).limit(20).all()
    
    # Get monthly spending by category
    category_spending = db.session.query(
        SpendingCategory.name,
        SpendingCategory.icon,
        SpendingCategory.color,
        func.sum(Transaction.amount).label('total')
    ).join(
        Transaction
    ).filter(
        Transaction.date >= month_start,
        Transaction.date <= month_end
    ).group_by(
        SpendingCategory.id
    ).order_by(
        func.sum(Transaction.amount).desc()
    ).all()
    
    # Daily average for this month
    days_in_month = (today - month_start).days + 1
    daily_average = monthly_total / days_in_month if days_in_month > 0 else 0
    
    return render_template(
        'financial/dashboard.html',
        recent_transactions=recent_transactions,
        monthly_total=monthly_total,
        month_transactions=month_transactions,
        category_spending=category_spending,
        daily_average=daily_average,
        current_month=today.strftime('%B %Y'),
        active='financial'
    )


# ==================== ADD TRANSACTION ====================

@financial_bp.route('/add', methods=['GET', 'POST'])
def add_transaction():
    """Add a new transaction"""
    if request.method == 'POST':
        # Get form data
        date_str = request.form.get('date')
        amount = float(request.form.get('amount', 0))
        merchant = request.form.get('merchant', '').strip()
        category_id = request.form.get('category_id')
        card = request.form.get('card', 'Amex')
        notes = request.form.get('notes', '').strip()
        
        # Handle new category
        if category_id == 'new':
            new_category_name = request.form.get('new_category', '').strip()
            if new_category_name:
                # Check if exists
                category = SpendingCategory.query.filter_by(name=new_category_name).first()
                if not category:
                    category = SpendingCategory(
                        name=new_category_name,
                        is_custom=True,
                        icon='💰',
                        color='#6ea8ff'
                    )
                    db.session.add(category)
                    db.session.commit()
                category_id = category.id
            else:
                flash('Please enter a category name', 'error')
                return redirect(url_for('financial.add_transaction'))
        
        # Create transaction
        transaction = Transaction(
            date=datetime.strptime(date_str, '%Y-%m-%d').date(),
            amount=amount,
            merchant=merchant,
            category_id=int(category_id) if category_id and category_id != 'new' else None,
            card=card,
            notes=notes
        )
        
        # Handle receipt photo
        if 'receipt_photo' in request.files:
            file = request.files['receipt_photo']
            if file and allowed_file(file.filename):
                filename = save_uploaded_photo(file, 'receipts', f"{merchant}_{date_str}")
                transaction.receipt_photo = filename
        
        # Update category usage count
        if transaction.category_id:
            category = SpendingCategory.query.get(transaction.category_id)
            category.usage_count += 1
        
        db.session.add(transaction)
        db.session.commit()
        
        flash(f'Transaction added: ${amount:.2f} at {merchant}', 'success')
        
        # Check if adding multiple
        if request.form.get('add_another'):
            return redirect(url_for('financial.add_transaction', 
                                  last_category=category_id,
                                  last_card=card))
        
        return redirect(url_for('financial.dashboard'))
    
    # GET request
    categories = SpendingCategory.query.order_by(
        SpendingCategory.is_custom,
        SpendingCategory.usage_count.desc(),
        SpendingCategory.name
    ).all()
    
    # Get last used values for convenience
    last_category = request.args.get('last_category')
    last_card = request.args.get('last_card', 'Amex')
    
    return render_template(
        'financial/add_transaction.html',
        categories=categories,
        cards=CARDS,
        today=date.today(),
        last_category=last_category,
        last_card=last_card,
        active='financial'
    )


# ==================== EDIT TRANSACTION ====================

@financial_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_transaction(id):
    """Edit an existing transaction"""
    transaction = Transaction.query.get_or_404(id)
    
    if request.method == 'POST':
        transaction.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
        transaction.amount = float(request.form.get('amount', 0))
        transaction.merchant = request.form.get('merchant', '').strip()
        transaction.category_id = int(request.form.get('category_id')) if request.form.get('category_id') else None
        transaction.card = request.form.get('card', 'Amex')
        transaction.notes = request.form.get('notes', '').strip()
        
        # Handle receipt photo
        if 'receipt_photo' in request.files:
            file = request.files['receipt_photo']
            if file and allowed_file(file.filename):
                # Delete old photo if exists
                if transaction.receipt_photo:
                    old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'receipts', transaction.receipt_photo)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                filename = save_uploaded_photo(file, 'receipts', f"{transaction.merchant}_{transaction.date}")
                transaction.receipt_photo = filename
        
        db.session.commit()
        flash('Transaction updated', 'success')
        return redirect(url_for('financial.dashboard'))
    
    categories = SpendingCategory.query.order_by(
        SpendingCategory.is_custom,
        SpendingCategory.name
    ).all()
    
    return render_template(
        'financial/edit_transaction.html',
        transaction=transaction,
        categories=categories,
        cards=CARDS,
        active='financial'
    )


# ==================== DELETE TRANSACTION ====================

@financial_bp.route('/delete/<int:id>', methods=['POST'])
def delete_transaction(id):
    """Delete a transaction"""
    transaction = Transaction.query.get_or_404(id)
    
    # Delete receipt photo if exists
    if transaction.receipt_photo:
        photo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'receipts', transaction.receipt_photo)
        if os.path.exists(photo_path):
            os.remove(photo_path)
    
    # Update category usage count
    if transaction.category_id:
        category = SpendingCategory.query.get(transaction.category_id)
        if category and category.usage_count > 0:
            category.usage_count -= 1
    
    db.session.delete(transaction)
    db.session.commit()
    
    flash('Transaction deleted', 'success')
    return redirect(url_for('financial.dashboard'))


# ==================== ANALYTICS ====================

@financial_bp.route('/analytics')
def analytics():
    """Spending analytics and insights"""
    # Date range selector (default to last 6 months)
    end_date = date.today()
    start_date = request.args.get('start_date')
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    else:
        start_date = end_date - timedelta(days=180)
    
    # Get all transactions in range
    transactions = Transaction.query.filter(
        Transaction.date >= start_date,
        Transaction.date <= end_date
    ).order_by(Transaction.date).all()
    
    # Monthly spending trend
    monthly_spending = defaultdict(float)
    monthly_transactions = defaultdict(int)
    for t in transactions:
        month_key = t.date.strftime('%Y-%m')
        monthly_spending[month_key] += t.amount
        monthly_transactions[month_key] += 1
    
    # Sort by month
    monthly_data = []
    for month_key in sorted(monthly_spending.keys()):
        year, month = month_key.split('-')
        month_name = calendar.month_name[int(month)][:3] + ' ' + year[2:]
        monthly_data.append({
            'month': month_name,
            'total': monthly_spending[month_key],
            'count': monthly_transactions[month_key],
            'average': monthly_spending[month_key] / monthly_transactions[month_key]
        })
    
    # Category breakdown
    category_totals = defaultdict(lambda: {'total': 0, 'count': 0, 'icon': '💰', 'color': '#6ea8ff'})
    for t in transactions:
        if t.category:
            category_totals[t.category.name]['total'] += t.amount
            category_totals[t.category.name]['count'] += 1
            category_totals[t.category.name]['icon'] = t.category.icon
            category_totals[t.category.name]['color'] = t.category.color
    
    # Sort categories by total
    category_data = []
    total_spending = sum(t.amount for t in transactions)
    for cat_name, cat_info in sorted(category_totals.items(), key=lambda x: x[1]['total'], reverse=True):
        percentage = (cat_info['total'] / total_spending * 100) if total_spending > 0 else 0
        category_data.append({
            'name': cat_name,
            'total': cat_info['total'],
            'count': cat_info['count'],
            'average': cat_info['total'] / cat_info['count'],
            'percentage': percentage,
            'icon': cat_info['icon'],
            'color': cat_info['color']
        })
    
    # Top merchants
    merchant_totals = defaultdict(lambda: {'total': 0, 'count': 0})
    for t in transactions:
        merchant_totals[t.merchant]['total'] += t.amount
        merchant_totals[t.merchant]['count'] += 1
    
    top_merchants = sorted(
        merchant_totals.items(),
        key=lambda x: x[1]['total'],
        reverse=True
    )[:15]
    
    # Card usage comparison
    card_totals = defaultdict(lambda: {'total': 0, 'count': 0})
    for t in transactions:
        card_totals[t.card]['total'] += t.amount
        card_totals[t.card]['count'] += 1
    
    # Statistics
    stats = {
        'total_spent': total_spending,
        'transaction_count': len(transactions),
        'average_transaction': total_spending / len(transactions) if transactions else 0,
        'largest_transaction': max(transactions, key=lambda t: t.amount) if transactions else None,
        'most_frequent_category': max(category_totals.items(), key=lambda x: x[1]['count'])[0] if category_totals else None,
        'days_tracked': (end_date - start_date).days + 1
    }
    
    return render_template(
        'financial/analytics.html',
        monthly_data=monthly_data,
        category_data=category_data,
        top_merchants=top_merchants,
        card_totals=dict(card_totals),
        stats=stats,
        start_date=start_date,
        end_date=end_date,
        active='financial'
    )


# ==================== SEARCH ====================

@financial_bp.route('/search')
def search():
    """Search transactions"""
    query = request.args.get('q', '').strip()
    category_filter = request.args.get('category')
    card_filter = request.args.get('card')
    
    transactions = Transaction.query
    
    if query:
        transactions = transactions.filter(
            db.or_(
                Transaction.merchant.ilike(f'%{query}%'),
                Transaction.notes.ilike(f'%{query}%')
            )
        )
    
    if category_filter:
        transactions = transactions.filter_by(category_id=category_filter)
    
    if card_filter:
        transactions = transactions.filter_by(card=card_filter)
    
    transactions = transactions.order_by(
        Transaction.date.desc(),
        Transaction.id.desc()
    ).all()
    
    categories = SpendingCategory.query.order_by(SpendingCategory.name).all()
    
    return render_template(
        'financial/search.html',
        transactions=transactions,
        categories=categories,
        cards=CARDS,
        query=query,
        category_filter=category_filter,
        card_filter=card_filter,
        active='financial'
    )


# ==================== API ENDPOINTS ====================

@financial_bp.route('/api/suggest-category', methods=['POST'])
def suggest_category():
    """API endpoint to suggest category based on merchant"""
    merchant = request.json.get('merchant', '').lower()
    
    # Check merchant aliases first
    alias = MerchantAlias.query.filter_by(alias=merchant).first()
    if alias and alias.default_category_id:
        category = SpendingCategory.query.get(alias.default_category_id)
        return jsonify({'category_id': category.id, 'category_name': category.name})
    
    # Check patterns
    for cat_name, patterns in MERCHANT_PATTERNS.items():
        for pattern in patterns:
            if pattern in merchant:
                category = SpendingCategory.query.filter_by(name=cat_name).first()
                if category:
                    return jsonify({'category_id': category.id, 'category_name': category.name})
    
    return jsonify({'category_id': None})