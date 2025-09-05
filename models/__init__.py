# models/__init__.py - Complete file with ProjectFile import
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
    ProjectFile  # ADD THIS LINE - This is what was missing!
)
from .goals import Goal
from .health import WeightEntry
from .todo import TodoList, TodoItem

__all__ = [
    'db',
    'DailyTask',
    'Equipment', 
    'MaintenanceRecord', 
    'MaintenanceReminder', 
    'EquipmentPhoto', 
    'MaintenancePhoto',
    'FuelLog',
    'ConsumableLog',
    'CarWashLog',
    'Receipt',
    'TCHProject',
    'TCHTask',
    'TCHIdea', 
    'TCHMilestone',
    'TCHProjectNote',
    'PersonalProject',
    'ProjectFile',  # ADD THIS LINE TOO
    'Goal',
    'WeightEntry',
    'TodoList',
    'TodoItem'
]