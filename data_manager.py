# data_manager.py
import json
import os
import shutil
import datetime
import logging
from typing import List, Dict, Optional, Union

# Import custom TypedDicts for structured data
from custom_types import Task, RecurringTask

# Configure logging for this module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class DataManager:
    """
    Manages loading and saving application data (tasks, categories, goals, recurring tasks)
    to JSON files. This centralizes file I/O operations and adds backup.
    """
    def __init__(self, data_file: str, categories_file: str, goals_file: str, recurring_tasks_file: str):
        self.data_file = data_file
        self.categories_file = categories_file
        self.goals_file = goals_file
        self.recurring_tasks_file = recurring_tasks_file
        logging.info(f"DataManager initialized with data_file: {self.data_file}")

    def _backup_file(self, file_path: str) -> None:
        """Creates a backup of the given file."""
        if os.path.exists(file_path):
            try:
                # Attempt atomic replacement (rename) first
                os.replace(file_path, file_path + ".bak")
                logging.debug(f"Backed up {file_path} using os.replace.")
            except OSError as e:
                # Fallback to copy if os.replace fails (e.g., cross-device link)
                logging.warning(f"os.replace failed for {file_path}: {e}. Falling back to shutil.copy2.")
                try:
                    shutil.copy2(file_path, file_path + ".bak")
                    logging.debug(f"Backed up {file_path} using shutil.copy2.")
                except Exception as copy_e:
                    logging.error(f"Failed to backup {file_path} even with shutil.copy2: {copy_e}")
            except Exception as e:
                logging.error(f"Unexpected error during backup of {file_path}: {e}")
        else:
            logging.debug(f"No file to backup at {file_path}.")

    def load_tasks_data(self) -> Dict[str, Dict[str, Task]]:
        """
        Loads all tasks data from the tasks JSON file.
        Returns a dictionary where keys are dates (str) and values are dictionaries of Task objects (keyed by task ID).
        Handles file not found and JSON decoding errors, attempting to load from backup.
        """
        if not os.path.exists(self.data_file):
            logging.info(f"Tasks data file not found: {self.data_file}. Returning empty data.")
            return {}
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                # Convert loaded raw data to the expected Dict[str, Dict[str, Task]] format
                # This also handles potential old list-based task data during initial load
                processed_data: Dict[str, Dict[str, Task]] = {}
                for date_key, tasks_for_date in raw_data.items():
                    if date_key.startswith('_'): # Handle metadata like _level, _total_xp
                        processed_data[date_key] = tasks_for_date # Keep as is for now, will be type-checked in app.py
                        continue
                    
                    if isinstance(tasks_for_date, list): # Old format: list of tasks
                        logging.warning(f"Old task list format detected for date {date_key}. Migrating to ID-based dictionary.")
                        converted_tasks: Dict[str, Task] = {}
                        for task_dict in tasks_for_date:
                            # Ensure 'id' exists, generate if missing
                            if 'id' not in task_dict:
                                task_dict['id'] = str(uuid.uuid4()) # Generate UUID for new ID
                            # Ensure all fields conform to Task TypedDict structure
                            converted_tasks[task_dict['id']] = Task(
                                id=task_dict['id'],
                                task=task_dict['task'],
                                done=task_dict['done'],
                                xp=task_dict['xp'],
                                due_time=task_dict.get('due_time'),
                                is_recurring_instance=task_dict.get('is_recurring_instance', False)
                            )
                        processed_data[date_key] = converted_tasks
                    elif isinstance(tasks_for_date, dict): # New format: dict of tasks
                        # Ensure each task within the dictionary conforms to Task TypedDict
                        processed_tasks_dict: Dict[str, Task] = {}
                        for task_id, task_dict in tasks_for_date.items():
                            processed_tasks_dict[task_id] = Task(
                                id=task_id, # Use the key as the ID
                                task=task_dict['task'],
                                done=task_dict['done'],
                                xp=task_dict['xp'],
                                due_time=task_dict.get('due_time'),
                                is_recurring_instance=task_dict.get('is_recurring_instance', False)
                            )
                        processed_data[date_key] = processed_tasks_dict
                    else:
                        logging.error(f"Unexpected data type for tasks on date {date_key}: {type(tasks_for_date)}. Skipping.")
                        processed_data[date_key] = {} # Default to empty dict for corrupted entries

                logging.info(f"Tasks data loaded from {self.data_file}.")
                return processed_data
        except json.JSONDecodeError as e:
            logging.error(f"Could not decode tasks data file {self.data_file}: {e}. Attempting to load from backup.")
            if os.path.exists(self.data_file + ".bak"):
                try:
                    with open(self.data_file + ".bak", "r", encoding="utf-8") as f_bak:
                        backup_data = json.load(f_bak)
                        # Recursive call to process backup data with the same logic
                        logging.info(f"Successfully loaded tasks data from backup: {self.data_file}.bak.")
                        return self.load_tasks_data_from_raw(backup_data) # Helper to process raw data
                except json.JSONDecodeError as backup_e:
                    logging.error(f"Backup tasks data file {self.data_file}.bak also corrupted: {backup_e}. Returning empty data.")
                    return {}
            logging.warning("No valid backup found for tasks data. Returning empty data.")
            return {}
        except Exception as e:
            logging.error(f"An unexpected error occurred while loading tasks data from {self.data_file}: {e}. Returning empty data.")
            return {}

    def load_tasks_data_from_raw(self, raw_data: dict) -> Dict[str, Dict[str, Task]]:
        """Helper to process raw loaded task data into the correct TypedDict format."""
        processed_data: Dict[str, Dict[str, Task]] = {}
        for date_key, tasks_for_date in raw_data.items():
            if date_key.startswith('_'): # Handle metadata like _level, _total_xp
                processed_data[date_key] = tasks_for_date
                continue
            
            if isinstance(tasks_for_date, list): # Old format: list of tasks
                converted_tasks: Dict[str, Task] = {}
                for task_dict in tasks_for_date:
                    if 'id' not in task_dict:
                        task_dict['id'] = str(uuid.uuid4())
                    converted_tasks[task_dict['id']] = Task(
                        id=task_dict['id'],
                        task=task_dict['task'],
                        done=task_dict['done'],
                        xp=task_dict['xp'],
                        due_time=task_dict.get('due_time'),
                        is_recurring_instance=task_dict.get('is_recurring_instance', False)
                    )
                processed_data[date_key] = converted_tasks
            elif isinstance(tasks_for_date, dict): # New format: dict of tasks
                processed_tasks_dict: Dict[str, Task] = {}
                for task_id, task_dict in tasks_for_date.items():
                    processed_tasks_dict[task_id] = Task(
                        id=task_id,
                        task=task_dict['task'],
                        done=task_dict['done'],
                        xp=task_dict['xp'],
                        due_time=task_dict.get('due_time'),
                        is_recurring_instance=task_dict.get('is_recurring_instance', False)
                    )
                processed_data[date_key] = processed_tasks_dict
            else:
                logging.error(f"Unexpected data type for tasks on date {date_key} during raw data processing: {type(tasks_for_date)}. Skipping.")
                processed_data[date_key] = {}
        return processed_data


    def save_tasks_data(self, tasks_data: Dict[str, Dict[str, Task]]) -> None:
        """
        Saves all tasks data to the tasks JSON file.
        Expects a dictionary where keys are dates (str) and values are dictionaries of Task objects.
        """
        self._backup_file(self.data_file)
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(tasks_data, f, indent=2, ensure_ascii=False)
            logging.info(f"Tasks data saved to {self.data_file}.")
        except Exception as e:
            logging.error(f"Failed to save tasks data to {self.data_file}: {e}")

    def load_categories_data(self) -> Dict[str, Optional[int]]:
        """
        Loads XP categories from the categories JSON file.
        Returns a dictionary where keys are category names (str) and values are XP amounts (int) or None.
        """
        default_categories: Dict[str, Optional[int]] = {
            "Easy": 5,
            "Medium": 10,
            "Hard": 15,
            "Miscellaneous": None
        }
        if not os.path.exists(self.categories_file):
            logging.info(f"Categories file not found: {self.categories_file}. Returning default categories.")
            return default_categories
        try:
            with open(self.categories_file, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)
                # Ensure loaded values are int or None
                for key, value in loaded_data.items():
                    if not isinstance(value, (int, type(None))):
                        logging.warning(f"Invalid XP value for category '{key}': {value}. Setting to None.")
                        loaded_data[key] = None
                logging.info(f"Categories data loaded from {self.categories_file}.")
                return loaded_data
        except json.JSONDecodeError as e:
            logging.error(f"Could not decode categories file {self.categories_file}: {e}. Attempting to load from backup.")
            if os.path.exists(self.categories_file + ".bak"):
                try:
                    with open(self.categories_file + ".bak", "r", encoding="utf-8") as f_bak:
                        backup_data = json.load(f_bak)
                        # Ensure backup data also conforms
                        for key, value in backup_data.items():
                            if not isinstance(value, (int, type(None))):
                                logging.warning(f"Invalid XP value in backup for category '{key}': {value}. Setting to None.")
                                backup_data[key] = None
                        logging.info(f"Successfully loaded categories data from backup: {self.categories_file}.bak.")
                        return backup_data
                except json.JSONDecodeError as backup_e:
                    logging.error(f"Backup categories file {self.categories_file}.bak also corrupted: {backup_e}. Returning default categories.")
                    return default_categories
            logging.warning("No valid backup found for categories data. Returning default categories.")
            return default_categories
        except Exception as e:
            logging.error(f"An unexpected error occurred while loading categories data from {self.categories_file}: {e}. Returning default categories.")
            return default_categories

    def save_categories_data(self, categories_data: Dict[str, Optional[int]]) -> None:
        """
        Saves XP categories to the categories JSON file.
        Expects a dictionary where keys are category names (str) and values are XP amounts (int) or None.
        """
        self._backup_file(self.categories_file)
        try:
            with open(self.categories_file, "w", encoding="utf-8") as f:
                json.dump(categories_data, f, indent=2, ensure_ascii=False)
            logging.info(f"Categories data saved to {self.categories_file}.")
        except Exception as e:
            logging.error(f"Failed to save categories data to {self.categories_file}: {e}")

    def load_goals_data(self, current_date: str) -> Dict[str, Union[int, str]]:
        """
        Loads XP goals from the goals JSON file.
        Returns a dictionary with 'daily_goal' (int) and 'last_daily_reset' (str).
        """
        default_goals: Dict[str, Union[int, str]] = {"daily_goal": 0, "last_daily_reset": current_date}
        if not os.path.exists(self.goals_file):
            logging.info(f"Goals file not found: {self.goals_file}. Returning default goals.")
            return default_goals
        try:
            with open(self.goals_file, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)
                # Ensure data conforms to expected types
                if not isinstance(loaded_data.get("daily_goal"), int):
                    loaded_data["daily_goal"] = 0
                    logging.warning("Invalid 'daily_goal' in goals data. Resetting to 0.")
                if not isinstance(loaded_data.get("last_daily_reset"), str):
                    loaded_data["last_daily_reset"] = current_date
                    logging.warning("Invalid 'last_daily_reset' in goals data. Resetting to current date.")
                logging.info(f"Goals data loaded from {self.goals_file}.")
                return loaded_data
        except json.JSONDecodeError as e:
            logging.error(f"Could not decode goals file {self.goals_file}: {e}. Attempting to load from backup.")
            if os.path.exists(self.goals_file + ".bak"):
                try:
                    with open(self.goals_file + ".bak", "r", encoding="utf-8") as f_bak:
                        backup_data = json.load(f_bak)
                        # Ensure backup data also conforms
                        if not isinstance(backup_data.get("daily_goal"), int):
                            backup_data["daily_goal"] = 0
                            logging.warning("Invalid 'daily_goal' in backup goals data. Resetting to 0.")
                        if not isinstance(backup_data.get("last_daily_reset"), str):
                            backup_data["last_daily_reset"] = current_date
                            logging.warning("Invalid 'last_daily_reset' in backup goals data. Resetting to current date.")
                        logging.info(f"Successfully loaded goals data from backup: {self.goals_file}.bak.")
                        return backup_data
                except json.JSONDecodeError as backup_e:
                    logging.error(f"Backup goals file {self.goals_file}.bak also corrupted: {backup_e}. Returning default goals.")
                    return default_goals
            logging.warning("No valid backup found for goals data. Returning default goals.")
            return default_goals
        except Exception as e:
            logging.error(f"An unexpected error occurred while loading goals data from {self.goals_file}: {e}. Returning default goals.")
            return default_goals

    def save_goals_data(self, goals_data: Dict[str, Union[int, str]]) -> None:
        """
        Saves XP goals to the goals JSON file.
        Expects a dictionary with 'daily_goal' (int) and 'last_daily_reset' (str).
        """
        self._backup_file(self.goals_file)
        try:
            with open(self.goals_file, "w", encoding="utf-8") as f:
                json.dump(goals_data, f, indent=2, ensure_ascii=False)
            logging.info(f"Goals data saved to {self.goals_file}.")
        except Exception as e:
            logging.error(f"Failed to save goals data to {self.goals_file}: {e}")

    def load_recurring_tasks_data(self) -> List[RecurringTask]:
        """
        Loads recurring tasks from the recurring tasks JSON file.
        Returns a list of RecurringTask objects.
        """
        if not os.path.exists(self.recurring_tasks_file):
            logging.info(f"Recurring tasks file not found: {self.recurring_tasks_file}. Returning empty list.")
            return []
        try:
            with open(self.recurring_tasks_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                processed_data: List[RecurringTask] = []
                for r_task_dict in raw_data:
                    # Ensure 'id' exists, generate if missing
                    if 'id' not in r_task_dict:
                        r_task_dict['id'] = str(uuid.uuid4())
                    # Ensure all fields conform to RecurringTask TypedDict structure
                    processed_data.append(RecurringTask(
                        id=r_task_dict['id'],
                        task=r_task_dict['task'],
                        xp=r_task_dict['xp'],
                        recurrence_type=r_task_dict['recurrence_type'],
                        recurrence_value=r_task_dict.get('recurrence_value'),
                        due_time=r_task_dict.get('due_time'),
                        last_generated_date=r_task_dict.get('last_generated_date')
                    ))
                logging.info(f"Recurring tasks data loaded from {self.recurring_tasks_file}.")
                return processed_data
        except json.JSONDecodeError as e:
            logging.error(f"Could not decode recurring tasks file {self.recurring_tasks_file}: {e}. Attempting to load from backup.")
            if os.path.exists(self.recurring_tasks_file + ".bak"):
                try:
                    with open(self.recurring_tasks_file + ".bak", "r", encoding="utf-8") as f_bak:
                        backup_data = json.load(f_bak)
                        # Process backup data with the same logic
                        processed_backup_data: List[RecurringTask] = []
                        for r_task_dict in backup_data:
                            if 'id' not in r_task_dict:
                                r_task_dict['id'] = str(uuid.uuid4())
                            processed_backup_data.append(RecurringTask(
                                id=r_task_dict['id'],
                                task=r_task_dict['task'],
                                xp=r_task_dict['xp'],
                                recurrence_type=r_task_dict['recurrence_type'],
                                recurrence_value=r_task_dict.get('recurrence_value'),
                                due_time=r_task_dict.get('due_time'),
                                last_generated_date=r_task_dict.get('last_generated_date')
                            ))
                        logging.info(f"Successfully loaded recurring tasks data from backup: {self.recurring_tasks_file}.bak.")
                        return processed_backup_data
                except json.JSONDecodeError as backup_e:
                    logging.error(f"Backup recurring tasks file {self.recurring_tasks_file}.bak also corrupted: {backup_e}. Returning empty list.")
                    return []
            logging.warning("No valid backup found for recurring tasks data. Returning empty list.")
            return []
        except Exception as e:
            logging.error(f"An unexpected error occurred while loading recurring tasks data from {self.recurring_tasks_file}: {e}. Returning empty list.")
            return []

    def save_recurring_tasks_data(self, recurring_tasks_data: List[RecurringTask]) -> None:
        """
        Saves recurring tasks to the recurring tasks JSON file.
        Expects a list of RecurringTask objects.
        """# data_manager.py
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

        self._backup_file(self.recurring_tasks_file)
        try:
            with open(self.recurring_tasks_file, "w", encoding="utf-8") as f:
                json.dump(recurring_tasks_data, f, indent=2, ensure_ascii=False)
            logging.info(f"Recurring tasks data saved to {self.recurring_tasks_file}.")
        except Exception as e:
            logging.error(f"Failed to save recurring tasks data to {self.recurring_tasks_file}: {e}")

