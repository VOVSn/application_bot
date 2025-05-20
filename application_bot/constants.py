# telegram_application_bot/constants.py

# Conversation states (ensure they are unique integers)
(
    STATE_ASKING_QUESTIONS,
    STATE_AWAITING_PHOTO,
    STATE_CONFIRM_CANCEL_EXISTING,
    STATE_CONFIRM_GLOBAL_CANCEL
) = range(4)

# You can add other constants here if needed, e.g., default file names
DEFAULT_SETTINGS_FILE = "settings.json"
DEFAULT_QUESTIONS_FILE = "questions.json"