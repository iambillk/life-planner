# modules/financial/routes.py
"""
Financial Tracking Routes
All routes for spending tracking and analytics
"""

from flask import render_template, request, redirect, url_for, flash, jsonify, current_app, session
from datetime import datetime, date, timedelta
from sqlalchemy import func, extract
from collections import defaultdict
import os
import calendar
import csv
import io
import re

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
    
    # Get monthly spending by category - FIXED: Added count field
    category_spending = db.session.query(
        SpendingCategory.name,
        SpendingCategory.icon,
        SpendingCategory.color,
        func.sum(Transaction.amount).label('total'),
        func.count(Transaction.id).label('count')
    ).join(
        Transaction
    ).filter(
        Transaction.date >= month_start,
        Transaction.date <= month_end
    ).group_by(
        SpendingCategory.id,
        SpendingCategory.name,
        SpendingCategory.icon,
        SpendingCategory.color
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
        # Create transaction
        transaction = Transaction(
            date=datetime.strptime(request.form.get('date'), '%Y-%m-%d').date(),
            amount=float(request.form.get('amount', 0)),
            merchant=request.form.get('merchant', '').strip(),
            category_id=int(request.form.get('category_id')) if request.form.get('category_id') else None,
            card=request.form.get('card', 'Amex'),
            notes=request.form.get('notes', '').strip()
        )
        
        # Handle receipt photo
        if 'receipt_photo' in request.files:
            file = request.files['receipt_photo']
            if file and allowed_file(file.filename):
                filename = save_uploaded_photo(file, 'receipts', f"{transaction.merchant}_{transaction.date}")
                transaction.receipt_photo = filename
        
        # Update category usage count
        if transaction.category_id:
            category = SpendingCategory.query.get(transaction.category_id)
            if category:
                category.usage_count += 1
        
        # Save transaction
        db.session.add(transaction)
        db.session.commit()
        
        # Create merchant alias for future auto-categorization
        if transaction.category_id:
            create_merchant_alias_if_needed(transaction.merchant, transaction.category_id)
            db.session.commit()
        
        flash(f'Transaction added: ${transaction.amount:.2f} at {transaction.merchant}', 'success')
        
        # Store last used values
        category_id = transaction.category_id
        card = transaction.card
        
        # Check if adding multiple
        if request.form.get('add_another'):
            return redirect(url_for('financial.add_transaction', 
                                  last_category=category_id,
                                  last_card=card))
        
        return redirect(url_for('financial.dashboard'))
    
    # GET request - fetch merchants for dropdown
    categories = SpendingCategory.query.order_by(
        SpendingCategory.is_custom,
        SpendingCategory.usage_count.desc(),
        SpendingCategory.name
    ).all()
    
    # Get unique merchants from database
    merchants_query = db.session.query(Transaction.merchant)\
        .distinct()\
        .order_by(Transaction.merchant)\
        .all()
    merchants = [m[0] for m in merchants_query if m[0]]
    
    # Get last used values for convenience
    last_category = request.args.get('last_category')
    last_card = request.args.get('last_card', 'Amex')
    
    return render_template(
        'financial/add_transaction.html',
        categories=categories,
        merchants=merchants,
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
        # Check if user wants to update all matching merchants
        update_all_matching = request.form.get('update_all_matching') == 'on'
        old_category_id = transaction.category_id
        
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
        
        # If category changed and user wants to update all matching
        if update_all_matching and old_category_id != transaction.category_id:
            # Update all other transactions with the same merchant
            matching = Transaction.query.filter(
                Transaction.merchant == transaction.merchant,
                Transaction.id != transaction.id  # Don't update the current one twice
            ).all()
            
            for t in matching:
                t.category_id = transaction.category_id
            
            # Create/update merchant alias
            if transaction.category_id:
                create_merchant_alias_if_needed(transaction.merchant, transaction.category_id)
            
            flash(f'Updated {len(matching) + 1} transactions from "{transaction.merchant}"', 'success')
        else:
            flash('Transaction updated', 'success')
        
        db.session.commit()
        return redirect(url_for('financial.dashboard'))
    
    categories = SpendingCategory.query.order_by(
        SpendingCategory.is_custom,
        SpendingCategory.name
    ).all()
    
    # Count how many other transactions have the same merchant
    same_merchant_count = Transaction.query.filter(
        Transaction.merchant == transaction.merchant,
        Transaction.id != transaction.id
    ).count()
    
    return render_template(
        'financial/edit_transaction.html',
        transaction=transaction,
        categories=categories,
        cards=CARDS,
        same_merchant_count=same_merchant_count,
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
    end_date_param = request.args.get('end_date')
    card_filter = request.args.get('card', 'all')  # GET THE CARD FILTER
    
    # Handle end_date from form
    if end_date_param:
        end_date = datetime.strptime(end_date_param, '%Y-%m-%d').date()
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    else:
        start_date = end_date - timedelta(days=180)
    
    # Get all transactions in range WITH CARD FILTER
    transactions_query = Transaction.query.filter(
        Transaction.date >= start_date,
        Transaction.date <= end_date
    )
    
    # Apply card filter if not 'all'
    if card_filter and card_filter != 'all':
        transactions_query = transactions_query.filter(Transaction.card == card_filter)
    
    transactions = transactions_query.order_by(Transaction.date).all()
    
    # Calculate total RIGHT AFTER getting FILTERED transactions
    total_spending = sum(t.amount for t in transactions)
    
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
            'count': monthly_transactions[month_key]
        })
    
    # Category breakdown
    category_totals = defaultdict(lambda: {'total': 0, 'count': 0, 'merchants': set()})
    for t in transactions:
        if t.category:
            category_totals[t.category.name]['total'] += t.amount
            category_totals[t.category.name]['count'] += 1
            category_totals[t.category.name]['icon'] = t.category.icon
            category_totals[t.category.name]['color'] = t.category.color
            if t.merchant:
                category_totals[t.category.name]['merchants'].add(t.merchant)
    
    # Prepare category data for display
    category_data = []
    for name, data in category_totals.items():
        category_data.append({
            'name': name,
            'total': data['total'],
            'count': data['count'],
            'percentage': (data['total'] / total_spending * 100) if total_spending > 0 else 0,
            'icon': data.get('icon', '📁'),
            'color': data.get('color', '#6ea8ff'),
            'unique_merchants': len(data['merchants'])
        })
    
    # Sort categories by total spent
    category_data.sort(key=lambda x: x['total'], reverse=True)
    
    # Weekday pattern analysis - ADD THIS BACK
    weekday_totals = defaultdict(lambda: {'total': 0, 'count': 0})
    for t in transactions:
        weekday = t.date.strftime('%A')
        weekday_totals[weekday]['total'] += t.amount
        weekday_totals[weekday]['count'] += 1
    
    # Prepare weekday data
    weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    weekday_data = []
    for day in weekday_order:
        if day in weekday_totals:
            weekday_data.append({
                'day': day[:3],
                'total': weekday_totals[day]['total'],
                'count': weekday_totals[day]['count'],
                'average': weekday_totals[day]['total'] / weekday_totals[day]['count'] if weekday_totals[day]['count'] > 0 else 0
            })
    
    # Top merchants
    merchant_totals = defaultdict(lambda: {
        'total': 0, 
        'count': 0, 
        'category': None,
        'first_date': None,
        'last_date': None
    })
    
    for t in transactions:
        if t.merchant:
            merchant_totals[t.merchant]['total'] += t.amount
            merchant_totals[t.merchant]['count'] += 1
            merchant_totals[t.merchant]['category'] = t.category.name if t.category else None
            
            # Track first and last transaction dates
            if not merchant_totals[t.merchant]['first_date'] or t.date < merchant_totals[t.merchant]['first_date']:
                merchant_totals[t.merchant]['first_date'] = t.date
            if not merchant_totals[t.merchant]['last_date'] or t.date > merchant_totals[t.merchant]['last_date']:
                merchant_totals[t.merchant]['last_date'] = t.date
    
    # Get top merchants
    top_merchants = []
    for merchant, data in sorted(merchant_totals.items(), key=lambda x: x[1]['total'], reverse=True)[:10]:
        # Calculate frequency
        if data['first_date'] and data['last_date'] and data['count'] > 1:
            days_between = (data['last_date'] - data['first_date']).days + 1
            if days_between > 0:
                frequency = f"Every {days_between // data['count']} days" if data['count'] > 1 else "Once"
            else:
                frequency = "Once"
        else:
            frequency = "Once"
        
        top_merchants.append({
            'name': str(merchant) if merchant else 'Unknown',
            'total': data['total'],
            'count': data['count'],
            'average': data['total'] / data['count'] if data['count'] > 0 else 0,
            'category': data['category'] or 'Uncategorized',
            'frequency': frequency
        })
    
    # Card usage comparison
    card_totals = defaultdict(lambda: {'total': 0, 'count': 0})
    for t in transactions:
        card_totals[t.card]['total'] += t.amount
        card_totals[t.card]['count'] += 1
    
    # Statistics - FIX: ADD ALL FIELDS THE TEMPLATE EXPECTS
    stats = {
        'total_spent': total_spending,
        'transaction_count': len(transactions),
        'average_transaction': total_spending / len(transactions) if transactions else 0,
        'largest_transaction': max(transactions, key=lambda t: t.amount) if transactions else None,
        'categories_used': len(category_totals),  # ADD THIS
        'unique_merchants': len(merchant_totals),  # ADD THIS
        'days_tracked': (end_date - start_date).days + 1
    }
    
    # Generate insights - ADD THIS ENTIRE SECTION
    insights = []
    
    # Spending trend insight
    if len(monthly_data) > 1:
        recent_month = monthly_data[-1]['total'] if monthly_data else 0
        previous_month = monthly_data[-2]['total'] if len(monthly_data) > 1 else 0
        if previous_month > 0:
            change = ((recent_month - previous_month) / previous_month) * 100
            if change > 10:
                insights.append(f"📈 Spending increased {change:.0f}% from last month")
            elif change < -10:
                insights.append(f"📉 Spending decreased {abs(change):.0f}% from last month")
    
    # Top category insight
    if category_data:
        top_cat = category_data[0]
        insights.append(f"{top_cat['icon']} {top_cat['name']} is your biggest expense ({top_cat['percentage']:.0f}% of total)")
    
    # Frequency insight
    if stats['transaction_count'] > 0:
        avg_days_between = stats['days_tracked'] / stats['transaction_count']
        insights.append(f"📅 You make a purchase every {avg_days_between:.1f} days on average")
    
    # High spending day insight
    if weekday_data:
        highest_day = max(weekday_data, key=lambda x: x['total'])
        insights.append(f"💸 {highest_day['day']}s tend to be your highest spending day")
    
    # RETURN WITH ALL REQUIRED VARIABLES
    return render_template(
        'financial/analytics.html',
        monthly_data=monthly_data,
        category_data=category_data,
        weekday_data=weekday_data,  # ADD THIS
        top_merchants=top_merchants,
        card_totals=dict(card_totals),
        stats=stats,
        insights=insights,  # ADD THIS
        start_date=start_date,
        end_date=end_date,
        card_filter=card_filter,  # ADD THIS
        cards=CARDS,  # ADD THIS
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


# ==================== SETTINGS ====================

@financial_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    """Manage categories and merchant aliases"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_category':
            # Add new custom category
            name = request.form.get('name', '').strip()
            icon = request.form.get('icon', '💰')
            color = request.form.get('color', '#6ea8ff')
            
            if name:
                # Check if category exists
                existing = SpendingCategory.query.filter_by(name=name).first()
                if existing:
                    flash(f'Category "{name}" already exists', 'error')
                else:
                    category = SpendingCategory(
                        name=name,
                        icon=icon,
                        color=color,
                        is_custom=True
                    )
                    db.session.add(category)
                    db.session.commit()
                    flash(f'Category "{name}" added', 'success')
                    
        elif action == 'delete_category':
            # Delete category (only if custom and no transactions)
            category_id = request.form.get('category_id')
            if category_id:
                category = SpendingCategory.query.get(int(category_id))
                if category:
                    if category.is_custom:
                        # Check if any transactions use this category
                        transaction_count = Transaction.query.filter_by(category_id=category.id).count()
                        if transaction_count > 0:
                            flash(f'Cannot delete "{category.name}" - {transaction_count} transactions use this category', 'error')
                        else:
                            db.session.delete(category)
                            db.session.commit()
                            flash(f'Category "{category.name}" deleted', 'success')
                    else:
                        flash('Cannot delete predefined categories', 'error')
                        
        elif action == 'add_merchant_alias':
            # Add merchant alias for auto-categorization
            merchant = request.form.get('merchant', '').strip()
            canonical = request.form.get('canonical', '').strip() or merchant
            category_id = request.form.get('default_category')
            
            if merchant and category_id:
                normalized = normalize_merchant_name(merchant)
                # Check if alias exists for normalized name
                existing = MerchantAlias.query.filter_by(normalized_name=normalized).first()
                if existing:
                    # Update existing
                    existing.canonical_name = canonical
                    existing.default_category_id = int(category_id)
                    flash(f'Merchant alias "{merchant}" updated', 'success')
                else:
                    # Create new
                    alias = MerchantAlias(
                        alias=merchant,
                        normalized_name=normalized,
                        canonical_name=canonical,
                        default_category_id=int(category_id)
                    )
                    db.session.add(alias)
                    flash(f'Merchant alias "{merchant}" added', 'success')
                db.session.commit()
                
        return redirect(url_for('financial.settings'))
    
    # GET request - show settings page
    categories = SpendingCategory.query.order_by(
        SpendingCategory.is_custom,
        SpendingCategory.name
    ).all()
    
    # Get category usage stats
    category_stats = db.session.query(
        SpendingCategory.id,
        func.count(Transaction.id).label('transaction_count'),
        func.sum(Transaction.amount).label('total_amount')
    ).outerjoin(
        Transaction
    ).group_by(
        SpendingCategory.id
    ).all()
    
    # Convert to dict for easy lookup
    stats_dict = {
        stat[0]: {
            'count': stat[1] or 0,
            'total': stat[2] or 0
        } for stat in category_stats
    }
    
    # Get merchant aliases
    aliases = MerchantAlias.query.order_by(MerchantAlias.alias).all()
    
    return render_template(
        'financial/settings.html',
        categories=categories,
        category_stats=stats_dict,
        aliases=aliases,
        active='financial'
    )


# ==================== API ENDPOINTS ====================

@financial_bp.route('/api/suggest-category', methods=['POST'])
def suggest_category():
    """API endpoint to suggest category based on merchant"""
    merchant = request.json.get('merchant', '').lower()
    
    if not merchant:
        return jsonify({'category_id': None})
    
    # Normalize the merchant name for matching
    normalized = normalize_merchant_name(merchant)
    
    # Check merchant aliases using normalized name
    alias = MerchantAlias.query.filter_by(normalized_name=normalized).first()
    if alias and alias.default_category_id:
        category = SpendingCategory.query.get(alias.default_category_id)
        return jsonify({'category_id': category.id, 'category_name': category.name})
    
    # Check patterns on normalized name
    normalized_lower = normalized.lower()
    for cat_name, patterns in MERCHANT_PATTERNS.items():
        for pattern in patterns:
            if pattern in normalized_lower:
                category = SpendingCategory.query.filter_by(name=cat_name).first()
                if category:
                    return jsonify({'category_id': category.id, 'category_name': category.name})
    
    return jsonify({'category_id': None})


# ==================== AMEX CSV IMPORT ====================

@financial_bp.route('/import', methods=['GET', 'POST'])
def import_amex():
    """Import transactions from American Express CSV"""
    if request.method == 'POST':
        # Check if file was uploaded
        if 'csv_file' not in request.files:
            flash('No file selected', 'error')
            return redirect(url_for('financial.import_amex'))
        
        file = request.files['csv_file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('financial.import_amex'))
        
        if not file.filename.lower().endswith('.csv'):
            flash('Please upload a CSV file', 'error')
            return redirect(url_for('financial.import_amex'))
        
        try:
            # Read CSV file
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_input = csv.DictReader(stream)
            
            # Parse and prepare transactions
            transactions_to_import = []
            skipped_transactions = []
            
            for row in csv_input:
                # Skip payment/credit transactions
                amount = float(row['Amount'])
                if amount < 0:
                    skipped_transactions.append({
                        'date': row['Date'],
                        'description': row['Description'],
                        'amount': amount,
                        'reason': 'Payment/Credit'
                    })
                    continue
                
                # Parse date (MM/DD/YYYY format)
                date_obj = datetime.strptime(row['Date'], '%m/%d/%Y').date()
                
                # Clean up merchant name
                merchant = row['Description'].strip()
                
                # Check for existing transaction (duplicate detection)
                existing = Transaction.query.filter_by(
                    date=date_obj,
                    amount=amount,
                    merchant=merchant,
                    card='Amex'
                ).first()
                
                if existing:
                    skipped_transactions.append({
                        'date': row['Date'],
                        'description': merchant,
                        'amount': amount,
                        'reason': 'Already imported'
                    })
                    continue
                
                # Map Amex category to our categories
                amex_category = row.get('Category', '')
                suggested_category = map_amex_category(amex_category, merchant)
                
                # Store transaction data
                transactions_to_import.append({
                    'date': date_obj,
                    'date_str': row['Date'],
                    'amount': amount,
                    'merchant': merchant[:100],
                    'suggested_category_id': suggested_category['id'],
                    'suggested_category_name': suggested_category['name']
                })
            
            # FIX: Store ALL transactions, not limited to 100
            session['amex_import_data'] = {
                'transactions': transactions_to_import,  # ALL transactions
                'skipped': skipped_transactions[:20],  # Show first 20 skipped for review
                'total_count': len(transactions_to_import),
                'total_amount': sum(t['amount'] for t in transactions_to_import),
                'skipped_count': len(skipped_transactions)
            }
            
            # Inform user about what will be imported
            flash(f'Found {len(transactions_to_import)} transactions to import (${sum(t["amount"] for t in transactions_to_import):,.2f} total)', 'success')
            
            if len(skipped_transactions) > 0:
                flash(f'Skipping {len(skipped_transactions)} payments/credits or duplicates', 'info')
            
            if len(transactions_to_import) > 100:
                flash(f'Note: Only first 100 shown for review, but ALL {len(transactions_to_import)} will be imported', 'info')
            
            return redirect(url_for('financial.review_import'))
            
        except Exception as e:
            flash(f'Error processing CSV file: {str(e)}', 'error')
            return redirect(url_for('financial.import_amex'))
    
    # GET request - show upload form
    return render_template('financial/import_amex.html', active='financial')

@financial_bp.route('/import/review', methods=['GET', 'POST'])
def review_import():
        """Review and confirm Amex transactions before importing"""
        import_data = session.get('amex_import_data')
        
        if not import_data:
            flash('No import data found. Please upload a CSV file first.', 'error')
            return redirect(url_for('financial.import_amex'))
        
        if request.method == 'POST':
            # Process confirmed import
            imported_count = 0
            errors = []
            
            # Import ALL transactions
            all_transactions = import_data['transactions']
            
            for idx, trans_data in enumerate(all_transactions):
                try:
                    # For displayed transactions (first 100), use form selections
                    # For non-displayed, use the suggested category from map_amex_category
                    if idx < 100:
                        category_id = request.form.get(f"category_{idx}")
                    else:
                        # Use the already-calculated suggested category
                        category_id = trans_data['suggested_category_id']
                    
                    # Create transaction
                    transaction = Transaction(
                        date=trans_data['date'],
                        amount=trans_data['amount'],
                        merchant=trans_data['merchant'],
                        category_id=int(category_id) if category_id and category_id != '' else None,
                        card='Amex',
                        notes=None
                    )
                    
                    # Update category usage count
                    if transaction.category_id:
                        category = SpendingCategory.query.get(transaction.category_id)
                        if category:
                            category.usage_count += 1
                    
                    # Create merchant alias for future auto-categorization
                    if category_id:
                        create_merchant_alias_if_needed(trans_data['merchant'], category_id)
                    
                    db.session.add(transaction)
                    imported_count += 1
                    
                    # Commit in batches for better performance
                    if imported_count % 50 == 0:
                        db.session.commit()
                    
                except Exception as e:
                    errors.append(f"{trans_data['date_str']} - {trans_data['merchant']}: {str(e)}")
            
            try:
                db.session.commit()
                
                # Clear session data
                session.pop('amex_import_data', None)
                
                if errors:
                    flash(f'Imported {imported_count} transactions with {len(errors)} errors', 'warning')
                    for error in errors[:5]:
                        flash(f'Error: {error}', 'error')
                else:
                    flash(f'Successfully imported ALL {imported_count} transactions!', 'success')
                
                return redirect(url_for('financial.dashboard'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Database error: {str(e)}', 'error')
                return redirect(url_for('financial.review_import'))
        
        # GET request - show review page
        categories = SpendingCategory.query.order_by(
            SpendingCategory.is_custom,
            SpendingCategory.usage_count.desc(),
            SpendingCategory.name
        ).all()
        
        return render_template(
            'financial/review_import.html',
            import_data=import_data,
            categories=categories,
            active='financial'
        )
@financial_bp.route('/import/cancel')
def cancel_import():
    """Cancel the import process"""
    session.pop('amex_import_data', None)
    flash('Import cancelled', 'info')
    return redirect(url_for('financial.import_amex'))


# ==================== HELPER FUNCTIONS ====================

def normalize_merchant_name(merchant_name):
    """
    Aggressively normalize merchant names to core business name only.
    """
    if not merchant_name:
        return ""
    
    # Start with uppercase
    name = merchant_name.upper().strip()
    
    # First, handle known merchants exactly - check the full string first
    exact_merchants = {
        # Map variations to canonical names
        'MEIJER STORE #197 000XFORD': 'MEIJER',
        'MEIJER EXPRESS 185/UAUBURN HILLS': 'MEIJER',
        'MEIJER EXPRESS 197/UOXFORD': 'MEIJER',
        'MEIJER EXPRESS 185/UAUBURN': 'MEIJER',
        'SUNOCO GAS 215-977-3000': 'SUNOCO',
        'TACO BELL 033309 333CLARKSTON': 'TACO BELL',
        'BP#8436073D BPD AND SONVJLE': 'BP',
        'BP D AND S': 'BP',
        'MARATHON 5694 0000 MOUNT PLEASAN': 'MARATHON',
        'MARATHON MOUNT PLEASAN': 'MARATHON',
        'ZEFFY* DETROITMYS MIDDLETOWN': 'ZEFFY',
        'BEIRUT PALACE 068880CLARKSTON': 'BEIRUT PALACE',
        'KROGER CLARKSTON': 'KROGER',
        'EXXONMOBIL 9901 ORTONVILLE': 'EXXONMOBIL',
        'EXXONMOBIL 9730 ROCHESTER HIL': 'EXXONMOBIL',
        'EXXONMOBIL ORTONVILLE': 'EXXONMOBIL',
        'EXXONMOBIL ROCHESTER HIL': 'EXXONMOBIL',
        'WILSON AUTOWASH 0000ORTONVILLE': 'WILSON AUTOWASH',
        'CHINA FARE RESTAURANORTONVILLE': 'CHINA FARE',
        'AC TIRE SERVICE CENTORTONVILLE': 'AC TIRE SERVICE',
        'BUECHE FOOD WORLD ORTONVILLE': 'BUECHE FOOD WORLD',
        'SPEEDWAY 44627 00004ROCHESTER HIL': 'SPEEDWAY',
        'SPEEDWAY 00004ROCHESTER HIL': 'SPEEDWAY',
        'TIM HORTON\'S OXFORD': 'TIM HORTONS',
        'DOLLAR GENERAL ORTONVILLE': 'DOLLAR GENERAL',
        'ALDI 67021 6702 LAKE ORION': 'ALDI',
        'ALDI LAKE ORION': 'ALDI',
        'TRACTOR SUPPLY CO ORTONVILLE': 'TRACTOR SUPPLY',
        'TRACTOR SUPPLY ORTONVILLE': 'TRACTOR SUPPLY',
        'RUB A DUB* RUB A DUBORION CHARTER TOWNSHIP': 'RUB A DUB',
        'RUB A DUB*': 'RUB A DUB',
        'UNCLE PETER\'S PASTIECLARKSTON': 'UNCLE PETERS PASTIE',
        'ART AND DICKS PARTY OXFORD': 'ART AND DICKS',
        'ART AND DICKS': 'ART AND DICKS',
        'USPS PO 2572400371 00XFORD': 'USPS',
        'USPS PO 00XFORD': 'USPS',
        'USPS PO 2571000462 0ORTONVILLE': 'USPS',
        'USPS PO 0ORTONVILLE': 'USPS',
        '7-ELEVEN 33602 00073CLARKSTON': '7-ELEVEN',
        '7-ELEVEN 00073CLARKSTON': '7-ELEVEN',
        'AUTOZONE #2144 00000WATERFORD': 'AUTOZONE',
        'AUTOZONE 00000WATERFORD': 'AUTOZONE',
        'O\'REILLY AUTO PARTS WATERFORD': 'OREILLY AUTO PARTS',
        'A&W ORTONVILLE': 'A&W',
        'A W ORTONVILLE': 'A&W',
        'TROY MEDICAL PC 0000TROY': 'TROY MEDICAL',
        'TROY MEDICAL PC': 'TROY MEDICAL',
        'CITGO OIL CO 479-928-7135': 'CITGO',
        'CITGO OIL 479-928-': 'CITGO',
        'ORTONVILLE CITGO 000ORTONVILLE': 'CITGO',
        'ORTONVILLE CITGO': 'CITGO',
        'LOWRY\'S LITTLE FLOCKHorton': 'LOWRYS LITTLE FLOCK',
        'LOWRY\'S LITTLE FLOCKHORTON': 'LOWRYS LITTLE FLOCK',
        'OFFICEMAX/DEPOT 6238JACKSON': 'OFFICEMAX',
    }
    
    # Check exact match first
    if name in exact_merchants:
        return exact_merchants[name]
    
    # Remove known city suffixes and everything after them
    cities = [
        'OXFORD', 'ORTONVILLE', 'CLARKSTON', 'WATERFORD', 
        'ROCHESTER HIL', 'ROCHESTER', 'LAKE ORION', 'TROY', 
        'JACKSON', 'HORTON', 'MIDDLETOWN', 'MOUNT PLEASAN',
        'UAUBURN HILLS', 'UAUBURN', 'UOXFORD'
    ]
    
    for city in cities:
        # Remove city and everything after it
        if city in name:
            name = name.split(city)[0].strip()
    
    # Now check if it starts with a known merchant prefix
    merchant_prefixes = {
        'MEIJER': 'MEIJER',
        'SUNOCO': 'SUNOCO',
        'TACO BELL': 'TACO BELL',
        'BP#': 'BP',
        'BP ': 'BP',
        'MARATHON': 'MARATHON',
        'ZEFFY': 'ZEFFY',
        'BEIRUT PALACE': 'BEIRUT PALACE',
        'KROGER': 'KROGER',
        'EXXONMOBIL': 'EXXONMOBIL',
        'WILSON AUTOWASH': 'WILSON AUTOWASH',
        'CHINA FARE': 'CHINA FARE',
        'AC TIRE': 'AC TIRE SERVICE',
        'BUECHE': 'BUECHE FOOD WORLD',
        'SPEEDWAY': 'SPEEDWAY',
        'TIM HORTON': 'TIM HORTONS',
        'DOLLAR GENERAL': 'DOLLAR GENERAL',
        'ALDI': 'ALDI',
        'TRACTOR SUPPLY': 'TRACTOR SUPPLY',
        'RUB A DUB': 'RUB A DUB',
        'UNCLE PETER': 'UNCLE PETERS PASTIE',
        'ART AND DICK': 'ART AND DICKS',
        'USPS': 'USPS',
        '7-ELEVEN': '7-ELEVEN',
        '7-11': '7-ELEVEN',
        'AUTOZONE': 'AUTOZONE',
        'O\'REILLY': 'OREILLY AUTO PARTS',
        'OREILLY': 'OREILLY AUTO PARTS',
        'A&W': 'A&W',
        'A W ': 'A&W',
        'TROY MEDICAL': 'TROY MEDICAL',
        'CITGO': 'CITGO',
        'LOWRY': 'LOWRYS LITTLE FLOCK',
        'OFFICEMAX': 'OFFICEMAX',
        'OFFICE MAX': 'OFFICEMAX',
    }
    
    for prefix, canonical in merchant_prefixes.items():
        if name.startswith(prefix):
            return canonical
    
    # Remove common patterns
    # Remove store numbers
    name = re.sub(r'#\d+', '', name)
    name = re.sub(r'\s+\d{4,}', '', name)
    name = re.sub(r'\s+0+[A-Z]+', '', name)  # Patterns like "000XFORD"
    
    # Remove phone numbers
    name = re.sub(r'\d{3}-\d{3}-\d{4}', '', name)
    
    # Remove special characters
    name = re.sub(r'[*#]', '', name)
    
    # Clean up
    name = ' '.join(name.split())
    
    # If we still have something reasonable, return it
    if len(name) > 2:
        return name
    
    # Otherwise return the original, cleaned
    return ' '.join(merchant_name.upper().split()[:3])  # First 3 words


def map_amex_category(amex_category, merchant):
    """Map American Express categories to our spending categories"""
    
    from .constants import AMEX_CATEGORY_MAP
    
    # Normalize the merchant name for better matching
    normalized = normalize_merchant_name(merchant)
    
    # First check merchant alias with normalized name
    alias = MerchantAlias.query.filter_by(normalized_name=normalized).first()
    
    if alias and alias.default_category_id:
        category = SpendingCategory.query.get(alias.default_category_id)
        if category:
            return {'id': category.id, 'name': category.name}
    
    # Then check merchant patterns with normalized name
    normalized_lower = normalized.lower()
    for cat_name, patterns in MERCHANT_PATTERNS.items():
        for pattern in patterns:
            if pattern in normalized_lower:
                category = SpendingCategory.query.filter_by(name=cat_name).first()
                if category:
                    return {'id': category.id, 'name': category.name}
    
    # Finally use Amex category mapping
    our_category_name = AMEX_CATEGORY_MAP.get(amex_category, 'Other')
    category = SpendingCategory.query.filter_by(name=our_category_name).first()
    
    if category:
        return {'id': category.id, 'name': category.name}
    
    # Default to 'Other'
    other_category = SpendingCategory.query.filter_by(name='Other').first()
    if other_category:
        return {'id': other_category.id, 'name': 'Other'}
    
    return {'id': None, 'name': 'Uncategorized'}


def create_merchant_alias_if_needed(merchant, category_id):
    """Create a merchant alias for future auto-categorization"""
    if not category_id:
        return
    
    merchant_clean = merchant.strip()
    normalized = normalize_merchant_name(merchant_clean)
    
    # Check if alias exists for this normalized name
    existing = MerchantAlias.query.filter_by(normalized_name=normalized).first()
    if not existing:
        # Create new alias
        alias = MerchantAlias(
            alias=merchant_clean,
            normalized_name=normalized,
            canonical_name=normalized,
            default_category_id=category_id
        )
        db.session.add(alias)

@financial_bp.route('/bulk-update-category', methods=['POST'])
def bulk_update_category():
    """Update all transactions from a merchant to a new category"""
    merchant = request.form.get('merchant')
    new_category_id = request.form.get('category_id')
    
    if not merchant:
        flash('No merchant specified', 'error')
        return redirect(url_for('financial.dashboard'))
    
    # Find all transactions with this merchant
    transactions = Transaction.query.filter_by(merchant=merchant).all()
    
    if not transactions:
        flash('No transactions found for this merchant', 'warning')
        return redirect(url_for('financial.dashboard'))
    
    # Update all transactions
    count = 0
    for transaction in transactions:
        transaction.category_id = int(new_category_id) if new_category_id else None
        count += 1
    
    # Also create/update merchant alias for future imports
    if new_category_id:
        create_merchant_alias_if_needed(merchant, new_category_id)
    
    db.session.commit()
    
    flash(f'Updated {count} transactions from "{merchant}" to new category', 'success')
    return redirect(request.referrer or url_for('financial.dashboard'))

# Add this route to handle bulk transaction updates

@financial_bp.route('/bulk-action', methods=['POST'])
def bulk_action():
    """Handle bulk actions on selected transactions"""
    
    # Get selected transaction IDs
    transaction_ids = request.form.getlist('transaction_ids')
    action = request.form.get('bulk_action')
    
    if not transaction_ids:
        flash('No transactions selected', 'warning')
        return redirect(request.referrer or url_for('financial.dashboard'))
    
    # Convert to integers
    transaction_ids = [int(id) for id in transaction_ids]
    
    if action == 'change_category':
        # Get the new category
        new_category_id = request.form.get('new_category_id')
        
        if not new_category_id:
            flash('No category selected', 'error')
            return redirect(request.referrer or url_for('financial.dashboard'))
        
        # Update all selected transactions
        transactions = Transaction.query.filter(Transaction.id.in_(transaction_ids)).all()
        
        # Track unique merchants for alias creation
        merchants_updated = set()
        
        for transaction in transactions:
            transaction.category_id = int(new_category_id) if new_category_id != 'none' else None
            merchants_updated.add(transaction.merchant)
        
        # Create merchant aliases for future auto-categorization
        if new_category_id != 'none':
            for merchant in merchants_updated:
                create_merchant_alias_if_needed(merchant, int(new_category_id))
        
        db.session.commit()
        flash(f'Updated {len(transactions)} transactions to new category', 'success')
        
    elif action == 'delete':
        # Delete selected transactions
        transactions = Transaction.query.filter(Transaction.id.in_(transaction_ids)).all()
        
        for transaction in transactions:
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
        flash(f'Deleted {len(transactions)} transactions', 'success')
        
    elif action == 'change_card':
        # Change card for selected transactions
        new_card = request.form.get('new_card')
        
        if not new_card:
            flash('No card selected', 'error')
            return redirect(request.referrer or url_for('financial.dashboard'))
        
        Transaction.query.filter(Transaction.id.in_(transaction_ids)).update(
            {'card': new_card},
            synchronize_session=False
        )
        db.session.commit()
        flash(f'Updated {len(transaction_ids)} transactions to {new_card}', 'success')
    
    return redirect(request.referrer or url_for('financial.dashboard'))

# Add these routes to your financial/routes.py file

# ==================== SETTINGS ====================

@financial_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    """Manage categories and merchant aliases"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_category':
            # Add new custom category
            name = request.form.get('name', '').strip()
            icon = request.form.get('icon', '💰')
            color = request.form.get('color', '#6ea8ff')
            
            if name:
                # Check if category exists
                existing = SpendingCategory.query.filter_by(name=name).first()
                if existing:
                    flash(f'Category "{name}" already exists', 'error')
                else:
                    category = SpendingCategory(
                        name=name,
                        icon=icon,
                        color=color,
                        is_custom=True
                    )
                    db.session.add(category)
                    db.session.commit()
                    flash(f'Category "{name}" added', 'success')
                    
        elif action == 'delete_category':
            # Delete category (only if custom and no transactions)
            category_id = request.form.get('category_id')
            if category_id:
                category = SpendingCategory.query.get(int(category_id))
                if category:
                    if category.is_custom:
                        # Check if any transactions use this category
                        transaction_count = Transaction.query.filter_by(category_id=category.id).count()
                        if transaction_count > 0:
                            flash(f'Cannot delete "{category.name}" - {transaction_count} transactions use this category', 'error')
                        else:
                            db.session.delete(category)
                            db.session.commit()
                            flash(f'Category "{category.name}" deleted', 'success')
                    else:
                        flash('Cannot delete predefined categories', 'error')
                        
        elif action == 'add_merchant_alias':
            # Add merchant alias for auto-categorization
            merchant = request.form.get('merchant', '').strip()
            canonical = request.form.get('canonical', '').strip() or merchant
            category_id = request.form.get('default_category')
            
            if merchant and category_id:
                normalized = normalize_merchant_name(merchant)
                # Check if alias exists for normalized name
                existing = MerchantAlias.query.filter_by(normalized_name=normalized).first()
                if existing:
                    # Update existing
                    existing.canonical_name = canonical
                    existing.default_category_id = int(category_id)
                    flash(f'Merchant alias "{merchant}" updated', 'success')
                else:
                    # Create new
                    alias = MerchantAlias(
                        alias=merchant,
                        normalized_name=normalized,
                        canonical_name=canonical,
                        default_category_id=int(category_id)
                    )
                    db.session.add(alias)
                    flash(f'Merchant alias "{merchant}" added', 'success')
                db.session.commit()
                
        return redirect(url_for('financial.settings'))
    
    # GET request - show settings page
    categories = SpendingCategory.query.order_by(
        SpendingCategory.is_custom,
        SpendingCategory.name
    ).all()
    
    # Get category usage stats
    category_stats = db.session.query(
        SpendingCategory.id,
        func.count(Transaction.id).label('transaction_count'),
        func.sum(Transaction.amount).label('total_amount')
    ).outerjoin(
        Transaction
    ).group_by(
        SpendingCategory.id
    ).all()
    
    # Convert to dict for easy lookup
    stats_dict = {
        stat[0]: {
            'count': stat[1] or 0,
            'total': stat[2] or 0
        } for stat in category_stats
    }
    
    # Get merchant aliases with usage counts
    aliases = []
    alias_records = MerchantAlias.query.order_by(MerchantAlias.alias).all()
    
    for alias in alias_records:
        # Count transactions that match this alias
        usage_count = Transaction.query.filter(
            db.or_(
                Transaction.merchant == alias.alias,
                Transaction.merchant == alias.canonical_name,
                Transaction.merchant == alias.normalized_name
            )
        ).count()
        
        # Add usage_count as a property we can access in the template
        alias.usage_count = usage_count
        aliases.append(alias)
    
    return render_template(
        'financial/settings.html',
        categories=categories,
        category_stats=stats_dict,
        aliases=aliases,
        active='financial'
    )


# ==================== MERCHANT ALIAS MANAGEMENT ====================

@financial_bp.route('/merchant-alias/edit', methods=['POST'])
def edit_merchant_alias():
    """Edit a merchant alias and optionally update all transactions"""
    alias_id = request.form.get('alias_id')
    new_canonical = request.form.get('canonical_name')
    new_category_id = request.form.get('category_id')
    update_transactions = request.form.get('update_transactions') == 'true'
    
    alias = MerchantAlias.query.get_or_404(int(alias_id))
    old_canonical = alias.canonical_name
    
    # Update the alias
    alias.canonical_name = new_canonical
    alias.normalized_name = new_canonical  # Also update normalized to match
    if new_category_id:
        alias.default_category_id = int(new_category_id) if new_category_id else None
    
    # If requested, update all transactions with this merchant
    if update_transactions:
        # Find all transactions that match the old name
        transactions = Transaction.query.filter(
            db.or_(
                Transaction.merchant == alias.alias,
                Transaction.merchant == old_canonical,
                Transaction.merchant == alias.normalized_name
            )
        ).all()
        
        for trans in transactions:
            trans.merchant = new_canonical
            if new_category_id:
                trans.category_id = int(new_category_id) if new_category_id else None
        
        flash(f'Updated alias and {len(transactions)} transactions', 'success')
    else:
        flash('Updated merchant alias rule', 'success')
    
    db.session.commit()
    return redirect(url_for('financial.settings'))


@financial_bp.route('/merchant-alias/<int:id>/delete', methods=['POST'])
def delete_merchant_alias(id):
    """Delete a merchant alias"""
    alias = MerchantAlias.query.get_or_404(id)
    merchant_name = alias.alias
    
    db.session.delete(alias)
    db.session.commit()
    
    flash(f'Deleted rule for "{merchant_name}"', 'success')
    return redirect(url_for('financial.settings'))


@financial_bp.route('/merchant-aliases/cleanup', methods=['POST'])
def cleanup_merchant_aliases():
    """Bulk cleanup merchant aliases with better normalization"""
    
    # Get all aliases
    aliases = MerchantAlias.query.all()
    
    # Mapping of bad names to good names - based on your actual data
    cleanup_map = {
        'MEIJER STORE #197 000XFORD': 'MEIJER',
        'MEIJER EXPRESS 185/UAUBURN HILLS': 'MEIJER',
        'MEIJER EXPRESS 197/UOXFORD': 'MEIJER', 
        'MEIJER EXPRESS 185/UAUBURN': 'MEIJER',
        'MEIJER 000XFORD': 'MEIJER',
        'SUNOCO GAS 215-977-3000': 'SUNOCO',
        'SUNOCO GAS 215-977-': 'SUNOCO',
        'TACO BELL 033309 333CLARKSTON': 'TACO BELL',
        'TACO BELL 333CLARKSTON': 'TACO BELL',
        'BP#8436073D BPD AND SONVJLE': 'BP',
        'BP D AND S': 'BP',
        'MARATHON 5694 0000 MOUNT PLEASAN': 'MARATHON',
        'MARATHON MOUNT PLEASAN': 'MARATHON',
        'ZEFFY* DETROITMYS MIDDLETOWN': 'ZEFFY',
        'BEIRUT PALACE 068880CLARKSTON': 'BEIRUT PALACE',
        'KROGER CLARKSTON': 'KROGER',
        'EXXONMOBIL 9901 ORTONVILLE': 'EXXONMOBIL',
        'EXXONMOBIL ORTONVILLE': 'EXXONMOBIL',
        'EXXONMOBIL 9730 ROCHESTER HIL': 'EXXONMOBIL',
        'EXXONMOBIL ROCHESTER HIL': 'EXXONMOBIL',
        'WILSON AUTOWASH 0000ORTONVILLE': 'WILSON AUTOWASH',
        'CHINA FARE RESTAURANORTONVILLE': 'CHINA FARE',
        'AC TIRE SERVICE CENTORTONVILLE': 'AC TIRE SERVICE',
        'BUECHE FOOD WORLD ORTONVILLE': 'BUECHE FOOD WORLD',
        'SPEEDWAY 44627 00004ROCHESTER HIL': 'SPEEDWAY',
        'SPEEDWAY 00004ROCHESTER HIL': 'SPEEDWAY',
        'TIM HORTON\'S OXFORD': 'TIM HORTONS',
        'DOLLAR GENERAL ORTONVILLE': 'DOLLAR GENERAL',
        'ALDI 67021 6702 LAKE ORION': 'ALDI',
        'ALDI LAKE ORION': 'ALDI',
        'TRACTOR SUPPLY CO ORTONVILLE': 'TRACTOR SUPPLY',
        'TRACTOR SUPPLY ORTONVILLE': 'TRACTOR SUPPLY',
        'RUB A DUB* RUB A DUBORION CHARTER TOWNSHIP': 'RUB A DUB',
        'RUB A DUB*': 'RUB A DUB',
        'UNCLE PETER\'S PASTIECLARKSTON': 'UNCLE PETERS PASTIE',
        'ART AND DICKS PARTY OXFORD': 'ART AND DICKS',
        'USPS PO 2572400371 00XFORD': 'USPS',
        'USPS PO 00XFORD': 'USPS',
        'USPS PO 2571000462 0ORTONVILLE': 'USPS',
        'USPS PO 0ORTONVILLE': 'USPS',
        '7-ELEVEN 33602 00073CLARKSTON': '7-ELEVEN',
        '7-ELEVEN 00073CLARKSTON': '7-ELEVEN',
        'AUTOZONE #2144 00000WATERFORD': 'AUTOZONE',
        'AUTOZONE 00000WATERFORD': 'AUTOZONE',
        'O\'REILLY AUTO PARTS WATERFORD': 'OREILLY AUTO PARTS',
        'A&W ORTONVILLE': 'A&W',
        'A W ORTONVILLE': 'A&W',
        'TROY MEDICAL PC 0000TROY': 'TROY MEDICAL',
        'CITGO OIL CO 479-928-7135': 'CITGO',
        'CITGO OIL 479-928-': 'CITGO',
        'ORTONVILLE CITGO 000ORTONVILLE': 'CITGO',
        'ORTONVILLE CITGO': 'CITGO',
        'LOWRY\'S LITTLE FLOCKHorton': 'LOWRYS LITTLE FLOCK',
        'LOWRY\'S LITTLE FLOCKHORTON': 'LOWRYS LITTLE FLOCK',
        'OFFICEMAX/DEPOT 6238JACKSON': 'OFFICEMAX',
    }
    
    updated_count = 0
    transaction_count = 0
    
    for alias in aliases:
        # Check if this alias needs cleaning
        for bad_name, good_name in cleanup_map.items():
            if bad_name in alias.canonical_name or alias.canonical_name in bad_name:
                # Update the alias
                old_name = alias.canonical_name
                alias.canonical_name = good_name
                alias.normalized_name = good_name
                updated_count += 1
                
                # Update all transactions with the old name
                transactions = Transaction.query.filter(
                    db.or_(
                        Transaction.merchant == alias.alias,
                        Transaction.merchant == old_name
                    )
                ).all()
                
                for trans in transactions:
                    trans.merchant = good_name
                
                transaction_count += len(transactions)
                break
    
    db.session.commit()
    
    flash(f'Cleaned up {updated_count} merchant rules and {transaction_count} transactions', 'success')
    return redirect(url_for('financial.settings'))