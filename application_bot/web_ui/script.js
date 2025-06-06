document.addEventListener('DOMContentLoaded', function () {
    // Element Cache
    const uiElements = {
        startButton: document.getElementById('start-button'),
        stopButton: document.getElementById('stop-button'),
        openApplicationsFolderButton: document.getElementById('open-applications-folder-button'),
        editQuestionsButton: document.getElementById('edit-questions-button'),

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
        settingsModalLogoSelect: document.getElementById('settings-modal-logo-select'), // Added
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
        themeLinkNavy: document.getElementById('theme-link-navy'),

        // Info and Settings Buttons
        helpButton: document.getElementById('help-button'),
        aboutButton: document.getElementById('about-button'),
        settingsIconButton: document.getElementById('settings-icon-button'),

        // Generic Info Modal Elements
        infoModal: document.getElementById('info-modal'),
        infoModalTitle: document.getElementById('info-modal-title'),
        infoModalBody: document.getElementById('info-modal-body'),
        infoModalCloseButton: document.getElementById('info-modal-close-button')
    };

    let currentMaxLogLines = 100;
    let currentGuiTranslations = {};
    let statusPrefix = "Status: ";
    let currentQuestionsData = [];
    let currentFetchedSettings = { THEME: 'default-dark', DEFAULT_LANG: 'en', SELECTED_LOGO: 'default' };

    function applyTheme(themeValue) {
        if (!themeValue) themeValue = 'default-dark'; 

        if (uiElements.mainStyleSheet) uiElements.mainStyleSheet.disabled = true;
        if (uiElements.themeLinkMemphis) uiElements.themeLinkMemphis.disabled = true;
        if (uiElements.themeLinkAurora) uiElements.themeLinkAurora.disabled = true;
        if (uiElements.themeLinkNavy) uiElements.themeLinkNavy.disabled = true;

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
            case 'navy-formal':
                if (uiElements.themeLinkNavy) uiElements.themeLinkNavy.disabled = false;
                document.body.classList.add('navy-formal-theme');
                break;
            default: 
                if (uiElements.mainStyleSheet) uiElements.mainStyleSheet.disabled = false;
                document.body.classList.add('dark-mode');
                themeValue = 'default-dark';
                break;
        }
        localStorage.setItem('selectedTheme', themeValue); 
        if(uiElements.settingsModalThemeSelect) uiElements.settingsModalThemeSelect.value = themeValue;
        currentFetchedSettings.THEME = themeValue; 
    }
    
    applyTheme(localStorage.getItem('selectedTheme'));
    
    function applyLogo(logoKey) {
        if (!logoKey) logoKey = 'default';
        let logoFilename = 'logo.png'; // Default
        if (logoKey === 'abc') {
            logoFilename = 'logo_abc.png';
        } else if (logoKey === 'zaya') {
            logoFilename = 'logo_zaya.png';
        }
        if (uiElements.logoImage) {
            uiElements.logoImage.src = `${logoFilename}?t=${new Date().getTime()}`;
        }
        currentFetchedSettings.SELECTED_LOGO = logoKey; 
    }

    if (uiElements.settingsModalThemeSelect) {
        uiElements.settingsModalThemeSelect.addEventListener('change', function () {
            applyTheme(this.value); 
        });
    }

    if (uiElements.settingsModalLogoSelect) { // Added event listener for logo select
        uiElements.settingsModalLogoSelect.addEventListener('change', function () {
            applyLogo(this.value);
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
                    if (!el.classList.contains('icon-button') && el.id !== 'info-modal-close-button') { 
                        el.textContent = translations[key];
                    } else if (el.id === 'info-modal-close-button') {
                        el.textContent = translations.gui_modal_info_ok_button || "OK";
                    }
                } else if (el.tagName === 'LABEL' || el.tagName === 'H2' || el.tagName === 'TH' || el.id === 'gui_title_text') {
                     el.textContent = translations[key];
                }
            }
        });

        if (uiElements.questionsModal.style.display === 'flex') {
            populateQuestionsTable(currentQuestionsData);
        }

        if (uiElements.helpButton) uiElements.helpButton.title = currentGuiTranslations.gui_help_button_title || "Help";
        if (uiElements.aboutButton) uiElements.aboutButton.title = currentGuiTranslations.gui_about_button_title || "About";
        if (uiElements.settingsIconButton) uiElements.settingsIconButton.title = currentGuiTranslations.gui_settings_button_title || "Settings";
        if (uiElements.infoModalCloseButton) uiElements.infoModalCloseButton.textContent = currentGuiTranslations.gui_modal_info_ok_button || "OK";
    };

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
    
    function showInfoModal(title, message) {
        if(uiElements.infoModalTitle) uiElements.infoModalTitle.textContent = title;
        if(uiElements.infoModalBody) uiElements.infoModalBody.textContent = message;
        if(uiElements.infoModal) uiElements.infoModal.style.display = 'flex';
        if(uiElements.infoModalCloseButton) uiElements.infoModalCloseButton.focus();
    }

    if (uiElements.infoModalCloseButton) {
        uiElements.infoModalCloseButton.addEventListener('click', () => {
            if(uiElements.infoModal) uiElements.infoModal.style.display = 'none';
        });
    }
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && uiElements.infoModal && uiElements.infoModal.style.display === 'flex') {
            uiElements.infoModal.style.display = 'none';
        }
    });


    if (uiElements.helpButton) {
        uiElements.helpButton.addEventListener('click', () => {
            const helpTitle = currentGuiTranslations.gui_help_modal_title || "Help";
            const helpMessage = currentGuiTranslations.gui_help_modal_content || "Help content not loaded.";
            showInfoModal(helpTitle, helpMessage);
        });
    }

    if (uiElements.aboutButton) {
        uiElements.aboutButton.addEventListener('click', () => {
            const aboutTitle = currentGuiTranslations.gui_about_modal_title || "About";
            const aboutMessage = currentGuiTranslations.gui_about_modal_content || "About content not loaded.";
            showInfoModal(aboutTitle, aboutMessage);
        });
    }

    if (uiElements.settingsIconButton) {
        uiElements.settingsIconButton.addEventListener('click', () => {
            openSettingsModal();
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
                    showInfoModal(
                        currentGuiTranslations.gui_alert_questions_saved_title || "Questions Updated",
                        currentGuiTranslations.gui_alert_questions_saved || "Questions saved successfully!"
                    );
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
                currentFetchedSettings = settings || { THEME: 'default-dark', DEFAULT_LANG: 'en', SELECTED_LOGO: 'default' };
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
        
        uiElements.settingsModalThemeSelect.value = settings.THEME || 'default-dark';
        applyTheme(settings.THEME || 'default-dark'); 

        uiElements.settingsModalLogoSelect.value = settings.SELECTED_LOGO || 'default'; // Added
        applyLogo(settings.SELECTED_LOGO || 'default'); // Added: Apply logo when modal opens

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
                THEME: uiElements.settingsModalThemeSelect.value, 
                SELECTED_LOGO: uiElements.settingsModalLogoSelect.value, // Added
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
                        showInfoModal(
                            currentGuiTranslations.gui_alert_settings_saved_title || "Settings Update",
                            currentGuiTranslations.gui_alert_settings_saved || "Settings saved successfully! Some changes may require a bot restart."
                        );
                        closeSettingsModal();
                        currentFetchedSettings.THEME = settingsToSave.THEME; 
                        currentFetchedSettings.SELECTED_LOGO = settingsToSave.SELECTED_LOGO; // Update after successful save
                        applyLogo(settingsToSave.SELECTED_LOGO); // Apply the saved logo
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
            applyGuiTranslations(config.guiTranslations); 
        }
        if (config.currentLang) {
             currentFetchedSettings.DEFAULT_LANG = config.currentLang; 
             setSystemLanguageToggleState(config.currentLang);
        }
        
        const themeFromPython = config.currentTheme || 'default-dark';
        currentFetchedSettings.THEME = themeFromPython;
        applyTheme(themeFromPython); 

        const logoFromPython = config.currentLogo || 'default'; // Added
        currentFetchedSettings.SELECTED_LOGO = logoFromPython; // Added
        applyLogo(logoFromPython); // Added
        if (uiElements.settingsModalLogoSelect) uiElements.settingsModalLogoSelect.value = logoFromPython; // Added


        currentMaxLogLines = config.maxLogLines || 100;
        if(uiElements.settingsModalLogLinesInput) uiElements.settingsModalLogLinesInput.value = currentMaxLogLines;

        if (config.initialLogs && config.initialLogs.length > 0) addBatchLogMessages(config.initialLogs);
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