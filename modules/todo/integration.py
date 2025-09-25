# modules/todo/integration.py
"""
Integration service for aggregating tasks from all modules
Provides a unified interface for tasks from TCH, Personal, Todo, and Daily modules
"""

from datetime import datetime, date
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from models import (
    db,
    TCHTask, TCHProject,
    PersonalTask, PersonalProject,
    TodoItem, TodoList,
    DailyTask
)

@dataclass
class UnifiedTask:
    """Wrapper class for tasks from different sources"""
    id: str  # Composite ID like "tch_123" or "personal_456"
    source: str  # 'tch', 'personal', 'todo', 'daily'
    source_id: int  # Original task ID
    title: str
    description: Optional[str]
    completed: bool
    completed_date: Optional[datetime]
    due_date: Optional[date]
    priority: str  # Normalized to low/medium/high/critical
    project_name: Optional[str]
    project_id: Optional[int]
    category: Optional[str]
    created_at: datetime
    can_edit: bool  # Whether this task type supports editing
    can_complete: bool  # Whether this task type supports completion
    original_data: Dict[str, Any]  # Store source-specific fields
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'source': self.source,
            'source_id': self.source_id,
            'title': self.title,
            'description': self.description,
            'completed': self.completed,
            'completed_date': self.completed_date.isoformat() if self.completed_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'priority': self.priority,
            'project_name': self.project_name,
            'project_id': self.project_id,
            'category': self.category,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'can_edit': self.can_edit,
            'can_complete': self.can_complete,
            'source_badge': self._get_source_badge(),
            'priority_class': self._get_priority_class()
        }
    
    def _get_source_badge(self) -> str:
        """Get display badge for task source"""
        badges = {
            'tch': '💼 TCH',
            'personal': '🏠 Personal',
            'todo': '📝 Todo',
            'daily': '📅 Daily'
        }
        return badges.get(self.source, '📌 Task')
    
    def _get_priority_class(self) -> str:
        """Get CSS class for priority styling"""
        classes = {
            'critical': 'priority-critical',
            'high': 'priority-high',
            'medium': 'priority-medium',
            'low': 'priority-low'
        }
        return classes.get(self.priority, 'priority-normal')


class TaskAggregator:
    """Service for aggregating tasks from all sources"""
    
    @staticmethod
    def get_all_tasks(
        include_completed: bool = False,
        source_filter: Optional[List[str]] = None,
        date_filter: Optional[str] = None
    ) -> List[UnifiedTask]:
        """
        Aggregate tasks from all sources
        
        Args:
            include_completed: Whether to include completed tasks
            source_filter: List of sources to include ('tch', 'personal', 'todo', 'daily')
            date_filter: Filter by date ('today', 'week', 'overdue')
        
        Returns:
            List of UnifiedTask objects
        """
        tasks = []
        sources_to_check = source_filter or ['tch', 'personal', 'todo', 'daily']
        
        # Get TCH Project Tasks
        if 'tch' in sources_to_check:
            tasks.extend(TaskAggregator._get_tch_tasks(include_completed))
        
        # Get Personal Project Tasks
        if 'personal' in sources_to_check:
            tasks.extend(TaskAggregator._get_personal_tasks(include_completed))
        
        # Get Todo List Items
        if 'todo' in sources_to_check:
            tasks.extend(TaskAggregator._get_todo_items(include_completed))
        
        # Get Daily Tasks (today only)
        if 'daily' in sources_to_check:
            tasks.extend(TaskAggregator._get_daily_tasks(include_completed))
        
        # Apply date filter if specified
        if date_filter:
            tasks = TaskAggregator._apply_date_filter(tasks, date_filter)
        
        # Sort by priority and due date
        tasks.sort(key=lambda t: (
            not t.due_date,  # Tasks with due dates first
            t.due_date if t.due_date else date.max,
            {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}.get(t.priority, 4)
        ))
        
        return tasks
    
    @staticmethod
    def _get_tch_tasks(include_completed: bool) -> List[UnifiedTask]:
        """Get tasks from TCH Projects"""
        tasks = []
        query = TCHTask.query.join(TCHProject)
        
        if not include_completed:
            query = query.filter(TCHTask.completed == False)
        
        for task in query.all():
            # Normalize priority
            priority = task.priority or 'medium'
            if task.project.priority == 'critical' and priority != 'critical':
                priority = 'high'  # Boost priority for critical projects
            
            tasks.append(UnifiedTask(
                id=f"tch_{task.id}",
                source='tch',
                source_id=task.id,
                title=task.title,
                description=task.description,
                completed=task.completed,
                completed_date=task.completed_date,
                due_date=task.due_date,
                priority=priority,
                project_name=task.project.name,
                project_id=task.project_id,
                category=task.category,
                created_at=task.created_at,
                can_edit=True,
                can_complete=True,
                original_data={
                    'assigned_to': task.assigned_to,
                    'order_num': task.order_num
                }
            ))
        
        return tasks
    
    @staticmethod
    def _get_personal_tasks(include_completed: bool) -> List[UnifiedTask]:
        """Get tasks from Personal Projects"""
        tasks = []
        query = PersonalTask.query.join(PersonalProject)
        
        if not include_completed:
            query = query.filter(PersonalTask.completed == False)
        
        for task in query.all():
            # PersonalTask uses 'content' field instead of 'title'
            # Get priority from project since PersonalTask doesn't have priority field
            priority = task.project.priority or 'medium'
            
            tasks.append(UnifiedTask(
                id=f"personal_{task.id}",
                source='personal',
                source_id=task.id,
                title=task.content,  # Note: PersonalTask uses 'content'
                description=None,  # PersonalTask doesn't have description
                completed=task.completed,
                completed_date=task.completed_at,
                due_date=None,  # PersonalTask doesn't have due_date in the model
                priority=priority,
                project_name=task.project.name,
                project_id=task.project_id,
                category=task.category,
                created_at=task.created_at,
                can_edit=True,
                can_complete=True,
                original_data={
                    'order_num': task.order_num
                }
            ))
        
        return tasks
    
    @staticmethod
    def _get_todo_items(include_completed: bool) -> List[UnifiedTask]:
        """Get items from Todo Lists"""
        tasks = []
        # Get standalone todo lists (not attached to projects)
        query = TodoItem.query.join(TodoList).filter(
            TodoList.is_archived == False
        )
        
        if not include_completed:
            query = query.filter(TodoItem.completed == False)
        
        for item in query.all():
            tasks.append(UnifiedTask(
                id=f"todo_{item.id}",
                source='todo',
                source_id=item.id,
                title=item.content,
                description=item.note,
                completed=item.completed,
                completed_date=item.completed_at,
                due_date=item.due_date,
                priority='high' if item.priority else 'medium',  # TodoItem.priority is boolean
                project_name=item.todo_list.title,
                project_id=item.list_id,
                category=None,
                created_at=item.created_at,
                can_edit=True,
                can_complete=True,
                original_data={
                    'list_title': item.todo_list.title,
                    'list_color': item.todo_list.color,
                    'order_num': item.order_num
                }
            ))
        
        return tasks
    
    @staticmethod
    def _get_daily_tasks(include_completed: bool) -> List[UnifiedTask]:
        """Get tasks from Daily Planner (today only)"""
        tasks = []
        query = DailyTask.query.filter(DailyTask.date == date.today())
        
        if not include_completed:
            query = query.filter(DailyTask.completed == False)
        
        for task in query.all():
            # Map numeric priority to text
            priority_map = {1: 'critical', 2: 'high', 3: 'medium', 4: 'low'}
            priority = priority_map.get(task.priority, 'medium')
            
            tasks.append(UnifiedTask(
                id=f"daily_{task.id}",
                source='daily',
                source_id=task.id,
                title=task.task_description,
                description=None,
                completed=task.completed,
                completed_date=task.completed_at,
                due_date=task.date,  # Daily tasks are always "due" on their date
                priority=priority,
                project_name=task.project_name,
                project_id=task.project_id,
                category=None,
                created_at=task.created_at,
                can_edit=False,  # Daily tasks are auto-generated
                can_complete=True,
                original_data={
                    'project_type': task.project_type
                }
            ))
        
        return tasks
    
    @staticmethod
    def _apply_date_filter(tasks: List[UnifiedTask], filter_type: str) -> List[UnifiedTask]:
        """Apply date-based filtering to tasks"""
        today = date.today()
        filtered = []
        
        for task in tasks:
            if filter_type == 'today':
                # Due today or overdue
                if task.due_date and task.due_date <= today:
                    filtered.append(task)
            elif filter_type == 'week':
                # Due within 7 days
                if task.due_date and (task.due_date - today).days <= 7:
                    filtered.append(task)
            elif filter_type == 'overdue':
                # Past due date and not completed
                if task.due_date and task.due_date < today and not task.completed:
                    filtered.append(task)
            elif filter_type == 'no_date':
                # No due date set
                if not task.due_date:
                    filtered.append(task)
        
        return filtered
    
    @staticmethod
    def complete_task(task_id: str) -> bool:
        """
        Mark a task as complete in its source system
        
        Args:
            task_id: Unified task ID (e.g., 'tch_123')
        
        Returns:
            True if successful, False otherwise
        """
        try:
            source, source_id = task_id.split('_', 1)
            source_id = int(source_id)
            
            if source == 'tch':
                task = TCHTask.query.get(source_id)
                if task:
                    task.completed = True
                    task.completed_date = datetime.utcnow()
            
            elif source == 'personal':
                task = PersonalTask.query.get(source_id)
                if task:
                    task.completed = True
                    task.completed_at = datetime.utcnow()
            
            elif source == 'todo':
                item = TodoItem.query.get(source_id)
                if item:
                    item.completed = True
                    item.completed_at = datetime.utcnow()
            
            elif source == 'daily':
                task = DailyTask.query.get(source_id)
                if task:
                    task.completed = True
                    task.completed_at = datetime.utcnow()
            else:
                return False
            
            db.session.commit()
            return True
            
        except Exception:
            db.session.rollback()
            return False
    
    @staticmethod
    def uncomplete_task(task_id: str) -> bool:
        """
        Mark a task as incomplete in its source system
        
        Args:
            task_id: Unified task ID (e.g., 'tch_123')
        
        Returns:
            True if successful, False otherwise
        """
        try:
            source, source_id = task_id.split('_', 1)
            source_id = int(source_id)
            
            if source == 'tch':
                task = TCHTask.query.get(source_id)
                if task:
                    task.completed = False
                    task.completed_date = None
            
            elif source == 'personal':
                task = PersonalTask.query.get(source_id)
                if task:
                    task.completed = False
                    task.completed_at = None
            
            elif source == 'todo':
                item = TodoItem.query.get(source_id)
                if item:
                    item.completed = False
                    item.completed_at = None
            
            elif source == 'daily':
                task = DailyTask.query.get(source_id)
                if task:
                    task.completed = False
                    task.completed_at = None
            else:
                return False
            
            db.session.commit()
            return True
            
        except Exception:
            db.session.rollback()
            return False