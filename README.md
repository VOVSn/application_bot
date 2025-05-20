# Telegram Application Submission Bot

This project is a Python-based Telegram bot designed to collect user applications. It guides users through a series of questions, allows them to submit photos, and then generates a PDF summary of their application. This PDF can be automatically sent to designated administrators. The bot also features a Tkinter-based GUI for easy start/stop control and real-time logging.

## Features

*   **Telegram Bot Interface**: Users interact with the bot via Telegram commands.
*   **Guided Application Process**: Asks a series of predefined questions.
*   **Photo Submission**: Allows users to upload one or more photos as part of their application.
*   **PDF Generation**: Creates a well-formatted PDF document containing all answers and submitted photos.
*   **Admin Notifications**: Sends the generated PDF to specified admin Telegram user IDs.
*   **Multi-language Support**: Text prompts and messages can be configured for multiple languages (e.g., English, Russian).
*   **Customizable Questions**: Application questions are defined in an external `questions.json` file.
*   **Configuration via JSON**: Bot token, admin IDs, file paths, timeouts, PDF settings, and language strings are managed in `settings.json`.
*   **Rate Limiting**: Prevents users from submitting applications too frequently.
*   **Conversation Timeout**: Automatically cancels an application if the user is inactive for too long.
*   **GUI Control Panel**: A simple Tkinter GUI to start/stop the bot and view live logs.
*   **Error Handling & Logging**: Robust logging for easier debugging and monitoring.
*   **Executable Packaging**: Includes a PyInstaller `.spec` file to build a standalone executable.

## Folder Structure
```
The project is organized as follows:
Application_bot/
├── .gitignore
├── application_bot # Main Python package for the bot
│ ├── applications/ # Default folder for storing generated PDF applications
│ │ └── ... (example PDFs)
│ ├── constants.py # Conversation state constants
│ ├── fonts/ # Folder for font files (e.g., for PDF generation)
│ │ └── DejaVuSans.ttf
│ ├── gui.py # Tkinter GUI control panel
│ ├── handlers/ # Telegram bot command and message handlers
│ │ ├── command_handlers.py
│ │ └── conversation_logic.py
│ ├── icon.ico # Icon for the executable/GUI
│ ├── main.py # Main CLI entry point for the bot
│ ├── pdf_generator.py # Logic for creating PDF applications
│ ├── questions.json # Default questions for the application (can be customized)
│ ├── settings.json # User-specific settings (copy from settings_example.json)
│ ├── settings_example.json # Example settings file
│ ├── temp_photos/ # Default folder for temporarily storing uploaded photos
│ └── utils.py # Utility functions (loading settings, i18n, etc.)
├── application_bot.spec # PyInstaller specification file for building the executable
└── requirements.txt # Python dependencies
```
## Prerequisites

*   Python 3.8 or higher
*   `pip` (Python package installer)

## Setup and Installation

1.  **Clone the repository (or download the source code):**
    ```bash
    git clone [https://github.com/VOVSn/Application_bot](https://github.com/VOVSn/Application_bot)
    cd Application_bot
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python -m venv venv
    # On Windows
    venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

1.  **Copy `settings_example.json` to `settings.json`:**
    ```bash
    cp application_bot/settings_example.json application_bot/settings.json
    ```
    *If you're on Windows and `cp` doesn't work, use `copy application_bot\settings_example.json application_bot\settings.json`*

2.  **Edit `application_bot/settings.json`:**
    *   **`BOT_TOKEN`**: **Required**. Your Telegram Bot Token obtained from BotFather.
    *   **`ADMIN_USER_IDS`**: **Required**. A comma-separated string of Telegram User IDs for administrators who will receive the application PDFs (e.g., `"12345678,98765432"`). You can get your User ID by messaging a bot like `@userinfobot` on Telegram.
    *   **`APPLICATION_FOLDER`**: Folder where generated PDFs are stored.
    *   **`QUESTIONS_FILE`**: Path to the JSON file containing application questions.
    *   **`TEMP_PHOTO_FOLDER`**: Folder for temporary photo storage during an application.
    *   **`FONT_FILE_PATH`**: Path to the TTF font file used for PDF generation (e.g., `"fonts/DejaVuSans.ttf"`). Ensure this font supports the characters you need.
    *   **`RATE_LIMIT_SECONDS`**: Cooldown period between application submissions for a user.
    *   **`CONVERSATION_TIMEOUT_SECONDS`**: How long the bot waits for a user response before canceling the application.
    *   **`APPLICATION_PHOTO_NUMB`**: Number of photos required for an application.
    *   **`SEND_PDF_TO_ADMINS`**: `true` to send PDFs to admins, `false` to only save them locally.
    *   **`MAX_ALLOWED_FILE_SIZE_MB`**: Maximum size for uploaded photos/files.
    *   **HTTP Timeout Settings**: Configure timeouts for Telegram API requests.
    *   **Language Settings (`OVERRIDE_USER_LANG`, `DEFAULT_LANG`, `LANGUAGES`)**: Configure bot language, default language, and provide translations for different text prompts.
    *   **`PDF_SETTINGS`**: Customize PDF layout, fonts, sizes, etc.

3.  **Customize Questions (Optional):**
    Edit `application_bot/questions.json` to define the questions the bot will ask. Each question should have an `id` (unique identifier) and `text` (the question prompt).

    Example:
    ```json
    [
      {"id": "full_name", "text": "Как Вас зовут? (Полное имя)"},
      {"id": "contact_phone", "text": "Ваш контактный номер телефона?"}
    ]
    ```

## Running the Bot

You can run the bot in two ways:

1.  **Command-Line Interface (CLI):**
    Navigate to the `Application_bot/` root directory and run:
    ```bash
    python -m application_bot.main
    ```
    or
    ```bash
    python application_bot/main.py
    ```
    Logs will be printed to the console. Press `Ctrl+C` to stop the bot.

2.  **Graphical User Interface (GUI):**
    Navigate to the `Application_bot/` root directory and run:
    ```bash
    python -m application_bot.gui
    ```
    or
    ```bash
    python application_bot/gui.py
    ```
    This will open the Tkinter control panel. Use the "Start Bot" and "Stop Bot" buttons. Logs will be displayed in the GUI's log area. Closing the GUI window will attempt to stop the bot gracefully.

## Building the Executable (One-Folder Bundle)

The project includes an `application_bot.spec` file configured for PyInstaller to create a one-folder (`onedir`) distributable.

1.  **Ensure PyInstaller and hooks are installed** (they are in `requirements.txt`):
    ```bash
    pip install pyinstaller pyinstaller-hooks-contrib
    ```

2.  **(Optional) Install UPX:** For smaller executable sizes, download UPX from [its official website](https://upx.github.io/) and ensure it's added to your system's PATH.

3.  **Build the executable:**
    Navigate to the `Application_bot/` root directory and run:
    ```bash
    pyinstaller application_bot.spec
    ```

4.  **Find the output:**
    The bundled application will be located in the `Application_bot/dist/ApplicationBotGUI/` folder. This folder contains the executable (`ApplicationBotGUI.exe` on Windows) and all necessary dependencies, including `settings.json`, `questions.json`, and the `fonts` folder.

5.  **Distribute:**
    You can distribute the entire `ApplicationBotGUI` folder. Users can run the `ApplicationBotGUI.exe` directly from this folder. They will need to have their own `settings.json` (or you can pre-configure one for them).

## Bot Usage (Telegram Commands)

*   **/start**: Displays a welcome message.
*   **/help**: Shows available commands and a brief help message.
*   **/apply**: Starts the application process. The bot will guide the user through questions.
*   **/cancel**: Allows the user to cancel an ongoing application process.

## Troubleshooting

*   **Bot doesn't start / `BOT_TOKEN` error**: Ensure your `BOT_TOKEN` in `application_bot/settings.json` is correct and valid.
*   **PDFs not sent to admins**: Verify that `ADMIN_USER_IDS` in `application_bot/settings.json` are correct numeric Telegram User IDs, and `SEND_PDF_TO_ADMINS` is `true`.
*   **Font errors / Garbled text in PDF**:
    *   Ensure the `FONT_FILE_PATH` in `settings.json` points to a valid `.ttf` font file.
    *   Make sure the chosen font supports all characters used in your questions and user answers (especially for non-Latin alphabets). `DejaVuSans.ttf` is a good general-purpose Unicode font.
*   **`ModuleNotFoundError` after building with PyInstaller**: If the executable crashes with this error, a specific module might not have been automatically included. Add the missing module name to the `hiddenimports` list in `application_bot.spec` and rebuild.
*   **Log Messages**: Check the console output (for CLI mode) or the log area in the GUI for error messages and detailed information.

## Contributing

Feel free to fork the project, create feature branches, and submit pull requests. For major changes, please open an issue first to discuss what you would like to change.

## License

Specify your license here (e.g., MIT, GPL, etc.). If no license is specified, it typically means standard copyright laws apply.
