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
        # sys.executable is C:\Path\To\dist\ApplicationBotGUI\ApplicationBotGUI.exe
        # os.path.dirname(sys.executable) is C:\Path\To\dist\ApplicationBotGUI\
        # This is correct for bundled app where settings.json is at the root.
        return os.path.dirname(sys.executable)
    else:
        # In development:
        # __file__ is, for example, C:\Dev\APPLICATION_BOT\Application_bot\application_bot\utils.py
        # os.path.dirname(__file__) is C:\Dev\APPLICATION_BOT\Application_bot\application_bot\
        # This is where settings.json, questions.json are located.
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

    # Create essential folders if they don't exist. These paths are relative to app root.
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
        return False
    
    questions_file_name = SETTINGS.get("QUESTIONS_FILE")
    if not questions_file_name:
        logger.critical("CRITICAL: 'QUESTIONS_FILE' not specified in settings.json.")
        return False

    questions_path = get_data_file_path(questions_file_name)
    QUESTIONS = load_json_file(questions_path, "Questions")
    return QUESTIONS is not None

def get_text(key: str, lang: Optional[str] = None, default: Optional[str] = None, **kwargs) -> str:
    global SETTINGS
    if not SETTINGS:
        return default if default is not None else f"<SETTINGS_NOT_LOADED_FOR_{key}>"

    selected_lang = lang
    if selected_lang is None:
        selected_lang = SETTINGS.get("DEFAULT_LANG", "en")
    
    lang_pack = SETTINGS.get("LANGUAGES", {}).get(selected_lang)
    
    # Fallback to default app language if specified lang or key not found
    if not lang_pack or key not in lang_pack:
        default_app_lang = SETTINGS.get("DEFAULT_LANG", "en")
        if selected_lang != default_app_lang:
            logger.debug(f"Key '{key}' not in lang '{selected_lang}', trying default app lang '{default_app_lang}'.")
            lang_pack = SETTINGS.get("LANGUAGES", {}).get(default_app_lang, {})
        
        # If still not found in default, or default is the same and key missing, try English
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

# Initial load logic (remains the same, called at the end of the file)
# if not load_settings():
#     logger.critical("Failed to load settings. Bot may not function correctly.")
# if not load_questions():
#     logger.warning("Failed to load questions. Application feature will be affected.")
# This initial load is problematic if utils.py is imported by multiple modules before
# main_gui_start() has a chance to call them. It's better to have main_gui_start()
# explicitly call load_settings() and load_questions() and handle failures there.
# The globals SETTINGS and QUESTIONS will be populated by these calls.
# For now, I'll leave the initial load calls commented out here, assuming main_gui_start() handles it.