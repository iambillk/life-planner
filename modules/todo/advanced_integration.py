# modules/todo/advanced_integration.py
"""
Advanced integration features for the unified todo system
Handles dependencies, recurring tasks, time tracking, and templates
"""

from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Set
import json
from models import db
from models.todo_advanced import (
    TaskDependency, RecurringTaskTemplate, TaskTimeLog,
    TaskTemplate, TaskMetadata, TaskUserPreferences
)
from .integration import TaskAggregator, UnifiedTask


class DependencyManager:
    """Manage task dependencies and relationships"""
    
    @staticmethod
    def add_dependency(dependent_id: str, prerequisite_id: str, dep_type: str = 'blocks') -> bool:
        """Add a dependency between two tasks"""
        try:
            # Check if dependency already exists
            existing = TaskDependency.query.filter_by(
                dependent_task_id=dependent_id,
                prerequisite_task_id=prerequisite_id
            ).first()
            
            if existing:
                return False
            
            # Extract task types for quick filtering
            dep_type_str = dependent_id.split('_')[0]
            prereq_type_str = prerequisite_id.split('_')[0]
            
            dependency = TaskDependency(
                dependent_task_id=dependent_id,
                dependent_task_type=dep_type_str,
                prerequisite_task_id=prerequisite_id,
                prerequisite_task_type=prereq_type_str,
                dependency_type=dep_type
            )
            
            db.session.add(dependency)
            db.session.commit()
            return True
            
        except Exception:
            db.session.rollback()
            return False
    
    @staticmethod
    def remove_dependency(dependent_id: str, prerequisite_id: str) -> bool:
        """Remove a dependency between two tasks"""
        try:
            dependency = TaskDependency.query.filter_by(
                dependent_task_id=dependent_id,
                prerequisite_task_id=prerequisite_id
            ).first()
            
            if dependency:
                db.session.delete(dependency)
                db.session.commit()
                return True
            return False
            
        except Exception:
            db.session.rollback()
            return False
    
    @staticmethod
    def get_dependencies(task_id: str) -> Dict[str, List[str]]:
        """Get all dependencies for a task"""
        # Tasks this task depends on
        prerequisites = TaskDependency.query.filter_by(
            dependent_task_id=task_id
        ).all()
        
        # Tasks that depend on this task
        dependents = TaskDependency.query.filter_by(
            prerequisite_task_id=task_id
        ).all()
        
        return {
            'prerequisites': [d.prerequisite_task_id for d in prerequisites],
            'dependents': [d.dependent_task_id for d in dependents],
            'blocked_by': [d.prerequisite_task_id for d in prerequisites if d.dependency_type == 'blocks'],
            'blocks': [d.dependent_task_id for d in dependents if d.dependency_type == 'blocks']
        }
    
    @staticmethod
    def can_complete(task_id: str) -> tuple[bool, List[str]]:
        """Check if a task can be completed (all prerequisites done)"""
        dependencies = TaskDependency.query.filter_by(
            dependent_task_id=task_id,
            dependency_type='blocks'
        ).all()
        
        incomplete_prereqs = []
        
        for dep in dependencies:
            # Check if prerequisite is complete
            prereq_task = TaskAggregator.get_single_task(dep.prerequisite_task_id)
            if prereq_task and not prereq_task.completed:
                incomplete_prereqs.append(dep.prerequisite_task_id)
        
        return len(incomplete_prereqs) == 0, incomplete_prereqs


class RecurringTaskManager:
    """Manage recurring task templates and generation"""
    
    @staticmethod
    def create_template(
        title: str,
        target_type: str,
        recurrence_type: str,
        **kwargs
    ) -> RecurringTaskTemplate:
        """Create a new recurring task template"""
        template = RecurringTaskTemplate(
            title=title,
            target_type=target_type,
            recurrence_type=recurrence_type,
            description=kwargs.get('description'),
            target_project_id=kwargs.get('project_id'),
            recurrence_days=kwargs.get('days'),  # For weekly
            recurrence_day_of_month=kwargs.get('day_of_month'),  # For monthly
            recurrence_interval=kwargs.get('interval', 1),
            priority=kwargs.get('priority', 'medium'),
            category=kwargs.get('category'),
            estimated_minutes=kwargs.get('estimated_minutes'),
            start_date=kwargs.get('start_date', date.today()),
            end_date=kwargs.get('end_date')
        )
        
        template.next_due = template.calculate_next_due()
        
        db.session.add(template)
        db.session.commit()
        return template
    
    @staticmethod
    def generate_due_tasks() -> List[str]:
        """Generate tasks from templates that are due"""
        created_tasks = []
        today = date.today()
        
        # Find all active templates with due tasks
        templates = RecurringTaskTemplate.query.filter(
            RecurringTaskTemplate.is_active == True,
            db.or_(
                RecurringTaskTemplate.end_date == None,
                RecurringTaskTemplate.end_date >= today
            )
        ).all()
        
        for template in templates:
            # Calculate if task is due
            if not template.next_due or template.next_due > today:
                continue
            
            # Create the task based on target type
            task_id = RecurringTaskManager._create_task_from_template(template)
            
            if task_id:
                created_tasks.append(task_id)
                
                # Update template
                template.last_created = today
                template.next_due = template.calculate_next_due()
        
        db.session.commit()
        return created_tasks
    
    @staticmethod
    def _create_task_from_template(template: RecurringTaskTemplate) -> Optional[str]:
        """Create a task from a template"""
        from models import TCHTask, PersonalTask, TodoItem, TodoList, TCHProject, PersonalProject
        
        try:
            if template.target_type == 'tch':
                # Find target project
                if template.target_project_id:
                    project = TCHProject.query.get(template.target_project_id)
                else:
                    project = TCHProject.query.filter_by(status='active').first()
                
                if not project:
                    return None
                
                task = TCHTask(
                    project_id=project.id,
                    title=template.title,
                    description=template.description,
                    priority=template.priority,
                    category=template.category,
                    due_date=template.next_due
                )
                db.session.add(task)
                db.session.flush()
                
                # Add metadata if estimated time provided
                if template.estimated_minutes:
                    metadata = TaskMetadata(
                        task_id=f'tch_{task.id}',
                        task_type='tch',
                        estimated_minutes=template.estimated_minutes
                    )
                    db.session.add(metadata)
                
                return f'tch_{task.id}'
            
            elif template.target_type == 'personal':
                if template.target_project_id:
                    project = PersonalProject.query.get(template.target_project_id)
                else:
                    project = PersonalProject.query.filter_by(status='active').first()
                
                if not project:
                    return None
                
                task = PersonalTask(
                    project_id=project.id,
                    content=template.title,
                    category=template.category
                )
                db.session.add(task)
                db.session.flush()
                
                if template.estimated_minutes:
                    metadata = TaskMetadata(
                        task_id=f'personal_{task.id}',
                        task_type='personal',
                        estimated_minutes=template.estimated_minutes
                    )
                    db.session.add(metadata)
                
                return f'personal_{task.id}'
            
            elif template.target_type == 'todo':
                # Find or create recurring tasks list
                todo_list = TodoList.query.filter_by(
                    title='Recurring Tasks',
                    is_archived=False
                ).first()
                
                if not todo_list:
                    todo_list = TodoList(
                        title='Recurring Tasks',
                        description='Automatically generated recurring tasks',
                        color='green',
                        is_pinned=True
                    )
                    db.session.add(todo_list)
                    db.session.flush()
                
                item = TodoItem(
                    list_id=todo_list.id,
                    content=template.title,
                    priority=(template.priority in ['high', 'critical']),
                    due_date=template.next_due
                )
                db.session.add(item)
                db.session.flush()
                
                if template.estimated_minutes:
                    metadata = TaskMetadata(
                        task_id=f'todo_{item.id}',
                        task_type='todo',
                        estimated_minutes=template.estimated_minutes
                    )
                    db.session.add(metadata)
                
                return f'todo_{item.id}'
            
        except Exception:
            db.session.rollback()
            return None


class TimeTracker:
    """Manage time tracking for tasks"""
    
    @staticmethod
    def start_timer(task_id: str, task_title: str = None) -> TaskTimeLog:
        """Start tracking time for a task"""
        # Stop any running timers for this task
        TimeTracker.stop_all_timers(task_id)
        
        task_type = task_id.split('_')[0]
        
        log = TaskTimeLog(
            task_id=task_id,
            task_type=task_type,
            task_title=task_title or 'Task',
            start_time=datetime.utcnow()
        )
        
        db.session.add(log)
        db.session.commit()
        return log
    
    @staticmethod
    def stop_timer(task_id: str) -> Optional[TaskTimeLog]:
        """Stop the active timer for a task"""
        log = TaskTimeLog.query.filter_by(
            task_id=task_id,
            end_time=None
        ).first()
        
        if log and log.stop():
            # Update task metadata with actual time
            metadata = TaskMetadata.query.filter_by(task_id=task_id).first()
            if not metadata:
                metadata = TaskMetadata(
                    task_id=task_id,
                    task_type=log.task_type
                )
                db.session.add(metadata)
            
            # Update actual minutes
            total_minutes = TimeTracker.get_total_time(task_id)
            metadata.actual_minutes = total_minutes
            
            db.session.commit()
            return log
        
        return None
    
    @staticmethod
    def stop_all_timers(task_id: str = None):
        """Stop all timers, optionally for a specific task"""
        query = TaskTimeLog.query.filter_by(end_time=None)
        
        if task_id:
            query = query.filter_by(task_id=task_id)
        
        logs = query.all()
        
        for log in logs:
            log.stop()
        
        if logs:
            db.session.commit()
    
    @staticmethod
    def get_active_timer(task_id: str) -> Optional[TaskTimeLog]:
        """Get the currently running timer for a task"""
        return TaskTimeLog.query.filter_by(
            task_id=task_id,
            end_time=None
        ).first()
    
    @staticmethod
    def get_total_time(task_id: str) -> int:
        """Get total time spent on a task in minutes"""
        logs = TaskTimeLog.query.filter_by(task_id=task_id).all()
        total = sum(log.duration_minutes or 0 for log in logs if log.duration_minutes)
        
        # Add current running timer if any
        active = TimeTracker.get_active_timer(task_id)
        if active:
            delta = datetime.utcnow() - active.start_time
            total += int(delta.total_seconds() / 60)
        
        return total
    
    @staticmethod
    def get_today_time() -> int:
        """Get total time tracked today in minutes"""
        today_start = datetime.combine(date.today(), datetime.min.time())
        
        logs = TaskTimeLog.query.filter(
            TaskTimeLog.start_time >= today_start
        ).all()
        
        total = 0
        for log in logs:
            if log.duration_minutes:
                total += log.duration_minutes
            elif log.is_running:
                delta = datetime.utcnow() - log.start_time
                total += int(delta.total_seconds() / 60)
        
        return total


class TemplateManager:
    """Manage reusable task templates"""
    
    @staticmethod
    def create_template(name: str, tasks: List[Dict], **kwargs) -> TaskTemplate:
        """Create a new task template"""
        template = TaskTemplate(
            name=name,
            description=kwargs.get('description'),
            category=kwargs.get('category'),
            target_type=kwargs.get('target_type', 'todo'),
            template_data=json.dumps({'tasks': tasks})
        )
        
        db.session.add(template)
        db.session.commit()
        return template
    
    @staticmethod
    def use_template(template_id: int, target_project_id: Optional[int] = None) -> List[str]:
        """Create tasks from a template"""
        template = TaskTemplate.query.get(template_id)
        if not template:
            return []
        
        created_tasks = []
        template_data = json.loads(template.template_data)
        
        from models import TCHTask, PersonalTask, TodoItem, TodoList, TCHProject, PersonalProject
        
        for task_data in template_data.get('tasks', []):
            try:
                if template.target_type == 'tch':
                    project = None
                    if target_project_id:
                        project = TCHProject.query.get(target_project_id)
                    if not project:
                        project = TCHProject.query.filter_by(status='active').first()
                    
                    if project:
                        task = TCHTask(
                            project_id=project.id,
                            title=task_data.get('title', 'Task'),
                            description=task_data.get('description'),
                            priority=task_data.get('priority', 'medium'),
                            category=task_data.get('category')
                        )
                        db.session.add(task)
                        db.session.flush()
                        
                        # Add metadata
                        if task_data.get('estimated_minutes'):
                            metadata = TaskMetadata(
                                task_id=f'tch_{task.id}',
                                task_type='tch',
                                estimated_minutes=task_data.get('estimated_minutes'),
                                tags=task_data.get('tags')
                            )
                            db.session.add(metadata)
                        
                        created_tasks.append(f'tch_{task.id}')
                
                elif template.target_type == 'personal':
                    project = None
                    if target_project_id:
                        project = PersonalProject.query.get(target_project_id)
                    if not project:
                        project = PersonalProject.query.filter_by(status='active').first()
                    
                    if project:
                        task = PersonalTask(
                            project_id=project.id,
                            content=task_data.get('title', 'Task'),
                            category=task_data.get('category')
                        )
                        db.session.add(task)
                        db.session.flush()
                        
                        if task_data.get('estimated_minutes'):
                            metadata = TaskMetadata(
                                task_id=f'personal_{task.id}',
                                task_type='personal',
                                estimated_minutes=task_data.get('estimated_minutes'),
                                tags=task_data.get('tags')
                            )
                            db.session.add(metadata)
                        
                        created_tasks.append(f'personal_{task.id}')
                
            except Exception:
                continue
        
        # Update template usage
        template.times_used += 1
        template.last_used = datetime.utcnow()
        
        db.session.commit()
        return created_tasks
    
    @staticmethod
    def get_templates(category: Optional[str] = None) -> List[TaskTemplate]:
        """Get all templates, optionally filtered by category"""
        query = TaskTemplate.query
        
        if category:
            query = query.filter_by(category=category)
        
        return query.order_by(TaskTemplate.times_used.desc()).all()


class MetadataManager:
    """Manage task metadata and extended properties"""
    
    @staticmethod
    def get_or_create(task_id: str) -> TaskMetadata:
        """Get or create metadata for a task"""
        metadata = TaskMetadata.query.filter_by(task_id=task_id).first()
        
        if not metadata:
            task_type = task_id.split('_')[0]
            metadata = TaskMetadata(
                task_id=task_id,
                task_type=task_type
            )
            db.session.add(metadata)
            db.session.commit()
        
        return metadata
    
    @staticmethod
    def update_metadata(task_id: str, **kwargs) -> bool:
        """Update metadata for a task"""
        try:
            metadata = MetadataManager.get_or_create(task_id)
            
            for key, value in kwargs.items():
                if hasattr(metadata, key):
                    setattr(metadata, key, value)
            
            metadata.updated_at = datetime.utcnow()
            db.session.commit()
            return True
            
        except Exception:
            db.session.rollback()
            return False
    
    @staticmethod
    def add_tags(task_id: str, tags: List[str]) -> bool:
        """Add tags to a task"""
        try:
            metadata = MetadataManager.get_or_create(task_id)
            
            for tag in tags:
                metadata.add_tag(tag)
            
            db.session.commit()
            return True
            
        except Exception:
            db.session.rollback()
            return False
    
    @staticmethod
    def get_tasks_by_tag(tag: str) -> List[str]:
        """Get all task IDs with a specific tag"""
        metadatas = TaskMetadata.query.filter(
            TaskMetadata.tags.like(f'%{tag}%')
        ).all()
        
        task_ids = []
        for metadata in metadatas:
            if metadata.has_tag(tag):
                task_ids.append(metadata.task_id)
        
        return task_ids