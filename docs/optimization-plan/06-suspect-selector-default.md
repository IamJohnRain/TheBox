# BUG-6: 嫌疑人下拉框无默认值 — 优化方案

> 优先级: **P2** (体验细节)  
> 影响范围: 前端 JS  
> 可并行: 是（独立修改 `ui/web/js/suspect.js`，与其他 BUG 无文件冲突）  
> 负责 Agent: Agent-A (与 BUG-4 同 Agent)

---

## 1. 问题描述

嫌疑人下拉框默认显示"选择嫌疑人..."占位选项，用户必须手动选择才能开始审讯。但 Python 侧 `load_case()` 已经自动调用 `_on_suspect_changed(0)` 选中了第一个嫌疑人，前端下拉框显示与实际状态不一致。

## 2. 根因分析

**文件**: `ui/web/js/suspect.js:72-92`

```javascript
loadSuspects(suspects) {
    this.suspects = suspects || [];
    this.selector.innerHTML = '<option value="">选择嫌疑人...</option>';
    this.suspects.forEach((suspect, index) => {
        const option = document.createElement('option');
        option.value = String(index);
        option.textContent = suspect.name || `嫌疑人 ${index + 1}`;
        this.selector.appendChild(option);
    });
    // 重置当前状态
    this.currentIndex = -1;  // ← 没有自动选中第一个
    this._resetDisplay();    // ← 显示"未选择"和"?"
}
```

**文件**: `ui/web/js/app.js:67-98` — `initGameState` 处理器

```javascript
bridge.on('initGameState', (data) => {
    // ...
    suspectManager.loadSuspects(state.suspects);  // ← 重置 currentIndex = -1
    // ...
    const idx = state.current_suspect_index || 0;
    if (state.suspects && state.suspects[idx]) {
        chatManager.switchSuspect(state.suspects[idx].name);  // ← 切换聊天，但未选中嫌疑人
    }
});
```

**问题**：`loadSuspects()` 将 `currentIndex` 重置为 -1，之后没有调用 `selectSuspect(0)` 来同步选中状态。虽然 Python 侧已选中第一个嫌疑人，但前端下拉框仍显示占位符。

**额外问题**：`_on_suspect_changed(0)` 会通过 `selectSuspect(0)` Slot 触发 Python → JS 的 `suspect_selected` 信号，这个信号又会触发前端 `suspectManager.selectSuspect(0)` 和 `chatManager.switchSuspect()`。但 `initGameState` 处理器中已经直接调用了 `chatManager.switchSuspect()`，可能导致重复调用。

---

## 3. 详细优化方案

### 3.1 Step 1: `loadSuspects()` 自动选中第一个嫌疑人

**文件**: `ui/web/js/suspect.js:72-92`

**修改后**：

```javascript
loadSuspects(suspects) {
    this.suspects = suspects || [];
    if (!this.selector) {
        console.error('[SuspectManager] Selector element not found');
        return;
    }

    this.selector.innerHTML = '<option value="">选择嫌疑人...</option>';

    this.suspects.forEach((suspect, index) => {
        const option = document.createElement('option');
        option.value = String(index);
        option.textContent = suspect.name || `嫌疑人 ${index + 1}`;
        this.selector.appendChild(option);
    });

    // 自动选中第一个嫌疑人
    if (this.suspects.length > 0) {
        this.selectSuspect(0);
    } else {
        this.currentIndex = -1;
        this._resetDisplay();
    }
}
```

**原因**: 案件加载后，第一个嫌疑人应自动选中，与 Python 侧状态保持一致。

### 3.2 Step 2: 调整 `app.js` 的 `initGameState` 处理器

**文件**: `ui/web/js/app.js:67-98`

**修改后**：

```javascript
bridge.on('initGameState', (data) => {
    if (!data || !data.state) return;
    const state = data.state;

    if (state.suspects) {
        suspectManager.loadSuspects(state.suspects);  // loadSuspects 内部已自动选中第一个
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

    // loadSuspects 已自动 selectSuspect(0)，这里只需切换聊天上下文
    const idx = state.current_suspect_index || 0;
    if (state.suspects && state.suspects[idx]) {
        chatManager.switchSuspect(state.suspects[idx].name);
    }
});
```

**注意**：`loadSuspects()` 内部调用 `selectSuspect(0)` 只更新了前端 UI（下拉框值、嫌疑人卡片显示），不会触发 Python 侧的 `selectSuspect` Slot，因为那是通过 `change` 事件触发的，而 `selectSuspect()` 方法直接设置 `selector.value` 不触发 `change` 事件。

### 3.3 Step 3: 去掉占位选项（可选优化）

如果不想保留"选择嫌疑人..."占位符，可以完全去掉：

```javascript
loadSuspects(suspects) {
    this.suspects = suspects || [];
    if (!this.selector) {
        console.error('[SuspectManager] Selector element not found');
        return;
    }

    this.selector.innerHTML = '';  // 不再添加占位选项

    this.suspects.forEach((suspect, index) => {
        const option = document.createElement('option');
        option.value = String(index);
        option.textContent = suspect.name || `嫌疑人 ${index + 1}`;
        this.selector.appendChild(option);
    });

    if (this.suspects.length > 0) {
        this.selectSuspect(0);
    } else {
        this.currentIndex = -1;
        this._resetDisplay();
    }
}
```

**建议**：保留占位选项但默认选中第一个。这样用户在"返回主菜单"后可以看到占位符，表明没有活跃案件。需要在 `_return_to_menu()` 的前端处理中重置为占位选项。

---

## 4. 验收测试

**测试文件**: `tests/test_fix_selector_default.py`

### 4.1 单元测试

```python
# 测试1: 案件加载后下拉框默认选中第一个嫌疑人
def test_suspect_selector_default_after_load(qtbot):
    window = WebMainWindow(mock_case_data)
    # 验证 JS 侧 suspect-selector 的值
    # 使用 evaluateJavaScript 检查
    result = window.web_view.page().runJavaScript(
        "document.getElementById('suspect-selector').value", 1000
    )
    assert result == "0"  # 选中第一个

# 测试2: initGameState 后 currentIndex 为 0
def test_current_index_after_init(qtbot):
    window = WebMainWindow(mock_case_data)
    result = window.web_view.page().runJavaScript(
        "window.suspectManager.currentIndex", 1000
    )
    assert result == 0

# 测试3: 嫌疑人名称显示正确
def test_suspect_name_displayed(qtbot):
    window = WebMainWindow(mock_case_data)
    result = window.web_view.page().runJavaScript(
        "document.getElementById('suspect-name').textContent", 1000
    )
    assert result != "未选择"
```

### 4.2 手动验收

| 场景 | 操作 | 预期结果 |
|------|------|---------|
| 案件加载 | 生成/加载案件 | 下拉框默认选中第一个嫌疑人，显示其名称 |
| 切换嫌疑人 | 点击下拉框切换 | 切换正常，聊天区域更新 |
| 返回主菜单 | 点击"返回主菜单" | 下拉框重置为占位选项 |

---

## 5. 涉及文件清单

| 文件 | 修改类型 | 修改内容 |
|------|---------|---------|
| `ui/web/js/suspect.js` | 修改 | `loadSuspects()` 自动选中第一个嫌疑人 |
| `ui/web/js/app.js` | 修改 | `initGameState` 处理器简化（去掉重复的 selectSuspect 逻辑） |
| `tests/test_fix_selector_default.py` | **新增** | 验收测试 |
