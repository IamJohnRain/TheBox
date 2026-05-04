/**
 * @fileoverview 证据模块。
 *
 * 管理证据列表的加载、清空和交互，包括证据卡片渲染、
 * 点击出示证据时的确认对话框。
 *
 * @author The Box Dev Team
 */

/**
 * EvidenceManager - 证据管理类。
 *
 * 负责：
 * - 加载证据列表并渲染证据卡片
 * - 清空证据面板
 * - 点击证据卡片时弹出确认对话框
 * - 确认后通过 bridge.presentEvidence() 出示证据
 */
class EvidenceManager {
    /**
     * 创建 EvidenceManager 实例。
     */
    constructor() {
        /** @type {HTMLElement} 证据列表容器 */
        this.listEl = document.getElementById('evidence-list');

        /** @type {HTMLElement} 空状态提示 */
        this.emptyEl = document.getElementById('evidence-empty');

        /** @type {Array.<{id: string, name: string, description: string, related_suspect: string}>} 证据数据缓存 */
        this.evidences = [];
    }

    /**
     * 加载证据列表。
     *
     * @param {Array.<{id: string, name: string, description: string, related_suspect?: string}>} evidences - 证据数据数组
     * @returns {void}
     *
     * @example
     * evidenceManager.loadEvidences([
     *     { id: 'ev_001', name: '财务报表', description: '存在异常数据', related_suspect: '张三' },
     *     { id: 'ev_002', name: '监控录像', description: '案发当晚录像', related_suspect: '李四' }
     * ]);
     */
    loadEvidences(evidences) {
        this.evidences = evidences || [];
        if (!this.listEl) {
            console.error('[EvidenceManager] List element not found');
            return;
        }

        // 清空现有内容
        this.listEl.innerHTML = '';

        if (this.evidences.length === 0) {
            const emptyMsg = document.createElement('p');
            emptyMsg.className = 'evidence-empty';
            emptyMsg.id = 'evidence-empty';
            emptyMsg.textContent = '暂无证据';
            this.listEl.appendChild(emptyMsg);
            return;
        }

        // 逐条添加证据卡片
        this.evidences.forEach((evidence) => {
            this._addEvidenceCard(evidence);
        });
    }

    /**
     * 清空证据面板。
     */
    clear() {
        this.evidences = [];
        if (this.listEl) {
            this.listEl.innerHTML = '<p class="evidence-empty" id="evidence-empty">暂无证据</p>';
        }
    }

    /**
     * 渲染单个证据卡片到列表。
     * @private
     * @param {{id: string, name: string, description: string, related_suspect?: string, isNew?: boolean}} evidence - 证据数据
     */
    _addEvidenceCard(evidence) {
        if (!this.listEl) return;

        const emptyMsg = this.listEl.querySelector('.evidence-empty');
        if (emptyMsg) {
            emptyMsg.remove();
        }

        const card = document.createElement('div');
        card.className = 'evidence-card card-hoverable' + (evidence.isNew ? ' new' : '');
        card.setAttribute('role', 'listitem');
        card.setAttribute('data-evidence-id', evidence.id);
        card.setAttribute('tabindex', '0');

        card.innerHTML = `
            <div class="evidence-header">
                <div class="evidence-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                        <line x1="16" y1="13" x2="8" y2="13"/>
                        <line x1="16" y1="17" x2="8" y2="17"/>
                        <polyline points="10 9 9 9 8 9"/>
                    </svg>
                </div>
                <h4 class="evidence-title">${this._escapeHtml(evidence.name || '未知证据')}</h4>
            </div>
            <p class="evidence-description">${this._escapeHtml(evidence.description || '')}</p>
            <button class="evidence-expand-btn" style="display:none;">展开</button>
        `;

        const descEl = card.querySelector('.evidence-description');
        const expandBtn = card.querySelector('.evidence-expand-btn');

        requestAnimationFrame(() => {
            if (descEl && descEl.scrollHeight > descEl.clientHeight + 4) {
                expandBtn.style.display = 'inline-block';
            }
        });

        if (expandBtn) {
            expandBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (descEl.classList.contains('expanded')) {
                    descEl.classList.remove('expanded');
                    expandBtn.textContent = '展开';
                } else {
                    descEl.classList.add('expanded');
                    expandBtn.textContent = '收起';
                }
            });
        }

        card.addEventListener('click', (e) => {
            if (e.target.closest('.evidence-expand-btn')) return;
            this._onEvidenceClick(evidence);
        });

        card.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.target.closest('.evidence-expand-btn')) {
                this._onEvidenceClick(evidence);
            }
        });

        this.listEl.appendChild(card);

        this.listEl.scrollTop = this.listEl.scrollHeight;
    }

    /**
     * 证据卡片点击处理。
     * 弹出确认对话框，确认后调用 bridge.presentEvidence()。
     * @private
     * @param {{id: string, name: string}} evidence - 证据数据
     */
    _onEvidenceClick(evidence) {
        if (!window.modalManager) return;
        const modal = window.modalManager;
        const bodyHtml = `
            <div class="evidence-detail-modal">
                <div class="evidence-detail-header">
                    <div class="evidence-detail-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                            <polyline points="14 2 14 8 20 8"/>
                            <line x1="16" y1="13" x2="8" y2="13"/>
                            <line x1="16" y1="17" x2="8" y2="17"/>
                            <polyline points="10 9 9 9 8 9"/>
                        </svg>
                    </div>
                    <h3 class="evidence-detail-title">${modal._escapeHtml(evidence.name || '未知证据')}</h3>
                </div>
                <div class="evidence-detail-body">
                    <p>${modal._escapeHtml(evidence.description || '暂无详情')}</p>
                </div>
            </div>
        `;
        modal._show(evidence.name || '证据详情', bodyHtml, [
            { text: '出示证据', class: 'modal-btn-primary modal-btn-full', callback: () => {
                if (window.bridge) {
                    window.bridge.presentEvidence(evidence.id);
                }
            }},
        ]);
    }

    /**
     * HTML 转义，防止 XSS。
     * @private
     * @param {string} text - 原始文本
     * @returns {string} 转义后的安全文本
     */
    _escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}
