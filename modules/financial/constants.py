# modules/financial/constants.py
"""
Financial Module Constants
Predefined categories and configuration
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
    {'name': 'Other', 'icon': '📌', 'color': '#94a3b8'},
]

# Common merchant aliases (for auto-categorization)
MERCHANT_PATTERNS = {
    'Groceries': ['kroger', 'publix', 'walmart', 'target', 'whole foods', 'aldi', 'costco'],
    'Gas': ['shell', 'exxon', 'bp', 'chevron', 'marathon', 'speedway', 'gas'],
    'Restaurants': ['restaurant', 'cafe', 'coffee', 'pizza', 'burger', 'chipotle', 'starbucks'],
    'Amazon': ['amazon', 'amzn'],
    'Subscriptions': ['netflix', 'spotify', 'hulu', 'disney', 'apple.com', 'google'],
}