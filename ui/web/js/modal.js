/**
 * @fileoverview 模态框模块。
 *
 * 管理各类模态框的显示和交互，包括信息对话框、确认对话框、
 * 存档选择对话框和结局对话框，支持 ESC 关闭和遮罩点击关闭。
 *
 * @author The Box Dev Team
 */

/**
 * ModalManager - 模态框管理类。
 *
 * 负责：
 * - 显示信息对话框（showInfo）
 * - 显示确认对话框（showConfirm）
 * - 显示存档选择列表对话框（showSaveList）
 * - 显示结局对话框（showEndingDialog）
 * - ESC 键关闭
 * - 遮罩层点击关闭
 */
class ModalManager {
    /**
     * 创建 ModalManager 实例。
     */
    constructor() {
        /** @type {HTMLElement} 遮罩层 */
        this.backdrop = document.getElementById('modal-backdrop');

        /** @type {HTMLElement} 模态框主体 */
        this.modal = document.getElementById('modal');

        /** @type {HTMLElement} 标题 */
        this.titleEl = document.getElementById('modal-title');

        /** @type {HTMLElement} 内容区 */
        this.bodyEl = document.getElementById('modal-body');

        /** @type {HTMLElement} 底部按钮区 */
        this.footerEl = document.getElementById('modal-footer');

        /** @type {HTMLElement} 关闭按钮 */
        this.closeBtn = document.getElementById('modal-close');

        /** @type {Function|null} 确认回调（用于确认对话框） */
        this._confirmCallback = null;

        this._bindEvents();
    }

    /**
     * 绑定事件监听器。
     * @private
     */
    _bindEvents() {
        // 关闭按钮
        if (this.closeBtn) {
            this.closeBtn.addEventListener('click', () => this.hide());
        }

        // 遮罩层点击关闭
        if (this.backdrop) {
            this.backdrop.addEventListener('click', () => this.hide());
        }

        // ESC 键关闭
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this._isVisible()) {
                this.hide();
            }
        });
    }

    /**
     * 检查模态框是否可见。
     * @private
     * @returns {boolean}
     */
    _isVisible() {
        return this.modal && this.modal.classList.contains('active');
    }

    /**
     * 显示信息对话框。
     *
     * @param {string} title - 对话框标题
     * @param {string} message - 对话框消息内容
     * @returns {void}
     *
     * @example
     * modalManager.showInfo('提示', '案件已生成完毕');
     */
    showInfo(title, message) {
        this._show(title, `<p>${this._escapeHtml(message)}</p>`, [
            { text: '确定', class: 'modal-btn-primary', callback: null },
        ]);
    }

    /**
     * 显示确认对话框。
     *
     * @param {string} title - 对话框标题
     * @param {string} message - 对话框消息内容
     * @param {Function} onConfirm - 确认回调函数
     * @returns {void}
     *
     * @example
     * modalManager.showConfirm('确认', '确定要退出吗？', () => {
     *     console.log('已确认');
     * });
     */
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

    /**
     * 显示存档选择对话框。
     *
     * @param {Array.<{session_id: string, name: string, date: string, summary: string}>} sessions - 存档列表
     * @returns {void}
     *
     * @example
     * modalManager.showSaveList([
     *     { session_id: 's1', name: '存档1', date: '2024-01-01', summary: '第一案' },
     *     { session_id: 's2', name: '存档2', date: '2024-01-02', summary: '第二案' }
     * ]);
     */
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

        // 绑定存档项点击事件
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

    /**
     * 显示结局对话框。
     *
     * @param {string} title - 对话框标题
     * @param {string} message - 结局描述消息
     * @returns {void}
     *
     * @example
     * modalManager.showEndingDialog('审讯结束', '你成功揭开了真相！');
     */
    showEndingDialog(title, message) {
        this._show(title, `<p>${this._escapeHtml(message)}</p>`, [
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

    /**
     * 隐藏模态框。
     */
    hide() {
        if (this.backdrop) this.backdrop.classList.remove('active');
        if (this.modal) this.modal.classList.remove('active');
        this._confirmCallback = null;
    }

    /**
     * 显示模态框（内部方法）。
     * @private
     * @param {string} title - 标题
     * @param {string} bodyHtml - 内容 HTML
     * @param {Array.<{text: string, class: string, callback: Function|null}>} buttons - 按钮配置
     */
    _show(title, bodyHtml, buttons) {
        if (!this.modal || !this.backdrop) {
            console.error('[ModalManager] Modal elements not found');
            return;
        }

        // 设置标题
        if (this.titleEl) {
            this.titleEl.textContent = title;
        }

        // 设置内容
        if (this.bodyEl) {
            this.bodyEl.innerHTML = bodyHtml;
        }

        // 设置按钮
        if (this.footerEl) {
            this.footerEl.innerHTML = '';
            buttons.forEach((btn) => {
                const buttonEl = document.createElement('button');
                buttonEl.className = `modal-btn ${btn.class || 'modal-btn-secondary'}`;
                buttonEl.textContent = btn.text;
                buttonEl.addEventListener('click', () => {
                    if (typeof btn.callback === 'function') {
                        btn.callback();
                    }
                    this.hide();
                });
                this.footerEl.appendChild(buttonEl);
            });
        }

        // 显示模态框
        this.backdrop.classList.add('active');
        this.modal.classList.add('active');
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
