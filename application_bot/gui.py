import webview
import logging
import sys
import threading
import asyncio
import queue
from collections import deque
import time
import json
import html
import os
import platform
import subprocess
from typing import List, Dict, Any

from application_bot import utils
from application_bot.main import create_bot_application, run_bot_async, stop_bot_async
from application_bot.utils import (
    load_settings, load_questions,
    get_external_file_path, save_settings as utils_save_settings, get_text, get_data_file_path # Renamed to avoid conflict
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
        "gui_modal_table_header_id", "gui_modal_table_header_text", "gui_modal_table_header_actions",
        "gui_alert_question_empty_fields", "gui_alert_duplicate_ids", "gui_alert_questions_saved",
        "gui_alert_questions_save_failed", "gui_alert_questions_save_error",
        # Keys for the new combined settings modal
        "gui_settings_button", "gui_modal_settings_title",
        "gui_tab_basic_settings", "gui_tab_pdf_settings", "gui_tab_admin_settings",
        "gui_override_user_lang_label",
        "gui_send_pdf_to_admins_label", "gui_app_photo_numb_label",
        "gui_bot_token_label", "gui_admin_ids_label",
        "gui_alert_settings_saved", "gui_alert_settings_save_failed",
        "gui_alert_settings_save_error", "gui_alert_bot_token_empty",
        "gui_alert_invalid_photo_numb",
        # Re-listing PDF settings specific labels for clarity, they are part of the new modal
        "gui_pdf_font_file_path", "gui_pdf_font_name_registered", "gui_pdf_page_width_mm",
        "gui_pdf_page_height_mm", "gui_pdf_margin_mm", "gui_pdf_photo_width_mm",
        "gui_pdf_photo_position", "gui_pdf_photo_pos_top_right", "gui_pdf_photo_pos_center",
        "gui_pdf_title_font_size", "gui_pdf_header_font_size", "gui_pdf_question_font_size",
        "gui_pdf_answer_font_size", "gui_pdf_question_bold",
        "gui_alert_pdf_settings_load_failed", # This might be part of general settings load failed now
        "gui_alert_pdf_font_paths_empty" # This might be part of general settings save failed now
    ]
    if not utils.SETTINGS: # Should not happen if load_settings creates a default
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
                self._gui._gui_eval_js(f"setLogLinesConfig({self._gui.current_max_log_lines})") # Revert UI
        except ValueError:
            logger.warning(f"GUI API: Non-integer log lines count from UI: {count_str}")
            self._gui._gui_eval_js(f"setLogLinesConfig({self._gui.current_max_log_lines})") # Revert UI

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
                self._gui._gui_eval_js(f"alert('{html.escape(alert_msg)}')")
            return

        app_folder_name = utils.SETTINGS.get("APPLICATION_FOLDER")
        if not app_folder_name:
            logger.error("GUI API: APPLICATION_FOLDER not defined in settings.")
            if self._gui.window:
                alert_msg = get_text("gui_alert_app_folder_not_configured", self._gui.current_language, default="Error: Application folder not configured.")
                self._gui._gui_eval_js(f"alert('{html.escape(alert_msg)}')")
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
                    self._gui._gui_eval_js(f"alert('{html.escape(alert_msg)}')")
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
                self._gui._gui_eval_js(f"alert('{html.escape(alert_msg)}')")

    def set_system_language(self, lang_code: str):
        if not utils.SETTINGS: # Should ideally not happen if defaults are created
            logger.error("GUI API: SETTINGS not loaded, cannot change language.")
            return {"error": "SETTINGS not loaded", "new_lang": "en", "translations": _get_gui_localization_texts("en")}

        original_lang = utils.SETTINGS.get("DEFAULT_LANG", "en")
        if lang_code not in utils.SETTINGS.get("LANGUAGES", {}):
            logger.warning(f"GUI API: Language code '{lang_code}' not found in settings. Reverting to original '{original_lang}'.")
            lang_code = original_lang # Revert to original if invalid

        utils.SETTINGS["DEFAULT_LANG"] = lang_code

        if utils_save_settings(utils.SETTINGS): # Use renamed import
            logger.info(f"GUI API: System language changed to '{lang_code}' and settings saved.")
            self._gui.current_language = lang_code
        else:
            logger.error(f"GUI API: Failed to save settings after changing language to '{lang_code}'. Reverting in-memory.")
            utils.SETTINGS["DEFAULT_LANG"] = original_lang # Revert in-memory
            lang_code = original_lang # Ensure lang_code reflects the actual state

        new_translations = _get_gui_localization_texts(lang_code)

        if self._gui.window: # Update window title immediately
            window_title = new_translations.get("gui_title", "Application Bot Control")
            self._gui.window.set_title(window_title)
        
        return {"new_lang": lang_code, "translations": new_translations}

    def get_questions(self):
        logger.info("GUI API: Received request for questions.")
        if utils.QUESTIONS is None:
            logger.info("GUI API: utils.QUESTIONS is None, attempting to load.")
            utils.load_questions() # This will populate utils.QUESTIONS or set to []

        if utils.QUESTIONS is not None:
            logger.debug(f"GUI API: Returning questions: {utils.QUESTIONS}")
            return utils.QUESTIONS
        else: # Should be [] if load_questions failed gracefully. This path is less likely.
            logger.warning("GUI API: Questions still not loaded after attempt, returning empty list to UI.")
            return [] # Should be an empty list if it failed to load

    def save_questions(self, questions_data: List[dict]):
        logger.info(f"GUI API: Received request to save questions. Count: {len(questions_data) if questions_data else 'None'}")
        if not isinstance(questions_data, list):
            logger.error("GUI API: Invalid data format for saving questions. Expected a list.")
            return False

        # Validate each question item
        for i, q_item in enumerate(questions_data):
            if not isinstance(q_item, dict) or "id" not in q_item or "text" not in q_item:
                logger.error(f"GUI API: Invalid question item format at index {i}: {q_item}. Missing 'id' or 'text'.")
                return False
            if not q_item["id"] or not q_item["text"]: # Check for empty strings
                 logger.error(f"GUI API: Question ID or text is empty at index {i}: {q_item}.")
                 return False

        if utils.save_questions(questions_data):
            logger.info("GUI API: Questions saved and reloaded successfully via utils.save_questions.")
            return True
        else:
            logger.error("GUI API: Failed to save questions via utils.save_questions.")
            return False

    def get_all_settings(self) -> Dict[str, Any]:
        logger.info("GUI API: Received request for all settings.")
        if not utils.SETTINGS: # Should be pre-filled with defaults by load_settings now
            logger.critical("GUI API: utils.SETTINGS is unexpectedly None in get_all_settings. This shouldn't happen.")
            # Fallback to a very basic structure for UI to prevent crash, though this indicates a deeper issue.
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

        # Ensure PDF_SETTINGS exists and has expected keys, providing defaults if not
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

        # Construct the full settings object for the GUI
        # Note: Log lines and dark mode are managed by GUI client-side or through specific API calls, not directly part of this dict
        return {
            "OVERRIDE_USER_LANG": utils.SETTINGS.get("OVERRIDE_USER_LANG", True),
            "DEFAULT_LANG": utils.SETTINGS.get("DEFAULT_LANG", "en"), # Used to set lang toggle state
            "BOT_TOKEN": utils.SETTINGS.get("BOT_TOKEN", ""),
            "ADMIN_USER_IDS": utils.SETTINGS.get("ADMIN_USER_IDS", ""),
            "APPLICATION_PHOTO_NUMB": utils.SETTINGS.get("APPLICATION_PHOTO_NUMB", 1),
            "SEND_PDF_TO_ADMINS": utils.SETTINGS.get("SEND_PDF_TO_ADMINS", True),
            "FONT_FILE_PATH": utils.SETTINGS.get("FONT_FILE_PATH", "fonts/DejaVuSans.ttf"),
            "PDF_SETTINGS": pdf_settings_data
        }

    def save_all_settings(self, new_settings_data: Dict[str, Any]) -> bool:
        logger.info(f"GUI API: Received request to save all settings: {new_settings_data}")
        if not utils.SETTINGS: # Should be pre-filled
            logger.error("GUI API: Cannot save settings, global utils.SETTINGS not loaded/initialized.")
            return False
        if not isinstance(new_settings_data, dict):
            logger.error(f"GUI API: Invalid structure for settings data: {new_settings_data}")
            return False

        # --- Basic Settings (from data payload) ---
        utils.SETTINGS["OVERRIDE_USER_LANG"] = bool(new_settings_data.get("OVERRIDE_USER_LANG", True))
        # DEFAULT_LANG is handled by set_system_language
        # Log lines and Dark mode are handled by their own mechanisms and not directly saved to settings.json here

        # --- Admin Settings ---
        bot_token = str(new_settings_data.get("BOT_TOKEN", "")).strip()
        if not bot_token: # Basic validation
            logger.error("GUI API: Bot Token cannot be empty.")
            # UI should also show an alert based on return from JS or specific error message
            return False # Or return a dict like {"success": False, "error_field": "BOT_TOKEN", "message_key": "gui_alert_bot_token_empty"}
        utils.SETTINGS["BOT_TOKEN"] = bot_token
        utils.SETTINGS["ADMIN_USER_IDS"] = str(new_settings_data.get("ADMIN_USER_IDS", "")).strip()

        # --- PDF Tab Specific Settings (not nested under PDF_SETTINGS) ---
        try:
            photo_numb = int(new_settings_data.get("APPLICATION_PHOTO_NUMB", 1))
            if photo_numb < 0: raise ValueError("Cannot be negative")
            utils.SETTINGS["APPLICATION_PHOTO_NUMB"] = photo_numb
        except (ValueError, TypeError):
            logger.error("GUI API: Invalid value for APPLICATION_PHOTO_NUMB.")
            return False # Or return specific error
        utils.SETTINGS["SEND_PDF_TO_ADMINS"] = bool(new_settings_data.get("SEND_PDF_TO_ADMINS", True))

        # --- Detailed PDF Settings (nested under PDF_SETTINGS) ---
        if "FONT_FILE_PATH" in new_settings_data and \
           "PDF_SETTINGS" in new_settings_data and \
           isinstance(new_settings_data["PDF_SETTINGS"], dict):

            utils.SETTINGS["FONT_FILE_PATH"] = str(new_settings_data["FONT_FILE_PATH"]).strip()
            if not utils.SETTINGS["FONT_FILE_PATH"]: # Basic validation
                logger.error("GUI API: PDF Font File Path cannot be empty.") # This should be handled by UI too
                # return False # Or specific error

            if "PDF_SETTINGS" not in utils.SETTINGS: # Should exist due to load_settings
                utils.SETTINGS["PDF_SETTINGS"] = {}

            pdf_sub_settings_from_ui = new_settings_data["PDF_SETTINGS"]
            current_pdf_settings = utils.SETTINGS["PDF_SETTINGS"] # Get current for updates

            try:
                # Update string type settings
                current_pdf_settings["font_name_registered"] = str(pdf_sub_settings_from_ui.get("font_name_registered", "CustomUnicodeFont")).strip()
                if not current_pdf_settings["font_name_registered"]:
                     logger.error("GUI API: PDF Registered Font Name cannot be empty.")
                     # return False
                current_pdf_settings["photo_position"] = str(pdf_sub_settings_from_ui.get("photo_position", "top_right"))

                # Update numeric float settings
                numeric_keys_float = ["page_width_mm", "page_height_mm", "margin_mm", "photo_width_mm"]
                for key in numeric_keys_float:
                    current_pdf_settings[key] = float(pdf_sub_settings_from_ui.get(key, current_pdf_settings.get(key, 0)))

                # Update numeric int settings
                numeric_keys_int = ["title_font_size", "header_font_size", "question_font_size", "answer_font_size"]
                for key in numeric_keys_int:
                     current_pdf_settings[key] = int(pdf_sub_settings_from_ui.get(key, current_pdf_settings.get(key, 0)))
                
                # Update boolean
                current_pdf_settings["question_bold"] = bool(pdf_sub_settings_from_ui.get("question_bold", True))

            except (ValueError, TypeError) as e:
                logger.error(f"GUI API: Invalid data type in PDF sub-settings: {e}. Data: {pdf_sub_settings_from_ui}")
                return False
        else:
            logger.warning("GUI API: FONT_FILE_PATH or PDF_SETTINGS structure missing/malformed in save_all_settings data.")
            # Depending on strictness, could return False here

        # Attempt to save all accumulated changes
        if utils_save_settings(utils.SETTINGS):
            logger.info("GUI API: All settings saved successfully to settings.json.")
            # Note: For BOT_TOKEN or ADMIN_USER_IDS changes to take effect in the bot,
            # the bot application typically needs to be restarted. The GUI can inform the user.
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
        self.current_language = "en" # Default, will be updated from settings
        self.initial_status_key = "gui_status_initializing"
        self.is_settings_loaded_successfully = False # More descriptive name

    def setup_gui_logging(self):
        gui_log_handler = WebviewLogHandler(self.log_queue)
        # Formatter with consistent date format
        formatter = logging.Formatter('%(asctime)s [%(levelname)-7s] %(name)s: %(message)s', datefmt='%H:%M:%S')
        gui_log_handler.setFormatter(formatter)
        root_logger = logging.getLogger()
        
        # Avoid adding duplicate handlers if this method is called multiple times (though it shouldn't be)
        if not any(isinstance(h, WebviewLogHandler) for h in root_logger.handlers):
            root_logger.addHandler(gui_log_handler)
        
        # Ensure a console handler is present for dev/debug visibility if not already added by basicConfig
        if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers if h.stream == sys.stderr):
            console_handler = logging.StreamHandler(sys.stderr) # Log to stderr
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
            
        root_logger.setLevel(logging.INFO) # Set root logger level
        # Set specific levels for noisy libraries
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
                batch_size = 0 # Max messages per batch
                # Max time to wait for a batch to fill before sending
                timeout_ms = 50 # milliseconds
                start_time = time.monotonic_ns()

                # Collect messages in a batch efficiently
                while not self.log_queue.empty() and batch_size < 50 : # Max 50 messages per batch
                    # If time exceeds timeout and we have some messages, send them
                    if (time.monotonic_ns() - start_time) / 1_000_000 > timeout_ms and batch_size > 0:
                        break
                    try:
                        msg = self.log_queue.get(timeout=0.01) # Short timeout to allow checking active flag
                        self.log_deque.append(msg)
                        messages_to_send.append(msg)
                        batch_size +=1
                    except queue.Empty:
                        break # No more messages currently
                
                if messages_to_send and self.window:
                    # Escape HTML characters in messages before sending to JS
                    js_safe_messages = [html.escape(m) for m in messages_to_send]
                    js_messages_array_str = json.dumps(js_safe_messages)
                    self._gui_eval_js(f'addBatchLogMessages({js_messages_array_str})')

            except Exception as e: # Catch broad exceptions to keep the thread alive
                # Use a logger that will definitely be visible (e.g., console if GUI logger fails)
                logging.critical(f"CRITICAL Error in _process_log_queue_loop: {e}", exc_info=True)
            
            # Adjust sleep time based on whether messages were processed
            time.sleep(0.15 if not messages_to_send else 0.05) 
        logger.info("GUI: Log processing thread stopped.")

    def _gui_eval_js(self, script: str):
        if self.window:
            try:
                self.window.evaluate_js(script)
            except Exception as e:
                # This can happen if the window is closing or JS context is lost
                logger.debug(f"GUI: Failed to evaluate JS (window might be closing/closed): {e}. Script: {script[:100]}...")


    def update_status(self, message_key_or_text: str, is_error: bool = False, is_running: bool = None, is_raw_text: bool = False):
        if self.window:
            js_message = json.dumps(message_key_or_text) # Ensure proper JS string
            js_is_error = str(is_error).lower() # true/false
            js_is_running = 'null' if is_running is None else str(is_running).lower()
            js_is_raw_text = str(is_raw_text).lower()
            self._gui_eval_js(f'updateStatus({js_message}, {js_is_error}, {js_is_running}, {js_is_raw_text})')

    def _run_bot_in_thread(self):
        self.bot_event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.bot_event_loop)
        try:
            self.bot_application_instance = create_bot_application() # Reads from utils.SETTINGS
            if self.bot_application_instance:
                logger.info("GUI: Bot application instance created successfully.")
                self.update_status("gui_status_running", is_running=True)
                self.bot_event_loop.run_until_complete(run_bot_async(self.bot_application_instance))
            else:
                logger.error("GUI: Failed to create bot application instance (likely BOT_TOKEN missing or invalid).")
                # Bot token is now editable, so this state is more important
                self.update_status("gui_status_failed_create_app", True, False)
        except Exception as e:
            logger.error(f"GUI: Unhandled exception in bot thread: {e}", exc_info=True)
            self.update_status("gui_status_crashed", True, False)
        finally:
            logger.info("GUI: Bot thread processing finished.")
            # Clean up event loop
            if self.bot_event_loop and self.bot_event_loop.is_running():
                try: self.bot_event_loop.stop()
                except Exception as e_loop_stop: logger.error(f"GUI: Error stopping bot event loop: {e_loop_stop}")
            if self.bot_event_loop and not self.bot_event_loop.is_closed():
                self.bot_event_loop.close()
            self._reset_ui_to_stopped_state()


    def start_bot_action(self):
        if not self.is_settings_loaded_successfully: # Check if settings.json was loaded properly
            self.update_status("gui_status_settings_not_loaded", True, False)
            logger.error("GUI: Attempted to start bot, but settings.json was not loaded successfully.")
            return
        if not utils.SETTINGS or not utils.SETTINGS.get("BOT_TOKEN"):
             self.update_status(get_text("gui_alert_bot_token_empty", self.current_language), True, False, is_raw_text=True)
             logger.error("GUI: Attempted to start bot, but BOT_TOKEN is missing in settings.")
             return
        if utils.QUESTIONS is None: # Check if questions are loaded; if not, try to load them
            if not load_questions(): # load_questions will update utils.QUESTIONS or log errors
                logger.warning("GUI: questions.json could not be loaded. /apply command may fail or use empty questions.")
                # Allow bot to start, but with a warning.
        
        if self.bot_thread and self.bot_thread.is_alive():
            logger.info("GUI: Bot is already running or starting.")
            return

        # Update UI immediately
        self._gui_eval_js('setButtonState("start-button", false)')
        self._gui_eval_js('setButtonState("stop-button", true)')
        self.update_status("gui_status_starting", is_running=None) # Intermediate state
        logger.info("GUI: Initiating bot start sequence...")

        self.bot_thread = threading.Thread(target=self._run_bot_in_thread, daemon=True)
        self.bot_thread.start()

    def _reset_ui_to_stopped_state(self):
        # This function should be callable even if self.window is None or closing
        self._gui_eval_js('setButtonState("start-button", true)')
        self._gui_eval_js('setButtonState("stop-button", false)')
        
        status_key = "gui_status_stopped"
        is_error = False
        if not self.is_settings_loaded_successfully:
            status_key = "gui_status_settings_not_loaded"
            is_error = True
        elif not utils.SETTINGS or not utils.SETTINGS.get("BOT_TOKEN"):
            # If token becomes empty after successful load, that's an error state for starting.
            # Display the specific message for bot token.
            # This raw text is okay because updateStatus will get the translation.
            status_key = get_text("gui_alert_bot_token_empty", self.current_language, default="Bot token is missing.")
            is_error = True
            self.update_status(status_key, is_error=is_error, is_running=False, is_raw_text=True)
        else:
            self.update_status(status_key, is_error=is_error, is_running=False)
            
        self.bot_application_instance = None # Clear instance


    def stop_bot_action(self):
        if not self.bot_thread or not self.bot_thread.is_alive():
            logger.info("GUI: Bot is not currently running or already stopping.")
            self._reset_ui_to_stopped_state() # Ensure UI is correct
            return

        if not self.bot_application_instance or not self.bot_event_loop:
            logger.warning("GUI: Stop called, but bot instance or event loop is missing. Forcing UI reset.")
            self._reset_ui_to_stopped_state()
            return

        self.update_status("gui_status_stopping", is_running=None) # Intermediate state
        logger.info("GUI: Initiating bot stop sequence...")

        if self.bot_event_loop.is_running():
            # Schedule stop_bot_async to run in the bot's event loop
            future = asyncio.run_coroutine_threadsafe(stop_bot_async(self.bot_application_instance), self.bot_event_loop)
            try:
                # Wait for the coroutine to complete, with a timeout
                future.result(timeout=15) # Increased timeout
                logger.info("GUI: Stop command sent and processed by bot thread.")
            except asyncio.TimeoutError:
                logger.warning("GUI: Timeout waiting for bot stop confirmation. Bot thread might take longer or be stuck.")
                # The bot thread will eventually exit, but UI might reset sooner.
            except Exception as e:
                logger.error(f"GUI: Error during run_coroutine_threadsafe for stop: {e}")
        else:
            logger.warning("GUI: Bot event loop not running. Cannot send stop command gracefully.")
            # UI will be reset by _run_bot_in_thread's finally block or here if needed.
        
        # UI state is typically reset by _run_bot_in_thread's finally block.
        # If stop is called independently and succeeds quickly, that block handles it.
        # If timeout occurs, _reset_ui_to_stopped_state might be called by `_run_bot_in_thread`'s finally block eventually.

    def on_frontend_ready(self):
        logger.info("GUI: Frontend reported ready. Initializing GUI state.")
        
        # Language and translations (current_language already set by main_gui_start)
        gui_translations = _get_gui_localization_texts(self.current_language)
        if self.window:
            window_title = gui_translations.get("gui_title", "Application Bot Control")
            self.window.set_title(window_title)

        # Initial config for JS
        initial_config = {
            "currentLang": self.current_language,
            "guiTranslations": gui_translations,
            "maxLogLines": self.current_max_log_lines,
            "initialLogs": list(self.log_deque) # Send existing logs if any (e.g. from pre-GUI init)
        }
        self._gui_eval_js(f"initializeGui({json.dumps(initial_config)})")
        
        # Set initial status and button states
        self._reset_ui_to_stopped_state() # This handles various conditions for initial status message


    def set_max_log_lines_config(self, count: int):
        logger.info(f"GUI: Setting max log lines to {count}")
        self.current_max_log_lines = count
        
        # Rebuild deque with new maxlen, preserving recent items
        current_logs = list(self.log_deque) # Get all current logs
        self.log_deque = deque(maxlen=self.current_max_log_lines) # New deque with new maxlen
        # Add items to new deque, it will automatically keep only the last `maxlen` items
        for log_item in current_logs[-self.current_max_log_lines:]: # Take up to new max from end of old list
            self.log_deque.append(log_item)
            
        # Send updated config and current (possibly truncated) logs to UI
        js_safe_current_logs = [html.escape(m) for m in list(self.log_deque)]
        self._gui_eval_js(f"setLogLinesConfig({self.current_max_log_lines}, {json.dumps(js_safe_current_logs)})")

    def repopulate_logs_to_frontend(self):
        # This is called if JS requests it, e.g., after a disconnect/reconnect (if that were handled)
        if self.log_deque:
            js_safe_logs = [html.escape(m) for m in list(self.log_deque)]
            self._gui_eval_js(f"clearLogs(); addBatchLogMessages({json.dumps(js_safe_logs)})")


    def run(self):
        # Logging setup should happen before any log messages are generated by GUI components
        self.setup_gui_logging() 

        self.log_processor_thread = threading.Thread(target=self._process_log_queue_loop, daemon=True)
        self.log_processor_thread.start()

        html_file_rel_path = "web_ui/gui.html"
        html_file_abs_path = get_asset_path(html_file_rel_path)
        
        # Initial title uses current_language which should be set by main_gui_start
        initial_title = get_text("gui_title", self.current_language, default="Application Bot Control")

        logger.info(f"GUI: Creating pywebview window. Title: '{initial_title}'. HTML: '{html_file_abs_path}'")
        self.window = webview.create_window(
            initial_title,
            html_file_abs_path,
            js_api=self.api,
            width=850, # Slightly wider for new settings modal
            height=700, # Slightly taller
            resizable=True,
            min_size=(800, 650) 
        )
        self.window.events.closed += self._trigger_cleanup_on_window_closed # For graceful shutdown
        
        debug_mode = utils.SETTINGS.get("PYWEBVIEW_DEBUG", False) if utils.SETTINGS else False
        logger.info(f"GUI: Starting pywebview main loop. Debug: {debug_mode}")
        
        webview.start(debug=debug_mode, private_mode=False) # private_mode=False is default and usually fine
        
        logger.info("GUI: Pywebview main loop has exited. Application should be shutting down.")
        # perform_app_cleanup will be called via the 'closed' event if window closed normally.
        # If webview.start exits for other reasons, ensure cleanup happens.
        # However, typically, the script ends here. If cleanup is needed after webview.start returns,
        # it should be explicitly called. The current 'closed' event handles normal exits.


    def _trigger_cleanup_on_window_closed(self):
        logger.info("GUI: Window 'closed' event received. Initiating cleanup.")
        self.perform_app_cleanup()

    def perform_app_cleanup(self):
        logger.info("GUI: Starting application cleanup sequence.")
        
        self.log_processing_active = False # Signal log processor to stop

        # Stop bot thread if running
        if self.bot_thread and self.bot_thread.is_alive():
            logger.info("GUI: Bot is running, attempting to stop it during cleanup.")
            if self.bot_application_instance and self.bot_event_loop and self.bot_event_loop.is_running():
                # Use run_coroutine_threadsafe as stop_bot_async is an async function
                future = asyncio.run_coroutine_threadsafe(stop_bot_async(self.bot_application_instance), self.bot_event_loop)
                try:
                    future.result(timeout=7) # Wait for stop to complete
                    logger.info("GUI: Bot stop command processed during cleanup.")
                except Exception as e: # Catches TimeoutError or other exceptions from stop_bot_async
                    logger.warning(f"GUI: Error or timeout stopping bot during cleanup: {e}")
            
            # Join the bot thread
            self.bot_thread.join(timeout=7) # Wait for thread to finish
            if self.bot_thread.is_alive():
                logger.warning("GUI: Bot thread did not terminate gracefully after stop and join.")
            else:
                logger.info("GUI: Bot thread terminated.")
        else:
            logger.info("GUI: Bot thread was not running or already finished at cleanup.")

        # Join log processor thread
        if self.log_processor_thread and self.log_processor_thread.is_alive():
            self.log_processor_thread.join(timeout=3) # Wait for log processor to finish
            if self.log_processor_thread.is_alive():
                logger.warning("GUI: Log processor thread did not terminate.")
            else:
                logger.info("GUI: Log processor thread terminated.")
        else:
            logger.info("GUI: Log processor thread was not running or already finished at cleanup.")
            
        logger.info("GUI: Application cleanup finished.")


def main_gui_start():
    # Basic logging setup for VERY early messages (before GUI handler is attached)
    # This helps if pywebview itself has issues or before setup_gui_logging runs.
    if not logging.getLogger().handlers: # Only if no handlers are configured yet
        logging.basicConfig(
            level=logging.INFO, 
            format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s", 
            datefmt='%H:%M:%S',
            stream=sys.stderr # Log to stderr initially
        )
        # Set levels for noisy libraries early
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("telegram").setLevel(logging.INFO) 
        logging.getLogger("httpcore").setLevel(logging.INFO)
        logging.getLogger("pywebview").setLevel(logging.INFO) # Pywebview's own logs

    logger.info("ApplicationBotGUI starting...")

    # Load settings and questions. utils.load_settings now ensures SETTINGS is not None.
    settings_file_ok = utils.load_settings() # Populates utils.SETTINGS, returns True if file existed and was valid
    questions_ok = utils.load_questions()    # Populates utils.QUESTIONS

    app_gui = BotGUI()

    # Set GUI state based on whether settings.json was successfully loaded
    app_gui.is_settings_loaded_successfully = settings_file_ok 
    
    # Determine initial language for GUI elements before window creation
    # utils.SETTINGS should always exist here due to changes in load_settings
    app_gui.current_language = utils.SETTINGS.get("DEFAULT_LANG", "en") 
    
    if settings_file_ok:
        logger.info(f"GUI: Settings loaded from settings.json. Initial language: {app_gui.current_language}")
    else:
        # load_settings now logs this and creates default utils.SETTINGS
        logger.critical("GUI CRITICAL: settings.json was not found or was invalid. GUI is using default values. Functionality may be limited until settings are configured and saved via the GUI.")
        # The GUI status will reflect "settings.json not loaded!"

    if not questions_ok: # Check result of load_questions()
        logger.warning("GUI WARNING: Failed to load questions.json initially. /apply command might be affected. Editing questions will start with an empty list or defaults if the file is missing/corrupt.")
        # utils.QUESTIONS would be an empty list if load_questions failed gracefully (e.g. file not found)

    try:
        app_gui.run()
    except Exception as e:
        logger.critical(f"GUI CRITICAL: Unhandled exception in app_gui.run(): {e}", exc_info=True)
        # If GUI itself crashes, try to perform cleanup.
        app_gui.perform_app_cleanup() 
    finally:
        # This block executes after webview.start() returns (GUI window closed) or if an exception occurred in try.
        # Cleanup is now primarily handled by the window's 'closed' event calling perform_app_cleanup.
        # If an exception happens *before* the window is even shown or the event loop starts,
        # perform_app_cleanup might be called from the except block.
        logger.info("ApplicationBotGUI main_gui_start function finished.")


if __name__ == "__main__":
    main_gui_start()