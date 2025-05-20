document.addEventListener('DOMContentLoaded', function () {
    // Element Cache
    const uiElements = {
        startButton: document.getElementById('start-button'),
        stopButton: document.getElementById('stop-button'),
        openApplicationsFolderButton: document.getElementById('open-applications-folder-button'),
        editQuestionsButton: document.getElementById('edit-questions-button'), // New
        statusDisplayLabelPrefix: document.getElementById('gui_status_label_prefix'),
        statusMessageContent: document.getElementById('status-message-content'),
        logOutput: document.getElementById('log-output'),
        logLinesInput: document.getElementById('log-lines-input'),
        darkModeToggle: document.getElementById('dark-mode-toggle'),
        langToggle: document.getElementById('lang-toggle'),
        guiTitleText: document.getElementById('gui_title_text'), 
        guiLogLinesLabel: document.getElementById('gui_log_lines_label'),
        guiDarkThemeLabel: document.getElementById('gui_dark_theme_label'),
        guiLangToggleLabel: document.getElementById('gui_lang_toggle_label'),
        logoImage: document.getElementById('logo'),
        // Questions Modal Elements
        questionsModal: document.getElementById('questions-modal'),
        questionsTableBody: document.getElementById('questions-table').getElementsByTagName('tbody')[0],
        addQuestionButton: document.getElementById('add-question-button'),
        saveQuestionsButton: document.getElementById('save-questions-button'),
        cancelQuestionsButton: document.getElementById('cancel-questions-button'),
        guiModalQuestionsTitle: document.getElementById('gui_modal_questions_title')
    };

    let currentMaxLogLines = 100;
    let currentGuiTranslations = {}; 
    let statusPrefix = "Status: "; 
    let currentQuestionsData = []; // For questions editing

    if (uiElements.logoImage) {
        const originalSrc = uiElements.logoImage.getAttribute('src');
        if (originalSrc) {
            const basePath = originalSrc.split('?')[0];
            uiElements.logoImage.src = `${basePath}?t=${new Date().getTime()}`;
            console.log("Updated logo src to (cache-busted):", uiElements.logoImage.src);
        }
    }

    function applyTheme(isDark) {
        document.body.classList.toggle('dark-mode', isDark);
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
        
        // Translate all elements with data-i18n-key attribute
        document.querySelectorAll('[data-i18n-key]').forEach(el => {
            const key = el.dataset.i18nKey;
            if (translations[key]) {
                if (el.tagName === 'INPUT' && el.type === 'button' || el.tagName === 'BUTTON') {
                    el.textContent = translations[key]; // For buttons
                } else if (el.tagName === 'LABEL' || el.tagName === 'H2' || el.tagName === 'TH' || el.id === 'gui_title_text') {
                     el.textContent = translations[key]; // For labels, headings, table headers, title
                }
                // Add more conditions if other element types need translation
            }
        });
        // Special handling for elements not easily covered by data-i18n-key or if it was missed
        if (translations.gui_start_button) uiElements.startButton.textContent = translations.gui_start_button;
        if (translations.gui_stop_button) uiElements.stopButton.textContent = translations.gui_stop_button;
        if (translations.gui_open_folder_button) uiElements.openApplicationsFolderButton.textContent = translations.gui_open_folder_button;
        if (translations.gui_edit_questions_button) uiElements.editQuestionsButton.textContent = translations.gui_edit_questions_button;
        if (translations.gui_log_lines_label) uiElements.guiLogLinesLabel.textContent = translations.gui_log_lines_label;
        if (translations.gui_dark_theme_label) uiElements.guiDarkThemeLabel.textContent = translations.gui_dark_theme_label;
        if (translations.gui_lang_toggle_label) uiElements.guiLangToggleLabel.textContent = translations.gui_lang_toggle_label;
        if (translations.gui_modal_questions_title) uiElements.guiModalQuestionsTitle.textContent = translations.gui_modal_questions_title;
        if (translations.gui_modal_add_question_button) uiElements.addQuestionButton.textContent = translations.gui_modal_add_question_button;
        if (translations.gui_modal_save_button) uiElements.saveQuestionsButton.textContent = translations.gui_modal_save_button;
        if (translations.gui_modal_cancel_button) uiElements.cancelQuestionsButton.textContent = translations.gui_modal_cancel_button;


        // Re-populate table if modal is open to update delete button text
        if (uiElements.questionsModal.style.display === 'flex') {
            populateQuestionsTable(currentQuestionsData);
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
        } else {
            console.error("PyWebview API not available for set_system_language");
        }
    });

    window.setSystemLanguageToggleState = function(langCode) {
        uiElements.langToggle.checked = (langCode === 'ru');
    };

    uiElements.startButton.addEventListener('click', () => {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.start_bot_action) {
            window.pywebview.api.start_bot_action();
        } else {
            console.error("PyWebview API not available for start_bot_action");
            updateStatus("gui_status_error_ui_disconnected", true, null, false); 
        }
    });

    uiElements.stopButton.addEventListener('click', () => {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.stop_bot_action) {
            window.pywebview.api.stop_bot_action();
        } else {
            console.error("PyWebview API not available for stop_bot_action");
            updateStatus("gui_status_error_ui_disconnected", true, null, false); 
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
                window.pywebview.api.set_max_log_lines_from_ui(newMax.toString()); 
            }
        } else {
            this.value = currentMaxLogLines; 
        }
    });

    window.updateStatus = function (messageKeyOrText, isError = false, isRunning = null, isRawText = false) {
        let messageToDisplay;
        if (isRawText) {
            messageToDisplay = messageKeyOrText;
        } else {
            messageToDisplay = currentGuiTranslations[messageKeyOrText] || messageKeyOrText.replace(/_/g, ' '); 
        }
        
        uiElements.statusMessageContent.textContent = messageToDisplay;
        const statusDisplayDiv = document.getElementById('status-display');
        statusDisplayDiv.classList.remove('running', 'stopped', 'error', 'intermediate');

        if (isError) { 
            statusDisplayDiv.classList.add('error');
        } else if (isRunning === true) {
            statusDisplayDiv.classList.add('running');
        } else if (isRunning === false) {
            statusDisplayDiv.classList.add('stopped');
        } else if (isRunning === null) { 
             statusDisplayDiv.classList.add('intermediate');
        }
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

    // --- Questions Modal Logic ---
    function openQuestionsModal() {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.get_questions) {
            window.pywebview.api.get_questions().then(questions => {
                currentQuestionsData = JSON.parse(JSON.stringify(questions || [])); // Deep copy
                populateQuestionsTable(currentQuestionsData);
                uiElements.questionsModal.style.display = 'flex';
            }).catch(err => {
                console.error("Error fetching questions:", err);
                alert("Could not load questions for editing.");
            });
        } else {
            console.error("PyWebview API not available for get_questions");
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
        currentQuestionsData.push({ id: `new_q_${Date.now()}`, text: '' }); // Use timestamp for temp unique ID
        populateQuestionsTable(currentQuestionsData);
        // Scroll to the new row if table is scrollable
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

            idInput.style.borderColor = ''; // Reset border
            textInput.style.borderColor = '';

            if (!id || !text) {
                alert((currentGuiTranslations.gui_alert_question_empty_fields || "Question ID and Text cannot be empty. Please fill all fields for row {row_num}.").replace('{row_num}', i + 1));
                if(!id) idInput.style.borderColor = 'red';
                if(!text) textInput.style.borderColor = 'red';
                hasError = true;
                break; 
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

        if (window.pywebview && window.pywebview.api && window.pywebview.api.save_questions) {
            window.pywebview.api.save_questions(updatedQuestions).then(success => {
                if (success) {
                    alert(currentGuiTranslations.gui_alert_questions_saved || "Questions saved successfully!");
                    closeQuestionsModal();
                } else {
                    alert(currentGuiTranslations.gui_alert_questions_save_failed || "Failed to save questions. Check logs.");
                }
            }).catch(err => {
                console.error("Error saving questions:", err);
                alert((currentGuiTranslations.gui_alert_questions_save_error || "Error saving questions: {error}").replace('{error}', String(err)));
            });
        } else {
            console.error("PyWebview API not available for save_questions");
            alert("Error: UI cannot connect to Python to save questions.");
        }
    });
    // --- End Questions Modal Logic ---

    window.initializeGui = function(config) {
        console.log("Initializing GUI with config:", config);
        
        if (config.guiTranslations) {
            applyGuiTranslations(config.guiTranslations);
        }
        if (config.currentLang) {
            setSystemLanguageToggleState(config.currentLang);
        }
        
        currentMaxLogLines = config.maxLogLines || 100;
        uiElements.logLinesInput.value = currentMaxLogLines;

        if (config.initialLogs && config.initialLogs.length > 0) {
            addBatchLogMessages(config.initialLogs);
        }

        const savedDarkMode = localStorage.getItem('darkMode');
        const isDark = (savedDarkMode !== null) ? (savedDarkMode === 'true') : true; 
        uiElements.darkModeToggle.checked = isDark;
        applyTheme(isDark);
    };

    window.addEventListener('pywebviewready', function () {
        console.log("PyWebview ready, notifying Python backend.");
        if (window.pywebview && window.pywebview.api && window.pywebview.api.frontend_is_ready) {
            window.pywebview.api.frontend_is_ready();
        } else {
            console.error("PyWebview API not available for frontend_is_ready call.");
            uiElements.statusDisplayLabelPrefix.textContent = "Status: ";
            uiElements.statusMessageContent.textContent = "Error: UI failed to connect to Python.";
            document.getElementById('status-display').classList.add('error');
        }
    });
});