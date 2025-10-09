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
from .standalone import StandaloneTask
from .rolodex import Contact, Company


from .admin_tools import (
    ToolExecution, KnowledgeItem, KnowledgeCategory,
    KnowledgeTag, KnowledgeRelation, init_admin_tools
)

from .ssh_logs import (
    SSHSession,
    SSHCommand,
    SSHScanLog,
    init_ssh_logs
)

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
    # PersonalProject,  <-- REMOVE THIS LINE
    ProjectFile
)
from .goals import Goal
from .health import WeightEntry
from .todo import TodoList, TodoItem

from .todo_advanced import (
    TaskDependency, 
    RecurringTaskTemplate, 
    TaskTimeLog,
    TaskTemplate, 
    TaskMetadata, 
    TaskUserPreferences
)

# ========== NEW: Real Estate Models ==========
from .realestate import (
    Property,
    PropertyMaintenance,
    PropertyVendor,
    PropertyMaintenancePhoto,
    MaintenanceTemplate
)

# New Personal Projects
from .persprojects import (
    PersonalProject,  # <-- KEEP THIS ONE
    PersonalTask,
    PersonalIdea,
    PersonalMilestone,
    PersonalProjectNote,
    PersonalProjectFile
)

# Import daily planner models
from models.daily_planner import (
    DailyConfig,
    CalendarEvent,
    EventType,
    RecurringEvent,
    DailyTask,
    HumanMaintenance,
    CapturedNote,
    HarassmentLog,
    ProjectRotation,
    init_daily_planner
)

from .financial import (
    SpendingCategory,
    Transaction,
    MerchantAlias
)



__all__ = [
    'db',
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
    # 'PersonalProject',
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
    'MaintenanceTemplate',
    # Personal Project Models
    'PersonalProject',  # <-- KEEP THIS ONE
    'PersonalTask',
    'PersonalIdea',
    'PersonalMilestone',
    'PersonalProjectNote',
    'PersonalProjectFile',
    # Daily Planner
    'DailyConfig',
    'CalendarEvent',
    'EventType',
    'RecurringEvent',    
    'DailyTask',
    'HumanMaintenance',
    'CapturedNote',
    'HarassmentLog',
    'ProjectRotation',
    'init_daily_planner',
    'SpendingCategory',
    'Transaction', 
    'MerchantAlias',
    # SSH Logs
    'SSHSession',
    'SSHCommand', 
    'SSHScanLog',
    'init_ssh_logs',
    # Rolodex
    'Contact',
    'Company'
]

