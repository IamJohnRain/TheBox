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
        const sessionsList = sessions || [];

        if (sessionsList.length === 0) {
            this._show('加载存档', '<p class="text-muted">没有找到存档记录</p>', [
                { text: '关闭', class: 'modal-btn-secondary', callback: null },
            ]);
            return;
        }

        let listHtml = '<div class="save-list">';
        sessionsList.forEach((session) => {
            listHtml += `
                <div class="save-item" data-session-id="${this._escapeHtml(session.session_id || '')}"
                     tabindex="0" role="button"
                     aria-label="加载存档 ${this._escapeHtml(session.name || '未命名')}">
                    <div class="save-item-info">
                        <h4 class="save-item-name">${this._escapeHtml(session.name || '未命名存档')}</h4>
                        <p class="save-item-date">${this._escapeHtml(session.date || '未知日期')}</p>
                    </div>
                    <p class="save-item-summary">${this._escapeHtml(session.summary || '')}</p>
                </div>
            `;
        });
        listHtml += '</div>';

        this._show('加载存档', listHtml, [
            { text: '取消', class: 'modal-btn-secondary', callback: null },
        ]);

        const saveItems = this.bodyEl.querySelectorAll('.save-item');
        saveItems.forEach((item) => {
            const clickHandler = () => {
                const sessionId = item.getAttribute('data-session-id');
                if (sessionId && window.bridge) {
                    window.bridge.selectSave(sessionId);
                }
                this.hide();
            };

            item.addEventListener('click', clickHandler);
            item.addEventListener('keypress', (e) => {
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
                this._onGenerateCase();
                return false;
            }},
            { text: '取消', class: 'modal-btn-secondary', callback: null },
        ]);
    }

    _onGenerateCase() {
        const story = document.getElementById('generate-story')?.value?.trim() || '';
        const model = document.getElementById('generate-model')?.value?.trim() || '';

        const resultEl = document.getElementById('generate-result');
        if (!story) {
            if (resultEl) {
                resultEl.innerHTML = '<span class="form-result-error">背景故事不能为空</span>';
            }
            return;
        }

        if (resultEl) {
            resultEl.innerHTML = '<span class="form-result-pending">正在生成案件，请耐心等待...</span>';
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
            window.bridge.submitCaseGeneration(story, model);
        }
    }

    updateGenerationProgress(message) {
        const resultEl = document.getElementById('generate-result');
        if (resultEl) {
            resultEl.innerHTML = `<span class="form-result-pending">${this._escapeHtml(message)}</span>`;
        }
    }

    updateGenerationError(errorMessage) {
        const resultEl = document.getElementById('generate-result');
        if (resultEl) {
            resultEl.innerHTML = `<span class="form-result-error">${this._escapeHtml(errorMessage)}</span>`;
        }

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
        this.hide();
    }

    // ================================================================
    // Core
    // ================================================================

    hide() {
        if (this.backdrop) this.backdrop.classList.remove('active');
        if (this.modal) this.modal.classList.remove('active');
        this._confirmCallback = null;
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
