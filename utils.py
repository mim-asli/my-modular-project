# utils.py
import tkinter as tk
import datetime
import calendar
from enum import Enum

# Define Filter Modes using Enum for clear task filtering options
class FilterMode(Enum):
    ALL = "all"
    DONE = "done"
    NOT_DONE = "not_done"

def xp_needed_for_level(level: int) -> int:
    """
    Calculates the XP required to reach a given level.
    The XP requirement increases with higher levels.
    """
    # Predefined XP thresholds for the first few levels
    xp_levels = [100, 150, 250, 400, 600, 900]
    if level - 1 < len(xp_levels):
        # Return XP from the predefined list if level is within range
        return xp_levels[level - 1]
    else:
        # For higher levels, calculate XP based on a linear progression
        # Starting from the last predefined level's XP + an increment per level
        return 900 + (level - len(xp_levels)) * 300

def center_window(window: tk.Toplevel, parent: tk.Tk) -> None:
    """
    Centers a Toplevel window relative to its parent window.
    Ensures dialogs appear in the middle of the main application window.
    """
    # Update window geometry to ensure accurate width/height calculations
    window.update_idletasks()
    
    # Calculate x and y coordinates to center the window
    # x = parent_x + (parent_width / 2) - (window_width / 2)
    # y = parent_y + (parent_height / 2) - (window_height / 2)
    x = parent.winfo_x() + (parent.winfo_width() // 2) - (window.winfo_width() // 2)
    y = parent.winfo_y() + (parent.winfo_height() // 2) - (window.winfo_height() // 2)
    
    # Set the window's position
    window.geometry(f"+{x}+{y}")
