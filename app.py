# app.py
import tkinter as tk
from tkinter import messagebox, ttk
import datetime
import uuid
import logging # Import the logging module

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Import constants from the constants module
from constants import (
    DATA_FILE, CATEGORIES_FILE, GOALS_FILE, RECURRING_TASKS_FILE,
    DARK_BG, DARK_FRAME_BG, DARK_TEXT, ACCENT_COLOR, ERROR_COLOR, SUCCESS_COLOR, WARNING_COLOR
)

# Import utility functions and enums from the utils module
from utils import xp_needed_for_level, center_window, FilterMode, generate_unique_id

# Import data manager class from the data_manager module
from data_manager import DataManager

# Import the entire ui_dialogs module
import ui_dialogs


class XPDashboardApp:
    """
    Main application class for the Daily XP Dashboard.
    Manages the UI, data, XP system, and task notifications.
    """
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Daily XP Dashboard - Dark Mode")
        root.configure(bg=DARK_BG)
        root.resizable(True, True) # Allow window resizing

        # Set protocol for handling application close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing_app)

        # Initialize DataManager for file operations
        self.data_manager = DataManager(DATA_FILE, CATEGORIES_FILE, GOALS_FILE, RECURRING_TASKS_FILE)

        # Application state variables
        self.current_date: str = datetime.date.today().strftime("%Y-%m-%d")
        self.tasks_data: dict = {} # Stores all tasks by date
        # self.tasks will now store tasks as a dictionary {task_id: task_details_dict}
        self.tasks: dict = {} 

        self.level: int = 1
        self.total_xp: int = 0
        self.daily_xp_today: int = 0
        self._goal_met_shown_for_today: bool = False # Flag to prevent repeated goal met notifications

        self.xp_categories: dict = {} # Stores XP categories and their values
        self.xp_goals: dict = {} # Stores daily XP goal and last reset date
        self.recurring_tasks: list = [] # Stores recurring task definitions

        self.sort_var = tk.StringVar(value="Default") # Variable for task sorting
        self.sort_options = ["Default", "XP (High to Low)", "XP (Low to High)", "Alphabetical", "Status (Done First)"]

        self.scheduled_notifications = {} # Dictionary to store Tkinter after IDs for notifications
        self.auto_save_id = None # To store the ID of the scheduled auto-save event
        self.recently_deleted_tasks = {} # Stores {task_id: (task_data, after_id)} for undo functionality
        self.undo_notification_id = None # To store the ID of the scheduled undo notification hide event

        # Setup UI, load state, and populate initial data
        self._setup_ui()
        self._setup_undo_notification_ui() # Setup the undo notification bar
        self._load_app_state()
        self.populate_tasks() # Call populate_tasks after loading data
        self.update_level_xp_labels(animated=False) # Initial update without animation
        self.update_daily_goal_display() # Initial update of daily goal
        self._schedule_all_current_tasks_notifications() # Schedule notifications on app start
        self._schedule_auto_save() # Start auto-save when the app initializes
        logging.info("XP Dashboard application initialized.") # Log application start

    def on_closing_app(self) -> None:
        """
        Handler for when the application is closing.
        Saves all current data and cancels any pending notifications and auto-save.
        """
        logging.info("Application is closing. Saving state and cancelling pending operations.")
        self._save_app_state() # Save all application state one last time
        # Cancel all scheduled Tkinter 'after' notifications
        for task_id in list(self.scheduled_notifications.keys()):
            self._cancel_notification_for_task(task_id)
        
        # Cancel the pending auto-save event
        if self.auto_save_id:
            self.root.after_cancel(self.auto_save_id)
            self.auto_save_id = None

        # Cancel any pending undo notification hide event
        if self.undo_notification_id:
            self.root.after_cancel(self.undo_notification_id)
            self.undo_notification_id = None

        # Permanently delete any tasks in recently_deleted_tasks before closing
        # This ensures data consistency if the app is closed while an undo is pending
        for task_id in list(self.recently_deleted_tasks.keys()):
            task_data, after_id = self.recently_deleted_tasks[task_id]
            if after_id:
                try:
                    self.root.after_cancel(after_id)
                except Exception as e:
                    logging.warning(f"Error cancelling undo timeout for task {task_id}: {e}")
            del self.recently_deleted_tasks[task_id] # Remove from temp storage
        logging.info("Application closed successfully.")
        self.root.destroy() # Destroy the main window

    def _load_app_state(self) -> None:
        """
        Loads all application data using DataManager and updates internal state variables.
        Includes migration logic for tasks from old list format to new dictionary format (with IDs).
        """
        logging.info("Loading application state...")
        self.tasks_data = self.data_manager.load_tasks_data()
        self.xp_categories = self.data_manager.load_categories_data()
        self.xp_goals = self.data_manager.load_goals_data(self.current_date)
        self.recurring_tasks = self.data_manager.load_recurring_tasks_data()

        # Handle tasks for the current date.
        # Check if tasks are in the old list format or new dictionary format.
        raw_tasks_for_today = self.tasks_data.get(self.current_date, {})
        if isinstance(raw_tasks_for_today, list):
            logging.info("Old task data format detected. Migrating to new ID-based format.")
            converted_tasks = {}
            for task in raw_tasks_for_today:
                if 'id' not in task:
                    task['id'] = generate_unique_id() # Assign a new unique ID if missing
                converted_tasks[task['id']] = task
            self.tasks = converted_tasks
            # Immediately save in the new format to prevent repeated conversion on next load
            self.tasks_data[self.current_date] = self.tasks
            self.data_manager.save_tasks_data(self.tasks_data)
            logging.info("Task data migration complete.")
        else:
            # New format: dictionary of tasks (already has IDs)
            self.tasks = raw_tasks_for_today

        # Load global XP and level
        self.level = self.tasks_data.get("_level", 1)
        self.total_xp = self.tasks_data.get("_total_xp", 0)
        
        # Calculate daily_xp_today based on loaded tasks for the current date
        self.daily_xp_today = sum(t['xp'] for t in self.tasks.values() if t['done'])

        # Check and reset daily XP goal if a new day has started
        if self.xp_goals.get("last_daily_reset") != self.current_date:
            logging.info(f"New day detected. Resetting daily XP goal for {self.current_date}.")
            self.daily_xp_today = 0
            self.xp_goals["last_daily_reset"] = self.current_date
            self.data_manager.save_goals_data(self.xp_goals)
            self._goal_met_shown_for_today = False
        else:
            # If goal was already met today, keep the flag true
            daily_goal = self.xp_goals.get("daily_goal", 0)
            if daily_goal > 0 and self.daily_xp_today >= daily_goal:
                self._goal_met_shown_for_today = True
            else:
                self._goal_met_shown_for_today = False

        # Generate any new daily tasks from recurring definitions
        self._generate_daily_tasks_from_recurring()
        self.update_header() # Update the header display
        self._schedule_all_current_tasks_notifications() # Re-schedule notifications after loading/generating tasks
        logging.info("Application state loaded.")

    def _save_app_state(self) -> None:
        """
        Saves all current application data using the DataManager.
        This includes tasks, XP, level, categories, goals, and recurring tasks.
        """
        logging.info("Saving application state...")
        self.tasks_data[self.current_date] = self.tasks # Save current day's tasks (which is a dict)
        self.tasks_data["_level"] = self.level # Save global level
        self.tasks_data["_total_xp"] = self.total_xp # Save global total XP
        self.data_manager.save_tasks_data(self.tasks_data)
        self.data_manager.save_categories_data(self.xp_categories)
        self.data_manager.save_goals_data(self.xp_goals)
        self.data_manager.save_recurring_tasks_data(self.recurring_tasks)
        logging.info("Application state saved.")

    # Helper methods to save specific data types
    def save_categories(self) -> None:
        self.data_manager.save_categories_data(self.xp_categories)
        logging.info("Categories data saved.")

    def save_goals(self) -> None:
        self.data_manager.save_goals_data(self.xp_goals)
        logging.info("Goals data saved.")

    def save_tasks(self) -> None:
        self.tasks_data[self.current_date] = self.tasks
        self.data_manager.save_tasks_data(self.tasks_data)
        logging.info("Tasks data saved.")

    def save_recurring_tasks(self) -> None:
        self.data_manager.save_recurring_tasks_data(self.recurring_tasks)
        logging.info("Recurring tasks data saved.")

    def _generate_daily_tasks_from_recurring(self) -> None:
        """
        Generates daily tasks from recurring task definitions if they are due
        and not already present in the current day's task list.
        """
        today_date_obj = datetime.datetime.strptime(self.current_date, "%Y-%m-%d").date()
        today_weekday_name = today_date_obj.strftime("%a") # e.g., "Mon", "Tue"

        updated_recurring_tasks = []
        # Create a set of task names already added today for quick lookup
        tasks_added_today_names = {task['task'] for task in self.tasks.values()}

        for r_task in self.recurring_tasks:
            last_generated_date_str = r_task.get("last_generated_date")
            last_generated_date_obj = None
            if last_generated_date_str:
                last_generated_date_obj = datetime.datetime.strptime(last_generated_date_str, "%Y-%m-%d").date()

            should_generate = False
            # Check if the task needs to be generated for today
            if last_generated_date_obj is None or last_generated_date_obj < today_date_obj:
                if r_task["recurrence_type"] == "daily":
                    should_generate = True
                elif r_task["recurrence_type"] == "weekly":
                    if today_weekday_name in r_task["recurrence_value"]:
                        should_generate = True

            if should_generate:
                # Only add if a task with the same name isn't already present today
                if r_task["task"] not in tasks_added_today_names:
                    new_daily_task_id = generate_unique_id() # Generate a unique ID for this new daily instance
                    new_daily_task = {
                        "id": new_daily_task_id,
                        "task": r_task["task"],
                        "done": False,
                        "xp": r_task["xp"],
                        "is_recurring_instance": True, # Flag to indicate it came from a recurring task
                        "due_time": r_task.get("due_time") # Carry over due_time from recurring task
                    }
                    self.tasks[new_daily_task_id] = new_daily_task # Add to the tasks dictionary
                    tasks_added_today_names.add(r_task["task"]) # Add name to set to prevent duplicates
                    logging.info(f"Generated new daily task from recurring: '{r_task['task']}' (ID: {new_daily_task_id})")
                r_task["last_generated_date"] = self.current_date # Update last generated date
            
            updated_recurring_tasks.append(r_task)
        
        self.recurring_tasks = updated_recurring_tasks
        self.save_recurring_tasks() # Save updated recurring tasks (with new last_generated_date)

    def sort_tasks(self, tasks_list: list) -> list:
        """
        Sorts the given list of task dictionaries based on the current sort_var selection.
        """
        sort_mode: str = self.sort_var.get()
        logging.debug(f"Sorting tasks by: {sort_mode}")

        if sort_mode == "XP (High to Low)":
            tasks_list.sort(key=lambda t: t['xp'], reverse=True)
        elif sort_mode == "XP (Low to High)":
            tasks_list.sort(key=lambda t: t['xp'])
        elif sort_mode == "Alphabetical":
            tasks_list.sort(key=lambda t: t['task'].lower())
        elif sort_mode == "Status (Done First)":
            # Sort by 'done' status (False comes before True), then alphabetically by task name
            tasks_list.sort(key=lambda t: (not t['done'], t['task'].lower()))
        return tasks_list

    def _setup_ui(self) -> None:
        """
        Sets up all UI elements for the main application window.
        Configures styling, creates labels, buttons, and task display area.
        """
        logging.info("Setting up UI elements.")
        self.style = ttk.Style()
        self.style.theme_use('clam') # Use 'clam' theme for better dark mode compatibility
        
        # Configure general button styling
        self.style.configure("TButton",
                             font=("Segoe UI", 11, "bold"),
                             relief="flat",
                             padding=[10, 5])

        # Configure specific button colors using custom styles
        self.style.configure("Accent.TButton", background=ACCENT_COLOR, foreground=DARK_BG)
        self.style.configure("Success.TButton", background=SUCCESS_COLOR, foreground=DARK_BG)
        self.style.configure("Warning.TButton", background=WARNING_COLOR, foreground=DARK_BG)
        self.style.configure("Error.TButton", background=ERROR_COLOR, foreground="white")

        # Configure progress bar styling
        self.style.configure("Custom.Horizontal.TProgressbar",
                        background=ACCENT_COLOR, troughcolor=DARK_FRAME_BG,
                        bordercolor=DARK_TEXT, lightcolor=ACCENT_COLOR,
                        darkcolor=ACCENT_COLOR, thickness=15, relief="flat")
        self.style.configure("GoalMet.Horizontal.TProgressbar",
                        background=SUCCESS_COLOR, troughcolor=DARK_FRAME_BG,
                        bordercolor=DARK_TEXT, lightcolor=SUCCESS_COLOR,
                        darkcolor=SUCCESS_COLOR, thickness=15, relief="flat")

        # Configure entry and combobox styling
        self.style.configure("TEntry",
                             fieldbackground=DARK_FRAME_BG,
                             foreground=DARK_TEXT,
                             insertbackground=ACCENT_COLOR, # Cursor color
                             font=("Segoe UI", 12),
                             bd=1, relief="solid")

        self.style.configure("TCombobox",
                             fieldbackground=DARK_FRAME_BG,
                             foreground=DARK_TEXT,
                             selectbackground=ACCENT_COLOR,
                             selectforeground=DARK_BG,
                             font=("Segoe UI", 11),
                             bd=1, relief="solid")

        # Configure general label styling and specific header/XP labels
        self.style.configure("TLabel", background=DARK_BG, foreground=DARK_TEXT)
        self.style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"), background=DARK_BG, foreground=DARK_TEXT)
        self.style.configure("LevelXP.TLabel", font=("Segoe UI", 14, "bold"), background=DARK_BG, foreground=ACCENT_COLOR)
        self.style.configure("Goal.TLabel", font=("Segoe UI", 12, "bold"), background=DARK_BG, foreground=DARK_TEXT)


        # Main application title/logo
        self.logo_label = tk.Label(self.root, text="🌟 XP Dashboard 🌟", font=("Segoe UI", 20, "bold"), bg=DARK_BG, fg=ACCENT_COLOR)
        self.logo_label.pack(pady=(10, 5))

        # Date selection button
        self.date_btn = tk.Button(self.root, text=f"Select Date ({self.current_date})", command=self.select_date,
                                  bg=ACCENT_COLOR, fg=DARK_BG, font=("Segoe UI", 11, "bold"),
                                  relief="flat", padx=10, pady=6,
                                  activebackground="#4a8ec9", activeforeground=DARK_TEXT)
        self.date_btn.pack(pady=(0, 10))

        # Header label showing task completion status
        self.header_label = tk.Label(self.root, text="", font=("Segoe UI", 14, "bold"), bg=DARK_BG, fg=DARK_TEXT)
        self.header_label.pack(pady=5)

        # Control frame for filter and sort options
        control_frame = tk.Frame(self.root, bg=DARK_BG)
        control_frame.pack(pady=5, fill="x")

        # Filter options (Radiobuttons)
        filter_frame = tk.Frame(control_frame, bg=DARK_BG)
        filter_frame.pack(side="left", padx=10)
        tk.Label(filter_frame, text="Filter: ", bg=DARK_BG, fg=DARK_TEXT, font=("Segoe UI", 12)).pack(side="left")
        self.filter_var = tk.StringVar(value=FilterMode.ALL.value)
        filters = [(f.name.replace("_", " ").title(), f.value) for f in FilterMode]
        for text, mode in filters:
            rb = tk.Radiobutton(filter_frame, text=text, variable=self.filter_var, value=mode,
                                bg=DARK_BG, fg=DARK_TEXT, selectcolor=ACCENT_COLOR,
                                font=("Segoe UI", 11), command=self.populate_tasks,
                                activebackground=DARK_FRAME_BG, activeforeground=ACCENT_COLOR)
            rb.pack(side="left", padx=5)

        # Sort options (Combobox)
        sort_frame = tk.Frame(control_frame, bg=DARK_BG)
        sort_frame.pack(side="right", padx=10)
        tk.Label(sort_frame, text="Sort by: ", bg=DARK_BG, fg=DARK_TEXT, font=("Segoe UI", 12)).pack(side="left")
        self.sort_combobox = ttk.Combobox(sort_frame, textvariable=self.sort_var, values=self.sort_options, state="readonly", font=("Segoe UI", 11))
        self.sort_combobox.pack(side="left", padx=5)
        self.sort_combobox.bind("<<ComboboxSelected>>", lambda e: self.populate_tasks())

        # Search bar
        search_frame = tk.Frame(self.root, bg=DARK_BG)
        search_frame.pack(pady=5, fill="x", padx=20)
        tk.Label(search_frame, text="Search: ", bg=DARK_BG, fg=DARK_TEXT, font=("Segoe UI", 12)).pack(side="left")
        self.search_entry = tk.Entry(search_frame, font=("Segoe UI", 12), bg=DARK_FRAME_BG, fg=DARK_TEXT, insertbackground=ACCENT_COLOR, bd=1, relief="solid")
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0,5))
        self.search_entry.bind("<KeyRelease>", lambda e: self.populate_tasks()) # Update tasks on key release

        # Clear search button
        self.clear_search_btn = tk.Button(search_frame, text="✖️", font=("Segoe UI", 10, "bold"),
                                          command=self.clear_search,
                                          bg=ERROR_COLOR, fg="white", relief="flat", padx=5, pady=2,
                                          activebackground="#a03d45", activeforeground="white")
        self.clear_search_btn.pack(side="left", padx=(0, 5))

        # Container for the scrollable task list
        self.tasks_frame_container = tk.Frame(self.root, bg=DARK_BG)
        self.tasks_frame_container.pack(fill=tk.BOTH, expand=True, padx=15) 

        # Canvas and Scrollbar for the task list
        self.canvas = tk.Canvas(self.tasks_frame_container, bg=DARK_FRAME_BG, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self.tasks_frame_container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=DARK_FRAME_BG)

        # Configure scrollable frame to update canvas scroll region
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # XP and Level display
        self.level_label = tk.Label(self.root, text="", font=("Segoe UI", 14, "bold"), bg=DARK_BG, fg=ACCENT_COLOR)
        self.level_label.pack(pady=(10, 0))

        self.xp_label = tk.Label(self.root, text="", font=("Segoe UI", 14, "bold"), bg=DARK_BG, fg=ACCENT_COLOR)
        self.xp_label.pack(pady=(0, 5))

        self.xp_progressbar = ttk.Progressbar(self.root, style="Custom.Horizontal.TProgressbar", orient="horizontal", length=400, mode="determinate")
        self.xp_progressbar.pack(pady=(0, 10))

        # Daily Goal display and controls
        self.daily_goal_frame = tk.Frame(self.root, bg=DARK_BG)
        self.daily_goal_frame.pack(pady=(5, 10), fill="x", padx=20)

        self.daily_goal_label = tk.Label(self.daily_goal_frame, text="", font=("Segoe UI", 12, "bold"), bg=DARK_BG, fg=DARK_TEXT)
        self.daily_goal_label.pack(side="left", padx=(0, 10))

        self.set_goal_btn = tk.Button(self.daily_goal_frame, text="Set Goal", command=self.set_daily_goal,
                                      bg=WARNING_COLOR, fg=DARK_BG, font=("Segoe UI", 10, "bold"),
                                      relief="flat", padx=8, pady=4,
                                      activebackground="#c7a35e", activeforeground=DARK_TEXT)
        self.set_goal_btn.pack(side="right")

        self.daily_goal_progressbar = ttk.Progressbar(self.daily_goal_frame, style="Custom.Horizontal.TProgressbar", orient="horizontal", length=200, mode="determinate")
        self.daily_goal_progressbar.pack(side="right", fill="x", expand=True, padx=(0, 10))

        # Task entry and add button
        entry_frame = tk.Frame(self.root, bg=DARK_BG)
        entry_frame.pack(pady=10, fill="x", padx=20)

        self.task_entry = tk.Entry(entry_frame, font=("Segoe UI", 12), bg=DARK_FRAME_BG, fg=DARK_TEXT, insertbackground=ACCENT_COLOR, bd=1, relief="solid")
        self.task_entry.pack(side="left", fill="x", expand=True, padx=(0,10))
        self.task_entry.bind("<Return>", self.on_enter_add_task) # Add task on Enter key press

        self.add_task_btn = tk.Button(entry_frame, text="Add Task \u2795", font=("Segoe UI", 12),
                                      command=self.add_task_from_entry,
                                      bg=SUCCESS_COLOR, fg=DARK_BG,
                                      activebackground="#79a361",
                                      activeforeground=DARK_TEXT,
                                      relief="flat", padx=10, pady=5)
        self.add_task_btn.pack(side="right")

        # Buttons for recurring tasks management
        self.add_recurring_task_btn = tk.Button(self.root, text="Add Recurring Task \u21BA", font=("Segoe UI", 12),
                                                command=self.add_recurring_task,
                                                bg=WARNING_COLOR, fg=DARK_BG,
                                                activebackground="#c7a35e",
                                                activeforeground=DARK_TEXT,
                                                relief="flat", padx=10, pady=5)
        self.add_recurring_task_btn.pack(pady=(0, 10))

        self.manage_recurring_tasks_btn = tk.Button(self.root, text="Manage Recurring Tasks \u2699", font=("Segoe UI", 12),
                                                    command=self.manage_recurring_tasks,
                                                    bg=ACCENT_COLOR, fg=DARK_BG,
                                                    activebackground="#4a8ec9",
                                                    activeforeground=DARK_TEXT,
                                                    relief="flat", padx=10, pady=5)
        self.manage_recurring_tasks_btn.pack(pady=(0, 10))

        # Bottom buttons frame for additional features
        bottom_buttons_frame = tk.Frame(self.root, bg=DARK_BG)
        bottom_buttons_frame.pack(pady=(0,10))

        self.edit_categories_btn = tk.Button(bottom_buttons_frame, text="Edit XP Categories", command=self.edit_categories_window,
                                             bg=WARNING_COLOR, fg=DARK_BG,
                                             font=("Segoe UI", 12, "bold"),
                                             relief="flat", padx=10, pady=6,
                                             activebackground="#c7a35e", activeforeground=DARK_TEXT)
        self.edit_categories_btn.pack(side="left", padx=5)

        self.view_history_btn = tk.Button(bottom_buttons_frame, text="View XP History", command=self.view_xp_history,
                                          bg=ACCENT_COLOR, fg=DARK_BG,
                                          font=("Segoe UI", 12, "bold"),
                                          relief="flat", padx=10, pady=6,
                                          activebackground="#4a8ec9", activeforeground=DARK_TEXT)
        self.view_history_btn.pack(side="right", padx=5)

        # Lists to keep references to dynamically created widgets (for potential future use if direct access is needed)
        self.task_vars: list = []
        self.checkbuttons: list = []
        self.delete_buttons: list = []
        self.edit_buttons: list = []

        # XP and Goal Met popup labels (initially hidden)
        self.xp_popup_label = tk.Label(self.root, text="", font=("Segoe UI", 16, "bold"), bg=DARK_BG, fg=SUCCESS_COLOR)
        self.xp_popup_label.place(relx=0.5, rely=0.5, anchor="center")
        self.xp_popup_label.place_forget()

        self.goal_met_popup_label = tk.Label(self.root, text="Daily Goal Met! 🎉", font=("Segoe UI", 20, "bold"), bg=DARK_BG, fg=SUCCESS_COLOR)
        self.goal_met_popup_label.place(relx=0.5, rely=0.5, anchor="center")
        self.goal_met_popup_label.place_forget()

    def _setup_undo_notification_ui(self) -> None:
        """
        Sets up the UI elements for the undo notification bar at the bottom of the window.
        """
        self.undo_notification_frame = tk.Frame(self.root, bg=DARK_FRAME_BG, bd=2, relief="raised")
        # Initially, don't pack it; it will be placed when needed
        
        self.undo_notification_label = tk.Label(self.undo_notification_frame, text="", bg=DARK_FRAME_BG, fg=DARK_TEXT, font=("Segoe UI", 10))
        self.undo_notification_label.pack(side="left", padx=10, pady=5)

        self.undo_button = tk.Button(self.undo_notification_frame, text="Undo", command=self.undo_delete_task,
                                     bg=ACCENT_COLOR, fg=DARK_BG, font=("Segoe UI", 10, "bold"),
                                     relief="flat", padx=8, pady=3,
                                     activebackground="#4a8ec9", activeforeground=DARK_TEXT)
        self.undo_button.pack(side="right", padx=5, pady=5)

    def _show_undo_notification(self, task_name: str) -> None:
        """
        Displays the undo notification bar with a message about the deleted task.
        Schedules the notification to hide after a few seconds.
        """
        logging.info(f"Showing undo notification for task: '{task_name}'")
        self.undo_notification_label.config(text=f"'{task_name}' deleted. ")
        self.undo_notification_frame.pack(side="bottom", fill="x", pady=5, padx=10)
        self.undo_notification_frame.lift() # Bring to front

        # Cancel any previous hide schedule to allow new notification to display fully
        if self.undo_notification_id:
            self.root.after_cancel(self.undo_notification_id)
            logging.debug("Cancelled previous undo notification hide schedule.")
        
        # Schedule to hide the notification after 5 seconds
        self.undo_notification_id = self.root.after(5000, self._hide_undo_notification)
        logging.debug("Scheduled new undo notification hide.")

    def _hide_undo_notification(self) -> None:
        """
        Hides the undo notification bar and clears the recently deleted task.
        This is typically called after the timer expires or after an undo action.
        """
        logging.info("Hiding undo notification.")
        self.undo_notification_frame.pack_forget()
        # Clear the recently deleted task as the undo window is now hidden
        # This prevents undoing a task that was permanently deleted or timed out
        self.recently_deleted_tasks.clear() # Clear all pending undos for simplicity for now
        self.undo_notification_id = None # Clear the scheduled ID

    def populate_tasks(self) -> None:
        """
        Clears the current task list display and repopulates it based on
        the current filter, search query, and sort order.
        """
        logging.info("Populating tasks display.")
        # Destroy all existing task widgets
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        # Clear lists holding references to old widgets
        self.task_vars.clear()
        self.checkbuttons.clear()
        self.delete_buttons.clear()
        self.edit_buttons.clear()

        # Get all current tasks as a list of dictionaries (from the tasks dictionary values)
        all_current_tasks = list(self.tasks.values()) 
        
        # Apply search filter
        search_query: str = self.search_entry.get().strip().lower()
        if search_query:
            logging.debug(f"Applying search filter: '{search_query}'")
            searched_tasks = [t for t in all_current_tasks if search_query in t['task'].lower()]
        else:
            searched_tasks = list(all_current_tasks)

        # Apply completion status filter
        if self.filter_var.get() == FilterMode.DONE.value:
            logging.debug("Applying 'Done' filter.")
            filtered_tasks = [t for t in searched_tasks if t["done"]]
        elif self.filter_var.get() == FilterMode.NOT_DONE.value:
            logging.debug("Applying 'Not Done' filter.")
            filtered_tasks = [t for t in searched_tasks if not t["done"]]
        else:
            filtered_tasks = list(searched_tasks)

        # Sort the filtered tasks
        sorted_tasks = self.sort_tasks(filtered_tasks)

        # Display a message if no tasks are found
        if not sorted_tasks:
            logging.info("No tasks found for current filter/search criteria.")
            tk.Label(self.scrollable_frame, text="No tasks found for this filter/search.", bg=DARK_FRAME_BG, fg=DARK_TEXT, font=("Segoe UI", 12)).pack(pady=20)
            self.update_header(sorted_tasks) # Update header even if no tasks
            self.canvas.update_idletasks()
            self.canvas.config(scrollregion=self.canvas.bbox("all"))
            return

        # Create and display widgets for each task
        for i, task in enumerate(sorted_tasks):
            task_row_frame = tk.Frame(self.scrollable_frame, bg=DARK_FRAME_BG, bd=2, relief="groove")
            task_row_frame.grid(row=i, column=0, sticky="ew", pady=5, padx=5)
            self.scrollable_frame.grid_columnconfigure(0, weight=1)

            var = tk.BooleanVar(value=task["done"]) # Boolean variable for checkbox state
            
            # Construct task display text
            task_display_text = f"{task['task']} ({task['xp']} XP)"
            if task.get("due_time"):
                task_display_text += f" @ {task['due_time']}"
            if task.get("is_recurring_instance"):
                task_display_text += " (R)" # Indicate if it's a recurring task instance

            # Task Checkbutton
            cb = tk.Checkbutton(
                task_row_frame,
                text=task_display_text,
                variable=var,
                command=lambda t_id=task['id']: self.toggle_task(t_id), # Pass task ID to toggle_task
                font=("Segoe UI", 13), # Slightly larger font for tasks
                bg=DARK_FRAME_BG,
                fg=ACCENT_COLOR if task["done"] else DARK_TEXT, # Change color based on completion status
                selectcolor=DARK_BG, # Color when checkbox is selected
                activebackground=ACCENT_COLOR, # Background when mouse hovers over active checkbox
                activeforeground=DARK_BG, # Foreground when mouse hovers over active checkbox
                anchor="w", # Align text to the west (left)
                padx=10,
                pady=6 # Slightly more vertical padding for better spacing
            )
            cb.grid(row=0, column=0, sticky="w", padx=(0, 5))

            # Add a clock icon if the task has a due_time and is not done
            if task.get("due_time") and not task["done"]:
                clock_icon_label = tk.Label(task_row_frame, text="⏰", font=("Segoe UI", 12), bg=DARK_FRAME_BG, fg=WARNING_COLOR)
                clock_icon_label.grid(row=0, column=0, sticky="e", padx=(0, 15), pady=6) # Place it on the right of the checkbox text

            # Edit button for task
            edit_btn = tk.Button(task_row_frame, text="✏️", font=("Segoe UI", 11),
                                 bg=WARNING_COLOR, fg=DARK_BG, relief="flat", padx=5, pady=2,
                                 command=lambda t_id=task['id']: self.edit_task(t_id), # Pass task ID to edit_task
                                 activebackground="#c7a35e", activeforeground=DARK_TEXT)
            edit_btn.grid(row=0, column=1, padx=(0, 5))

            # Delete button for task
            del_btn = tk.Button(task_row_frame, text="🗑️", font=("Segoe UI", 11),
                                 bg=ERROR_COLOR, fg="white", relief="flat", padx=5, pady=2,
                                 command=lambda t_id=task['id']: self.delete_task(t_id), # Pass task ID to delete_task
                                 activebackground="#a03d45", activeforeground="white")
            del_btn.grid(row=0, column=2, padx=(0, 5))

            # Configure column weights for responsive layout within the task row frame
            task_row_frame.grid_columnconfigure(0, weight=1) # Task description takes most space
            task_row_frame.grid_columnconfigure(1, weight=0) # Edit button fixed size
            task_row_frame.grid_columnconfigure(2, weight=0) # Delete button fixed size

            # Store references to dynamically created widgets (for potential future use if direct access is needed)
            self.task_vars.append(var)
            self.checkbuttons.append(cb)
            self.delete_buttons.append(del_btn)
            self.edit_buttons.append(edit_btn)
        logging.info(f"Displayed {len(sorted_tasks)} tasks.")
        # Update XP labels, header, and canvas scroll region after repopulating
        self.update_level_xp_labels(animated=False)
        self.update_header(sorted_tasks)
        self.canvas.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

    def clear_search(self) -> None:
        """Clears the search entry field and repopulates the task list."""
        logging.info("Clearing search and repopulating tasks.")
        self.search_entry.delete(0, tk.END)
        self.populate_tasks()

    def update_header(self, tasks_list: list = None) -> None:
        """
        Updates the header label to show the current date's task completion status.
        """
        if tasks_list is None:
            tasks_list = list(self.tasks.values()) # If no list provided, use all current tasks
        total: int = len(tasks_list)
        done: int = sum(1 for t in tasks_list if t["done"])
        header_text = f"Tasks for {self.current_date} - {done}/{total} completed"
        self.header_label.config(text=header_text)
        logging.debug(f"Header updated: {header_text}")

    def toggle_task(self, task_id: str) -> None:
        """
        Toggles the 'done' status of a task identified by its unique ID.
        Includes a confirmation dialog for tasks with high XP.
        Updates XP accordingly and refreshes the UI.
        """
        task_to_toggle = self.tasks.get(task_id) # Retrieve task dictionary by its ID
        
        if not task_to_toggle:
            logging.error(f"Attempted to toggle non-existent task with ID: {task_id}")
            self._show_error("Error", "Could not find the task to toggle.")
            return

        previous_done: bool = task_to_toggle["done"] # Store previous state
        
        # Define a threshold for showing confirmation dialog
        XP_CONFIRMATION_THRESHOLD = 10 

        # Determine if confirmation is needed
        needs_confirmation = False
        if task_to_toggle["xp"] >= XP_CONFIRMATION_THRESHOLD:
            if not previous_done: # Confirm when marking a high-XP task as done
                needs_confirmation = True
                confirm_message = f"Are you sure you want to mark '{task_to_toggle['task']}' as DONE and gain {task_to_toggle['xp']} XP?"
            else: # Confirm when marking a high-XP task as UNDONE
                needs_confirmation = True
                confirm_message = f"Are you sure you want to mark '{task_to_toggle['task']}' as NOT DONE and lose {task_to_toggle['xp']} XP?"
        
        if needs_confirmation:
            logging.info(f"Confirmation requested for toggling high-XP task: '{task_to_toggle['task']}'")
            confirm = self._ask_custom_yesno("Confirm Task Status Change", confirm_message)
            if not confirm:
                logging.info(f"Toggling task '{task_to_toggle['task']}' cancelled by user.")
                # If user cancels, do not proceed with toggling
                self.populate_tasks() # Refresh to ensure checkbox state is correct
                return

        # Proceed with toggling if no confirmation needed or confirmed by user
        self.tasks[task_id]["done"] = not previous_done # Toggle the 'done' status
        self.save_tasks() # Save the updated tasks data

        # Adjust XP based on task completion/uncompletion
        if not previous_done and self.tasks[task_id]["done"]: # Task just marked done
            logging.info(f"Task '{task_to_toggle['task']}' (ID: {task_id}) marked as DONE. Adding {task_to_toggle['xp']} XP.")
            self.add_xp(task_to_toggle["xp"])
            self._show_xp_popup(task_to_toggle["xp"], "add")
            self._cancel_notification_for_task(task_id) # Cancel notification if task is done
        elif previous_done and not self.tasks[task_id]["done"]: # Task just marked undone
            logging.info(f"Task '{task_to_toggle['task']}' (ID: {task_id}) marked as NOT DONE. Removing {task_to_toggle['xp']} XP.")
            self.remove_xp(task_to_toggle["xp"])
            self._show_xp_popup(task_to_toggle["xp"], "remove")
            self._schedule_notifications_for_task(self.tasks[task_id]) # Re-schedule notification if task is undone
        
        # Crucial: Repopulate tasks to refresh all UI elements with new states/colors
        self.populate_tasks() 
        self.update_daily_goal_display() # Update daily goal display (which recalculates daily_xp_today)

    def add_xp(self, amount: int) -> None:
        """
        Adds XP to the total, handles level ups, and updates XP/level displays.
        """
        logging.info(f"Adding {amount} XP. Current total XP: {self.total_xp}")
        self.total_xp += amount
        # Check for level ups
        while self.total_xp >= xp_needed_for_level(self.level):
            xp_for_current_level = xp_needed_for_level(self.level)
            self.total_xp -= xp_for_current_level # Subtract XP for current level
            self.level += 1 # Increment level
            logging.info(f"Level Up! Reached level {self.level}. XP for next level: {xp_needed_for_level(self.level)}")
            self._show_info("Level Up!", f"Congratulations! You reached level {self.level} 🎉")
            self._send_notification("Level Up!", f"Congratulations! You reached level {self.level} 🎉")
        self._save_app_state() # Save updated XP and level
        self.update_level_xp_labels(animated=True) # Update labels with animation

    def remove_xp(self, amount: int) -> None:
        """
        Removes XP from the total, handles level downs (if XP goes below zero),
        and updates XP/level displays.
        """
        logging.info(f"Removing {amount} XP. Current total XP: {self.total_xp}")
        self.total_xp -= amount
        if self.total_xp < 0:
            # Handle potential level downs if XP goes negative
            while self.total_xp < 0 and self.level > 1:
                self.level -= 1 # Decrement level
                self.total_xp += xp_needed_for_level(self.level) # Add XP back from previous level
                logging.info(f"Level Down. Current level: {self.level}. Total XP: {self.total_xp}")
            if self.total_xp < 0:
                self.total_xp = 0 # Ensure XP doesn't go below zero at level 1
                logging.info("XP clamped to 0 at level 1.")
        self._save_app_state() # Save updated XP and level
        self.update_level_xp_labels(animated=True) # Update labels with animation

    def update_level_xp_labels(self, animated: bool = True) -> None:
        """
        Updates the level, XP labels, and the XP progress bar.
        Can animate the XP change for a smoother visual effect.
        """
        logging.debug(f"Updating level/XP labels. Animated: {animated}")
        self.level_label.config(text=f"Level: {self.level}")
        
        xp_for_next_level: int = xp_needed_for_level(self.level)
        self.xp_progressbar.config(maximum=xp_for_next_level)

        target_xp: int = self.total_xp
        
        if not animated:
            # If no animation, update immediately
            self.xp_label.config(text=f"XP: {target_xp} / {xp_for_next_level}")
            self.xp_progressbar.config(value=target_xp)
            self.root.update_idletasks() # Force UI update
            return
        
        # For animation, start from the current progress bar value
        current_xp_display: int = int(self.xp_progressbar.cget("value"))
        step: int = 1 if target_xp > current_xp_display else -1 # Determine animation direction
        self.animate_xp(current_xp_display, target_xp, step, xp_for_next_level)

    def get_current_xp_display(self) -> int:
        """
        (Deprecated/Internal) Extracts the currently displayed XP value from the label.
        Used internally by animate_xp, but animate_xp now starts directly from progressbar value.
        """
        text: str = self.xp_label.cget("text")
        try:
            parts = text.split(":")
            if len(parts) > 1:
                xp_part = parts[1].split("/")[0].strip()
                return int(xp_part)
            return 0
        except ValueError:
            logging.warning(f"Could not parse XP from label text: '{text}'")
            return 0

    def animate_xp(self, current_xp_display: int, target_xp: int, step: int, xp_for_next_level: int) -> None:
        """
        Recursively animates the XP label and progress bar to smoothly transition to target XP.
        """
        if current_xp_display == target_xp:
            # Animation finished, ensure final values are set
            self.xp_label.config(text=f"XP: {target_xp} / {xp_for_next_level}")
            self.xp_progressbar.config(value=target_xp)
            self.root.update_idletasks() # Force final UI update
            logging.debug("XP animation finished.")
            return
        
        # Calculate the next XP value in the animation step
        if step > 0:
            next_xp = min(current_xp_display + step, target_xp)
        else: # step < 0
            next_xp = max(current_xp_display + step, target_xp)

        self.xp_label.config(text=f"XP: {next_xp} / {xp_for_next_level}")
        self.xp_progressbar.config(value=next_xp)
        # Schedule the next animation step after a short delay
        self.root.after(20, lambda: self.animate_xp(next_xp, target_xp, step, xp_for_next_level))

    def _show_xp_popup(self, amount: int, type: str) -> None:
        """
        Displays a temporary pop-up showing XP change (+XP or -XP) with animation.
        """
        logging.debug(f"Showing XP popup: {type}{amount} XP")
        text_color: str = SUCCESS_COLOR if type == "add" else ERROR_COLOR
        text_prefix: str = "+" if type == "add" else "-"
        self.xp_popup_label.config(text=f"{text_prefix}{amount} XP", fg=text_color)
        
        # Calculate initial position for the popup
        main_window_width: int = self.root.winfo_width()
        main_window_height: int = self.root.winfo_height()
        x_pos: float = main_window_width / 2
        y_pos: float = main_window_height / 2 - 50 # Slightly above center

        self.xp_popup_label.place(x=x_pos, y=y_pos, anchor="center")
        self.xp_popup_label.lift() # Bring the label to the top

        duration: int = 1000 # Animation duration in milliseconds
        steps: int = 50 # Number of animation steps
        delay: int = duration // steps # Delay between each step
        
        initial_y: float = y_pos # Store initial Y position for animation

        def animate_movement():
            nonlocal initial_y
            initial_y -= 2 # Move upwards
            self.xp_popup_label.place(x=x_pos, y=initial_y, anchor="center")
            
            # Continue animation until it moves 100 pixels up
            if initial_y > (y_pos - 100):
                self.root.after(delay, animate_movement)
            else:
                self.xp_popup_label.place_forget() # Hide label after animation
                logging.debug("XP popup animation finished.")

        animate_movement() # Start the animation

    def _show_goal_met_popup(self) -> None:
        """
        Displays a temporary pop-up when the daily XP goal is met, with animation.
        """
        logging.info("Daily goal met! Showing popup.")
        self.goal_met_popup_label.config(text="Daily Goal Met! 🎉", fg=SUCCESS_COLOR)
        
        # Calculate initial position for the popup
        main_window_width: int = self.root.winfo_width()
        main_window_height: int = self.root.winfo_height()
        x_pos: float = main_window_width / 2
        y_pos: float = main_window_height / 2 + 50 # Slightly below center

        self.goal_met_popup_label.place(x=x_pos, y=y_pos, anchor="center")
        self.goal_met_popup_label.lift() # Bring the label to the top

        duration: int = 1500 # Animation duration in milliseconds
        steps: int = 75 # Number of animation steps
        delay: int = duration // steps # Delay between each step
        
        initial_y: float = y_pos # Store initial Y position for animation

        def animate_movement():
            nonlocal initial_y
            initial_y -= 1 # Move upwards
            self.goal_met_popup_label.place(x=x_pos, y=initial_y, anchor="center")
            
            # Continue animation until it moves 50 pixels up
            if initial_y > (y_pos - 50):
                self.root.after(delay, animate_movement)
            else:
                self.goal_met_popup_label.place_forget() # Hide label after animation
                logging.debug("Goal met popup animation finished.")

        animate_movement() # Start the animation

    def _send_notification(self, title: str, message: str) -> None:
        """
        Sends a system notification using the plyer library.
        Provides a Tkinter messagebox as a fallback if plyer is not available or fails.
        """
        logging.info(f"Sending notification: Title='{title}', Message='{message}'")
        if ui_dialogs.PLYER_AVAILABLE: # Access PLYER_AVAILABLE from ui_dialogs module
            try:
                ui_dialogs.notification.notify( # Access notification from ui_dialogs module
                    title=title,
                    message=message,
                    app_name="XP Dashboard",
                    timeout=10 # Notification timeout in seconds
                )
                logging.debug("System notification sent via plyer.")
            except Exception as e:
                logging.error(f"Failed to send system notification via plyer: {e}. Falling back to messagebox.")
                # Fallback to messagebox if plyer fails at runtime
                messagebox.showinfo(title, message)
        else:
            logging.info("Plyer not available. Sending notification via messagebox.")
            messagebox.showinfo(title, message)

    def _schedule_notifications_for_task(self, task: dict) -> None:
        """
        Schedules a Tkinter 'after' event for a task notification if it's undone
        and has a future due_time.
        """
        task_id = task['id'] # Use task's unique ID as the key for scheduled notifications
        due_time_str = task.get('due_time')

        # Cancel any existing notification for this task to avoid duplicates
        self._cancel_notification_for_task(task_id)

        if not task['done'] and due_time_str: # Only schedule for undone tasks with a due time
            try:
                # Parse due time (HH:MM)
                hour, minute = map(int, due_time_str.split(':'))
                
                now = datetime.datetime.now() # Current datetime
                
                # Construct target datetime for today with the specified hour/minute
                target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

                # If target time is in the past, don't schedule for today
                if target_time <= now:
                    logging.info(f"Task '{task['task']}' (ID: {task_id}) due time is in the past. Not scheduling notification.")
                    return

                # Calculate time difference in milliseconds
                time_diff = (target_time - now).total_seconds() * 1000

                if time_diff > 0:
                    after_id = self.root.after(int(time_diff), lambda: self._trigger_task_notification(task_id))
                    self.scheduled_notifications[task_id] = after_id # Store the after ID
                    logging.info(f"Scheduled notification for task '{task['task']}' (ID: {task_id}) at {due_time_str}.")
            except ValueError as e:
                logging.warning(f"Invalid due time format for task '{task['task']}' (ID: {task_id}): {due_time_str}. Error: {e}")
                # Handle invalid time format gracefully (no notification scheduled)
                pass
            except Exception as e:
                logging.error(f"Error scheduling notification for task '{task['task']}' (ID: {task_id}): {e}")
                # Catch any other unexpected errors during scheduling
                pass

    def _cancel_notification_for_task(self, task_id: str) -> None:
        """
        Cancels a previously scheduled Tkinter 'after' notification for a given task ID.
        """
        if task_id in self.scheduled_notifications:
            try:
                self.root.after_cancel(self.scheduled_notifications[task_id])
                del self.scheduled_notifications[task_id] # Remove from tracking dictionary
                logging.info(f"Cancelled notification for task ID: {task_id}")
            except Exception as e:
                logging.warning(f"Error cancelling notification for task ID {task_id}: {e}. It might have already fired or been cancelled.")
                pass 
        else:
            logging.debug(f"No active notification found for task ID: {task_id} to cancel.")

    def _schedule_all_current_tasks_notifications(self) -> None:
        """
        Clears all currently scheduled notifications and re-schedules them
        for all undone tasks for the current day.
        Called on app load and date changes.
        """
        logging.info("Rescheduling all current tasks notifications.")
        # Clear all existing schedules
        for task_id in list(self.scheduled_notifications.keys()):
            self._cancel_notification_for_task(task_id)

        # Schedule notifications for all currently loaded undone tasks
        for task in self.tasks.values():
            self._schedule_notifications_for_task(task)
        logging.info("All current tasks notifications rescheduled.")

    def _trigger_task_notification(self, task_id: str) -> None:
        """
        Callback function executed when a scheduled task notification's time arrives.
        Triggers the actual system notification if the task is still undone.
        """
        # Retrieve the task by its ID to check its current state
        found_task = self.tasks.get(task_id)
        
        # Only send notification if the task still exists and is not yet done
        if found_task and not found_task['done']:
            logging.info(f"Triggering notification for task: '{found_task['task']}' (ID: {task_id})")
            self._send_notification("Task Reminder!", f"It's time for: {found_task['task']}")
        else:
            logging.info(f"Notification triggered for task ID: {task_id}, but task not found or already done. Skipping notification.")
        
        # Remove from scheduled_notifications once triggered (regardless of whether notification was sent)
        if task_id in self.scheduled_notifications:
            del self.scheduled_notifications[task_id]

    def _schedule_auto_save(self) -> None:
        """
        Schedules the auto-save function to run periodically.
        Cancels any existing auto-save schedule before setting a new one.
        """
        # Cancel any existing auto-save to prevent multiple schedules
        if self.auto_save_id:
            self.root.after_cancel(self.auto_save_id)
            self.auto_save_id = None
            logging.debug("Cancelled previous auto-save schedule.")
        
        # Schedule the next auto-save in 5 minutes (300,000 milliseconds)
        # You can adjust this interval as needed (e.g., 60000 for 1 minute)
        AUTO_SAVE_INTERVAL_MS = 300000 
        self.auto_save_id = self.root.after(AUTO_SAVE_INTERVAL_MS, self._perform_auto_save)
        logging.info(f"Auto-save scheduled for {AUTO_SAVE_INTERVAL_MS / 1000} seconds from now.")

    def _perform_auto_save(self) -> None:
        """
        Performs the auto-save operation and then reschedules itself.
        """
        logging.info("Performing auto-save.")
        self._save_app_state()
        # Reschedule auto-save for the next interval
        self._schedule_auto_save()

    def _show_info(self, title: str, message: str) -> None:
        """
        Displays an informational message using CustomDialog and logs it.
        """
        logging.info(f"Info Dialog: {title} - {message}")
        dialog = ui_dialogs.CustomDialog(self.root, title, message, buttons=[("OK", "ok", ACCENT_COLOR)])
        dialog.show()

    def _show_warning(self, title: str, message: str) -> None:
        """
        Displays a warning message using CustomDialog and logs it.
        """
        logging.warning(f"Warning Dialog: {title} - {message}")
        dialog = ui_dialogs.CustomDialog(self.root, title, message, buttons=[("OK", "ok", WARNING_COLOR)])
        dialog.show()

    def _show_error(self, title: str, message: str) -> None:
        """
        Displays an error message using CustomDialog and logs it.
        """
        logging.error(f"Error Dialog: {title} - {message}")
        dialog = ui_dialogs.CustomDialog(self.root, title, message, buttons=[("OK", "ok", ERROR_COLOR)])
        dialog.show()

    def _ask_custom_yesno(self, title: str, message: str) -> bool:
        """
        Displays a custom Yes/No confirmation dialog and logs the interaction.
        """
        logging.info(f"Confirmation Dialog: {title} - {message}")
        dialog = ui_dialogs.CustomDialog(
            self.root,
            title,
            message,
            buttons=[("Yes", True, SUCCESS_COLOR), ("No", False, ERROR_COLOR)]
        )
        result = dialog.show()
        logging.info(f"Confirmation Dialog result: {result}")
        return result

    def set_daily_goal(self) -> None:
        """
        Opens a dialog to allow the user to set or update their daily XP goal.
        """
        current_goal: int = self.xp_goals.get("daily_goal", 0)
        logging.info(f"Opening dialog to set daily XP goal. Current goal: {current_goal}")
        dialog = ui_dialogs.CustomDialog(
            self.root,
            "Set Daily XP Goal",
            "Enter your daily XP goal:",
            buttons=[("Set", "set", ACCENT_COLOR), ("Cancel", None, ERROR_COLOR)],
            entry_text=str(current_goal) # Pre-fill with current goal
        )
        result = dialog.show()

        if result == "set":
            goal_value_str: str = dialog.entry_var.get().strip()
            if goal_value_str.isdigit() and int(goal_value_str) >= 0:
                new_goal: int = int(goal_value_str)
                self.xp_goals["daily_goal"] = new_goal
                self.xp_goals["last_daily_reset"] = self.current_date # Reset goal tracking for today
                # Recalculate daily_xp_today to ensure consistency after setting new goal
                self.daily_xp_today = sum(t['xp'] for t in self.tasks.values() if t['done'])
                self.save_goals() # Save updated goal
                self.update_daily_goal_display() # Refresh goal display
                self._show_info("Goal Set!", f"Daily XP goal set to {self.xp_goals['daily_goal']} XP.")
                logging.info(f"Daily XP goal set to: {new_goal}")
            else:
                self._show_error("Error", "Please enter a valid positive number for the goal.")
                logging.warning(f"Invalid input for daily goal: '{goal_value_str}'")
        else:
            logging.info("Setting daily XP goal cancelled by user.")

    def update_daily_goal_display(self) -> None:
        """
        Updates the daily goal label and progress bar based on current daily XP and goal.
        Triggers a "goal met" popup and notification if the goal is reached.
        """
        daily_goal: int = self.xp_goals.get("daily_goal", 0)
        
        # Always recalculate daily_xp_today based on current tasks for robustness
        self.daily_xp_today = sum(t['xp'] for t in self.tasks.values() if t['done'])

        # Reset daily XP if a new day has started since the last reset
        if self.xp_goals.get("last_daily_reset") != self.current_date:
            self.daily_xp_today = 0
            self.xp_goals["last_daily_reset"] = self.current_date
            self.save_goals()
            self._goal_met_shown_for_today = False # Reset flag for new day
            logging.info("Daily XP reset for new day.")

        self.daily_goal_label.config(text=f"Daily Goal: {self.daily_xp_today} / {daily_goal} XP")
        
        # Configure progress bar based on goal
        if daily_goal > 0:
            self.daily_goal_progressbar.config(maximum=daily_goal, value=self.daily_xp_today)
        else:
            # If goal is 0, set max to 1 to avoid division by zero and show empty progress
            self.daily_goal_progressbar.config(maximum=1, value=0)
        
        self.root.update_idletasks() # Force UI update for the progress bar

        # Check if daily goal is met and trigger popup/notification
        if self.daily_xp_today >= daily_goal and daily_goal > 0:
            if not self._goal_met_shown_for_today: # Only show once per day
                self.daily_goal_progressbar.config(style="GoalMet.Horizontal.TProgressbar") # Change progress bar color
                self._show_goal_met_popup()
                self._send_notification("Daily Goal Achieved!", f"You've reached your daily XP goal of {daily_goal} XP! Keep up the great work! 🎉")
                self._goal_met_shown_for_today = True
                logging.info(f"Daily goal of {daily_goal} XP achieved!")
        else:
            self.daily_goal_progressbar.config(style="Custom.Horizontal.TProgressbar") # Reset progress bar color
            if self._goal_met_shown_for_today:
                self._goal_met_shown_for_today = False # Reset flag if goal is no longer met
                logging.info("Daily goal status changed from met to not met.")

    def add_task_from_entry(self) -> None:
        """
        Adds a new task based on user input from the main entry field.
        Opens a TaskDetailsDialog to collect full task information.
        """
        task_desc: str = self.task_entry.get().strip()
        if not task_desc:
            self._show_warning("Warning", "Task description cannot be empty.")
            logging.warning("Attempted to add task with empty description.")
            return

        logging.info(f"Attempting to add new task: '{task_desc}'")
        # Open TaskDetailsDialog to get XP, due time, etc.
        dialog = ui_dialogs.TaskDetailsDialog(self.root, self.xp_categories, initial_task_name=task_desc)
        returned_task_data = dialog.show() 

        if returned_task_data and isinstance(returned_task_data, dict):
            new_task_id = generate_unique_id() # Generate a unique ID for the new task
            new_task: dict = {
                "id": new_task_id, # Assign the unique ID
                "task": returned_task_data["task"],
                "done": False,
                "xp": returned_task_data["xp"],
                "due_time": returned_task_data["due_time"]
            }
            self.tasks[new_task_id] = new_task # Add the new task to the tasks dictionary
            self.save_tasks() # Save updated tasks
            self.populate_tasks() # Refresh UI
            self.task_entry.delete(0, tk.END) # Clear the entry field
            self._schedule_notifications_for_task(new_task) # Schedule notification for new task
            logging.info(f"Task '{new_task['task']}' (ID: {new_task_id}) added successfully.")
        else:
            logging.info("Adding new task cancelled or returned invalid data.")
            # Dialog was cancelled or returned invalid data, do not add task
            pass

    def on_enter_add_task(self, event: tk.Event) -> None:
        """Event handler for pressing Enter key in the task entry field."""
        logging.debug("Enter key pressed in task entry. Calling add_task_from_entry.")
        self.add_task_from_entry()

    def _ask_manual_xp(self, task_desc: str, initial_xp: int = None) -> int | None:
        """
        Opens a custom dialog to ask the user for manual XP input.
        Used when adding/editing categories.
        """
        logging.info(f"Asking for manual XP for '{task_desc}'.")
        dialog = ui_dialogs.CustomDialog(
            self.root,
            "Manual XP",
            f"Enter XP points for '{task_desc}':",
            buttons=[("OK", "ok", ACCENT_COLOR), ("Cancel", None, ERROR_COLOR)],
            entry_text=str(initial_xp) if initial_xp is not None else ""
        )
        result = dialog.show()

        if result is None:
            logging.info("Manual XP input cancelled by user.")
            return None # User cancelled
        
        xp_value_str: str = dialog.entry_var.get().strip()
        if xp_value_str.isdigit():
            logging.info(f"Manual XP entered for '{task_desc}': {xp_value_str}")
            return int(xp_value_str)
        else:
            self._show_error("Error", "Please enter a valid number for XP.")
            logging.warning(f"Invalid manual XP input for '{task_desc}': '{xp_value_str}'")
            return None

    def add_recurring_task(self) -> None:
        """
        Opens a dialog to add a new recurring task definition.
        """
        logging.info("Opening dialog to add recurring task.")
        dialog = ui_dialogs.AddRecurringTaskDialog(self.root, self.xp_categories)
        returned_task_data = dialog.show()

        if returned_task_data and isinstance(returned_task_data, dict):
            # Assign a unique ID to the recurring task itself
            if 'id' not in returned_task_data:
                returned_task_data['id'] = generate_unique_id()
            self.recurring_tasks.append(returned_task_data) # Add to recurring tasks list
            self.save_recurring_tasks() # Save updated recurring tasks
            self._show_info("Recurring Task Added", f"'{returned_task_data['task']}' added as a recurring task.")
            self.populate_tasks() # Refresh main task list (might generate new task for today)
            logging.info(f"Recurring task '{returned_task_data['task']}' (ID: {returned_task_data['id']}) added successfully.")
        else:
            logging.info("Adding recurring task cancelled or returned invalid data.")
            # Dialog was cancelled or returned invalid data
            pass

    def manage_recurring_tasks(self) -> None:
        """
        Opens a dedicated window to manage (view, edit, delete) recurring tasks.
        """
        logging.info("Opening recurring tasks management window.")
        ui_dialogs.ManageRecurringTasksWindow(self.root, self)

    def edit_recurring_task(self, task_id_to_edit: str, refresh_callback: callable) -> None:
        """
        Opens a dialog to edit an existing recurring task definition.
        Identifies the task by its unique ID.
        """
        logging.info(f"Attempting to edit recurring task with ID: {task_id_to_edit}")
        original_index = -1
        task_to_edit = None
        # Find the recurring task by its ID
        for i, task in enumerate(self.recurring_tasks):
            if task.get('id') == task_id_to_edit:
                original_index = i
                task_to_edit = task
                break
        
        if original_index == -1:
            logging.error(f"Could not find recurring task with ID: {task_id_to_edit} to edit.")
            self._show_error("Error", "Could not find the recurring task to edit.")
            return

        # Open the AddRecurringTaskDialog in edit mode
        dialog = ui_dialogs.AddRecurringTaskDialog(self.root, self.xp_categories, initial_task=task_to_edit)
        returned_task_data = dialog.show() 

        if returned_task_data and isinstance(returned_task_data, dict):
            # Ensure the ID remains the same for the existing task
            returned_task_data["id"] = task_id_to_edit 
            # Preserve last_generated_date, as it's not edited in the dialog
            returned_task_data["last_generated_date"] = task_to_edit.get("last_generated_date")
            self.recurring_tasks[original_index] = returned_task_data # Update the recurring task
            self.save_recurring_tasks() # Save updated recurring tasks
            self._show_info("Recurring Task Updated", f"'{returned_task_data['task']}' updated.")
            refresh_callback() # Callback to refresh the recurring tasks management window
            self.populate_tasks() # Refresh main task list (might update existing instances)
            logging.info(f"Recurring task '{returned_task_data['task']}' (ID: {task_id_to_edit}) updated successfully.")
        else:
            logging.info(f"Editing recurring task '{task_to_edit.get('task', 'N/A')}' (ID: {task_id_to_edit}) cancelled or returned invalid data.")
            # Edit was cancelled or data was invalid
            pass

    def delete_recurring_task(self, task_id_to_delete: str, refresh_callback: callable) -> None:
        """
        Deletes a recurring task definition after user confirmation.
        Identifies the task by its unique ID.
        """
        logging.info(f"Attempting to delete recurring task with ID: {task_id_to_delete}")
        task_found = None
        original_index = -1
        # Find the recurring task by its ID
        for i, task in enumerate(self.recurring_tasks):
            if task.get('id') == task_id_to_delete:
                task_found = task
                original_index = i
                break

        if not task_found:
            logging.error(f"Could not find recurring task with ID: {task_id_to_delete} to delete.")
            self._show_error("Error", "Could not find the recurring task to delete.")
            return

        # Ask for confirmation before deleting
        confirm: bool = self._ask_custom_yesno("Confirm Delete Recurring Task", f"Are you sure you want to delete recurring task:\n'{task_found['task']}'?")
        if confirm:
            if original_index != -1:
                del self.recurring_tasks[original_index] # Delete the recurring task
                self.save_recurring_tasks() # Save updated recurring tasks
                self._show_info("Recurring Task Deleted", f"'{task_found['task']}' deleted from recurring tasks.")
                refresh_callback() # Callback to refresh the recurring tasks management window
                logging.info(f"Recurring task '{task_found['task']}' (ID: {task_id_to_delete}) deleted successfully.")
            else:
                # Should not happen if task_found is True
                logging.error(f"Internal error: Recurring task '{task_found['task']}' (ID: {task_id_to_delete}) found but index not valid for deletion.")
                self._show_error("Error", "Could not find the recurring task to delete (internal error).")
        else:
            logging.info(f"Deletion of recurring task '{task_found['task']}' (ID: {task_id_to_delete}) cancelled by user.")
            # Deletion cancelled
            pass

    def edit_task(self, task_id_to_edit: str) -> None:
        """
        Opens a custom dialog to edit an existing daily task.
        Identifies the task by its unique ID.
        """
        logging.info(f"Attempting to edit daily task with ID: {task_id_to_edit}")
        task_to_edit = self.tasks.get(task_id_to_edit) # Retrieve task dictionary by its ID
        
        if not task_to_edit:
            logging.error(f"Could not find daily task with ID: {task_id_to_edit} to edit.")
            self._show_error("Error", "Could not find the task to edit.")
            return

        original_xp: int = task_to_edit["xp"] # Store original XP for potential adjustment

        # Open TaskDetailsDialog in edit mode, passing the full task dictionary
        dialog = ui_dialogs.TaskDetailsDialog(self.root, self.xp_categories, initial_task=task_to_edit)
        returned_task_data = dialog.show() 

        if returned_task_data and isinstance(returned_task_data, dict):
            # Update the task details in the self.tasks dictionary
            self.tasks[task_id_to_edit]["task"] = returned_task_data["task"]
            self.tasks[task_id_to_edit]["xp"] = returned_task_data["xp"]
            self.tasks[task_id_to_edit]["due_time"] = returned_task_data["due_time"]
            
            # Adjust total XP if the task was already marked done and XP value changed
            if task_to_edit["done"]:
                logging.info(f"Task '{task_to_edit['task']}' (ID: {task_id_to_edit}) was done. Adjusting XP from {original_xp} to {returned_task_data['xp']}.")
                self.remove_xp(original_xp) # Remove old XP
                self.add_xp(returned_task_data["xp"]) # Add new XP
                
            # Re-schedule notification for the updated task
            self._cancel_notification_for_task(task_id_to_edit) # Cancel old notification
            self._schedule_notifications_for_task(self.tasks[task_id_to_edit]) # Schedule new one

            self.save_tasks() # Save updated tasks
            self.populate_tasks() # Refresh UI
            self.update_daily_goal_display() # Update daily goal display
            logging.info(f"Daily task '{task_to_edit['task']}' (ID: {task_id_to_edit}) updated successfully.")
        else:
            logging.info(f"Editing daily task '{task_to_edit.get('task', 'N/A')}' (ID: {task_id_to_edit}) cancelled or returned invalid data.")
            # Edit was cancelled or data was invalid
            pass

    def delete_task(self, task_id_to_delete: str) -> None:
        """
        Deletes a daily task. Instead of immediate permanent deletion, it stores the task
        temporarily for an "undo" option and shows a notification.
        """
        logging.info(f"Attempting to delete daily task with ID: {task_id_to_delete}")
        task_found = self.tasks.get(task_id_to_delete) # Retrieve task dictionary by its ID

        if not task_found:
            logging.error(f"Could not find daily task with ID: {task_id_to_delete} to delete.")
            self._show_error("Error", "Could not find the task to delete.")
            return

        # Ask for confirmation before deleting, showing the task name
        confirm: bool = self._ask_custom_yesno("Confirm Delete", f"Are you sure you want to delete task:\n'{task_found['task']}'?")
        if confirm:
            logging.info(f"User confirmed deletion of task '{task_found['task']}' (ID: {task_id_to_delete}).")
            # If there's a task already in recently_deleted_tasks, permanently delete it first
            # This simplifies the undo logic to only handle one pending undo at a time
            if self.recently_deleted_tasks:
                # Get the ID of the task that was previously marked for deletion
                prev_deleted_task_id = list(self.recently_deleted_tasks.keys())[0]
                logging.info(f"Another task (ID: {prev_deleted_task_id}) was pending undo. Permanently deleting it now.")
                self._permanently_delete_task(prev_deleted_task_id, save_state=True) # Force permanent deletion and save

            # Remove XP if task was already done
            if task_found["done"]:
                self.remove_xp(task_found["xp"]) 
            
            # Temporarily remove from current tasks display
            del self.tasks[task_id_to_delete] 
            self._cancel_notification_for_task(task_id_to_delete) # Cancel any pending notification

            # Store the task for potential undo
            # Schedule permanent deletion after 5 seconds
            undo_timeout_id = self.root.after(5000, lambda: self._permanently_delete_task(task_id_to_delete, save_state=True))
            self.recently_deleted_tasks[task_id_to_delete] = (task_found, undo_timeout_id)
            
            self.populate_tasks() # Refresh UI to show task removed
            self.update_daily_goal_display() # Update daily goal display
            self._show_undo_notification(task_found['task']) # Show undo notification

        else:
            logging.info(f"Deletion of task '{task_found['task']}' (ID: {task_id_to_delete}) cancelled by user.")
            # Deletion cancelled
            pass

    def _permanently_delete_task(self, task_id: str, save_state: bool = False) -> None:
        """
        Performs the permanent deletion of a task. This is called after the undo timeout
        or when a new task is deleted (invalidating the previous undo).
        """
        logging.info(f"Attempting permanent deletion of task ID: {task_id}. Save state: {save_state}")
        # Ensure the task is no longer in the temporary undo storage
        if task_id in self.recently_deleted_tasks:
            task_data, after_id = self.recently_deleted_tasks.pop(task_id)
            if after_id:
                try:
                    self.root.after_cancel(after_id) # Ensure the timer is cancelled
                    logging.debug(f"Cancelled undo timeout for task ID: {task_id}.")
                except Exception as e:
                    logging.warning(f"Error cancelling undo timeout for task ID {task_id}: {e}. It might have already fired or been cancelled.")
            
            # If the task was not undone, it means it's now permanently deleted.
            # No need to remove from self.tasks again, as it was already removed in delete_task.
            # We just need to save the state if requested.
            if save_state:
                self.save_tasks() # Save the state after permanent deletion
                logging.info(f"Task ID: {task_id} permanently deleted and state saved.")
        else:
            logging.debug(f"Task ID: {task_id} not found in recently_deleted_tasks for permanent deletion. Already handled?")

        self._hide_undo_notification() # Ensure notification is hidden

    def undo_delete_task(self) -> None:
        """
        Restores the last deleted task if an undo is pending.
        """
        logging.info("Attempting to undo last task deletion.")
        if not self.recently_deleted_tasks:
            self._show_info("No Undo Available", "There are no recently deleted tasks to undo.")
            logging.info("Undo requested, but no recently deleted tasks found.")
            return

        # For simplicity, we handle only the last deleted task
        # Get the first (and only) item from the dictionary
        task_id_to_restore = list(self.recently_deleted_tasks.keys())[0]
        task_data_to_restore, after_id = self.recently_deleted_tasks.pop(task_id_to_restore)

        # Cancel the scheduled permanent deletion
        if after_id:
            try:
                self.root.after_cancel(after_id)
                logging.debug(f"Cancelled permanent deletion timeout for restored task ID: {task_id_to_restore}.")
            except Exception as e:
                logging.warning(f"Error cancelling permanent deletion timeout for task ID {task_id_to_restore}: {e}. It might have already fired or been cancelled.")

        # Restore the task to the current tasks dictionary
        self.tasks[task_id_to_restore] = task_data_to_restore
        self.save_tasks() # Save the restored task
        logging.info(f"Task '{task_data_to_restore['task']}' (ID: {task_id_to_restore}) restored.")

        # If the task was done before deletion, re-add its XP
        if task_data_to_restore["done"]:
            logging.info(f"Restored task '{task_data_to_restore['task']}' was done. Re-adding {task_data_to_restore['xp']} XP.")
            self.add_xp(task_data_to_restore["xp"])
            self._show_xp_popup(task_data_to_restore["xp"], "add")
        
        # Re-schedule notification for the restored task if it was undone
        self._schedule_notifications_for_task(task_data_to_restore)

        self.populate_tasks() # Refresh UI to show task restored
        self.update_daily_goal_display() # Update daily goal display
        self._hide_undo_notification() # Hide the undo notification bar
        self._show_info("Task Restored", f"'{task_data_to_restore['task']}' has been restored.")


    def select_date(self) -> None:
        """
        Allows the user to select a different date using a custom calendar dialog.
        Loads tasks for the selected date and refreshes the UI.
        """
        logging.info("Opening date selection dialog.")
        initial_date_obj: datetime.date = datetime.datetime.strptime(self.current_date, "%Y-%m-%d").date()
        calendar_dialog = ui_dialogs.CalendarDialog(self.root, initial_date=initial_date_obj)
        selected_date_str: str | None = calendar_dialog.show()

        if selected_date_str:
            logging.info(f"Date selected: {selected_date_str}. Changing current date.")
            self.current_date = selected_date_str # Update current date
            self.date_btn.config(text=f"Select Date ({self.current_date})") # Update button text
            self._load_app_state() # Load tasks and state for the new date
            self.populate_tasks() # Refresh UI with new tasks
            self.update_level_xp_labels(animated=False) # Update XP/level display
            self.update_daily_goal_display() # Update daily goal display
        else:
            logging.info("Date selection cancelled by user.")
            # Date selection cancelled
            pass

    def edit_categories_window(self) -> None:
        """
        Opens a dedicated window to edit XP categories, their values, and add/delete categories.
        """
        logging.info("Opening XP Categories edit window.")
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit XP Categories")
        dialog.geometry("500x500")
        dialog.configure(bg=DARK_BG)
        dialog.transient(self.root) # Make it transient to the main window
        dialog.grab_set() # Make it modal

        center_window(dialog, self.root)

        existing_cats_frame = tk.LabelFrame(dialog, text="Existing Categories", bg=DARK_BG, fg=DARK_TEXT, font=("Segoe UI", 12, "bold"), bd=2, relief="groove")
        existing_cats_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Canvas and Scrollbar for scrollable category list
        cat_canvas = tk.Canvas(existing_cats_frame, bg=DARK_FRAME_BG, highlightthickness=0)
        cat_scrollbar = tk.Scrollbar(existing_cats_frame, orient="vertical", command=cat_canvas.yview)
        self.cat_scrollable_frame = tk.Frame(cat_canvas, bg=DARK_FRAME_BG)

        self.cat_scrollable_frame.bind(
            "<Configure>",
            lambda e: cat_canvas.configure(scrollregion=cat_canvas.bbox("all"))
        )
        cat_canvas.create_window((0, 0), window=self.cat_scrollable_frame, anchor="nw")
        cat_canvas.configure(yscrollcommand=cat_scrollbar.set)
        cat_canvas.pack(side="left", fill="both", expand=True)
        cat_scrollbar.pack(side="right", fill="y")

        self.cat_vars: dict = {} # Stores StringVar for each category's XP value

        def populate_category_list() -> None:
            """Populates the list of XP categories in the edit window."""
            logging.debug("Populating category list in edit window.")
            for widget in self.cat_scrollable_frame.winfo_children():
                widget.destroy() # Clear existing widgets
            self.cat_vars.clear() # Clear stored StringVar references

            row: int = 0
            for cat, xp in self.xp_categories.items():
                cat_row_frame = tk.Frame(self.cat_scrollable_frame, bg=DARK_FRAME_BG)
                cat_row_frame.grid(row=row, column=0, sticky="ew", pady=2, padx=5)
                self.cat_scrollable_frame.grid_columnconfigure(0, weight=1)

                tk.Label(cat_row_frame, text=cat, bg=DARK_FRAME_BG, fg=DARK_TEXT, font=("Segoe UI", 12)).grid(row=0, column=0, sticky="w", pady=5)
                
                var = tk.StringVar(value=str(xp) if xp is not None else "")
                entry = tk.Entry(cat_row_frame, textvariable=var, font=("Segoe UI", 12), width=10,
                                 bg=DARK_BG, fg=DARK_TEXT, insertbackground=ACCENT_COLOR, bd=1, relief="solid")
                entry.grid(row=0, column=1, pady=5, padx=5)
                self.cat_vars[cat] = var # Store StringVar for later retrieval

                if cat != "Miscellaneous": # Prevent deleting the default "Miscellaneous" category
                    del_cat_btn = tk.Button(cat_row_frame, text="🗑️", font=("Segoe UI", 10),
                                            bg=ERROR_COLOR, fg="white", relief="flat", padx=5, pady=2,
                                            command=lambda c=cat: delete_category(c),
                                            activebackground="#a03d45", activeforeground="white")
                    del_cat_btn.grid(row=0, column=2, padx=5)
                
                cat_row_frame.grid_columnconfigure(0, weight=1)
                cat_row_frame.grid_columnconfigure(1, weight=0)
                cat_row_frame.grid_columnconfigure(2, weight=0)

                row += 1
            cat_canvas.update_idletasks()
            cat_canvas.config(scrollregion=cat_canvas.bbox("all"))


        def add_new_category() -> None:
            """Opens a dialog to add a new XP category."""
            logging.info("Attempting to add new category.")
            dialog_add = ui_dialogs.CustomDialog(
                dialog,
                "Add New Category",
                "Enter new category name:",
                buttons=[("Next", "next", ACCENT_COLOR), ("Cancel", None, ERROR_COLOR)],
                entry_text=""
            )
            cat_name_result = dialog_add.show()

            if cat_name_result == "next":
                category_name: str = dialog_add.entry_var.get().strip()
                if not category_name:
                    self._show_warning("Warning", "Category name cannot be empty.")
                    logging.warning("Attempted to add category with empty name.")
                    return

                if category_name in self.xp_categories:
                    self._show_warning("Warning", f"Category '{category_name}' already exists.")
                    logging.warning(f"Attempted to add existing category: '{category_name}'")
                    return
                
                # Ask for default XP for the new category
                xp_value: int | None = self._ask_manual_xp(f"Default XP for '{category_name}'", initial_xp="")
                if xp_value is None:
                    xp_for_new_cat: int | None = None # User cancelled or entered invalid XP
                else:
                    xp_for_new_cat = xp_value

                self.xp_categories[category_name] = xp_for_new_cat # Add new category
                self.save_categories() # Save categories
                populate_category_list() # Refresh category list in the window
                logging.info(f"New category '{category_name}' added with default XP: {xp_for_new_cat}.")
            else:
                logging.info("Adding new category cancelled by user.")

        def delete_category(category_name: str) -> None:
            """Deletes an XP category after confirmation."""
            logging.info(f"Attempting to delete category: '{category_name}'")
            confirm: bool = self._ask_custom_yesno("Confirm Delete Category", f"Are you sure you want to delete category:\n'{category_name}'?\nTasks using this category will revert to 'Miscellaneous' XP.")
            if confirm:
                if category_name in self.xp_categories:
                    del self.xp_categories[category_name] # Delete category
                    self.save_categories() # Save categories
                    populate_category_list() # Refresh category list
                    self.populate_tasks() # Refresh main tasks (tasks using this category will now show 'Miscellaneous' XP)
                    logging.info(f"Category '{category_name}' deleted successfully.")
                else:
                    logging.error(f"Could not find category '{category_name}' to delete.")
                    self._show_error("Error", "Could not find the category to delete.")
            else:
                logging.info(f"Deletion of category '{category_name}' cancelled by user.")

        def save_and_close_categories() -> None:
            """Saves all changes to XP categories and closes the edit window."""
            logging.info("Saving category changes and closing window.")
            new_categories: dict = {}
            for cat, var in self.cat_vars.items():
                val: str = var.get().strip()
                if val == "":
                    new_categories[cat] = None # Store as None if XP is empty
                else:
                    try:
                        new_categories[cat] = int(val) # Convert to integer
                    except ValueError:
                        error_msg = f"XP for '{cat}' must be a number or empty."
                        self._show_error("Error", error_msg)
                        logging.error(f"Invalid XP value for category '{cat}': '{val}'. Error: {error_msg}")
                        return # Stop if invalid input
            self.xp_categories = new_categories # Update categories
            self.save_categories() # Save categories
            dialog.destroy() # Close the dialog
            self.populate_tasks() # Refresh main tasks (to reflect category changes)
            logging.info("Category changes saved and window closed.")

        # Buttons for category actions
        cat_action_frame = tk.Frame(dialog, bg=DARK_BG)
        cat_action_frame.pack(pady=10)
        tk.Button(cat_action_frame, text="Add New Category \u2795", command=add_new_category,
                  bg=SUCCESS_COLOR, fg=DARK_BG, font=("Segoe UI", 11, "bold"), relief="flat", padx=10, pady=6,
                  activebackground="#79a361", activeforeground=DARK_TEXT).pack(side="left", padx=5)
        
        btn_frame = tk.Frame(dialog, bg=DARK_BG)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Save Changes", command=save_and_close_categories,
                  bg=ACCENT_COLOR, fg=DARK_BG, font=("Segoe UI", 12, "bold"), relief="flat", padx=10, pady=6,
                  activebackground="#4a8ec9", activeforeground=DARK_TEXT).pack(side="left", padx=10)
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy,
                  bg=ERROR_COLOR, fg="white", font=("Segoe UI", 12, "bold"), relief="flat", padx=10, pady=6,
                  activebackground="#a03d45", activeforeground="white").pack(side="left", padx=10)

        populate_category_list() # Initial population of the category list
        self.root.wait_window(dialog) # Wait for the dialog to close

    def view_xp_history(self) -> None:
        """Opens a new window to display the history of daily XP earned."""
        logging.info("Opening XP History window.")
        latest_tasks_data: dict = self.data_manager.load_tasks_data() # Load fresh data
        # Pass the main app instance to the history window
        ui_dialogs.XPHistoryWindow(self.root, latest_tasks_data, self)


if __name__ == "__main__":
    # Main entry point for the application
    root = tk.Tk()
    app = XPDashboardApp(root)
    root.mainloop() # Start the Tkinter event loop
