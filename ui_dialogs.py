# ui_dialogs.py
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import datetime
import calendar
import uuid # Used for generating unique IDs for tasks
from enum import Enum # Used for FilterMode in CalendarDialog (though FilterMode itself is in utils)

# Import matplotlib for plotting and FigureCanvasTkAgg for embedding in Tkinter
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Import constants for consistent styling
from constants import DARK_BG, DARK_FRAME_BG, DARK_TEXT, ACCENT_COLOR, ERROR_COLOR, SUCCESS_COLOR, WARNING_COLOR

# Import utility functions like center_window and FilterMode
from utils import center_window, FilterMode

# Try importing plyer for system notifications, provide a Tkinter messagebox fallback
try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False


class CustomDialog(tk.Toplevel):
    """
    A base class for creating custom themed dialogs.
    Provides a consistent look and feel for messages and inputs across the application.
    """
    def __init__(self, parent: tk.Tk, title: str, message: str, buttons: list = None, entry_text: str = None, combobox_values: list = None, initial_combobox_value: str = None, checkbox_options: dict = None):
        super().__init__(parent)
        self.parent = parent
        self.title(title)
        self.geometry("400x200") # Default size, can be adjusted by subclasses
        self.configure(bg=DARK_BG)
        self.transient(parent) # Make dialog transient to its parent window
        self.result = None # Stores the result of the dialog (e.g., button clicked, data)

        # Display the main message of the dialog
        tk.Label(self, text=message, bg=DARK_BG, fg=DARK_TEXT, font=("Segoe UI", 12), wraplength=350).pack(pady=10)

        # Optional: Add an entry field if entry_text is provided
        if entry_text is not None:
            self.entry_var = tk.StringVar(value=entry_text)
            self.entry = tk.Entry(self, textvariable=self.entry_var, font=("Segoe UI", 12), width=40,
                                  bg=DARK_FRAME_BG, fg=DARK_TEXT, insertbackground=ACCENT_COLOR, bd=1, relief="solid")
            self.entry.pack(pady=5)
            # Bind Enter key to the first button's command if buttons are provided
            if buttons and buttons[0]:
                self.bind("<Return>", lambda e: self._on_button_click(buttons[0][1]))

        if combobox_values is not None:
            self.combobox_var = tk.StringVar(value=initial_combobox_value or combobox_values[0])
            self.combobox = ttk.Combobox(self, textvariable=self.combobox_var, values=combobox_values, state="readonly", font=("Segoe UI", 11))
            self.combobox.pack(pady=5)

        self.checkbox_vars = {}
        if checkbox_options:
            chk_frame = tk.Frame(self, bg=DARK_BG)
            chk_frame.pack(pady=5)
            for text, initial_value in checkbox_options.items():
                var = tk.BooleanVar(value=initial_value)
                chk = tk.Checkbutton(chk_frame, text=text, variable=var,
                                     bg=DARK_BG, fg=DARK_TEXT, selectcolor=ACCENT_COLOR,
                                     font=("Segoe UI", 10), activebackground=DARK_FRAME_BG, activeforeground=ACCENT_COLOR)
                chk.pack(side="left", padx=2, pady=2)
                self.checkbox_vars[text] = var

        # Frame for dialog buttons
        btn_frame = tk.Frame(self, bg=DARK_BG)
        btn_frame.pack(pady=10)

        # Add buttons based on the 'buttons' list
        if buttons:
            for btn_text, btn_command, btn_color in buttons:
                tk.Button(btn_frame, text=btn_text, command=lambda cmd=btn_command: self._on_button_click(cmd),
                          bg=btn_color, fg=DARK_BG if btn_color != ERROR_COLOR else "white",
                          font=("Segoe UI", 11, "bold"), relief="flat", padx=10, pady=5,
                          activebackground=btn_color if btn_color != ERROR_COLOR else "#a03d45",
                          activeforeground=DARK_TEXT if btn_color != ERROR_COLOR else "white"
                          ).pack(side="left", padx=5)
        
        # Protocol for handling window close event (e.g., clicking X button)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_button_click(self, command: any) -> None:
        """Handles a button click within the dialog, sets the result, and destroys the window."""
        self.result = command
        self.destroy()

    def _on_close(self) -> None:
        """Handles the dialog being closed by the user (e.g., via X button), sets result to None."""
        self.result = None
        self.destroy()

    def show(self) -> any:
        """
        Displays the dialog, centers it, sets focus, and waits for user interaction.
        Returns the result set by button clicks or None if closed.
        """
        self.update_idletasks() # Ensure widgets are rendered for accurate size calculation
        center_window(self, self.parent) # Center the dialog relative to its parent
        self.grab_set() # Grab all input events, making the dialog modal
        self.focus_set() # Set keyboard focus to the dialog
        self.parent.wait_window(self) # Pause parent window execution until this dialog is destroyed
        return self.result

class CalendarDialog(tk.Toplevel):
    """
    A custom calendar dialog for selecting dates.
    Allows users to navigate months and select a specific date.
    """
    def __init__(self, parent: tk.Tk, initial_date: datetime.date = None):
        super().__init__(parent)
        self.parent = parent
        self.title("Select Date")
        self.configure(bg=DARK_BG)
        self.transient(parent)
        self.grab_set() # Make the calendar modal
        self.result_date = None # Stores the selected date

        # Initialize current year and month for the calendar display
        self.current_year = initial_date.year if initial_date else datetime.date.today().year
        self.current_month = initial_date.month if initial_date else datetime.date.today().month

        center_window(self, parent) # Center the calendar dialog

        self._create_widgets() # Build the UI elements
        self._show_calendar() # Populate the calendar grid

    def _create_widgets(self) -> None:
        """Creates the header (month/year, navigation buttons) and day grid frames."""
        header_frame = tk.Frame(self, bg=DARK_FRAME_BG)
        header_frame.pack(pady=10, padx=10, fill="x")

        # Previous month button
        tk.Button(header_frame, text="<", command=self._prev_month,
                  bg=ACCENT_COLOR, fg=DARK_BG, font=("Segoe UI", 10, "bold"), relief="flat",
                  activebackground="#4a8ec9", activeforeground=DARK_TEXT).pack(side="left", padx=5)
        
        # Label to display current month and year
        self.month_year_label = tk.Label(header_frame, text="", font=("Segoe UI", 14, "bold"), bg=DARK_FRAME_BG, fg=DARK_TEXT)
        self.month_year_label.pack(side="left", expand=True)

        # Next month button
        tk.Button(header_frame, text=">", command=self._next_month,
                  bg=ACCENT_COLOR, fg=DARK_BG, font=("Segoe UI", 10, "bold"), relief="flat",
                  activebackground="#4a8ec9", activeforeground=DARK_TEXT).pack(side="right", padx=5)

        # Weekdays header (Mo, Tu, We, etc.)
        weekdays_frame = tk.Frame(self, bg=DARK_FRAME_BG)
        weekdays_frame.pack(padx=10, fill="x")
        week_days = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
        for day in week_days:
            tk.Label(weekdays_frame, text=day, font=("Segoe UI", 10, "bold"), bg=DARK_FRAME_BG, fg=ACCENT_COLOR, width=4).pack(side="left", padx=1)

        # Frame to hold the day buttons (calendar grid)
        self.calendar_frame = tk.Frame(self, bg=DARK_BG)
        self.calendar_frame.pack(padx=10, pady=5)

        # Bottom buttons (Today, Cancel)
        button_frame = tk.Frame(self, bg=DARK_BG)
        button_frame.pack(pady=10)
        tk.Button(button_frame, text="Today", command=self._select_today,
                  bg=WARNING_COLOR, fg=DARK_BG, font=("Segoe UI", 11, "bold"), relief="flat", padx=10, pady=5,
                  activebackground="#c7a35e", activeforeground=DARK_TEXT).pack(side="left", padx=5)
        tk.Button(button_frame, text="Cancel", command=self._on_close,
                  bg=ERROR_COLOR, fg="white", font=("Segoe UI", 11, "bold"), relief="flat", padx=10, pady=5,
                  activebackground="#a03d45", activeforeground="white").pack(side="right", padx=5)

    def _show_calendar(self) -> None:
        """Populates the calendar grid with day buttons for the current month."""
        # Clear existing day widgets
        for widget in self.calendar_frame.winfo_children():
            widget.destroy()

        # Update month/year label
        self.month_year_label.config(text=f"{calendar.month_name[self.current_month]} {self.current_year}")

        # Get month's days arranged by week, starting Monday
        cal = calendar.Calendar(firstweekday=calendar.MONDAY)
        month_days = cal.monthdayscalendar(self.current_year, self.current_month)

        for week_idx, week in enumerate(month_days):
            for day_idx, day in enumerate(week):
                if day == 0:
                    # Empty label for days outside the current month
                    tk.Label(self.calendar_frame, text="", bg=DARK_BG, width=4).grid(row=week_idx, column=day_idx, padx=1, pady=1)
                else:
                    date_obj = datetime.date(self.current_year, self.current_month, day)
                    btn = tk.Button(self.calendar_frame, text=str(day),
                                    command=lambda d=date_obj: self._select_date(d), # Pass the date object to the command
                                    font=("Segoe UI", 10), width=4, height=2,
                                    bg=DARK_FRAME_BG, fg=DARK_TEXT, relief="flat",
                                    activebackground=ACCENT_COLOR, activeforeground=DARK_BG)
                    
                    # Highlight today's date
                    if date_obj == datetime.date.today():
                        btn.config(bg=ACCENT_COLOR, fg=DARK_BG, font=("Segoe UI", 10, "bold"),
                                   activebackground="#4a8ec9", activeforeground=DARK_TEXT)
                    # Highlight the currently selected date in the main app (if applicable)
                    elif hasattr(self.parent, 'current_date') and date_obj.strftime("%Y-%m-%d") == self.parent.current_date:
                        btn.config(bg=WARNING_COLOR, fg=DARK_BG, font=("Segoe UI", 10, "bold"),
                                   activebackground="#c7a35e", activeforeground=DARK_TEXT)
                    else:
                        btn.config(activebackground=DARK_TEXT, activeforeground=DARK_FRAME_BG)

                    btn.grid(row=week_idx, column=day_idx, padx=1, pady=1)

    def _prev_month(self) -> None:
        """Navigates to the previous month and updates the calendar display."""
        self.current_month -= 1
        if self.current_month < 1:
            self.current_month = 12
            self.current_year -= 1
        self._show_calendar()

    def _next_month(self) -> None:
        """Navigates to the next month and updates the calendar display."""
        self.current_month += 1
        if self.current_month > 12:
            self.current_month = 1
            self.current_year += 1
        self._show_calendar()

    def _select_date(self, date_obj: datetime.date) -> None:
        """Sets the selected date and closes the dialog."""
        self.result_date = date_obj.strftime("%Y-%m-%d")
        self.destroy()

    def _on_close(self) -> None:
        """Handles dialog closure without selecting a date."""
        self.result_date = None
        self.destroy()

    def show(self) -> str | None:
        """Displays the calendar dialog and returns the selected date string or None."""
        self.parent.wait_window(self) # Wait for the dialog to be closed
        return self.result_date

class XPHistoryWindow(tk.Toplevel):
    """
    A window to display the history of daily XP earned, including a trend chart.
    Shows XP earned per day and a list of completed tasks for each day.
    Allows editing and deleting tasks directly from history.
    """
    def __init__(self, parent: tk.Tk, tasks_data: dict, app_instance: 'XPDashboardApp'):
        super().__init__(parent)
        self.parent = parent
        self.tasks_data = tasks_data # Raw tasks data loaded from JSON
        self.app_instance = app_instance # Reference to the main application instance
        
        self.title("XP History")
        self.geometry("700x700") # Increased size to accommodate the chart
        self.configure(bg=DARK_BG)
        self.transient(parent)
        self.grab_set() # Make the history window modal

        center_window(self, parent)

        tk.Label(self, text="Daily XP Earned History", font=("Segoe UI", 16, "bold"), bg=DARK_BG, fg=ACCENT_COLOR).pack(pady=10)

        # Frame for the Matplotlib chart
        chart_frame = tk.Frame(self, bg=DARK_FRAME_BG, bd=2, relief="groove")
        chart_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self._plot_xp_history(chart_frame) # Plot the XP history chart

        # Canvas and Scrollbar for scrollable history display
        self.canvas = tk.Canvas(self, bg=DARK_FRAME_BG, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=DARK_FRAME_BG)

        # Configure scrollable frame to update canvas scroll region
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        self.scrollbar.pack(side="right", fill="y")

        self._display_history() # Populate the history display (textual list)

    def _plot_xp_history(self, parent_frame: tk.Frame) -> None:
        """
        Generates and embeds a Matplotlib chart showing daily XP trend.
        """
        dates = []
        xp_values = []

        # Extract daily XP data
        all_dates_in_data = [d for d in self.tasks_data.keys() if not d.startswith('_')]
        all_dates_in_data.sort(key=lambda d: datetime.datetime.strptime(d, "%Y-%m-%d")) # Sort chronologically

        for date_str in all_dates_in_data:
            daily_tasks_raw = self.tasks_data.get(date_str, {})
            daily_tasks = list(daily_tasks_raw.values()) if isinstance(daily_tasks_raw, dict) else daily_tasks_raw
            daily_xp = sum(t['xp'] for t in daily_tasks if t['done'])
            
            dates.append(datetime.datetime.strptime(date_str, "%Y-%m-%d"))
            xp_values.append(daily_xp)

        if not dates:
            tk.Label(parent_frame, text="No XP data to plot yet.", bg=DARK_FRAME_BG, fg=DARK_TEXT, font=("Segoe UI", 12)).pack(pady=20)
            return

        # Create a Matplotlib figure and axis
        fig, ax = plt.subplots(figsize=(6, 3), facecolor=DARK_FRAME_BG)
        ax.plot(dates, xp_values, marker='o', linestyle='-', color=ACCENT_COLOR)

        # Customize plot appearance for dark theme
        ax.set_facecolor(DARK_BG)
        fig.patch.set_facecolor(DARK_FRAME_BG) # Background of the figure itself

        ax.tick_params(axis='x', colors=DARK_TEXT) # X-axis tick labels color
        ax.tick_params(axis='y', colors=DARK_TEXT) # Y-axis tick labels color
        ax.xaxis.label.set_color(DARK_TEXT) # X-axis label color
        ax.yaxis.label.set_color(DARK_TEXT) # Y-axis label color
        ax.title.set_color(DARK_TEXT) # Title color
        ax.spines['bottom'].set_color(DARK_TEXT) # X-axis line color
        ax.spines['left'].set_color(DARK_TEXT) # Y-axis line color
        ax.spines['top'].set_visible(False) # Hide top spine
        ax.spines['right'].set_visible(False) # Hide right spine

        ax.set_xlabel("Date")
        ax.set_ylabel("XP Earned")
        ax.set_title("Daily XP Trend")
        plt.xticks(rotation=45, ha='right') # Rotate x-axis labels for readability
        plt.tight_layout() # Adjust layout to prevent labels overlapping

        # Embed the Matplotlib figure into the Tkinter frame
        canvas_tk = FigureCanvasTkAgg(fig, master=parent_frame)
        canvas_tk_widget = canvas_tk.get_tk_widget()
        canvas_tk_widget.pack(fill="both", expand=True)
        canvas_tk.draw()


    def _display_history(self) -> None:
        """Populates the history window with daily XP records (textual list)."""
        # Clear existing widgets
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # Get all date keys from tasks_data, excluding internal keys (like _level, _total_xp)
        dates = [d for d in self.tasks_data.keys() if not d.startswith('_')]
        # Sort dates in reverse chronological order
        dates.sort(key=lambda d: datetime.datetime.strptime(d, "%Y-%m-%d"), reverse=True)

        if not dates:
            tk.Label(self.scrollable_frame, text="No XP history available yet.", bg=DARK_FRAME_BG, fg=DARK_TEXT, font=("Segoe UI", 12)).pack(pady=20)
            return

        for date_str in dates:
            # Retrieve tasks for the current date. Handle both old list format and new dict format.
            daily_tasks_raw = self.tasks_data.get(date_str, {})
            # Ensure daily_tasks is a dictionary, even if it was stored as a list (for old data migration)
            daily_tasks_dict = daily_tasks_raw if isinstance(daily_tasks_raw, dict) else {t.get('id', str(uuid.uuid4())): t for t in daily_tasks_raw}

            # Calculate total XP earned for this specific day
            daily_xp = sum(t['xp'] for t in daily_tasks_dict.values() if t['done'])

            # Create a frame for each day's summary
            frame = tk.Frame(self.scrollable_frame, bg=DARK_FRAME_BG, bd=2, relief="groove")
            frame.pack(fill="x", padx=5, pady=5)

            # Display date and XP earned
            tk.Label(frame, text=f"Date: {date_str}", font=("Segoe UI", 12, "bold"), bg=DARK_FRAME_BG, fg=ACCENT_COLOR).pack(anchor="w", padx=10, pady=3)
            tk.Label(frame, text=f"XP Earned: {daily_xp}", font=("Segoe UI", 12), bg=DARK_FRAME_BG, fg=DARK_TEXT).pack(anchor="w", padx=10, pady=3)
            
            # List completed tasks for the day with edit/delete buttons
            completed_tasks_for_display = [t for t in daily_tasks_dict.values() if t['done']]
            if completed_tasks_for_display:
                tk.Label(frame, text="Completed Tasks:", font=("Segoe UI", 11, "italic"), bg=DARK_FRAME_BG, fg=DARK_TEXT).pack(anchor="w", padx=15)
                
                for task in completed_tasks_for_display:
                    task_row_in_history_frame = tk.Frame(frame, bg=DARK_FRAME_BG)
                    task_row_in_history_frame.pack(fill="x", padx=20, pady=2)
                    
                    task_display_text = f"- {task['task']} ({task['xp']} XP)"
                    if task.get("due_time"):
                        task_display_text += f" @ {task['due_time']}"

                    tk.Label(task_row_in_history_frame, text=task_display_text, font=("Segoe UI", 11), bg=DARK_FRAME_BG, fg=DARK_TEXT, wraplength=300, anchor="w").pack(side="left", fill="x", expand=True)

                    # Edit button for task in history
                    edit_btn = tk.Button(task_row_in_history_frame, text="✏️", font=("Segoe UI", 9),
                                         bg=WARNING_COLOR, fg=DARK_BG, relief="flat", padx=3, pady=1,
                                         command=lambda d=date_str, t_id=task['id']: self._edit_task_from_history(d, t_id),
                                         activebackground="#c7a35e", activeforeground=DARK_TEXT)
                    edit_btn.pack(side="left", padx=(5, 2))

                    # Delete button for task in history
                    del_btn = tk.Button(task_row_in_history_frame, text="🗑️", font=("Segoe UI", 9),
                                         bg=ERROR_COLOR, fg="white", relief="flat", padx=3, pady=1,
                                         command=lambda d=date_str, t_id=task['id']: self._delete_task_from_history(d, t_id),
                                         activebackground="#a03d45", activeforeground="white")
                    del_btn.pack(side="left", padx=(0, 5))
            else:
                tk.Label(frame, text="No completed tasks for this day.", font=("Segoe UI", 11, "italic"), bg=DARK_FRAME_BG, fg=DARK_TEXT).pack(anchor="w", padx=15)
            
            # Separator line between daily entries
            tk.Frame(self.scrollable_frame, height=1, bg=DARK_TEXT).pack(fill="x", padx=5, pady=5)

        # Update canvas scroll region after all widgets are packed
        self.canvas.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

    def _edit_task_from_history(self, date_str: str, task_id: str) -> None:
        """
        Handles editing a task from the history window.
        Changes the main app's current date, then calls the main app's edit_task.
        """
        # Change the main app's current date to the date of the task
        # This will trigger app._load_app_state() and app.populate_tasks()
        self.app_instance.current_date = date_str
        self.app_instance.date_btn.config(text=f"Select Date ({self.app_instance.current_date})")
        self.app_instance._load_app_state()
        self.app_instance.populate_tasks()

        # Now, call the main app's edit_task method for the specific task
        # The main app's UI will update to show the task details dialog
        self.app_instance.edit_task(task_id)

        # After editing, refresh the history window to reflect changes
        self.tasks_data = self.app_instance.data_manager.load_tasks_data() # Reload data
        self._display_history() # Re-render history list
        self._plot_xp_history(self.winfo_children()[1]) # Re-plot chart (assuming chart_frame is the second child)


    def _delete_task_from_history(self, date_str: str, task_id: str) -> None:
        """
        Handles deleting a task from the history window.
        Changes the main app's current date, then calls the main app's delete_task.
        """
        # Change the main app's current date to the date of the task
        # This will trigger app._load_app_state() and app.populate_tasks()
        self.app_instance.current_date = date_str
        self.app_instance.date_btn.config(text=f"Select Date ({self.app_instance.current_date})")
        self.app_instance._load_app_state()
        self.app_instance.populate_tasks()

        # Now, call the main app's delete_task method for the specific task
        # The main app's UI will update
        self.app_instance.delete_task(task_id)

        # After deleting, refresh the history window to reflect changes
        self.tasks_data = self.app_instance.data_manager.load_tasks_data() # Reload data
        self._display_history() # Re-render history list
        self._plot_xp_history(self.winfo_children()[1]) # Re-plot chart


class AddRecurringTaskDialog(CustomDialog):
    """
    Custom dialog for adding or editing recurring tasks.
    Extends CustomDialog to include specific fields for recurring task details.
    """
    def __init__(self, parent: tk.Tk, xp_categories: dict, initial_task: dict = None):
        self.xp_categories = xp_categories
        self.initial_task = initial_task or {} # Ensure initial_task is always a dictionary
        
        # Determine dialog title and button text based on whether it's an add or edit operation
        title = "Add Recurring Task" if initial_task is None else "Edit Recurring Task"
        message = "Enter task details and recurrence:" if initial_task is None else "Edit task details and recurrence:"
        button_text = "Add" if initial_task is None else "Save"
        button_command = "add" if initial_task is None else "save"

        # Initialize the base CustomDialog with common elements
        super().__init__(parent, title, message,
                         buttons=[(button_text, button_command, SUCCESS_COLOR), ("Cancel", None, ERROR_COLOR)],
                         entry_text=self.initial_task.get("task", "") if initial_task else "")

        # XP Category selection
        xp_cat_frame = tk.Frame(self, bg=DARK_BG)
        xp_cat_frame.pack(pady=5)
        tk.Label(xp_cat_frame, text="XP Category:", bg=DARK_BG, fg=DARK_TEXT, font=("Segoe UI", 11)).pack(side="left", padx=5)
        
        # Determine initial XP category value
        initial_xp_category = list(self.xp_categories.keys())[0] # Default to first category
        if initial_task:
            for cat, xp_val in self.xp_categories.items():
                if xp_val == initial_task.get("xp"):
                    initial_xp_category = cat
                    break
            else:
                initial_xp_category = "Miscellaneous" # Fallback if XP value doesn't match a category

        self.xp_category_var = tk.StringVar(value=initial_xp_category)
        self.xp_category_combobox = ttk.Combobox(xp_cat_frame, textvariable=self.xp_category_var,
                                                 values=list(self.xp_categories.keys()), state="readonly", font=("Segoe UI", 11))
        self.xp_category_combobox.pack(side="left", padx=5)
        self.xp_category_combobox.bind("<<ComboboxSelected>>", self._on_category_selected)

        # Manual XP entry (visible only if "Miscellaneous" category is selected)
        self.manual_xp_frame = tk.Frame(self, bg=DARK_BG)
        tk.Label(self.manual_xp_frame, text="Manual XP:", bg=DARK_BG, fg=DARK_TEXT, font=("Segoe UI", 11)).pack(side="left", padx=5)
        self.manual_xp_var = tk.StringVar(value=str(initial_task.get("xp", "")) if initial_task and initial_xp_category == "Miscellaneous" else "")
        self.manual_xp_entry = tk.Entry(self.manual_xp_frame, textvariable=self.manual_xp_var, font=("Segoe UI", 11), width=10,
                                        bg=DARK_FRAME_BG, fg=DARK_TEXT, insertbackground=ACCENT_COLOR, bd=1, relief="solid")
        self.manual_xp_entry.pack(side="left", padx=5)
        self._on_category_selected() # Call once to set initial visibility based on initial_xp_category

        # Recurrence type selection (Daily/Weekly)
        recurrence_frame = tk.Frame(self, bg=DARK_BG)
        recurrence_frame.pack(pady=5)
        tk.Label(recurrence_frame, text="Recurrence:", bg=DARK_BG, fg=DARK_TEXT, font=("Segoe UI", 11)).pack(side="left", padx=5)
        
        initial_recurrence_type = initial_task.get("recurrence_type", "daily").capitalize() if initial_task else "Daily"
        self.recurrence_type_var = tk.StringVar(value=initial_recurrence_type)
        self.recurrence_type_combobox = ttk.Combobox(recurrence_frame, textvariable=self.recurrence_type_var,
                                                     values=["Daily", "Weekly"], state="readonly", font=("Segoe UI", 11))
        self.recurrence_type_combobox.pack(side="left", padx=5)
        self.recurrence_type_combobox.bind("<<ComboboxSelected>>", self._on_recurrence_type_selected)

        # Weekly options (checkboxes for days of the week)
        self.weekly_options_frame = tk.Frame(self, bg=DARK_BG)
        self.day_checkbox_vars = {
            "Mon": tk.BooleanVar(value=False), "Tue": tk.BooleanVar(value=False), "Wed": tk.BooleanVar(value=False),
            "Thu": tk.BooleanVar(value=False), "Fri": tk.BooleanVar(value=False), "Sat": tk.BooleanVar(value=False),
            "Sun": tk.BooleanVar(value=False)
        }
        # Set initial values for weekly checkboxes if editing an existing weekly task
        if initial_task and initial_task.get("recurrence_type") == "weekly":
            for day in initial_task.get("recurrence_value", []):
                if day in self.day_checkbox_vars:
                    self.day_checkbox_vars[day].set(True)
        else:
            # Default to weekdays if adding a new task
            self.day_checkbox_vars["Mon"].set(True)
            self.day_checkbox_vars["Tue"].set(True)
            self.day_checkbox_vars["Wed"].set(True)
            self.day_checkbox_vars["Thu"].set(True)
            self.day_checkbox_vars["Fri"].set(True)

        for day, var in self.day_checkbox_vars.items():
            chk = tk.Checkbutton(self.weekly_options_frame, text=day, variable=var,
                                 bg=DARK_BG, fg=DARK_TEXT, selectcolor=ACCENT_COLOR,
                                 font=("Segoe UI", 10), activebackground=DARK_FRAME_BG, activeforeground=ACCENT_COLOR)
            chk.pack(side="left", padx=1, pady=1)
        
        self._on_recurrence_type_selected() # Call once to set initial visibility of weekly options

        # Error message label
        self.error_label = tk.Label(self, text="", fg=ERROR_COLOR, bg=DARK_BG, font=("Segoe UI", 10, "bold"), wraplength=350)
        self.error_label.pack(pady=(0, 5))

        # Adjust dialog size and center it after all widgets are packed
        self.update_idletasks()
        self.geometry(f"450x{self.winfo_height()}")
        center_window(self, parent)

    def _display_error(self, message: str) -> None:
        """Displays an error message in the dialog's error label."""
        self.error_label.config(text=message)

    def _on_category_selected(self, event=None):
        """Shows/hides the manual XP entry based on the selected XP category."""
        selected_category = self.xp_category_var.get()
        if selected_category == "Miscellaneous":
            self.manual_xp_frame.pack(pady=5)
        else:
            self.manual_xp_frame.pack_forget()
        # Re-adjust dialog size and center after visibility change
        self.update_idletasks()
        self.geometry(f"450x{self.winfo_height()}")
        center_window(self, self.parent)

    def _on_recurrence_type_selected(self, event=None):
        """Shows/hides weekly day checkboxes based on the selected recurrence type."""
        selected_type = self.recurrence_type_var.get()
        if selected_type == "Weekly":
            self.weekly_options_frame.pack(pady=5)
        else:
            self.weekly_options_frame.pack_forget()
        # Re-adjust dialog size and center after visibility change
        self.update_idletasks()
        self.geometry(f"450x{self.winfo_height()}")
        center_window(self, self.parent)

    def _get_validated_data(self) -> dict:
        """
        Collects and returns the task details after input validation has passed.
        This method is called ONLY after validate_input returns True.
        """
        task_desc = self.entry_var.get().strip()
        xp_category = self.xp_category_var.get()
        xp_value = None
        if xp_category == "Miscellaneous":
            xp_value = int(self.manual_xp_var.get())
        else:
            xp_value = self.xp_categories.get(xp_category)
            if xp_value is None: # Fallback for categories with no predefined XP
                xp_value = 0
        
        # Assign a unique ID for new recurring tasks; preserve existing ID if editing
        task_id = self.initial_task.get("id", str(uuid.uuid4()))

        recurrence_type = self.recurrence_type_var.get()
        recurrence_value = None
        if recurrence_type == "Weekly":
            recurrence_value = [day for day, var in self.day_checkbox_vars.items() if var.get()]
        
        return {
            "id": task_id, # Include the unique ID
            "task": task_desc,
            "xp": xp_value,
            "recurrence_type": recurrence_type.lower(),
            "recurrence_value": recurrence_value,
            # Preserve last_generated_date if editing, otherwise it's None for new tasks
            "last_generated_date": self.initial_task.get("last_generated_date") if self.initial_task else None
        }

    def validate_input(self) -> bool:
        """
        Validates all input fields in the dialog.
        Displays an error message if validation fails.
        """
        self._display_error("") # Clear any previous error messages
        task_desc = self.entry_var.get().strip()
        if not task_desc:
            self._display_error("Task description cannot be empty.")
            return False

        xp_category = self.xp_category_var.get()
        if xp_category == "Miscellaneous":
            try:
                xp_value = int(self.manual_xp_var.get())
                if xp_value < 0:
                    raise ValueError # XP cannot be negative
            except ValueError:
                self._display_error("Please enter a valid positive number for Manual XP.")
                return False
        
        recurrence_type = self.recurrence_type_var.get()
        if recurrence_type == "Weekly":
            selected_days = [day for day, var in self.day_checkbox_vars.items() if var.get()]
            if not selected_days:
                self._display_error("Please select at least one day for weekly recurrence.")
                return False
        return True

    def _on_button_click(self, command: any) -> None:
        """
        Overrides the base CustomDialog's button click handler to include input validation
        before closing the dialog for "add" or "save" commands.
        """
        if command == "add" or command == "save":
            if self.validate_input(): # Validate input before proceeding
                self.result = self._get_validated_data() # Get data only if validation passes
                self.destroy()
            else:
                # If validation fails, the dialog remains open and an error message is displayed
                pass
        else: # For "Cancel" or other non-submission commands
            self.result = command
            self.destroy()

    def get_task_details(self) -> dict | None:
        """Returns the collected and validated task details dictionary, or None if cancelled."""
        return self.result


class ManageRecurringTasksWindow(tk.Toplevel):
    """
    A window to display, edit, and delete recurring tasks.
    Provides a dedicated interface for managing recurring task definitions.
    """
    def __init__(self, parent: tk.Tk, app_instance: 'XPDashboardApp'):
        super().__init__(parent)
        self.parent = parent
        self.app = app_instance # Reference to the main application instance
        self.title("Manage Recurring Tasks")
        self.geometry("600x500")
        self.configure(bg=DARK_BG)
        self.transient(parent)
        self.grab_set() # Make this window modal

        center_window(self, parent)

        tk.Label(self, text="Your Recurring Tasks", font=("Segoe UI", 16, "bold"), bg=DARK_BG, fg=ACCENT_COLOR).pack(pady=10)

        # Canvas and Scrollbar for scrollable list of recurring tasks
        self.canvas = tk.Canvas(self, bg=DARK_FRAME_BG, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=DARK_FRAME_BG)

        # Configure scrollable frame to update canvas scroll region
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        self.scrollbar.pack(side="right", fill="y")

        self.populate_recurring_list() # Populate the list of recurring tasks

        # Close button for the window
        tk.Button(self, text="Close", command=self.destroy,
                  bg=ACCENT_COLOR, fg=DARK_BG, font=("Segoe UI", 11, "bold"), relief="flat", padx=10, pady=5,
                  activebackground="#4a8ec9", activeforeground=DARK_TEXT).pack(pady=10)

    def populate_recurring_list(self) -> None:
        """
        Clears and repopulates the list of recurring tasks in the window.
        Includes edit and delete buttons for each task.
        """
        # Clear existing widgets
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        if not self.app.recurring_tasks:
            tk.Label(self.scrollable_frame, text="No recurring tasks defined yet.", bg=DARK_FRAME_BG, fg=DARK_TEXT, font=("Segoe UI", 12)).pack(pady=20)
            return

        for i, r_task in enumerate(self.app.recurring_tasks):
            task_row_frame = tk.Frame(self.scrollable_frame, bg=DARK_FRAME_BG, bd=2, relief="groove")
            task_row_frame.grid(row=i, column=0, sticky="ew", pady=5, padx=5)
            self.scrollable_frame.grid_columnconfigure(0, weight=1)

            # Display task name, XP, and recurrence details
            task_text = f"{r_task['task']} ({r_task['xp']} XP) - "
            if r_task['recurrence_type'] == 'daily':
                task_text += "Daily"
            elif r_task['recurrence_type'] == 'weekly':
                days = ", ".join(r_task['recurrence_value'])
                task_text += f"Weekly ({days})"
            
            tk.Label(task_row_frame, text=task_text, font=("Segoe UI", 13), bg=DARK_FRAME_BG, fg=DARK_TEXT, wraplength=400, anchor="w").grid(row=0, column=0, sticky="w", padx=10, pady=6)

            # Edit button for the recurring task
            edit_btn = tk.Button(task_row_frame, text="✏️", font=("Segoe UI", 11),
                                 bg=WARNING_COLOR, fg=DARK_BG, relief="flat", padx=5, pady=2,
                                 # Pass task ID to edit_recurring_task for robust lookup
                                 command=lambda t_id=r_task['id']: self.app.edit_recurring_task(t_id, self.populate_recurring_list),
                                 activebackground="#c7a35e", activeforeground=DARK_TEXT)
            edit_btn.grid(row=0, column=1, padx=(0, 5))

            # Delete button for the recurring task
            del_btn = tk.Button(task_row_frame, text="🗑️", font=("Segoe UI", 11),
                                 bg=ERROR_COLOR, fg="white", relief="flat", padx=5, pady=2,
                                 # Pass task ID to delete_recurring_task for robust lookup
                                 command=lambda t_id=r_task['id']: self.app.delete_recurring_task(t_id, self.populate_recurring_list),
                                 activebackground="#a03d45", activeforeground="white")
            del_btn.grid(row=0, column=2, padx=(0, 5))

            # Configure column weights for proper layout
            task_row_frame.grid_columnconfigure(0, weight=1)
            task_row_frame.grid_columnconfigure(1, weight=0)
            task_row_frame.grid_columnconfigure(2, weight=0)

        # Update canvas scroll region after all widgets are packed
        self.canvas.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

class TaskDetailsDialog(CustomDialog):
    """
    Custom dialog for adding or editing individual daily tasks.
    Extends CustomDialog to include fields for task name, XP category/value, and due time.
    """
    def __init__(self, parent: tk.Tk, xp_categories: dict, initial_task: dict = None, initial_task_name: str = ""):
        self.xp_categories = xp_categories
        self.initial_task = initial_task or {} # Ensure initial_task is always a dictionary
        
        # Determine dialog title and button text based on add/edit mode
        title = "Add New Task" if not initial_task else "Edit Task"
        message = "Enter task details:"
        button_text = "Add" if not initial_task else "Save"
        button_command = "add" if not initial_task else "save"

        # Initialize the base CustomDialog with common elements (message, entry, buttons)
        super().__init__(parent, title, message,
                         buttons=[(button_text, button_command, SUCCESS_COLOR), ("Cancel", None, ERROR_COLOR)],
                         entry_text=self.initial_task.get("task", initial_task_name) if self.initial_task or initial_task_name else "")

        # XP Category selection
        xp_cat_frame = tk.Frame(self, bg=DARK_BG)
        xp_cat_frame.pack(pady=5)
        tk.Label(xp_cat_frame, text="XP Category:", bg=DARK_BG, fg=DARK_TEXT, font=("Segoe UI", 11)).pack(side="left", padx=5)
        
        # Determine initial XP category for the combobox
        initial_xp_category = "Miscellaneous" # Default value
        if self.initial_task.get("xp") is not None:
            for cat, xp_val in self.xp_categories.items():
                if xp_val == self.initial_task["xp"]:
                    initial_xp_category = cat
                    break
            else:
                initial_xp_category = "Miscellaneous" # Fallback if XP value doesn't match a category

        self.xp_category_var = tk.StringVar(value=initial_xp_category)
        self.xp_category_combobox = ttk.Combobox(xp_cat_frame, textvariable=self.xp_category_var,
                                                 values=list(self.xp_categories.keys()), state="readonly", font=("Segoe UI", 11))
        self.xp_category_combobox.pack(side="left", padx=5)
        self.xp_category_combobox.bind("<<ComboboxSelected>>", self._on_category_selected)

        # Manual XP entry (visible only if "Miscellaneous" category is selected)
        self.manual_xp_frame = tk.Frame(self, bg=DARK_BG)
        tk.Label(self.manual_xp_frame, text="Manual XP:", bg=DARK_BG, fg=DARK_TEXT, font=("Segoe UI", 11)).pack(side="left", padx=5)
        self.manual_xp_var = tk.StringVar(value=str(self.initial_task.get("xp", "")) if initial_xp_category == "Miscellaneous" else "")
        self.manual_xp_entry = tk.Entry(self.manual_xp_frame, textvariable=self.manual_xp_var, font=("Segoe UI", 11), width=10,
                                        bg=DARK_FRAME_BG, fg=DARK_TEXT, insertbackground=ACCENT_COLOR, bd=1, relief="solid")
        self.manual_xp_entry.pack(side="left", padx=5)
        self._on_category_selected() # Call once to set initial visibility

        # Due Time input field
        time_frame = tk.Frame(self, bg=DARK_BG)
        time_frame.pack(pady=5)
        tk.Label(time_frame, text="Due Time (HH:MM, optional):", bg=DARK_BG, fg=DARK_TEXT, font=("Segoe UI", 11)).pack(side="left", padx=5)
        self.due_time_var = tk.StringVar(value=self.initial_task.get("due_time", ""))
        self.due_time_entry = tk.Entry(time_frame, textvariable=self.due_time_var, font=("Segoe UI", 11), width=10,
                                      bg=DARK_FRAME_BG, fg=DARK_TEXT, insertbackground=ACCENT_COLOR, bd=1, relief="solid")
        self.due_time_entry.pack(side="left", padx=5)

        # Error message label for validation feedback
        self.error_label = tk.Label(self, text="", fg=ERROR_COLOR, bg=DARK_BG, font=("Segoe UI", 10, "bold"), wraplength=350)
        self.error_label.pack(pady=(0, 5))

        # Adjust dialog size and center after all widgets are packed
        self.update_idletasks()
        self.geometry(f"450x{self.winfo_height()}")
        center_window(self, parent)

    def _display_error(self, message: str) -> None:
        """Displays an error message in the dialog's error label."""
        self.error_label.config(text=message)

    def _on_category_selected(self, event=None):
        """Shows/hides the manual XP entry based on the selected XP category."""
        selected_category = self.xp_category_var.get()
        if selected_category == "Miscellaneous":
            self.manual_xp_frame.pack(pady=5)
        else:
            self.manual_xp_frame.pack_forget()
        # Re-adjust dialog size and center after visibility change
        self.update_idletasks()
        self.geometry(f"450x{self.winfo_height()}")
        center_window(self, self.parent)

    def _get_validated_data(self) -> dict:
        """
        Collects and returns the task details after input validation has passed.
        This method is called ONLY after validate_input returns True.
        """
        task_desc = self.entry_var.get().strip()
        xp_category = self.xp_category_var.get()
        xp_value = None
        if xp_category == "Miscellaneous":
            xp_value = int(self.manual_xp_var.get())
        else:
            xp_value = self.xp_categories.get(xp_category)
            if xp_value is None: # Fallback for categories with no predefined XP
                xp_value = 0
        
        due_time = self.due_time_var.get().strip()
        if not due_time:
            due_time = None # Store as None if empty

        return {
            "task": task_desc,
            "xp": xp_value,
            "due_time": due_time
        }

    def validate_input(self) -> bool:
        """
        Validates all input fields in the dialog.
        Displays an error message if validation fails.
        """
        self._display_error("") # Clear any previous error messages
        task_desc = self.entry_var.get().strip()
        if not task_desc:
            self._display_error("Task description cannot be empty.")
            return False

        xp_category = self.xp_category_var.get()
        if xp_category == "Miscellaneous":
            try:
                xp_value = int(self.manual_xp_var.get())
                if xp_value < 0:
                    raise ValueError # XP cannot be negative
            except ValueError:
                self._display_error("Please enter a valid positive number for Manual XP.")
                return False
        
        due_time = self.due_time_var.get().strip()
        if due_time:
            try:
                h, m = map(int, due_time.split(':'))
                if not (0 <= h <= 23 and 0 <= m <= 59):
                    raise ValueError # Invalid hour or minute range
            except ValueError:
                self._display_error("Invalid time format. Please use HH:MM (e.g., 09:30 or 14:00).")
                return False
        return True

    def _on_button_click(self, command: any) -> None:
        """
        Overrides the base CustomDialog's button click handler to include input validation
        before closing the dialog for "add" or "save" commands.
        """
        if command == "add" or command == "save":
            if self.validate_input(): # Validate input before proceeding
                self.result = self._get_validated_data() # Get data only if validation passes
                self.destroy()
            else:
                # If validation fails, the dialog remains open and an error message is displayed
                pass
        else: # For "Cancel" or other non-submission commands
            self.result = command
            self.destroy()

    def get_task_details(self) -> dict | None:
        """Returns the collected and validated task details dictionary, or None if cancelled."""
        return self.result
