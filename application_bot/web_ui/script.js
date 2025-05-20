document.addEventListener('DOMContentLoaded', function () {
    const startButton = document.getElementById('start-button');
    const stopButton = document.getElementById('stop-button');
    const openApplicationsFolderButton = document.getElementById('open-applications-folder-button'); // New
    const statusDisplay = document.getElementById('status-display');
    const logOutput = document.getElementById('log-output');
    const logLinesInput = document.getElementById('log-lines-input');
    const darkModeToggle = document.getElementById('dark-mode-toggle');

    let currentMaxLogLines = 100; // Will be updated from Python

    // --- Theme Handling ---
    function applyTheme(isDark) {
        if (isDark) {
            document.body.classList.add('dark-mode');
        } else {
            document.body.classList.remove('dark-mode');
        }
    }

    darkModeToggle.addEventListener('change', function () {
        const isDark = this.checked;
        applyTheme(isDark);
        localStorage.setItem('darkMode', isDark);
        if (window.pywebview && window.pywebview.api) {
            // Optional: notify Python about theme change if needed for some reason
            // window.pywebview.api.set_theme(isDark ? 'dark' : 'light');
        }
    });

    // Load saved theme
    const savedDarkMode = localStorage.getItem('darkMode');
    if (savedDarkMode !== null) {
        const isDark = savedDarkMode === 'true';
        darkModeToggle.checked = isDark;
        applyTheme(isDark);
    } else {
        applyTheme(darkModeToggle.checked); // Apply default
    }


    // --- Bot Controls ---
    startButton.addEventListener('click', () => {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.start_bot_action) {
            window.pywebview.api.start_bot_action();
        } else {
            console.error("PyWebview API not available for start_bot_action");
            updateStatus("Error: UI disconnected", true, true);
        }
    });

    stopButton.addEventListener('click', () => {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.stop_bot_action) {
            window.pywebview.api.stop_bot_action();
        } else {
            console.error("PyWebview API not available for stop_bot_action");
            updateStatus("Error: UI disconnected", true, true);
        }
    });

    openApplicationsFolderButton.addEventListener('click', () => { // New event listener
        if (window.pywebview && window.pywebview.api && window.pywebview.api.open_applications_folder) {
            window.pywebview.api.open_applications_folder();
        } else {
            console.error("PyWebview API not available for open_applications_folder");
            // You could display an error in the statusDisplay if you want
            // updateStatus("Error: UI disconnected, cannot open folder", true);
        }
    });

    logLinesInput.addEventListener('change', function() {
        const newMax = parseInt(this.value, 10);
        if (!isNaN(newMax) && newMax >= 10 && newMax <= 1000) {
            if (window.pywebview && window.pywebview.api && window.pywebview.api.set_max_log_lines_from_ui) {
                window.pywebview.api.set_max_log_lines_from_ui(newMax);
            } else {
                 console.error("PyWebview API not available for set_max_log_lines_from_ui");
            }
        } else {
            // Restore previous valid value or default if API not ready
            this.value = currentMaxLogLines; 
        }
    });


    // --- Functions callable by Python ---
    window.updateStatus = function (message, isError = false, isRunning = null) {
        statusDisplay.textContent = `Status: ${message}`;
        statusDisplay.classList.remove('running', 'stopped', 'error');
        if (isRunning === true) { // Explicitly running
            statusDisplay.classList.add('running');
        } else if (isRunning === false) { // Explicitly stopped
            statusDisplay.classList.add('stopped');
        } else { // Infer from error
             if (isError) {
                statusDisplay.classList.add('error');
            } else if (message.toLowerCase().includes("running")) {
                 statusDisplay.classList.add('running');
            } else if (message.toLowerCase().includes("stopped") || message.toLowerCase().includes("initializing")) {
                 statusDisplay.classList.add('stopped');
            }
        }
    };

    window.addLogMessage = function (htmlMessage) {
        const logEntry = document.createElement('div');
        // Assuming htmlMessage is already escaped and formatted by Python if needed.
        // For simplicity, treating it as plain text here, but can set innerHTML if Python sends HTML.
        logEntry.textContent = htmlMessage; 
        logOutput.appendChild(logEntry);

        // Prune old log entries if over limit
        while (logOutput.children.length > currentMaxLogLines) {
            logOutput.removeChild(logOutput.firstChild);
        }
        logOutput.scrollTop = logOutput.scrollHeight; // Auto-scroll
    };
    
    window.addBatchLogMessages = function(messagesArray) {
        const fragment = document.createDocumentFragment();
        messagesArray.forEach(msg => {
            const logEntry = document.createElement('div');
            logEntry.textContent = msg; // Assuming plain text
            fragment.appendChild(logEntry);
        });
        logOutput.appendChild(fragment);

        while (logOutput.children.length > currentMaxLogLines) {
            logOutput.removeChild(logOutput.firstChild);
        }
        logOutput.scrollTop = logOutput.scrollHeight; // Auto-scroll
    };

    window.setButtonState = function (buttonId, enabled) {
        const button = document.getElementById(buttonId);
        if (button) {
            button.disabled = !enabled;
        }
    };
    
    window.setLogLinesConfig = function(maxLines, currentLogs = []) {
        currentMaxLogLines = parseInt(maxLines, 10);
        logLinesInput.value = currentMaxLogLines;
        
        clearLogs();
        if (currentLogs && currentLogs.length > 0) {
            addBatchLogMessages(currentLogs);
        }
    };

    window.clearLogs = function() {
        logOutput.innerHTML = '';
    };

    // --- PyWebview Initialization ---
    window.addEventListener('pywebviewready', function () {
        console.log("PyWebview ready, notifying Python backend.");
        if (window.pywebview && window.pywebview.api && window.pywebview.api.frontend_is_ready) {
            window.pywebview.api.frontend_is_ready();
        } else {
            console.error("PyWebview API not available for frontend_is_ready call.");
            updateStatus("Error: UI failed to connect", true, false);
        }
    });
});