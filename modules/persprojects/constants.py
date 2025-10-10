# modules/persprojects/constants.py
"""
Personal Projects Module Constants
===================================

All category definitions and configuration for personal projects.

FILE: modules/persprojects/constants.py
VERSION: 1.1.0
UPDATED: 2025-01-10

CHANGELOG:
----------
v1.1.0 (2025-01-10)
- Added PERSONAL_TASK_CATEGORIES for task categorization
- Fixed missing task categories that were causing validation errors

v1.0.0 (2025-01-07)
- Initial creation with project categories, statuses, and priorities
"""

# =============================================================================
# PROJECT CATEGORIES
# =============================================================================

PERSONAL_PROJECT_CATEGORIES = [
    'Home Improvement',
    'Hobbies & Crafts', 
    'Learning & Education',
    'Health & Fitness',
    'Financial',
    'Travel',
    'Creative',
    'Family & Relationships',
    'Organization',
    'Other'
]

# =============================================================================
# TASK CATEGORIES
# =============================================================================

PERSONAL_TASK_CATEGORIES = [
    'Home Maintenance',
    'DIY Project',
    'Shopping',
    'Research',
    'Planning',
    'Execution',
    'Learning',
    'Practice',
    'Administrative',
    'Other'
]

# =============================================================================
# PROJECT STATUSES
# =============================================================================

PROJECT_STATUSES = [
    ('planning', 'Planning'),
    ('active', 'Active'),
    ('on_hold', 'On Hold'),
    ('completed', 'Completed')
]

# =============================================================================
# PRIORITY LEVELS
# =============================================================================

PRIORITY_LEVELS = [
    ('low', 'Low'),
    ('medium', 'Medium'),
    ('high', 'High'),
    ('critical', 'Critical')
]

# =============================================================================
# IDEA STATUSES
# =============================================================================

IDEA_STATUSES = [
    ('new', 'New'),
    ('considering', 'Considering'),
    ('implemented', 'Implemented'),
    ('rejected', 'Rejected')
]

# =============================================================================
# NOTE CATEGORIES
# =============================================================================

NOTE_CATEGORIES = [
    'general',
    'progress',
    'issue',
    'research',
    'reference'
]