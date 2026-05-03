# The Box 优化方案 — 主索引（修订版 v2.0）

> 版本: 2.0（评审后修订）  
> 日期: 2026-05-03  
> 状态: 待实施  
> 评审报告: [REVIEW-REPORT.md](REVIEW-REPORT.md)

## 修订说明

基于架构评审（架构专家 + 架构师A + 架构师B）的综合意见，对原方案进行以下修订：

| 修订项 | 原方案 | 修订后 | 原因 |
|--------|--------|--------|------|
| BUG-1 DOM 缓存 | 消息对象挂载 `_domElement` | 使用 `data-suspect` 属性 + CSS class | 避免内存泄漏和职责混乱 |
| BUG-5 信号设计 | `disable_all_actions` / `enable_all_actions` 两个信号 | `set_game_interactive(bool)` 单一信号 | 与 `set_input_enabled(bool)` 模式一致 |
| BUG-5 `load_case()` | 缺少操作启用逻辑 | 增加 `set_game_interactive.emit(True)` | 修复 `_restart()` 后操作无法恢复的 P0 问题 |
| BUG-5 复盘加载 | 使用 `show_dialog` | 使用 `show_loading` | 避免用户关闭 dialog 后 Worker 仍在运行 |
| BUG-4 `from_dict()` | 不修改 | 增加 `case_id`/`case_title` 恢复 | 确保恢复后的引擎状态完整 |
| BUG-3 优先级 | P2 | P2（建议延后） | 不应阻塞 P0 BUG 修复 |
| BUG-1 动画控制 | `style.animation = 'none'` | CSS class `.no-animation` | 避免内联样式不可恢复 |

---

## 问题总览

| 编号 | 问题 | 优先级 | 影响范围 | 方案文档 | 评审结论 |
|------|------|--------|---------|---------|---------|
| BUG-4 | 存档读档失败（"未知案件"） | **P0** | 后端 Python | [04-save-load-bug.md](04-save-load-bug.md) | 通过 |
| BUG-5 | 嫌疑人崩溃后流程错误 + 缺少复盘打分 | **P0** | 前端+后端 | [05-breakdown-flow-and-review.md](05-breakdown-flow-and-review.md) | 需修改 |
| BUG-1 | 页面闪动（生成案件/读档时） | P1 | 前端 JS/CSS | [01-page-flicker.md](01-page-flicker.md) | 需修改 |
| BUG-2 | 系统日志不规范 | P1 | 后端 Python 全局 | [02-logging-standardization.md](02-logging-standardization.md) | 通过 |
| BUG-6 | 嫌疑人下拉框无默认值 | P2 | 前端 JS | [06-suspect-selector-default.md](06-suspect-selector-default.md) | 通过 |
| BUG-3 | 缺少日志查询页面 + 启动参数日志级别 | P2 | 前端+后端 | [03-log-viewer-page.md](03-log-viewer-page.md) | 建议延后 |

---

## 信号机制统一设计（评审新增）

原方案中信号设计不一致，修订后统一为以下模式：

```python
# ui/web_bridge.py — 统一信号设计

# 细粒度控制（已有）
set_input_enabled = Signal(bool)        # 仅控制聊天输入框+发送按钮

# 粗粒度控制（修订：合并为单一信号）
set_game_interactive = Signal(bool)     # 控制所有游戏操作（输入框、下拉框、施压/共情、证据）
```

**前端处理**（`app.js`）：
```javascript
bridge.on('gameInteractive', (enabled) => {
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
    document.querySelectorAll('.evidence-card').forEach(card => {
        card.style.pointerEvents = enabled ? '' : 'none';
        card.style.opacity = enabled ? '' : '0.5';
    });
});
```

---

## 多 Agent 并行修复策略（修订版）

### 依赖关系图

```
Phase 1 (并行，3组同时开工):
  Agent-A: BUG-4 + BUG-6
    → core/db.py, core/interrogation.py, ui/web_main_window.py(load_case/_on_save_*/_on_load_*), ui/web/js/suspect.js

  Agent-B: BUG-2
    → core/logger.py, core/llm_client.py, core/suspect_agent.py, core/interrogation.py, ui/web_main_window.py(日志)

  Agent-C: BUG-5
    → ui/web_main_window.py(_on_worker_finished/_handle_ending/_restart/_return_to_menu),
      ui/web_bridge.py, ui/web/js/bridge.js, ui/web/js/app.js, ui/web/js/modal.js,
      新增 core/review_generator.py

Phase 2 (串行，等 Phase 1 完成):
  Agent-A: BUG-1
    → ui/web/js/chat.js, ui/web/css/components.css, ui/web_main_window.py(_on_case_generated)

  Agent-B: BUG-3（建议延后）
    → main.py, core/logger.py, ui/web_bridge.py, ui/web_main_window.py,
      新增 core/log_handler.py, ui/web/js/log-viewer.js, ui/web/css/log-viewer.css

Phase 3: 全量回归测试
```

### 文件冲突解决方案

**关键冲突点**：`load_case()` 方法

- **Agent-A** 负责：增加 `db.save_case()` 调用、`case_id` 生成逻辑
- **Agent-C** 不直接修改 `load_case()`，而是在 `_restart()` 中调用 `load_case()`（已包含 Agent-A 的修改）
- **Agent-C** 在 `_return_to_menu()` 中调用 `set_game_interactive.emit(False)`

**`web_main_window.py` 修改区域划分**：

| 行号范围 | 方法 | 负责 Agent |
|---------|------|-----------|
| 185-206 | `load_case()` | Agent-A |
| 271-276 | `_on_worker_finished()` | Agent-C |
| 346-359 | `_handle_ending()` | Agent-C |
| 361-375 | `_restart()` | Agent-C |
| 377-390 | `_return_to_menu()` | Agent-C |
| 507-525 | `_on_save_game()` | Agent-A |
| 527-554 | `_on_load_game()` | Agent-A |
| 556-603 | `_on_save_selected()` | Agent-A |
| 新增 | `_on_review_requested()` 等 | Agent-C |
| 新增 | 日志相关方法 | Agent-B |

---

## 验收测试策略（修订版）

| BUG | 验收方式 | 验收脚本 | 评审补充 |
|-----|---------|---------|---------|
| BUG-1 | 视觉检查 + 自动化测试 | `pytest tests/test_fix_flicker.py -v` | 需手动测试切换嫌疑人场景 |
| BUG-2 | 日志输出检查 | `pytest tests/test_fix_logging.py -v` | 需验证日志中无敏感信息泄露 |
| BUG-3 | 功能测试 + 启动参数测试 | `pytest tests/test_fix_log_viewer.py -v` | 需测试高日志频率场景 |
| BUG-4 | 存档/读档端到端测试 | `pytest tests/test_fix_save_load.py -v` | 需测试 case_id 缺失的边缘情况 |
| BUG-5 | 游戏流程端到端测试 | `pytest tests/test_fix_breakdown_flow.py -v` | 需测试 restart 后操作恢复 |
| BUG-6 | UI 初始化测试 | `pytest tests/test_fix_selector_default.py -v` | 需测试返回主菜单后重置 |

---

## 实施顺序建议（修订版）

```
Phase 1 (并行):  BUG-4, BUG-5, BUG-2, BUG-6  ← 4个任务同时开工
Phase 2 (串行):  BUG-1                        ← 等 BUG-5 完成后开工
Phase 3 (可选):  BUG-3                        ← 建议延后，不阻塞主流程
Phase 4:         全量回归测试 + 集成验收
```

**总预估工时**：~580min（9.5h）
- Phase 1: ~2.5h（并行）
- Phase 2: ~1.5h
- Phase 3: ~2.5h（可选）
- Phase 4: ~0.75h

---

## 关键修改清单（评审后新增/修订）

### BUG-1 修订

**Step 1 修订**：使用 `data-suspect` 属性 + CSS class 替代 `_domElement` 缓存

```javascript
// chat.js — _renderMessage() 修订
_renderMessage(role, content, suspectName, time) {
    if (!this.container) return;
    const messageEl = document.createElement('div');
    messageEl.className = `message message-${role}`;
    messageEl.setAttribute('data-suspect', 
        role === 'player' ? (this._currentSuspect || '_default') : (suspectName || '_default')
    );
    // ... innerHTML 设置 ...
    this.container.appendChild(messageEl);
    this._scrollToBottom();
}

// chat.js — switchSuspect() 修订
switchSuspect(suspectName) {
    this._currentSuspect = suspectName;
    this._removeTypingIndicator();
    if (!this.container) return;

    // 隐藏所有消息
    this.container.querySelectorAll('.message').forEach(el => {
        el.classList.add('msg-hidden');
    });

    // 显示当前嫌疑人和默认消息
    this.container.querySelectorAll(
        `.message[data-suspect="${CSS.escape(suspectName)}"], .message[data-suspect="_default"]`
    ).forEach(el => {
        el.classList.remove('msg-hidden');
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
```

```css
/* components.css — 新增 */
.message.msg-hidden { display: none; }
.message.no-animation { animation: none; }
```

**Step 6 修订**：使用 CSS class 替代内联样式

### BUG-4 修订

**Step 3 修订**：`from_dict()` 增加 `case_id`/`case_title` 恢复

```python
@staticmethod
def from_dict(state: dict, case_data: dict) -> "InterrogationEngine":
    engine = InterrogationEngine(case_data)
    # ... 现有恢复逻辑 ...
    
    # 修订：确保 case_data 包含 case_id
    if "case_id" not in engine.case and state.get("case_id"):
        engine.case["case_id"] = state["case_id"]
    if "title" not in engine.case and state.get("case_title"):
        engine.case["title"] = state["case_title"]
    
    return engine
```

### BUG-5 修订

**Step 2 修订**：合并为单一信号

```python
# ui/web_bridge.py
set_game_interactive = Signal(bool)  # 替代 disable_all_actions / enable_all_actions
```

**Step 3 修订**：`_handle_ending()` 使用新信号

```python
def _handle_ending(self, state_event):
    self._countdown_timer.stop()
    self.bridge.set_game_interactive.emit(False)  # 禁用所有操作
    # ... 后续不变 ...
```

**Step 6 修订**：复盘加载使用 `show_loading`

```python
def _on_review_requested(self):
    if self.engine is None:
        return
    if self._review_worker and self._review_worker.isRunning():
        return
    self._review_worker = ReviewWorker(self.engine)
    self._review_worker.finished.connect(self._on_review_ready)
    self._review_worker.error.connect(self._on_review_error)
    self._review_worker.start()
    self.bridge.show_loading.emit("正在生成审讯复盘报告...", False)  # 替代 show_dialog

def _on_review_ready(self, review_data):
    self._review_worker = None
    self.bridge.hide_loading.emit()  # 隐藏加载提示
    self.bridge.show_review.emit(review_data)

def _on_review_error(self, error_msg):
    self._review_worker = None
    self.bridge.hide_loading.emit()
    self.bridge.show_dialog.emit("复盘失败", f"生成复盘报告失败: {error_msg}")
```

**Step 8 修订**：`load_case()` 增加操作启用

```python
def load_case(self, case_data):
    """加载案件到引擎并更新 UI。"""
    # ... 现有逻辑 ...
    self.bridge.init_game_state.emit(state)
    self.bridge.set_game_interactive.emit(True)  # 修订：启用所有操作
    # ... 后续不变 ...
```

**`_return_to_menu()` 修订**：

```python
def _return_to_menu(self):
    self.engine = None
    self.bridge.clear_chat.emit()
    self.bridge.set_game_interactive.emit(False)  # 禁用所有操作
    self._countdown_timer.stop()
```

---

## 附录

### 评审报告
- 完整评审报告：[REVIEW-REPORT.md](REVIEW-REPORT.md)

### 涉及文件总览

| 文件 | 修改类型 | 涉及 BUG |
|------|---------|---------|
| `core/db.py` | 修改 | BUG-4 |
| `core/interrogation.py` | 修改 | BUG-4, BUG-5 |
| `core/llm_client.py` | 修改 | BUG-2 |
| `core/logger.py` | 修改 | BUG-2, BUG-3 |
| `core/suspect_agent.py` | 修改 | BUG-2 |
| `core/review_generator.py` | **新增** | BUG-5 |
| `core/log_handler.py` | **新增** | BUG-3 |
| `main.py` | 修改 | BUG-3 |
| `ui/web_bridge.py` | 修改 | BUG-3, BUG-5 |
| `ui/web_main_window.py` | 修改 | BUG-1, BUG-2, BUG-3, BUG-4, BUG-5 |
| `ui/web/js/chat.js` | 修改 | BUG-1 |
| `ui/web/js/suspect.js` | 修改 | BUG-6 |
| `ui/web/js/app.js` | 修改 | BUG-3, BUG-5 |
| `ui/web/js/modal.js` | 修改 | BUG-5 |
| `ui/web/js/bridge.js` | 修改 | BUG-3, BUG-5 |
| `ui/web/js/log-viewer.js` | **新增** | BUG-3 |
| `ui/web/index.html` | 修改 | BUG-3 |
| `ui/web/css/components.css` | 修改 | BUG-1 |
| `ui/web/css/log-viewer.css` | **新增** | BUG-3 |
