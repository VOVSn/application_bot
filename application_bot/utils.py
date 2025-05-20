# application_bot/utils.py
import os
import sys
import json
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Global cache for settings, questions, and languages
SETTINGS: Optional[Dict[str, Any]] = None
QUESTIONS: Optional[List[Dict[str, str]]] = None
LANGUAGES_CACHE: Optional[Dict[str, Dict[str, str]]] = None

def get_app_root_dir() -> str:
    """
    Get the root directory for EXTERNAL data files (settings.json, questions.json)
    that are meant to be alongside the executable in a PyInstaller bundle.
    For development, this is the 'application_bot' subfolder.
    """
    if getattr(sys, 'frozen', False):  # PyInstaller bundle
        return os.path.dirname(sys.executable) # Directory containing the executable
    else:
        # Development: 'application_bot' directory where this utils.py is
        return os.path.dirname(os.path.abspath(__file__))

def get_data_file_path(filename_at_root: str) -> str:
    """
    Constructs an absolute path to an EXTERNAL data file (e.g. settings.json)
    assumed to be at the application root (next to executable or in app_bot/ for dev).
    """
    return os.path.join(get_app_root_dir(), filename_at_root)

def get_internal_data_path(relative_bundle_path: str) -> str:
    """
    Get the path to a data file that is bundled and accessed via sys._MEIPASS.
    'relative_bundle_path' is the path as specified in the 'datas' tuple's destination
    (e.g., 'languages.json' if its destination is '.', or 'subdir/file.ext' if destination is 'subdir').
    """
    if getattr(sys, 'frozen', False):  # PyInstaller bundle
        # sys._MEIPASS is the root of the extracted data files (e.g., dist/AppName for one-folder)
        return os.path.join(sys._MEIPASS, relative_bundle_path)
    else:
        # Development: file is relative to this utils.py module (application_bot folder)
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_bundle_path)


def get_external_file_path(relative_path_from_app_root: str) -> str:
    """
    Constructs an absolute path to a file/folder (like 'applications' or 'fonts/DejaVuSans.ttf')
    These paths are specified in settings.json as relative to the app root.
    For bundled apps, this resolves to a path within the app's directory (e.g. dist/AppName/applications).
    For development, this resolves from the application_bot directory.
    """
    # This function is similar to get_data_file_path but used for directories/files defined *inside* settings.json
    # If these are truly internal resources like fonts, they should be accessed via get_internal_data_path('fonts/font.ttf')
    # If they are output directories like 'applications', then get_app_root_dir() is correct.
    # The current usage (e.g. FONT_FILE_PATH) is for a file that is part of the bundle's internal structure.
    # Let's clarify for FONT_FILE_PATH:
    if relative_path_from_app_root.startswith("fonts/"): # Assuming fonts are always internal
        return get_internal_data_path(relative_path_from_app_root)
    
    # For output folders like 'applications' or 'temp_photos'
    return os.path.join(get_app_root_dir(), relative_path_from_app_root)


def load_json_file(file_path: str, file_description: str) -> Optional[Any]:
    """Loads a JSON file and handles errors."""
    if not os.path.exists(file_path):
        logger.warning(f"{file_description} file not found at {file_path}. This might be normal if it's the first run.")
        return None
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if not content.strip():
                logger.warning(f"{file_description} file at {file_path} is empty.")
                if file_description.lower() == "questions": return []
                elif file_description.lower() == "languages": return {}
                return None
            return json.loads(content)
    except FileNotFoundError:
        logger.critical(f"CRITICAL: {file_description} file not found at {file_path}")
    except json.JSONDecodeError as e:
        logger.critical(f"CRITICAL: Error decoding {file_description} file at {file_path}: {e}")
    except Exception as e:
        logger.critical(f"CRITICAL: An unexpected error occurred while loading {file_description} at {file_path}: {e}")
    return None

def save_settings(settings_data: Dict[str, Any], path: str = "settings.json") -> bool:
    """Saves the settings dictionary to an EXTERNAL JSON file."""
    settings_path = get_data_file_path(path) # External path
    try:
        settings_data_to_save = {k: v for k, v in settings_data.items() if k != "LANGUAGES"}
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(settings_data_to_save, f, ensure_ascii=False, indent=4)
        logger.info(f"Settings successfully saved to {settings_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving settings to {settings_path}: {e}")
    return False

def load_settings(path: str = "settings.json") -> bool:
    global SETTINGS
    settings_path = get_data_file_path(path) # External path
    loaded_content = load_json_file(settings_path, "Settings")

    if loaded_content is None:
        SETTINGS = {
            "BOT_TOKEN": "", "ADMIN_USER_IDS": "", "DEFAULT_LANG": "en",
            "OVERRIDE_USER_LANG": True, "SEND_PDF_TO_ADMINS": True,
            "APPLICATION_PHOTO_NUMB": 1, "PDF_SETTINGS": {},
            "QUESTIONS_FILE": "questions.json", "LANGUAGES_FILE": "languages.json",
            "APPLICATION_FOLDER": "applications", "TEMP_PHOTO_FOLDER": "temp_photos",
            "FONT_FILE_PATH": "fonts/DejaVuSans.ttf" # This path will be resolved by get_external_file_path
        }
        logger.warning(f"Settings file {settings_path} not found or invalid. Loaded minimal default settings.")
        file_existed_and_valid = False
    else:
        SETTINGS = loaded_content
        file_existed_and_valid = True

    # Ensure defaults for crucial keys
    SETTINGS.setdefault("OVERRIDE_USER_LANG", True)
    SETTINGS.setdefault("SEND_PDF_TO_ADMINS", True)
    SETTINGS.setdefault("APPLICATION_PHOTO_NUMB", 1)
    SETTINGS.setdefault("DEFAULT_LANG", "en")
    SETTINGS.setdefault("PDF_SETTINGS", {})
    SETTINGS.setdefault("QUESTIONS_FILE", "questions.json")
    SETTINGS.setdefault("LANGUAGES_FILE", "languages.json")
    SETTINGS.setdefault("APPLICATION_FOLDER", "applications")
    SETTINGS.setdefault("TEMP_PHOTO_FOLDER", "temp_photos")
    SETTINGS.setdefault("FONT_FILE_PATH", "fonts/DejaVuSans.ttf")


    # Ensure output directories exist
    for folder_key in ["APPLICATION_FOLDER", "TEMP_PHOTO_FOLDER"]:
        folder_name = SETTINGS.get(folder_key)
        if folder_name:
            try:
                # These are external output folders, so use get_external_file_path which resolves to app root
                full_folder_path = get_external_file_path(folder_name)
                os.makedirs(full_folder_path, exist_ok=True)
                logger.info(f"Ensured output directory exists: {full_folder_path}")
            except OSError as e:
                logger.error(f"Could not create output directory {full_folder_path}: {e}")
        else:
            logger.warning(f"Configuration for output folder '{folder_key}' is missing in settings.json.")
    
    return file_existed_and_valid


def load_languages() -> bool:
    global LANGUAGES_CACHE, SETTINGS
    if not SETTINGS:
        logger.warning("load_languages called before settings loaded. Attempting to load settings.")
        load_settings()
        if not SETTINGS:
             logger.error("Settings unavailable, cannot determine languages file. Using minimal languages.")
             LANGUAGES_CACHE = {"en": {"gui_title": "[EN] App Bot (L_FAIL)"}, "ru": {"gui_title": "[RU] Бот Заявок (L_FAIL)"}}
             return False

    lang_file_name_from_settings = SETTINGS.get("LANGUAGES_FILE", "languages.json")
    
    # Use get_internal_data_path for languages.json as it's a bundled resource
    languages_path = get_internal_data_path(lang_file_name_from_settings)
    
    logger.info(f"Attempting to load languages from internal path: {languages_path}")
    loaded_data = load_json_file(languages_path, "Languages")

    default_min_langs = {
        "en": {"gui_title": "[EN Minimal] App Bot"},
        "ru": {"gui_title": "[RU Minimal] Бот Заявок"}
    }

    if loaded_data is None:
        logger.warning(f"Languages file '{languages_path}' not found or error. Using minimal default languages.")
        LANGUAGES_CACHE = default_min_langs
        return False
    elif not isinstance(loaded_data, dict) or not loaded_data:
        logger.error(f"Languages file '{languages_path}' is not a valid non-empty dictionary. Using minimal languages.")
        LANGUAGES_CACHE = default_min_langs
        return False
    
    valid_langs_loaded = {}
    for lang_code, translations in loaded_data.items():
        if isinstance(translations, dict):
            valid_langs_loaded[lang_code] = translations
        else:
            logger.warning(f"Language pack for '{lang_code}' in '{languages_path}' is not a dictionary. Skipping.")
    
    if not valid_langs_loaded:
        logger.error(f"No valid language packs found in '{languages_path}'. Using minimal default languages.")
        LANGUAGES_CACHE = default_min_langs
        return False

    LANGUAGES_CACHE = valid_langs_loaded
    logger.info(f"Successfully loaded {len(LANGUAGES_CACHE)} language packs from {languages_path}.")
    return True


def load_questions() -> bool:
    global QUESTIONS, SETTINGS
    if not SETTINGS:
        logger.error("Settings not loaded. Cannot load questions.")
        QUESTIONS = []
        return False
    
    questions_file_name = SETTINGS.get("QUESTIONS_FILE")
    if not questions_file_name:
        logger.critical("CRITICAL: 'QUESTIONS_FILE' not specified in settings.json.")
        QUESTIONS = []
        return False

    questions_path = get_data_file_path(questions_file_name) # External path
    loaded_data = load_json_file(questions_path, "Questions")

    if loaded_data is None:
        logger.warning(f"Questions file '{questions_path}' not found or error loading. Defaulting to empty questions list.")
        QUESTIONS = []
        return False
    elif not isinstance(loaded_data, list):
        logger.error(f"Questions file '{questions_path}' does not contain a list. Defaulting to empty questions list.")
        QUESTIONS = []
        return False
    
    QUESTIONS = loaded_data
    logger.info(f"Successfully loaded {len(QUESTIONS)} questions from {questions_path}.")
    return True

def save_questions(questions_data: List[Dict[str, str]], path: Optional[str] = None) -> bool:
    global QUESTIONS, SETTINGS

    if path is None:
        if SETTINGS and SETTINGS.get("QUESTIONS_FILE"):
            file_name = SETTINGS["QUESTIONS_FILE"]
        else:
            logger.warning("QUESTIONS_FILE not found in settings, using default 'questions.json' for saving.")
            file_name = "questions.json" 
            if SETTINGS: SETTINGS["QUESTIONS_FILE"] = file_name
    else: file_name = path

    questions_file_path = get_data_file_path(file_name) # External path
    
    try:
        with open(questions_file_path, 'w', encoding='utf-8') as f:
            json.dump(questions_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Questions successfully saved to {questions_file_path}")
        QUESTIONS = list(questions_data)
        return True
    except Exception as e:
        logger.error(f"Error saving questions to {questions_file_path}: {e}")
    return False

def get_text(key: str, lang: Optional[str] = None, default: Optional[str] = None, **kwargs) -> str:
    global SETTINGS, LANGUAGES_CACHE

    current_settings = SETTINGS
    current_languages_cache = LANGUAGES_CACHE

    if not current_settings:
        # This is a fallback for very early calls, normally load_settings should run first
        logger.debug("get_text: SETTINGS not yet loaded, attempting one-time load for this call.")
        load_settings() # Populates global SETTINGS
        current_settings = SETTINGS # Re-fetch
        if not current_settings:
            logger.error(f"get_text: SETTINGS still not available after load attempt. Key: {key}")
            return default if default is not None else f"<S_NF_{key}>"

    if not current_languages_cache:
        # Fallback for early calls
        logger.debug("get_text: LANGUAGES_CACHE not yet loaded, attempting one-time load for this call.")
        load_languages() # Populates global LANGUAGES_CACHE
        current_languages_cache = LANGUAGES_CACHE # Re-fetch
        if not current_languages_cache:
            logger.error(f"get_text: LANGUAGES_CACHE still not available after load attempt. Key: {key}")
            return default if default is not None else f"<L_NF_{key}>"
            
    selected_lang = lang
    if selected_lang is None:
        selected_lang = current_settings.get("DEFAULT_LANG", "en")

    lang_pack = current_languages_cache.get(selected_lang)
    
    if not lang_pack or key not in lang_pack:
        default_app_lang = current_settings.get("DEFAULT_LANG", "en")
        if selected_lang != default_app_lang: # Try default app lang if different
            lang_pack = current_languages_cache.get(default_app_lang)
        
        if not lang_pack or key not in lang_pack: # If still not found, try 'en' as ultimate fallback
            if default_app_lang != "en": 
                lang_pack = current_languages_cache.get("en")

    text_template = lang_pack.get(key) if lang_pack else None

    if text_template is None:
        if default is not None: return default
        logger.warning(f"I18N: Key '{key}' not found for lang '{selected_lang}' or fallbacks.")
        return f"<{key}_!{selected_lang}>"
    
    try:
        return text_template.format(**kwargs)
    except KeyError as e:
        logger.warning(f"I18N: Placeholder {e} missing for key '{key}' in lang '{selected_lang}'. Tpl: '{text_template}'")
        return text_template 
    except Exception as e:
        logger.error(f"I18N: Formatting error for key '{key}', lang '{selected_lang}': {e}")
        return f"<F_ERR_{key}_{selected_lang}>"