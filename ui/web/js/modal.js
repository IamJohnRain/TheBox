/**
 * @fileoverview 模态框模块。
 */

class ModalManager {
    constructor() {
        this.backdrop = document.getElementById('modal-backdrop');
        this.modal = document.getElementById('modal');
        this.titleEl = document.getElementById('modal-title');
        this.bodyEl = document.getElementById('modal-body');
        this.footerEl = document.getElementById('modal-footer');
        this.closeBtn = document.getElementById('modal-close');
        this._confirmCallback = null;
        this._bindEvents();
    }

    _bindEvents() {
        if (this.closeBtn) {
            this.closeBtn.addEventListener('click', () => this.hide());
        }

        if (this.backdrop) {
            this.backdrop.addEventListener('click', () => this.hide());
        }

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this._isVisible()) {
                this.hide();
            }
        });
    }

    _isVisible() {
        return this.modal && this.modal.classList.contains('active');
    }

    isVisible() {
        return this._isVisible();
    }

    showInfo(title, message) {
        this._show(title, `<p>${this._escapeHtml(message)}</p>`, [
            { text: '确定', class: 'modal-btn-primary', callback: null },
        ]);
    }

    showConfirm(title, message, onConfirm) {
        this._confirmCallback = onConfirm;
        this._show(title, `<p>${this._escapeHtml(message)}</p>`, [
            { text: '取消', class: 'modal-btn-secondary', callback: null },
            { text: '确认', class: 'modal-btn-primary', callback: () => {
                if (typeof this._confirmCallback === 'function') {
                    this._confirmCallback();
                }
                this._confirmCallback = null;
            }},
        ]);
    }

    showSaveList(sessions) {
        this.showSaveSlots(sessions, false);
    }

    showSaveSlots(slots, isSaveMode) {
        const slotsList = slots || [];

        let listHtml = '<div class="save-slots">';
        slotsList.forEach((slot) => {
            if (slot.empty) {
                listHtml += `
                    <div class="save-slot save-slot-empty" data-slot="${slot.slot_number}" tabindex="0" role="button">
                        <div class="save-slot-number">槽位 ${slot.slot_number}</div>
                        <div class="save-slot-info">
                            <div class="save-slot-name">空槽位</div>
                            <div class="save-slot-date">点击保存</div>
                        </div>
                    </div>
                `;
            } else {
                listHtml += `
                    <div class="save-slot save-slot-occupied" data-slot="${slot.slot_number}" data-session-id="${this._escapeHtml(slot.session_id || '')}" tabindex="0" role="button">
                        <div class="save-slot-number">槽位 ${slot.slot_number}</div>
                        <div class="save-slot-info">
                            <div class="save-slot-name">${this._escapeHtml(slot.name || '未知存档')}</div>
                            <div class="save-slot-date">${this._escapeHtml(slot.date || '未知日期')}</div>
                        </div>
                        <button class="save-slot-delete-btn" data-delete-slot="${slot.slot_number}" title="删除此存档" aria-label="删除槽位 ${slot.slot_number}">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="3 6 5 6 21 6"/>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                            </svg>
                        </button>
                    </div>
                `;
            }
        });
        listHtml += '</div>';

        const title = isSaveMode ? '选择存档槽位' : '加载存档';
        this._show(title, listHtml, [
            { text: '取消', class: 'modal-btn-secondary', callback: null },
        ]);

        const slotEls = this.bodyEl.querySelectorAll('.save-slot');
        slotEls.forEach((el) => {
            const slotNumber = parseInt(el.getAttribute('data-slot'), 10);
            const isOccupied = el.classList.contains('save-slot-occupied');

            const deleteBtn = el.querySelector('.save-slot-delete-btn');
            if (deleteBtn) {
                deleteBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const deleteSlot = parseInt(deleteBtn.getAttribute('data-delete-slot'), 10);
                    if (window.modalManager) {
                        window.modalManager.showConfirm(
                            '确认删除',
                            `确定要删除槽位 ${deleteSlot} 的存档吗？此操作不可撤销。`,
                            () => {
                                if (window.bridge) window.bridge.deleteSave(deleteSlot);
                            }
                        );
                    } else if (window.bridge) {
                        window.bridge.deleteSave(deleteSlot);
                    }
                });
            }

            const clickHandler = () => {
                if (isSaveMode) {
                    if (isOccupied) {
                        if (window.modalManager) {
                            window.modalManager.showConfirm(
                                '覆盖存档',
                                `槽位 ${slotNumber} 已有存档，确定要覆盖吗？`,
                                () => {
                                    if (window.bridge) window.bridge.saveToSlot(slotNumber);
                                }
                            );
                        }
                    } else {
                        if (window.bridge) window.bridge.saveToSlot(slotNumber);
                    }
                } else {
                    if (isOccupied) {
                        const sessionId = el.getAttribute('data-session-id');
                        if (sessionId && window.bridge) {
                            window.bridge.selectSave(sessionId);
                        }
                    }
                }
            };

            el.addEventListener('click', clickHandler);
            el.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') clickHandler();
            });
        });
    }

    showEndingDialog(title, message) {
        this._show(title, `<p>${this._escapeHtml(message)}</p>`, [
            {
                text: '复盘审讯',
                class: 'modal-btn-primary',
                callback: () => {
                    if (window.bridge) window.bridge.requestReview();
                },
            },
            {
                text: '重新开始',
                class: 'modal-btn-secondary',
                callback: () => {
                    if (window.bridge) window.bridge.requestRestart();
                },
            },
            {
                text: '返回主菜单',
                class: 'modal-btn-secondary',
                callback: () => {
                    if (window.bridge) window.bridge.requestReturnToMenu();
                },
            },
        ]);
    }

    showCaseBriefing(data) {
        const title = data.title || '案件资料';
        const victim = data.victim || '未知';
        const causeOfDeath = data.causeOfDeath || '未知';
        const crimeScene = data.crimeScene || '未知';
        const suspects = data.suspects || [];

        let suspectsHtml = '';
        suspects.forEach((s) => {
            suspectsHtml += `
                <div class="briefing-suspect-card" style="
                    background: rgba(0, 245, 255, 0.05);
                    border: 1px solid var(--color-border);
                    border-radius: var(--radius-md);
                    padding: var(--space-3);
                    margin-bottom: var(--space-3);
                ">
                    <div style="font-weight: 600; color: var(--color-accent-cyan); margin-bottom: var(--space-1);">
                        ${this._escapeHtml(s.name || '未知')}
                    </div>
                    <div style="color: var(--color-text-secondary); font-size: 0.9em; margin-bottom: var(--space-1);">
                        身份：${this._escapeHtml(s.role || '未知')}
                    </div>
                    <div style="color: var(--color-text-secondary); font-size: 0.9em;">
                        性格：${this._escapeHtml(s.personality || '未知')}
                    </div>
                </div>
            `;
        });

        const bodyHtml = `
            <div class="case-briefing">
                <div style="text-align:left; margin-bottom: var(--space-4);">
                    <h4 style="margin-bottom: var(--space-2); color: var(--color-accent-cyan);">案件背景</h4>
                    <p><strong>受害者：</strong>${this._escapeHtml(victim)}</p>
                    <p><strong>死因：</strong>${this._escapeHtml(causeOfDeath)}</p>
                    <p><strong>犯罪现场：</strong>${this._escapeHtml(crimeScene)}</p>
                </div>
                <div style="text-align:left;">
                    <h4 style="margin-bottom: var(--space-2); color: var(--color-accent-cyan);">审讯对象资料</h4>
                    ${suspectsHtml || '<p class="text-muted">暂无嫌疑人资料</p>'}
                </div>
            </div>
        `;

        this._show(title, bodyHtml, [
            { text: '开始审讯', class: 'modal-btn-primary', callback: null },
        ]);
    }

    showReviewReport(reviewData) {
        const score = reviewData.score || 0;
        const scoreClass = score >= 70 ? 'success' : score >= 40 ? 'warning' : 'failure';
        const scoreIcon = score >= 70 ? '✓' : score >= 40 ? '!' : '✗';

        let momentsHtml = '';
        (reviewData.key_moments || []).forEach((m) => {
            momentsHtml += `<li>${this._escapeHtml(m)}</li>`;
        });

        let suggestionsHtml = '';
        (reviewData.suggestions || []).forEach((s) => {
            suggestionsHtml += `<li>${this._escapeHtml(s)}</li>`;
        });

        // 案件真相区域
        let truthHtml = '';
        const caseTruth = reviewData.caseTruth;
        if (caseTruth) {
            truthHtml = `
                <div style="text-align:left; margin: var(--space-4) 0; padding: var(--space-4); background: rgba(0, 245, 255, 0.05); border-radius: var(--radius-md); border: 1px solid var(--color-border);">
                    <h4 style="margin-bottom: var(--space-2); color: var(--color-accent-cyan);">案件真相</h4>
                    <p><strong>受害者：</strong>${this._escapeHtml(caseTruth.victim || '')}</p>
                    <p><strong>死因：</strong>${this._escapeHtml(caseTruth.causeOfDeath || '')}</p>
                    <p><strong>犯罪现场：</strong>${this._escapeHtml(caseTruth.crimeScene || '')}</p>
                    <p style="margin-top: var(--space-2);"><strong>完整真相：</strong>${this._escapeHtml(caseTruth.truth || '')}</p>
                </div>
            `;
        }

        const bodyHtml = `
            <div class="result-modal">
                <div class="result-icon ${scoreClass}">${scoreIcon}</div>
                <div class="result-title ${scoreClass}">综合评分: ${score}/100</div>
                <div class="result-description">${this._escapeHtml(reviewData.verdict || '')}</div>
                <div style="text-align:left; margin: var(--space-4) 0;">
                    <h4 style="margin-bottom: var(--space-2); color: var(--color-accent-cyan);">策略分析</h4>
                    <p>${this._escapeHtml(reviewData.strategy_analysis || '')}</p>
                </div>
                <div style="text-align:left; margin: var(--space-4) 0;">
                    <h4 style="margin-bottom: var(--space-2); color: var(--color-accent-cyan);">关键转折</h4>
                    <ul style="padding-left: var(--space-6);">${momentsHtml || '<li>无</li>'}</ul>
                </div>
                <div style="text-align:left; margin: var(--space-4) 0;">
                    <h4 style="margin-bottom: var(--space-2); color: var(--color-accent-cyan);">改进建议</h4>
                    <ul style="padding-left: var(--space-6);">${suggestionsHtml || '<li>无</li>'}</ul>
                </div>
                ${truthHtml}
            </div>
        `;

        this._show('审讯复盘', bodyHtml, [
            {
                text: '重新开始',
                class: 'modal-btn-primary',
                callback: () => {
                    if (window.bridge) window.bridge.requestRestart();
                },
            },
            {
                text: '返回主菜单',
                class: 'modal-btn-secondary',
                callback: () => {
                    if (window.bridge) window.bridge.requestReturnToMenu();
                },
            },
        ]);
    }

    // ================================================================
    // Settings Modal
    // ================================================================

    showSettings(data) {
        const settings = data || {};
        const providers = settings.providers || [];
        const models = settings.models || [];
        const currentProvider = settings.provider || '';
        const currentApiKey = settings.api_key || '';
        const currentBaseUrl = settings.base_url || '';
        const currentModel = settings.model || '';

        let providerOptions = '';
        providers.forEach((p) => {
            const selected = p.id === currentProvider ? ' selected' : '';
            providerOptions += `<option value="${this._escapeHtml(p.id)}"${selected}>${this._escapeHtml(p.name)}</option>`;
        });

        let modelOptions = '';
        models.forEach((m) => {
            const selected = m === currentModel ? ' selected' : '';
            modelOptions += `<option value="${this._escapeHtml(m)}"${selected}>${this._escapeHtml(m)}</option>`;
        });

        const isCustomModel = currentModel && models.indexOf(currentModel) === -1;

        const bodyHtml = `
            <div class="modal-form">
                <div class="form-group">
                    <label class="form-label" for="settings-provider">Provider</label>
                    <select class="form-select" id="settings-provider">
                        ${providerOptions}
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label" for="settings-api-key">API Key</label>
                    <input type="password" class="form-input" id="settings-api-key"
                           value="${this._escapeHtml(currentApiKey)}" placeholder="输入 API Key">
                </div>
                <div class="form-group">
                    <label class="form-label" for="settings-base-url">Base URL</label>
                    <input type="text" class="form-input" id="settings-base-url"
                           value="${this._escapeHtml(currentBaseUrl)}" placeholder="https://api.example.com/v1">
                </div>
                <div class="form-group">
                    <label class="form-label" for="settings-model">模型</label>
                    <div class="form-combo">
                        <input type="text" class="form-input form-combo-input" id="settings-model"
                               value="${this._escapeHtml(currentModel)}" placeholder="输入或选择模型名称"
                               list="settings-model-list">
                        <datalist id="settings-model-list">
                            ${modelOptions}
                        </datalist>
                    </div>
                </div>
                <div class="form-result" id="settings-test-result"></div>
            </div>
        `;

        this._show('LLM 设置', bodyHtml, [
            { text: '测试连接', class: 'modal-btn-secondary', callback: () => {
                this._onTestConnection();
                return false;
            }},
            { text: '保存', class: 'modal-btn-primary', callback: () => {
                this._onSaveSettings();
                return false;  // 不关闭模态框，让用户看到保存结果
            }},
            { text: '取消', class: 'modal-btn-secondary', callback: null },
        ]);

        this._setupSettingsProviderChange(providers);
    }

    _setupSettingsProviderChange(providers) {
        const providerSelect = document.getElementById('settings-provider');
        if (!providerSelect) return;

        providerSelect.addEventListener('change', () => {
            const providerId = providerSelect.value;
            const provider = providers.find((p) => p.id === providerId);
            if (!provider) return;

            const baseUrlInput = document.getElementById('settings-base-url');
            const modelInput = document.getElementById('settings-model');
            const modelList = document.getElementById('settings-model-list');
            const apiKeyInput = document.getElementById('settings-api-key');

            if (provider.default_base_url && baseUrlInput) {
                baseUrlInput.value = provider.default_base_url || '';
            }

            if (modelList) {
                modelList.innerHTML = '';
                if (provider.models) {
                    provider.models.forEach((m) => {
                        const opt = document.createElement('option');
                        opt.value = m;
                        modelList.appendChild(opt);
                    });
                }
            }

            if (provider.default_model && modelInput) {
                modelInput.value = provider.default_model || '';
            }

            if (apiKeyInput) {
                apiKeyInput.value = '';
                apiKeyInput.placeholder = '输入 API Key';
            }

            const resultEl = document.getElementById('settings-test-result');
            if (resultEl) resultEl.innerHTML = '';
        });
    }

    _onTestConnection() {
        const apiKey = document.getElementById('settings-api-key')?.value?.trim() || '';
        const baseUrl = document.getElementById('settings-base-url')?.value?.trim() || '';
        const model = document.getElementById('settings-model')?.value?.trim() || '';

        const resultEl = document.getElementById('settings-test-result');
        if (resultEl) {
            resultEl.innerHTML = '<span class="form-result-pending">正在测试连接...</span>';
        }

        if (window.bridge) {
            window.bridge.testConnection(apiKey, baseUrl, model);
        }
    }

    _onSaveSettings() {
        const provider = document.getElementById('settings-provider')?.value?.trim() || '';
        const apiKey = document.getElementById('settings-api-key')?.value?.trim() || '';
        const baseUrl = document.getElementById('settings-base-url')?.value?.trim() || '';
        const model = document.getElementById('settings-model')?.value?.trim() || '';

        if (!apiKey || !baseUrl || !model) {
            const resultEl = document.getElementById('settings-test-result');
            if (resultEl) {
                resultEl.innerHTML = '<span class="form-result-error">API Key、Base URL 和模型名称不能为空</span>';
            }
            return;
        }

        if (window.bridge) {
            window.bridge.submitSettings(provider, apiKey, baseUrl, model);
        }
    }

    updateTestResult(success, message) {
        const resultEl = document.getElementById('settings-test-result');
        if (resultEl) {
            const cls = success ? 'form-result-success' : 'form-result-error';
            resultEl.innerHTML = `<span class="${cls}">${this._escapeHtml(message)}</span>`;
        }
    }

    // ================================================================
    // Case Generation Modal
    // ================================================================

    showGenerateCase() {
        this._genSteps = [
            { emoji: '📐', text: '正在搭建虚拟世界框架...', status: 'pending' },
            { emoji: '🎬', text: '正在打造故事场景...', status: 'pending' },
            { emoji: '🧠', text: '正在与 AI 构思案件...', status: 'pending' },
            { emoji: '🔍', text: '正在编织线索与谜题...', status: 'pending' },
            { emoji: '⚖️', text: '正在校验逻辑自洽性...', status: 'pending' },
            { emoji: '✅', text: '案件世界构建完成！', status: 'pending' },
        ];
        this._genCurrentStep = -1;
        this._genTypewriterTimer = null;

        const bodyHtml = `
            <div class="modal-form">
                <div class="form-group">
                    <label class="form-label" for="generate-story">背景故事</label>
                    <textarea class="form-textarea" id="generate-story" rows="6"
                              placeholder="请输入案件的背景故事..."></textarea>
                </div>
                <div class="form-group">
                    <label class="form-label" for="generate-model">模型名称 <span class="form-label-hint">(可选，留空使用当前设置)</span></label>
                    <input type="text" class="form-input" id="generate-model"
                           placeholder="留空使用默认模型">
                </div>
                <div class="form-result" id="generate-result"></div>
            </div>
        `;

        this._show('生成新案件', bodyHtml, [
            { text: '生成', class: 'modal-btn-primary', callback: () => {
                this._onGenerateCase(false);
                return false;
            }},
            { text: '取消', class: 'modal-btn-secondary', callback: null },
        ]);
    }

    _onGenerateCase(safeMode) {
        const story = document.getElementById('generate-story')?.value?.trim() || '';
        const model = document.getElementById('generate-model')?.value?.trim() || '';

        const resultEl = document.getElementById('generate-result');
        if (!story) {
            if (resultEl) {
                resultEl.innerHTML = '<span class="form-result-error">背景故事不能为空</span>';
            }
            return;
        }

        this._resetGenSteps();
        if (resultEl) {
            resultEl.innerHTML = this._renderGenSteps();
        }

        const generateBtn = this.footerEl?.querySelector('.modal-btn-primary');
        if (generateBtn) {
            generateBtn.disabled = true;
            generateBtn.textContent = '生成中...';
        }

        const storyEl = document.getElementById('generate-story');
        const modelEl = document.getElementById('generate-model');
        if (storyEl) storyEl.disabled = true;
        if (modelEl) modelEl.disabled = true;

        if (window.bridge) {
            if (safeMode) {
                window.bridge.submitCaseGenerationSafe(story, model);
            } else {
                window.bridge.submitCaseGeneration(story, model);
            }
        }
    }

    _resetGenSteps() {
        this._genSteps.forEach((s) => { s.status = 'pending'; });
        this._genCurrentStep = -1;
    }

    _matchStepIndex(message) {
        const mapping = [
            { pattern: '搭建虚拟世界框架', index: 0 },
            { pattern: '打造故事场景', index: 1 },
            { pattern: '安全创作模式', index: 1 },
            { pattern: '构思案件', index: 2 },
            { pattern: '编织线索', index: 3 },
            { pattern: '校验逻辑', index: 4 },
            { pattern: '构建完成', index: 5 },
        ];
        for (const m of mapping) {
            if (message.includes(m.pattern)) return m.index;
        }
        return -1;
    }

    _renderGenSteps() {
        let html = '<div class="gen-progress">';
        this._genSteps.forEach((step, i) => {
            let icon = '';
            let textClass = '';
            if (step.status === 'done') {
                icon = '<span class="gen-step-icon gen-step-done">✓</span>';
                textClass = 'gen-step-text-done';
            } else if (step.status === 'active') {
                icon = `<span class="gen-step-icon gen-step-active">${step.emoji}</span>`;
                textClass = 'gen-step-text-active';
            } else {
                icon = '<span class="gen-step-icon gen-step-pending">○</span>';
                textClass = 'gen-step-text-pending';
            }
            html += `<div class="gen-step ${step.status}">${icon}<span class="gen-step-text ${textClass}" id="gen-step-text-${i}">${step.status === 'active' ? '' : this._escapeHtml(step.text)}</span></div>`;
        });
        html += '</div>';

        const progress = this._genCurrentStep >= 0
            ? Math.min(100, Math.round(((this._genCurrentStep + 0.5) / this._genSteps.length) * 100))
            : 0;
        html += `<div class="gen-progress-bar"><div class="gen-progress-fill" style="width:${progress}%"></div></div>`;
        return html;
    }

    _typewriterEffect(elementId, text, speed) {
        if (this._genTypewriterTimer) {
            clearInterval(this._genTypewriterTimer);
            this._genTypewriterTimer = null;
        }
        const el = document.getElementById(elementId);
        if (!el) return;
        let idx = 0;
        el.innerHTML = '';
        this._genTypewriterTimer = setInterval(() => {
            if (idx < text.length) {
                el.textContent = text.substring(0, idx + 1);
                idx++;
            } else {
                clearInterval(this._genTypewriterTimer);
                this._genTypewriterTimer = null;
            }
        }, speed || 40);
    }

    updateGenerationProgress(message) {
        const stepIdx = this._matchStepIndex(message);
        if (stepIdx < 0) return;

        if (stepIdx <= this._genCurrentStep) return;

        if (this._genCurrentStep >= 0) {
            this._genSteps[this._genCurrentStep].status = 'done';
        }
        this._genSteps[stepIdx].status = 'active';
        this._genCurrentStep = stepIdx;

        const resultEl = document.getElementById('generate-result');
        if (resultEl) {
            resultEl.innerHTML = this._renderGenSteps();
            if (this._genSteps[stepIdx].status === 'active') {
                this._typewriterEffect(`gen-step-text-${stepIdx}`, this._genSteps[stepIdx].text, 40);
            }
        }
    }

    _ERROR_CONFIGS = {
        content_filter: {
            icon: '🛡️',
            title: 'AI 安全审查触发了警报',
            desc: '你的背景故事可能包含敏感内容，试试这些修改建议：',
            tips: [
                '避免直接描述暴力场景，用推理小说风格描述',
                '将"被谋杀"改为"离奇离世"',
                '将"凶器"改为"关键物证"',
                '用"神秘事件"代替"犯罪案件"',
            ],
            showSafeBtn: true,
        },
        json_parse: {
            icon: '🧩',
            title: 'AI 返回了无法理解的格式',
            desc: 'AI 生成复杂内容时偶尔会出错，再试一次通常能成功。',
            tips: [],
            showSafeBtn: false,
        },
        schema: {
            icon: '🔍',
            title: '案件逻辑校验未通过',
            desc: 'AI 生成的案件结构不完整，再试一次吧。',
            tips: [],
            showSafeBtn: false,
        },
        network: {
            icon: '📡',
            title: '网络连接似乎不太稳定',
            desc: '请检查网络后重试。',
            tips: [],
            showSafeBtn: false,
        },
        empty: {
            icon: '📝',
            title: '背景故事不能为空',
            desc: '请输入一段背景故事来生成案件。',
            tips: [],
            showSafeBtn: false,
        },
        unknown: {
            icon: '⚠️',
            title: '案件生成遇到了意外状况',
            desc: '请稍后重试，或尝试修改背景故事内容。',
            tips: [],
            showSafeBtn: false,
        },
    };

    updateGenerationError(errorJson) {
        if (this._genTypewriterTimer) {
            clearInterval(this._genTypewriterTimer);
            this._genTypewriterTimer = null;
        }

        let errorType = 'unknown';
        try {
            const parsed = JSON.parse(errorJson);
            errorType = parsed.type || 'unknown';
        } catch (e) {
            // fallback: try to guess from raw string
            if (errorJson.includes('sensitive') || errorJson.includes('422')) {
                errorType = 'content_filter';
            } else if (errorJson.includes('JSON') || errorJson.includes('json')) {
                errorType = 'json_parse';
            }
        }

        const config = this._ERROR_CONFIGS[errorType] || this._ERROR_CONFIGS.unknown;

        let tipsHtml = '';
        if (config.tips && config.tips.length > 0) {
            tipsHtml = '<ul class="gen-error-tips">';
            config.tips.forEach((tip) => {
                tipsHtml += `<li>${this._escapeHtml(tip)}</li>`;
            });
            tipsHtml += '</ul>';
        }

        let actionsHtml = '<div class="gen-error-actions">';
        if (config.showSafeBtn) {
            actionsHtml += '<button class="gen-btn gen-btn-safe" id="gen-btn-safe">🛡️ 用安全模式重试</button>';
        }
        actionsHtml += '<button class="gen-btn gen-btn-retry" id="gen-btn-retry">🔄 重新生成</button>';
        actionsHtml += '<button class="gen-btn gen-btn-edit" id="gen-btn-edit">✏️ 修改故事</button>';
        actionsHtml += '</div>';

        const resultEl = document.getElementById('generate-result');
        if (resultEl) {
            resultEl.innerHTML = `
                <div class="gen-error-card">
                    <div class="gen-error-icon">${config.icon}</div>
                    <div class="gen-error-title">${this._escapeHtml(config.title)}</div>
                    <div class="gen-error-desc">${this._escapeHtml(config.desc)}</div>
                    ${tipsHtml}
                    ${actionsHtml}
                </div>
            `;
        }

        const safeBtn = document.getElementById('gen-btn-safe');
        if (safeBtn) {
            safeBtn.addEventListener('click', () => { this._onGenerateCase(true); });
        }

        const retryBtn = document.getElementById('gen-btn-retry');
        if (retryBtn) {
            retryBtn.addEventListener('click', () => { this._onGenerateCase(false); });
        }

        const editBtn = document.getElementById('gen-btn-edit');
        if (editBtn) {
            editBtn.addEventListener('click', () => { this._enableGenForm(); });
        }
    }

    _enableGenForm() {
        const resultEl = document.getElementById('generate-result');
        if (resultEl) resultEl.innerHTML = '';

        const generateBtn = this.footerEl?.querySelector('.modal-btn-primary');
        if (generateBtn) {
            generateBtn.disabled = false;
            generateBtn.textContent = '生成';
        }

        const storyEl = document.getElementById('generate-story');
        const modelEl = document.getElementById('generate-model');
        if (storyEl) storyEl.disabled = false;
        if (modelEl) modelEl.disabled = false;
    }

    updateGenerationComplete() {
        if (this._genTypewriterTimer) {
            clearInterval(this._genTypewriterTimer);
            this._genTypewriterTimer = null;
        }
        this.hide();
    }

    // ================================================================
    // Core
    // ================================================================

    hide() {
        if (this.backdrop) this.backdrop.classList.remove('active');
        if (this.modal) this.modal.classList.remove('active');
        this._confirmCallback = null;
        // 恢复因模态框暂停的计时器 UI 更新
        if (window.timerManager) window.timerManager.flush();
    }

    _show(title, bodyHtml, buttons) {
        if (!this.modal || !this.backdrop) {
            console.error('[ModalManager] Modal elements not found');
            return;
        }

        if (this.titleEl) {
            this.titleEl.textContent = title;
        }

        if (this.bodyEl) {
            this.bodyEl.innerHTML = bodyHtml;
        }

        if (this.footerEl) {
            this.footerEl.innerHTML = '';
            buttons.forEach((btn) => {
                const buttonEl = document.createElement('button');
                buttonEl.className = `modal-btn ${btn.class || 'modal-btn-secondary'}`;
                buttonEl.textContent = btn.text;
                buttonEl.addEventListener('click', () => {
                    const result = typeof btn.callback === 'function' ? btn.callback() : undefined;
                    if (result !== false) {
                        this.hide();
                    }
                });
                this.footerEl.appendChild(buttonEl);
            });
        }

        this.backdrop.classList.add('active');
        this.modal.classList.add('active');
    }

    _escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}
