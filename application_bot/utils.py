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
        return os.path.join(sys._MEIPASS, relative_bundle_path)
    else:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_bundle_path)


def get_external_file_path(relative_path_from_app_root: str) -> str:
    """
    Constructs an absolute path to a file/folder (like 'applications' or 'fonts/DejaVuSans.ttf')
    These paths are specified in settings.json as relative to the app root.
    For bundled apps, this resolves to a path within the app's directory (e.g. dist/AppName/applications).
    For development, this resolves from the application_bot directory.
    """
    if relative_path_from_app_root.startswith("fonts/"):
        return get_internal_data_path(relative_path_from_app_root)
    
    return os.path.join(get_app_root_dir(), relative_path_from_app_root)


def load_json_file(file_path: str, file_description: str) -> Optional[Any]:
    """Loads a JSON file and handles errors."""
    logger.debug(f"Attempting to load {file_description} from: {file_path}")
    if not os.path.exists(file_path):
        logger.warning(f"{file_description} file not found at {file_path}.")
        return None
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if not content.strip():
                logger.warning(f"{file_description} file at {file_path} is empty.")
                if file_description.lower().startswith("questions"): return []
                elif file_description.lower().startswith("languages"): return {}
                return None 
            return json.loads(content)
    except FileNotFoundError:
        logger.error(f"{file_description} file not found at {file_path} (FileNotFoundError).")
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding {file_description} file at {file_path}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading {file_description} at {file_path}: {e}")
    return None

def save_json_file(data: Any, file_path: str, file_description: str, indent: int = 4) -> bool:
    """Saves data to a JSON file."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
        logger.info(f"{file_description} successfully saved to {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving {file_description} to {file_path}: {e}")
    return False


def save_settings(settings_data: Dict[str, Any], filename: str = "settings.json") -> bool:
    """Saves the settings dictionary to an EXTERNAL JSON file."""
    settings_path = get_data_file_path(filename) 
    settings_data_to_save = {k: v for k, v in settings_data.items() if k != "LANGUAGES"}
    return save_json_file(settings_data_to_save, settings_path, "Settings")

def load_settings(filename: str = "settings.json") -> bool:
    global SETTINGS 
    
    external_settings_path = get_data_file_path(filename)
    loaded_content = load_json_file(external_settings_path, f"External Settings ({filename})")
    file_existed_and_valid_externally = loaded_content is not None

    if not file_existed_and_valid_externally and getattr(sys, 'frozen', False):
        logger.info(f"External settings not found or invalid at '{external_settings_path}'. "
                    f"Attempting to load bundled default settings.")
        internal_settings_path = get_internal_data_path(filename)
        bundled_content = load_json_file(internal_settings_path, f"Bundled Default Settings ({filename})")
        if bundled_content is not None:
            logger.info(f"Successfully loaded bundled default settings from '{internal_settings_path}'. "
                        f"These will be used and saved to '{external_settings_path}'.")
            SETTINGS = bundled_content
            _ensure_default_settings_keys()
            if not save_settings(SETTINGS, filename): 
                logger.error(f"Failed to bootstrap external settings file at '{external_settings_path}' from bundled defaults.")
            file_existed_and_valid_externally = True 
        else:
            logger.warning(f"Bundled default settings also not found or invalid at '{internal_settings_path}'. "
                           f"Using minimal hardcoded defaults.")
            SETTINGS = {} 
            file_existed_and_valid_externally = False 
    elif file_existed_and_valid_externally:
        SETTINGS = loaded_content
    else: 
        SETTINGS = {} 
        file_existed_and_valid_externally = False

    _ensure_default_settings_keys() 

    for folder_key in ["APPLICATION_FOLDER", "TEMP_PHOTO_FOLDER"]:
        folder_name = SETTINGS.get(folder_key)
        if folder_name:
            try:
                full_folder_path = get_external_file_path(folder_name)
                os.makedirs(full_folder_path, exist_ok=True)
                logger.info(f"Ensured output directory exists: {full_folder_path}")
            except OSError as e:
                logger.error(f"Could not create output directory {full_folder_path}: {e}")
        else:
            logger.warning(f"Configuration for output folder '{folder_key}' is missing in settings.json.")
    
    return file_existed_and_valid_externally


def _ensure_default_settings_keys():
    """Helper to apply default values to the global SETTINGS dictionary."""
    global SETTINGS
    if SETTINGS is None: 
        SETTINGS = {}    
        logger.error("_ensure_default_settings_keys called with SETTINGS as None. Initializing to {}.")

    default_values = {
        "BOT_TOKEN": "", "ADMIN_USER_IDS": "", "DEFAULT_LANG": "en", "THEME": "default-dark",
        "OVERRIDE_USER_LANG": True, "SEND_PDF_TO_ADMINS": True,
        "APPLICATION_PHOTO_NUMB": 1, "PDF_SETTINGS": {},
        "QUESTIONS_FILE": "questions.json", "LANGUAGES_FILE": "languages.json",
        "APPLICATION_FOLDER": "applications", "TEMP_PHOTO_FOLDER": "temp_photos",
        "FONT_FILE_PATH": "fonts/DejaVuSans.ttf",
        "RATE_LIMIT_SECONDS": 600, "CONVERSATION_TIMEOUT_SECONDS": 1200,
        "MAX_ALLOWED_FILE_SIZE_MB": 10, "HTTP_CONNECT_TIMEOUT": 10.0,
        "HTTP_READ_TIMEOUT": 30.0, "HTTP_WRITE_TIMEOUT": 30.0, "HTTP_POOL_TIMEOUT": 15.0,
        "PYWEBVIEW_DEBUG": False
    }
    for key, value in default_values.items():
        SETTINGS.setdefault(key, value)
    
    if "PDF_SETTINGS" not in SETTINGS or not isinstance(SETTINGS["PDF_SETTINGS"], dict):
        SETTINGS["PDF_SETTINGS"] = {} 
        
    default_pdf_settings = {
        "page_width_mm": 210.0, "page_height_mm": 297.0, "margin_mm": 15.0,
        "photo_position": "top_right", "photo_width_mm": 80.0,
        "font_name_registered": "CustomUnicodeFont", "title_font_size": 16,
        "header_font_size": 10, "question_font_size": 12,
        "question_bold": True, "answer_font_size": 10
    }
    for key, value in default_pdf_settings.items():
        SETTINGS["PDF_SETTINGS"].setdefault(key, value)


def load_languages() -> bool:
    global LANGUAGES_CACHE, SETTINGS
    if not SETTINGS:
        logger.warning("load_languages called before settings loaded. Attempting to load settings.")
        if not load_settings(): 
             logger.error("Settings unavailable after attempt, cannot determine languages file. Using minimal languages.")
             LANGUAGES_CACHE = {"en": {"gui_title": "[EN] App Bot (L_FAIL_S_FAIL)"}, "ru": {"gui_title": "[RU] Бот Заявок (L_FAIL_S_FAIL)"}}
             return False
    
    lang_file_name_from_settings = SETTINGS.get("LANGUAGES_FILE", "languages.json")
    languages_path = get_internal_data_path(lang_file_name_from_settings) 
    
    loaded_data = load_json_file(languages_path, "Languages")

    default_min_langs = {
        "en": {"gui_title": "[EN Minimal] App Bot"},
        "ru": {"gui_title": "[RU Minimal] Бот Заявок"}
    }

    if loaded_data is None or not isinstance(loaded_data, dict) or not loaded_data:
        logger.warning(f"Languages file '{languages_path}' not found, error, or invalid. Using minimal default languages.")
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
        logger.error("Settings not loaded. Cannot determine questions file. Questions will be empty.")
        QUESTIONS = []
        return False
    
    questions_file_name = SETTINGS.get("QUESTIONS_FILE", "questions.json")
    
    external_questions_path = get_data_file_path(questions_file_name)
    loaded_data = load_json_file(external_questions_path, f"External Questions ({questions_file_name})")
    file_existed_and_valid_externally = isinstance(loaded_data, list) 

    if not file_existed_and_valid_externally and getattr(sys, 'frozen', False):
        logger.info(f"External questions not found or invalid at '{external_questions_path}'. "
                    f"Attempting to load bundled default questions.")
        internal_questions_path = get_internal_data_path(questions_file_name)
        bundled_data = load_json_file(internal_questions_path, f"Bundled Default Questions ({questions_file_name})")

        if isinstance(bundled_data, list):
            logger.info(f"Successfully loaded bundled default questions from '{internal_questions_path}'. "
                        f"These will be used and saved to '{external_questions_path}'.")
            QUESTIONS = bundled_data
            if not save_questions(QUESTIONS, questions_file_name): 
                 logger.error(f"Failed to bootstrap external questions file at '{external_questions_path}' from bundled defaults.")
            file_existed_and_valid_externally = True 
        else:
            logger.warning(f"Bundled default questions also not found or invalid at '{internal_questions_path}'. "
                           f"Using empty questions list.")
            QUESTIONS = []
            file_existed_and_valid_externally = False
    elif file_existed_and_valid_externally:
        QUESTIONS = loaded_data
    else: 
        logger.warning(f"Questions file '{external_questions_path}' not found, invalid, or not a list. Using empty questions list.")
        QUESTIONS = []
        file_existed_and_valid_externally = False
    
    if file_existed_and_valid_externally:
        logger.info(f"Successfully loaded {len(QUESTIONS)} questions.")
    return file_existed_and_valid_externally


def save_questions(questions_data: List[Dict[str, str]], filename: Optional[str] = None) -> bool:
    global QUESTIONS, SETTINGS 

    if filename is None:
        if SETTINGS and SETTINGS.get("QUESTIONS_FILE"):
            actual_filename = SETTINGS["QUESTIONS_FILE"]
        else:
            logger.warning("QUESTIONS_FILE not found in settings, using default 'questions.json' for saving.")
            actual_filename = "questions.json" 
            if SETTINGS: SETTINGS["QUESTIONS_FILE"] = actual_filename 
    else: actual_filename = filename

    questions_file_path = get_data_file_path(actual_filename)
    
    if save_json_file(questions_data, questions_file_path, "Questions", indent=2):
        QUESTIONS = list(questions_data) 
        return True
    return False


def get_text(key: str, lang: Optional[str] = None, default: Optional[str] = None, **kwargs) -> str:
    global SETTINGS, LANGUAGES_CACHE

    if SETTINGS is None:
        logger.debug("get_text: SETTINGS not loaded. Triggering load.")
        load_settings()
        if SETTINGS is None: 
            logger.error("get_text: SETTINGS still not available after load attempt. Key: %s", key)
            return default if default is not None else f"<S_NF_{key}>"

    if LANGUAGES_CACHE is None:
        logger.debug("get_text: LANGUAGES_CACHE not loaded. Triggering load.")
        load_languages()
        if LANGUAGES_CACHE is None: 
            logger.error("get_text: LANGUAGES_CACHE still not available after load attempt. Key: %s", key)
            return default if default is not None else f"<L_NF_{key}>"
            
    selected_lang = lang
    if selected_lang is None:
        selected_lang = SETTINGS.get("DEFAULT_LANG", "en")

    if selected_lang not in LANGUAGES_CACHE:
        logger.debug(f"get_text: Lang '{selected_lang}' not in LANGUAGES_CACHE. Trying DEFAULT_LANG.")
        selected_lang = SETTINGS.get("DEFAULT_LANG", "en")
        if selected_lang not in LANGUAGES_CACHE:
            logger.debug(f"get_text: DEFAULT_LANG '{selected_lang}' also not in LANGUAGES_CACHE. Trying 'en'.")
            selected_lang = "en" 

    lang_pack = LANGUAGES_CACHE.get(selected_lang)
    
    if not lang_pack:
        logger.error(f"I18N: Language pack for '{selected_lang}' (and fallbacks) not found. Key: '{key}'.")
        return default if default is not None else f"<LP_NF_{key}_{selected_lang}>"

    text_template = lang_pack.get(key)

    if text_template is None:
        default_app_lang = SETTINGS.get("DEFAULT_LANG", "en")
        if selected_lang != default_app_lang:
            logger.debug(f"I18N: Key '{key}' not found in '{selected_lang}'. Trying app default '{default_app_lang}'.")
            lang_pack_default_app = LANGUAGES_CACHE.get(default_app_lang)
            if lang_pack_default_app:
                text_template = lang_pack_default_app.get(key)
        
        if text_template is None and selected_lang != "en" and default_app_lang != "en":
            logger.debug(f"I18N: Key '{key}' not found in app default '{default_app_lang}'. Trying 'en'.")
            lang_pack_en = LANGUAGES_CACHE.get("en")
            if lang_pack_en:
                text_template = lang_pack_en.get(key)

    if text_template is None:
        if default is not None: return default
        logger.warning(f"I18N: Key '{key}' not found for lang '{lang}' or fallbacks ('{selected_lang}', app default, 'en').")
        return f"<{key}_!{lang or selected_lang}>" 
    
    try:
        return text_template.format(**kwargs)
    except KeyError as e:
        logger.warning(f"I18N: Placeholder {e} missing for key '{key}' in lang '{selected_lang}'. Template: '{text_template}'")
        return text_template 
    except Exception as e: 
        logger.error(f"I18N: Formatting error for key '{key}', lang '{selected_lang}': {e}. Template: '{text_template}'")
        return f"<F_ERR_{key}_{selected_lang}>"