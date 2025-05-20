import os
import sys
import json
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Global cache for settings and questions
SETTINGS: Optional[Dict[str, Any]] = None
QUESTIONS: Optional[List[Dict[str, str]]] = None

def get_executable_dir() -> str:
    """Get the directory of the executable or the script."""
    if getattr(sys, 'frozen', False):  # PyInstaller bundle
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__)) # Development

def get_external_file_path(filename: str) -> str:
    """Constructs an absolute path to a file assumed to be in the same dir as the executable."""
    return os.path.join(get_executable_dir(), filename)

def load_json_file(file_path: str, file_description: str) -> Optional[Any]:
    """Loads a JSON file and handles errors."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.critical(f"CRITICAL: {file_description} file not found at {file_path}")
    except json.JSONDecodeError as e:
        logger.critical(f"CRITICAL: Error decoding {file_description} file at {file_path}: {e}")
    except Exception as e:
        logger.critical(f"CRITICAL: An unexpected error occurred while loading {file_description} at {file_path}: {e}")
    return None

def load_settings(path: str = "settings.json") -> bool:
    global SETTINGS
    settings_path = get_external_file_path(path)
    SETTINGS = load_json_file(settings_path, "Settings")
    if SETTINGS is None:
        return False

    # Create essential folders if they don't exist
    for folder_key in ["APPLICATION_FOLDER", "TEMP_PHOTO_FOLDER"]:
        folder_name = SETTINGS.get(folder_key)
        if folder_name:
            try:
                os.makedirs(get_external_file_path(folder_name), exist_ok=True)
            except OSError as e:
                logger.error(f"Could not create directory {folder_name}: {e}")
                # Potentially critical, decide if bot should exit
        else:
            logger.warning(f"Configuration for '{folder_key}' is missing in settings.json.")
    return True


def load_questions() -> bool:
    global QUESTIONS, SETTINGS
    if not SETTINGS:
        logger.error("Settings not loaded. Cannot load questions.")
        return False
    
    questions_file_name = SETTINGS.get("QUESTIONS_FILE")
    if not questions_file_name:
        logger.critical("CRITICAL: 'QUESTIONS_FILE' not specified in settings.json.")
        return False

    questions_path = get_external_file_path(questions_file_name)
    QUESTIONS = load_json_file(questions_path, "Questions")
    return QUESTIONS is not None


def get_text(key: str, lang: Optional[str] = None, **kwargs) -> str:
    global SETTINGS
    if not SETTINGS:
        return f"<SETTINGS_NOT_LOADED_FOR_{key}>"

    if lang is None:
        lang = SETTINGS.get("DEFAULT_LANG", "en")
    
    lang_pack = SETTINGS.get("LANGUAGES", {}).get(lang)
    if not lang_pack: # Fallback to default language if specified lang not found
        lang_pack = SETTINGS.get("LANGUAGES", {}).get(SETTINGS.get("DEFAULT_LANG", "en"), {})
            
    text_template = lang_pack.get(key, f"<{key}_NOT_FOUND_IN_{lang}>")
    
    try:
        return text_template.format(**kwargs)
    except KeyError as e:
        logger.warning(f"Placeholder {e} missing for i18n key '{key}' in lang '{lang}'. Template: '{text_template}'")
        return text_template # Return as is, or a more specific error
    except Exception as e:
        logger.error(f"Error formatting text for key '{key}': {e}")
        return f"<FORMATTING_ERROR_{key}>"

# Initial load
if not load_settings():
    logger.critical("Failed to load settings. Bot may not function correctly.")
    # Consider sys.exit(1) if settings are absolutely crucial for any operation
if not load_questions():
    logger.critical("Failed to load questions. Application feature will be disabled.")