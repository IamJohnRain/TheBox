/**
 * @fileoverview 主应用入口模块。
 */

(function () {
    'use strict';

    let chatManager;
    let suspectManager;
    let evidenceManager;
    let timerManager;
    let loadingManager;
    let modalManager;
    let keyboardManager;

    function init() {
        console.log('[App] Initializing...');

        initModules();
        bindUIEvents();
        initBridge();

        setTimeout(() => {
            const navbar = document.querySelector('.navbar');
            if (navbar) navbar.classList.add('blurred');
        }, 1000);

        console.log('[App] Initialization complete');
    }

    function initModules() {
        chatManager = new ChatManager();
        suspectManager = new SuspectManager();
        evidenceManager = new EvidenceManager();
        timerManager = new TimerManager();
        loadingManager = new LoadingManager();
        modalManager = new ModalManager();
        keyboardManager = new KeyboardManager();

        window.chatManager = chatManager;
        window.suspectManager = suspectManager;
        window.evidenceManager = evidenceManager;
        window.timerManager = timerManager;
        window.loadingManager = loadingManager;
        window.modalManager = modalManager;
        window.keyboardManager = keyboardManager;
    }

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
                bindBridgeEvents();
            });
    }

    function bindBridgeEvents() {
        const bridge = window.bridge;
        if (!bridge) return;

        function rafThrottle(fn) {
            let pending = false;
            let lastArg = null;
            return (arg) => {
                lastArg = arg;
                if (!pending) {
                    pending = true;
                    requestAnimationFrame(() => {
                        fn(lastArg);
                        pending = false;
                    });
                }
            };
        }

        // 游戏状态初始化
        bridge.on('initGameState', (data) => {
            if (!data || !data.state) return;
            const state = data.state;

            if (state.suspects) {
                suspectManager.loadSuspects(state.suspects);
            }

            if (state.evidences) {
                evidenceManager.loadEvidences(state.evidences);
            }

            const timeLeft = typeof state.timeLeft === 'number'
                ? state.timeLeft
                : (typeof state.time_left === 'number' ? state.time_left : null);
            if (timeLeft !== null) {
                timerManager.update(timeLeft);
            }

            if (typeof state.inputEnabled === 'boolean') {
                chatManager.setInputEnabled(state.inputEnabled);
            }

            if (state.caseTitle) {
                chatManager.setTitle(state.caseTitle);
            }

            if (state.caseBackground || state.suspectProfiles) {
                window._cachedCaseBriefing = {
                    title: state.caseBackground?.title || state.caseTitle || '案件资料',
                    victim: state.caseBackground?.victim || '',
                    causeOfDeath: state.caseBackground?.causeOfDeath || '',
                    crimeScene: state.caseBackground?.crimeScene || '',
                    suspects: (state.suspectProfiles || []).map((p) => ({
                        name: p.name || '',
                        role: p.role || '',
                        personality: p.personality || '',
                    })),
                };
            }

            const idx = state.current_suspect_index || 0;
            if (state.suspects && state.suspects[idx]) {
                chatManager.switchSuspect(state.suspects[idx].name);
            }
        });

        // 批量初始化 - 合并游戏状态 + 交互控制，消除中间态
        bridge.on('initFullState', (data) => {
            if (!data || !data.data) return;
            const d = data.data;
            const state = d.state || {};

            if (state.suspects) {
                suspectManager.loadSuspects(state.suspects);
            }

            if (state.evidences) {
                evidenceManager.loadEvidences(state.evidences);
            }

            const timeLeft = typeof state.timeLeft === 'number'
                ? state.timeLeft
                : (typeof state.time_left === 'number' ? state.time_left : null);
            if (timeLeft !== null) {
                timerManager.update(timeLeft);
            }

            const interactive = typeof d.interactive === 'boolean' ? d.interactive : true;
            chatManager.setInputEnabled(interactive);

            if (state.caseTitle) {
                chatManager.setTitle(state.caseTitle);
            }

            if (state.caseBackground || state.suspectProfiles) {
                window._cachedCaseBriefing = {
                    title: state.caseBackground?.title || state.caseTitle || '案件资料',
                    victim: state.caseBackground?.victim || '',
                    causeOfDeath: state.caseBackground?.causeOfDeath || '',
                    crimeScene: state.caseBackground?.crimeScene || '',
                    suspects: (state.suspectProfiles || []).map((p) => ({
                        name: p.name || '',
                        role: p.role || '',
                        personality: p.personality || '',
                    })),
                };
            }

            const idx = state.current_suspect_index || 0;
            if (state.suspects && state.suspects[idx]) {
                chatManager.switchSuspect(state.suspects[idx].name);
            }

            // 设置交互状态
            const selector = document.getElementById('suspect-selector');
            if (selector) selector.disabled = !interactive;

            const btnPressure = document.getElementById('btn-pressure');
            const btnEmpathy = document.getElementById('btn-empathy');
            if (btnPressure) btnPressure.disabled = !interactive;
            if (btnEmpathy) btnEmpathy.disabled = !interactive;

            document.querySelectorAll('.evidence-card').forEach((card) => {
                card.style.pointerEvents = interactive ? '' : 'none';
                card.style.opacity = interactive ? '' : '0.5';
            });
        });

        // 批量消息初始化 - DocumentFragment 一次性插入
        bridge.on('initMessages', (data) => {
            if (!data || !data.messages) return;
            chatManager.loadMessages(data.messages);
        });

        bridge.on('suspectUpdate', rafThrottle((data) => {
            if (!data) return;
            suspectManager.updateSuspect(data.name, data.pressure);
        }));

        bridge.on('newMessage', (data) => {
            if (!data) return;
            chatManager.addMessage(data.role, data.content, data.suspectName);
        });

        bridge.on('timerUpdate', rafThrottle((data) => {
            if (!data) return;
            timerManager.update(data.timeLeft);
        }));

        bridge.on('evidenceUpdate', (data) => {
            if (!data) return;
            evidenceManager.loadEvidences(data.evidences);
        });

        bridge.on('inputEnabled', (data) => {
            if (!data) return;
            chatManager.setInputEnabled(data.enabled);
        });

        bridge.on('showDialog', (data) => {
            if (!data) return;
            modalManager.showInfo(data.title, data.message);
        });

        bridge.on('clearChat', () => {
            chatManager.clear();
        });

        bridge.on('showLoading', (data) => {
            if (!data) return;
            loadingManager.show(data.message, data.cancellable);
        });

        bridge.on('hideLoading', () => {
            loadingManager.hide();
        });

        bridge.on('loadingProgress', (data) => {
            if (!data) return;
            loadingManager.updateProgress(data.elapsedSeconds);
        });

        bridge.on('typingIndicator', (data) => {
            if (!data) return;
            if (data.visible) {
                chatManager.showTypingIndicator();
            } else {
                chatManager.hideTypingIndicator();
            }
        });

        bridge.on('showSaveList', (data) => {
            if (!data) return;
            modalManager.showSaveSlots(data.sessions, false);
        });

        bridge.on('showSaveSlots', (data) => {
            if (!data) return;
            const isSaveMode = data.slots && data.slots._saveMode === true;
            modalManager.showSaveSlots(data.slots, isSaveMode);
        });

        bridge.on('showEndingDialog', (data) => {
            if (!data) return;
            modalManager.showEndingDialog(data.title, data.message);
        });

        // Settings modal
        bridge.on('showSettingsModal', (data) => {
            if (!data || !data.data) return;
            modalManager.showSettings(data.data);
        });

        bridge.on('settingsTestResult', (data) => {
            if (!data) return;
            modalManager.updateTestResult(data.success, data.message);
        });

        bridge.on('settingsSaved', () => {
            // 在表单内显示内联成功提示，不再关闭模态框再重开
            const resultEl = document.getElementById('settings-test-result');
            if (resultEl) {
                resultEl.innerHTML = '<span class="form-result-success">✓ 设置已保存</span>';
            }
        });

        // Case generation modal
        bridge.on('showGenerateModal', () => {
            modalManager.showGenerateCase();
        });

        bridge.on('caseGenerationProgress', (data) => {
            if (!data) return;
            modalManager.updateGenerationProgress(data.message);
        });

        bridge.on('caseGenerationComplete', () => {
            modalManager.updateGenerationComplete();
        });

        bridge.on('caseGenerationError', (data) => {
            if (!data) return;
            modalManager.updateGenerationError(data.errorMessage);
        });

        // 游戏交互控制
        bridge.on('gameInteractive', (data) => {
            if (!data) return;
            const enabled = data.enabled;

            // 聊天输入框
            chatManager.setInputEnabled(enabled);

            // 嫌疑人下拉框
            const selector = document.getElementById('suspect-selector');
            if (selector) selector.disabled = !enabled;

            // 施压/共情按钮
            const btnPressure = document.getElementById('btn-pressure');
            const btnEmpathy = document.getElementById('btn-empathy');
            if (btnPressure) btnPressure.disabled = !enabled;
            if (btnEmpathy) btnEmpathy.disabled = !enabled;

            // 证据卡片
            document.querySelectorAll('.evidence-card').forEach((card) => {
                card.style.pointerEvents = enabled ? '' : 'none';
                card.style.opacity = enabled ? '' : '0.5';
            });
        });

        // 复盘报告展示
        bridge.on('showReview', (data) => {
            if (!data || !data.data) return;
            modalManager.showReviewReport(data.data);
        });

        // 案件资料展示
        bridge.on('showCaseBriefing', (data) => {
            if (!data || !data.data) return;
            modalManager.showCaseBriefing(data.data);
        });
    }

    // ================================================================
    // UI 事件绑定
    // ================================================================

    function bindUIEvents() {
        bindButton('btn-case-briefing', () => {
            if (window._cachedCaseBriefing) {
                modalManager.showCaseBriefing(window._cachedCaseBriefing);
            } else if (window.bridge) {
                window.bridge.requestCaseBriefing();
            }
        });

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

        const suspectSelector = document.getElementById('suspect-selector');
        if (suspectSelector) {
            suspectSelector.addEventListener('change', (e) => {
                const index = parseInt(e.target.value, 10);
                if (!isNaN(index) && index >= 0) {
                    if (window.bridge) window.bridge.selectSuspect(index);
                    suspectManager.selectSuspect(index);

                    const suspect = suspectManager.suspects[index];
                    if (suspect && suspect.name) {
                        chatManager.switchSuspect(suspect.name);
                    }
                }
            });
        }

        bindButton('btn-pressure', () => {
            if (window.bridge) window.bridge.applyPressure();
        });

        bindButton('btn-empathy', () => {
            if (window.bridge) window.bridge.applyEmpathy();
        });

        const chatInput = document.getElementById('chat-input');
        const btnSend = document.getElementById('btn-send');

        function sendMessage() {
            const text = chatManager.getInputText();
            if (text && window.bridge) {
                window.bridge.sendMessage(text);
                chatManager.addMessage('player', text, '审讯员');
            }
        }

        if (chatInput) {
            chatInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    e.stopPropagation();
                    sendMessage();
                }
            });
        }

        if (btnSend) {
            btnSend.addEventListener('click', sendMessage);
        }

        keyboardManager.register('ctrl+s', () => {
            if (window.bridge) window.bridge.requestSave();
        });

        keyboardManager.register('ctrl+l', () => {
            if (window.bridge) window.bridge.requestLoad();
        });

        keyboardManager.register('escape', () => {
            if (window.modalManager && window.modalManager.isVisible()) {
                window.modalManager.hide();
            }
        });
    }

    function bindButton(elementId, handler) {
        const btn = document.getElementById(elementId);
        if (btn) {
            btn.addEventListener('click', handler);
        } else {
            console.warn(`[App] Button #${elementId} not found`);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
