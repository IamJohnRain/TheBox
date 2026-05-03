/**
 * @fileoverview 聊天消息模块。
 *
 * 管理按嫌疑人分组的聊天消息，包括消息渲染、
 * 嫌疑人切换、打字指示器等。
 */

class ChatManager {
    constructor() {
        this.container = document.getElementById('chat-container');
        this.input = document.getElementById('chat-input');
        this.sendBtn = document.getElementById('btn-send');
        this.chatTitle = document.getElementById('chat-title');
        this._typingEl = null;

        this._messagesBySuspect = {};
        this._currentSuspect = null;
    }

    addMessage(role, content, suspectName) {
        if (!this.container) return;
        if (!content || !content.trim()) return;

        this._removeTypingIndicator();

        const time = new Date().toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
        });

        const owner = role === 'player'
            ? (this._currentSuspect || '_default')
            : (suspectName || '_default');

        if (!this._messagesBySuspect[owner]) {
            this._messagesBySuspect[owner] = [];
        }
        this._messagesBySuspect[owner].push({ role, content, suspectName, time });

        if (owner === this._currentSuspect || owner === '_default' || role === 'system') {
            this._renderMessage(role, content, suspectName, time);
        }
    }

    _renderMessage(role, content, suspectName, time) {
        if (!this.container) return;

        const messageEl = document.createElement('div');
        messageEl.className = `message message-${role}`;

        // 标记消息归属嫌疑人
        const owner = role === 'player'
            ? (this._currentSuspect || '_default')
            : (suspectName || '_default');
        messageEl.setAttribute('data-suspect', owner);

        if (role === 'system') {
            messageEl.innerHTML = `
                <div class="message-content">${this._escapeHtml(content)}</div>
            `;
        } else {
            const displayName = suspectName || (role === 'player' ? '审讯员' : '嫌疑人');
            messageEl.innerHTML = `
                <span class="message-sender">${this._escapeHtml(displayName)}</span>
                <div class="message-content">${this._escapeHtml(content)}</div>
                <span class="message-time">${time}</span>
            `;
        }

        this.container.appendChild(messageEl);
        this._scrollToBottom();
    }

    switchSuspect(suspectName) {
        this._currentSuspect = suspectName;
        this._removeTypingIndicator();

        if (!this.container) return;

        // 隐藏所有消息（不销毁 DOM）
        this.container.querySelectorAll('.message').forEach(el => {
            el.classList.add('msg-hidden');
        });

        // 显示当前嫌疑人和默认消息
        const escapedName = CSS.escape(suspectName || '');
        this.container.querySelectorAll(
            `.message[data-suspect="${escapedName}"], .message[data-suspect="_default"]`
        ).forEach(el => {
            el.classList.remove('msg-hidden');
            // 已有消息不播放动画
            el.classList.add('no-animation');
        });

        // 处理占位符
        const msgs = this._messagesBySuspect[suspectName] || [];
        const defaultMsgs = this._messagesBySuspect['_default'] || [];
        if (msgs.length === 0 && defaultMsgs.length === 0) {
            this._showPlaceholder(suspectName);
        } else {
            this._hidePlaceholder();
        }

        this._scrollToBottom();
    }

    _showPlaceholder(suspectName) {
        let placeholder = this.container.querySelector('.chat-placeholder');
        if (!placeholder) {
            placeholder = document.createElement('div');
            placeholder.className = 'message message-system chat-placeholder';
            placeholder.setAttribute('data-suspect', '_placeholder');
            placeholder.innerHTML = `<div class="message-content">与 ${this._escapeHtml(suspectName || '嫌疑人')} 的对话将在这里显示...</div>`;
            this.container.appendChild(placeholder);
        }
        placeholder.classList.remove('msg-hidden');
    }

    _hidePlaceholder() {
        const placeholder = this.container.querySelector('.chat-placeholder');
        if (placeholder) placeholder.classList.add('msg-hidden');
    }

    showTypingIndicator() {
        if (!this.container || this._typingEl) return;

        this._typingEl = document.createElement('div');
        this._typingEl.className = 'message message-suspect typing-indicator';
        this._typingEl.innerHTML = `
            <div class="message-content">
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
            </div>
        `;
        this.container.appendChild(this._typingEl);
        this._scrollToBottom();
    }

    hideTypingIndicator() {
        this._removeTypingIndicator();
    }

    _removeTypingIndicator() {
        if (this._typingEl && this._typingEl.parentNode) {
            this._typingEl.parentNode.removeChild(this._typingEl);
        }
        this._typingEl = null;
    }

    clear() {
        if (!this.container) return;
        this.container.innerHTML = '';  // clear 时可以安全清空，因为是从零开始
        this._typingEl = null;
        this._messagesBySuspect = {};
        this._currentSuspect = null;

        const placeholder = document.createElement('div');
        placeholder.className = 'message message-system chat-placeholder';
        placeholder.setAttribute('data-suspect', '_placeholder');
        placeholder.innerHTML = '<div class="message-content">选择嫌疑人开始审讯...</div>';
        this.container.appendChild(placeholder);
    }

    setInputEnabled(enabled) {
        if (this.input) this.input.disabled = !enabled;
        if (this.sendBtn) this.sendBtn.disabled = !enabled;
    }

    setTitle(title) {
        if (this.chatTitle) this.chatTitle.textContent = title;
    }

    getInputText() {
        if (!this.input) return '';
        const text = this.input.value.trim();
        if (text) this.input.value = '';
        return text;
    }

    _scrollToBottom() {
        if (this.container) {
            requestAnimationFrame(() => {
                this.container.scrollTop = this.container.scrollHeight;
            });
        }
    }

    _escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}
