# 架构评审报告

## 基本信息
- **方案名称**：The Box 优化方案（6个BUG修复 + 1个新功能）
- **评审日期**：2026-05-03
- **方案文档**：`docs/optimization-plan/00-master-index.md` ~ `06-suspect-selector-default.md`
- **参与评审**：架构专家、架构师A、架构师B

---

## 评审结论

| 维度 | 架构专家 | 架构师A | 架构师B | 综合结论 |
|------|---------|---------|---------|----------|
| 技术可行性 | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 架构合理性 | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| 实现难度 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| 风险评估 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |

**总体结论**：**需修改后通过**

方案整体方向正确，根因分析准确度高（特别是 BUG-4 和 BUG-5），但存在若干 P0/P1 级别问题需要在实施前修正。

---

## 技术可行性评估

### 架构专家分析

**已验证的根因分析**（通过代码确认）：

| BUG | 根因描述 | 代码位置 | 验证结果 |
|-----|---------|---------|---------|
| BUG-1 | `switchSuspect()` 使用 `innerHTML=''` 销毁DOM | `chat.js:74` | ✅ 确认 |
| BUG-1 | 存档加载时双重清空（`clear_chat` + `initGameState`） | `web_main_window.py:572,587` | ✅ 确认 |
| BUG-1 | Modal `transition: all 0.3s ease` 过度动画 | `components.css:588` | ✅ 确认 |
| BUG-2 | Console handler 缺少时间戳 | `logger.py:26` 格式为 `"%(levelname)s: %(message)s"` | ✅ 确认 |
| BUG-4 | `load_case()` 从未调用 `db.save_case()` | `web_main_window.py:185-206` | ✅ 确认 |
| BUG-4 | `to_dict()` 不包含 `case_id`/`case_title` | `interrogation.py:151-168` | ✅ 确认 |
| BUG-5 | `_on_worker_finished()` 无条件启用输入 | `web_main_window.py:274` | ✅ 确认 |
| BUG-5 | `_handle_ending()` 只禁用输入框 | `web_main_window.py:346-359` | ✅ 确认 |
| BUG-6 | `loadSuspects()` 重置 `currentIndex=-1` | `suspect.js:29` | ✅ 确认 |

**发现的问题**：

1. **BUG-1 Step 1 的 DOM 缓存机制过于复杂**（P1）
   - 方案在消息对象上挂载 `_domElement` 引用，但 `_renderMessage()` 中"缓存到最后一条消息"的逻辑与切换时需要显示所有消息的需求不匹配
   - `_showOrRenderMessage()` 和 `_renderMessage()` 职责重叠

2. **BUG-5 Step 8 的 `enable_all_actions` 遗漏**（P0）
   - 方案说"load_case() 中应增加 enable_all_actions.emit()"，但 Step 1-7 的代码中均未体现
   - 崩溃后点击"重新开始"→`_restart()`→`load_case()` 不会重新启用操作

### 架构师A意见

- BUG-2 根因分析需要核实（A 认为 console handler 可能已有时间戳）—— **经核实，A 的判断有误**，`logger.py:26` 确实是 `"%(levelname)s: %(message)s"`
- BUG-1 的 DOM 缓存逻辑建议简化，用 `visibility: hidden` 替代 `display: none`
- BUG-5 的信号/Slot 定义位置不够清晰

### 架构师B意见

- BUG-1 的 `_domElement` 引用存在内存泄漏风险，建议用 `WeakMap`
- BUG-3 的 `WebBridgeLogHandler` 存在线程安全问题
- BUG-5 的 `enableAllActions` 与 `disableAllActions` 不对称
- BUG-4 的降级处理加剧了 N+1 查询问题

### 共识点

1. **BUG-4 根因分析完全准确**：`load_case()` 未调用 `db.save_case()` 是核心问题
2. **BUG-5 根因分析完全准确**：`_on_worker_finished()` 无条件 `set_input_enabled(True)` 覆盖了结局禁用
3. **BUG-1 的 `innerHTML=''` 是闪动根因**：三方一致认同
4. **BUG-6 简单可行**：修改量小，风险低

### 分歧点

| 问题 | 架构专家 | 架构师A | 架构师B | 采纳结论 | 理由 |
|------|---------|---------|---------|----------|------|
| BUG-2 console handler 格式 | 方案正确，确实缺少时间戳 | 方案有误，已有时间戳 | 方案正确 | **方案正确** | 代码验证 `logger.py:26` 确为 `"%(levelname)s: %(message)s"` |
| BUG-1 DOM 缓存策略 | 用独立 Map 缓存 | 用 visibility:hidden 简化 | 用 WeakMap | **用 CSS class 控制** | 避免在消息对象上挂载 DOM 引用，用 data 属性 + CSS class |
| BUG-5 信号设计 | 统一为 `set_game_interactive(bool)` | 保持两个独立信号 | 统一为单一信号 | **统一为单一信号** | 与 `set_input_enabled(bool)` 模式一致，避免不对称 |

### 综合结论

技术可行性通过，但 BUG-1 的 DOM 缓存方案和 BUG-5 的信号设计需要简化。

---

## 架构合理性评估

### 架构专家分析

**优点**：
- 依赖关系图清晰，BUG-4/BUG-2/BUG-6 可并行
- 每个 BUG 的修改范围明确
- 验收测试策略完善

**问题**：

1. **`web_main_window.py` 正在成为"上帝类"**（P2）
   - 当前 603 行，BUG-3/BUG-5 将增加 100+ 行
   - Worker 类（WebWorker、CaseGenerateWorker、ReviewWorker）应抽离到独立模块

2. **信号机制不一致**（P1）
   - `set_input_enabled(bool)` — 细粒度布尔信号
   - `disable_all_actions()` / `enable_all_actions()` — 粗粒度无参信号
   - 应统一为 `set_game_interactive(bool)`

3. **并行 Agent 的文件冲突风险**（P1）
   - Agent-A 和 Agent-C 都需修改 `load_case()` 方法
   - Agent-C 的 Step 8 要在 `load_case()` 中增加 `enable_all_actions.emit()`
   - 需明确 `load_case()` 的修改由谁负责

### 架构师A意见

- BUG-5 的前端修改涉及多个文件（app.js, bridge.js, modal.js），耦合度偏高
- BUG-2 和 BUG-3 的 `logger.py` 修改需要合并处理

### 架构师B意见

- `enable_all_actions` 与 `disable_all_actions` 应合并为 `set_game_interactive(bool)`
- `web_main_window.py` 的膨胀问题需要长期关注
- BUG-3 的日志面板可能遮挡页面底部内容

### 共识点

1. 信号机制需要统一
2. `web_main_window.py` 需要长期重构
3. 并行 Agent 的文件冲突需要明确

### 综合结论

架构合理性通过，但信号机制需要统一设计。

---

## 实现难度评估

### 工作量分析

| BUG | 方案估算 | 架构专家 | 架构师A | 架构师B | 综合评估 |
|-----|---------|---------|---------|---------|----------|
| BUG-1 | 95min | 90min | 90min | 120min | **100min** |
| BUG-2 | 60min | 45min | 45min | 45min | **45min** |
| BUG-3 | 130min | 150min | 130min | 180min | **150min** |
| BUG-4 | 60min | 60min | 60min | 75min | **65min** |
| BUG-5 | 135min | 150min | 150min | 180min | **160min** |
| BUG-6 | 20min | 15min | 15min | 15min | **15min** |
| 回归测试 | 30min | 45min | 30min | 60min | **45min** |
| **总计** | **530min** | **555min** | **520min** | **675min** | **580min (~9.5h)** |

### 技术难点

1. **BUG-1**：DOM 缓存机制设计，需要平衡性能和代码复杂度
2. **BUG-3**：`WebBridgeLogHandler` 的线程安全，CSS 变量依赖确认
3. **BUG-5**：跨语言信号联动，复盘生成器的 prompt 设计，`ReviewWorker` 线程安全
4. **BUG-4**：降级处理的边界情况覆盖

### 综合结论

实现难度适中，BUG-3 和 BUG-5 是最复杂的部分。建议 BUG-3 降级为 P2，优先完成 P0 的 BUG-4 和 BUG-5。

---

## 风险评估

### 风险清单

| 风险 | 来源 | 可能性 | 影响 | 等级 | 应对策略 |
|------|------|--------|------|------|----------|
| BUG-5 `_restart()` 后操作无法恢复 | 专家/B | 高 | 高 | **P0** | `load_case()` 中必须 `enable_all_actions.emit()` |
| BUG-1 DOM 缓存导致消息丢失 | 专家/A/B | 中 | 高 | **P1** | 简化缓存策略，充分测试切换场景 |
| BUG-3 `WebBridgeLogHandler` 线程不安全 | B | 中 | 中 | **P1** | 给 `_throttle_count`/`_last_second` 加锁 |
| BUG-5 复盘生成超时阻塞 | A/B | 中 | 中 | **P1** | 使用 `show_loading` 替代 `show_dialog`，增加超时 |
| BUG-5 `enable/disable` 不对称导致状态混乱 | B | 中 | 中 | **P1** | 统一为 `set_game_interactive(bool)` |
| BUG-4 降级处理加剧 N+1 查询 | B | 中 | 低 | **P2** | 优化 `list_sessions()` 使用 JOIN |
| BUG-1 `animation: none` 内联样式不可恢复 | B | 低 | 低 | **P2** | 使用 CSS class 替代内联样式 |
| BUG-3 日志面板遮挡页面内容 | B | 中 | 低 | **P2** | 主内容区域预留底部 padding |

### 综合结论

风险可控，但 P0 问题（`_restart()` 后操作无法恢复）必须在实施前修正。

---

## 改进建议

### 必须修改（P0）

#### 1. BUG-5: `load_case()` 中必须增加 `enable_all_actions.emit()`

- **问题**：方案 Step 8 提到"load_case() 中应增加 enable_all_actions.emit()"，但 Step 1-7 的代码中均未体现。崩溃后点击"重新开始"→`_restart()`→`load_case()` 不会重新启用操作，用户将处于完全无法操作的状态。
- **提出者**：架构专家 + 架构师B
- **解决方案**：在 `load_case()` 的 `init_game_state.emit()` 之后，增加 `self.bridge.set_game_interactive.emit(True)`
- **影响范围**：`ui/web_main_window.py` 的 `load_case()` 方法

#### 2. BUG-5: 统一信号设计

- **问题**：`disable_all_actions()` / `enable_all_actions()` 是两个独立信号，与 `set_input_enabled(bool)` 模式不一致，容易出现"禁用后忘记启用"的情况。
- **提出者**：架构师B
- **解决方案**：合并为 `set_game_interactive(bool)` 单一信号，前端统一处理
- **影响范围**：`ui/web_bridge.py`、`ui/web/js/bridge.js`、`ui/web/js/app.js`、`ui/web_main_window.py`

#### 3. BUG-1: 简化 DOM 缓存机制

- **问题**：在消息对象上挂载 `_domElement` 引用会导致职责混乱、内存泄漏风险、`_showOrRenderMessage()` 与 `_renderMessage()` 职责重叠。
- **提出者**：架构专家 + 架构师A + 架构师B
- **解决方案**：
  - 不在消息对象上挂载 DOM 引用
  - 使用 `data-suspect` 和 `data-index` 属性标记消息 DOM 元素
  - `switchSuspect()` 时通过 CSS class 控制显示/隐藏：
    ```javascript
    switchSuspect(suspectName) {
        this._currentSuspect = suspectName;
        this._removeTypingIndicator();
        if (!this.container) return;

        // 隐藏所有消息
        this.container.querySelectorAll('.message').forEach(el => {
            el.classList.add('hidden');
        });

        // 显示当前嫌疑人的消息
        this.container.querySelectorAll(`.message[data-suspect="${suspectName}"], .message[data-suspect="_default"]`).forEach(el => {
            el.classList.remove('hidden');
            el.style.animation = 'none'; // 已有消息不播动画
        });

        // 如果没有消息，显示占位符
        const msgs = this._messagesBySuspect[suspectName] || [];
        if (msgs.length === 0) {
            this._showPlaceholder(suspectName);
        }
        this._scrollToBottom();
    }
    ```
  - `_renderMessage()` 中为每个消息 DOM 添加 `data-suspect` 属性
  - CSS 中增加 `.message.hidden { display: none; }`
- **影响范围**：`ui/web/js/chat.js`、`ui/web/css/components.css`

### 强烈建议（P1）

#### 4. BUG-3: `WebBridgeLogHandler` 线程安全

- **问题**：`_throttle_count` 和 `_last_second` 在多线程环境下不是线程安全的。
- **提出者**：架构师B
- **解决方案**：使用 `threading.Lock` 保护节流状态
- **影响范围**：`core/log_handler.py`

#### 5. BUG-5: 复盘生成使用 `show_loading` 替代 `show_dialog`

- **问题**：`show_dialog` 的默认按钮是"确定"，用户点击后 modal 关闭，但后台 ReviewWorker 仍在运行。
- **提出者**：架构师B
- **解决方案**：使用 `show_loading` 信号显示加载提示，复盘完成后再隐藏
- **影响范围**：`ui/web_main_window.py` 的 `_on_review_requested()`

#### 6. BUG-4: `from_dict()` 恢复 `case_id`/`case_title` 到 `engine.case`

- **问题**：`to_dict()` 增加了 `case_id`/`case_title`，但 `from_dict()` 未将其写入 `engine.case`，可能导致恢复后的引擎状态不完整。
- **提出者**：架构师B
- **解决方案**：在 `from_dict()` 中，如果 `case_data` 缺少 `case_id`，从 `state` 中补充
- **影响范围**：`core/interrogation.py` 的 `from_dict()` 方法

#### 7. BUG-2: 日志中避免敏感信息泄露

- **问题**：`logger.debug(f"用户发送消息: {text[:50]}")` 可能泄露用户输入内容。
- **提出者**：架构师A
- **解决方案**：定义常量 `MAX_LOG_TEXT_LENGTH = 100`，在日志规范中说明 DEBUG 日志仅在开发环境启用
- **影响范围**：`ui/web_main_window.py`、`core/suspect_agent.py`

#### 8. BUG-3: 日志面板遮挡页面内容

- **问题**：`position: fixed; bottom: 0` 的日志面板会遮挡页面底部内容。
- **提出者**：架构师B
- **解决方案**：主内容区域增加 `padding-bottom: 32px`，或在面板展开时动态调整
- **影响范围**：`ui/web/css/components.css` 或 `ui/web/index.html`

### 可选优化（P2）

#### 9. BUG-4: 优化 N+1 查询

- **问题**：`_on_load_game()` 对每个 session 都调用 `db.load_case()`，降级时还调用 `db.load_full_session()`。
- **提出者**：架构师B
- **解决方案**：修改 `list_sessions()` 使用 JOIN 一次性获取 case_title
- **影响范围**：`core/db.py`

#### 10. BUG-1: 使用 CSS class 替代内联 `animation: none`

- **问题**：`style.animation = 'none'` 是内联样式，优先级高于 CSS 类，不可恢复。
- **提出者**：架构师B
- **解决方案**：使用 `.no-animation { animation: none !important; }` CSS class
- **影响范围**：`ui/web/js/chat.js`、`ui/web/css/components.css`

#### 11. 长期: `web_main_window.py` 重构

- **问题**：当前 603 行，BUG-3/BUG-5 后将超过 700 行，成为"上帝类"。
- **提出者**：架构专家
- **解决方案**：将 Worker 类抽离到 `ui/workers.py`，将存档/读档逻辑抽离到 `ui/save_load_manager.py`
- **影响范围**：`ui/` 目录结构

---

## 附录

### 评审依据

- **参考文档**：`docs/optimization-plan/00-master-index.md` ~ `06-suspect-selector-default.md`
- **代码分析**：通过 `@explore` Agent 读取了全部 15 个相关源文件
- **关键验证**：
  - `logger.py:26` 确认为 `"%(levelname)s: %(message)s"`（方案正确）
  - `chat.js:74` 确认为 `this.container.innerHTML = ''`（方案正确）
  - `web_main_window.py:274` 确认为 `self.bridge.set_input_enabled.emit(True)`（方案正确）
  - `web_main_window.py:185-206` 确认 `load_case()` 未调用 `db.save_case()`（方案正确）

### 意见来源说明

- 标记「专家」：架构专家独立评审结论
- 标记「A」：架构师A评审意见
- 标记「B」：架构师B评审意见
- 标记「共识」：三方一致认同
- 标记「综合」：经分析后形成的最终结论

### 修正后的依赖关系图

```
Phase 1 (并行):
  Agent-A: BUG-4 + BUG-6  →  修改 db.py, interrogation.py, web_main_window.py(load_case/_on_save_*/_on_load_*), suspect.js
  Agent-B: BUG-2           →  修改 logger.py, llm_client.py, suspect_agent.py, interrogation.py, web_main_window.py(日志)
  Agent-C: BUG-5           →  修改 web_main_window.py(_on_worker_finished/_handle_ending/_restart), web_bridge.py, bridge.js, app.js, modal.js, 新增 review_generator.py

Phase 2 (串行，等 Phase 1 完成):
  Agent-A: BUG-1           →  修改 chat.js, components.css, web_main_window.py(_on_case_generated)
  Agent-B: BUG-3           →  修改 main.py, logger.py, web_bridge.py, web_main_window.py, 新增 log_handler.py, log-viewer.js, log-viewer.css

Phase 3: 全量回归测试
```

**注意**：`load_case()` 的修改由 Agent-A 负责（增加 `db.save_case()`），Agent-C 在 `_restart()` 中调用 `load_case()` 即可，无需直接修改 `load_case()`。

### 备注

1. 本评审基于 2026-05-03 的代码快照，如代码有变更需重新评审
2. BUG-3（日志查询页面）建议降级为 P2，不应阻塞 P0 BUG 的修复
3. 总预估工时从方案的 530min 调整为 580min（~9.5h），主要增加在 BUG-1 和 BUG-5
