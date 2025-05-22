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
import copy # Added this import
import socket # Added for network check

# Import the specific error types we want to handle gracefully
from telegram.error import NetworkError as PTBNetworkError # Renamed to avoid clash
from httpx import ConnectError, ReadTimeout, RemoteProtocolError, WriteTimeout, PoolTimeout

from application_bot import utils
from application_bot.main import create_bot_application, run_bot_async, stop_bot_async
from application_bot.utils import (
    load_settings, load_questions, load_languages,
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
        "gui_alert_question_text_empty", "gui_alert_duplicate_ids",
        "gui_alert_questions_saved_title", "gui_alert_questions_saved",
        "gui_alert_questions_save_failed", "gui_alert_questions_save_error",
        "gui_settings_button", "gui_modal_settings_title",
        "gui_tab_basic_settings", "gui_tab_pdf_settings", "gui_tab_admin_settings",
        "gui_override_user_lang_label",
        "gui_send_pdf_to_admins_label", "gui_app_photo_numb_label",
        "gui_bot_token_label", "gui_admin_ids_label",
        "gui_alert_settings_saved_title", "gui_alert_settings_saved",
        "gui_alert_settings_save_failed",
        "gui_alert_settings_save_error", "gui_alert_bot_token_empty",
        "gui_alert_invalid_photo_numb",
        "gui_pdf_font_file_path", "gui_pdf_font_name_registered", "gui_pdf_page_width_mm",
        "gui_pdf_page_height_mm", "gui_pdf_margin_mm", "gui_pdf_photo_width_mm",
        "gui_pdf_photo_position", "gui_pdf_photo_pos_top_right", "gui_pdf_photo_pos_center",
        "gui_pdf_title_font_size", "gui_pdf_header_font_size", "gui_pdf_question_font_size",
        "gui_pdf_answer_font_size", "gui_pdf_question_bold",
        "gui_alert_pdf_settings_load_failed",
        "gui_alert_pdf_font_paths_empty",
        "gui_theme_label", "gui_theme_default_dark", "gui_theme_default_light",
        "gui_theme_memphis", "gui_theme_aurora_dreams", "gui_theme_navy_formal",
        "gui_help_button_title", "gui_about_button_title", "gui_settings_button_title",
        "gui_help_modal_title", "gui_help_modal_content",
        "gui_about_modal_title", "gui_about_modal_content",
        "gui_modal_info_ok_button",
        "gui_logo_label", "gui_logo_default", "gui_logo_abc", "gui_logo_zaya",
        # Network status keys
        "gui_status_connection_lost", "gui_status_connection_restored",
        "gui_status_bot_paused_no_connection", "gui_status_bot_cannot_start_no_connection",
        "gui_status_connection_lost_bot_stopped", "gui_status_attempting_restart_after_connection"
    ]
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
        self.target_network_error_loggers = (
            'telegram.ext.Updater',
            'telegram.bot', 
            'telegram.ext.ExtBot',
        )
        self.network_exception_types = (
            PTBNetworkError, 
            ConnectError,    
            ReadTimeout,
            RemoteProtocolError,
            WriteTimeout,
            PoolTimeout,
            socket.gaierror, 
            socket.timeout,  
        )

    def emit(self, record: logging.LogRecord):
        if record.name in self.target_network_error_loggers and \
           record.levelno >= logging.ERROR and \
           record.exc_info:
            
            _etype, evalue, _tb = record.exc_info 
            
            if isinstance(evalue, self.network_exception_types):
                date_fmt = self.formatter.datefmt if self.formatter else '%H:%M:%S'
                timestamp = time.strftime(date_fmt, time.localtime(record.created))
                
                exc_class_name = evalue.__class__.__name__
                exc_message_first_line = str(evalue).splitlines()[0] if str(evalue) else ""
                
                concise_msg = (
                    f"{timestamp} [{record.levelname:<7s}] {record.name}: "
                    f"Network issue: {exc_class_name}"
                )
                if exc_message_first_line:
                    concise_msg += f" - {exc_message_first_line}"
                
                self.log_queue.put(concise_msg)
                return 

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
        if lang_code not in utils.LANGUAGES_CACHE:
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
            if not q_item["text"]:
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
            return {
                "OVERRIDE_USER_LANG": True, "DEFAULT_LANG": "en", "THEME": "default-dark",
                "SELECTED_LOGO": "default", 
                "BOT_TOKEN": "", "ADMIN_USER_IDS": "",
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
            "THEME": utils.SETTINGS.get("THEME", "default-dark"),
            "SELECTED_LOGO": utils.SETTINGS.get("SELECTED_LOGO", "default"), 
            "BOT_TOKEN": utils.SETTINGS.get("BOT_TOKEN", ""),
            "ADMIN_USER_IDS": utils.SETTINGS.get("ADMIN_USER_IDS", ""),
            "APPLICATION_PHOTO_NUMB": utils.SETTINGS.get("APPLICATION_PHOTO_NUMB", 1),
            "SEND_PDF_TO_ADMINS": utils.SETTINGS.get("SEND_PDF_TO_ADMINS", True),
            "FONT_FILE_PATH": utils.SETTINGS.get("FONT_FILE_PATH", "fonts/DejaVuSans.ttf"),
            "PDF_SETTINGS": pdf_settings_data
        }

    def save_all_settings(self, new_settings_data: Dict[str, Any]) -> bool:
        loggable_settings_data = copy.deepcopy(new_settings_data)
        if "BOT_TOKEN" in loggable_settings_data:
            loggable_settings_data["BOT_TOKEN"] = "[REDACTED]"
        
        logger.info(f"GUI API: Received request to save all settings: {loggable_settings_data}") 

        if not utils.SETTINGS:
            logger.error("GUI API: Cannot save settings, global utils.SETTINGS not loaded/initialized.")
            return False
        if not isinstance(new_settings_data, dict):
            logger.error(f"GUI API: Invalid structure for settings data: {new_settings_data}") 
            return False

        utils.SETTINGS["OVERRIDE_USER_LANG"] = bool(new_settings_data.get("OVERRIDE_USER_LANG", True))
        utils.SETTINGS["THEME"] = str(new_settings_data.get("THEME", "default-dark"))
        utils.SETTINGS["SELECTED_LOGO"] = str(new_settings_data.get("SELECTED_LOGO", "default")) 
        
        bot_token = str(new_settings_data.get("BOT_TOKEN", "")).strip()
        if not bot_token:
            logger.error("GUI API: Bot Token cannot be empty.")
            return False 
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
            
            if "PDF_SETTINGS" not in utils.SETTINGS:
                utils.SETTINGS["PDF_SETTINGS"] = {}

            pdf_sub_settings_from_ui = new_settings_data["PDF_SETTINGS"]
            current_pdf_settings = utils.SETTINGS["PDF_SETTINGS"]

            try:
                current_pdf_settings["font_name_registered"] = str(pdf_sub_settings_from_ui.get("font_name_registered", "CustomUnicodeFont")).strip()
                current_pdf_settings["photo_position"] = str(pdf_sub_settings_from_ui.get("photo_position", "top_right"))
                
                numeric_keys_float = ["page_width_mm", "page_height_mm", "margin_mm", "photo_width_mm"]
                for key in numeric_keys_float:
                    current_pdf_settings[key] = float(pdf_sub_settings_from_ui.get(key, current_pdf_settings.get(key, 0.0)))

                numeric_keys_int = ["title_font_size", "header_font_size", "question_font_size", "answer_font_size"]
                for key in numeric_keys_int:
                     current_pdf_settings[key] = int(pdf_sub_settings_from_ui.get(key, current_pdf_settings.get(key, 0)))
                
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
        
        self.gui_active = True 
        self.log_processor_thread = None
        
        self.current_language = "en" 
        self.initial_status_key = "gui_status_initializing"
        self.is_settings_loaded_successfully = False

        self.is_network_connected = True  
        self.connection_checker_thread = None
        self.network_check_interval = 15  
        self.bot_should_be_running = False  
        self.last_connection_error_message_key = None 
        self.bot_operation_lock = threading.Lock() # To prevent race conditions with bot start/stop


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
        logger.info("GUI: Log processing thread started.")
        while self.gui_active:
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

    def _perform_network_check(self, host="api.telegram.org", port=443, timeout=5) -> bool:
        try:
            socket.create_connection((host, port), timeout=timeout).close()
            return True
        except OSError:
            return False

    def _check_connection_loop(self):
        logger.info("GUI: Connection checker thread started.")
        
        while self.gui_active:
            current_connection_status = self._perform_network_check()

            if current_connection_status != self.is_network_connected:
                self.is_network_connected = current_connection_status
                logger.info(f"GUI: Network status changed to: {'Connected' if self.is_network_connected else 'Disconnected'}")

                if self.is_network_connected:
                    self.update_status("gui_status_connection_restored", is_running=None)
                    if self.bot_should_be_running:
                        logger.info("GUI: Network restored. Bot should be running. Ensuring a fresh start.")
                        self.update_status("gui_status_attempting_restart_after_connection", is_running=None)
                        # Force stop any lingering instance and then start fresh
                        self._ensure_bot_stopped_for_restart()
                        self.start_bot_action() 
                else: # Network Lost
                    logger.warning("GUI: Network connection lost.")
                    self.update_status("gui_status_connection_lost", is_error=True, is_running=None)
                    if self.bot_should_be_running:
                        logger.info("GUI: Network lost while bot was intended to run. Attempting to stop current bot instance.")
                        self._ensure_bot_stopped_for_restart() # Stop the bot if it was running
                        # Status will be updated by update_status based on bot_should_be_running and is_network_connected
            
            time.sleep(self.network_check_interval)
        logger.info("GUI: Connection checker thread stopped.")

    def _ensure_bot_stopped_for_restart(self):
        """Helper to stop the bot if it's running. Used before a network-related restart."""
        with self.bot_operation_lock:
            if self.bot_thread and self.bot_thread.is_alive():
                logger.info("GUI: Internal call to stop bot for restart...")
                if self.bot_application_instance and self.bot_event_loop and self.bot_event_loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(stop_bot_async(self.bot_application_instance), self.bot_event_loop)
                    try:
                        future.result(timeout=5) # Shorter timeout for internal stop
                        logger.info("GUI: Bot instance stopped for restart.")
                    except Exception as e:
                        logger.warning(f"GUI: Error/timeout stopping bot instance for restart: {e}")
                
                # Wait for thread to finish, essential before starting a new one
                self.bot_thread.join(timeout=5)
                if self.bot_thread.is_alive():
                    logger.warning("GUI: Bot thread did not terminate after stop command for restart.")
                else:
                    logger.info("GUI: Bot thread confirmed terminated for restart.")
                self.bot_thread = None
                self.bot_application_instance = None
            else:
                logger.info("GUI: No active bot instance to stop for restart.")


    def _gui_eval_js(self, script: str):
        if self.window:
            try:
                self.window.evaluate_js(script)
            except Exception as e:
                logger.debug(f"GUI: Failed to evaluate JS (window might be closing/closed): {e}. Script: {script[:100]}...")

    def update_status_internal(self, message_key_or_text: str, is_error: bool = False, is_running: bool = None, is_raw_text: bool = False):
        if self.window:
            final_message_key_or_text = message_key_or_text
            final_is_error = is_error
            final_is_running = is_running 
            final_is_raw_text = is_raw_text

            if not self.is_network_connected and self.bot_should_be_running and message_key_or_text == "gui_status_stopped":
                final_message_key_or_text = "gui_status_connection_lost_bot_stopped"
                final_is_error = True
                final_is_running = False 
                final_is_raw_text = False
                self.last_connection_error_message_key = final_message_key_or_text
            
            elif self.last_connection_error_message_key and message_key_or_text == "gui_status_stopped" and not self.is_network_connected:
                final_message_key_or_text = self.last_connection_error_message_key
                final_is_error = True
                final_is_running = False
                final_is_raw_text = False


            js_message = json.dumps(final_message_key_or_text)
            js_is_error = str(final_is_error).lower()
            js_is_running_str = 'null' if final_is_running is None else str(final_is_running).lower()
            js_is_raw_text = str(final_is_raw_text).lower()
            
            self._gui_eval_js(f'updateStatus({js_message}, {js_is_error}, {js_is_running_str}, {js_is_raw_text})')

    def update_status(self, message_key_or_text: str, is_error: bool = False, is_running: bool = None, is_raw_text: bool = False):
        if not self.is_network_connected and self.bot_should_be_running:
            if message_key_or_text not in ["gui_status_connection_restored", "gui_status_attempting_restart_after_connection"]:
                # If bot thread exists, it means PTB might be retrying internally. Buttons should reflect this.
                current_bot_thread_alive = self.bot_thread and self.bot_thread.is_alive()
                self.update_status_internal("gui_status_bot_paused_no_connection", True, current_bot_thread_alive, False)
                self.last_connection_error_message_key = "gui_status_bot_paused_no_connection"
                return

        self.update_status_internal(message_key_or_text, is_error, is_running, is_raw_text)
        
        connection_error_keys = [
            "gui_status_connection_lost", "gui_status_bot_paused_no_connection",
            "gui_status_bot_cannot_start_no_connection", "gui_status_connection_lost_bot_stopped"
        ]
        if message_key_or_text in connection_error_keys:
            self.last_connection_error_message_key = message_key_or_text
        elif not is_error or message_key_or_text in ["gui_status_connection_restored", "gui_status_attempting_restart_after_connection", "gui_status_running", "gui_status_stopped"]:
             if self.is_network_connected : 
                self.last_connection_error_message_key = None


    def _run_bot_in_thread(self):
        self.bot_event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.bot_event_loop)
        try:
            # This lock ensures that the bot_application_instance is not None when stop_bot_async is called.
            with self.bot_operation_lock:
                 self.bot_application_instance = create_bot_application()

            if self.bot_application_instance:
                logger.info("GUI: Bot application instance created successfully.")
                if not self.is_network_connected: # Re-check, network might have dropped
                    logger.warning("GUI: Network connection lost before bot could fully start. Thread will exit.")
                    self.update_status("gui_status_bot_cannot_start_no_connection", True, False) 
                    return 

                self.update_status("gui_status_running", is_running=True)
                self.bot_event_loop.run_until_complete(run_bot_async(self.bot_application_instance))
            else:
                logger.error("GUI: Failed to create bot application instance (likely BOT_TOKEN missing or invalid).")
                self.update_status("gui_status_failed_create_app", True, False)
        except Exception as e:
            # Log full traceback to console/file for debugging
            logger.error(f"GUI: Unhandled exception in bot thread: {e}", exc_info=True) 
            
            is_network_related_exception = isinstance(e, (PTBNetworkError, ConnectError, ReadTimeout, RemoteProtocolError, WriteTimeout, PoolTimeout, socket.gaierror, socket.timeout))

            if not self.is_network_connected or is_network_related_exception:
                self.update_status("gui_status_bot_paused_no_connection", True, False)
            else:
                self.update_status("gui_status_crashed", True, False)
        finally:
            logger.info("GUI: Bot thread processing finished.")
            if self.bot_event_loop and self.bot_event_loop.is_running():
                try: self.bot_event_loop.stop()
                except Exception as e_loop_stop: logger.error(f"GUI: Error stopping bot event loop: {e_loop_stop}")
            if self.bot_event_loop and not self.bot_event_loop.is_closed():
                self.bot_event_loop.close()
            
            with self.bot_operation_lock: # Ensure instance is cleared safely
                self.bot_application_instance = None
            
            # Only reset UI to stopped if user didn't intend to stop or if network is fine
            # If bot_should_be_running and network is down, connection_checker handles restart attempt
            if not (self.bot_should_be_running and not self.is_network_connected):
                 self._reset_ui_to_stopped_state()


    def start_bot_action(self):
        with self.bot_operation_lock:
            self.bot_should_be_running = True 

            if not self.is_network_connected:
                logger.error("GUI: Cannot start bot, no internet connection.")
                self.update_status("gui_status_bot_cannot_start_no_connection", True, False)
                return

            if not self.is_settings_loaded_successfully:
                self.update_status("gui_status_settings_not_loaded", True, False)
                logger.error("GUI: Attempted to start bot, but settings.json was not loaded successfully.")
                self.bot_should_be_running = False 
                return
            if not utils.SETTINGS or not utils.SETTINGS.get("BOT_TOKEN"):
                self.update_status(get_text("gui_alert_bot_token_empty", self.current_language), True, False, is_raw_text=True)
                logger.error("GUI: Attempted to start bot, but BOT_TOKEN is missing in settings.")
                self.bot_should_be_running = False 
                return
            if utils.QUESTIONS is None: 
                if not load_questions():
                    logger.warning("GUI: questions.json could not be loaded. /apply command may fail or use empty questions.")
            
            if self.bot_thread and self.bot_thread.is_alive():
                logger.info("GUI: Bot is already running or starting.")
                if self.is_network_connected:
                    self.update_status("gui_status_running", is_running=True)
                else: 
                    self.update_status("gui_status_bot_paused_no_connection", is_error=True, is_running=True)
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
        is_raw_text = False

        if self.bot_should_be_running and not self.is_network_connected:
            status_key = "gui_status_connection_lost_bot_stopped"
            is_error = True
            self.last_connection_error_message_key = status_key
        elif not self.is_settings_loaded_successfully:
            status_key = "gui_status_settings_not_loaded"
            is_error = True
        elif not utils.SETTINGS or not utils.SETTINGS.get("BOT_TOKEN"):
            status_key = get_text("gui_alert_bot_token_empty", self.current_language, default="Bot token is missing.")
            is_error = True
            is_raw_text = True
        
        self.update_status_internal(status_key, is_error=is_error, is_running=False, is_raw_text=is_raw_text)
            
        # self.bot_application_instance = None # Moved to _run_bot_in_thread finally with lock


    def stop_bot_action(self):
        with self.bot_operation_lock:
            self.bot_should_be_running = False 

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

            if self.bot_event_loop.is_running() and self.bot_application_instance:
                future = asyncio.run_coroutine_threadsafe(stop_bot_async(self.bot_application_instance), self.bot_event_loop)
                try:
                    future.result(timeout=15)
                    logger.info("GUI: Stop command sent and processed by bot thread.")
                except asyncio.TimeoutError:
                    logger.warning("GUI: Timeout waiting for bot stop confirmation. Bot thread might take longer or be stuck.")
                except Exception as e:
                    logger.error(f"GUI: Error during run_coroutine_threadsafe for stop: {e}")
            else:
                logger.warning("GUI: Bot event loop not running or instance missing. Cannot send stop command gracefully.")
        
        # _reset_ui_to_stopped_state will be called by the bot_thread's finally block.

    def on_frontend_ready(self):
        logger.info("GUI: Frontend reported ready. Initializing GUI state.")
        
        gui_translations = _get_gui_localization_texts(self.current_language)
        if self.window:
            window_title = gui_translations.get("gui_title", "Application Bot Control")
            self.window.set_title(window_title)

        initial_config = {
            "currentLang": self.current_language,
            "currentTheme": utils.SETTINGS.get("THEME", "default-dark") if utils.SETTINGS else "default-dark",
            "currentLogo": utils.SETTINGS.get("SELECTED_LOGO", "default") if utils.SETTINGS else "default",
            "guiTranslations": gui_translations,
            "maxLogLines": self.current_max_log_lines,
            "initialLogs": [html.escape(log_item, quote=False) for log_item in list(self.log_deque)]
        }
        self._gui_eval_js(f"initializeGui({json.dumps(initial_config)})")
        
        if not self.is_network_connected:
            self.update_status("gui_status_connection_lost_bot_stopped", True, False)
        else:
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

        self.connection_checker_thread = threading.Thread(target=self._check_connection_loop, daemon=True)
        self.connection_checker_thread.start()


        html_file_rel_path = "web_ui/gui.html"
        html_file_abs_path = get_asset_path(html_file_rel_path)
        
        self.is_network_connected = self._perform_network_check()
        if not self.is_network_connected:
            self.initial_status_key = "gui_status_connection_lost_bot_stopped" 
            logger.warning("GUI: Initial network check failed. Starting with connection lost status.")
        
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
        
        webview.start(debug=debug_mode, private_mode=True) 
        
        logger.info("GUI: Pywebview main loop has exited. Application should be shutting down.")


    def _trigger_cleanup_on_window_closed(self):
        logger.info("GUI: Window 'closed' event received. Initiating cleanup.")
        self.perform_app_cleanup()

    def perform_app_cleanup(self):
        logger.info("GUI: Starting application cleanup sequence.")
        
        self.gui_active = False 
        self.bot_should_be_running = False # Ensure no restarts are attempted during cleanup

        with self.bot_operation_lock:
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
            self.bot_application_instance = None # Clear it finally

        if self.log_processor_thread and self.log_processor_thread.is_alive():
            self.log_processor_thread.join(timeout=3)
            if self.log_processor_thread.is_alive():
                logger.warning("GUI: Log processor thread did not terminate.")
            else:
                logger.info("GUI: Log processor thread terminated.")
        else:
            logger.info("GUI: Log processor thread was not running or already finished at cleanup.")
        
        if self.connection_checker_thread and self.connection_checker_thread.is_alive():
            self.connection_checker_thread.join(timeout=self.network_check_interval + 1) 
            if self.connection_checker_thread.is_alive():
                logger.warning("GUI: Connection checker thread did not terminate.")
            else:
                logger.info("GUI: Connection checker thread terminated.")
        else:
            logger.info("GUI: Connection checker thread was not running or already finished at cleanup.")
            
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
        logger.info(f"GUI: Settings loaded. Initial language: {app_gui.current_language}, Theme: {utils.SETTINGS.get('THEME', 'default-dark')}, Logo: {utils.SETTINGS.get('SELECTED_LOGO', 'default')}")
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