# telegram_application_bot/handlers/command_handlers.py
import logging
from telegram import Update, ReplyKeyboardRemove, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

try:
    from application_bot.utils import get_text, SETTINGS
    from application_bot.constants import (
        STATE_CONFIRM_GLOBAL_CANCEL,
        STATE_ASKING_QUESTIONS,
        STATE_AWAITING_PHOTO
    )
except ImportError:
    from application_bot.utils import get_text, SETTINGS
    from application_bot.constants import (
        STATE_CONFIRM_GLOBAL_CANCEL,
        STATE_ASKING_QUESTIONS,
        STATE_AWAITING_PHOTO
    )

logger = logging.getLogger(__name__)

def get_user_lang(context: ContextTypes.DEFAULT_TYPE, update: Update = None) -> str:
    user_id = update.effective_user.id if update and update.effective_user else "UnknownUser"

    # 1. Priority: Already set in user_data (e.g., by a future /setlang command)
    if "user_lang" in context.user_data:
        # logger.debug(f"User {user_id}: Using cached language '{context.user_data['user_lang']}' from user_data.")
        return context.user_data["user_lang"]

    determined_lang = None
    # Default to True if the setting is missing, to prioritize DEFAULT_LANG
    override_user_lang = SETTINGS.get("OVERRIDE_USER_LANG", True) if SETTINGS else True

    # 2. Try to use Telegram's language code IF NOT overriding
    if not override_user_lang:
        if update and update.effective_user and update.effective_user.language_code:
            user_tg_lang_full = update.effective_user.language_code
            user_tg_lang_short = user_tg_lang_full.split('-')[0]
            logger.debug(f"User {user_id}: OVERRIDE_USER_LANG is false. Telegram language_code: '{user_tg_lang_full}' (short: '{user_tg_lang_short}')")

            if SETTINGS and "LANGUAGES" in SETTINGS:
                if user_tg_lang_short in SETTINGS["LANGUAGES"]:
                    determined_lang = user_tg_lang_short
                    logger.info(f"User {user_id}: Detected language '{determined_lang}' from Telegram client, matching available languages.")
                else:
                    logger.debug(f"User {user_id}: Telegram language '{user_tg_lang_short}' not in available bot languages: {list(SETTINGS['LANGUAGES'].keys())}.")
            else:
                logger.warning(f"User {user_id}: SETTINGS or SETTINGS['LANGUAGES'] not available for Telegram language detection.")
        elif update is None or update.effective_user is None or not update.effective_user.language_code:
             logger.debug(f"User {user_id}: OVERRIDE_USER_LANG is false, but no Telegram client language info available in update.")
    else: # override_user_lang is true
        logger.info(f"User {user_id}: OVERRIDE_USER_LANG is true. Will use DEFAULT_LANG from settings.")

    # 3. Use DEFAULT_LANG from settings if no language determined yet OR if overriding
    if not determined_lang:
        source_info = "as primary due to OVERRIDE_USER_LANG" if override_user_lang else "as fallback"
        if SETTINGS and "DEFAULT_LANG" in SETTINGS:
            default_lang_from_settings = SETTINGS["DEFAULT_LANG"]
            # Ensure the DEFAULT_LANG itself is valid and exists in LANGUAGES
            if SETTINGS.get("LANGUAGES", {}).get(default_lang_from_settings):
                determined_lang = default_lang_from_settings
                logger.info(f"User {user_id}: Using DEFAULT_LANG '{determined_lang}' from settings {source_info}.")
            else:
                logger.warning(f"User {user_id}: DEFAULT_LANG '{default_lang_from_settings}' from settings is not a configured language in LANGUAGES. Falling back to 'en'.")
                determined_lang = "en" # Hard fallback if default_lang is misconfigured
        else:
            logger.warning(f"User {user_id}: SETTINGS or SETTINGS['DEFAULT_LANG'] not available. Falling back to 'en'.")
            determined_lang = "en" # Ultimate fallback

    # Cache the determined language for this session
    context.user_data["user_lang"] = determined_lang
    logger.debug(f"User {user_id}: Cached language '{determined_lang}' to user_data.")
    return determined_lang

# ... rest of command_handlers.py, including start_command, help_command, etc.
# Ensure they all call get_user_lang(context, update) to get the language.
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = get_user_lang(context, update) # This will now respect OVERRIDE_USER_LANG
    logger.info(f"User {user.id} ({user.username}) started bot. Effective language for session: {lang}")
    await update.message.reply_text(get_text("start_message", lang))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_user_lang(context, update)
    await update.message.reply_text(get_text("help_message", lang), reply_markup=ReplyKeyboardRemove())

async def cancel_command_entry_point(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(context, update)

    if ('current_question_index' in context.user_data or
        context.user_data.get('is_awaiting_photo', False) or
        context.user_data.get('current_state_for_cancel_confirmation') is not None):

        yes_text = get_text("confirm_action_yes", lang)
        no_text = get_text("confirm_action_no", lang)
        keyboard = [[KeyboardButton(yes_text)], [KeyboardButton(no_text)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

        current_q_state = context.user_data.get('current_q_state')
        if current_q_state == STATE_ASKING_QUESTIONS:
             context.user_data['current_state_for_cancel_confirmation'] = STATE_ASKING_QUESTIONS
        elif current_q_state == STATE_AWAITING_PHOTO:
             context.user_data['current_state_for_cancel_confirmation'] = STATE_AWAITING_PHOTO
        elif 'current_question_index' in context.user_data and not context.user_data.get('is_awaiting_photo', False):
             context.user_data['current_state_for_cancel_confirmation'] = STATE_ASKING_QUESTIONS
        elif context.user_data.get('is_awaiting_photo', False):
             context.user_data['current_state_for_cancel_confirmation'] = STATE_AWAITING_PHOTO
        else:
             context.user_data['current_state_for_cancel_confirmation'] = None

        await update.message.reply_text(get_text("cancel_prompt", lang), reply_markup=reply_markup)
        return STATE_CONFIRM_GLOBAL_CANCEL
    else:
        await update.message.reply_text(get_text("no_active_application_to_cancel", lang), reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END