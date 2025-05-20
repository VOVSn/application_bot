# application_bot/main.py
import logging
import sys
import asyncio

from telegram import Update # Ensure Update is imported
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes # Add ContextTypes
from telegram.request import HTTPXRequest

from application_bot.utils import SETTINGS, QUESTIONS, load_settings, load_questions, get_text # Added get_text for filter message
from application_bot.constants import (
    STATE_ASKING_QUESTIONS, STATE_AWAITING_PHOTO,
    STATE_CONFIRM_CANCEL_EXISTING, STATE_CONFIRM_GLOBAL_CANCEL
)
from application_bot.handlers.command_handlers import (
    start_command as ch_start_command,
    help_command as ch_help_command,
    cancel_command_entry_point as ch_cancel_entry_point,
    get_user_lang # Added get_user_lang for filter message
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

# --- Global File Size Filter (for messages outside specific states if needed) ---
# This filter can be applied to global handlers if you want to reject large files
# even before they enter a conversation or match a command.
async def global_file_size_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not SETTINGS: return True # Allow if settings not loaded (should not happen)

    max_size_mb = SETTINGS.get("MAX_ALLOWED_FILE_SIZE_MB", 10)
    max_size_bytes = max_size_mb * 1024 * 1024
    message = update.message

    file_to_check = None
    if message:
        if message.document: file_to_check = message.document
        elif message.video: file_to_check = message.video
        elif message.animation: file_to_check = message.animation
        elif message.audio: file_to_check = message.audio
        elif message.voice: file_to_check = message.voice
        # For photos, the conversation handler's 'handle_photo' does a more detailed check.
        # This global filter is more for other unsolicited large files.

    if file_to_check and hasattr(file_to_check, 'file_size') and file_to_check.file_size and file_to_check.file_size > max_size_bytes:
        user_id = message.from_user.id if message.from_user else "UnknownUser"
        file_type = "file"
        if message.document: file_type = "document"
        elif message.video: file_type = "video"
        # ... and so on for other types

        logger.warning(
            f"User {user_id} sent a large unsolicited {file_type} "
            f"({file_to_check.file_size} bytes). Max allowed: {max_size_bytes} bytes. Message will be ignored by this filter."
        )
        # Optionally, send a message. Be careful with sending messages in filters that might run often.
        # lang = get_user_lang(context, update)
        # try:
        #     await message.reply_text(get_text("file_too_large_or_unsupported_type", lang, max_size_mb=max_size_mb))
        # except Exception as e:
        #     logger.error(f"Error replying to user about large file in global filter: {e}")
        return False # Filter out this update for handlers using this filter
    return True # Allow other messages

# --- Bot Application Setup ---
def create_bot_application():
    if not SETTINGS or not SETTINGS.get("BOT_TOKEN"):
        logger.critical("BOT_TOKEN not found in settings. Bot cannot be created.")
        return None
    if QUESTIONS is None:
        logger.warning("QUESTIONS not loaded. /apply command might fail.")

    connect_timeout = SETTINGS.get("HTTP_CONNECT_TIMEOUT", 10.0)
    read_timeout = SETTINGS.get("HTTP_READ_TIMEOUT", 30.0)
    write_timeout = SETTINGS.get("HTTP_WRITE_TIMEOUT", 30.0)
    pool_timeout = SETTINGS.get("HTTP_POOL_TIMEOUT", 15.0)
    logger.info(
        f"Configuring HTTPX timeouts: connect={connect_timeout}s, read={read_timeout}s, "
        f"write={write_timeout}s, pool={pool_timeout}s"
    )
    custom_request = HTTPXRequest(
        connect_timeout=connect_timeout, read_timeout=read_timeout,
        write_timeout=write_timeout, pool_timeout=pool_timeout
    )
    app_builder = Application.builder().token(SETTINGS["BOT_TOKEN"]).concurrent_updates(True).request(custom_request)
    application = app_builder.build()

    # Conversation Handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("apply", cl_apply_command_entry)],
        states={
            STATE_ASKING_QUESTIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cl_handle_answer)
            ],
            STATE_AWAITING_PHOTO: [
                # This handler will now be called for photos, text, documents, videos etc.
                # cl_handle_photo itself will do the specific filtering for photos vs other types.
                MessageHandler(
                    filters.PHOTO | filters.TEXT | filters.Document.DOC | filters.VIDEO | filters.ANIMATION | filters.AUDIO | filters.VOICE | filters.Sticker.ALL, # Catch more types
                    cl_handle_photo # cl_handle_photo will reject non-photos or oversized photos
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
            CommandHandler("cancel", ch_cancel_entry_point), # Global cancel command
            # Handles any other command sent during the conversation
            MessageHandler(filters.COMMAND, cl_unhandled_message_in_conv),
            # Handles any other non-command, non-photo, non-text (if STATE_AWAITING_PHOTO is too broad)
            # This one is tricky because STATE_AWAITING_PHOTO now catches many types.
            # We rely on cl_handle_photo and cl_unhandled_message_in_conv to manage state.
            # If cl_handle_photo doesn't want a message, it returns STATE_AWAITING_PHOTO.
            # If a message type is not covered by STATE_AWAITING_PHOTO's filter,
            # and not a command, it might fall through here IF it's not already handled by a state.
            # Given STATE_AWAITING_PHOTO is broad, this fallback is less likely to be hit for non-commands.
            # MessageHandler(filters.ALL & ~filters.COMMAND, cl_unhandled_message_in_conv) # This might be too broad now
        ],
        conversation_timeout=SETTINGS.get("CONVERSATION_TIMEOUT_SECONDS", 1200),
        per_user=True,
        per_chat=True,
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", ch_start_command))
    application.add_handler(CommandHandler("help", ch_help_command))
    # Note: "cancel" is also a fallback in conv_handler, so it works both globally and within conversation.

    # --- Optional: Global handler for unsolicited large files ---
    # This handler would run for messages NOT caught by the conversation or other specific command handlers.
    # async def handle_globally_rejected_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #     if update.message:
    #         lang = get_user_lang(context, update)
    #         max_size_mb = SETTINGS.get("MAX_ALLOWED_FILE_SIZE_MB", 10)
    #         await update.message.reply_text(get_text("file_too_large_or_unsupported_type", lang, max_size_mb=max_size_mb))
    #
    # # This filter would be applied with a low priority (high group number)
    # # It uses the global_file_size_filter to decide if it should run
    # application.add_handler(
    #     MessageHandler(
    #         (filters.DOCUMENT | filters.VIDEO | filters.ANIMATION | filters.AUDIO | filters.VOICE) & filters.UpdateType(global_file_size_filter, inverted=True),
    #         handle_globally_rejected_file
    #     ), group=5 # Make sure it runs after commands and conversations
    # )

    logger.info("Telegram Bot Application instance created and configured with custom timeouts and file filters.")
    return application

# ... (run_bot_async, stop_bot_async, main_cli remain the same) ...
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
            # application.run_polling() # This is blocking and handles its own loop
            # For consistency with GUI, let's use run_bot_async
            loop.run_until_complete(run_bot_async(application))
        except KeyboardInterrupt:
            logger.info("Bot interrupted by user (KeyboardInterrupt). Shutting down...")
            if application: # Ensure application exists before trying to stop
                 loop.run_until_complete(stop_bot_async(application))
        finally:
            # The loop might be closed by run_until_complete if it finishes,
            # or if stop_bot_async does loop.stop()
            # Adding a check before closing
            if loop.is_running():
                loop.stop() # Stop the loop if it's still running
            # Attempt to close only if not already closed.
            # This can be tricky; PTB's shutdown might handle loop closing.
            # if not loop.is_closed():
            #    loop.close()
            # Let's rely on PTB's shutdown to manage the loop if run_polling was used,
            # or allow our explicit stop to handle it if run_bot_async was used.
            pass # Loop management can be complex; primary goal is graceful bot shutdown.
        logger.info("Bot polling stopped (CLI mode).")
    else:
        logger.error("Failed to create bot application. Exiting CLI.")

if __name__ == "__main__":
    main_cli()