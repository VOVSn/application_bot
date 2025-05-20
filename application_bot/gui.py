# application_bot/gui.py
import webview
import logging
import sys
import threading
import asyncio
import queue
from collections import deque
import time
import json
import html # Ensure html is imported
import os
import platform
import subprocess
from typing import List, Dict, Any

from application_bot import utils
from application_bot.main import create_bot_application, run_bot_async, stop_bot_async
from application_bot.utils import (
    load_settings, load_questions, load_languages, # Added load_languages
    get_external_file_path, save_settings as utils_save_settings, get_text, get_data_file_path
)

MAX_LOG_LINES_DEFAULT = 100
logger = logging.getLogger(__name__)

def get_asset_path(relative_path_from_gui_module_dir: str):
    """ Get absolute path to resource (e.g., web_ui), works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path_from_gui_module_dir)

def _get_gui_localization_texts(lang_code: str) -> dict:
    """Fetches GUI-specific text translations using utils.get_text for proper fallbacks."""
    texts = {}
    gui_keys = [
        "gui_title", "gui_status_label_prefix", "gui_status_initializing", "gui_status_running",
        "gui_status_stopped", "gui_status_starting", "gui_status_stopping",
        "gui_status_error_prefix", "gui_status_crashed", "gui_status_settings_not_loaded",
        "gui_status_failed_create_app", "gui_start_button", "gui_stop_button",
        "gui_open_folder_button", "gui_log_lines_label", "gui_dark_theme_label",
        "gui_lang_toggle_label", "gui_status_error_ui_disconnected",
        "gui_edit_questions_button", "gui_modal_questions_title", "gui_modal_add_question_button",
        "gui_modal_save_button", "gui_modal_cancel_button", "gui_modal_delete_button",
        "gui_modal_table_header_text", "gui_modal_table_header_actions",
        "gui_alert_question_text_empty", "gui_alert_duplicate_ids", "gui_alert_questions_saved", # MODIFIED
        "gui_alert_questions_save_failed", "gui_alert_questions_save_error",
        "gui_settings_button", "gui_modal_settings_title",
        "gui_tab_basic_settings", "gui_tab_pdf_settings", "gui_tab_admin_settings",
        "gui_override_user_lang_label",
        "gui_send_pdf_to_admins_label", "gui_app_photo_numb_label",
        "gui_bot_token_label", "gui_admin_ids_label",
        "gui_alert_settings_saved", "gui_alert_settings_save_failed",
        "gui_alert_settings_save_error", "gui_alert_bot_token_empty",
        "gui_alert_invalid_photo_numb",
        "gui_pdf_font_file_path", "gui_pdf_font_name_registered", "gui_pdf_page_width_mm",
        "gui_pdf_page_height_mm", "gui_pdf_margin_mm", "gui_pdf_photo_width_mm",
        "gui_pdf_photo_position", "gui_pdf_photo_pos_top_right", "gui_pdf_photo_pos_center",
        "gui_pdf_title_font_size", "gui_pdf_header_font_size", "gui_pdf_question_font_size",
        "gui_pdf_answer_font_size", "gui_pdf_question_bold",
        "gui_alert_pdf_settings_load_failed",
        "gui_alert_pdf_font_paths_empty"
    ]
    # get_text will handle cases where SETTINGS or LANGUAGES_CACHE are not fully loaded by using fallbacks.
    # This explicit check is a safeguard, but get_text is now more robust.
    if not utils.SETTINGS or not utils.LANGUAGES_CACHE:
         logger.warning("_get_gui_localization_texts: utils.SETTINGS or utils.LANGUAGES_CACHE not yet populated. Using keys as text.")
         return {key: key.replace("gui_", "").replace("_", " ").title() for key in gui_keys}

    for key in gui_keys:
        texts[key] = get_text(key, lang_code, default=f"[{key.upper()}]")
    return texts


class WebviewLogHandler(logging.Handler):
    def __init__(self, log_queue_ref):
        super().__init__()
        self.log_queue = log_queue_ref

    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put(msg)


class PyWebviewApi:
    def __init__(self, gui_instance):
        self._gui = gui_instance

    def start_bot_action(self):
        self._gui.start_bot_action()

    def stop_bot_action(self):
        self._gui.stop_bot_action()

    def set_max_log_lines_from_ui(self, count_str):
        try:
            count = int(count_str)
            if 10 <= count <= 1000:
                self._gui.set_max_log_lines_config(count)
            else:
                logger.warning(f"GUI API: Invalid log lines count from UI: {count}")
                self._gui._gui_eval_js(f"setLogLinesConfig({self._gui.current_max_log_lines})")
        except ValueError:
            logger.warning(f"GUI API: Non-integer log lines count from UI: {count_str}")
            self._gui._gui_eval_js(f"setLogLinesConfig({self._gui.current_max_log_lines})")

    def frontend_is_ready(self):
        self._gui.on_frontend_ready()

    def request_log_repopulation(self):
        self._gui.repopulate_logs_to_frontend()

    def open_applications_folder(self):
        logger.info("GUI API: Received request to open applications folder.")
        if not utils.SETTINGS:
            logger.error("GUI API: Cannot open applications folder, SETTINGS not loaded.")
            if self._gui.window:
                alert_msg = get_text("gui_alert_settings_not_loaded", self._gui.current_language, default="Error: Settings not loaded. Cannot open folder.")
                self._gui._gui_eval_js(f"alert('{html.escape(alert_msg, quote=False)}')")
            return

        app_folder_name = utils.SETTINGS.get("APPLICATION_FOLDER")
        if not app_folder_name:
            logger.error("GUI API: APPLICATION_FOLDER not defined in settings.")
            if self._gui.window:
                alert_msg = get_text("gui_alert_app_folder_not_configured", self._gui.current_language, default="Error: Application folder not configured.")
                self._gui._gui_eval_js(f"alert('{html.escape(alert_msg, quote=False)}')")
            return

        folder_path = get_external_file_path(app_folder_name)

        if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
            logger.warning(f"GUI API: Applications folder '{folder_path}' does not exist. Attempting to create it.")
            try:
                os.makedirs(folder_path, exist_ok=True)
                logger.info(f"GUI API: Created applications folder: {folder_path}")
            except OSError as e:
                logger.error(f"GUI API: Could not create applications folder {folder_path}: {e}")
                if self._gui.window:
                    alert_msg = get_text("gui_alert_cannot_create_folder", self._gui.current_language, default="Error: Could not create or access folder. Check logs.").format(folder=folder_path)
                    self._gui._gui_eval_js(f"alert('{html.escape(alert_msg, quote=False)}')")
                return

        try:
            normalized_folder_path = os.path.normpath(folder_path)
            if platform.system() == "Windows":
                os.startfile(normalized_folder_path)
            elif platform.system() == "Darwin":
                subprocess.run(["open", normalized_folder_path], check=True)
            else:
                subprocess.run(["xdg-open", normalized_folder_path], check=True)
            logger.info(f"GUI API: Successfully requested to open folder: {normalized_folder_path}")
        except Exception as e:
            logger.error(f"GUI API: Error opening folder '{normalized_folder_path}': {e}")
            if self._gui.window:
                alert_msg = get_text("gui_alert_cannot_open_folder", self._gui.current_language, default="Error: Could not open folder. Check logs.").format(folder=normalized_folder_path)
                self._gui._gui_eval_js(f"alert('{html.escape(alert_msg, quote=False)}')")

    def set_system_language(self, lang_code: str):
        if not utils.SETTINGS:
            logger.error("GUI API: SETTINGS not loaded, cannot change language.")
            return {"error": "SETTINGS not loaded", "new_lang": "en", "translations": _get_gui_localization_texts("en")}
        if not utils.LANGUAGES_CACHE:
            logger.error("GUI API: LANGUAGES_CACHE not loaded, cannot change language effectively.")
            return {"error": "LANGUAGES_CACHE not loaded", "new_lang": utils.SETTINGS.get("DEFAULT_LANG", "en"), "translations": _get_gui_localization_texts(utils.SETTINGS.get("DEFAULT_LANG", "en"))}


        original_lang = utils.SETTINGS.get("DEFAULT_LANG", "en")
        if lang_code not in utils.LANGUAGES_CACHE: # Check against loaded languages
            logger.warning(f"GUI API: Language code '{lang_code}' not found in available languages. Reverting to original '{original_lang}'.")
            lang_code = original_lang

        utils.SETTINGS["DEFAULT_LANG"] = lang_code

        if utils_save_settings(utils.SETTINGS):
            logger.info(f"GUI API: System language changed to '{lang_code}' and settings saved.")
            self._gui.current_language = lang_code
        else:
            logger.error(f"GUI API: Failed to save settings after changing language to '{lang_code}'. Reverting in-memory.")
            utils.SETTINGS["DEFAULT_LANG"] = original_lang
            lang_code = original_lang

        new_translations = _get_gui_localization_texts(lang_code)

        if self._gui.window:
            window_title = new_translations.get("gui_title", "Application Bot Control")
            self._gui.window.set_title(window_title)
        
        return {"new_lang": lang_code, "translations": new_translations}

    def get_questions(self):
        logger.info("GUI API: Received request for questions.")
        if utils.QUESTIONS is None:
            logger.info("GUI API: utils.QUESTIONS is None, attempting to load.")
            utils.load_questions()

        if utils.QUESTIONS is not None:
            logger.debug(f"GUI API: Returning questions: {utils.QUESTIONS}")
            return utils.QUESTIONS
        else:
            logger.warning("GUI API: Questions still not loaded after attempt, returning empty list to UI.")
            return []

    def save_questions(self, questions_data: List[dict]):
        logger.info(f"GUI API: Received request to save questions. Count: {len(questions_data) if questions_data else 'None'}")
        if not isinstance(questions_data, list):
            logger.error("GUI API: Invalid data format for saving questions. Expected a list.")
            return False

        for i, q_item in enumerate(questions_data):
            if not isinstance(q_item, dict) or "id" not in q_item or "text" not in q_item:
                logger.error(f"GUI API: Invalid question item format at index {i}: {q_item}. Missing 'id' or 'text'.")
                return False
            # ID is no longer user-editable directly in UI to be empty, but text can be.
            if not q_item["text"]: # Removed check for q_item["id"] being empty
                 logger.error(f"GUI API: Question text is empty at index {i}: {q_item}.")
                 return False

        if utils.save_questions(questions_data):
            logger.info("GUI API: Questions saved and reloaded successfully via utils.save_questions.")
            return True
        else:
            logger.error("GUI API: Failed to save questions via utils.save_questions.")
            return False

    def get_all_settings(self) -> Dict[str, Any]:
        logger.info("GUI API: Received request for all settings.")
        if not utils.SETTINGS:
            logger.critical("GUI API: utils.SETTINGS is unexpectedly None in get_all_settings. This shouldn't happen.")
            # Fallback, though load_settings should prevent this
            return {
                "OVERRIDE_USER_LANG": True, "DEFAULT_LANG": "en", "BOT_TOKEN": "", "ADMIN_USER_IDS": "",
                "APPLICATION_PHOTO_NUMB": 1, "SEND_PDF_TO_ADMINS": True,
                "FONT_FILE_PATH": "fonts/DejaVuSans.ttf",
                "PDF_SETTINGS": {
                    "page_width_mm": 210, "page_height_mm": 297, "margin_mm": 15,
                    "photo_position": "top_right", "photo_width_mm": 80,
                    "font_name_registered": "CustomUnicodeFont", "title_font_size": 16,
                    "header_font_size": 10, "question_font_size": 12,
                    "question_bold": True, "answer_font_size": 10
                }
            }

        pdf_settings_data = utils.SETTINGS.get("PDF_SETTINGS", {}).copy()
        default_pdf_config = {
            "page_width_mm": 210, "page_height_mm": 297, "margin_mm": 15,
            "photo_position": "top_right", "photo_width_mm": 80,
            "font_name_registered": "CustomUnicodeFont", "title_font_size": 16,
            "header_font_size": 10, "question_font_size": 12,
            "question_bold": True, "answer_font_size": 10
        }
        for key, default_value in default_pdf_config.items():
            pdf_settings_data.setdefault(key, default_value)
        
        return {
            "OVERRIDE_USER_LANG": utils.SETTINGS.get("OVERRIDE_USER_LANG", True),
            "DEFAULT_LANG": utils.SETTINGS.get("DEFAULT_LANG", "en"),
            "BOT_TOKEN": utils.SETTINGS.get("BOT_TOKEN", ""),
            "ADMIN_USER_IDS": utils.SETTINGS.get("ADMIN_USER_IDS", ""),
            "APPLICATION_PHOTO_NUMB": utils.SETTINGS.get("APPLICATION_PHOTO_NUMB", 1),
            "SEND_PDF_TO_ADMINS": utils.SETTINGS.get("SEND_PDF_TO_ADMINS", True),
            "FONT_FILE_PATH": utils.SETTINGS.get("FONT_FILE_PATH", "fonts/DejaVuSans.ttf"),
            "PDF_SETTINGS": pdf_settings_data
        }

    def save_all_settings(self, new_settings_data: Dict[str, Any]) -> bool:
        logger.info(f"GUI API: Received request to save all settings: {new_settings_data}")
        if not utils.SETTINGS:
            logger.error("GUI API: Cannot save settings, global utils.SETTINGS not loaded/initialized.")
            return False
        if not isinstance(new_settings_data, dict):
            logger.error(f"GUI API: Invalid structure for settings data: {new_settings_data}")
            return False

        utils.SETTINGS["OVERRIDE_USER_LANG"] = bool(new_settings_data.get("OVERRIDE_USER_LANG", True))
        # DEFAULT_LANG is handled by set_system_language API call

        bot_token = str(new_settings_data.get("BOT_TOKEN", "")).strip()
        if not bot_token:
            logger.error("GUI API: Bot Token cannot be empty.")
            return False # UI will show alert, this confirms failure
        utils.SETTINGS["BOT_TOKEN"] = bot_token
        utils.SETTINGS["ADMIN_USER_IDS"] = str(new_settings_data.get("ADMIN_USER_IDS", "")).strip()

        try:
            photo_numb = int(new_settings_data.get("APPLICATION_PHOTO_NUMB", 1))
            if photo_numb < 0: raise ValueError("Cannot be negative")
            utils.SETTINGS["APPLICATION_PHOTO_NUMB"] = photo_numb
        except (ValueError, TypeError):
            logger.error("GUI API: Invalid value for APPLICATION_PHOTO_NUMB.")
            return False
        utils.SETTINGS["SEND_PDF_TO_ADMINS"] = bool(new_settings_data.get("SEND_PDF_TO_ADMINS", True))

        if "FONT_FILE_PATH" in new_settings_data and \
           "PDF_SETTINGS" in new_settings_data and \
           isinstance(new_settings_data["PDF_SETTINGS"], dict):

            utils.SETTINGS["FONT_FILE_PATH"] = str(new_settings_data["FONT_FILE_PATH"]).strip()
            if not utils.SETTINGS["FONT_FILE_PATH"]:
                logger.error("GUI API: PDF Font File Path cannot be empty.")
                # return False # UI should also validate this, let save proceed if user insists

            if "PDF_SETTINGS" not in utils.SETTINGS:
                utils.SETTINGS["PDF_SETTINGS"] = {}

            pdf_sub_settings_from_ui = new_settings_data["PDF_SETTINGS"]
            current_pdf_settings = utils.SETTINGS["PDF_SETTINGS"]

            try:
                current_pdf_settings["font_name_registered"] = str(pdf_sub_settings_from_ui.get("font_name_registered", "CustomUnicodeFont")).strip()
                if not current_pdf_settings["font_name_registered"]:
                     logger.error("GUI API: PDF Registered Font Name cannot be empty.")
                     # return False # UI validates, let save proceed

                current_pdf_settings["photo_position"] = str(pdf_sub_settings_from_ui.get("photo_position", "top_right"))
                
                numeric_keys_float = ["page_width_mm", "page_height_mm", "margin_mm", "photo_width_mm"]
                for key in numeric_keys_float:
                    current_pdf_settings[key] = float(pdf_sub_settings_from_ui.get(key, current_pdf_settings.get(key, 0.0))) # Default to 0.0 for float

                numeric_keys_int = ["title_font_size", "header_font_size", "question_font_size", "answer_font_size"]
                for key in numeric_keys_int:
                     current_pdf_settings[key] = int(pdf_sub_settings_from_ui.get(key, current_pdf_settings.get(key, 0))) # Default to 0 for int
                
                current_pdf_settings["question_bold"] = bool(pdf_sub_settings_from_ui.get("question_bold", True))

            except (ValueError, TypeError) as e:
                logger.error(f"GUI API: Invalid data type in PDF sub-settings: {e}. Data: {pdf_sub_settings_from_ui}")
                return False
        else:
            logger.warning("GUI API: FONT_FILE_PATH or PDF_SETTINGS structure missing/malformed in save_all_settings data.")

        if utils_save_settings(utils.SETTINGS):
            logger.info("GUI API: All settings saved successfully to settings.json.")
            return True
        else:
            logger.error("GUI API: Failed to save updated settings to settings.json.")
            return False

class BotGUI:
    def __init__(self):
        self.window = None
        self.api = PyWebviewApi(self)
        self.bot_application_instance = None
        self.bot_thread = None
        self.bot_event_loop = None
        self.log_queue = queue.Queue()
        self.current_max_log_lines = MAX_LOG_LINES_DEFAULT
        self.log_deque = deque(maxlen=self.current_max_log_lines)
        self.log_processing_active = False
        self.log_processor_thread = None
        self.current_language = "en" 
        self.initial_status_key = "gui_status_initializing"
        self.is_settings_loaded_successfully = False

    def setup_gui_logging(self):
        gui_log_handler = WebviewLogHandler(self.log_queue)
        formatter = logging.Formatter('%(asctime)s [%(levelname)-7s] %(name)s: %(message)s', datefmt='%H:%M:%S')
        gui_log_handler.setFormatter(formatter)
        root_logger = logging.getLogger()
        
        if not any(isinstance(h, WebviewLogHandler) for h in root_logger.handlers):
            root_logger.addHandler(gui_log_handler)
        
        if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers if h.stream == sys.stderr):
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
            
        root_logger.setLevel(logging.INFO)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("telegram").setLevel(logging.INFO) 
        logging.getLogger("httpcore").setLevel(logging.INFO)
        logger.info("GUI logging initialized.")


    def _process_log_queue_loop(self):
        self.log_processing_active = True
        logger.info("GUI: Log processing thread started.")
        while self.log_processing_active:
            try:
                messages_to_send = []
                batch_size = 0 
                timeout_ms = 50 
                start_time = time.monotonic_ns()

                while not self.log_queue.empty() and batch_size < 50 :
                    if (time.monotonic_ns() - start_time) / 1_000_000 > timeout_ms and batch_size > 0:
                        break
                    try:
                        msg = self.log_queue.get(timeout=0.01)
                        self.log_deque.append(msg)
                        messages_to_send.append(msg)
                        batch_size +=1
                    except queue.Empty:
                        break 
                
                if messages_to_send and self.window:
                    js_safe_messages = [html.escape(m, quote=False) for m in messages_to_send]
                    js_messages_array_str = json.dumps(js_safe_messages)
                    self._gui_eval_js(f'addBatchLogMessages({js_messages_array_str})')

            except Exception as e:
                logging.critical(f"CRITICAL Error in _process_log_queue_loop: {e}", exc_info=True)
            
            time.sleep(0.15 if not messages_to_send else 0.05) 
        logger.info("GUI: Log processing thread stopped.")

    def _gui_eval_js(self, script: str):
        if self.window:
            try:
                self.window.evaluate_js(script)
            except Exception as e:
                logger.debug(f"GUI: Failed to evaluate JS (window might be closing/closed): {e}. Script: {script[:100]}...")


    def update_status(self, message_key_or_text: str, is_error: bool = False, is_running: bool = None, is_raw_text: bool = False):
        if self.window:
            js_message = json.dumps(message_key_or_text)
            js_is_error = str(is_error).lower()
            js_is_running = 'null' if is_running is None else str(is_running).lower()
            js_is_raw_text = str(is_raw_text).lower()
            self._gui_eval_js(f'updateStatus({js_message}, {js_is_error}, {js_is_running}, {js_is_raw_text})')

    def _run_bot_in_thread(self):
        self.bot_event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.bot_event_loop)
        try:
            self.bot_application_instance = create_bot_application()
            if self.bot_application_instance:
                logger.info("GUI: Bot application instance created successfully.")
                self.update_status("gui_status_running", is_running=True)
                self.bot_event_loop.run_until_complete(run_bot_async(self.bot_application_instance))
            else:
                logger.error("GUI: Failed to create bot application instance (likely BOT_TOKEN missing or invalid).")
                self.update_status("gui_status_failed_create_app", True, False)
        except Exception as e:
            logger.error(f"GUI: Unhandled exception in bot thread: {e}", exc_info=True)
            self.update_status("gui_status_crashed", True, False)
        finally:
            logger.info("GUI: Bot thread processing finished.")
            if self.bot_event_loop and self.bot_event_loop.is_running():
                try: self.bot_event_loop.stop()
                except Exception as e_loop_stop: logger.error(f"GUI: Error stopping bot event loop: {e_loop_stop}")
            if self.bot_event_loop and not self.bot_event_loop.is_closed():
                self.bot_event_loop.close()
            self._reset_ui_to_stopped_state()


    def start_bot_action(self):
        if not self.is_settings_loaded_successfully:
            self.update_status("gui_status_settings_not_loaded", True, False)
            logger.error("GUI: Attempted to start bot, but settings.json was not loaded successfully.")
            return
        if not utils.SETTINGS or not utils.SETTINGS.get("BOT_TOKEN"):
             self.update_status(get_text("gui_alert_bot_token_empty", self.current_language), True, False, is_raw_text=True)
             logger.error("GUI: Attempted to start bot, but BOT_TOKEN is missing in settings.")
             return
        if utils.QUESTIONS is None: 
            if not load_questions():
                logger.warning("GUI: questions.json could not be loaded. /apply command may fail or use empty questions.")
        
        if self.bot_thread and self.bot_thread.is_alive():
            logger.info("GUI: Bot is already running or starting.")
            return

        self._gui_eval_js('setButtonState("start-button", false)')
        self._gui_eval_js('setButtonState("stop-button", true)')
        self.update_status("gui_status_starting", is_running=None)
        logger.info("GUI: Initiating bot start sequence...")

        self.bot_thread = threading.Thread(target=self._run_bot_in_thread, daemon=True)
        self.bot_thread.start()

    def _reset_ui_to_stopped_state(self):
        self._gui_eval_js('setButtonState("start-button", true)')
        self._gui_eval_js('setButtonState("stop-button", false)')
        
        status_key = "gui_status_stopped"
        is_error = False
        is_raw = False
        if not self.is_settings_loaded_successfully:
            status_key = "gui_status_settings_not_loaded"
            is_error = True
        elif not utils.SETTINGS or not utils.SETTINGS.get("BOT_TOKEN"):
            status_key = get_text("gui_alert_bot_token_empty", self.current_language, default="Bot token is missing.")
            is_error = True
            is_raw = True # Since get_text returns the actual string
        
        self.update_status(status_key, is_error=is_error, is_running=False, is_raw_text=is_raw)
            
        self.bot_application_instance = None


    def stop_bot_action(self):
        if not self.bot_thread or not self.bot_thread.is_alive():
            logger.info("GUI: Bot is not currently running or already stopping.")
            self._reset_ui_to_stopped_state()
            return

        if not self.bot_application_instance or not self.bot_event_loop:
            logger.warning("GUI: Stop called, but bot instance or event loop is missing. Forcing UI reset.")
            self._reset_ui_to_stopped_state()
            return

        self.update_status("gui_status_stopping", is_running=None)
        logger.info("GUI: Initiating bot stop sequence...")

        if self.bot_event_loop.is_running():
            future = asyncio.run_coroutine_threadsafe(stop_bot_async(self.bot_application_instance), self.bot_event_loop)
            try:
                future.result(timeout=15)
                logger.info("GUI: Stop command sent and processed by bot thread.")
            except asyncio.TimeoutError:
                logger.warning("GUI: Timeout waiting for bot stop confirmation. Bot thread might take longer or be stuck.")
            except Exception as e:
                logger.error(f"GUI: Error during run_coroutine_threadsafe for stop: {e}")
        else:
            logger.warning("GUI: Bot event loop not running. Cannot send stop command gracefully.")
        

    def on_frontend_ready(self):
        logger.info("GUI: Frontend reported ready. Initializing GUI state.")
        
        gui_translations = _get_gui_localization_texts(self.current_language)
        if self.window:
            window_title = gui_translations.get("gui_title", "Application Bot Control")
            self.window.set_title(window_title)

        initial_config = {
            "currentLang": self.current_language,
            "guiTranslations": gui_translations,
            "maxLogLines": self.current_max_log_lines,
            "initialLogs": [html.escape(log_item, quote=False) for log_item in list(self.log_deque)]
        }
        self._gui_eval_js(f"initializeGui({json.dumps(initial_config)})")
        
        self._reset_ui_to_stopped_state()


    def set_max_log_lines_config(self, count: int):
        logger.info(f"GUI: Setting max log lines to {count}")
        self.current_max_log_lines = count
        
        current_logs = list(self.log_deque)
        self.log_deque = deque(maxlen=self.current_max_log_lines)
        for log_item in current_logs[-self.current_max_log_lines:]:
            self.log_deque.append(log_item)
        
        js_safe_current_logs = [html.escape(m, quote=False) for m in list(self.log_deque)]
        self._gui_eval_js(f"setLogLinesConfig({self.current_max_log_lines}, {json.dumps(js_safe_current_logs)})")

    def repopulate_logs_to_frontend(self):
        if self.log_deque:
            js_safe_logs = [html.escape(m, quote=False) for m in list(self.log_deque)]
            self._gui_eval_js(f"clearLogs(); addBatchLogMessages({json.dumps(js_safe_logs)})")


    def run(self):
        self.setup_gui_logging() 

        self.log_processor_thread = threading.Thread(target=self._process_log_queue_loop, daemon=True)
        self.log_processor_thread.start()

        html_file_rel_path = "web_ui/gui.html"
        html_file_abs_path = get_asset_path(html_file_rel_path)
        
        initial_title = get_text("gui_title", self.current_language, default="Application Bot Control")

        logger.info(f"GUI: Creating pywebview window. Title: '{initial_title}'. HTML: '{html_file_abs_path}'")
        self.window = webview.create_window(
            initial_title,
            html_file_abs_path,
            js_api=self.api,
            width=850,
            height=700,
            resizable=True,
            min_size=(800, 650) 
        )
        self.window.events.closed += self._trigger_cleanup_on_window_closed
        
        debug_mode = utils.SETTINGS.get("PYWEBVIEW_DEBUG", False) if utils.SETTINGS else False
        logger.info(f"GUI: Starting pywebview main loop. Debug: {debug_mode}, Private Mode: True")
        
        # MODIFIED: Set private_mode to True to help prevent caching issues
        webview.start(debug=debug_mode, private_mode=True) 
        
        logger.info("GUI: Pywebview main loop has exited. Application should be shutting down.")


    def _trigger_cleanup_on_window_closed(self):
        logger.info("GUI: Window 'closed' event received. Initiating cleanup.")
        self.perform_app_cleanup()

    def perform_app_cleanup(self):
        logger.info("GUI: Starting application cleanup sequence.")
        
        self.log_processing_active = False

        if self.bot_thread and self.bot_thread.is_alive():
            logger.info("GUI: Bot is running, attempting to stop it during cleanup.")
            if self.bot_application_instance and self.bot_event_loop and self.bot_event_loop.is_running():
                future = asyncio.run_coroutine_threadsafe(stop_bot_async(self.bot_application_instance), self.bot_event_loop)
                try:
                    future.result(timeout=7)
                    logger.info("GUI: Bot stop command processed during cleanup.")
                except Exception as e:
                    logger.warning(f"GUI: Error or timeout stopping bot during cleanup: {e}")
            
            self.bot_thread.join(timeout=7)
            if self.bot_thread.is_alive():
                logger.warning("GUI: Bot thread did not terminate gracefully after stop and join.")
            else:
                logger.info("GUI: Bot thread terminated.")
        else:
            logger.info("GUI: Bot thread was not running or already finished at cleanup.")

        if self.log_processor_thread and self.log_processor_thread.is_alive():
            self.log_processor_thread.join(timeout=3)
            if self.log_processor_thread.is_alive():
                logger.warning("GUI: Log processor thread did not terminate.")
            else:
                logger.info("GUI: Log processor thread terminated.")
        else:
            logger.info("GUI: Log processor thread was not running or already finished at cleanup.")
            
        logger.info("GUI: Application cleanup finished.")


def main_gui_start():
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO, 
            format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s", 
            datefmt='%H:%M:%S',
            stream=sys.stderr
        )
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("telegram").setLevel(logging.INFO) 
        logging.getLogger("httpcore").setLevel(logging.INFO)
        logging.getLogger("pywebview").setLevel(logging.INFO)

    logger.info("ApplicationBotGUI starting...")

    settings_file_ok = utils.load_settings()
    languages_ok = utils.load_languages()
    questions_ok = utils.load_questions()

    app_gui = BotGUI()
    app_gui.is_settings_loaded_successfully = settings_file_ok 
    
    app_gui.current_language = utils.SETTINGS.get("DEFAULT_LANG", "en") if utils.SETTINGS else "en"
    
    if settings_file_ok:
        logger.info(f"GUI: Settings loaded. Initial language from settings: {app_gui.current_language}")
    else:
        logger.critical("GUI CRITICAL: settings.json was not found or was invalid. GUI is using default values. Functionality may be limited.")

    if not languages_ok:
        logger.warning("GUI WARNING: Failed to load languages.json. GUI text might be missing or fallback to keys/defaults.")

    if not questions_ok:
        logger.warning("GUI WARNING: Failed to load questions.json initially. /apply command might be affected.")

    try:
        app_gui.run()
    except Exception as e:
        logger.critical(f"GUI CRITICAL: Unhandled exception in app_gui.run(): {e}", exc_info=True)
        app_gui.perform_app_cleanup() 
    finally:
        logger.info("ApplicationBotGUI main_gui_start function finished.")


if __name__ == "__main__":
    main_gui_start()