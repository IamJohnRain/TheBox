/**
 * @fileoverview QWebChannel 通信桥接模块。
 *
 * 负责建立与 Python 后端的 QWebChannel 连接，设置所有 Python → JS 信号监听器，
 * 并提供 JS → Python 的方法调用接口。支持事件回调注册机制（on/trigger）。
 *
 * @author The Box Dev Team
 */

/**
 * WebBridge - Python ↔ JavaScript 通信桥接类。
 *
 * 通过 QWebChannel 与 PySide6 后端的 WebBridge QObject 双向通信：
 * - Python → JS：监听 Signal 事件，触发注册的回调
 * - JS → Python：调用 Slot 方法，发射后端信号
 */
class WebBridge {
    constructor() {
        /** @type {Object|null} QWebChannel 暴露的 bridge 对象 */
        this.pythonBridge = null;

        /** @type {Object.<string, Function[]>} 事件回调映射 */
        this.callbacks = {};

        /** @type {number} 初始化重试次数计数 */
        this._initRetries = 0;

        /** @type {number} 最大重试次数 */
        this._maxRetries = 3;

        /** @type {number} 重试间隔（毫秒） */
        this._retryInterval = 1000;
    }

    /**
     * 初始化 QWebChannel 连接（带重试机制）。
     *
     * @returns {Promise<Object>} 成功时 resolve(pythonBridge)，失败时 reject(Error)
     */
    init() {
        return new Promise((resolve, reject) => {
            this._attemptInit(resolve, reject);
        });
    }

    /**
     * 尝试初始化 QWebChannel 连接。
     * @private
     * @param {Function} resolve - Promise resolve 回调
     * @param {Function} reject - Promise reject 回调
     */
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

    /**
     * 处理初始化失败，支持重试。
     * @private
     * @param {Function} resolve - Promise resolve 回调
     * @param {Function} reject - Promise reject 回调
     */
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

    /**
     * 设置所有 Python → JS 信号监听器。
     * @private
     */
    _setupSignalListeners() {
        // 游戏状态信号
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

        // 加载状态信号
        this.pythonBridge.show_loading.connect((message, cancellable) => {
            this._trigger('showLoading', { message, cancellable });
        });

        this.pythonBridge.hide_loading.connect(() => {
            this._trigger('hideLoading');
        });

        this.pythonBridge.update_loading_progress.connect((elapsedSeconds) => {
            this._trigger('loadingProgress', { elapsedSeconds });
        });

        // 存档列表信号
        this.pythonBridge.show_save_list.connect((sessions) => {
            this._trigger('showSaveList', { sessions });
        });

        // 结局对话框信号
        this.pythonBridge.show_ending_dialog.connect((title, message) => {
            this._trigger('showEndingDialog', { title, message });
        });

        console.log('[WebBridge] Signal listeners setup complete');
    }

    /**
     * 注册事件回调。
     *
     * @param {string} event - 事件名称
     * @param {Function} callback - 回调函数，接收 data 参数
     * @returns {void}
     *
     * @example
     * window.bridge.on('newMessage', (data) => {
     *     console.log(data.role, data.content, data.suspectName);
     * });
     */
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

    /**
     * 移除事件回调。
     *
     * @param {string} event - 事件名称
     * @param {Function} [callback] - 要移除的回调，不传则移除该事件所有回调
     * @returns {void}
     */
    off(event, callback) {
        if (!this.callbacks[event]) return;
        if (!callback) {
            delete this.callbacks[event];
            return;
        }
        this.callbacks[event] = this.callbacks[event].filter((cb) => cb !== callback);
    }

    /**
     * 触发事件回调。
     * @private
     * @param {string} event - 事件名称
     * @param {*} [data] - 事件数据
     */
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

    /**
     * 发送聊天消息。
     * @param {string} text - 消息文本
     */
    sendMessage(text) {
        if (this.pythonBridge && text && text.trim()) {
            this.pythonBridge.sendMessage(text.trim());
        }
    }

    /**
     * 选择嫌疑人。
     * @param {number} index - 嫌疑人索引
     */
    selectSuspect(index) {
        if (this.pythonBridge && typeof index === 'number') {
            this.pythonBridge.selectSuspect(index);
        }
    }

    /**
     * 出示证据。
     * @param {string} evidenceId - 证据 ID
     */
    presentEvidence(evidenceId) {
        if (this.pythonBridge && evidenceId) {
            this.pythonBridge.presentEvidence(evidenceId);
        }
    }

    /**
     * 施压操作。
     */
    applyPressure() {
        if (this.pythonBridge) {
            this.pythonBridge.applyPressure();
        }
    }

    /**
     * 共情操作。
     */
    applyEmpathy() {
        if (this.pythonBridge) {
            this.pythonBridge.applyEmpathy();
        }
    }

    /**
     * 请求存档。
     */
    requestSave() {
        if (this.pythonBridge) {
            this.pythonBridge.requestSave();
        }
    }

    /**
     * 请求读档。
     */
    requestLoad() {
        if (this.pythonBridge) {
            this.pythonBridge.requestLoad();
        }
    }

    /**
     * 请求打开设置。
     */
    requestSettings() {
        if (this.pythonBridge) {
            this.pythonBridge.requestSettings();
        }
    }

    /**
     * 请求生成案件。
     */
    requestGenerateCase() {
        if (this.pythonBridge) {
            this.pythonBridge.requestGenerateCase();
        }
    }

    /**
     * 取消当前操作。
     */
    cancelOperation() {
        if (this.pythonBridge) {
            this.pythonBridge.cancelOperation();
        }
    }

    /**
     * 选择存档。
     * @param {string} sessionId - 存档会话 ID
     */
    selectSave(sessionId) {
        if (this.pythonBridge && sessionId) {
            this.pythonBridge.selectSave(sessionId);
        }
    }

    /**
     * 请求重新开始。
     */
    requestRestart() {
        if (this.pythonBridge) {
            this.pythonBridge.requestRestart();
        }
    }

    /**
     * 请求返回主菜单。
     */
    requestReturnToMenu() {
        if (this.pythonBridge) {
            this.pythonBridge.requestReturnToMenu();
        }
    }
}

// 全局单例
window.bridge = new WebBridge();
