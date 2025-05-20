import webview
import logging
import sys
import threading
import asyncio
import queue
from collections import deque
import time # For sleep in log processing loop
import json # For preparing batch log messages
import html # For escaping log messages
import os
import platform # For opening folder
import subprocess # For opening folder

from application_bot.main import create_bot_application, run_bot_async, stop_bot_async
from application_bot.utils import load_settings, load_questions, SETTINGS, QUESTIONS, get_external_file_path # Added get_external_file_path

MAX_LOG_LINES_DEFAULT = 100


def get_asset_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__)) # Directory of gui.py
    return os.path.join(base_path, relative_path)


class WebviewLogHandler(logging.Handler):
    def __init__(self, log_queue_ref):
        super().__init__()
        self.log_queue = log_queue_ref # Reference to BotGUI's queue

    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put(msg)


class PyWebviewApi:
    def __init__(self, gui_instance):
        self._gui = gui_instance # Renamed from self.gui

    def start_bot_action(self):
        self._gui.start_bot_action() # Updated

    def stop_bot_action(self):
        self._gui.stop_bot_action() # Updated

    def set_max_log_lines_from_ui(self, count_str): # Called from JS
        try:
            count = int(count_str)
            if 10 <= count <= 1000:
                self._gui.set_max_log_lines_config(count) # Updated
            else:
                logging.warning(f"GUI: Invalid log lines count from UI: {count}")
                self._gui.window.evaluate_js(f"setLogLinesConfig({self._gui.current_max_log_lines})") # Updated
        except ValueError:
            logging.warning(f"GUI: Non-integer log lines count from UI: {count_str}")
            self._gui.window.evaluate_js(f"setLogLinesConfig({self._gui.current_max_log_lines})") # Updated


    def frontend_is_ready(self): # Called by JS when DOM is ready
        self._gui.on_frontend_ready() # Updated

    def request_log_repopulation(self): # Called by JS if it clears logs and needs them back
        self._gui.repopulate_logs_to_frontend() # Updated

    def open_applications_folder(self): # New method
        logging.info("GUI: Received request to open applications folder.")
        if not SETTINGS:
            logging.error("GUI: Cannot open applications folder, SETTINGS not loaded.")
            if self._gui.window:
                self._gui.window.evaluate_js("alert('Error: Settings not loaded. Cannot open folder.')")
            return

        app_folder_name = SETTINGS.get("APPLICATION_FOLDER")
        if not app_folder_name:
            logging.error("GUI: APPLICATION_FOLDER not defined in settings.")
            if self._gui.window:
                self._gui.window.evaluate_js("alert('Error: Application folder not configured in settings.')")
            return

        folder_path = get_external_file_path(app_folder_name)

        if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
            logging.warning(f"GUI: Applications folder '{folder_path}' does not exist or is not a directory. Attempting to create it.")
            try:
                os.makedirs(folder_path, exist_ok=True)
                logging.info(f"GUI: Created applications folder: {folder_path}")
            except OSError as e:
                logging.error(f"GUI: Could not create applications folder {folder_path}: {e}")
                if self._gui.window:
                    self._gui.window.evaluate_js(f"alert('Error: Could not create or access folder: {folder_path}. Check logs.')")
                return
        
        try:
            normalized_folder_path = os.path.normpath(folder_path)
            if platform.system() == "Windows":
                os.startfile(normalized_folder_path)
            elif platform.system() == "Darwin": # macOS
                subprocess.run(["open", normalized_folder_path], check=True)
            else: # Linux and other UNIX-like
                subprocess.run(["xdg-open", normalized_folder_path], check=True)
            logging.info(f"GUI: Successfully requested to open folder: {normalized_folder_path}")
        except FileNotFoundError: 
            logging.error(f"GUI: Could not open folder '{normalized_folder_path}'. Command not found (e.g., xdg-open or open).")
            if self._gui.window:
                 self._gui.window.evaluate_js(f"alert('Error: System command to open folder not found. Check logs.')")
        except subprocess.CalledProcessError as e:
             logging.error(f"GUI: Error opening folder '{normalized_folder_path}' with system command: {e}")
             if self._gui.window:
                  self._gui.window.evaluate_js(f"alert('Error: Failed to open folder using system command. Check logs.')")
        except Exception as e:
            logging.error(f"GUI: An unexpected error occurred while trying to open folder '{normalized_folder_path}': {e}")
            if self._gui.window:
                self._gui.window.evaluate_js(f"alert('Error: Could not open folder: {normalized_folder_path}. Check logs.')")


class BotGUI:
    def __init__(self):
        self.window = None # PyWebview window instance
        self.api = PyWebviewApi(self)

        self.bot_application_instance = None
        self.bot_thread = None
        self.bot_event_loop = None

        self.log_queue = queue.Queue()
        self.current_max_log_lines = MAX_LOG_LINES_DEFAULT
        self.log_deque = deque(maxlen=self.current_max_log_lines)
        self.log_processing_active = False
        self.log_processor_thread = None

        self.initial_status_message = "Initializing..."
        self.is_settings_loaded = False

        if not SETTINGS:
            self.initial_status_message = "Error: settings.json not loaded!"
            logging.error("GUI: settings.json was not loaded on initial import.")
            self.is_settings_loaded = False
        else:
            self.is_settings_loaded = True
            self.initial_status_message = "Stopped"


    def setup_gui_logging(self):
        gui_log_handler = WebviewLogHandler(self.log_queue)
        formatter = logging.Formatter('%(asctime)s [%(levelname)-7s] %(name)s: %(message)s', datefmt='%H:%M:%S')
        gui_log_handler.setFormatter(formatter)

        root_logger = logging.getLogger()
        if not root_logger.handlers: # Avoid duplicate console logs if main_cli also runs
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setFormatter(formatter)
            console_handler.setLevel(logging.ERROR) # Only critical errors to console
            root_logger.addHandler(console_handler)

        root_logger.addHandler(gui_log_handler)
        root_logger.setLevel(logging.INFO)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.info("GUI logging initialized. Interface is ready.")

    def _process_log_queue_loop(self):
        self.log_processing_active = True
        logging.info("GUI: Log processing thread started.")
        while self.log_processing_active:
            try:
                messages_to_send = []
                batch_size = 0
                while not self.log_queue.empty() and batch_size < 50: # Process up to 50 messages per cycle
                    msg = self.log_queue.get_nowait()
                    self.log_deque.append(msg) # log_deque has maxlen, handles pruning
                    messages_to_send.append(msg)
                    batch_size += 1

                if messages_to_send and self.window:
                    js_safe_messages = [html.escape(m) for m in messages_to_send]
                    js_messages_array_str = json.dumps(js_safe_messages)
                    self.window.evaluate_js(f'addBatchLogMessages({js_messages_array_str})')

            except queue.Empty:
                pass # Normal, queue might be empty
            except Exception as e:
                logging.critical(f"CRITICAL Error in _process_log_queue_loop: {e}", exc_info=True)

            time.sleep(0.2) # Check queue periodically
        logging.info("GUI: Log processing thread stopped.")


    def update_status(self, message: str, is_error: bool = False, is_running: bool = None):
        if self.window:
            js_message = json.dumps(message)
            js_is_error = str(is_error).lower()
            js_is_running = 'null' if is_running is None else str(is_running).lower()
            self.window.evaluate_js(f'updateStatus({js_message}, {js_is_error}, {js_is_running})')

    def _run_bot_in_thread(self):
        self.bot_event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.bot_event_loop)

        try:
            self.bot_application_instance = create_bot_application()
            if self.bot_application_instance:
                logging.info("Bot application instance created successfully by GUI.")
                self.update_status("Running", is_running=True)
                self.bot_event_loop.run_until_complete(run_bot_async(self.bot_application_instance))
            else:
                logging.error("GUI: Failed to create bot application instance.")
                self.update_status("Error - Failed to create app", True, False)
        except Exception as e:
            logging.error(f"GUI: Unhandled exception in bot thread: {e}", exc_info=True)
            self.update_status(f"Crashed - Check Logs", True, False)
        finally:
            logging.info("GUI: Bot thread processing finished.")
            if self.bot_event_loop and self.bot_event_loop.is_running():
                try:
                    self.bot_event_loop.stop()
                except Exception as e_loop_stop:
                    logging.error(f"GUI: Error stopping bot event loop: {e_loop_stop}")
            self._reset_ui_to_stopped_state()


    def start_bot_action(self):
        if not self.is_settings_loaded:
             self.update_status("Error: settings.json not loaded. Bot cannot start.", True, False)
             logging.error("GUI: Attempted to start bot, but settings.json is not loaded.")
             return
        if QUESTIONS is None: # QUESTIONS loaded by utils on import, or by main_gui_start
            logging.warning("GUI: questions.json might not be loaded. /apply may fail.")


        if self.bot_thread and self.bot_thread.is_alive():
            logging.info("GUI: Bot is already running or starting.")
            return

        if self.window:
            self.window.evaluate_js('setButtonState("start-button", false)')
            self.window.evaluate_js('setButtonState("stop-button", true)')
        self.update_status("Starting...", is_running=None) # Intermediate state
        logging.info("GUI: Initiating bot start sequence...")

        self.bot_thread = threading.Thread(target=self._run_bot_in_thread, daemon=True)
        self.bot_thread.start()

    def _reset_ui_to_stopped_state(self):
        if self.window:
            self.window.evaluate_js('setButtonState("start-button", true)')
            self.window.evaluate_js('setButtonState("stop-button", false)')

        status_msg = "Stopped" if self.is_settings_loaded else "Error: settings.json not loaded!"
        is_error = not self.is_settings_loaded
        self.update_status(status_msg, is_error=is_error, is_running=False)

        self.bot_application_instance = None

    def stop_bot_action(self):
        if not self.bot_thread or not self.bot_thread.is_alive():
            logging.info("GUI: Bot is not currently running or already stopping.")
            self._reset_ui_to_stopped_state()
            return

        if not self.bot_application_instance or not self.bot_event_loop:
            logging.warning("GUI: Stop called, but bot instance or event loop is missing. Forcing UI reset.")
            self._reset_ui_to_stopped_state()
            return

        self.update_status("Stopping...", is_running=None)
        logging.info("GUI: Initiating bot stop sequence...")

        if self.bot_event_loop.is_running():
            future = asyncio.run_coroutine_threadsafe(stop_bot_async(self.bot_application_instance), self.bot_event_loop)
            try:
                future.result(timeout=15)
                logging.info("GUI: Stop command sent and processed by bot thread.")
            except asyncio.TimeoutError:
                logging.warning("GUI: Timeout waiting for bot stop confirmation.")
            except Exception as e:
                logging.error(f"GUI: Error during run_coroutine_threadsafe for stop: {e}")
        else:
            logging.warning("GUI: Bot event loop not running. Cannot send stop command gracefully.")

    def on_frontend_ready(self):
        """Called by JS when the frontend is loaded and ready."""
        logging.info("GUI: Frontend reported ready.")
        self.update_status(self.initial_status_message, is_error=not self.is_settings_loaded, is_running=False)
        if self.window: # Ensure window exists before evaluate_js
            self.window.evaluate_js(f"setLogLinesConfig({self.current_max_log_lines}, {json.dumps(list(self.log_deque))})")
        self._reset_ui_to_stopped_state() # Ensure correct button states

    def set_max_log_lines_config(self, count: int):
        """Sets the max log lines and updates the deque and frontend."""
        logging.info(f"GUI: Setting max log lines to {count}")
        self.current_max_log_lines = count

        current_logs = list(self.log_deque)
        self.log_deque = deque(maxlen=self.current_max_log_lines)
        for log_item in current_logs[-self.current_max_log_lines:]: # Take last N items up to new max
            self.log_deque.append(log_item)

        if self.window:
            js_safe_current_logs = [html.escape(m) for m in list(self.log_deque)]
            self.window.evaluate_js(f"setLogLinesConfig({self.current_max_log_lines}, {json.dumps(js_safe_current_logs)})")

    def repopulate_logs_to_frontend(self):
        """Sends the current content of log_deque to the frontend."""
        if self.window and self.log_deque:
            js_safe_logs = [html.escape(m) for m in list(self.log_deque)]
            self.window.evaluate_js(f"clearLogs(); addBatchLogMessages({json.dumps(js_safe_logs)})")


    def run(self):
        self.setup_gui_logging()

        self.log_processor_thread = threading.Thread(target=self._process_log_queue_loop, daemon=True)
        self.log_processor_thread.start()

        html_file = get_asset_path("web_ui/gui.html")


        self.window = webview.create_window(
            "Application Bot",
            html_file, # Use the absolute path
            js_api=self.api,
            width=800,
            height=600,
            resizable=True,
            min_size=(600, 400)
        )
        self.window.events.closed += self._trigger_cleanup_on_window_closed
        webview.start(debug=SETTINGS.get("PYWEBVIEW_DEBUG", True) if SETTINGS else True)
        logging.info("GUI: Pywebview main loop has exited. Application should be shutting down.")

    def _trigger_cleanup_on_window_closed(self):
        """Called by pywebview when the window is actually closed."""
        logging.info("GUI: Window 'closed' event received. Initiating cleanup.")
        self.perform_app_cleanup()

    def perform_app_cleanup(self):
        """Performs application cleanup.
           This method is now called when the pywebview window.events.closed event fires.
        """
        logging.info("GUI: Starting application cleanup sequence.")
        self.log_processing_active = False # Signal log processor to stop

        if self.bot_thread and self.bot_thread.is_alive():
            logging.info("GUI: Bot is running, attempting to stop it during cleanup.")
            self.stop_bot_action() # This will message the bot thread to stop.

            self.bot_thread.join(timeout=7) # Increased timeout slightly
            if self.bot_thread.is_alive():
                logging.warning("GUI: Bot thread did not terminate gracefully during cleanup.")
        else:
            logging.info("GUI: Bot thread was not running or already finished at cleanup.")


        if self.log_processor_thread and self.log_processor_thread.is_alive():
            self.log_processor_thread.join(timeout=3) # Increased timeout
            if self.log_processor_thread.is_alive():
                logging.warning("GUI: Log processor thread did not terminate gracefully during cleanup.")
        else:
            logging.info("GUI: Log processor thread was not running or already finished at cleanup.")

        logging.info("GUI: Application cleanup finished.")

def main_gui_start():
    settings_ok = load_settings()
    questions_ok = load_questions() # QUESTIONS global is set here

    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
            datefmt='%H:%M:%S',
            stream=sys.stderr # Default to stderr for initial logs
        )
        logging.getLogger("httpx").setLevel(logging.WARNING) # Keep httpx less verbose
        logging.getLogger("pywebview").setLevel(logging.INFO) # pywebview can be verbose on DEBUG

    if not settings_ok:
        logging.critical("CRITICAL: Failed to load settings.json. GUI might not function correctly.")
    if not questions_ok: # QUESTIONS global might be None
        logging.warning("WARNING: Failed to load questions.json. /apply command might be affected.")

    app_gui = BotGUI()
    app_gui.run()

if __name__ == "__main__":
    main_gui_start()