# ui_dialogs.py
import tkinter as tk
from tkinter import messagebox, ttk
import datetime
import calendar
from enum import Enum
from typing import List, Dict, Optional, Union, TYPE_CHECKING
import uuid # For generating unique IDs

# Try to import plyer notification, provide a fallback if not available
try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    notification = None
    PLYER_AVAILABLE = False
    print("Warning: 'plyer' library not found. System notifications will not be available.")

# Import constants from the constants module
from constants import (
    DARK_BG, DARK_FRAME_BG, DARK_TEXT, ACCENT_COLOR, ERROR_COLOR, SUCCESS_COLOR, WARNING_COLOR
)

# Import utility functions and enums from the utils module
from utils import center_window, FilterMode, generate_unique_id

# Import custom TypedDicts for structured data
from custom_types import Task, RecurringTask

# This is for type hinting the app_instance without circular imports
if TYPE_CHECKING:
    from app import XPDashboardApp


class CustomDialog(tk.Toplevel):
    """
    A base class for creating custom themed dialogs.
    Provides a consistent look and feel for messages and inputs.
    """
    def __init__(self, parent: tk.Tk, title: str, message: str, buttons: Optional[List[tuple[str, Union[str, bool, None], str]]] = None, entry_text: Optional[str] = None, combobox_values: Optional[List[str]] = None, initial_combobox_value: Optional[str] = None, checkbox_options: Optional[Dict[str, bool]] = None):
        super().__init__(parent)
        self.parent = parent
        self.title(title)
        self.geometry("400x200") # Default size, can be adjusted dynamically
        self.configure(bg=DARK_BG)
        self.transient(parent)
        # self.grab_set() # MOVED: This call is moved to the show() method
        self.result: Union[str, bool, None] = None

        center_window(self, parent) # This already calls update_idletasks()

        tk.Label(self, text=message, bg=DARK_BG, fg=DARK_TEXT, font=("Segoe UI", 12), wraplength=350).pack(pady=10)

        if entry_text is not None:
            self.entry_var = tk.StringVar(value=entry_text)
            self.entry = tk.Entry(self, textvariable=self.entry_var, font=("Segoe UI", 12), width=40,
                                  bg=DARK_FRAME_BG, fg=DARK_TEXT, insertbackground=ACCENT_COLOR, bd=1, relief="solid")
            self.entry.pack(pady=5)
            self.entry.focus_set()
            # Bind Enter key to the first button's command if available
            if buttons and len(buttons) > 0:
                self.bind("<Return>", lambda e: self._on_button_click(buttons[0][1]))

        if combobox_values is not None:
            self.combobox_var = tk.StringVar(value=initial_combobox_value or (combobox_values[0] if combobox_values else ""))
            self.combobox = ttk.Combobox(self, textvariable=self.combobox_var, values=combobox_values, state="readonly", font=("Segoe UI", 11))
            self.combobox.pack(pady=5)

        self.checkbox_vars: Dict[str, tk.BooleanVar] = {}
        if checkbox_options:
            chk_frame = tk.Frame(self, bg=DARK_BG)
            chk_frame.pack(pady=5)
            for text, initial_value in checkbox_options.items():
                var = tk.BooleanVar(value=initial_value)
                chk = tk.Checkbutton(chk_frame, text=text, variable=var,
                                     bg=DARK_BG, fg=DARK_TEXT, selectcolor=ACCENT_COLOR,
                                     font=("Segoe UI", 10),
                                     activebackground=DARK_FRAME_BG, activeforeground=ACCENT_COLOR)
                chk.pack(side="left", padx=2, pady=2)
                self.checkbox_vars[text] = var

        btn_frame = tk.Frame(self, bg=DARK_BG)
        btn_frame.pack(pady=10)

        if buttons:
            for btn_text, btn_command, btn_color in buttons:
                tk.Button(btn_frame, text=btn_text, command=lambda cmd=btn_command: self._on_button_click(cmd),
                          bg=btn_color, fg=DARK_BG if btn_color != ERROR_COLOR else "white",
                          font=("Segoe UI", 11, "bold"), relief="flat", padx=10, pady=5,
                          activebackground=btn_color if btn_color != ERROR_COLOR else "#a03d45",
                          activeforeground=DARK_TEXT if btn_color != ERROR_COLOR else "white"
                          ).pack(side="left", padx=5)
        
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_button_click(self, command: Union[str, bool, None]) -> None:
        """Internal handler for button clicks."""
        self.result = command
        self.destroy()

    def _on_close(self) -> None:
        """Handle window close button, setting result to None."""
        self.result = None
        self.destroy()

    def show(self) -> Union[str, bool, None]:
        """Display the dialog and wait for it to close."""
        self.grab_set() # ADDED: Call grab_set just before waiting for the window
        self.parent.wait_window(self)
        return self.result

class CalendarDialog(tk.Toplevel):
    """
    A custom calendar dialog for selecting dates.
    """
    def __init__(self, parent: tk.Tk, initial_date: Optional[datetime.date] = None):
        super().__init__(parent)
        self.parent = parent
        self.title("Select Date")
        self.configure(bg=DARK_BG)
        self.transient(parent)
        # self.grab_set() # MOVED: This call is moved to the show() method
        self.result_date: Optional[str] = None

        self.current_year: int = initial_date.year if initial_date else datetime.date.today().year
        self.current_month: int = initial_date.month if initial_date else datetime.date.today().month

        center_window(self, parent)

        self._create_widgets()
        self._show_calendar()

    def _create_widgets(self) -> None:
        header_frame = tk.Frame(self, bg=DARK_FRAME_BG)
        header_frame.pack(pady=10, padx=10, fill="x")

        tk.Button(header_frame, text="<", command=self._prev_month,
                  bg=ACCENT_COLOR, fg=DARK_BG, font=("Segoe UI", 10, "bold"), relief="flat",
                  activebackground="#4a8ec9", activeforeground=DARK_TEXT).pack(side="left", padx=5)
        
        self.month_year_label = tk.Label(header_frame, text="", font=("Segoe UI", 14, "bold"), bg=DARK_FRAME_BG, fg=DARK_TEXT)
        self.month_year_label.pack(side="left", expand=True)

        tk.Button(header_frame, text=">", command=self._next_month,
                  bg=ACCENT_COLOR, fg=DARK_BG, font=("Segoe UI", 10, "bold"), relief="flat",
                  activebackground="#4a8ec9", activeforeground=DARK_TEXT).pack(side="right", padx=5)

        weekdays_frame = tk.Frame(self, bg=DARK_FRAME_BG)
        weekdays_frame.pack(padx=10, fill="x")
        week_days = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
        for day in week_days:
            tk.Label(weekdays_frame, text=day, font=("Segoe UI", 10, "bold"), bg=DARK_FRAME_BG, fg=ACCENT_COLOR, width=4).pack(side="left", padx=1)

        self.calendar_frame = tk.Frame(self, bg=DARK_BG)
        self.calendar_frame.pack(padx=10, pady=5)

        button_frame = tk.Frame(self, bg=DARK_BG)
        button_frame.pack(pady=10)
        tk.Button(button_frame, text="Today", command=self._select_today,
                  bg=WARNING_COLOR, fg=DARK_BG, font=("Segoe UI", 11, "bold"), relief="flat", padx=10, pady=5,
                  activebackground="#c7a35e", activeforeground=DARK_TEXT).pack(side="left", padx=5)
        tk.Button(button_frame, text="Cancel", command=self._on_close,
                  bg=ERROR_COLOR, fg="white", font=("Segoe UI", 11, "bold"), relief="flat", padx=10, pady=5,
                  activebackground="#a03d45", activeforeground="white").pack(side="right", padx=5)

    def _show_calendar(self) -> None:
        for widget in self.calendar_frame.winfo_children():
            widget.destroy()

        self.month_year_label.config(text=f"{calendar.month_name[self.current_month]} {self.current_year}")

        cal = calendar.Calendar(firstweekday=calendar.MONDAY)
        month_days = cal.monthdayscalendar(self.current_year, self.current_month)

        for week_idx, week in enumerate(month_days):
            for day_idx, day in enumerate(week):
                if day == 0:
                    tk.Label(self.calendar_frame, text="", bg=DARK_BG, width=4).grid(row=week_idx, column=day_idx, padx=1, pady=1)
                else:
                    date_obj = datetime.date(self.current_year, self.current_month, day)
                    btn = tk.Button(self.calendar_frame, text=str(day),
                                    command=lambda d=date_obj: self._select_date(d),
                                    font=("Segoe UI", 10), width=4, height=2,
                                    bg=DARK_FRAME_BG, fg=DARK_TEXT, relief="flat",
                                    activebackground=ACCENT_COLOR, activeforeground=DARK_BG)
                    
                    if date_obj == datetime.date.today():
                        btn.config(bg=ACCENT_COLOR, fg=DARK_BG, font=("Segoe UI", 10, "bold"),
                                   activebackground="#4a8ec9", activeforeground=DARK_TEXT)
                    elif date_obj.strftime("%Y-%m-%d") == self.parent.current_date:
                        btn.config(bg=WARNING_COLOR, fg=DARK_BG, font=("Segoe UI", 10, "bold"),
                                   activebackground="#c7a35e", activeforeground=DARK_TEXT)
                    else:
                        btn.config(activebackground=DARK_TEXT, activeforeground=DARK_FRAME_BG)

                    btn.grid(row=week_idx, column=day_idx, padx=1, pady=1)

    def _prev_month(self) -> None:
        self.current_month -= 1
        if self.current_month < 1:
            self.current_month = 12
            self.current_year -= 1
        self._show_calendar()

    def _next_month(self) -> None:
        self.current_month += 1
        if self.current_month > 12:
            self.current_month = 1
            self.current_year += 1
        self._show_calendar()

    def _select_date(self, date_obj: datetime.date) -> None:
        self.result_date = date_obj.strftime("%Y-%m-%d")
        self.destroy()

    def _select_today(self) -> None:
        self.result_date = datetime.date.today().strftime("%Y-%m-%d")
        self.destroy()

    def _on_close(self) -> None:
        self.result_date = None
        self.destroy()

    def show(self) -> Optional[str]:
        self.grab_set() # ADDED: Call grab_set just before waiting for the window
        self.parent.wait_window(self)
        return self.result_date

class TaskDetailsDialog(CustomDialog):
    """
    Custom dialog for adding/editing task details including XP category, manual XP, and due time.
    """
    def __init__(self, parent: tk.Tk, xp_categories: Dict[str, Optional[int]], initial_task_name: Optional[str] = None, initial_task: Optional[Task] = None):
        self.xp_categories = xp_categories
        self.initial_task = initial_task # Full task dictionary if editing
        
        title = "Add New Task" if initial_task is None else "Edit Task"
        message = "Enter task details:"
        button_text = "Add" if initial_task is None else "Save"
        button_command = "add" if initial_task is None else "save"

        super().__init__(parent, title, message,
                         buttons=[(button_text, button_command, SUCCESS_COLOR), ("Cancel", None, ERROR_COLOR)],
                         entry_text=initial_task_name or (initial_task.get("task", "") if initial_task else ""))

        # Adjust dialog size for more fields
        self.geometry("450x350")

        # XP Category combobox
        xp_cat_frame = tk.Frame(self, bg=DARK_BG)
        xp_cat_frame.pack(pady=5)
        tk.Label(xp_cat_frame, text="XP Category:", bg=DARK_BG, fg=DARK_TEXT, font=("Segoe UI", 11)).pack(side="left", padx=5)
        
        initial_xp_category = self._get_category_from_xp(initial_task.get("xp")) if initial_task else list(self.xp_categories.keys())[0]
        self.xp_category_var = tk.StringVar(value=initial_xp_category)
        self.xp_category_combobox = ttk.Combobox(xp_cat_frame, textvariable=self.xp_category_var,
                                                 values=list(self.xp_categories.keys()), state="readonly", font=("Segoe UI", 11))
        self.xp_category_combobox.pack(side="left", padx=5)
        self.xp_category_combobox.bind("<<ComboboxSelected>>", self._on_category_selected)

        # Manual XP entry (initially hidden)
        self.manual_xp_frame = tk.Frame(self, bg=DARK_BG)
        tk.Label(self.manual_xp_frame, text="Manual XP:", bg=DARK_BG, fg=DARK_TEXT, font=("Segoe UI", 11)).pack(side="left", padx=5)
        self.manual_xp_var = tk.StringVar(value=str(initial_task["xp"]) if initial_task and initial_xp_category == "Miscellaneous" else "")
        self.manual_xp_entry = tk.Entry(self.manual_xp_frame, textvariable=self.manual_xp_var, font=("Segoe UI", 11), width=10,
                                        bg=DARK_FRAME_BG, fg=DARK_TEXT, insertbackground=ACCENT_COLOR, bd=1, relief="solid")
        self.manual_xp_entry.pack(side="left", padx=5)
        self._on_category_selected() # Call once to set initial visibility

        # Due Time entry
        due_time_frame = tk.Frame(self, bg=DARK_BG)
        due_time_frame.pack(pady=5)
        tk.Label(due_time_frame, text="Due Time (HH:MM):", bg=DARK_BG, fg=DARK_TEXT, font=("Segoe UI", 11)).pack(side="left", padx=5)
        self.due_time_var = tk.StringVar(value=initial_task.get("due_time", "") if initial_task else "")
        self.due_time_entry = tk.Entry(due_time_frame, textvariable=self.due_time_var, font=("Segoe UI", 11), width=10,
                                      bg=DARK_FRAME_BG, fg=DARK_TEXT, insertbackground=ACCENT_COLOR, bd=1, relief="solid")
        self.due_time_entry.pack(side="left", padx=5)
        tk.Label(due_time_frame, text="(Optional)", bg=DARK_BG, fg=DARK_TEXT, font=("Segoe UI", 9, "italic")).pack(side="left", padx=2)

        # Recenter dialog after adding elements
        self.update_idletasks()
        self.geometry(f"450x{self.winfo_height()}")
        center_window(self, parent)

    def _get_category_from_xp(self, xp_value: Optional[int]) -> str:
        """Helper to find the category name for a given XP value."""
        for cat, xp in self.xp_categories.items():
            if xp == xp_value:
                return cat
        return "Miscellaneous" # Default if no exact match or if XP is None

    def _on_category_selected(self, event: Optional[tk.Event] = None) -> None:
        """Handles category combobox selection to show/hide manual XP entry."""
        selected_category: str = self.xp_category_var.get()
        if selected_category == "Miscellaneous":
            self.manual_xp_frame.pack(pady=5)
        else:
            self.manual_xp_frame.pack_forget()
        
        # Adjust dialog size dynamically
        self.update_idletasks()
        self.geometry(f"450x{self.winfo_height()}")
        center_window(self, self.parent)

    def show(self) -> Optional[Task]:
        """
        Displays the dialog and returns the constructed Task TypedDict or None if cancelled.
        Overrides CustomDialog's show method to return structured task data.
        """
        self.grab_set() # ADDED: Call grab_set just before waiting for the window
        self.parent.wait_window(self)
        if self.result == "add" or self.result == "save":
            task_desc: str = self.entry_var.get().strip()
            if not task_desc:
                messagebox.showerror("Error", "Task description cannot be empty.")
                return None

            xp_category: str = self.xp_category_var.get()
            xp_value: Optional[int] = None

            if xp_category == "Miscellaneous":
                manual_xp_str: str = self.manual_xp_var.get().strip()
                if manual_xp_str:
                    try:
                        xp_value = int(manual_xp_str)
                        if xp_value < 0: raise ValueError
                    except ValueError:
                        messagebox.showerror("Error", "Please enter a valid positive number for Manual XP.")
                        return None
                else:
                    xp_value = 0 # Default to 0 XP if miscellaneous and no value entered
            else:
                xp_value = self.xp_categories.get(xp_category)
                if xp_value is None: # If category exists but has None XP (e.g., custom category without default XP)
                    xp_value = 0 

            due_time_str: str = self.due_time_var.get().strip()
            if due_time_str:
                try:
                    # Validate HH:MM format
                    datetime.datetime.strptime(due_time_str, "%H:%M").time()
                except ValueError:
                    messagebox.showerror("Error", "Invalid time format. Please use HH:MM (e.g., 14:30).")
                    return None
            else:
                due_time_str = None # Store as None if empty

            # If editing, use the original ID and recurring instance flag
            task_id = self.initial_task["id"] if self.initial_task else generate_unique_id()
            is_recurring_instance = self.initial_task["is_recurring_instance"] if self.initial_task else False

            # Construct and return the Task TypedDict
            return Task(
                id=task_id,
                task=task_desc,
                done=self.initial_task["done"] if self.initial_task else False, # Preserve done status if editing
                xp=xp_value, # type: ignore # xp_value is guaranteed to be int or None here
                due_time=due_time_str,
                is_recurring_instance=is_recurring_instance
            )
        return None


class AddRecurringTaskDialog(CustomDialog):
    """
    Custom dialog for adding/editing recurring tasks.
    """
    def __init__(self, parent: tk.Tk, xp_categories: Dict[str, Optional[int]], initial_task: Optional[RecurringTask] = None):
        self.xp_categories = xp_categories
        self.initial_task = initial_task
        
        title = "Add Recurring Task" if initial_task is None else "Edit Recurring Task"
        message = "Enter task details and recurrence:"
        button_text = "Add" if initial_task is None else "Save"
        button_command = "add" if initial_task is None else "save"

        super().__init__(parent, title, message,
                         buttons=[(button_text, button_command, SUCCESS_COLOR), ("Cancel", None, ERROR_COLOR)],
                         entry_text=initial_task.get("task", "") if initial_task else "")

        self.geometry("450x450") # Adjust size for recurring task options

        # XP Category combobox
        xp_cat_frame = tk.Frame(self, bg=DARK_BG)
        xp_cat_frame.pack(pady=5)
        tk.Label(xp_cat_frame, text="XP Category:", bg=DARK_BG, fg=DARK_TEXT, font=("Segoe UI", 11)).pack(side="left", padx=5)
        
        initial_xp_category = self._get_category_from_xp(initial_task.get("xp")) if initial_task else list(self.xp_categories.keys())[0]
        self.xp_category_var = tk.StringVar(value=initial_xp_category)
        self.xp_category_combobox = ttk.Combobox(xp_cat_frame, textvariable=self.xp_category_var,
                                                 values=list(self.xp_categories.keys()), state="readonly", font=("Segoe UI", 11))
        self.xp_category_combobox.pack(side="left", padx=5)
        self.xp_category_combobox.bind("<<ComboboxSelected>>", self._on_category_selected)

        # Manual XP entry (initially hidden)
        self.manual_xp_frame = tk.Frame(self, bg=DARK_BG)
        tk.Label(self.manual_xp_frame, text="Manual XP:", bg=DARK_BG, fg=DARK_TEXT, font=("Segoe UI", 11)).pack(side="left", padx=5)
        self.manual_xp_var = tk.StringVar(value=str(initial_task["xp"]) if initial_task and initial_xp_category == "Miscellaneous" else "")
        self.manual_xp_entry = tk.Entry(self.manual_xp_frame, textvariable=self.manual_xp_var, font=("Segoe UI", 11), width=10,
                                        bg=DARK_FRAME_BG, fg=DARK_TEXT, insertbackground=ACCENT_COLOR, bd=1, relief="solid")
        self.manual_xp_entry.pack(side="left", padx=5)
        self._on_category_selected() # Call once to set initial visibility

        # Due Time entry for recurring tasks
        due_time_frame = tk.Frame(self, bg=DARK_BG)
        due_time_frame.pack(pady=5)
        tk.Label(due_time_frame, text="Due Time (HH:MM):", bg=DARK_BG, fg=DARK_TEXT, font=("Segoe UI", 11)).pack(side="left", padx=5)
        self.due_time_var = tk.StringVar(value=initial_task.get("due_time", "") if initial_task else "")
        self.due_time_entry = tk.Entry(due_time_frame, textvariable=self.due_time_var, font=("Segoe UI", 11), width=10,
                                      bg=DARK_FRAME_BG, fg=DARK_TEXT, insertbackground=ACCENT_COLOR, bd=1, relief="solid")
        self.due_time_entry.pack(side="left", padx=5)
        tk.Label(due_time_frame, text="(Optional)", bg=DARK_BG, fg=DARK_TEXT, font=("Segoe UI", 9, "italic")).pack(side="left", padx=2)


        # Recurrence Type
        recurrence_frame = tk.Frame(self, bg=DARK_BG)
        recurrence_frame.pack(pady=5)
        tk.Label(recurrence_frame, text="Recurrence:", bg=DARK_BG, fg=DARK_TEXT, font=("Segoe UI", 11)).pack(side="left", padx=5)
        
        initial_recurrence_type = initial_task.get("recurrence_type", "daily").capitalize() if initial_task else "Daily"
        self.recurrence_type_var = tk.StringVar(value=initial_recurrence_type)
        self.recurrence_type_combobox = ttk.Combobox(recurrence_frame, textvariable=self.recurrence_type_var,
                                                     values=["Daily", "Weekly"], state="readonly", font=("Segoe UI", 11))
        self.recurrence_type_combobox.pack(side="left", padx=5)
        self.recurrence_type_combobox.bind("<<ComboboxSelected>>", self._on_recurrence_type_selected)

        # Weekly Recurrence Options (initially hidden)
        self.weekly_options_frame = tk.Frame(self, bg=DARK_BG)
        self.day_checkbox_vars: Dict[str, tk.BooleanVar] = {
            "Mon": tk.BooleanVar(value=False), "Tue": tk.BooleanVar(value=False), "Wed": tk.BooleanVar(value=False),
            "Thu": tk.BooleanVar(value=False), "Fri": tk.BooleanVar(value=False), "Sat": tk.BooleanVar(value=False),
            "Sun": tk.BooleanVar(value=False)
        }
        # Pre-fill weekly options if editing
        if initial_task and initial_task.get("recurrence_type") == "weekly":
            for day in initial_task.get("recurrence_value", []): # type: ignore
                if day in self.day_checkbox_vars:
                    self.day_checkbox_vars[day].set(True)
        else: # Default for new weekly tasks
            # Set weekdays to True by default for new weekly tasks
            self.day_checkbox_vars["Mon"].set(True)
            self.day_checkbox_vars["Tue"].set(True)
            self.day_checkbox_vars["Wed"].set(True)
            self.day_checkbox_vars["Thu"].set(True)
            self.day_checkbox_vars["Fri"].set(True)

        for day, var in self.day_checkbox_vars.items():
            chk = tk.Checkbutton(self.weekly_options_frame, text=day, variable=var,
                                 bg=DARK_BG, fg=DARK_TEXT, selectcolor=ACCENT_COLOR,
                                 font=("Segoe UI", 10),
                                 activebackground=DARK_FRAME_BG, activeforeground=ACCENT_COLOR)
            chk.pack(side="left", padx=1, pady=1)
        
        self._on_recurrence_type_selected() # Call once to set initial visibility

        self.update_idletasks()
        self.geometry(f"450x{self.winfo_height()}")
        center_window(self, parent)

    def _get_category_from_xp(self, xp_value: Optional[int]) -> str:
        """Helper to find the category name for a given XP value."""
        for cat, xp in self.xp_categories.items():
            if xp == xp_value:
                return cat
        return "Miscellaneous" # Default if no exact match or if XP is None

    def _on_category_selected(self, event: Optional[tk.Event] = None) -> None:
        """Handles category combobox selection to show/hide manual XP entry."""
        selected_category: str = self.xp_category_var.get()
        if selected_category == "Miscellaneous":
            self.manual_xp_frame.pack(pady=5)
        else:
            self.manual_xp_frame.pack_forget()
        
        self.update_idletasks()
        self.geometry(f"450x{self.winfo_height()}")
        center_window(self, self.parent)

    def _on_recurrence_type_selected(self, event: Optional[tk.Event] = None) -> None:
        """Handles recurrence type combobox selection to show/hide weekly options."""
        selected_type: str = self.recurrence_type_var.get()
        if selected_type == "Weekly":
            self.weekly_options_frame.pack(pady=5)
        else:
            self.weekly_options_frame.pack_forget()
        
        self.update_idletasks()
        self.geometry(f"450x{self.winfo_height()}")
        center_window(self, self.parent)

    def show(self) -> Optional[RecurringTask]:
        """
        Displays the dialog and returns the constructed RecurringTask TypedDict or None if cancelled.
        Overrides CustomDialog's show method to return structured recurring task data.
        """
        self.grab_set() # ADDED: Call grab_set just before waiting for the window
        self.parent.wait_window(self)
        if self.result == "add" or self.result == "save":
            task_desc: str = self.entry_var.get().strip()
            if not task_desc:
                messagebox.showerror("Error", "Task description cannot be empty.")
                return None

            xp_category: str = self.xp_category_var.get()
            xp_value: Optional[int] = None
            if xp_category == "Miscellaneous":
                manual_xp_str: str = self.manual_xp_var.get().strip()
                if manual_xp_str:
                    try:
                        xp_value = int(manual_xp_str)
                        if xp_value < 0: raise ValueError
                    except ValueError:
                        messagebox.showerror("Error", "Please enter a valid positive number for Manual XP.")
                        return None
                else:
                    xp_value = 0 # Default to 0 XP if miscellaneous and no value entered
            else:
                xp_value = self.xp_categories.get(xp_category)
                if xp_value is None:
                    xp_value = 0 

            recurrence_type: str = self.recurrence_type_var.get().lower()
            recurrence_value: Optional[List[str]] = None
            if recurrence_type == "weekly":
                selected_days: List[str] = [day for day, var in self.day_checkbox_vars.items() if var.get()]
                if not selected_days:
                    messagebox.showerror("Error", "Please select at least one day for weekly recurrence.")
                    return None
                recurrence_value = selected_days
            
            due_time_str: str = self.due_time_var.get().strip()
            if due_time_str:
                try:
                    datetime.datetime.strptime(due_time_str, "%H:%M").time()
                except ValueError:
                    messagebox.showerror("Error", "Invalid time format. Please use HH:MM (e.g., 14:30).")
                    return None
            else:
                due_time_str = None

            # If editing, use the original ID; otherwise, generate a new one
            task_id = self.initial_task["id"] if self.initial_task else generate_unique_id()

            # Construct and return the RecurringTask TypedDict
            return RecurringTask(
                id=task_id,
                task=task_desc,
                xp=xp_value, # type: ignore
                recurrence_type=recurrence_type,
                recurrence_value=recurrence_value,
                due_time=due_time_str,
                last_generated_date=self.initial_task.get("last_generated_date") if self.initial_task else None
            )
        return None


class ManageRecurringTasksWindow(tk.Toplevel):
    """
    A window to display, edit, and delete recurring tasks.
    """
    def __init__(self, parent: tk.Tk, app_instance: 'XPDashboardApp'):
        super().__init__(parent)
        self.parent = parent
        self.app = app_instance
        self.title("Manage Recurring Tasks")
        self.geometry("600x500")
        self.configure(bg=DARK_BG)
        self.transient(parent)
        # self.grab_set() # MOVED: This call is moved to after UI elements are packed
        
        center_window(self, parent)

        tk.Label(self, text="Your Recurring Tasks", font=("Segoe UI", 16, "bold"), bg=DARK_BG, fg=ACCENT_COLOR).pack(pady=10)

        self.canvas = tk.Canvas(self, bg=DARK_FRAME_BG, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=DARK_FRAME_BG)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        self.scrollbar.pack(side="right", fill="y")

        self.populate_recurring_list()

        tk.Button(self, text="Close", command=self.destroy,
                  bg=ACCENT_COLOR, fg=DARK_BG, font=("Segoe UI", 11, "bold"), relief="flat", padx=10, pady=5,
                  activebackground="#4a8ec9", activeforeground=DARK_TEXT).pack(pady=10)
        
        self.grab_set() # ADDED: Call grab_set after all UI elements are packed

    def populate_recurring_list(self) -> None:
        """Populates the list of recurring tasks in the window."""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        if not self.app.recurring_tasks:
            tk.Label(self.scrollable_frame, text="No recurring tasks defined yet.", bg=DARK_FRAME_BG, fg=DARK_TEXT, font=("Segoe UI", 12)).pack(pady=20)
            return

        for i, r_task in enumerate(self.app.recurring_tasks):
            task_row_frame = tk.Frame(self.scrollable_frame, bg=DARK_FRAME_BG, bd=1, relief="solid")
            task_row_frame.grid(row=i, column=0, sticky="ew", pady=2, padx=5)
            self.scrollable_frame.grid_columnconfigure(0, weight=1)

            task_text = f"{r_task['task']} ({r_task['xp']} XP) - "
            if r_task['recurrence_type'] == 'daily':
                task_text += "Daily"
            elif r_task['recurrence_type'] == 'weekly':
                days = ", ".join(r_task['recurrence_value']) # type: ignore
                task_text += f"Weekly ({days})"
            if r_task.get("due_time"):
                task_text += f" @ {r_task['due_time']}"
            
            tk.Label(task_row_frame, text=task_text, font=("Segoe UI", 12), bg=DARK_FRAME_BG, fg=DARK_TEXT, wraplength=400, anchor="w").grid(row=0, column=0, sticky="w", padx=10, pady=5)

            edit_btn = tk.Button(task_row_frame, text="✏️", font=("Segoe UI", 11),
                                 bg=WARNING_COLOR, fg=DARK_BG, relief="flat", padx=5, pady=2,
                                 command=lambda t_id=r_task['id']: self.app.edit_recurring_task(t_id, self.populate_recurring_list),
                                 activebackground="#c7a35e", activeforeground=DARK_TEXT)
            edit_btn.grid(row=0, column=1, padx=(0, 5))

            del_btn = tk.Button(task_row_frame, text="🗑️", font=("Segoe UI", 11),
                                 bg=ERROR_COLOR, fg="white", relief="flat", padx=5, pady=2,
                                 command=lambda t_id=r_task['id']: self.app.delete_recurring_task(t_id, self.populate_recurring_list),
                                 activebackground="#a03d45", activeforeground="white")
            del_btn.grid(row=0, column=2, padx=(0, 5))

            task_row_frame.grid_columnconfigure(0, weight=1)
            task_row_frame.grid_columnconfigure(1, weight=0)
            task_row_frame.grid_columnconfigure(2, weight=0)

        self.canvas.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

class XPHistoryWindow(tk.Toplevel):
    """
    A window to display the history of daily XP earned.
    """
    def __init__(self, parent: tk.Tk, tasks_data: Dict[str, Dict[str, Task]], app_instance: 'XPDashboardApp'):
        super().__init__(parent)
        self.parent = parent
        self.app = app_instance # Store app instance for access to its methods (e.g., edit_task)
        self.title("XP History")
        self.geometry("450x600")
        self.configure(bg=DARK_BG)
        self.transient(parent)
        # self.grab_set() # MOVED: This call is moved to after UI elements are packed

        center_window(self, parent)

        tk.Label(self, text="Daily XP Earned History", font=("Segoe UI", 16, "bold"), bg=DARK_BG, fg=ACCENT_COLOR).pack(pady=10)

        self.canvas = tk.Canvas(self, bg=DARK_FRAME_BG, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=DARK_FRAME_BG)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        self.scrollbar.pack(side="right", fill="y")

        self.tasks_data = tasks_data
        self._display_history()

        self.grab_set() # ADDED: Call grab_set after all UI elements are packed

    def _display_history(self) -> None:
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        dates = [d for d in self.tasks_data.keys() if not d.startswith('_')]
        dates.sort(key=lambda d: datetime.datetime.strptime(d, "%Y-%m-%d"), reverse=True)

        if not dates:
            tk.Label(self.scrollable_frame, text="No XP history available yet.", bg=DARK_FRAME_BG, fg=DARK_TEXT, font=("Segoe UI", 12)).pack(pady=20)
            return

        for date_str in dates:
            daily_tasks: Dict[str, Task] = self.tasks_data.get(date_str, {})
            # Calculate daily XP from completed tasks for that date
            daily_xp: int = sum(t['xp'] for t in daily_tasks.values() if t['done'])

            # Frame for each date's summary
            date_summary_frame = tk.Frame(self.scrollable_frame, bg=DARK_FRAME_BG, bd=1, relief="solid")
            date_summary_frame.pack(fill="x", padx=5, pady=5)

            # Date and XP Earned labels
            tk.Label(date_summary_frame, text=f"Date: {date_str}", font=("Segoe UI", 11, "bold"), bg=DARK_FRAME_BG, fg=ACCENT_COLOR).pack(anchor="w", padx=5, pady=2)
            tk.Label(date_summary_frame, text=f"XP Earned: {daily_xp}", font=("Segoe UI", 11), bg=DARK_FRAME_BG, fg=DARK_TEXT).pack(anchor="w", padx=5, pady=2)
            
            # Frame for individual tasks of the day
            tasks_list_frame = tk.Frame(date_summary_frame, bg=DARK_FRAME_BG)
            tasks_list_frame.pack(fill="x", padx=10, pady=2)

            # Display individual tasks for the day
            if daily_tasks:
                tk.Label(tasks_list_frame, text="Tasks:", font=("Segoe UI", 10, "italic"), bg=DARK_FRAME_BG, fg=DARK_TEXT).pack(anchor="w", padx=5, pady=2)
                
                # Sort tasks by completion status (done first) then alphabetically
                sorted_daily_tasks: List[Task] = sorted(daily_tasks.values(), key=lambda t: (not t['done'], t['task'].lower()))

                for task in sorted_daily_tasks:
                    task_display_text = f"[{'✔️' if task['done'] else ' '}] {task['task']} ({task['xp']} XP)"
                    if task.get("due_time"):
                        task_display_text += f" @ {task['due_time']}"
                    if task.get("is_recurring_instance"):
                        task_display_text += " (R)"

                    task_row = tk.Frame(tasks_list_frame, bg=DARK_FRAME_BG)
                    task_row.pack(fill="x", pady=1)

                    task_label = tk.Label(task_row, text=task_display_text, font=("Segoe UI", 10), bg=DARK_FRAME_BG, fg=DARK_TEXT, wraplength=300, anchor="w")
                    task_label.pack(side="left", fill="x", expand=True)

                    # Add Edit button for each task
                    edit_btn = tk.Button(task_row, text="✏️", font=("Segoe UI", 9),
                                         bg=WARNING_COLOR, fg=DARK_BG, relief="flat", padx=3, pady=1,
                                         command=lambda t_id=task['id'], d_str=date_str: self._edit_task_from_history(t_id, d_str),
                                         activebackground="#c7a35e", activeforeground=DARK_TEXT)
                    edit_btn.pack(side="right", padx=(5,0))
            else:
                tk.Label(tasks_list_frame, text="No tasks recorded for this day.", font=("Segoe UI", 10, "italic"), bg=DARK_FRAME_BG, fg=DARK_TEXT).pack(anchor="w", padx=5, pady=2)
            
            tk.Frame(self.scrollable_frame, height=1, bg=DARK_TEXT).pack(fill="x", padx=5, pady=5) # Separator

        self.canvas.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

    def _edit_task_from_history(self, task_id: str, date_str: str) -> None:
        """
        Handles editing a task directly from the history window.
        Switches the main app's date and then calls its edit_task method.
        """
        # First, change the main app's current date to the date of the task
        if self.app.current_date != date_str:
            self.app.current_date = date_str
            self.app.date_btn.config(text=f"Select Date ({self.app.current_date})")
            self.app._load_app_state() # Reload tasks for the selected date
            self.app.populate_tasks() # Refresh main UI

        # Then, call the main app's edit_task method with the task ID
        self.app.edit_task(task_id)
        # After editing in the main window, refresh this history window
        self.tasks_data = self.app.data_manager.load_tasks_data() # Reload data to reflect changes
        self._display_history() # Re-display history

