import os
import sys
import json
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Global cache for settings and questions
SETTINGS: Optional[Dict[str, Any]] = None
QUESTIONS: Optional[List[Dict[str, str]]] = None

def get_app_root_dir() -> str:
    """Get the root directory for data files like settings.json, questions.json.
    For PyInstaller, this is the directory containing the executable.
    For development, this is the 'application_bot' subfolder where these files reside.
    """
    if getattr(sys, 'frozen', False):  # PyInstaller bundle
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_data_file_path(filename_at_root: str) -> str:
    """
    Constructs an absolute path to a data file (e.g. settings.json, questions.json)
    assumed to be at the application root.
    """
    return os.path.join(get_app_root_dir(), filename_at_root)

def get_external_file_path(relative_path_from_app_root: str) -> str:
    """
    Constructs an absolute path to a file/folder (like 'applications' or 'fonts/DejaVuSans.ttf')
    These paths are specified in settings.json as relative to the app root.
    The .spec file ensures these are bundled correctly relative to the executable.
    """
    return os.path.join(get_app_root_dir(), relative_path_from_app_root)

def load_json_file(file_path: str, file_description: str) -> Optional[Any]:
    """Loads a JSON file and handles errors."""
    if not os.path.exists(file_path): # Check before opening
        logger.warning(f"{file_description} file not found at {file_path}. This might be normal if it's the first run for questions.")
        return None # Return None, not an empty list, to distinguish from an empty file.
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if not content.strip(): # File is empty or only whitespace
                logger.warning(f"{file_description} file at {file_path} is empty.")
                if file_description.lower() == "questions": # Specifically for questions, an empty file means no questions
                    return []
                return None # For settings, an empty file is an error
            return json.loads(content)
    except FileNotFoundError: # Should be caught by os.path.exists, but as a safeguard
        logger.critical(f"CRITICAL: {file_description} file not found at {file_path}")
    except json.JSONDecodeError as e:
        logger.critical(f"CRITICAL: Error decoding {file_description} file at {file_path}: {e}")
    except Exception as e:
        logger.critical(f"CRITICAL: An unexpected error occurred while loading {file_description} at {file_path}: {e}")
    return None

def save_settings(settings_data: Dict[str, Any], path: str = "settings.json") -> bool:
    """Saves the settings dictionary to a JSON file at the app root."""
    settings_path = get_data_file_path(path)
    try:
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(settings_data, f, ensure_ascii=False, indent=4)
        logger.info(f"Settings successfully saved to {settings_path}")
        return True
    except FileNotFoundError:
        logger.error(f"Error saving settings: Path not found {settings_path} (this is unexpected for writing).")
    except TypeError as e:
        logger.error(f"Error saving settings: Data is not JSON serializable. {e}")
    except Exception as e:
        logger.error(f"Error saving settings to {settings_path}: {e}")
    return False

def load_settings(path: str = "settings.json") -> bool:
    global SETTINGS
    settings_path = get_data_file_path(path)
    SETTINGS = load_json_file(settings_path, "Settings")
    if SETTINGS is None:
        return False

    for folder_key in ["APPLICATION_FOLDER", "TEMP_PHOTO_FOLDER"]:
        folder_name = SETTINGS.get(folder_key)
        if folder_name:
            try:
                full_folder_path = get_external_file_path(folder_name)
                os.makedirs(full_folder_path, exist_ok=True)
                logger.info(f"Ensured directory exists: {full_folder_path}")
            except OSError as e:
                logger.error(f"Could not create directory {full_folder_path}: {e}")
        else:
            logger.warning(f"Configuration for '{folder_key}' is missing in settings.json.")
    return True

def load_questions() -> bool:
    global QUESTIONS, SETTINGS
    if not SETTINGS:
        logger.error("Settings not loaded. Cannot load questions.")
        QUESTIONS = [] # Ensure QUESTIONS is at least an empty list if settings aren't loaded
        return False
    
    questions_file_name = SETTINGS.get("QUESTIONS_FILE")
    if not questions_file_name:
        logger.critical("CRITICAL: 'QUESTIONS_FILE' not specified in settings.json.")
        QUESTIONS = []
        return False

    questions_path = get_data_file_path(questions_file_name)
    loaded_data = load_json_file(questions_path, "Questions")

    if loaded_data is None: # File not found or major error
        logger.warning(f"Questions file '{questions_path}' not found or error loading. Defaulting to empty questions list.")
        QUESTIONS = []
        return False # Indicate failure to load from file, though QUESTIONS is set to empty.
    elif not isinstance(loaded_data, list):
        logger.error(f"Questions file '{questions_path}' does not contain a list. Defaulting to empty questions list.")
        QUESTIONS = []
        return False
    
    QUESTIONS = loaded_data
    logger.info(f"Successfully loaded {len(QUESTIONS)} questions from {questions_path}.")
    return True

def save_questions(questions_data: List[Dict[str, str]], path: Optional[str] = None) -> bool:
    """Saves the questions list to a JSON file and updates the global QUESTIONS."""
    global QUESTIONS, SETTINGS

    if path is None:
        if SETTINGS and SETTINGS.get("QUESTIONS_FILE"):
            file_name = SETTINGS["QUESTIONS_FILE"]
        else:
            logger.warning("QUESTIONS_FILE not found in settings, using default 'questions.json' for saving.")
            file_name = "questions.json" 
            if SETTINGS: 
                SETTINGS["QUESTIONS_FILE"] = file_name # Update in-memory SETTINGS if we used a default
    else: 
        file_name = path

    questions_file_path = get_data_file_path(file_name)
    
    try:
        with open(questions_file_path, 'w', encoding='utf-8') as f:
            json.dump(questions_data, f, ensure_ascii=False, indent=2) # Original questions.json used indent=2
        logger.info(f"Questions successfully saved to {questions_file_path}")
        QUESTIONS = list(questions_data) # Update global QUESTIONS with a copy
        return True
    except FileNotFoundError: 
        logger.error(f"Error saving questions: Path not found {questions_file_path} (unexpected for 'w' mode).")
    except TypeError as e:
        logger.error(f"Error saving questions: Data is not JSON serializable. {e}")
    except Exception as e:
        logger.error(f"Error saving questions to {questions_file_path}: {e}")
    return False

def get_text(key: str, lang: Optional[str] = None, default: Optional[str] = None, **kwargs) -> str:
    global SETTINGS
    if not SETTINGS:
        return default if default is not None else f"<SETTINGS_NOT_LOADED_FOR_{key}>"

    selected_lang = lang
    if selected_lang is None:
        selected_lang = SETTINGS.get("DEFAULT_LANG", "en")
    
    lang_pack = SETTINGS.get("LANGUAGES", {}).get(selected_lang)
    
    if not lang_pack or key not in lang_pack:
        default_app_lang = SETTINGS.get("DEFAULT_LANG", "en")
        if selected_lang != default_app_lang:
            logger.debug(f"Key '{key}' not in lang '{selected_lang}', trying default app lang '{default_app_lang}'.")
            lang_pack = SETTINGS.get("LANGUAGES", {}).get(default_app_lang, {})
        
        if (not lang_pack or key not in lang_pack) and default_app_lang != "en":
            logger.debug(f"Key '{key}' not in default app lang '{default_app_lang}', trying 'en'.")
            lang_pack = SETTINGS.get("LANGUAGES", {}).get("en", {})

    text_template = lang_pack.get(key) if lang_pack else None

    if text_template is None:
        if default is not None:
            return default
        logger.warning(f"Translation key '{key}' not found for language '{selected_lang}' or fallbacks.")
        return f"<{key}_NOT_FOUND_IN_{selected_lang}>"
    
    try:
        return text_template.format(**kwargs)
    except KeyError as e:
        logger.warning(f"Placeholder {e} missing for i18n key '{key}' in lang '{selected_lang}'. Template: '{text_template}'")
        return text_template
    except Exception as e:
        logger.error(f"Error formatting text for key '{key}' in lang '{selected_lang}': {e}")
        return f"<FORMATTING_ERROR_{key}_{selected_lang}>"