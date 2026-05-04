# BUG-1: 页面闪动 — 优化方案（修订版 v2.0）

> 优先级: **P1** (用户体验严重受损)  
> 影响范围: 前端 JS + CSS  
> 可并行: **否** — 需等 BUG-5 的 `_on_worker_finished` 修复后再开工  
> 负责 Agent: Agent-A (组2)  
> 评审状态: **需修改后通过**

---

## 修订说明

| 修订项 | 原方案 | 修订后 | 原因 |
|--------|--------|--------|------|
| DOM 缓存策略 | 消息对象挂载 `_domElement` | 使用 `data-suspect` 属性 + CSS class | 避免内存泄漏和职责混乱 |
| 动画控制 | `style.animation = 'none'` 内联样式 | CSS class `.no-animation` | 避免内联样式不可恢复 |
| `_showOrRenderMessage` | 新增方法 | 删除，复用 `_renderMessage` | 减少职责重叠 |

---

## 1. 问题描述

点击按钮（特别是"生成案件"完成后、"读档"选择存档后）页面会出现闪动。生成新案件窗口的闪动为非必现，与浏览器渲染时序竞争有关。

## 2. 根因分析

### 2.1 根因 A（严重）：`chatManager.switchSuspect()` 销毁整个聊天 DOM 再逐条重建

**文件**: `ui/web/js/chat.js:68-94`

```javascript
switchSuspect(suspectName) {
    this._currentSuspect = suspectName;
    this._removeTypingIndicator();
    if (!this.container) return;
    this.container.innerHTML = '';  // ← 同步销毁所有子节点，浏览器立刻渲染空白帧
    // ... 随后逐条 _renderMessage() 重建
}
```

每条消息重建时触发 `message-fade-in 0.4s` 动画（`components.css:290`），导致消息一条条淡入。

### 2.2 根因 B（严重）：存档加载时双重清空

**文件**: `ui/web_main_window.py:572,587`

```python
self.bridge.clear_chat.emit()       # 第一次清空 → chatManager.clear() → 空白+占位符
# ...
self.bridge.init_game_state.emit(state)  # 第二次清空 → switchSuspect() → innerHTML=''
```

### 2.3 根因 C（中等）：Modal 关闭动画与页面重渲染时序竞争

**文件**: `web_main_window.py:481-485`

```python
def _on_case_generated(self, case_dict):
    self.bridge.case_generation_complete.emit(case_dict)  # → JS: modalManager.hide() (0.3s transition)
    self._case_gen_worker = None
    self.load_case(case_dict)  # → 立即触发 initGameState → switchSuspect() → DOM 重建
```

### 2.4 根因 D（轻微）：`backdrop-filter: blur(4px)` 触发全视口合成层切换

**文件**: `components.css:476,559`

---

## 3. 详细优化方案（修订版）

### 3.1 Step 1: 优化 `chatManager.switchSuspect()` — 使用 CSS class 控制显示/隐藏

**文件**: `ui/web/js/chat.js`  
**策略**: 使用 `data-suspect` 属性标记消息，通过 CSS class 控制显示/隐藏，替代 `innerHTML=''`

**修改 `_renderMessage()`**：

```javascript
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
```

**修改 `switchSuspect()`**：

```javascript
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
```

**修改 `clear()`**：

```javascript
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
```

**CSS 新增**（`components.css`）：

```css
/* 消息显示/隐藏控制 */
.message.msg-hidden { display: none; }
.message.no-animation { animation: none; }
```

**优势**：
- 不在消息对象上挂载 DOM 引用，避免内存泄漏
- 使用 CSS class 控制，可恢复、可调试
- `data-suspect` 属性清晰标记消息归属
- `CSS.escape()` 处理特殊字符

### 3.2 Step 2: 删除存档加载时的冗余 `clear_chat` 信号

**文件**: `ui/web_main_window.py:556-603` — `_on_save_selected()`

**修改**: 删除第 572 行的 `self.bridge.clear_chat.emit()`，因为 `initGameState` → `switchSuspect()` 已包含清空逻辑。

```python
def _on_save_selected(self, session_id):
    try:
        result = db.load_full_session(session_id)
        if result is None:
            self.bridge.show_dialog.emit("读档失败", "存档数据不存在")
            return

        case_id, engine_state_dict = result
        case_data = db.load_case(case_id)
        if case_data is None:
            ...  # 降级处理（见 BUG-4 方案）

        self.engine = InterrogationEngine.from_dict(engine_state_dict, case_data)

        # 删除: self.bridge.clear_chat.emit()  ← 不再需要，switchSuspect 已处理

        state = { ... }
        self.bridge.init_game_state.emit(state)
        # ... 后续不变
```

### 3.3 Step 3: 修复 Modal `transition: all` 过度动画

**文件**: `ui/web/css/components.css:572-595`

**修改后**：
```css
.modal {
    ...
    transition: opacity 0.3s ease, visibility 0.3s ease, transform 0.3s ease;
}
```

### 3.4 Step 4: 案件生成完成后延迟加载

**文件**: `ui/web_main_window.py:481-485`

**修改后**：
```python
def _on_case_generated(self, case_dict):
    self.bridge.case_generation_complete.emit(case_dict)
    self._case_gen_worker = None
    # 延迟加载案件，等 modal 关闭动画完成
    QTimer.singleShot(350, lambda: self.load_case(case_dict))
```

### 3.5 Step 5: 为 overlay 增加合成层提升

> **⚠️ 已废弃** — `will-change: transform` 在 Qt WebEngine 中会强制创建 GPU 合成层，与频闪根因一致，不应使用。参见 `docs/ui-modal-evidence-bug-fix-plan-v2.md` 的修订说明和 Fix-A 修复方案，该方案已移除所有 `will-change`/`contain`/`backface-visibility` 合成层属性。

~~**文件**: `ui/web/css/components.css`~~

~~```css
.loading-overlay {
    ...
    will-change: transform;
}

.modal-backdrop {
    ...
    will-change: transform;
}
```~~

---

## 4. 验收测试

### 4.1 手动验收清单

| 场景 | 操作 | 预期结果 | 是否闪动 |
|------|------|---------|---------|
| 生成案件 | 点击"生成案件"→ 填写背景 → 生成 | 案件加载后界面平滑切换 | 否 |
| 读档 | 点击"读档"→ 选择存档 | 聊天记录平滑恢复 | 否 |
| 切换嫌疑人 | 点击下拉框切换 | 聊天记录瞬间切换，无闪烁 | 否 |
| 多次切换 | 快速切换嫌疑人 A→B→A | 消息正确显示，无丢失 | 否 |
| 施压/共情 | 点击施压/共情按钮 | 消息正常添加，无闪烁 | 否 |

### 4.2 自动化测试

```python
def test_switch_suspect_uses_css_class():
    """验证 switchSuspect 使用 CSS class 而非 innerHTML=''"""
    # 检查 chat.js 源码不包含 container.innerHTML = ''
    # 检查消息元素有 data-suspect 属性
    ...

def test_save_selected_no_double_clear(qtbot):
    """验证存档加载不触发双重 clear_chat"""
    ...
```

---

## 5. 涉及文件清单

| 文件 | 修改类型 | 修改内容 |
|------|---------|---------|
| `ui/web/js/chat.js` | 修改 | `switchSuspect()` 改为 CSS 隐藏/显示；`_renderMessage()` 增加 `data-suspect` 属性；新增 `_showPlaceholder()`/`_hidePlaceholder()` |
| `ui/web_main_window.py` | 修改 | `_on_save_selected()` 删除冗余 `clear_chat`；`_on_case_generated()` 延迟加载 |
| `ui/web/css/components.css` | 修改 | `.modal` transition 精确化；overlay 增加 `will-change`；新增 `.msg-hidden`/`.no-animation` |
| `tests/test_fix_flicker.py` | **新增** | 验收测试 |

---

## 6. 分步实施顺序

1. **Step 1**: 优化 `switchSuspect()` 的 DOM 策略（核心修复，约 45min）
2. **Step 2**: 删除冗余 `clear_chat`（简单，约 5min）
3. **Step 3**: 修复 Modal transition（简单，约 5min）
4. **Step 4**: 延迟加载案件（简单，约 10min）— 已由 `ui-modal-evidence-bug-fix-plan-v2.md` Fix-B 实施并扩展
5. **Step 5**: ~~合成层提升~~ **已废弃**，参见 `docs/ui-modal-evidence-bug-fix-plan-v2.md`
6. 验收测试（约 20min）

建议 Step 1 完成后先手动测试，确认闪动消除后再做 Step 2-5。
