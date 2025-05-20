# telegram_application_bot/handlers/conversation_logic.py
import logging
import os
import time
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

# Assuming utils, constants, pdf_generator are accessible
try:
    from application_bot.utils import SETTINGS, QUESTIONS, get_text, get_external_file_path, load_questions
    from application_bot.constants import (
        STATE_ASKING_QUESTIONS, STATE_AWAITING_PHOTO,
        STATE_CONFIRM_CANCEL_EXISTING, STATE_CONFIRM_GLOBAL_CANCEL
    )
    from application_bot.pdf_generator import create_application_pdf
    from application_bot.handlers.command_handlers import get_user_lang
except ImportError:
    from application_bot.utils import SETTINGS, QUESTIONS, get_text, get_external_file_path, load_questions
    from application_bot.constants import (
        STATE_ASKING_QUESTIONS, STATE_AWAITING_PHOTO,
        STATE_CONFIRM_CANCEL_EXISTING, STATE_CONFIRM_GLOBAL_CANCEL
    )
    from application_bot.pdf_generator import create_application_pdf
    from application_bot.handlers.command_handlers import get_user_lang


logger = logging.getLogger(__name__)

# --- Rate Limiting ---
# ... (keep existing rate limiting functions) ...
def check_rate_limit(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    now = time.time()
    limit_seconds = SETTINGS.get("RATE_LIMIT_SECONDS", 600) if SETTINGS else 600
    if "rate_limits" not in context.bot_data:
        context.bot_data["rate_limits"] = {}
    last_submission_time = context.bot_data["rate_limits"].get(user_id, 0)
    return now - last_submission_time < limit_seconds

def update_rate_limit_timestamp(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    if "rate_limits" not in context.bot_data: # Ensure key exists
        context.bot_data["rate_limits"] = {}
    context.bot_data["rate_limits"][user_id] = time.time()

# --- Data Cleanup ---
# ... (keep existing cleanup function) ...
def cleanup_user_application_data(context: ContextTypes.DEFAULT_TYPE):
    temp_photo_paths = context.user_data.pop('application_photo_paths', [])
    temp_photo_folder_name = SETTINGS.get("TEMP_PHOTO_FOLDER", "temp_photos") if SETTINGS else "temp_photos"
    base_path_arg = temp_photo_folder_name if temp_photo_folder_name else "temp_photos"
    temp_photo_base_path = get_external_file_path(base_path_arg)


    for photo_path in temp_photo_paths:
        abs_photo_path = os.path.abspath(photo_path)
        abs_temp_base_path = os.path.abspath(temp_photo_base_path)
        if os.path.commonpath([abs_temp_base_path, abs_photo_path]) == abs_temp_base_path:
            try:
                if os.path.exists(photo_path):
                    os.remove(photo_path)
                    logger.info(f"Cleaned up temp photo: {photo_path}")
            except OSError as e:
                logger.warning(f"Could not remove temp photo {photo_path}: {e}")
        else:
            logger.error(f"Attempted to delete photo outside temp folder: {photo_path} (base: {abs_temp_base_path}). Skipped.")

    keys_to_remove = ['current_question_index', 'current_question_id', 'answers',
                      'is_awaiting_photo', 'current_q_state', 'current_state_for_cancel_confirmation']
    for key in keys_to_remove:
        context.user_data.pop(key, None)

# --- Conversation Entry and State Handlers ---
# ... (apply_command_entry, handle_confirm_cancel_existing, ask_next_question, handle_answer, prompt_for_photo remain largely the same) ...
async def apply_command_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    lang = get_user_lang(context, update)
    context.user_data['current_q_state'] = STATE_ASKING_QUESTIONS

    if not QUESTIONS:
        if not load_questions():
            logger.warning(f"User {user.id} tried /apply, but questions are not loaded and reload failed.")
            await update.message.reply_text(get_text("application_failed", lang) + " (No questions configured)", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        logger.info("Successfully reloaded questions on demand.")


    if 'current_question_index' in context.user_data or context.user_data.get('is_awaiting_photo', False):
        yes_text = get_text("confirm_cancel_yes", lang)
        no_text = get_text("confirm_cancel_no", lang)
        keyboard = [[KeyboardButton(yes_text)], [KeyboardButton(no_text)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(get_text("already_in_application", lang), reply_markup=reply_markup)
        context.user_data['current_q_state'] = STATE_CONFIRM_CANCEL_EXISTING
        return STATE_CONFIRM_CANCEL_EXISTING

    if check_rate_limit(user.id, context):
        last_submission_time = context.bot_data["rate_limits"].get(user.id, 0)
        rate_limit_sec = SETTINGS.get("RATE_LIMIT_SECONDS", 600) if SETTINGS else 600
        wait_time_total_seconds = rate_limit_sec - (time.time() - last_submission_time)
        wait_time_minutes = int(wait_time_total_seconds / 60) + 1
        await update.message.reply_text(get_text("rate_limit_exceeded", lang, wait_time=wait_time_minutes), reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    context.user_data['answers'] = {}
    context.user_data['current_question_index'] = 0
    context.user_data['application_photo_paths'] = []
    context.user_data['is_awaiting_photo'] = False

    await update.message.reply_text(get_text("apply_intro", lang), reply_markup=ReplyKeyboardRemove())
    return await ask_next_question(update, context)

async def handle_confirm_cancel_existing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_response = update.message.text
    lang = get_user_lang(context, update)

    if user_response == get_text("confirm_cancel_yes", lang):
        await update.message.reply_text(get_text("application_cancelled", lang), reply_markup=ReplyKeyboardRemove())
        cleanup_user_application_data(context)
        return await apply_command_entry(update, context)
    elif user_response == get_text("confirm_cancel_no", lang):
        await update.message.reply_text(get_text("continue_current_application", lang), reply_markup=ReplyKeyboardRemove())
        if context.user_data.get('is_awaiting_photo', False):
            context.user_data['current_q_state'] = STATE_AWAITING_PHOTO
            return await prompt_for_photo(update, context)
        else:
            context.user_data['current_q_state'] = STATE_ASKING_QUESTIONS
            return await ask_next_question(update, context, resume=True)
    else:
        yes_text = get_text("confirm_cancel_yes", lang)
        no_text = get_text("confirm_cancel_no", lang)
        keyboard = [[KeyboardButton(yes_text)], [KeyboardButton(no_text)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(get_text("already_in_application", lang), reply_markup=reply_markup)
        context.user_data['current_q_state'] = STATE_CONFIRM_CANCEL_EXISTING
        return STATE_CONFIRM_CANCEL_EXISTING

async def ask_next_question(update: Update, context: ContextTypes.DEFAULT_TYPE, resume: bool = False) -> int:
    current_q_index = context.user_data.get('current_question_index', 0)
    context.user_data['current_q_state'] = STATE_ASKING_QUESTIONS
    lang = get_user_lang(context, update) # Ensure lang is available

    if not QUESTIONS:
        logger.error("ask_next_question: QUESTIONS not loaded!")
        # Use context.bot.send_message for safety if update.message is None (e.g., from callback)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=get_text("application_failed", lang) + " (No questions available)")
        cleanup_user_application_data(context)
        return ConversationHandler.END

    if current_q_index < len(QUESTIONS):
        question_data = QUESTIONS[current_q_index]
        context.user_data['current_question_id'] = question_data['id']
        target_message = update.message or (update.callback_query and update.callback_query.message)
        if target_message:
            await target_message.reply_text(question_data['text'], reply_markup=ReplyKeyboardRemove())
        else: # Fallback if called without a direct message reply context (e.g. after a timeout resume)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=question_data['text'], reply_markup=ReplyKeyboardRemove())
        return STATE_ASKING_QUESTIONS
    else:
        context.user_data['is_awaiting_photo'] = True
        context.user_data['current_q_state'] = STATE_AWAITING_PHOTO
        return await prompt_for_photo(update, context)

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_answer = update.message.text
    question_id = context.user_data.get('current_question_id')
    if question_id:
        context.user_data['answers'][question_id] = user_answer
    context.user_data['current_question_index'] += 1
    return await ask_next_question(update, context)

async def prompt_for_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context, update)
    num_photos_required = SETTINGS.get("APPLICATION_PHOTO_NUMB", 1) if SETTINGS else 1
    collected_photos = len(context.user_data.get('application_photo_paths', []))
    context.user_data['current_q_state'] = STATE_AWAITING_PHOTO

    message_text = ""
    if num_photos_required == 1:
        message_text = get_text("ask_photo_single", lang)
    elif num_photos_required > 1:
        if collected_photos == 0:
            message_text = get_text("ask_photo_multiple_initial", lang, count=num_photos_required)
        else:
            message_text = get_text("ask_photo_multiple", lang, count=num_photos_required, collected=collected_photos, total=num_photos_required)
    else: # 0 photos required
        logger.info(f"User {update.effective_user.id}: 0 photos required, skipping photo stage.")
        return await finalize_application(update, context)

    target_message = update.message or (update.callback_query and update.callback_query.message)
    if target_message:
        await target_message.reply_text(message_text, reply_markup=ReplyKeyboardRemove())
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=message_text, reply_markup=ReplyKeyboardRemove())
    return STATE_AWAITING_PHOTO

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    lang = get_user_lang(context, update)
    num_photos_required = SETTINGS.get("APPLICATION_PHOTO_NUMB", 1) if SETTINGS else 1
    max_file_size_mb = SETTINGS.get("MAX_ALLOWED_FILE_SIZE_MB", 10) if SETTINGS else 10
    max_file_size_bytes = max_file_size_mb * 1024 * 1024
    context.user_data['current_q_state'] = STATE_AWAITING_PHOTO


    # --- START FILE TYPE AND SIZE CHECK ---
    if not update.message or not update.message.photo:
        # If it's not a photo, but some other file type or text
        if update.message and (update.message.document or update.message.video or update.message.animation or update.message.audio or update.message.voice):
            file_size = 0
            if update.message.document: file_size = update.message.document.file_size
            elif update.message.video: file_size = update.message.video.file_size
            elif update.message.animation: file_size = update.message.animation.file_size
            # Photos don't usually have file_size directly on the top-level message.photo object in the same way.
            # We check photo size later if it *is* a photo object.

            if file_size and file_size > max_file_size_bytes:
                await update.message.reply_text(get_text("file_too_large_or_unsupported_type", lang, max_size_mb=max_file_size_mb))
                logger.warning(f"User {user.id} sent a non-photo file that is too large: {file_size} bytes.")
                return STATE_AWAITING_PHOTO # Stay in this state, ask again

            await update.message.reply_text(get_text("please_send_photo_not_other_file", lang))
            logger.warning(f"User {user.id} sent a non-photo file type when photo was expected.")
            return STATE_AWAITING_PHOTO # Stay in this state, ask again

        elif update.message and update.message.text: # User sent text instead of photo
            await update.message.reply_text(get_text("please_send_photo_not_other_file", lang))
            logger.warning(f"User {user.id} sent text when photo was expected.")
            return STATE_AWAITING_PHOTO

        # Fallback for other unexpected message types or if message is None
        await context.bot.send_message(chat_id=update.effective_chat.id, text=get_text("not_a_photo", lang))
        return await prompt_for_photo(update, context) # Re-prompt
    # --- END FILE TYPE AND SIZE CHECK ---

    # At this point, we know update.message.photo exists.
    # Now check photo size (Telegram sends multiple resolutions)
    largest_photo = update.message.photo[-1] # Smallest to largest
    if largest_photo.file_size and largest_photo.file_size > max_file_size_bytes:
        await update.message.reply_text(get_text("file_too_large_or_unsupported_type", lang, max_size_mb=max_file_size_mb))
        logger.warning(f"User {user.id} sent a photo that is too large: {largest_photo.file_size} bytes.")
        return STATE_AWAITING_PHOTO # Stay in this state, ask again

    temp_photo_folder_name = SETTINGS.get("TEMP_PHOTO_FOLDER", "temp_photos") if SETTINGS else "temp_photos"
    temp_photo_dir = get_external_file_path(temp_photo_folder_name)
    os.makedirs(temp_photo_dir, exist_ok=True)

    current_photo_paths = context.user_data.get('application_photo_paths', [])

    if len(current_photo_paths) < num_photos_required:
        try:
            photo_file = await largest_photo.get_file() # This is where actual download might occur
            photo_filename = f"{user.id}_{int(time.time())}_{len(current_photo_paths)}.jpg"
            local_photo_path = os.path.join(temp_photo_dir, photo_filename)
            await photo_file.download_to_drive(local_photo_path)
            current_photo_paths.append(local_photo_path)
            logger.info(f"User {user.id} sent photo, saved to {local_photo_path} (Size: {largest_photo.width}x{largest_photo.height}, FileSize: {largest_photo.file_size or 'N/A'})")
        except Exception as e:
            logger.error(f"Error downloading photo for user {user.id}: {e}")
            await update.message.reply_text(get_text("application_failed", lang) + " (Photo error)")
            # Don't end conversation, just re-prompt or indicate error
            return STATE_AWAITING_PHOTO

    context.user_data['application_photo_paths'] = current_photo_paths

    if len(current_photo_paths) < num_photos_required:
        remaining_needed = num_photos_required - len(current_photo_paths)
        await update.message.reply_text(get_text("photo_received_collecting_more", lang, remaining_photos=remaining_needed))
        return STATE_AWAITING_PHOTO
    else:
        await update.message.reply_text(get_text("all_photos_received_processing", lang), reply_markup=ReplyKeyboardRemove())
        context.user_data['is_awaiting_photo'] = False
        return await finalize_application(update, context)


async def finalize_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    lang = get_user_lang(context, update)

    try:
        pdf_filepath = create_application_pdf(
            user_id=user.id,
            username=user.username,
            answers=context.user_data.get('answers', {}),
            photo_file_paths=context.user_data.get('application_photo_paths', []),
            user_lang=lang
        )

        if not pdf_filepath:
            logger.error(f"PDF generation failed for user {user.id}.")
            await update.message.reply_text(get_text("application_failed", lang) + " (PDF Error)")
            # cleanup_user_application_data is called in finally
            return ConversationHandler.END

        if SETTINGS and SETTINGS.get("SEND_PDF_TO_ADMINS", True):
            admin_ids_str = SETTINGS.get("ADMIN_USER_IDS", "")
            admin_ids = [int(admin_id.strip()) for admin_id in admin_ids_str.split(',') if admin_id.strip().isdigit()]

            if not admin_ids:
                logger.warning(f"No valid ADMIN_USER_IDS configured to send PDF for user {user.id}.")
            else:
                admin_notification_text = get_text("admin_notification", lang,
                                                   username=user.username or "N/A",
                                                   user_id=user.id,
                                                   submission_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                for admin_id in admin_ids:
                    try:
                        with open(pdf_filepath, 'rb') as pdf_file_obj:
                            await context.bot.send_document(chat_id=admin_id, document=pdf_file_obj, caption=admin_notification_text)
                        logger.info(f"Sent PDF to admin {admin_id} for user {user.id}")
                    except Exception as e:
                        logger.error(f"Failed to send PDF to admin {admin_id} for user {user.id}: {e}")
        else:
            logger.info(f"SEND_PDF_TO_ADMINS is false. PDF for user {user.id} saved at {pdf_filepath} but not sent.")

        await update.message.reply_text(get_text("application_submitted", lang))
        update_rate_limit_timestamp(user.id, context)

    except Exception as e:
        logger.error(f"Critical error during finalize_application for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(get_text("application_failed", lang))
    finally:
        cleanup_user_application_data(context)

    return ConversationHandler.END

# ... (cancel_application_flow, handle_confirm_global_cancel, conversation_timeout_handler_function remain the same) ...
async def cancel_application_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context, update)

    if ('current_question_index' in context.user_data or
        context.user_data.get('is_awaiting_photo', False) or
        context.user_data.get('current_state_for_cancel_confirmation') is not None):

        yes_text = get_text("confirm_action_yes", lang)
        no_text = get_text("confirm_action_no", lang)
        keyboard = [[KeyboardButton(yes_text)], [KeyboardButton(no_text)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

        context.user_data['current_state_for_cancel_confirmation'] = context.user_data.get('current_q_state')

        await update.message.reply_text(get_text("cancel_prompt", lang), reply_markup=reply_markup)
        return STATE_CONFIRM_GLOBAL_CANCEL
    else:
        await update.message.reply_text(get_text("no_active_application_to_cancel", lang), reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

async def handle_confirm_global_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_response = update.message.text
    lang = get_user_lang(context, update)
    stored_previous_state = context.user_data.pop('current_state_for_cancel_confirmation', None)

    if user_response == get_text("confirm_action_yes", lang):
        cleanup_user_application_data(context)
        await update.message.reply_text(get_text("application_cancelled", lang), reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    elif user_response == get_text("confirm_action_no", lang):
        await update.message.reply_text(get_text("continue_current_application", lang), reply_markup=ReplyKeyboardRemove())
        if stored_previous_state == STATE_AWAITING_PHOTO:
            return await prompt_for_photo(update, context)
        elif stored_previous_state == STATE_ASKING_QUESTIONS:
            return await ask_next_question(update, context, resume=True)
        else: # Fallback if state was lost or invalid
            if context.user_data.get('is_awaiting_photo', False):
                 return await prompt_for_photo(update, context)
            elif 'current_question_index' in context.user_data :
                 return await ask_next_question(update, context, resume=True)
            # If no clear state to return to, end the conversation or send a generic message.
            # For now, let's assume if we can't determine, we should end.
            logger.warning(f"Global cancel 'No': Could not determine state to return to. Ending conversation for user {update.effective_user.id}")
            await update.message.reply_text(get_text("generic_error_prompt", lang), reply_markup=ReplyKeyboardRemove()) # Or a more specific message
            cleanup_user_application_data(context)
            return ConversationHandler.END
    else: # Invalid response to yes/no question
        yes_text = get_text("confirm_action_yes", lang)
        no_text = get_text("confirm_action_no", lang)
        keyboard = [[KeyboardButton(yes_text)], [KeyboardButton(no_text)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        context.user_data['current_state_for_cancel_confirmation'] = stored_previous_state # Restore popped state
        await update.message.reply_text(get_text("cancel_prompt", lang), reply_markup=reply_markup) # Re-ask
        return STATE_CONFIRM_GLOBAL_CANCEL

async def conversation_timeout_handler_function(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = "UnknownUser"
    chat_id = None

    if hasattr(context, '_user_id') and context._user_id: user_id = context._user_id
    if hasattr(context, '_chat_id') and context._chat_id: chat_id = context._chat_id
    
    lang = context.user_data.get("user_lang", SETTINGS.get("DEFAULT_LANG", "en") if SETTINGS else "en")
    if isinstance(update, Update):
        lang = get_user_lang(context, update)
        if not chat_id and update.effective_chat: chat_id = update.effective_chat.id
        if user_id == "UnknownUser" and update.effective_user: user_id = update.effective_user.id
    
    logger.info(f"Conversation timed out for user {user_id} in chat {chat_id}.")

    if chat_id:
        try:
            await context.bot.send_message(chat_id=chat_id, text=get_text("timeout_message", lang), reply_markup=ReplyKeyboardRemove())
        except Exception as e:
            logger.error(f"Error sending timeout message to {chat_id}: {e}")
            
    cleanup_user_application_data(context)
    return ConversationHandler.END

async def unhandled_message_in_conv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles messages that are not an answer, not a photo when expected, or not a command."""
    lang = get_user_lang(context, update)
    current_conv_state = context.user_data.get('current_q_state')
    user_message_text = update.message.text if update.message and update.message.text else "<non-text_message>"
    logger.warning(f"User {update.effective_user.id} sent unhandled message: '{user_message_text}' in state {current_conv_state}")

    if current_conv_state == STATE_AWAITING_PHOTO:
        # If user sends anything other than a photo (or a command, handled by fallback)
        await update.message.reply_text(get_text("please_send_photo_not_other_file", lang), reply_markup=ReplyKeyboardRemove())
        return STATE_AWAITING_PHOTO # Stay in photo state and re-prompt implicitly via filter in main
    elif current_conv_state == STATE_ASKING_QUESTIONS:
        # User sent something unexpected when an answer was expected (e.g., a sticker, voice message)
        # The `MessageHandler(filters.TEXT & ~filters.COMMAND, cl_handle_answer)` should catch text.
        # This `unhandled_message_in_conv` would catch other types if the filters are set up broadly.
        await update.message.reply_text(get_text("generic_error_prompt", lang), reply_markup=ReplyKeyboardRemove()) # Or a more specific "Please provide a text answer"
        return await ask_next_question(update, context, resume=True) # Re-ask current question
    elif current_conv_state == STATE_CONFIRM_CANCEL_EXISTING:
        yes_text = get_text("confirm_cancel_yes", lang)
        no_text = get_text("confirm_cancel_no", lang)
        keyboard = [[KeyboardButton(yes_text)], [KeyboardButton(no_text)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(get_text("already_in_application", lang), reply_markup=reply_markup)
        return STATE_CONFIRM_CANCEL_EXISTING
    elif current_conv_state == STATE_CONFIRM_GLOBAL_CANCEL:
        yes_text = get_text("confirm_action_yes", lang)
        no_text = get_text("confirm_action_no", lang)
        keyboard = [[KeyboardButton(yes_text)], [KeyboardButton(no_text)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(get_text("cancel_prompt", lang), reply_markup=reply_markup)
        return STATE_CONFIRM_GLOBAL_CANCEL
    
    # Fallback if state is unknown or doesn't require specific re-prompt
    await update.message.reply_text(get_text("generic_error_prompt", lang), reply_markup=ReplyKeyboardRemove())
    # Consider ending conversation if state is truly unrecoverable
    # cleanup_user_application_data(context)
    # return ConversationHandler.END
    # For now, let's assume we try to keep the conversation alive if possible by re-prompting.
    # If it's a command, the CommandHandler fallback in ConversationHandler should take precedence.
    # If it's truly unhandled, the conversation might end or loop here.
    # This needs to align with the filters in main.py's ConversationHandler.
    logger.error(f"Unhandled message in conv reached a generic fallback for user {update.effective_user.id}. State: {current_conv_state}")
    return current_conv_state if current_conv_state else ConversationHandler.END # Try to stay or end