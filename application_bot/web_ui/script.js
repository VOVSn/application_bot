document.addEventListener('DOMContentLoaded', function () {
    // Element Cache
    const uiElements = {
        startButton: document.getElementById('start-button'),
        stopButton: document.getElementById('stop-button'),
        openApplicationsFolderButton: document.getElementById('open-applications-folder-button'),
        editQuestionsButton: document.getElementById('edit-questions-button'),
        editSettingsButton: document.getElementById('edit-settings-button'),

        statusDisplayLabelPrefix: document.getElementById('gui_status_label_prefix'),
        statusMessageContent: document.getElementById('status-message-content'),
        logOutput: document.getElementById('log-output'),
        guiTitleText: document.getElementById('gui_title_text'),
        logoImage: document.getElementById('logo'),

        // Questions Modal Elements
        questionsModal: document.getElementById('questions-modal'),
        questionsTableBody: document.getElementById('questions-table').getElementsByTagName('tbody')[0],
        addQuestionButton: document.getElementById('add-question-button'),
        saveQuestionsButton: document.getElementById('save-questions-button'),
        cancelQuestionsButton: document.getElementById('cancel-questions-button'),

        // General Settings Modal Elements
        settingsModal: document.getElementById('settings-modal'),
        saveAllSettingsButton: document.getElementById('save-all-settings-button'),
        cancelAllSettingsButton: document.getElementById('cancel-all-settings-button'),
        basicSettingsTabButton: document.getElementById('basic-settings-tab-btn'),

        // Basic Settings Tab Inputs (inside modal)
        settingsModalLogLinesInput: document.getElementById('settings-modal-log-lines-input'),
        settingsModalThemeSelect: document.getElementById('settings-modal-theme-select'),
        settingsModalLangToggle: document.getElementById('settings-modal-lang-toggle'),
        settingsOverrideUserLangToggle: document.getElementById('settings-override-user-lang-toggle'),

        // PDF Settings Tab Inputs (inside modal)
        pdfFontFilePathInput: document.getElementById('pdf-font-file-path'),
        pdfFontNameRegisteredInput: document.getElementById('pdf-font-name-registered'),
        pdfPageWidthMmInput: document.getElementById('pdf-page-width-mm'),
        pdfPageHeightMmInput: document.getElementById('pdf-page-height-mm'),
        pdfMarginMmInput: document.getElementById('pdf-margin-mm'),
        pdfPhotoWidthMmInput: document.getElementById('pdf-photo-width-mm'),
        pdfPhotoPositionSelect: document.getElementById('pdf-photo-position'),
        pdfTitleFontSizeInput: document.getElementById('pdf-title-font-size'),
        pdfHeaderFontSizeInput: document.getElementById('pdf-header-font-size'),
        pdfQuestionFontSizeInput: document.getElementById('pdf-question-font-size'),
        pdfAnswerFontSizeInput: document.getElementById('pdf-answer-font-size'),
        pdfQuestionBoldCheckbox: document.getElementById('pdf-question-bold'),
        pdfAppPhotoNumbInput: document.getElementById('pdf-app-photo-numb'),
        pdfSendToAdminsToggle: document.getElementById('pdf-send-to-admins'),

        // Admin Settings Tab Inputs (inside modal)
        adminBotTokenInput: document.getElementById('admin-bot-token'),
        adminUserIdsInput: document.getElementById('admin-user-ids'),

        // Theme Stylesheets
        mainStyleSheet: document.getElementById('main-stylesheet'),
        themeLinkMemphis: document.getElementById('theme-link-memphis'),
        themeLinkAurora: document.getElementById('theme-link-aurora'),

        // Info Buttons
        helpButton: document.getElementById('help-button'),
        aboutButton: document.getElementById('about-button'),
        appVersionDisplay: document.getElementById('app-version-display')
    };

    let currentMaxLogLines = 100;
    let currentGuiTranslations = {};
    let statusPrefix = "Status: ";
    let currentQuestionsData = [];
    let currentFetchedSettings = {};

    if (uiElements.logoImage) {
        const originalSrc = uiElements.logoImage.getAttribute('src');
        if (originalSrc) {
            const basePath = originalSrc.split('?')[0];
            uiElements.logoImage.src = `${basePath}?t=${new Date().getTime()}`;
        }
    }

    function applyTheme(themeValue) {
        if (uiElements.mainStyleSheet) uiElements.mainStyleSheet.disabled = true;
        if (uiElements.themeLinkMemphis) uiElements.themeLinkMemphis.disabled = true;
        if (uiElements.themeLinkAurora) uiElements.themeLinkAurora.disabled = true;

        document.body.className = '';

        switch (themeValue) {
            case 'default-dark':
                if (uiElements.mainStyleSheet) uiElements.mainStyleSheet.disabled = false;
                document.body.classList.add('dark-mode');
                break;
            case 'default-light':
                if (uiElements.mainStyleSheet) uiElements.mainStyleSheet.disabled = false;
                document.body.classList.add('light-mode');
                break;
            case 'memphis':
                if (uiElements.themeLinkMemphis) uiElements.themeLinkMemphis.disabled = false;
                document.body.classList.add('memphis-theme');
                break;
            case 'aurora-dreams':
                if (uiElements.themeLinkAurora) uiElements.themeLinkAurora.disabled = false;
                document.body.classList.add('aurora-theme');
                break;
            default:
                if (uiElements.mainStyleSheet) uiElements.mainStyleSheet.disabled = false;
                document.body.classList.add('dark-mode');
                themeValue = 'default-dark';
                break;
        }
        localStorage.setItem('selectedTheme', themeValue);
        if(uiElements.settingsModalThemeSelect) uiElements.settingsModalThemeSelect.value = themeValue;
    }
    
    if (uiElements.settingsModalThemeSelect) {
        uiElements.settingsModalThemeSelect.addEventListener('change', function () {
            applyTheme(this.value); 
        });
    }

    window.applyGuiTranslations = function(translations) {
        currentGuiTranslations = translations;
        statusPrefix = translations.gui_status_label_prefix || "Status: ";
        if (uiElements.statusDisplayLabelPrefix) uiElements.statusDisplayLabelPrefix.textContent = statusPrefix;
        if (uiElements.guiTitleText) uiElements.guiTitleText.textContent = translations.gui_title || "Application Bot Control";
        document.title = translations.gui_title || "Application Bot Control";

        document.querySelectorAll('[data-i18n-key]').forEach(el => {
            const key = el.dataset.i18nKey;
            if (translations[key]) {
                if (el.tagName === 'OPTION') {
                    el.textContent = translations[key];
                } else if (el.tagName === 'INPUT' && (el.type === 'button' || el.type === 'submit') || el.tagName === 'BUTTON') {
                    // Don't override text content for icon buttons if they primarily use SVG
                    if (!el.classList.contains('icon-button')) {
                        el.textContent = translations[key];
                    }
                } else if (el.tagName === 'LABEL' || el.tagName === 'H2' || el.tagName === 'TH' || el.id === 'gui_title_text') {
                     el.textContent = translations[key];
                }
            }
        });

        if (uiElements.questionsModal.style.display === 'flex') {
            populateQuestionsTable(currentQuestionsData);
        }

        // Update tooltips for help/about buttons
        if (uiElements.helpButton) uiElements.helpButton.title = currentGuiTranslations.gui_help_button_title || "Help";
        if (uiElements.aboutButton) uiElements.aboutButton.title = currentGuiTranslations.gui_about_button_title || "About";
    };

    uiElements.settingsModalLangToggle.addEventListener('change', function() {
        // Language change is handled on modal save now
    });

    window.setSystemLanguageToggleState = function(langCode) {
        if (uiElements.settingsModalLangToggle) {
            uiElements.settingsModalLangToggle.checked = (langCode === 'ru');
        }
    };

    uiElements.startButton.addEventListener('click', () => {
        if (window.pywebview && window.pywebview.api.start_bot_action) {
            window.pywebview.api.start_bot_action();
        } else {
            updateStatus("gui_status_error_ui_disconnected", true, null, false);
        }
    });

    uiElements.stopButton.addEventListener('click', () => {
        if (window.pywebview && window.pywebview.api.stop_bot_action) {
            window.pywebview.api.stop_bot_action();
        } else {
            updateStatus("gui_status_error_ui_disconnected", true, null, false);
        }
    });

    uiElements.openApplicationsFolderButton.addEventListener('click', () => {
        if (window.pywebview && window.pywebview.api.open_applications_folder) {
            window.pywebview.api.open_applications_folder();
        }
    });

    uiElements.settingsModalLogLinesInput.addEventListener('change', function() {
        // Log lines change is handled on modal save now
    });

    // Help and About Button Event Listeners
    if (uiElements.helpButton) {
        uiElements.helpButton.addEventListener('click', () => {
            const helpTitle = currentGuiTranslations.gui_help_modal_title || "Help";
            const helpMessage = (
                currentGuiTranslations.gui_help_modal_content ||
                "Application Bot Control - Help:\n\n" +
                "- Start/Stop Bot: Controls the Telegram bot's operation.\n" +
                "- Open Applications Folder: Opens the folder where PDF applications are saved.\n" +
                "- Edit Questions: Modify the questions the bot asks users.\n"   +
                "- Settings: Configure bot token, admin IDs, PDF options, language, theme, and log lines.\n\n" +
                "The bot allows users to apply by answering questions and submitting photos, generating a PDF."
            );
            alert(`${helpTitle}\n\n${helpMessage}`);
        });
    }

    if (uiElements.aboutButton) {
        uiElements.aboutButton.addEventListener('click', () => {
            const aboutTitle = currentGuiTranslations.gui_about_modal_title || "About";
            const aboutMessage = (
                currentGuiTranslations.gui_about_modal_content ||
                "Application Bot Control\n" +
                "Version: 0.1.1 beta\n" +
                "Author: VOVSN\n" +
                "GitHub: github.com/vovsn\n\n" +
                "This application provides a GUI to manage and configure the Application Telegram Bot."
            );
            alert(`${aboutTitle}\n\n${aboutMessage}`);
        });
    }


    window.updateStatus = function (messageKeyOrText, isError = false, isRunning = null, isRawText = false) {
        let messageToDisplay = isRawText ? messageKeyOrText : (currentGuiTranslations[messageKeyOrText] || messageKeyOrText.replace(/_/g, ' '));
        if (uiElements.statusMessageContent) uiElements.statusMessageContent.textContent = messageToDisplay;
        const statusDisplayDiv = document.getElementById('status-display');
        if (statusDisplayDiv) {
            statusDisplayDiv.className = 'status-display';
            if (isError) statusDisplayDiv.classList.add('error');
            else if (isRunning === true) statusDisplayDiv.classList.add('running');
            else if (isRunning === false) statusDisplayDiv.classList.add('stopped');
            else if (isRunning === null) statusDisplayDiv.classList.add('intermediate');
        }
    };

    window.addBatchLogMessages = function(messagesArray) {
        if (!uiElements.logOutput) return;
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
        const button = document.getElementById(buttonId);
        if (button) button.disabled = !enabled;
    };

    window.setLogLinesConfig = function(maxLines, currentLogs = []) {
        currentMaxLogLines = parseInt(maxLines, 10);
        if(uiElements.settingsModalLogLinesInput) uiElements.settingsModalLogLinesInput.value = currentMaxLogLines;
        clearLogs();
        if (currentLogs && currentLogs.length > 0) addBatchLogMessages(currentLogs);
    };

    window.clearLogs = function() { if(uiElements.logOutput) uiElements.logOutput.innerHTML = ''; };

    function openQuestionsModal() {
        if (window.pywebview && window.pywebview.api.get_questions) {
            window.pywebview.api.get_questions().then(questions => {
                currentQuestionsData = JSON.parse(JSON.stringify(questions || []));
                populateQuestionsTable(currentQuestionsData);
                uiElements.questionsModal.style.display = 'flex';
            }).catch(err => {
                console.error("Error fetching questions:", err);
                alert(currentGuiTranslations.gui_alert_questions_load_failed || "Could not load questions for editing.");
            });
        } else {
            alert("Error: UI cannot connect to Python to get questions.");
        }
    }
    function closeQuestionsModal() {
        uiElements.questionsModal.style.display = 'none';
        uiElements.questionsTableBody.innerHTML = '';
    }

    function populateQuestionsTable(questions) {
        uiElements.questionsTableBody.innerHTML = '';
        questions.forEach((q, index) => {
            const row = uiElements.questionsTableBody.insertRow();
            row.dataset.originalIndex = index; 

            const textCell = row.insertCell();
            textCell.innerHTML = `<input type="text" class="neumorphic-input modal-input" value="${q.text || ''}" placeholder="Question text...">`;

            const actionsCell = row.insertCell();
            const deleteButton = document.createElement('button');
            deleteButton.classList.add('neumorphic-button', 'action-button', 'modal-button', 'delete-icon-btn'); 
            deleteButton.innerHTML = `<svg class="trash-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" fill="currentColor"/></svg>`;
            
            const deleteLabel = currentGuiTranslations.gui_modal_delete_button || 'Delete'; 
            deleteButton.setAttribute('aria-label', deleteLabel);
            deleteButton.title = deleteLabel;
            
            deleteButton.onclick = () => deleteQuestionRow(index); 
            actionsCell.appendChild(deleteButton);
        });
    }

    function deleteQuestionRow(indexInCurrentData) {
        currentQuestionsData.splice(indexInCurrentData, 1);
        populateQuestionsTable(currentQuestionsData); 
    }

    uiElements.editQuestionsButton.addEventListener('click', openQuestionsModal);
    uiElements.cancelQuestionsButton.addEventListener('click', closeQuestionsModal);

    uiElements.addQuestionButton.addEventListener('click', () => {
        currentQuestionsData.push({ id: `new_q_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`, text: '' }); 
        populateQuestionsTable(currentQuestionsData);
        const tableContainer = uiElements.questionsModal.querySelector('.questions-table-container');
        if (tableContainer) tableContainer.scrollTop = tableContainer.scrollHeight;
    });

    uiElements.saveQuestionsButton.addEventListener('click', () => {
        const updatedQuestions = [];
        const rows = uiElements.questionsTableBody.rows;
        let hasError = false;

        for (let i = 0; i < rows.length; i++) {
            const originalIndex = parseInt(rows[i].dataset.originalIndex, 10);
            const id = currentQuestionsData[originalIndex] ? currentQuestionsData[originalIndex].id : `new_q_save_fallback_${Date.now()}_${i}`;
            
            const textInput = rows[i].cells[0].querySelector('input'); 
            const text = textInput.value.trim();
            
            textInput.style.borderColor = ''; 

            if (!text) {
                alert((currentGuiTranslations.gui_alert_question_text_empty || "Question Text cannot be empty for row {row_num}.").replace('{row_num}', i + 1));
                textInput.style.borderColor = 'red';
                hasError = true; break;
            }
            updatedQuestions.push({ id: id, text: text });
        }

        if (hasError) return;

        if (window.pywebview && window.pywebview.api.save_questions) {
            window.pywebview.api.save_questions(updatedQuestions).then(success => {
                if (success) {
                    alert(currentGuiTranslations.gui_alert_questions_saved || "Questions saved successfully!");
                    closeQuestionsModal();
                } else {
                    alert(currentGuiTranslations.gui_alert_questions_save_failed || "Failed to save questions. Check logs.");
                }
            }).catch(err => alert((currentGuiTranslations.gui_alert_questions_save_error || "Error saving questions: {error}").replace('{error}', String(err))));
        } else {
             alert("Error: UI cannot connect to Python to save questions.");
        }
    });

    window.openSettingsTab = function(evt, tabName) {
        let i, tabcontent, tablinks;
        tabcontent = uiElements.settingsModal.getElementsByClassName("tab-content");
        for (i = 0; i < tabcontent.length; i++) {
            tabcontent[i].style.display = "none";
            tabcontent[i].classList.remove("active-tab");
        }
        tablinks = uiElements.settingsModal.getElementsByClassName("tab-button");
        for (i = 0; i < tablinks.length; i++) {
            tablinks[i].classList.remove("active");
        }
        const currentTab = document.getElementById(tabName);
        if(currentTab) {
            currentTab.style.display = "block";
            currentTab.classList.add("active-tab");
        }
        if(evt && evt.currentTarget) evt.currentTarget.classList.add("active");
    }

    function openSettingsModal() {
        if (window.pywebview && window.pywebview.api.get_all_settings) {
            window.pywebview.api.get_all_settings().then(settings => {
                currentFetchedSettings = settings || {};
                populateAllSettingsForm(currentFetchedSettings);
                uiElements.settingsModal.style.display = 'flex';
                if (uiElements.basicSettingsTabButton) {
                    uiElements.basicSettingsTabButton.click();
                }
            }).catch(err => {
                console.error("Error fetching all settings:", err);
                alert(currentGuiTranslations.gui_alert_settings_load_failed || "Could not load settings for editing.");
            });
        } else {
            alert("Error: UI cannot connect to Python to get settings.");
        }
    }

    function closeSettingsModal() {
        uiElements.settingsModal.style.display = 'none';
    }

    function populateAllSettingsForm(settings) {
        uiElements.settingsModalLogLinesInput.value = currentMaxLogLines;
        
        const savedTheme = localStorage.getItem('selectedTheme') || 'default-dark';
        uiElements.settingsModalThemeSelect.value = savedTheme;

        uiElements.settingsModalLangToggle.checked = (settings.DEFAULT_LANG === 'ru');
        uiElements.settingsOverrideUserLangToggle.checked = settings.OVERRIDE_USER_LANG === undefined ? true : settings.OVERRIDE_USER_LANG;

        const pdfSettings = settings.PDF_SETTINGS || {};
        uiElements.pdfFontFilePathInput.value = settings.FONT_FILE_PATH || "fonts/DejaVuSans.ttf";
        uiElements.pdfFontNameRegisteredInput.value = pdfSettings.font_name_registered || "CustomUnicodeFont";
        uiElements.pdfPageWidthMmInput.value = pdfSettings.page_width_mm === undefined ? 210 : pdfSettings.page_width_mm;
        uiElements.pdfPageHeightMmInput.value = pdfSettings.page_height_mm === undefined ? 297 : pdfSettings.page_height_mm;
        uiElements.pdfMarginMmInput.value = pdfSettings.margin_mm === undefined ? 15 : pdfSettings.margin_mm;
        uiElements.pdfPhotoWidthMmInput.value = pdfSettings.photo_width_mm === undefined ? 80 : pdfSettings.photo_width_mm;
        uiElements.pdfPhotoPositionSelect.value = pdfSettings.photo_position || "top_right";
        uiElements.pdfTitleFontSizeInput.value = pdfSettings.title_font_size === undefined ? 16 : pdfSettings.title_font_size;
        uiElements.pdfHeaderFontSizeInput.value = pdfSettings.header_font_size === undefined ? 10 : pdfSettings.header_font_size;
        uiElements.pdfQuestionFontSizeInput.value = pdfSettings.question_font_size === undefined ? 12 : pdfSettings.question_font_size;
        uiElements.pdfAnswerFontSizeInput.value = pdfSettings.answer_font_size === undefined ? 10 : pdfSettings.answer_font_size;
        uiElements.pdfQuestionBoldCheckbox.checked = typeof pdfSettings.question_bold === 'boolean' ? pdfSettings.question_bold : true;
        uiElements.pdfAppPhotoNumbInput.value = settings.APPLICATION_PHOTO_NUMB === undefined ? 1 : settings.APPLICATION_PHOTO_NUMB;
        uiElements.pdfSendToAdminsToggle.checked = settings.SEND_PDF_TO_ADMINS === undefined ? true : settings.SEND_PDF_TO_ADMINS;

        uiElements.adminBotTokenInput.value = settings.BOT_TOKEN || "";
        uiElements.adminUserIdsInput.value = settings.ADMIN_USER_IDS || "";
    }

    uiElements.editSettingsButton.addEventListener('click', openSettingsModal);
    uiElements.cancelAllSettingsButton.addEventListener('click', closeSettingsModal);

    uiElements.saveAllSettingsButton.addEventListener('click', () => {
        const newMaxLogs = parseInt(uiElements.settingsModalLogLinesInput.value, 10);
        if (!isNaN(newMaxLogs) && newMaxLogs >= 10 && newMaxLogs <= 1000) {
            if (newMaxLogs !== currentMaxLogLines) {
                 if (window.pywebview && window.pywebview.api.set_max_log_lines_from_ui) {
                    window.pywebview.api.set_max_log_lines_from_ui(newMaxLogs.toString());
                }
            }
        } else {
            uiElements.settingsModalLogLinesInput.value = currentMaxLogLines;
        }

        const newLang = uiElements.settingsModalLangToggle.checked ? 'ru' : 'en';
        let languageChangePromise = Promise.resolve(); 
        if (newLang !== currentFetchedSettings.DEFAULT_LANG) {
            if (window.pywebview && window.pywebview.api.set_system_language) {
                languageChangePromise = window.pywebview.api.set_system_language(newLang).then(response => {
                    if (response && response.translations) applyGuiTranslations(response.translations);
                    if (response && response.new_lang) {
                        currentFetchedSettings.DEFAULT_LANG = response.new_lang;
                         setSystemLanguageToggleState(response.new_lang);
                    }
                }).catch(err => console.error("Error setting system language from modal:", err));
            }
        }
        
        languageChangePromise.then(() => {
            const settingsToSave = {
                OVERRIDE_USER_LANG: uiElements.settingsOverrideUserLangToggle.checked,
                APPLICATION_PHOTO_NUMB: parseInt(uiElements.pdfAppPhotoNumbInput.value, 10),
                SEND_PDF_TO_ADMINS: uiElements.pdfSendToAdminsToggle.checked,
                FONT_FILE_PATH: uiElements.pdfFontFilePathInput.value.trim(),
                PDF_SETTINGS: {
                    font_name_registered: uiElements.pdfFontNameRegisteredInput.value.trim(),
                    page_width_mm: parseFloat(uiElements.pdfPageWidthMmInput.value),
                    page_height_mm: parseFloat(uiElements.pdfPageHeightMmInput.value),
                    margin_mm: parseFloat(uiElements.pdfMarginMmInput.value),
                    photo_width_mm: parseFloat(uiElements.pdfPhotoWidthMmInput.value),
                    photo_position: uiElements.pdfPhotoPositionSelect.value,
                    title_font_size: parseInt(uiElements.pdfTitleFontSizeInput.value, 10),
                    header_font_size: parseInt(uiElements.pdfHeaderFontSizeInput.value, 10),
                    question_font_size: parseInt(uiElements.pdfQuestionFontSizeInput.value, 10),
                    answer_font_size: parseInt(uiElements.pdfAnswerFontSizeInput.value, 10),
                    question_bold: uiElements.pdfQuestionBoldCheckbox.checked
                },
                BOT_TOKEN: uiElements.adminBotTokenInput.value.trim(),
                ADMIN_USER_IDS: uiElements.adminUserIdsInput.value.trim()
            };

            if (!settingsToSave.BOT_TOKEN) {
                alert(currentGuiTranslations.gui_alert_bot_token_empty || "Bot Token cannot be empty.");
                uiElements.adminBotTokenInput.focus(); return;
            }
            if (isNaN(settingsToSave.APPLICATION_PHOTO_NUMB) || settingsToSave.APPLICATION_PHOTO_NUMB < 0) {
                alert(currentGuiTranslations.gui_alert_invalid_photo_numb || "Number of photos must be a non-negative number.");
                uiElements.pdfAppPhotoNumbInput.focus(); return;
            }
             if (!settingsToSave.FONT_FILE_PATH) {
                alert(currentGuiTranslations.gui_alert_pdf_font_paths_empty || "Font File Path cannot be empty.");
                uiElements.pdfFontFilePathInput.focus(); return;
            }
            if (!settingsToSave.PDF_SETTINGS.font_name_registered) {
                alert(currentGuiTranslations.gui_alert_pdf_font_paths_empty || "Registered Font Name cannot be empty.");
                uiElements.pdfFontNameRegisteredInput.focus(); return;
            }

            if (window.pywebview && window.pywebview.api.save_all_settings) {
                window.pywebview.api.save_all_settings(settingsToSave).then(success => {
                    if (success) {
                        alert(currentGuiTranslations.gui_alert_settings_saved || "Settings saved successfully! Some changes may require a bot restart.");
                        closeSettingsModal();
                    } else {
                        alert(currentGuiTranslations.gui_alert_settings_save_failed || "Failed to save some settings. Check logs for details.");
                    }
                }).catch(err => {
                    alert((currentGuiTranslations.gui_alert_settings_save_error || "Error saving settings: {error}").replace('{error}', String(err)));
                });
            } else {
                alert("Error: UI cannot connect to Python to save settings.");
            }
        });
    });

    window.initializeGui = function(config) {
        console.log("Initializing GUI with config:", config);
        if (config.guiTranslations) {
            applyGuiTranslations(config.guiTranslations); // This will now also set button titles
        }
        if (config.currentLang) {
             currentFetchedSettings.DEFAULT_LANG = config.currentLang; 
             setSystemLanguageToggleState(config.currentLang);
        }

        currentMaxLogLines = config.maxLogLines || 100;
        if(uiElements.settingsModalLogLinesInput) uiElements.settingsModalLogLinesInput.value = currentMaxLogLines;

        if (config.initialLogs && config.initialLogs.length > 0) addBatchLogMessages(config.initialLogs);

        const savedTheme = localStorage.getItem('selectedTheme') || 'default-dark';
        applyTheme(savedTheme);
    };

    window.addEventListener('pywebviewready', function () {
        if (window.pywebview && window.pywebview.api.frontend_is_ready) {
            window.pywebview.api.frontend_is_ready();
        } else {
            if(uiElements.statusDisplayLabelPrefix) uiElements.statusDisplayLabelPrefix.textContent = "Status: ";
            if(uiElements.statusMessageContent) uiElements.statusMessageContent.textContent = "Error: UI failed to connect to Python.";
            const statusDisplayDiv = document.getElementById('status-display');
            if(statusDisplayDiv) statusDisplayDiv.classList.add('error');
        }
    });
});