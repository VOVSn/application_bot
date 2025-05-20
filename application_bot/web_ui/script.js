document.addEventListener('DOMContentLoaded', function () {
    // Element Cache
    const uiElements = {
        startButton: document.getElementById('start-button'),
        stopButton: document.getElementById('stop-button'),
        openApplicationsFolderButton: document.getElementById('open-applications-folder-button'),
        statusDisplayLabelPrefix: document.getElementById('gui_status_label_prefix'),
        statusMessageContent: document.getElementById('status-message-content'),
        logOutput: document.getElementById('log-output'),
        logLinesInput: document.getElementById('log-lines-input'),
        darkModeToggle: document.getElementById('dark-mode-toggle'),
        langToggle: document.getElementById('lang-toggle'), // New
        // Labels to translate
        guiTitleText: document.getElementById('gui_title_text'), // For document.title
        guiLogLinesLabel: document.getElementById('gui_log_lines_label'),
        guiDarkThemeLabel: document.getElementById('gui_dark_theme_label'),
        guiLangToggleLabel: document.getElementById('gui_lang_toggle_label')
    };

    let currentMaxLogLines = 100;
    let currentGuiTranslations = {}; // To store current GUI strings
    let statusPrefix = "Status: "; // Default, will be updated by localization

    // --- Theme Handling ---
    function applyTheme(isDark) {
        document.body.classList.toggle('dark-mode', isDark);
    }

    uiElements.darkModeToggle.addEventListener('change', function () {
        const isDark = this.checked;
        applyTheme(isDark);
        localStorage.setItem('darkMode', isDark.toString());
    });

    // --- Language Handling ---
    window.applyGuiTranslations = function(translations) {
        currentGuiTranslations = translations; // Store for dynamic status messages
        statusPrefix = translations.gui_status_label_prefix || "Status: ";
        uiElements.statusDisplayLabelPrefix.textContent = statusPrefix;

        document.title = translations.gui_title_text || "Application Bot Control";
        uiElements.startButton.textContent = translations.gui_start_button || "Start Bot";
        uiElements.stopButton.textContent = translations.gui_stop_button || "Stop Bot";
        uiElements.openApplicationsFolderButton.textContent = translations.gui_open_folder_button || "Open Applications Folder";
        uiElements.guiLogLinesLabel.textContent = translations.gui_log_lines_label || "Log Lines:";
        uiElements.guiDarkThemeLabel.textContent = translations.gui_dark_theme_label || "Dark Theme";
        uiElements.guiLangToggleLabel.textContent = translations.gui_lang_toggle_label || "System Language (En/Ru):";
        // Update current status message with new prefix if needed
        const currentStatusText = uiElements.statusMessageContent.textContent;
        if (currentStatusText) { //Re-apply status with potentially new general prefix
             uiElements.statusMessageContent.textContent = currentStatusText; // This line is a bit redundant, real update happens in updateStatus
        }
    };

    uiElements.langToggle.addEventListener('change', function() {
        const newLang = this.checked ? 'ru' : 'en'; // Checked = RU, Unchecked = EN
        if (window.pywebview && window.pywebview.api && window.pywebview.api.set_system_language) {
            window.pywebview.api.set_system_language(newLang).then(response => {
                if (response && response.translations) {
                    applyGuiTranslations(response.translations);
                    // Update status potentially using new language keys
                    // This assumes current status message needs re-translation or re-prefixing
                    // The Python side's update_status should handle sending correctly localized messages
                    // However, the generic prefix is part of the GUI.
                }
                if (response && response.new_lang) {
                     uiElements.langToggle.checked = (response.new_lang === 'ru');
                }
            }).catch(err => console.error("Error setting system language:", err));
        } else {
            console.error("PyWebview API not available for set_system_language");
        }
    });

    window.setSystemLanguageToggleState = function(langCode) {
        uiElements.langToggle.checked = (langCode === 'ru');
    };


    // --- Bot Controls ---
    uiElements.startButton.addEventListener('click', () => {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.start_bot_action) {
            window.pywebview.api.start_bot_action();
        } else {
            console.error("PyWebview API not available for start_bot_action");
            updateStatus("gui_status_error_ui_disconnected", true, true); // Use key
        }
    });

    uiElements.stopButton.addEventListener('click', () => {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.stop_bot_action) {
            window.pywebview.api.stop_bot_action();
        } else {
            console.error("PyWebview API not available for stop_bot_action");
            updateStatus("gui_status_error_ui_disconnected", true, true); // Use key
        }
    });

    uiElements.openApplicationsFolderButton.addEventListener('click', () => {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.open_applications_folder) {
            window.pywebview.api.open_applications_folder();
        } else {
            console.error("PyWebview API not available for open_applications_folder");
        }
    });

    uiElements.logLinesInput.addEventListener('change', function() {
        const newMax = parseInt(this.value, 10);
        if (!isNaN(newMax) && newMax >= 10 && newMax <= 1000) {
            if (window.pywebview && window.pywebview.api && window.pywebview.api.set_max_log_lines_from_ui) {
                window.pywebview.api.set_max_log_lines_from_ui(newMax);
            }
        } else {
            this.value = currentMaxLogLines; 
        }
    });

    // --- Functions callable by Python ---
    window.updateStatus = function (messageKeyOrText, isError = false, isRunning = null, isRawText = false) {
        let messageToDisplay;
        if (isRawText) {
            messageToDisplay = messageKeyOrText;
        } else {
            messageToDisplay = currentGuiTranslations[messageKeyOrText] || messageKeyOrText.replace(/_/g, ' '); // Fallback
        }
        
        uiElements.statusMessageContent.textContent = messageToDisplay;
        const statusDisplayDiv = document.getElementById('status-display'); // Get parent div for class manipulation
        statusDisplayDiv.classList.remove('running', 'stopped', 'error', 'intermediate');

        if (isRunning === true) {
            statusDisplayDiv.classList.add('running');
        } else if (isRunning === false) {
            statusDisplayDiv.classList.add('stopped');
        } else if (isRunning === null && isError) { // Error takes precedence if isRunning is not explicit
            statusDisplayDiv.classList.add('error');
        } else if (isRunning === null) { // Intermediate state (e.g. "Starting...", "Stopping...")
             statusDisplayDiv.classList.add('intermediate');
        }
         // If no class set, it's a general status
    };
    
    // addLogMessage, addBatchLogMessages, setButtonState, clearLogs remain similar
    window.addBatchLogMessages = function(messagesArray) {
        const fragment = document.createDocumentFragment();
        messagesArray.forEach(msg => {
            const logEntry = document.createElement('div');
            logEntry.textContent = msg; 
            fragment.appendChild(logEntry);
        });
        uiElements.logOutput.appendChild(fragment);

        while (uiElements.logOutput.children.length > currentMaxLogLines) {
            uiElements.logOutput.removeChild(uiElements.logOutput.firstChild);
        }
        uiElements.logOutput.scrollTop = uiElements.logOutput.scrollHeight;
    };

    window.setButtonState = function (buttonId, enabled) {
        const button = document.getElementById(buttonId); // Assuming buttonId is 'start-button' or 'stop-button'
        if (button) {
            button.disabled = !enabled;
        }
    };
    
    window.setLogLinesConfig = function(maxLines, currentLogs = []) {
        currentMaxLogLines = parseInt(maxLines, 10);
        uiElements.logLinesInput.value = currentMaxLogLines;
        
        clearLogs();
        if (currentLogs && currentLogs.length > 0) {
            addBatchLogMessages(currentLogs);
        }
    };

    window.clearLogs = function() {
        uiElements.logOutput.innerHTML = '';
    };

    // --- Initialization called by Python after pywebviewready ---
    window.initializeGui = function(config) {
        console.log("Initializing GUI with config:", config);
        applyGuiTranslations(config.guiTranslations || {});
        setSystemLanguageToggleState(config.currentLang || 'en');
        
        currentMaxLogLines = config.maxLogLines || 100;
        uiElements.logLinesInput.value = currentMaxLogLines;
        if (config.initialLogs && config.initialLogs.length > 0) {
            addBatchLogMessages(config.initialLogs);
        }

        // Initial theme
        const savedDarkMode = localStorage.getItem('darkMode');
        const isDark = (savedDarkMode !== null) ? (savedDarkMode === 'true') : true; // Default to true (dark)
        uiElements.darkModeToggle.checked = isDark;
        applyTheme(isDark);

        // Initial status message (Python's BotGUI.initial_status_message needs to be a key)
        // BotGUI will call updateStatus itself after this initialization.
        // updateStatus(config.initialStatusKey || "gui_status_initializing", config.initialStatusIsError, config.initialStatusIsRunning);
        // This part is tricky, BotGUI calls updateStatus separately in on_frontend_ready. Let Python handle it.
    };

    // --- PyWebview Initialization ---
    window.addEventListener('pywebviewready', function () {
        console.log("PyWebview ready, notifying Python backend.");
        if (window.pywebview && window.pywebview.api && window.pywebview.api.frontend_is_ready) {
            window.pywebview.api.frontend_is_ready();
        } else {
            console.error("PyWebview API not available for frontend_is_ready call.");
            uiElements.statusMessageContent.textContent = "Error: UI failed to connect";
            const statusDisplayDiv = document.getElementById('status-display');
            statusDisplayDiv.classList.add('error');
        }
    });
});