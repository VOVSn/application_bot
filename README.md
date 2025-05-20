# Telegram Application Submission Bot / Бот для Подачи Заявок в Telegram



This project is a Python-based Telegram bot designed to collect user applications. It guides users through a series of questions, allows them to submit photos, and then generates a PDF summary of their application. This PDF can be automatically sent to designated administrators. The bot also features a `pywebview`-based GUI for easy start/stop control, settings management, question editing, and real-time logging.

Этот проект представляет собой Telegram-бота на Python, предназначенного для сбора заявок от пользователей. Он проводит пользователей через серию вопросов, позволяет им отправлять фотографии, а затем генерирует PDF-сводку их заявки. Этот PDF может автоматически отправляться назначенным администраторам. Бот также имеет графический интерфейс пользователя (GUI) на основе `pywebview` для удобного управления запуском/остановкой, настройками, редактированием вопросов и просмотра логов в реальном времени.

---

## Features / Особенности

*   **Telegram Bot Interface**: Users interact with the bot via Telegram commands.
*   **Guided Application Process**: Asks a series of predefined questions.
*   **Photo Submission**: Allows users to upload one or more photos as part of their application.
*   **PDF Generation**: Creates a well-formatted PDF document containing all answers and submitted photos.
*   **Admin Notifications**: Sends the generated PDF to specified admin Telegram user IDs.
*   **Multi-language Support**: Text prompts and messages can be configured for multiple languages (e.g., English, Russian).
*   **Customizable Questions**: Application questions are defined and editable via the GUI or directly in `questions.json`.
*   **Configuration via GUI & JSON**: Bot token, admin IDs, file paths, timeouts, PDF settings, and language strings are managed in `settings.json` and editable through the GUI.
*   **Rate Limiting**: Prevents users from submitting applications too frequently.
*   **Conversation Timeout**: Automatically cancels an application if the user is inactive for too long.
*   **GUI Control Panel (`pywebview`)**: A modern GUI to start/stop the bot, view live logs, edit questions, and manage all settings.
*   **Error Handling & Logging**: Robust logging for easier debugging and monitoring.
*   **Executable Packaging**: Includes a PyInstaller `.spec` file to build a standalone executable.


*   **Интерфейс Telegram-бота**: Пользователи взаимодействуют с ботом через команды Telegram.
*   **Пошаговый процесс подачи заявки**: Задает серию предопределенных вопросов.
*   **Отправка фотографий**: Позволяет пользователям загружать одну или несколько фотографий как часть заявки.
*   **Генерация PDF**: Создает хорошо отформатированный PDF-документ, содержащий все ответы и отправленные фотографии.
*   **Уведомления администраторам**: Отправляет сгенерированный PDF указанным ID пользователей Telegram администраторов.
*   **Поддержка нескольких языков**: Текстовые подсказки и сообщения могут быть настроены для нескольких языков (например, английский, русский).
*   **Настраиваемые вопросы**: Вопросы для заявки определяются и редактируются через GUI или непосредственно в файле `questions.json`.
*   **Конфигурация через GUI и JSON**: Токен бота, ID администраторов, пути к файлам, тайм-ауты, настройки PDF и языковые строки управляются в `settings.json` и редактируются через GUI.
*   **Ограничение частоты запросов**: Предотвращает слишком частую подачу заявок пользователями.
*   **Тайм-аут разговора**: Автоматически отменяет заявку, если пользователь неактивен слишком долго.
*   **Панель управления GUI (`pywebview`)**: Современный GUI для запуска/остановки бота, просмотра логов в реальном времени, редактирования вопросов и управления всеми настройками.
*   **Обработка ошибок и логирование**: Надежное логирование для упрощения отладки и мониторинга.
*   **Сборка исполняемого файла**: Включает файл `.spec` для PyInstaller для создания автономного исполняемого файла.

---

## Folder Structure / Структура Папок


The project is organized as follows:
Use code with caution.
```
Application_bot/
├── .gitignore
├── ApplicationBotGUI.spec # PyInstaller specification file
├── README.md
├── application_bot/ # Main Python package for the bot
│ ├── applications/ # Default folder for storing generated PDF applications
│ ├── constants.py # Conversation state constants
│ ├── fonts/ # Folder for font files (e.g., for PDF generation)
│ │ └── DejaVuSans.ttf
│ ├── gui.py # Python backend for the pywebview GUI
│ ├── handlers/ # Telegram bot command and message handlers
│ │ ├── command_handlers.py
│ │ └── conversation_logic.py
│ ├── icon.ico # Icon for the executable/GUI
│ ├── main.py # Main CLI entry point and bot logic
│ ├── pdf_generator.py # Logic for creating PDF applications
│ ├── questions.json # Default questions for the application
│ ├── settings.json # Bot and application settings
│ ├── temp_photos/ # Default folder for temporarily storing uploaded photos
│ ├── utils.py # Utility functions (loading settings, i18n, etc.)
│ └── web_ui/ # HTML, CSS, JS files for the pywebview GUI
│ ├── gui.html
│ ├── logo.png
│ ├── script.js
│ └── style.css
└── requirements.txt # Python dependencies
```
## Prerequisites / Предварительные Требования

*   Python 3.8 or higher
*   `pip` (Python package installer)



---
## Setup and Installation / Установка и Настройка

1.  **Clone the repository (or download the source code):**
    ```bash
    git clone https://github.com/VOVSn/Application_bot
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

---
## Configuration / Конфигурация

1.  **Edit `application_bot/settings.json`:**
    This file will be created automatically on the first run if it doesn't exist, or you can create it manually with default values.
    The GUI provides an interface to edit most of these settings.
    *   **`BOT_TOKEN`**: **Required**. Your Telegram Bot Token obtained from BotFather.
    *   **`ADMIN_USER_IDS`**: **Required**. A comma-separated string of Telegram User IDs for administrators (e.g., `"12345678,98765432"`). Get User ID via `@userinfobot`.
    *   **`APPLICATION_FOLDER`**: Folder for generated PDFs.
    *   **`QUESTIONS_FILE`**: Path to the JSON file for application questions.
    *   **`TEMP_PHOTO_FOLDER`**: Folder for temporary photo storage.
    *   **`FONT_FILE_PATH`**: Path to the TTF font for PDF generation (e.g., `"fonts/DejaVuSans.ttf"`).
    *   **`RATE_LIMIT_SECONDS`**: Cooldown between user submissions.
    *   **`CONVERSATION_TIMEOUT_SECONDS`**: User inactivity timeout.
    *   **`APPLICATION_PHOTO_NUMB`**: Number of photos required.
    *   **`SEND_PDF_TO_ADMINS`**: `true` to send PDFs to admins, `false` to save locally.
    *   **`MAX_ALLOWED_FILE_SIZE_MB`**: Max size for uploads.
    *   **HTTP Timeout Settings**: For Telegram API requests.
    *   **Language Settings (`OVERRIDE_USER_LANG`, `DEFAULT_LANG`, `LANGUAGES`)**: Bot language configuration and translations.
    *   **`PDF_SETTINGS`**: PDF layout, fonts, sizes.
    *   **`PYWEBVIEW_DEBUG`**: `true` to enable debug console for pywebview GUI.

2.  **Customize Questions (Optional):**
    Edit `application_bot/questions.json` or use the "Edit Questions" feature in the GUI. Each question needs an `id` (unique) and `text`.

    Example:
    ```json
    [
      {"id": "full_name", "text": "What is your full name?"},
      {"id": "contact_phone", "text": "Your contact phone number?"}
    ]
    ```

---
## Running the Bot / Запуск Бота

You can run the bot in two ways:

1.  **Command-Line Interface (CLI):**
    Navigate to the `Application_bot/` root directory and run:
    ```bash
    python -m application_bot.main
    ```
    Logs will be printed to the console. Press `Ctrl+C` to stop the bot.

2.  **Graphical User Interface (GUI):**
    Navigate to the `Application_bot/` root directory and run:
    ```bash
    python -m application_bot.gui
    ```
    This will open the `pywebview` control panel. Use the "Start Bot" and "Stop Bot" buttons, and access settings/questions via their respective buttons. Logs are displayed in the GUI. Closing the GUI window stops the bot.

Вы можете запустить бота двумя способами:

1.  **Интерфейс командной строки (CLI):**
    Перейдите в корневой каталог `Application_bot/` и выполните:
    ```bash
    python -m application_bot.main
    ```
    Логи будут выводиться в консоль. Нажмите `Ctrl+C`, чтобы остановить бота.

2.  **Графический интерфейс пользователя (GUI):**
    Перейдите в корневой каталог `Application_bot/` и выполните:
    ```bash
    python -m application_bot.gui
    ```
    Это откроет панель управления `pywebview`. Используйте кнопки «Start Bot» и «Stop Bot», а также получайте доступ к настройкам/вопросам через соответствующие кнопки. Логи отображаются в GUI. Закрытие окна GUI останавливает бота.

---
## Building the Executable (One-Folder Bundle) / Сборка Исполняемого Файла (пакет в одну папку)

The project includes an `ApplicationBotGUI.spec` file for PyInstaller to create a one-folder distributable.

1.  **Ensure PyInstaller is installed** (it's in `requirements.txt`).
2.  **(Optional) Install UPX:** For smaller executables, download UPX from [its official website](https://upx.github.io/) and add it to your system's PATH. The `.spec` file is configured to use UPX if available.
3.  **Build:** Navigate to `Application_bot/` root and run:
    ```bash
    pyinstaller ApplicationBotGUI.spec
    ```
4.  **Output:** The bundled app is in `Application_bot/dist/ApplicationBotGUI/`. This folder contains the executable and all dependencies.
5.  **Distribute:** Share the `ApplicationBotGUI` folder. Users run `ApplicationBotGUI.exe` (or equivalent). `settings.json` and `questions.json` will be created/used within this folder.

Проект включает файл `ApplicationBotGUI.spec` для PyInstaller для создания дистрибутива в виде одной папки.

1.  **Убедитесь, что PyInstaller установлен** (он есть в `requirements.txt`).
2.  **(Необязательно) Установите UPX:** Для уменьшения размера исполняемых файлов загрузите UPX с [официального сайта](https://upx.github.io/) и добавьте его в PATH вашей системы. Файл `.spec` настроен на использование UPX, если он доступен.
3.  **Сборка:** Перейдите в корень `Application_bot/` и выполните:
    ```bash
    pyinstaller ApplicationBotGUI.spec
    ```
4.  **Результат:** Собранное приложение находится в `Application_bot/dist/ApplicationBotGUI/`. Эта папка содержит исполняемый файл и все зависимости.
5.  **Распространение:** Поделитесь папкой `ApplicationBotGUI`. Пользователи запускают `ApplicationBotGUI.exe` (или эквивалент). Файлы `settings.json` и `questions.json` будут создаваться/использоваться внутри этой папки.

---
## Bot Usage (Telegram Commands) / Использование Бота (Команды Telegram)


*   `/start`: Displays a welcome message.
*   `/help`: Shows available commands.
*   `/apply`: Starts the application process.
*   `/cancel`: Cancels an ongoing application.

---

*   `/start`: Отображает приветственное сообщение.
*   `/help`: Показывает доступные команды.
*   `/apply`: Начинает процесс подачи заявки.
*   `/cancel`: Отменяет текущий процесс подачи заявки.

---
## Troubleshooting / Устранение Неисправностей


*   **Bot doesn't start / `BOT_TOKEN` error**: Ensure `BOT_TOKEN` in `application_bot/settings.json` (or via GUI) is correct.
*   **PDFs not sent**: Verify `ADMIN_USER_IDS` and `SEND_PDF_TO_ADMINS` in settings.
*   **Font errors in PDF**: Check `FONT_FILE_PATH` and ensure font supports all characters.
*   **`ModuleNotFoundError` after build**: Add missing module to `hiddenimports` in `.spec` file and rebuild.
*   **Log Messages**: Check console (CLI) or GUI log area for errors.

---

*   **Бот не запускается / ошибка `BOT_TOKEN`**: Убедитесь, что `BOT_TOKEN` в `application_bot/settings.json` (или через GUI) указан правильно.
*   **PDF не отправляются**: Проверьте `ADMIN_USER_IDS` и `SEND_PDF_TO_ADMINS` в настройках.
*   **Ошибки шрифтов в PDF**: Проверьте `FONT_FILE_PATH` и убедитесь, что шрифт поддерживает все символы.
*   **`ModuleNotFoundError` после сборки**: Добавьте отсутствующий модуль в `hiddenimports` в файле `.spec` и пересоберите.
*   **Сообщения в логах**: Проверяйте вывод консоли (CLI) или область логов в GUI на наличие ошибок.






