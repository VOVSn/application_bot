document.addEventListener('DOMContentLoaded', function () {
    // Element Cache
    const uiElements = {
        startButton: document.getElementById('start-button'),
        stopButton: document.getElementById('stop-button'),
        openApplicationsFolderButton: document.getElementById('open-applications-folder-button'),
        editQuestionsButton: document.getElementById('edit-questions-button'),
        editPdfSettingsButton: document.getElementById('edit-pdf-settings-button'), // New
        statusDisplayLabelPrefix: document.getElementById('gui_status_label_prefix'),
        statusMessageContent: document.getElementById('status-message-content'),
        logOutput: document.getElementById('log-output'),
        logLinesInput: document.getElementById('log-lines-input'),
        darkModeToggle: document.getElementById('dark-mode-toggle'),
        langToggle: document.getElementById('lang-toggle'),
        guiTitleText: document.getElementById('gui_title_text'), 
        logoImage: document.getElementById('logo'),
        // Questions Modal Elements
        questionsModal: document.getElementById('questions-modal'),
        questionsTableBody: document.getElementById('questions-table').getElementsByTagName('tbody')[0],
        addQuestionButton: document.getElementById('add-question-button'),
        saveQuestionsButton: document.getElementById('save-questions-button'),
        cancelQuestionsButton: document.getElementById('cancel-questions-button'),
        // PDF Settings Modal Elements
        pdfSettingsModal: document.getElementById('pdf-settings-modal'),
        savePdfSettingsButton: document.getElementById('save-pdf-settings-button'),
        cancelPdfSettingsButton: document.getElementById('cancel-pdf-settings-button'),
        // PDF Settings Form Inputs
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
    };

    let currentMaxLogLines = 100;
    let currentGuiTranslations = {}; 
    let statusPrefix = "Status: "; 
    let currentQuestionsData = []; 
    let currentPdfSettings = {}; // For PDF settings editing

    if (uiElements.logoImage) {
        const originalSrc = uiElements.logoImage.getAttribute('src');
        if (originalSrc) {
            const basePath = originalSrc.split('?')[0];
            uiElements.logoImage.src = `${basePath}?t=${new Date().getTime()}`;
        }
    }

    function applyTheme(isDark) {
        document.body.classList.toggle('dark-mode', isDark);
        document.body.classList.toggle('light-mode', !isDark); // For specific light/dark modal input styling
    }

    uiElements.darkModeToggle.addEventListener('change', function () {
        const isDark = this.checked;
        applyTheme(isDark);
        localStorage.setItem('darkMode', isDark.toString());
    });

    window.applyGuiTranslations = function(translations) {
        currentGuiTranslations = translations; 
        statusPrefix = translations.gui_status_label_prefix || "Status: ";
        uiElements.statusDisplayLabelPrefix.textContent = statusPrefix;

        document.title = translations.gui_title_text || "Application Bot Control";
        
        document.querySelectorAll('[data-i18n-key]').forEach(el => {
            const key = el.dataset.i18nKey;
            if (translations[key]) {
                if (el.tagName === 'OPTION') {
                    el.textContent = translations[key];
                } else if (el.tagName === 'INPUT' && el.type === 'button' || el.tagName === 'BUTTON') {
                    el.textContent = translations[key]; 
                } else if (el.tagName === 'LABEL' || el.tagName === 'H2' || el.tagName === 'TH' || el.id === 'gui_title_text') {
                     el.textContent = translations[key]; 
                }
            }
        });
        
        if (uiElements.questionsModal.style.display === 'flex') {
            populateQuestionsTable(currentQuestionsData); // Re-translate delete buttons
        }
    };

    uiElements.langToggle.addEventListener('change', function() {
        const newLang = this.checked ? 'ru' : 'en'; 
        if (window.pywebview && window.pywebview.api && window.pywebview.api.set_system_language) {
            window.pywebview.api.set_system_language(newLang).then(response => {
                if (response && response.translations) {
                    applyGuiTranslations(response.translations);
                }
                if (response && response.new_lang) {
                     uiElements.langToggle.checked = (response.new_lang === 'ru');
                }
            }).catch(err => console.error("Error setting system language:", err));
        }
    });

    window.setSystemLanguageToggleState = function(langCode) {
        uiElements.langToggle.checked = (langCode === 'ru');
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

    uiElements.logLinesInput.addEventListener('change', function() {
        const newMax = parseInt(this.value, 10);
        if (!isNaN(newMax) && newMax >= 10 && newMax <= 1000) {
            if (window.pywebview && window.pywebview.api.set_max_log_lines_from_ui) {
                window.pywebview.api.set_max_log_lines_from_ui(newMax.toString()); 
            }
        } else {
            this.value = currentMaxLogLines; 
        }
    });

    window.updateStatus = function (messageKeyOrText, isError = false, isRunning = null, isRawText = false) {
        let messageToDisplay = isRawText ? messageKeyOrText : (currentGuiTranslations[messageKeyOrText] || messageKeyOrText.replace(/_/g, ' '));
        uiElements.statusMessageContent.textContent = messageToDisplay;
        const statusDisplayDiv = document.getElementById('status-display');
        statusDisplayDiv.className = 'status-display'; // Reset classes
        if (isError) statusDisplayDiv.classList.add('error');
        else if (isRunning === true) statusDisplayDiv.classList.add('running');
        else if (isRunning === false) statusDisplayDiv.classList.add('stopped');
        else if (isRunning === null) statusDisplayDiv.classList.add('intermediate');
    };
    
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
        const button = document.getElementById(buttonId);
        if (button) button.disabled = !enabled;
    };
    
    window.setLogLinesConfig = function(maxLines, currentLogs = []) {
        currentMaxLogLines = parseInt(maxLines, 10);
        uiElements.logLinesInput.value = currentMaxLogLines; 
        clearLogs();
        if (currentLogs && currentLogs.length > 0) addBatchLogMessages(currentLogs); 
    };

    window.clearLogs = function() { uiElements.logOutput.innerHTML = ''; };

    // --- Questions Modal Logic ---
    function openQuestionsModal() {
        if (window.pywebview && window.pywebview.api.get_questions) {
            window.pywebview.api.get_questions().then(questions => {
                currentQuestionsData = JSON.parse(JSON.stringify(questions || [])); 
                populateQuestionsTable(currentQuestionsData);
                uiElements.questionsModal.style.display = 'flex';
            }).catch(err => alert("Could not load questions for editing."));
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
            row.insertCell().innerHTML = `<input type="text" class="neumorphic-input" value="${q.id || ''}" placeholder="unique_question_id">`;
            row.insertCell().innerHTML = `<input type="text" class="neumorphic-input" value="${q.text || ''}" placeholder="Question text...">`;
            const actionsCell = row.insertCell();
            const deleteButton = document.createElement('button');
            deleteButton.textContent = currentGuiTranslations.gui_modal_delete_button || 'Delete';
            deleteButton.classList.add('neumorphic-button', 'action-button', 'modal-button');
            deleteButton.onclick = () => deleteQuestionRow(index);
            actionsCell.appendChild(deleteButton);
        });
    }
    function deleteQuestionRow(index) {
        currentQuestionsData.splice(index, 1); 
        populateQuestionsTable(currentQuestionsData); 
    }
    uiElements.editQuestionsButton.addEventListener('click', openQuestionsModal);
    uiElements.cancelQuestionsButton.addEventListener('click', closeQuestionsModal);
    uiElements.addQuestionButton.addEventListener('click', () => {
        currentQuestionsData.push({ id: `new_q_${Date.now()}`, text: '' }); 
        populateQuestionsTable(currentQuestionsData);
        const tableContainer = document.querySelector('.questions-table-container');
        if (tableContainer) tableContainer.scrollTop = tableContainer.scrollHeight;
    });
    uiElements.saveQuestionsButton.addEventListener('click', () => {
        const updatedQuestions = [];
        const rows = uiElements.questionsTableBody.rows;
        let hasError = false;
        for (let i = 0; i < rows.length; i++) {
            const idInput = rows[i].cells[0].querySelector('input');
            const textInput = rows[i].cells[1].querySelector('input');
            const id = idInput.value.trim();
            const text = textInput.value.trim();
            idInput.style.borderColor = ''; textInput.style.borderColor = '';
            if (!id || !text) {
                alert((currentGuiTranslations.gui_alert_question_empty_fields || "Question ID and Text cannot be empty. Please fill all fields for row {row_num}.").replace('{row_num}', i + 1));
                if(!id) idInput.style.borderColor = 'red'; if(!text) textInput.style.borderColor = 'red';
                hasError = true; break; 
            }
            updatedQuestions.push({ id: id, text: text });
        }
        if (hasError) return;
        const ids = updatedQuestions.map(q => q.id);
        const duplicateIds = ids.filter((item, index) => ids.indexOf(item) !== index);
        if (duplicateIds.length > 0) {
            alert((currentGuiTranslations.gui_alert_duplicate_ids || "Duplicate question IDs found: {ids}. IDs must be unique.").replace('{ids}', duplicateIds.join(', ')));
            return;
        }
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

    // --- PDF Settings Modal Logic ---
    function openPdfSettingsModal() {
        if (window.pywebview && window.pywebview.api.get_pdf_settings) {
            window.pywebview.api.get_pdf_settings().then(settings => {
                currentPdfSettings = settings || {}; // Store for potential reset/validation
                populatePdfSettingsForm(currentPdfSettings);
                uiElements.pdfSettingsModal.style.display = 'flex';
            }).catch(err => {
                console.error("Error fetching PDF settings:", err);
                alert(currentGuiTranslations.gui_alert_pdf_settings_load_failed || "Could not load PDF settings for editing.");
            });
        } else {
            alert("Error: UI cannot connect to Python to get PDF settings.");
        }
    }

    function closePdfSettingsModal() {
        uiElements.pdfSettingsModal.style.display = 'none';
    }

    function populatePdfSettingsForm(settings) {
        const pdfSettings = settings.PDF_SETTINGS || {}; // Nested object
        uiElements.pdfFontFilePathInput.value = settings.FONT_FILE_PATH || "fonts/DejaVuSans.ttf";
        uiElements.pdfFontNameRegisteredInput.value = pdfSettings.font_name_registered || "CustomUnicodeFont";
        uiElements.pdfPageWidthMmInput.value = pdfSettings.page_width_mm || 210;
        uiElements.pdfPageHeightMmInput.value = pdfSettings.page_height_mm || 297;
        uiElements.pdfMarginMmInput.value = pdfSettings.margin_mm || 15;
        uiElements.pdfPhotoWidthMmInput.value = pdfSettings.photo_width_mm || 80;
        uiElements.pdfPhotoPositionSelect.value = pdfSettings.photo_position || "top_right";
        uiElements.pdfTitleFontSizeInput.value = pdfSettings.title_font_size || 16;
        uiElements.pdfHeaderFontSizeInput.value = pdfSettings.header_font_size || 10;
        uiElements.pdfQuestionFontSizeInput.value = pdfSettings.question_font_size || 12;
        uiElements.pdfAnswerFontSizeInput.value = pdfSettings.answer_font_size || 10;
        uiElements.pdfQuestionBoldCheckbox.checked = typeof pdfSettings.question_bold === 'boolean' ? pdfSettings.question_bold : true;
    }
    
    uiElements.editPdfSettingsButton.addEventListener('click', openPdfSettingsModal);
    uiElements.cancelPdfSettingsButton.addEventListener('click', closePdfSettingsModal);

    uiElements.savePdfSettingsButton.addEventListener('click', () => {
        const newSettings = {
            FONT_FILE_PATH: uiElements.pdfFontFilePathInput.value.trim(),
            PDF_SETTINGS: {
                font_name_registered: uiElements.pdfFontNameRegisteredInput.value.trim(),
                page_width_mm: parseFloat(uiElements.pdfPageWidthMmInput.value) || 210,
                page_height_mm: parseFloat(uiElements.pdfPageHeightMmInput.value) || 297,
                margin_mm: parseFloat(uiElements.pdfMarginMmInput.value) || 15,
                photo_width_mm: parseFloat(uiElements.pdfPhotoWidthMmInput.value) || 80,
                photo_position: uiElements.pdfPhotoPositionSelect.value,
                title_font_size: parseInt(uiElements.pdfTitleFontSizeInput.value, 10) || 16,
                header_font_size: parseInt(uiElements.pdfHeaderFontSizeInput.value, 10) || 10,
                question_font_size: parseInt(uiElements.pdfQuestionFontSizeInput.value, 10) || 12,
                answer_font_size: parseInt(uiElements.pdfAnswerFontSizeInput.value, 10) || 10,
                question_bold: uiElements.pdfQuestionBoldCheckbox.checked
            }
        };

        // Basic validation (can be more extensive)
        if (!newSettings.FONT_FILE_PATH || !newSettings.PDF_SETTINGS.font_name_registered) {
            alert(currentGuiTranslations.gui_alert_pdf_font_paths_empty || "Font File Path and Registered Font Name cannot be empty.");
            return;
        }

        if (window.pywebview && window.pywebview.api.save_pdf_settings) {
            window.pywebview.api.save_pdf_settings(newSettings).then(success => {
                if (success) {
                    alert(currentGuiTranslations.gui_alert_pdf_settings_saved || "PDF settings saved successfully!");
                    closePdfSettingsModal();
                } else {
                    alert(currentGuiTranslations.gui_alert_pdf_settings_save_failed || "Failed to save PDF settings. Check logs.");
                }
            }).catch(err => {
                alert((currentGuiTranslations.gui_alert_pdf_settings_save_error || "Error saving PDF settings: {error}").replace('{error}', String(err)));
            });
        } else {
            alert("Error: UI cannot connect to Python to save PDF settings.");
        }
    });
    // --- End PDF Settings Modal Logic ---

    window.initializeGui = function(config) {
        console.log("Initializing GUI with config:", config);
        if (config.guiTranslations) applyGuiTranslations(config.guiTranslations);
        if (config.currentLang) setSystemLanguageToggleState(config.currentLang);
        currentMaxLogLines = config.maxLogLines || 100;
        uiElements.logLinesInput.value = currentMaxLogLines;
        if (config.initialLogs && config.initialLogs.length > 0) addBatchLogMessages(config.initialLogs);
        const savedDarkMode = localStorage.getItem('darkMode');
        const isDark = (savedDarkMode !== null) ? (savedDarkMode === 'true') : true; 
        uiElements.darkModeToggle.checked = isDark;
        applyTheme(isDark); // Apply theme after setting checkbox
    };

    window.addEventListener('pywebviewready', function () {
        if (window.pywebview && window.pywebview.api.frontend_is_ready) {
            window.pywebview.api.frontend_is_ready();
        } else {
            uiElements.statusDisplayLabelPrefix.textContent = "Status: ";
            uiElements.statusMessageContent.textContent = "Error: UI failed to connect to Python.";
            document.getElementById('status-display').classList.add('error');
        }
    });
});