# telegram_application_bot/handlers/conversation_logic.py
import logging
import os
import time
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

# MODIFIED IMPORTS:
from application_bot import utils
from application_bot.utils import get_text, get_external_file_path, load_questions
from application_bot.constants import (
    STATE_ASKING_QUESTIONS, STATE_AWAITING_PHOTO,
    STATE_CONFIRM_CANCEL_EXISTING, STATE_CONFIRM_GLOBAL_CANCEL
)
from application_bot.pdf_generator import create_application_pdf
from application_bot.handlers.command_handlers import get_user_lang


logger = logging.getLogger(__name__)

def check_rate_limit(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    now = time.time()
    limit_seconds = utils.SETTINGS.get("RATE_LIMIT_SECONDS", 600) if utils.SETTINGS else 600 # MODIFIED
    if "rate_limits" not in context.bot_data:
        context.bot_data["rate_limits"] = {}
    last_submission_time = context.bot_data["rate_limits"].get(user_id, 0)
    return now - last_submission_time < limit_seconds

def update_rate_limit_timestamp(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    if "rate_limits" not in context.bot_data: 
        context.bot_data["rate_limits"] = {}
    context.bot_data["rate_limits"][user_id] = time.time()

def cleanup_user_application_data(context: ContextTypes.DEFAULT_TYPE):
    temp_photo_paths = context.user_data.pop('application_photo_paths', [])
    temp_photo_folder_name = utils.SETTINGS.get("TEMP_PHOTO_FOLDER", "temp_photos") if utils.SETTINGS else "temp_photos" # MODIFIED
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

async def apply_command_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    lang = get_user_lang(context, update)
    context.user_data['current_q_state'] = STATE_ASKING_QUESTIONS

    if not utils.QUESTIONS: # MODIFIED
        if not load_questions(): # This function updates utils.QUESTIONS internally
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
        rate_limit_sec = utils.SETTINGS.get("RATE_LIMIT_SECONDS", 600) if utils.SETTINGS else 600 # MODIFIED
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
    lang = get_user_lang(context, update) 

    if not utils.QUESTIONS: # MODIFIED
        logger.error("ask_next_question: QUESTIONS not loaded!")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=get_text("application_failed", lang) + " (No questions available)")
        cleanup_user_application_data(context)
        return ConversationHandler.END

    if current_q_index < len(utils.QUESTIONS): # MODIFIED
        question_data = utils.QUESTIONS[current_q_index] # MODIFIED
        context.user_data['current_question_id'] = question_data['id']
        target_message = update.message or (update.callback_query and update.callback_query.message)
        if target_message:
            await target_message.reply_text(question_data['text'], reply_markup=ReplyKeyboardRemove())
        else: 
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
    num_photos_required = utils.SETTINGS.get("APPLICATION_PHOTO_NUMB", 1) if utils.SETTINGS else 1 # MODIFIED
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
    else: 
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
    num_photos_required = utils.SETTINGS.get("APPLICATION_PHOTO_NUMB", 1) if utils.SETTINGS else 1 # MODIFIED
    max_file_size_mb = utils.SETTINGS.get("MAX_ALLOWED_FILE_SIZE_MB", 10) if utils.SETTINGS else 10 # MODIFIED
    max_file_size_bytes = max_file_size_mb * 1024 * 1024
    context.user_data['current_q_state'] = STATE_AWAITING_PHOTO


    if not update.message or not update.message.photo:
        if update.message and (update.message.document or update.message.video or update.message.animation or update.message.audio or update.message.voice):
            file_size = 0
            if update.message.document: file_size = update.message.document.file_size
            elif update.message.video: file_size = update.message.video.file_size
            elif update.message.animation: file_size = update.message.animation.file_size
            
            if file_size and file_size > max_file_size_bytes:
                await update.message.reply_text(get_text("file_too_large_or_unsupported_type", lang, max_size_mb=max_file_size_mb))
                logger.warning(f"User {user.id} sent a non-photo file that is too large: {file_size} bytes.")
                return STATE_AWAITING_PHOTO 

            await update.message.reply_text(get_text("please_send_photo_not_other_file", lang))
            logger.warning(f"User {user.id} sent a non-photo file type when photo was expected.")
            return STATE_AWAITING_PHOTO 

        elif update.message and update.message.text: 
            await update.message.reply_text(get_text("please_send_photo_not_other_file", lang))
            logger.warning(f"User {user.id} sent text when photo was expected.")
            return STATE_AWAITING_PHOTO

        await context.bot.send_message(chat_id=update.effective_chat.id, text=get_text("not_a_photo", lang))
        return await prompt_for_photo(update, context) 
    
    largest_photo = update.message.photo[-1] 
    if largest_photo.file_size and largest_photo.file_size > max_file_size_bytes:
        await update.message.reply_text(get_text("file_too_large_or_unsupported_type", lang, max_size_mb=max_file_size_mb))
        logger.warning(f"User {user.id} sent a photo that is too large: {largest_photo.file_size} bytes.")
        return STATE_AWAITING_PHOTO 

    temp_photo_folder_name = utils.SETTINGS.get("TEMP_PHOTO_FOLDER", "temp_photos") if utils.SETTINGS else "temp_photos" # MODIFIED
    temp_photo_dir = get_external_file_path(temp_photo_folder_name)
    os.makedirs(temp_photo_dir, exist_ok=True)

    current_photo_paths = context.user_data.get('application_photo_paths', [])

    if len(current_photo_paths) < num_photos_required:
        try:
            photo_file = await largest_photo.get_file() 
            photo_filename = f"{user.id}_{int(time.time())}_{len(current_photo_paths)}.jpg"
            local_photo_path = os.path.join(temp_photo_dir, photo_filename)
            await photo_file.download_to_drive(local_photo_path)
            current_photo_paths.append(local_photo_path)
            logger.info(f"User {user.id} sent photo, saved to {local_photo_path} (Size: {largest_photo.width}x{largest_photo.height}, FileSize: {largest_photo.file_size or 'N/A'})")
        except Exception as e:
            logger.error(f"Error downloading photo for user {user.id}: {e}")
            await update.message.reply_text(get_text("application_failed", lang) + " (Photo error)")
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
            return ConversationHandler.END

        if utils.SETTINGS and utils.SETTINGS.get("SEND_PDF_TO_ADMINS", True): # MODIFIED
            admin_ids_str = utils.SETTINGS.get("ADMIN_USER_IDS", "") # MODIFIED
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
        else: 
            if context.user_data.get('is_awaiting_photo', False):
                 return await prompt_for_photo(update, context)
            elif 'current_question_index' in context.user_data :
                 return await ask_next_question(update, context, resume=True)
            logger.warning(f"Global cancel 'No': Could not determine state to return to. Ending conversation for user {update.effective_user.id}")
            await update.message.reply_text(get_text("generic_error_prompt", lang), reply_markup=ReplyKeyboardRemove()) 
            cleanup_user_application_data(context)
            return ConversationHandler.END
    else: 
        yes_text = get_text("confirm_action_yes", lang)
        no_text = get_text("confirm_action_no", lang)
        keyboard = [[KeyboardButton(yes_text)], [KeyboardButton(no_text)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        context.user_data['current_state_for_cancel_confirmation'] = stored_previous_state 
        await update.message.reply_text(get_text("cancel_prompt", lang), reply_markup=reply_markup) 
        return STATE_CONFIRM_GLOBAL_CANCEL

async def conversation_timeout_handler_function(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = "UnknownUser"
    chat_id = None

    if hasattr(context, '_user_id') and context._user_id: user_id = context._user_id
    if hasattr(context, '_chat_id') and context._chat_id: chat_id = context._chat_id
    
    lang = context.user_data.get("user_lang", utils.SETTINGS.get("DEFAULT_LANG", "en") if utils.SETTINGS else "en") # MODIFIED
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
    lang = get_user_lang(context, update)
    current_conv_state = context.user_data.get('current_q_state')
    user_message_text = update.message.text if update.message and update.message.text else "<non-text_message>"
    logger.warning(f"User {update.effective_user.id} sent unhandled message: '{user_message_text}' in state {current_conv_state}")

    if current_conv_state == STATE_AWAITING_PHOTO:
        await update.message.reply_text(get_text("please_send_photo_not_other_file", lang), reply_markup=ReplyKeyboardRemove())
        return STATE_AWAITING_PHOTO 
    elif current_conv_state == STATE_ASKING_QUESTIONS:
        await update.message.reply_text(get_text("generic_error_prompt", lang), reply_markup=ReplyKeyboardRemove()) 
        return await ask_next_question(update, context, resume=True) 
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
    
    await update.message.reply_text(get_text("generic_error_prompt", lang), reply_markup=ReplyKeyboardRemove())
    logger.error(f"Unhandled message in conv reached a generic fallback for user {update.effective_user.id}. State: {current_conv_state}")
    return current_conv_state if current_conv_state else ConversationHandler.END 