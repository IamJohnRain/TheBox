/**
 * @fileoverview 主应用入口模块。
 *
 * 在 DOMContentLoaded 时初始化 Bridge、各功能模块，
 * 绑定 Bridge 事件到模块方法，绑定按钮和键盘事件。
 *
 * @author The Box Dev Team
 */

(function () {
    'use strict';

    // ================================================================
    // 模块实例
    // ================================================================

    /** @type {ChatManager} */
    let chatManager;

    /** @type {SuspectManager} */
    let suspectManager;

    /** @type {EvidenceManager} */
    let evidenceManager;

    /** @type {TimerManager} */
    let timerManager;

    /** @type {LoadingManager} */
    let loadingManager;

    /** @type {ModalManager} */
    let modalManager;

    /** @type {KeyboardManager} */
    let keyboardManager;

    // ================================================================
    // 初始化
    // ================================================================

    /**
     * 应用初始化入口。
     * 在 DOMContentLoaded 后调用。
     */
    function init() {
        console.log('[App] Initializing...');

        // 1. 初始化各模块
        initModules();

        // 2. 绑定 UI 事件
        bindUIEvents();

        // 3. 初始化 Bridge 连接
        initBridge();

        console.log('[App] Initialization complete');
    }

    /**
     * 初始化所有功能模块。
     */
    function initModules() {
        chatManager = new ChatManager();
        suspectManager = new SuspectManager();
        evidenceManager = new EvidenceManager();
        timerManager = new TimerManager();
        loadingManager = new LoadingManager();
        modalManager = new ModalManager();
        keyboardManager = new KeyboardManager();

        // 暴露到全局，供跨模块引用
        window.chatManager = chatManager;
        window.suspectManager = suspectManager;
        window.evidenceManager = evidenceManager;
        window.timerManager = timerManager;
        window.loadingManager = loadingManager;
        window.modalManager = modalManager;
        window.keyboardManager = keyboardManager;
    }

    /**
     * 初始化 QWebChannel Bridge 连接并绑定信号。
     */
    function initBridge() {
        if (!window.bridge) {
            console.error('[App] Bridge singleton not found');
            return;
        }

        window.bridge
            .init()
            .then(() => {
                console.log('[App] Bridge connected');
                bindBridgeEvents();
            })
            .catch((error) => {
                console.error('[App] Bridge connection failed:', error);
                // 即使连接失败也尝试绑定事件，后续重连可能成功
                bindBridgeEvents();
            });
    }

    /**
     * 绑定 Bridge 信号到各模块方法。
     */
    function bindBridgeEvents() {
        const bridge = window.bridge;
        if (!bridge) return;

        // 游戏状态初始化
        bridge.on('initGameState', (data) => {
            if (!data || !data.state) return;
            const state = data.state;

            // 加载嫌疑人列表
            if (state.suspects) {
                suspectManager.loadSuspects(state.suspects);
            }

            // 加载证据列表
            if (state.evidences) {
                evidenceManager.loadEvidences(state.evidences);
            }

            // 更新计时器
            if (typeof state.timeLeft === 'number') {
                timerManager.update(state.timeLeft);
            }

            // 输入状态
            if (typeof state.inputEnabled === 'boolean') {
                chatManager.setInputEnabled(state.inputEnabled);
            }

            // 聊天标题
            if (state.caseTitle) {
                chatManager.setTitle(state.caseTitle);
            }
        });

        // 嫌疑人更新
        bridge.on('suspectUpdate', (data) => {
            if (!data) return;
            suspectManager.updateSuspect(data.name, data.pressure);
        });

        // 新消息
        bridge.on('newMessage', (data) => {
            if (!data) return;
            chatManager.addMessage(data.role, data.content, data.suspectName);
        });

        // 计时器更新
        bridge.on('timerUpdate', (data) => {
            if (!data) return;
            timerManager.update(data.timeLeft);
        });

        // 证据更新
        bridge.on('evidenceUpdate', (data) => {
            if (!data) return;
            evidenceManager.loadEvidences(data.evidences);
        });

        // 输入启用/禁用
        bridge.on('inputEnabled', (data) => {
            if (!data) return;
            chatManager.setInputEnabled(data.enabled);
        });

        // 信息对话框
        bridge.on('showDialog', (data) => {
            if (!data) return;
            modalManager.showInfo(data.title, data.message);
        });

        // 清空聊天
        bridge.on('clearChat', () => {
            chatManager.clear();
        });

        // 显示加载
        bridge.on('showLoading', (data) => {
            if (!data) return;
            loadingManager.show(data.message, data.cancellable);
        });

        // 隐藏加载
        bridge.on('hideLoading', () => {
            loadingManager.hide();
        });

        // 加载进度
        bridge.on('loadingProgress', (data) => {
            if (!data) return;
            loadingManager.updateProgress(data.elapsedSeconds);
        });

        // 存档列表
        bridge.on('showSaveList', (data) => {
            if (!data) return;
            modalManager.showSaveList(data.sessions);
        });

        // 结局对话框
        bridge.on('showEndingDialog', (data) => {
            if (!data) return;
            modalManager.showEndingDialog(data.title, data.message);
        });
    }

    // ================================================================
    // UI 事件绑定
    // ================================================================

    /**
     * 绑定所有 UI 事件（按钮、输入框、键盘快捷键）。
     */
    function bindUIEvents() {
        // 导航栏按钮
        bindButton('btn-generate', () => {
            if (window.bridge) window.bridge.requestGenerateCase();
        });

        bindButton('btn-save', () => {
            if (window.bridge) window.bridge.requestSave();
        });

        bindButton('btn-load', () => {
            if (window.bridge) window.bridge.requestLoad();
        });

        bindButton('btn-settings', () => {
            if (window.bridge) window.bridge.requestSettings();
        });

        // 嫌疑人选择器
        const suspectSelector = document.getElementById('suspect-selector');
        if (suspectSelector) {
            suspectSelector.addEventListener('change', (e) => {
                const index = parseInt(e.target.value, 10);
                if (!isNaN(index) && index >= 0) {
                    if (window.bridge) window.bridge.selectSuspect(index);
                    suspectManager.selectSuspect(index);
                }
            });
        }

        // 施压 / 共情按钮
        bindButton('btn-pressure', () => {
            if (window.bridge) window.bridge.applyPressure();
        });

        bindButton('btn-empathy', () => {
            if (window.bridge) window.bridge.applyEmpathy();
        });

        // 聊天输入
        const chatInput = document.getElementById('chat-input');
        const btnSend = document.getElementById('btn-send');

        // 发送消息
        function sendMessage() {
            const text = chatManager.getInputText();
            if (text && window.bridge) {
                window.bridge.sendMessage(text);
                // 同时在本地显示玩家消息（即时反馈）
                chatManager.addMessage('player', text, '审讯员');
            }
        }

        if (chatInput) {
            // Enter 键发送消息（在输入框聚焦时，由输入框自身监听，不走全局 KeyboardManager）
            chatInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    e.stopPropagation(); // 阻止冒泡到 KeyboardManager
                    sendMessage();
                }
            });
        }

        if (btnSend) {
            btnSend.addEventListener('click', sendMessage);
        }

        // ============================================================
        // 全局键盘快捷键
        // ============================================================

        // Ctrl+S 存档
        keyboardManager.register('ctrl+s', () => {
            if (window.bridge) window.bridge.requestSave();
        });

        // Ctrl+L 读档
        keyboardManager.register('ctrl+l', () => {
            if (window.bridge) window.bridge.requestLoad();
        });

        // Escape 关闭模态框（仅在模态框可见时生效）
        keyboardManager.register('escape', () => {
            if (window.modalManager && window.modalManager.isVisible()) {
                window.modalManager.hide();
            }
        });
    }

    /**
     * 辅助函数：安全绑定按钮点击事件。
     * @param {string} elementId - 按钮 ID
     * @param {Function} handler - 事件处理函数
     */
    function bindButton(elementId, handler) {
        const btn = document.getElementById(elementId);
        if (btn) {
            btn.addEventListener('click', handler);
        } else {
            console.warn(`[App] Button #${elementId} not found`);
        }
    }

    // ================================================================
    // 启动
    // ================================================================

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
