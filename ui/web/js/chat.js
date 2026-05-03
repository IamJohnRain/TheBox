/**
 * @fileoverview 聊天消息模块。
 *
 * 管理聊天消息的添加、清空和输入控制，区分消息类型（玩家/嫌疑人/系统），
 * 并支持自动滚动到底部。
 *
 * @author The Box Dev Team
 */

/**
 * ChatManager - 聊天消息管理类。
 *
 * 负责：
 * - 向聊天容器添加不同类型的消息（player/suspect/system）
 * - 清空聊天记录
 * - 启用/禁用输入框和发送按钮
 * - 自动滚动到最新消息
 */
class ChatManager {
    /**
     * 创建 ChatManager 实例。
     */
    constructor() {
        /** @type {HTMLElement} 聊天消息容器 */
        this.container = document.getElementById('chat-container');

        /** @type {HTMLInputElement} 聊天输入框 */
        this.input = document.getElementById('chat-input');

        /** @type {HTMLButtonElement} 发送按钮 */
        this.sendBtn = document.getElementById('btn-send');

        /** @type {HTMLHeadingElement} 聊天标题 */
        this.chatTitle = document.getElementById('chat-title');
    }

    /**
     * 添加消息到聊天流。
     *
     * @param {string} role - 消息角色：'player'（玩家）、'suspect'（嫌疑人）、'system'（系统）
     * @param {string} content - 消息内容
     * @param {string} [suspectName] - 嫌疑人名称（角色为 suspect 或 player 时显示）
     * @returns {void}
     *
     * @example
     * chatManager.addMessage('player', '你当时在哪里？', '审讯员');
     * chatManager.addMessage('suspect', '我在家...', '张三');
     * chatManager.addMessage('system', '审讯开始');
     */
    addMessage(role, content, suspectName) {
        if (!this.container) {
            console.error('[ChatManager] Container element not found');
            return;
        }

        if (!content || !content.trim()) {
            console.warn('[ChatManager] Empty message ignored');
            return;
        }

        const messageEl = document.createElement('div');
        messageEl.className = `message message-${role}`;

        const time = new Date().toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
        });

        if (role === 'system') {
            messageEl.innerHTML = `
                <div class="message-content">${this._escapeHtml(content)}</div>
            `;
        } else {
            const displayName =
                suspectName || (role === 'player' ? '审讯员' : '嫌疑人');
            messageEl.innerHTML = `
                <span class="message-sender">${this._escapeHtml(displayName)}</span>
                <div class="message-content">${this._escapeHtml(content)}</div>
                <span class="message-time">${time}</span>
            `;
        }

        this.container.appendChild(messageEl);
        this._scrollToBottom();
    }

    /**
     * 清空聊天记录。
     * 保留一条系统提示消息。
     */
    clear() {
        if (!this.container) return;
        this.container.innerHTML = '';
        // 添加默认系统提示
        const placeholder = document.createElement('div');
        placeholder.className = 'message message-system';
        placeholder.innerHTML = '<div class="message-content">选择嫌疑人开始审讯...</div>';
        this.container.appendChild(placeholder);
    }

    /**
     * 启用或禁用聊天输入。
     *
     * @param {boolean} enabled - true 启用，false 禁用
     */
    setInputEnabled(enabled) {
        if (this.input) {
            this.input.disabled = !enabled;
        }
        if (this.sendBtn) {
            this.sendBtn.disabled = !enabled;
        }
    }

    /**
     * 设置聊天标题。
     *
     * @param {string} title - 标题文本
     */
    setTitle(title) {
        if (this.chatTitle) {
            this.chatTitle.textContent = title;
        }
    }

    /**
     * 获取输入框文本并清空。
     *
     * @returns {string} 输入的文本，空字符串表示无有效输入
     */
    getInputText() {
        if (!this.input) return '';
        const text = this.input.value.trim();
        if (text) {
            this.input.value = '';
        }
        return text;
    }

    /**
     * 自动滚动到聊天底部。
     * @private
     */
    _scrollToBottom() {
        if (this.container) {
            // 使用 requestAnimationFrame 确保在 DOM 更新后执行
            requestAnimationFrame(() => {
                this.container.scrollTop = this.container.scrollHeight;
            });
        }
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
