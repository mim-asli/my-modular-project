# data_manager.py
import json
import os
import shutil

# Import constants from the constants module
from constants import DATA_FILE, CATEGORIES_FILE, GOALS_FILE, RECURRING_TASKS_FILE

class DataManager:
    """
    Manages loading and saving application data to JSON files, with backup functionality.
    Ensures data persistence and provides recovery options in case of corruption.
    """
    def __init__(self, data_file: str, categories_file: str, goals_file: str, recurring_tasks_file: str):
        self.data_file = data_file
        self.categories_file = categories_file
        self.goals_file = goals_file
        self.recurring_tasks_file = recurring_tasks_file

    def _backup_file(self, file_path: str) -> None:
        """
        Creates a backup of the given file.
        Renames the existing file to .bak before saving new data.
        """
        if os.path.exists(file_path):
            try:
                # Atomically replace the old backup with the current file
                os.replace(file_path, file_path + ".bak")
            except OSError:
                # Fallback to copy if os.replace fails (e.g., cross-device)
                shutil.copy2(file_path, file_path + ".bak")
            
    def _load_json(self, file_path: str, default_data: any) -> any:
        """
        Generic method to load JSON data from a file.
        Includes backup loading and error handling for JSON decoding issues.
        """
        if not os.path.exists(file_path):
            # Return default data if the file does not exist
            return default_data
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                # Attempt to load data from the primary file
                return json.load(f)
        except json.JSONDecodeError:
            # If primary file is corrupted, try loading from backup
            if os.path.exists(file_path + ".bak"):
                try:
                    with open(file_path + ".bak", "r", encoding="utf-8") as f_bak:
                        return json.load(f_bak)
                except json.JSONDecodeError:
                    # If backup is also corrupted, fall through to return default data
                    pass
            # If both are corrupted or backup doesn't exist, return default
            return default_data

    def _save_json(self, file_path: str, data: any) -> None:
        """
        Generic method to save JSON data to a file.
        Creates a backup before writing the new data to prevent data loss.
        """
        self._backup_file(file_path) # Create a backup of the current file
        with open(file_path, "w", encoding="utf-8") as f:
            # Write the new data to the primary file with indentation for readability
            json.dump(data, f, indent=2, ensure_ascii=False)

    # Specific methods for loading and saving different types of application data
    def load_tasks_data(self) -> dict:
        return self._load_json(self.data_file, {})

    def save_tasks_data(self, tasks_data: dict) -> None:
        self._save_json(self.data_file, tasks_data)

    def load_categories_data(self) -> dict:
        # Default categories with their XP values
        return self._load_json(self.categories_file, {
            "Easy": 5, "Medium": 10, "Hard": 15, "Miscellaneous": None
        })

    def save_categories_data(self, categories_data: dict) -> None:
        self._save_json(self.categories_file, categories_data)

    def load_goals_data(self, current_date: str) -> dict:
        # Default daily goal is 0, reset date is current date
        return self._load_json(self.goals_file, {"daily_goal": 0, "last_daily_reset": current_date})

    def save_goals_data(self, goals_data: dict) -> None:
        self._save_json(self.goals_file, goals_data)

    def load_recurring_tasks_data(self) -> list:
        # Default is an empty list of recurring tasks
        return self._load_json(self.recurring_tasks_file, [])

    def save_recurring_tasks_data(self, recurring_tasks_data: list) -> None:
        self._save_json(self.recurring_tasks_file, recurring_tasks_data)
