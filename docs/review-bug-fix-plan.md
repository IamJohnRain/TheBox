# 架构评审报告

## 基本信息
- 方案名称：Bug 修复方案：存档/读档、独立对话上下文、出示证件、移除蒙版
- 评审日期：2026-05-03
- 方案文档：`docs/fix-bug-fix-plan.md`
- 参与评审：架构专家、架构师A、架构师B

## 评审结论
| 维度 | 架构专家 | 架构师A | 架构师B | 综合结论 |
|------|---------|---------|---------|----------|
| 技术可行性 | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐½ |
| 架构合理性 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| 实现难度 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| 风险评估 | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐½ |

**总体结论**：**需修改后通过**

> 方案的 4 个 Bug 根因分析准确，TDD 方法论值得肯定，修复顺序和依赖关系合理。但存在 2 个 P0 级问题（Fix-4 超时保护丢失、用户取消操作入口丢失）和若干 P1 级问题，必须在实施前修复。预估总工作量从方案估算的 ~4.5 天调整为 ~6 天。

---

## 技术可行性评估

### 架构专家分析

**逐项根因验证结果：**

| Fix | 根因描述 | 源码验证 | 结论 |
|-----|---------|---------|------|
| Fix-4 | `_start_worker()` 同时 emit `show_loading` + `show_typing_indicator` | `web_main_window.py:273` 确有 `self.bridge.show_loading.emit(loading_msg, True)` | ✅ 正确 |
| Fix-3 | `evidence.js` 使用 `evidence.title`（undefined）和 `evidence.tag`（undefined） | `evidence.js:111` 用 `evidence.title`，`evidence.js:113` 用 `evidence.tag`；`EvidenceData` 定义只有 `id/name/description/related_suspect` | ✅ 正确 |
| Fix-1 | 存档提示无案件名/时间；读档字段名不匹配；`time_left` ≠ `timeLeft`；未 emit `clear_chat`；未恢复聊天历史 | `web_main_window.py:563-564` 只显示 UUID；`:577` 发送 `created_at` 非 `date`；`:205` 用 `time_left`；`:589-625` 无 `clear_chat` 和聊天恢复 | ✅ 正确 |
| Fix-2 | ChatManager 使用单一 `#chat-container`，无按嫌疑人分组 | `chat.js` 无 `_messagesBySuspect`/`_currentSuspect`/`switchSuspect()`；`app.js:217-223` 切换嫌疑人未调用 chatManager | ✅ 正确 |

**发现的关键问题：**

1. **Fix-4 删除超时定时器导致 Worker 可能永久挂起**：`_timeout_timer`（60s）是 WebWorker 的唯一超时保护。`WebWorker.run()` 中 `engine.submit_action()` 是阻塞调用，若 LLM 服务无响应（不返回错误也不返回结果），Worker 线程将永远挂起，`_current_worker` 永不为 None，后续所有操作被 `_start_worker()` 的 `if self._current_worker and self._current_worker.isRunning()` 拦截，**系统完全卡死**。

2. **Fix-4 删除 loading overlay 后用户失去取消操作入口**：当前唯一的取消入口是 `loading.js:49-57` 的取消按钮，通过 `bridge.cancelOperation()` → `_on_cancel_operation()` 触发。删除 overlay 后，此入口消失。

3. **Fix-1 与 Fix-2 存在时序耦合**：`_on_save_selected()` 的信号发射顺序必须为 `clear_chat` → `init_game_state`（含 `switchSuspect`）→ `add_message` 序列，否则消息归属会错乱。方案中顺序正确，但未显式标注此为关键约束。

4. **Python 端回调导致 player 消息重复**：`app.js:241` 的 `sendMessage()` 先 `addMessage('player', text, '审讯员')`，Worker 完成后 `update_ui_from_engine()` 又 emit `add_message(role='player', ...)`，导致玩家消息在聊天区域出现两次。这是**已有问题**，但 Fix-2 应考虑解决。

5. **state dict 命名约定不一致**：方案将 `time_left` 改为 `timeLeft`（camelCase），但 `current_suspect_index` 仍保持 snake_case。`app.js:232` 读 `state.current_suspect_index`，与 `timeLeft` 风格不统一。

### 架构师A意见

- Fix-3/4 根因正确，方案可行
- Fix-1 的 `time_left` → `timeLeft` 是**破坏性变更**，`test_web_integration.py` 中断言 `time_left` 会失败
- Fix-1 读档恢复聊天时 `add_message.emit("player", content, "审讯员")` 的 role 映射需验证
- Fix-4 删除超时保护后需在文档中明确说明
- Fix-2 chat.js 重写与现有架构差异大，需仔细验证与 app.js 集成

### 架构师B意见

- Fix-3 根因验证通过，字段映射正确
- Fix-4 存在 P0 级问题：删除 `_timeout_timer` 后 Worker 可能永久挂起；删除 loading overlay 后用户无法取消操作
- Fix-1 与 Fix-2 的 `_on_save_selected()` 时序配合需严格：`clear_chat` → `init_game_state` → `add_message` 序列
- 方案遗漏了对 `web_bridge.py`（3个信号）、`bridge.js`（3个监听器）、`app.js`（3个事件处理）、`loading.js`（整个文件150行）、`index.html`（`#loading-overlay` DOM）的同步清理
- Fix-2 的 `addMessage` 中 `role='suspect'` 且 `suspectName` 为空时，消息会归到 `_default` 分组，切换嫌疑人时丢失

### 共识点

1. 四个 Bug 的根因分析均经源码验证**正确无误**
2. Fix-4 删除超时保护机制是危险的设计决策，三方均认为风险较高
3. Fix-2 的 ChatManager 完整重写风险偏高，应考虑增量式修改
4. Fix-1 的 `time_left` → `timeLeft` 是破坏性变更，需全面更新已有测试
5. 方案遗漏了对 loading 相关代码的同步清理

### 分歧点

| 问题 | 架构专家 | 架构师A | 架构师B | 采纳结论 | 理由 |
|------|---------|---------|---------|----------|------|
| Fix-4 超时保护删除的严重程度 | P0 | P1 | P0 | **P0** | Worker 线程永久挂起会导致系统完全不可用，这是不可接受的。A 标记为 P1 可能低估了影响 |
| Python 回调导致重复 player 消息 | P1 | 未提及 | P2 | **P1** | 虽然是已有问题，但 Fix-2 改变了消息存储逻辑，重复消息会同时出现在 `_messagesBySuspect` 和 DOM 中，影响更严重 |
| 是否需要在本轮清理 loading 相关死代码 | P1 | P2 | P1 | **P1** | 大量死代码（信号定义、JS 监听器、DOM 元素、整个 loading.js）会影响可维护性，建议本轮清理 |

### 综合结论

技术可行性总体**通过**，根因分析和修复方向正确。但 Fix-4 存在 2 个 P0 级问题（超时保护、取消入口），必须在实施前修改方案。Fix-1 的破坏性变更和 Fix-2 的架构变更也需补充处理。

---

## 架构合理性评估

### 架构专家分析

**优点：**

1. **TDD 方法论**：严格遵循"先写失败测试→再改代码→测试通过"流程，值得肯定
2. **修复顺序合理**：`Fix-4 → Fix-3 → Fix-1 → Fix-2` 的依赖链正确：Fix-1 与 Fix-4 同文件（`web_main_window.py`），Fix-2 与 Fix-1 同文件（`app.js`）
3. **Fix-3 模块边界清晰**：只改 `evidence.js`，不影响其他模块
4. **Agent 调度表完整**：11 步骤、依赖关系、Prompt 摘要清晰

**问题：**

1. **Python→JS 字段命名约定不统一**：state dict 中 `timeLeft`（camelCase）与 `current_suspect_index`（snake_case）并存。缺少统一的 key 转换策略，长期维护会产生混乱。

2. **Fix-2 完整重写 ChatManager 的方式过于激进**：当前 `chat.js` 为 128 行，方案重写后约 160 行。重写意味着所有现有功能都需要重新验证，增加了回归风险。

3. **信号发射顺序未作为关键约束标注**：`_on_save_selected()` 中 `clear_chat` → `init_game_state` → `add_message` 的顺序对 Fix-2 正确运作至关重要，但方案未标注此为约束。

4. **缺少对 `web_bridge.py` 信号的同步清理**：`show_loading`、`hide_loading`、`update_loading_progress` 三个信号定义在 Fix-4 后成为死代码。

5. **缺少对 `loading.js`、`bridge.js`、`app.js`、`index.html` 的同步清理**：详见风险评估中的遗漏清理清单。

### 架构师A意见

- Fix-4 符合单一职责原则，接口不变
- Fix-2 `switchSuspect()` 与现有 `clear()` 有重叠逻辑，需确认不会冲突
- Fix-1 的 state dict 变更是破坏性的
- Fix-3 符合数据一致性原则

### 架构师B意见

- 方案对 `chat.js` 完整重写风险偏高，建议增量修改
- Python 与 JS 端字段命名约定不统一，应统一为 camelCase 或在 bridge 层做转换
- `sendMessage()` 中 `addMessage('player', text, '审讯员')` 的 `suspectName` 参数在 Fix-2 后被忽略（owner 取 `_currentSuspect`），参数传递不清晰
- `update_ui_from_engine()` 中 `role='player'` 的消息 emit 会导致与 JS 端 `sendMessage()` 的重复消息

### 共识点

1. Fix-2 的 ChatManager 重写方式风险偏高，应考虑增量修改
2. Python→JS 字段命名约定不统一，缺少转换策略
3. Fix-4 后遗留大量死代码需清理

### 分歧点

| 问题 | 架构专家 | 架构师A | 架构师B | 采纳结论 | 理由 |
|------|---------|---------|---------|----------|------|
| Fix-2 应完全重写还是增量修改 | 倾向增量 | 提及风险 | 强烈建议增量 | **增量修改** | 增量修改风险更低，每步可独立验证，且不会改变 ChatManager 的公共接口 |
| 命名约定应在何时统一 | 本轮 | 未明确 | 本轮 | **本轮** | 既然已经在修改 state dict，不如一并统一，避免后续再改 |

### 综合结论

架构合理性**需修改**。主要问题：Fix-2 的完全重写方式风险偏高、字段命名约定不统一、缺少对死代码的清理计划。建议：Fix-2 改为增量修改；本轮统一 state dict 的 camelCase 命名；补充 loading 相关代码的清理步骤。

---

## 实现难度评估

### 工作量分析

| 阶段 | 方案估算 | 架构专家 | 架构师A | 架构师B | 综合评估 |
|------|---------|---------|---------|---------|----------|
| Fix-4（测试+修复+更新） | ~1天 | ~1.5天 | 0.5天 | ~1.5天 | ~1.5天 |
| Fix-3（测试+修复） | ~0.5天 | ~0.5天 | 0.25天 | ~0.5天 | ~0.5天 |
| Fix-1（测试+修复+更新） | ~1.5天 | ~2天 | 1.5天 | ~2天 | ~2天 |
| Fix-2（测试+修复） | ~1.5天 | ~2天 | 2天 | ~2天 | ~2天 |
| Loading 相关清理 | 未估算 | ~0.5天 | 未估算 | ~0.5天 | ~0.5天 |
| **总计** | ~4.5天 | ~6.5天 | ~3.75天 | ~6.5天 | **~6天** |

> 方案估算偏乐观。Fix-4 需额外设计超时保留和取消入口方案；Fix-1 需处理与 Fix-2 的时序配合及命名统一；Fix-2 改为增量修改后复杂度可略降，但仍需充分测试。

### 技术难点

1. **Fix-4 超时机制替代方案设计**：需要在不使用 loading overlay 的前提下提供 LLM 超时保护——保留 `_timeout_timer`，将超时后的 UI 反馈从 `hide_loading` 改为 `show_typing_indicator(False)` + 系统消息
2. **Fix-4 取消操作替代入口设计**：需在聊天区域或导航栏添加取消按钮——推荐在 typing indicator 旁添加取消按钮
3. **Fix-2 的 ChatManager 增量修改与 app.js 的集成**：需确保 Python 回调的 `add_message` 与 JS 端 `sendMessage` 的 `addMessage` 不产生重复
4. **Fix-1 与 Fix-2 的时序配合**：`_on_save_selected()` 中的信号发射顺序必须严格

### 综合结论

实现难度**中等偏高**，主要因为 Fix-4 的超时机制和取消入口需要重新设计，Fix-2 的 ChatManager 重写（改为增量修改后略降）与 app.js 集成需仔细测试。建议总工期从 ~4.5 天调整为 ~6 天。

---

## 风险评估

### 风险清单

| 风险 | 来源 | 可能性 | 影响 | 等级 | 应对策略 |
|------|------|--------|------|------|----------|
| Fix-4 删除超时定时器后 Worker 永久挂起 | 专家/B | 高 | 高 | **P0** | 保留 `_timeout_timer`，仅移除 UI overlay 层的 `show_loading`/`hide_loading` emit；超时后改 emit `show_typing_indicator(False)` + 系统消息 |
| Fix-4 删除 loading overlay 后用户无法取消操作 | 专家/B | 高 | 中 | **P0** | 在 typing indicator 旁或聊天输入区添加"取消"按钮 |
| Fix-2 ChatManager 重写引入回归 Bug | 专家/A/B | 中 | 中 | **P1** | 改为增量修改，每步独立测试；增加 JS 单元测试 |
| Fix-1 与 Fix-2 信号时序错误导致消息丢失 | 专家/B | 中 | 中 | **P1** | 严格定义信号发射顺序（`clear_chat` → `init_game_state` → `add_message`），添加集成测试验证 |
| Python 回调导致重复 player 消息 | 专家/B | 中 | 低 | **P1** | 在 Python 端 `update_ui_from_engine()` 中，`role='player'` 的消息不再 emit `add_message`，或在 JS 端添加去重逻辑 |
| Fix-1 `time_left`→`timeLeft` 破坏性变更影响已有测试 | 专家/A | 高 | 中 | **P1** | 全面更新 `test_web_integration.py` 中所有 `time_left` 断言 |
| Loading 相关死代码未清理 | 专家/A/B | 高 | 低 | **P1** | 本轮同步清理：`web_bridge.py` 3 个信号、`app.js` 3 个事件处理、`bridge.js` 3 个监听器、`loading.js` 整个文件、`index.html` DOM 元素 |
| Fix-2 addMessage 中 suspectName 为空时消息归属错误 | B | 中 | 低 | **P2** | 当 `role='suspect'` 且 `suspectName` 为空时，fallback 到 `this._currentSuspect` |
| state dict 命名约定不统一 | 专家/B | 低 | 中 | **P2** | 本轮统一为 camelCase 或在 bridge 层做转换 |
| 旧存档中 `time_left`（snake_case）不兼容 | B | 低 | 中 | **P2** | 在 `app.js` 的 `initGameState` 中保留 `time_left` fallback（方案已做） |

### 综合结论

存在 **2 个 P0 级风险**，必须在实施前修复。Fix-4 的超时保护丢失和取消入口丢失是不可妥协的功能需求——删除它们会导致系统在 LLM 无响应时完全卡死，用户无法恢复。另有 **5 个 P1 级风险**需要重点关注。

---

## 改进建议

### 必须修改（P0）

1. **保留超时定时器，仅移除 UI 层的 loading overlay**
   - 问题：删除 `_timeout_timer` 后 Worker 可能永久挂起，系统卡死
   - 提出者：架构专家 / 架构师B
   - 解决方案：
     - **保留** `_timeout_timer` 和 `_on_worker_timeout()` 方法
     - `_timeout_timer` 超时后，不再 emit `hide_loading`，改为 emit `show_typing_indicator(False)` + `add_message("system", "响应超时，请重试", "")` + `set_input_enabled(True)`
     - **删除** `_progress_timer` 和 `_update_loading_progress()`（纯 loading overlay 的进度显示，可安全删除）
   - 影响范围：`web_main_window.py` 的 `_start_worker()`、`_on_worker_timeout()`、`_cleanup_after_worker()`
   - 需同步修改：测试代码中关于 `_timeout_timer` 的断言应保留

2. **提供替代的取消操作入口**
   - 问题：删除 loading overlay 后，用户无法在 LLM 响应期间取消操作
   - 提出者：架构专家 / 架构师B
   - 解决方案（推荐方案A）：
     - **方案A**：在聊天输入区域，当 `show_typing_indicator(True)` 触发时，将发送按钮文本/图标替换为"取消"，点击后调用 `bridge.cancelOperation()`
     - **方案B**：在 typing indicator 旁添加一个小的 ✕ 图标
     - **方案C**：在导航栏添加"取消"按钮
   - 影响范围：`chat.js`（添加取消按钮逻辑）、`app.js`（绑定取消事件）、`web_main_window.py`（`_on_cancel_operation()` 不再 emit `hide_loading`）

### 强烈建议（P1）

3. **Fix-2 改为增量修改 ChatManager**
   - 问题：完全重写 ChatManager 风险高，回归测试工作量大
   - 提出者：架构专家 / 架构师B
   - 解决方案：分步增量修改：
     - Step 1: 添加 `_messagesBySuspect` 和 `_currentSuspect` 属性
     - Step 2: 修改 `addMessage` 增加存储逻辑（owner 判断）
     - Step 3: 添加 `switchSuspect()` 方法
     - Step 4: 提取 `_renderMessage()` 方法（从 `addMessage` 中抽取渲染逻辑）
     - 每步独立测试

4. **统一 Python→JS 的 state dict 命名约定**
   - 问题：`timeLeft`（camelCase）与 `current_suspect_index`（snake_case）并存
   - 提出者：架构专家 / 架构师B
   - 解决方案：在 `web_main_window.py` 的 `_on_save_selected()` 和 `load_case()` 中，state dict 的 key 统一为 camelCase：
     ```python
     state = {
         "suspects": [...],
         "evidences": [...],
         "timeLeft": self.engine.time_left,
         "currentSuspectIndex": self.engine.current_suspect_index,
         "state": self.engine.state,
         "caseId": case_id,
         "caseTitle": case_data.get("title", ""),
     }
     ```
   - 影响范围：`web_main_window.py`、`app.js`（读取 `state.currentSuspectIndex` 而非 `state.current_suspect_index`）

5. **处理 Python 回调导致的重复 player 消息**
   - 问题：JS `sendMessage()` 先 `addMessage('player')`，Python Worker 完成后又 emit `add_message(role='player')`，消息重复
   - 提出者：架构专家 / 架构师B
   - 解决方案：在 Python 端 `update_ui_from_engine()` 中，`role='player'` 的消息**不再 emit** `add_message`（因为 JS 端已经自行渲染了），只 emit `role='suspect'` 和 `role='system'` 的消息
   - 影响范围：`web_main_window.py:366-372`

6. **同步清理 Loading 相关代码**
   - 问题：Fix-4 后遗留大量死代码
   - 提出者：架构专家 / 架构师A / 架构师B
   - 清理清单：
     | 文件 | 清理内容 |
     |------|---------|
     | `web_bridge.py` | 删除 `show_loading`、`hide_loading`、`update_loading_progress` 三个信号定义（第45-47行） |
     | `app.js` | 删除 `showLoading`、`hideLoading`、`loadingProgress` 事件处理（第126-138行）；删除 `loadingManager` 变量（第12、31行） |
     | `bridge.js` | 删除 `show_loading`、`hide_loading`、`update_loading_progress` 的信号监听器 |
     | `loading.js` | 删除整个文件（150行）或标记为废弃 |
     | `index.html` | 删除 `#loading-overlay` DOM 元素；删除 `<script src="js/loading.js">` 引用 |
   - 影响范围：5 个文件，建议作为 Fix-4 的补充步骤

7. **Fix-1 破坏性变更需完整测试覆盖**
   - 问题：`time_left` → `timeLeft` 会破坏现有测试
   - 提出者：架构专家 / 架构师A
   - 解决方案：全面搜索并更新 `test_web_integration.py` 中所有 `time_left` 断言

### 可选优化（P2）

8. **Fix-2 的 `addMessage` 中 `role='suspect'` 且 `suspectName` 为空时 fallback 到 `_currentSuspect`**
   - 提出者：架构师B
   - 解决方案：
     ```javascript
     const owner = role === 'player'
         ? (this._currentSuspect || '_default')
         : (suspectName || this._currentSuspect || '_default');
     ```

9. **Fix-3 同步更新 `evidence.js` 的 JSDoc 注释**
   - 提出者：架构师A
   - 问题：第 30-31 行 JSDoc 仍声明 `title` 和 `tag` 字段
   - 解决方案：更新为 `{id: string, name: string, description: string, related_suspect?: string}`

10. **在方案中显式标注 `_on_save_selected()` 的信号发射顺序为关键约束**
    - 提出者：架构专家
    - 顺序：`clear_chat` → `init_game_state`（含 `switchSuspect`）→ `add_message` 序列

---

## 附录

### 评审依据

- **方案文档**：`docs/fix-bug-fix-plan.md`（1489行）
- **源代码分析**：
  - `ui/web_main_window.py`（628行）- 完整阅读
  - `ui/web/js/evidence.js`（173行）- 完整阅读
  - `ui/web/js/chat.js`（128行）- 完整阅读
  - `ui/web/js/app.js`（288行）- 完整阅读
  - `ui/web_bridge.py`（156行）- 完整阅读
  - `ui/web/js/loading.js`（150行）- 完整阅读
  - `core/interrogation.py`（206行）- 完整阅读
  - `core/db.py`（186行）- 关键函数验证
  - `schemas/interface_definitions.py`（53行）- 完整阅读
  - `tests/test_web_integration.py`（1074行）- 关键测试类验证
  - `tests/fixtures/conftest.py`（51行）- 完整阅读
  - `tests/fixtures/mock_cases/simple.json`（29行）- 完整阅读

### 意见来源说明
- 标记「专家」：架构专家独立评审结论
- 标记「A」：架构师A评审意见
- 标记「B」：架构师B评审意见
- 标记「共识」：三方一致认同
- 标记「综合」：经分析后形成的最终结论

### 修改后的 Fix-4 建议方案

```python
def _start_worker(self, action, content, evidence_id=None):
    """启动后台 Worker。"""
    if self._current_worker and self._current_worker.isRunning():
        logger.warning("上一个操作仍在进行中")
        return
    if self.engine is None:
        return

    # ✅ 保留：显示 typing indicator
    self.bridge.show_typing_indicator.emit(True)
    self.bridge.set_input_enabled.emit(False)

    # ✅ 保留：超时保护（仅移除 show_loading，不删除定时器）
    self._timeout_timer = QTimer(self)
    self._timeout_timer.setSingleShot(True)
    self._timeout_timer.timeout.connect(self._on_worker_timeout)
    self._timeout_timer.start(LLM_TIMEOUT_SECONDS * 1000)

    # ❌ 删除：_progress_timer（纯 loading overlay 进度，不再需要）
    # ❌ 删除：show_loading emit

    self._current_worker = WebWorker(self.engine, action, content, evidence_id)
    self._current_worker.finished.connect(self._on_worker_finished)
    self._current_worker.error.connect(self._on_worker_error)
    self._current_worker.start()

def _on_worker_timeout(self):
    """Worker 超时。"""
    if self._current_worker and self._current_worker.isRunning():
        self._current_worker.interrupt()
        self._current_worker.wait(2000)
        self._cleanup_after_worker()
        # ✅ 改为：不 emit hide_loading，改 emit typing indicator
        self.bridge.show_typing_indicator.emit(False)
        self.bridge.add_message.emit("system", "响应超时，请重试", "")
        self.bridge.set_input_enabled.emit(True)
        self._current_worker = None
```

### 备注

- 本次评审覆盖了方案的全部内容，包括 4 个 Fix 项、测试代码、修复代码和 Agent 调度总表
- 评审过程中验证了方案中所有对源代码的引用，确认根因分析准确
- 风险评估重点关注的 Fix-4 超时问题，是本次评审发现的最严重问题，建议在实施前必须解决
- 工作量估算基于对代码复杂度的分析和各方评审意见的综合，建议预留 1-2 天缓冲
