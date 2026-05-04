/**
 * @fileoverview QWebChannel 通信桥接模块。
 *
 * 负责建立与 Python 后端的 QWebChannel 连接，设置所有 Python → JS 信号监听器，
 * 并提供 JS → Python 的方法调用接口。支持事件回调注册机制（on/trigger）。
 */

class WebBridge {
    constructor() {
        this.pythonBridge = null;
        this.callbacks = {};
        this._initRetries = 0;
        this._maxRetries = 3;
        this._retryInterval = 1000;
    }

    init() {
        return new Promise((resolve, reject) => {
            this._attemptInit(resolve, reject);
        });
    }

    _attemptInit(resolve, reject) {
        if (typeof QWebChannel === 'undefined') {
            console.warn('[WebBridge] QWebChannel not available, retrying...');
            this._handleInitFailure(resolve, reject);
            return;
        }

        if (typeof qt === 'undefined' || !qt.webChannelTransport) {
            console.warn('[WebBridge] qt.webChannelTransport not available, retrying...');
            this._handleInitFailure(resolve, reject);
            return;
        }

        try {
            new QWebChannel(qt.webChannelTransport, (channel) => {
                this.pythonBridge = channel.objects.bridge;
                if (this.pythonBridge) {
                    this._setupSignalListeners();
                    console.log('[WebBridge] Connected successfully');
                    resolve(this.pythonBridge);
                } else {
                    console.warn('[WebBridge] Bridge object not found in channel');
                    this._handleInitFailure(resolve, reject);
                }
            });
        } catch (error) {
            console.error('[WebBridge] Init error:', error);
            this._handleInitFailure(resolve, reject);
        }
    }

    _handleInitFailure(resolve, reject) {
        this._initRetries++;
        if (this._initRetries < this._maxRetries) {
            console.log(`[WebBridge] Retrying (${this._initRetries}/${this._maxRetries})...`);
            setTimeout(() => this._attemptInit(resolve, reject), this._retryInterval);
        } else {
            const error = new Error(
                `Bridge initialization failed after ${this._maxRetries} attempts`
            );
            console.error('[WebBridge]', error.message);
            reject(error);
        }
    }

    _setupSignalListeners() {
        this.pythonBridge.init_game_state.connect((state) => {
            this._trigger('initGameState', { state });
        });

        this.pythonBridge.update_suspect.connect((name, pressure) => {
            this._trigger('suspectUpdate', { name, pressure });
        });

        this.pythonBridge.add_message.connect((role, content, suspectName) => {
            this._trigger('newMessage', { role, content, suspectName });
        });

        this.pythonBridge.update_timer.connect((timeLeft) => {
            this._trigger('timerUpdate', { timeLeft });
        });

        this.pythonBridge.update_evidence_list.connect((evidences) => {
            this._trigger('evidenceUpdate', { evidences });
        });

        this.pythonBridge.set_input_enabled.connect((enabled) => {
            this._trigger('inputEnabled', { enabled });
        });

        this.pythonBridge.show_dialog.connect((title, message) => {
            this._trigger('showDialog', { title, message });
        });

        this.pythonBridge.clear_chat.connect(() => {
            this._trigger('clearChat');
        });

        this.pythonBridge.show_loading.connect((message, cancellable) => {
            this._trigger('showLoading', { message, cancellable });
        });

        this.pythonBridge.hide_loading.connect(() => {
            this._trigger('hideLoading');
        });

        this.pythonBridge.update_loading_progress.connect((elapsedSeconds) => {
            this._trigger('loadingProgress', { elapsedSeconds });
        });

        this.pythonBridge.show_typing_indicator.connect((visible) => {
            this._trigger('typingIndicator', { visible });
        });

        this.pythonBridge.show_save_list.connect((sessions) => {
            this._trigger('showSaveList', { sessions });
        });

        this.pythonBridge.show_ending_dialog.connect((title, message) => {
            this._trigger('showEndingDialog', { title, message });
        });

        this.pythonBridge.show_settings_modal.connect((data) => {
            this._trigger('showSettingsModal', { data });
        });

        this.pythonBridge.settings_test_result.connect((success, message) => {
            this._trigger('settingsTestResult', { success, message });
        });

        this.pythonBridge.settings_saved.connect(() => {
            this._trigger('settingsSaved');
        });

        this.pythonBridge.show_generate_modal.connect(() => {
            this._trigger('showGenerateModal');
        });

        this.pythonBridge.case_generation_progress.connect((message) => {
            this._trigger('caseGenerationProgress', { message });
        });

        this.pythonBridge.case_generation_complete.connect((caseData) => {
            this._trigger('caseGenerationComplete', { caseData });
        });

        this.pythonBridge.case_generation_error.connect((errorMessage) => {
            this._trigger('caseGenerationError', { errorMessage });
        });

        this.pythonBridge.set_game_interactive.connect((enabled) => {
            this._trigger('gameInteractive', { enabled });
        });

        this.pythonBridge.show_review.connect((data) => {
            this._trigger('showReview', { data });
        });

        this.pythonBridge.show_case_briefing.connect((data) => {
            this._trigger('showCaseBriefing', { data });
        });

        console.log('[WebBridge] Signal listeners setup complete');
    }

    on(event, callback) {
        if (typeof callback !== 'function') {
            console.warn('[WebBridge] on() callback must be a function for event:', event);
            return;
        }
        if (!this.callbacks[event]) {
            this.callbacks[event] = [];
        }
        this.callbacks[event].push(callback);
    }

    off(event, callback) {
        if (!this.callbacks[event]) return;
        if (!callback) {
            delete this.callbacks[event];
            return;
        }
        this.callbacks[event] = this.callbacks[event].filter((cb) => cb !== callback);
    }

    _trigger(event, data) {
        if (this.callbacks[event]) {
            this.callbacks[event].forEach((cb) => {
                try {
                    cb(data);
                } catch (error) {
                    console.error(`[WebBridge] Error in callback for '${event}':`, error);
                }
            });
        }
    }

    // ================================================================
    // JS → Python 方法
    // ================================================================

    sendMessage(text) {
        if (this.pythonBridge && text && text.trim()) {
            this.pythonBridge.sendMessage(text.trim());
        }
    }

    selectSuspect(index) {
        if (this.pythonBridge && typeof index === 'number') {
            this.pythonBridge.selectSuspect(index);
        }
    }

    presentEvidence(evidenceId) {
        if (this.pythonBridge && evidenceId) {
            this.pythonBridge.presentEvidence(evidenceId);
        }
    }

    applyPressure() {
        if (this.pythonBridge) {
            this.pythonBridge.applyPressure();
        }
    }

    applyEmpathy() {
        if (this.pythonBridge) {
            this.pythonBridge.applyEmpathy();
        }
    }

    requestSave() {
        if (this.pythonBridge) {
            this.pythonBridge.requestSave();
        }
    }

    requestLoad() {
        if (this.pythonBridge) {
            this.pythonBridge.requestLoad();
        }
    }

    requestSettings() {
        if (this.pythonBridge) {
            this.pythonBridge.requestSettings();
        }
    }

    requestGenerateCase() {
        if (this.pythonBridge) {
            this.pythonBridge.requestGenerateCase();
        }
    }

    cancelOperation() {
        if (this.pythonBridge) {
            this.pythonBridge.cancelOperation();
        }
    }

    selectSave(sessionId) {
        if (this.pythonBridge && sessionId) {
            this.pythonBridge.selectSave(sessionId);
        }
    }

    requestRestart() {
        if (this.pythonBridge) {
            this.pythonBridge.requestRestart();
        }
    }

    requestReturnToMenu() {
        if (this.pythonBridge) {
            this.pythonBridge.requestReturnToMenu();
        }
    }

    submitSettings(provider, apiKey, baseUrl, model) {
        if (this.pythonBridge) {
            this.pythonBridge.submitSettings(provider, apiKey, baseUrl, model);
        }
    }

    testConnection(apiKey, baseUrl, model) {
        if (this.pythonBridge) {
            this.pythonBridge.testConnection(apiKey, baseUrl, model);
        }
    }

    submitCaseGeneration(background, model) {
        if (this.pythonBridge) {
            this.pythonBridge.submitCaseGeneration(background, model);
        }
    }

    submitCaseGenerationSafe(background, model) {
        if (this.pythonBridge) {
            this.pythonBridge.submitCaseGenerationSafe(background, model);
        }
    }

    cancelCaseGeneration() {
        if (this.pythonBridge) {
            this.pythonBridge.cancelCaseGeneration();
        }
    }

    requestReview() {
        if (this.pythonBridge) {
            this.pythonBridge.requestReview();
        }
    }

    requestCaseBriefing() {
        if (this.pythonBridge) {
            this.pythonBridge.requestCaseBriefing();
        }
    }
}

window.bridge = new WebBridge();
