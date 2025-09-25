# modules/financial/constants.py
"""
Financial Module Constants
Predefined categories and configuration
Updated to handle Amex categories
"""

# Credit cards
CARDS = ['Amex', 'Other']

# Predefined spending categories with icons and colors
PREDEFINED_CATEGORIES = [
    {'name': 'Groceries', 'icon': '🛒', 'color': '#22c55e'},
    {'name': 'Restaurants', 'icon': '🍽️', 'color': '#f59e0b'},
    {'name': 'Gas', 'icon': '⛽', 'color': '#ef4444'},
    {'name': 'Amazon', 'icon': '📦', 'color': '#ff9500'},
    {'name': 'Utilities', 'icon': '💡', 'color': '#8b5cf6'},
    {'name': 'Entertainment', 'icon': '🎬', 'color': '#ec4899'},
    {'name': 'Medical', 'icon': '🏥', 'color': '#14b8a6'},
    {'name': 'Home', 'icon': '🏠', 'color': '#6366f1'},
    {'name': 'Subscriptions', 'icon': '📱', 'color': '#0ea5e9'},
    {'name': 'Auto', 'icon': '🚗', 'color': '#84cc16'},
    {'name': 'Clothing', 'icon': '👕', 'color': '#a855f7'},
    {'name': 'Travel', 'icon': '✈️', 'color': '#06b6d4'},
    {'name': 'Personal Care', 'icon': '💅', 'color': '#f472b6'},
    {'name': 'Gifts', 'icon': '🎁', 'color': '#fb923c'},
    {'name': 'Shipping', 'icon': '📮', 'color': '#64748b'},  # New for Amex
    {'name': 'Charity', 'icon': '❤️', 'color': '#e11d48'},   # New for Amex
    {'name': 'Other', 'icon': '📌', 'color': '#94a3b8'},
]

# Common merchant aliases (for auto-categorization)
# Updated with more patterns based on your spending
MERCHANT_PATTERNS = {
    'Groceries': [
        'kroger', 'publix', 'walmart', 'target', 'whole foods', 'aldi', 'costco',
        'meijer', 'trader joe', 'safeway', 'wegmans', 'harris teeter'
    ],
    'Gas': [
        'shell', 'exxon', 'bp', 'chevron', 'marathon', 'speedway', 'gas',
        'fuel', 'sunoco', 'mobil', 'citgo', 'valero', '76', 'phillips'
    ],
    'Restaurants': [
        'restaurant', 'cafe', 'coffee', 'pizza', 'burger', 'chipotle', 'starbucks',
        'taco bell', 'mcdonalds', 'wendys', 'subway', 'panera', 'dunkin',
        'chick-fil-a', 'olive garden', 'applebees', 'bar', 'grill', 'diner',
        'beirut palace', 'sushi', 'thai', 'chinese', 'mexican', 'italian'
    ],
    'Amazon': [
        'amazon', 'amzn', 'aws', 'prime video', 'whole foods'
    ],
    'Subscriptions': [
        'netflix', 'spotify', 'hulu', 'disney', 'apple.com', 'google',
        'youtube', 'adobe', 'microsoft', 'dropbox', 'icloud', 'paramount'
    ],
    'Auto': [
        'autozone', 'advance auto', 'oreilly', 'napa', 'jiffy lube',
        'oil change', 'tire', 'mechanic', 'repair', 'service center'
    ],
    'Medical': [
        'pharmacy', 'cvs', 'walgreens', 'rite aid', 'hospital', 'clinic',
        'doctor', 'dental', 'medical', 'health', 'urgent care'
    ],
    'Home': [
        'home depot', 'lowes', 'menards', 'ace hardware', 'hardware',
        'furniture', 'ikea', 'wayfair', 'bed bath'
    ],
    'Charity': [
        'charity', 'donation', 'nonprofit', 'foundation', 'zeffy',
        'gofundme', 'red cross', 'goodwill', 'salvation army'
    ]
}

# Amex Category Mapping
# Maps American Express categories to our internal categories
AMEX_CATEGORY_MAP = {
    'Merchandise & Supplies-Groceries': 'Groceries',
    'Transportation-Fuel': 'Gas',
    'Restaurant-Bar & Café': 'Restaurants',
    'Restaurant-Restaurant': 'Restaurants',
    'Business Services-Health Care Services': 'Medical',
    'Merchandise & Supplies-General Retail': 'Other',
    'Merchandise & Supplies-Hardware Supplies': 'Home',
    'Transportation-Auto Services': 'Auto',
    'Business Services-Mailing & Shipping': 'Shipping',
    'Other-Charities': 'Charity',
    'Business Services-Other Services': 'Other',
    'Fees & Adjustments-Fees & Adjustments': 'Other'
}