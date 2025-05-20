# application_bot/main.py
import logging
import sys
import asyncio

from telegram import Update 
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes 
from telegram.request import HTTPXRequest

# MODIFIED IMPORTS
from application_bot import utils
from application_bot.utils import load_settings, load_questions, get_text 
from application_bot.constants import (
    STATE_ASKING_QUESTIONS, STATE_AWAITING_PHOTO,
    STATE_CONFIRM_CANCEL_EXISTING, STATE_CONFIRM_GLOBAL_CANCEL
)
from application_bot.handlers.command_handlers import (
    start_command as ch_start_command,
    help_command as ch_help_command,
    cancel_command_entry_point as ch_cancel_entry_point,
    get_user_lang 
)
from application_bot.handlers.conversation_logic import (
    apply_command_entry as cl_apply_command_entry,
    handle_answer as cl_handle_answer,
    handle_photo as cl_handle_photo,
    handle_confirm_cancel_existing as cl_handle_confirm_cancel_existing,
    handle_confirm_global_cancel as cl_handle_confirm_global_cancel,
    unhandled_message_in_conv as cl_unhandled_message_in_conv,
    conversation_timeout_handler_function as cl_conversation_timeout_handler,
    cleanup_user_application_data
)

logger = logging.getLogger(__name__)

async def global_file_size_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not utils.SETTINGS: return True # MODIFIED

    max_size_mb = utils.SETTINGS.get("MAX_ALLOWED_FILE_SIZE_MB", 10) # MODIFIED
    max_size_bytes = max_size_mb * 1024 * 1024
    message = update.message

    file_to_check = None
    if message:
        if message.document: file_to_check = message.document
        elif message.video: file_to_check = message.video
        elif message.animation: file_to_check = message.animation
        elif message.audio: file_to_check = message.audio
        elif message.voice: file_to_check = message.voice

    if file_to_check and hasattr(file_to_check, 'file_size') and file_to_check.file_size and file_to_check.file_size > max_size_bytes:
        user_id = message.from_user.id if message.from_user else "UnknownUser"
        file_type = "file"
        if message.document: file_type = "document"
        elif message.video: file_type = "video"

        logger.warning(
            f"User {user_id} sent a large unsolicited {file_type} "
            f"({file_to_check.file_size} bytes). Max allowed: {max_size_bytes} bytes. Message will be ignored by this filter."
        )
        return False 
    return True 

def create_bot_application():
    if not utils.SETTINGS or not utils.SETTINGS.get("BOT_TOKEN"): # MODIFIED
        logger.critical("BOT_TOKEN not found in settings. Bot cannot be created.")
        return None
    if utils.QUESTIONS is None: # MODIFIED
        logger.warning("QUESTIONS not loaded. /apply command might fail.")

    connect_timeout = utils.SETTINGS.get("HTTP_CONNECT_TIMEOUT", 10.0) # MODIFIED
    read_timeout = utils.SETTINGS.get("HTTP_READ_TIMEOUT", 30.0) # MODIFIED
    write_timeout = utils.SETTINGS.get("HTTP_WRITE_TIMEOUT", 30.0) # MODIFIED
    pool_timeout = utils.SETTINGS.get("HTTP_POOL_TIMEOUT", 15.0) # MODIFIED
    logger.info(
        f"Configuring HTTPX timeouts: connect={connect_timeout}s, read={read_timeout}s, "
        f"write={write_timeout}s, pool={pool_timeout}s"
    )
    custom_request = HTTPXRequest(
        connect_timeout=connect_timeout, read_timeout=read_timeout,
        write_timeout=write_timeout, pool_timeout=pool_timeout
    )
    app_builder = Application.builder().token(utils.SETTINGS["BOT_TOKEN"]).concurrent_updates(True).request(custom_request) # MODIFIED
    application = app_builder.build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("apply", cl_apply_command_entry)],
        states={
            STATE_ASKING_QUESTIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cl_handle_answer)
            ],
            STATE_AWAITING_PHOTO: [
                MessageHandler(
                    filters.PHOTO | filters.TEXT | filters.Document.DOC | filters.VIDEO | filters.ANIMATION | filters.AUDIO | filters.VOICE | filters.Sticker.ALL, 
                    cl_handle_photo 
                )
            ],
            STATE_CONFIRM_CANCEL_EXISTING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cl_handle_confirm_cancel_existing)
            ],
            STATE_CONFIRM_GLOBAL_CANCEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cl_handle_confirm_global_cancel)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", ch_cancel_entry_point), 
            MessageHandler(filters.COMMAND, cl_unhandled_message_in_conv),
        ],
        conversation_timeout=utils.SETTINGS.get("CONVERSATION_TIMEOUT_SECONDS", 1200), # MODIFIED
        per_user=True,
        per_chat=True,
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", ch_start_command))
    application.add_handler(CommandHandler("help", ch_help_command))

    logger.info("Telegram Bot Application instance created and configured with custom timeouts and file filters.")
    return application

async def run_bot_async(application: Application):
    if not application:
        logger.error("Application instance is None. Cannot run bot.")
        return
    try:
        logger.info("Initializing bot application...")
        if "rate_limits" not in application.bot_data:
            application.bot_data["rate_limits"] = {}
        await application.initialize()
        logger.info("Starting bot updater to poll for updates...")
        await application.updater.start_polling()
        logger.info("Starting bot application processor...")
        await application.start()
        logger.info("Bot is now running and polling for messages.")
        while application.updater and application.updater.running:
            await asyncio.sleep(1)
        logger.info("Bot polling has stopped (updater not running).")
    except Exception as e:
        logger.error(f"Exception during bot operation: {e}", exc_info=True)
    finally:
        logger.info("Bot run_bot_async function is finishing. Ensuring cleanup...")
        if application.running:
            await application.stop()
        if application.updater and application.updater.running:
            await application.updater.stop()

async def stop_bot_async(application: Application):
    if not application:
        logger.warning("Application instance is None. Cannot stop.")
        return
    try:
        logger.info("Attempting to stop bot gracefully...")
        if application.updater and application.updater.running:
            logger.info("Stopping updater...")
            await application.updater.stop()
        else:
            logger.info("Updater not running or not present.")
        if application.running:
            logger.info("Stopping application processor...")
            await application.stop()
        else:
            logger.info("Application processor not running.")
        logger.info("Shutting down application...")
        await application.shutdown()
        logger.info("Bot has been shut down.")
    except Exception as e:
        logger.error(f"Exception during bot stop: {e}", exc_info=True)

def main_cli():
    if not load_settings():
        sys.exit("CRITICAL: Settings not loaded. Exiting CLI.")
    if not load_questions():
        logger.warning("CLI: Questions not loaded. /apply may be affected.")

    if not logging.getLogger().handlers:
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
        )
        logging.getLogger("httpx").setLevel(logging.WARNING)

    logger.info("Starting bot in CLI mode...")
    application = create_bot_application()

    if application:
        logger.info("Running bot with application.run_polling()...")
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(run_bot_async(application))
        except KeyboardInterrupt:
            logger.info("Bot interrupted by user (KeyboardInterrupt). Shutting down...")
            if application: 
                 loop.run_until_complete(stop_bot_async(application))
        finally:
            if loop.is_running():
                loop.stop() 
            pass 
        logger.info("Bot polling stopped (CLI mode).")
    else:
        logger.error("Failed to create bot application. Exiting CLI.")

if __name__ == "__main__":
    main_cli()