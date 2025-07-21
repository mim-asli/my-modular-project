# utils.py
import datetime
import uuid
from enum import Enum

def xp_needed_for_level(level: int) -> int:
    """
    Calculates the amount of XP needed to reach a given level.
    The formula can be adjusted to change the leveling curve.
    """
    if level <= 0:
        return 0
    # Example: XP needed increases linearly with level
    # Level 1: 100 XP
    # Level 2: 200 XP
    # Level 3: 300 XP
    return level * 100

def center_window(window: any, parent: any = None) -> None:
    """
    Centers a Tkinter window on the screen or relative to its parent.
    """
    window.update_idletasks() # Ensure widgets are rendered for accurate size calculation
    
    if parent:
        # Center relative to parent window
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()

        win_width = window.winfo_width()
        win_height = window.winfo_height()

        x = parent_x + (parent_width // 2) - (win_width // 2)
        y = parent_y + (parent_height // 2) - (win_height // 2)
    else:
        # Center on the screen
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()

        win_width = window.winfo_width()
        win_height = window.winfo_height()

        x = (screen_width // 2) - (win_width // 2)
        y = (screen_height // 2) - (win_height // 2)

    window.geometry(f'+{x}+{y}')

class FilterMode(Enum):
    """
    Enum for defining task filter modes.
    """
    ALL = "all"
    DONE = "done"
    NOT_DONE = "not_done"

def generate_unique_id() -> str:
    """
    Generates a universally unique identifier (UUID).
    This ensures each task has a unique, collision-resistant ID.
    """
    return str(uuid.uuid4())
