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
        func.count(Transaction.id).label('count')  # ADDED THIS LINE
    ).join(
        Transaction
    ).filter(
        Transaction.date >= month_start,
        Transaction.date <= month_end
    ).group_by(
        SpendingCategory.id,
        SpendingCategory.name,  # Added to GROUP BY
        SpendingCategory.icon,  # Added to GROUP BY
        SpendingCategory.color  # Added to GROUP BY
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
    merchants = [m[0] for m in merchants_query if m[0]]  # Extract merchant names, filter None
    
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
    
    # BUILD merchant_totals FIRST (MOVE THIS UP!)
    merchant_totals = defaultdict(lambda: {
        'total': 0, 
        'count': 0,
        'category': None,
        'first_date': None,
        'last_date': None
    })
    
    for t in transactions:
        merchant_totals[t.merchant]['total'] += t.amount
        merchant_totals[t.merchant]['count'] += 1
        merchant_totals[t.merchant]['category'] = t.category.name if t.category else 'Uncategorized'
        
        # Track first and last visit
        if not merchant_totals[t.merchant]['first_date'] or t.date < merchant_totals[t.merchant]['first_date']:
            merchant_totals[t.merchant]['first_date'] = t.date
        if not merchant_totals[t.merchant]['last_date'] or t.date > merchant_totals[t.merchant]['last_date']:
            merchant_totals[t.merchant]['last_date'] = t.date
    
    # THEN build enhanced top merchants data
    top_merchants = []
    if merchant_totals:  # Only process if there are merchants
        for merchant, data in sorted(merchant_totals.items(), key=lambda x: x[1]['total'], reverse=True)[:15]:
            # Ensure dates exist
            if data['first_date'] and data['last_date']:
                days_between = (data['last_date'] - data['first_date']).days + 1
                frequency = f"Every {days_between // data['count']} days" if data['count'] > 1 else "Once"
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
            category_mappings = {}
            
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
                
                transactions_to_import.append({
                    'date': date_obj,
                    'date_str': row['Date'],
                    'amount': amount,
                    'merchant': merchant,
                    'amex_category': amex_category,
                    'suggested_category_id': suggested_category['id'],
                    'suggested_category_name': suggested_category['name'],
                    'address': row.get('Address', ''),
                    'city_state': row.get('City/State', ''),
                    'reference': row.get('Reference', '').strip("'")
                })
            
            # Store in session for review
            session['amex_import_data'] = {
                'transactions': transactions_to_import,
                'skipped': skipped_transactions,
                'total_count': len(transactions_to_import),
                'total_amount': sum(t['amount'] for t in transactions_to_import),
                'skipped_count': len(skipped_transactions)
            }
            
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
        
        # FIXED: Use enumerate to match the template's loop.index0
        for idx, trans_data in enumerate(import_data['transactions']):
            try:
                # FIXED: Get the category from form using index
                category_id = request.form.get(f"category_{idx}")
                
                # Create transaction
                transaction = Transaction(
                    date=trans_data['date'],
                    amount=trans_data['amount'],
                    merchant=trans_data['merchant'],
                    category_id=int(category_id) if category_id and category_id != '' else None,
                    card='Amex',
                    notes=f"Ref: {trans_data.get('reference', '')}"  # FIXED: Use .get() for safety
                )
                
                # Update category usage count
                if transaction.category_id:
                    category = SpendingCategory.query.get(transaction.category_id)
                    if category:
                        category.usage_count += 1
                
                # Check for merchant alias - only if a category was selected
                if category_id:
                    create_merchant_alias_if_needed(trans_data['merchant'], category_id)
                
                db.session.add(transaction)
                imported_count += 1
                
            except Exception as e:
                errors.append(f"{trans_data['date_str']} - {trans_data['merchant']}: {str(e)}")
        
        try:
            db.session.commit()
            
            # Clear session data
            session.pop('amex_import_data', None)
            
            if errors:
                flash(f'Imported {imported_count} transactions with {len(errors)} errors', 'warning')
                for error in errors[:5]:  # Show first 5 errors
                    flash(f'Error: {error}', 'error')
            else:
                flash(f'Successfully imported {imported_count} transactions!', 'success')
            
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

def map_amex_category(amex_category, merchant):
    """Map American Express categories to our spending categories"""
    
    # Import the mapping from constants
    from .constants import AMEX_CATEGORY_MAP
    
    # First check merchant alias
    merchant_lower = merchant.lower()
    alias = MerchantAlias.query.filter(
        db.func.lower(MerchantAlias.alias) == merchant_lower
    ).first()
    
    if alias and alias.default_category_id:
        category = SpendingCategory.query.get(alias.default_category_id)
        if category:
            return {'id': category.id, 'name': category.name}
    
    # Then check merchant patterns
    for cat_name, patterns in MERCHANT_PATTERNS.items():
        for pattern in patterns:
            if pattern in merchant_lower:
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
    
    # Check if alias already exists
    existing = MerchantAlias.query.filter_by(alias=merchant_clean).first()
    if not existing:
        # Create new alias
        alias = MerchantAlias(
            alias=merchant_clean,
            canonical_name=merchant_clean,
            default_category_id=int(category_id)
        )
        db.session.add(alias)
# Add this route to modules/financial/routes.py

# ==================== SETTINGS & CATEGORY MANAGEMENT ====================

@financial_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    """Financial settings and category management"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_category':
            # Add new category
            name = request.form.get('name', '').strip()
            icon = request.form.get('icon', '💰')
            color = request.form.get('color', '#6ea8ff')
            
            if name:
                # Check if already exists
                existing = SpendingCategory.query.filter_by(name=name).first()
                if existing:
                    flash(f'Category "{name}" already exists', 'error')
                else:
                    new_category = SpendingCategory(
                        name=name,
                        icon=icon,
                        color=color,
                        is_custom=True
                    )
                    db.session.add(new_category)
                    db.session.commit()
                    flash(f'Category "{name}" added successfully!', 'success')
            else:
                flash('Category name is required', 'error')
                
        elif action == 'update_category':
            # Update existing category
            category_id = request.form.get('category_id')
            if category_id:
                category = SpendingCategory.query.get(int(category_id))
                if category:
                    category.icon = request.form.get(f'icon_{category_id}', category.icon)
                    category.color = request.form.get(f'color_{category_id}', category.color)
                    db.session.commit()
                    flash(f'Category "{category.name}" updated!', 'success')
                    
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
                # Check if alias exists
                existing = MerchantAlias.query.filter_by(alias=merchant).first()
                if existing:
                    # Update existing
                    existing.canonical_name = canonical
                    existing.default_category_id = int(category_id)
                    flash(f'Merchant alias "{merchant}" updated', 'success')
                else:
                    # Create new
                    alias = MerchantAlias(
                        alias=merchant,
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
