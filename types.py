# types.py
from typing import TypedDict, List, Optional

class Task(TypedDict):
    """
    Defines the structure for a task dictionary.
    This helps with type checking and code clarity.
    """
    id: str
    task: str
    done: bool
    xp: int
    due_time: Optional[str] # Optional due time, can be None
    is_recurring_instance: bool # Indicates if this task is an instance of a recurring task

class RecurringTask(TypedDict):
    """
    Defines the structure for a recurring task definition.
    """
    id: str
    task: str
    xp: int
    recurrence_type: str # e.g., "daily", "weekly"
    recurrence_value: Optional[List[str]] # e.g., ["Mon", "Wed"] for weekly, or None for daily
    due_time: Optional[str] # Optional due time for recurring tasks
    last_generated_date: Optional[str] # Last date this recurring task was instantiated as a daily task
