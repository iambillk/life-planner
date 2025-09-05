# models/__init__.py - Updated with Real Estate models
"""
Models initialization file
Imports all models for easy access throughout the application

CHANGELOG:
v1.1.0 (2025-01-03)
- Added Real Estate Management models (Property, PropertyMaintenance, etc.)

v1.0.0 (Original)
- Initial model imports for all existing modules
"""

from .base import db
from .daily import DailyTask
from .equipment import (
    Equipment, 
    MaintenanceRecord, 
    MaintenanceReminder, 
    EquipmentPhoto, 
    MaintenancePhoto,
    FuelLog,
    ConsumableLog,
    CarWashLog,
    Receipt
)
from .projects import (
    TCHProject, 
    TCHTask,
    TCHIdea,
    TCHMilestone,
    TCHProjectNote,
    PersonalProject,
    ProjectFile
)
from .goals import Goal
from .health import WeightEntry
from .todo import TodoList, TodoItem

# ========== NEW: Real Estate Models ==========
from .realestate import (
    Property,
    PropertyMaintenance,
    PropertyVendor,
    PropertyMaintenancePhoto,
    MaintenanceTemplate
)

__all__ = [
    'db',
    'DailyTask',
    # Equipment models
    'Equipment', 
    'MaintenanceRecord', 
    'MaintenanceReminder', 
    'EquipmentPhoto', 
    'MaintenancePhoto',
    'FuelLog',
    'ConsumableLog',
    'CarWashLog',
    'Receipt',
    # Project models
    'TCHProject',
    'TCHTask',
    'TCHIdea', 
    'TCHMilestone',
    'TCHProjectNote',
    'PersonalProject',
    'ProjectFile',
    # Other models
    'Goal',
    'WeightEntry',
    'TodoList',
    'TodoItem',
    # Real Estate models
    'Property',
    'PropertyMaintenance',
    'PropertyVendor',
    'PropertyMaintenancePhoto',
    'MaintenanceTemplate'
]