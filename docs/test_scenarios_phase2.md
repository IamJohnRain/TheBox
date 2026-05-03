# 测试场景设计 - Phase 2: JavaScript 通信层与核心模块

> **项目**: The Box: Local Verdict  
> **阶段**: WebView UI 重构 - 阶段 2  
> **编写**: 测试 Agent  
> **日期**: 2026-05-03  
> **状态**: 待评审

---

## 一、测试概述

### 1.1 测试目标

验证阶段 2 交付物的功能正确性：
1. JS 模块文件结构正确（8 个独立模块文件已创建）
2. `bridge.js` 能通过 QWebChannel 与 Python `WebBridge` 双向通信
3. 各 UI 功能模块（聊天、嫌疑人、证据、倒计时、加载状态、模态框）独立工作正常
4. `app.js` 作为主入口能正确初始化和协调所有模块

### 1.2 测试策略

| 测试层级 | 方法 | 工具 |
|----------|------|------|
| **文件结构** | 静态检查 JS 文件存在性和内容 | pytest + pathlib |
| **Python 信号层** | 验证 WebBridge 信号发射与参数 | pytest-qt (qtbot) |
| **JS 模块内容** | 解析 JS 文件，验证函数/导出定义 | pytest + 正则/AST |
| **集成通信** | QWebEngineView 加载后执行 JS 回调验证 | pytest-qt + QWebEnginePage.runJavaScript |
| **端到端流程** | 模拟用户操作，验证 Python↔JS 全链路 | pytest-qt |

### 1.3 Mock 策略

- **LLM 调用**：全部 Mock（`unittest.mock` 替换 `LLMClient`）
- **QWebChannel 传输**：集成测试中使用真实的 `qt.webChannelTransport`
- **定时器**：使用 `qtbot.waitSignal` / `qtbot.waitUntil` 替代 `time.sleep`

---

## 二、功能模块测试场景

### 功能模块 1：文件结构与模块加载

#### 场景 1.1：JS 模块文件存在性
- **前置条件**：项目代码已更新到阶段 2
- **测试步骤**：
  1. 检查 `ui/web/js/bridge.js` 文件存在
  2. 检查 `ui/web/js/chat.js` 文件存在
  3. 检查 `ui/web/js/suspect.js` 文件存在
  4. 检查 `ui/web/js/evidence.js` 文件存在
  5. 检查 `ui/web/js/timer.js` 文件存在
  6. 检查 `ui/web/js/loading.js` 文件存在
  7. 检查 `ui/web/js/modal.js` 文件存在
  8. 检查 `ui/web/js/app.js` 文件存在
- **预期结果**：全部 8 个文件存在且非空（大于 0 字节）
- **优先级**：P0

#### 场景 1.2：index.html 引用 JS 模块
- **前置条件**：JS 模块文件已创建
- **测试步骤**：
  1. 读取 `index.html` 内容
  2. 检查是否包含 `<script src="js/bridge.js">` 引用
  3. 检查是否包含 `<script src="js/chat.js">` 引用
  4. 检查是否包含 `<script src="js/suspect.js">` 引用
  5. 检查是否包含 `<script src="js/evidence.js">` 引用
  6. 检查是否包含 `<script src="js/timer.js">` 引用
  7. 检查是否包含 `<script src="js/loading.js">` 引用
  8. 检查是否包含 `<script src="js/modal.js">` 引用
  9. 检查是否包含 `<script src="js/app.js">` 引用
- **预期结果**：`index.html` 中包含全部 8 个 JS 文件的引用，且 `bridge.js` 在 `app.js` 之前加载
- **优先级**：P0

#### 场景 1.3：JS 模块加载顺序
- **前置条件**：`index.html` 已引用 JS 模块
- **测试步骤**：
  1. 解析 `index.html` 中所有 `<script>` 标签的顺序
  2. 验证 `qwebchannel.js` 在 `bridge.js` 之前
  3. 验证 `bridge.js` 在其他业务模块之前
  4. 验证 `app.js` 在最后
- **预期结果**：加载顺序为 qwebchannel → bridge → chat/suspect/evidence/timer/loading/modal → app
- **优先级**：P1

#### 场景 1.4：JS 模块导出格式
- **前置条件**：JS 模块文件已创建
- **测试步骤**：
  1. 读取每个 JS 模块文件内容
  2. 检查 `bridge.js` 是否导出/暴露 `Bridge` 类或对象
  3. 检查 `chat.js` 是否导出/暴露聊天相关函数
  4. 检查 `suspect.js` 是否导出/暴露嫌疑人相关函数
  5. 检查 `evidence.js` 是否导出/暴露证据相关函数
  6. 检查 `timer.js` 是否导出/暴露倒计时相关函数
  7. 检查 `loading.js` 是否导出/暴露加载状态相关函数
  8. 检查 `modal.js` 是否导出/暴露模态框相关函数
- **预期结果**：每个模块都通过全局命名空间（如 `window.TheBox.Bridge`）或 ES module 暴露接口
- **优先级**：P1

---

### 功能模块 2：Bridge 通信层（bridge.js）

#### 场景 2.1：Bridge 初始化成功
- **前置条件**：`WebMainWindow` 已创建，QWebChannel 已注册
- **测试步骤**：
  1. 创建 `WebMainWindow` 实例
  2. 等待页面加载完成
  3. 通过 `runJavaScript` 执行 `typeof window.TheBox !== 'undefined'`
  4. 通过 `runJavaScript` 执行 `window.TheBox.bridge !== null`
  5. 通过 `runJavaScript` 执行 `window.TheBox.bridge.isConnected === true`
- **预期结果**：Bridge 对象存在且 `isConnected` 为 `true`
- **优先级**：P0

#### 场景 2.2：JS 调用 Python 槽方法 - sendMessage
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 在 Python 端监听 `bridge.message_sent` 信号
  2. 通过 `runJavaScript` 调用 `window.TheBox.bridge.sendChatMessage("hello")`
  3. 等待信号触发
- **预期结果**：`message_sent` 信号被触发，参数为 `"hello"`
- **优先级**：P0

#### 场景 2.3：JS 调用 Python 槽方法 - selectSuspect
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 监听 `bridge.suspect_selected` 信号
  2. 通过 JS 调用 `window.TheBox.bridge.selectSuspect(0)`
  3. 等待信号触发
- **预期结果**：`suspect_selected` 信号被触发，参数为 `0`
- **优先级**：P0

#### 场景 2.4：JS 调用 Python 槽方法 - presentEvidence
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 监听 `bridge.evidence_presented` 信号
  2. 通过 JS 调用 `window.TheBox.bridge.presentEvidence("e1")`
  3. 等待信号触发
- **预期结果**：`evidence_presented` 信号被触发，参数为 `"e1"`
- **优先级**：P0

#### 场景 2.5：JS 调用 Python 槽方法 - 全部槽方法覆盖
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 依次测试以下 JS → Python 调用：
     - `applyPressure()` → `pressure_applied`
     - `applyEmpathy()` → `empathy_applied`
     - `requestSave()` → `save_requested`
     - `requestLoad()` → `load_requested`
     - `requestSettings()` → `settings_requested`
     - `requestGenerateCase()` → `generate_case_requested`
     - `cancelOperation()` → `cancel_requested`
     - `selectSave("s1")` → `save_selected`
     - `requestRestart()` → `restart_requested`
     - `requestReturnToMenu()` → `return_to_menu_requested`
  2. 每次调用后验证对应信号被触发且参数正确
- **预期结果**：所有 JS→Python 槽方法调用均能正确触发对应信号
- **优先级**：P0

#### 场景 2.6：Python 信号触发 JS 回调 - addMessage
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 通过 `runJavaScript` 设置一个 JS 端回调计数器
  2. 在 Python 端发射 `bridge.add_message.emit("suspect", "我什么都没做", "张三")`
  3. 等待信号传递
  4. 通过 `runJavaScript` 检查 `#chat-container` 中是否新增了消息元素
  5. 检查消息内容是否包含"我什么都没做"
- **预期结果**：JS 端接收到信号并在 UI 上添加了新消息
- **优先级**：P0

#### 场景 2.7：Python 信号触发 JS 回调 - updateSuspect
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.update_suspect.emit("张三", 75)`
  2. 等待信号传递
  3. 通过 `runJavaScript` 检查嫌疑人名称和压力值是否更新
- **预期结果**：嫌疑人信息在 UI 上更新
- **优先级**：P0

#### 场景 2.8：Python 信号触发 JS 回调 - updateTimer
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.update_timer.emit(120)`
  2. 等待信号传递
  3. 通过 `runJavaScript` 检查 `#timer-display` 的文本内容
- **预期结果**：计时器显示 "02:00"
- **优先级**：P0

#### 场景 2.9：Python 信号触发 JS 回调 - updateEvidenceList
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.update_evidence_list.emit([{"id":"e1","title":"沾血的锄头","description":"锄头上有血迹"}])`
  2. 等待信号传递
  3. 通过 `runJavaScript` 检查 `#evidence-list` 中是否添加了证据卡片
- **预期结果**：证据列表中显示 1 张证据卡片
- **优先级**：P0

#### 场景 2.10：Python 信号触发 JS 回调 - 全部信号覆盖
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 依次测试以下 Python→JS 信号：
     - `init_game_state` → JS 初始化游戏状态
     - `set_input_enabled` → JS 启用/禁用输入框
     - `show_dialog` → JS 显示对话框
     - `clear_chat` → JS 清空聊天
     - `show_loading` → JS 显示加载
     - `hide_loading` → JS 隐藏加载
     - `update_loading_progress` → JS 更新加载进度
     - `show_save_list` → JS 显示存档列表
     - `show_ending_dialog` → JS 显示结局对话框
  2. 每次发射信号后验证 JS 端 UI 状态变化
- **预期结果**：所有 Python→JS 信号均能触发 UI 更新
- **优先级**：P1

#### 场景 2.11：Bridge 初始化重试机制
- **前置条件**：`bridge.js` 已实现重试逻辑
- **测试步骤**：
  1. 读取 `bridge.js` 文件内容
  2. 检查是否包含重试逻辑（如 `retry`、`reconnect`、`MAX_RETRIES`、`retryCount` 等关键字）
  3. 检查最大重试次数是否合理（≥ 3 次）
  4. 检查重试间隔是否设置（如 `setTimeout` 延迟）
  5. 检查重试失败后是否有错误处理或日志
- **预期结果**：
  - `bridge.js` 包含重试机制代码
  - 最大重试次数 ≥ 3
  - 有重试间隔（如 1s、2s 指数退避）
  - 重试全部失败后有 `console.error` 或回调通知
- **优先级**：P0

#### 场景 2.12：Bridge 重试次数验证
- **前置条件**：Bridge 重试机制已实现
- **测试步骤**：
  1. 通过 `runJavaScript` 模拟 `qt.webChannelTransport` 不可用（设为 `undefined`）
  2. 初始化 Bridge
  3. 通过 `runJavaScript` 检查 `window.TheBox.bridge.retryCount` 或日志
  4. 验证重试次数达到上限后不再尝试
- **预期结果**：重试次数达到 `MAX_RETRIES` 后停止，`isConnected` 保持 `false`
- **优先级**：P1

#### 场景 2.13：Bridge 连接超时处理
- **前置条件**：Bridge 重试机制已实现
- **测试步骤**：
  1. 模拟 QWebChannel 传输层延迟
  2. 验证在重试期间 `isConnected` 为 `false`
  3. 验证重试结束后状态正确
- **预期结果**：超时后 Bridge 状态为未连接，UI 仍可操作（降级模式）
- **优先级**：P2

#### 场景 2.14：Bridge 断线重连
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 验证 `bridge.js` 是否包含断线检测逻辑
  2. 验证是否在断线后尝试重新连接
- **预期结果**：`bridge.js` 包含断线检测和重连逻辑（如有设计）
- **优先级**：P2

---

### 功能模块 3：聊天模块（chat.js）

#### 场景 3.1：添加玩家消息
- **前置条件**：Bridge 已连接，聊天输入已启用
- **测试步骤**：
  1. 发射 `bridge.set_input_enabled.emit(True)` 启用输入
  2. 通过 `runJavaScript` 设置输入框值为 "你那天晚上在哪里？"
  3. 通过 `runJavaScript` 触发发送按钮点击
  4. 检查 `#chat-container` 中是否新增 `message-player` 类消息
  5. 检查消息内容是否为 "你那天晚上在哪里？"
- **预期结果**：聊天区域显示玩家消息，样式为 `message-player`
- **优先级**：P0

#### 场景 3.2：添加嫌疑人消息
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.add_message.emit("suspect", "我什么都没做", "张三")`
  2. 等待信号传递
  3. 检查 `#chat-container` 中是否新增 `message-suspect` 类消息
  4. 检查发送者名称显示为 "张三"
  5. 检查消息内容为 "我什么都没做"
- **预期结果**：聊天区域显示嫌疑人消息，包含发送者名称
- **优先级**：P0

#### 场景 3.3：添加系统消息
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.add_message.emit("system", "选择嫌疑人开始审讯", "")`
  2. 等待信号传递
  3. 检查 `#chat-container` 中是否新增 `message-system` 类消息
  4. 检查消息内容为 "选择嫌疑人开始审讯"
- **预期结果**：聊天区域显示居中的系统消息
- **优先级**：P0

#### 场景 3.4：清空聊天记录
- **前置条件**：聊天区域有多条消息
- **测试步骤**：
  1. 先添加若干条消息
  2. 发射 `bridge.clear_chat.emit()`
  3. 等待信号传递
  4. 检查 `#chat-container` 子元素数量
- **预期结果**：`#chat-container` 中无消息子元素
- **优先级**：P1

#### 场景 3.5：输入框禁用状态下无法发送
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.set_input_enabled.emit(False)` 禁用输入
  2. 等待信号传递
  3. 通过 `runJavaScript` 检查 `#chat-input` 的 `disabled` 属性
  4. 通过 `runJavaScript` 检查 `#btn-send` 的 `disabled` 属性
- **预期结果**：`#chat-input` 和 `#btn-send` 均为 `disabled`
- **优先级**：P0

#### 场景 3.6：输入框启用状态
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.set_input_enabled.emit(True)` 启用输入
  2. 等待信号传递
  3. 通过 `runJavaScript` 检查 `#chat-input` 的 `disabled` 属性为 `false`
  4. 检查 `#btn-send` 的 `disabled` 属性为 `false`
- **预期结果**：输入框和发送按钮可用
- **优先级**：P0

#### 场景 3.7：发送空消息被拦截
- **前置条件**：输入框已启用
- **测试步骤**：
  1. 通过 `runJavaScript` 设置输入框值为空字符串
  2. 触发发送
  3. 检查 `message_sent` 信号是否被触发
- **预期结果**：空消息不触发 `message_sent` 信号
- **优先级**：P1

#### 场景 3.8：发送纯空格消息被拦截
- **前置条件**：输入框已启用
- **测试步骤**：
  1. 设置输入框值为 "   "（纯空格）
  2. 触发发送
  3. 检查信号是否被触发
- **预期结果**：纯空格消息不触发信号（JS 端 trim 后为空）
- **优先级**：P1

#### 场景 3.9：Enter 键发送消息
- **前置条件**：输入框已启用
- **测试步骤**：
  1. 在输入框中输入文本
  2. 模拟按下 Enter 键
  3. 检查消息是否被发送
- **预期结果**：Enter 键触发发送，输入框被清空
- **优先级**：P1

#### 场景 3.10：XSS 防护 - HTML 注入
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.add_message.emit("suspect", "<script>alert('xss')</script>", "张三")`
  2. 检查消息内容是否被转义
  3. 验证没有实际执行 script 标签
- **预期结果**：HTML 标签被转义显示，不执行
- **优先级**：P1

#### 场景 3.11：消息自动滚动到底部
- **前置条件**：聊天区域有足够多消息产生滚动
- **测试步骤**：
  1. 连续添加多条消息（超过可视区域）
  2. 检查 `#chat-container` 的 `scrollTop` 是否等于 `scrollHeight - clientHeight`
- **预期结果**：聊天容器自动滚动到最新消息
- **优先级**：P2

---

### 功能模块 4：嫌疑人模块（suspect.js）

#### 场景 4.1：嫌疑人信息更新 - 名称和角色
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.init_game_state.emit({"suspects": [{"name": "张三", "role": "邻居"}]})` 或等效信号
  2. 通过 `runJavaScript` 检查 `#suspect-name` 的文本
  3. 通过 `runJavaScript` 检查 `#suspect-role` 的文本
- **预期结果**：嫌疑人姓名和角色正确显示
- **优先级**：P0

#### 场景 4.2：嫌疑人压力值更新
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.update_suspect.emit("张三", 75)`
  2. 检查 `#pressure-value` 的文本为 "75%"
  3. 检查 `#pressure-bar` 的宽度约为 75%
  4. 检查 `#pressure-bar` 的 CSS 类包含 `medium`（30-70 区间）
- **预期结果**：压力条和数值正确更新，颜色等级正确
- **优先级**：P0

#### 场景 4.3：压力等级 - 低压力
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.update_suspect.emit("张三", 20)`
  2. 检查 `#pressure-bar` 的 CSS 类包含 `low`
  3. 检查 `#pressure-value` 的 CSS 类包含 `low`
- **预期结果**：低压力样式（绿色）应用
- **优先级**：P1

#### 场景 4.4：压力等级 - 中等压力
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.update_suspect.emit("张三", 50)`
  2. 检查 `#pressure-bar` 的 CSS 类包含 `medium`
- **预期结果**：中等压力样式（黄色）应用
- **优先级**：P1

#### 场景 4.5：压力等级 - 高压力
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.update_suspect.emit("张三", 85)`
  2. 检查 `#pressure-bar` 的 CSS 类包含 `high`
- **预期结果**：高压力样式（红色 + 脉冲动画）应用
- **优先级**：P1

#### 场景 4.6：压力值边界 - 0%
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.update_suspect.emit("张三", 0)`
  2. 检查压力条宽度为 0%
  3. 检查值为 "0%"
- **预期结果**：压力条为空，值为 0%
- **优先级**：P1

#### 场景 4.7：压力值边界 - 100%
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.update_suspect.emit("张三", 100)`
  2. 检查压力条宽度为 100%
  3. 检查值为 "100%"
  4. 检查 CSS 类包含 `high`
- **预期结果**：压力条满，值为 100%，红色样式
- **优先级**：P1

#### 场景 4.8：压力值超界 - 大于 100
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.update_suspect.emit("张三", 150)`
  2. 检查压力条宽度不超过 100%
  3. 检查显示值被限制在 100%
- **预期结果**：压力值被 JS 端 clamp 到 100%
- **优先级**：P1

#### 场景 4.9：压力值超界 - 小于 0
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.update_suspect.emit("张三", -10)`
  2. 检查压力条宽度为 0%
  3. 检查显示值为 0%
- **预期结果**：压力值被 JS 端 clamp 到 0%
- **优先级**：P1

#### 场景 4.10：嫌疑人选择器切换
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 通过 `runJavaScript` 修改 `#suspect-selector` 的值为 `"suspect-1"`
  2. 触发 `change` 事件
  3. 监听 `bridge.suspect_selected` 信号
- **预期结果**：`suspect_selected` 信号被触发
- **优先级**：P0

#### 场景 4.11：嫌疑人头像占位符更新
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.update_suspect.emit("张三", 50)`
  2. 检查 `#suspect-avatar` 的文本内容为 "张"（取首字）
- **预期结果**：头像占位符显示名字首字
- **优先级**：P2

#### 场景 4.12：施压按钮点击
- **前置条件**：Bridge 已连接，按钮已启用
- **测试步骤**：
  1. 通过 `runJavaScript` 启用施压按钮
  2. 触发点击
  3. 监听 `bridge.pressure_applied` 信号
- **预期结果**：`pressure_applied` 信号被触发
- **优先级**：P0

#### 场景 4.13：共情按钮点击
- **前置条件**：Bridge 已连接，按钮已启用
- **测试步骤**：
  1. 通过 `runJavaScript` 启用共情按钮
  2. 触发点击
  3. 监听 `bridge.empathy_applied` 信号
- **预期结果**：`empathy_applied` 信号被触发
- **优先级**：P0

---

### 功能模块 5：证据模块（evidence.js）

#### 场景 5.1：证据列表加载
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.update_evidence_list.emit([{"id":"e1","title":"沾血的锄头","description":"锄头上有血迹"},{"id":"e2","title":"泥脚印","description":"从门口延伸到工具房"}])`
  2. 等待信号传递
  3. 通过 `runJavaScript` 检查 `#evidence-list` 中 `.evidence-card` 的数量
- **预期结果**：证据列表显示 2 张证据卡片
- **优先级**：P0

#### 场景 5.2：证据卡片内容正确
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射证据列表信号（含 1 条证据）
  2. 检查第一张卡片的标题为 "沾血的锄头"
  3. 检查描述文本为 "锄头上有血迹"
- **预期结果**：证据卡片标题和描述正确显示
- **优先级**：P0

#### 场景 5.3：证据卡片点击响应
- **前置条件**：证据列表已加载
- **测试步骤**：
  1. 加载证据列表
  2. 通过 `runJavaScript` 模拟点击第一张证据卡片
  3. 监听 `bridge.evidence_presented` 信号
- **预期结果**：`evidence_presented` 信号被触发，参数为 "e1"
- **优先级**：P0

#### 场景 5.4：空证据列表显示
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.update_evidence_list.emit([])`
  2. 检查 `#evidence-list` 中是否显示空状态文本（如"暂无证据"）
- **预期结果**：显示空证据提示
- **优先级**：P1

#### 场景 5.5：证据列表替换更新
- **前置条件**：已有证据列表
- **测试步骤**：
  1. 先加载 2 条证据
  2. 再发射新的 3 条证据列表
  3. 检查证据卡片数量为 3（而非 5）
- **预期结果**：证据列表是替换而非追加
- **优先级**：P1

#### 场景 5.6：新证据标记
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射含 `isNew: true` 标记的证据
  2. 检查对应卡片是否包含 `new` CSS 类
- **预期结果**：新证据卡片有 NEW 标记
- **优先级**：P2

#### 场景 5.7：证据标签显示
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射含 `tag` 字段的证据
  2. 检查卡片中是否显示 `.evidence-tag` 元素
- **预期结果**：证据标签正确显示
- **优先级**：P2

#### 场景 5.8：大量证据渲染性能
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射包含 20 条证据的列表
  2. 检查渲染时间是否在 1 秒内
- **预期结果**：20 条证据在 1 秒内渲染完成
- **优先级**：P2

---

### 功能模块 6：倒计时模块（timer.js）

#### 场景 6.1：倒计时显示 - 正常时间
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.update_timer.emit(600)` (10 分钟)
  2. 检查 `#timer-display` 的文本为 "10:00"
- **预期结果**：计时器显示 "10:00"
- **优先级**：P0

#### 场景 6.2：倒计时显示 - 分钟和秒
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.update_timer.emit(125)` (2 分 5 秒)
  2. 检查 `#timer-display` 的文本为 "02:05"
- **预期结果**：计时器显示 "02:05"（含前导零）
- **优先级**：P0

#### 场景 6.3：倒计时显示 - 警告状态（≤ 60 秒）
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.update_timer.emit(45)`
  2. 检查 `#timer-display` 的 CSS 类包含 `warning`
- **预期结果**：计时器变为警告样式（黄色）
- **优先级**：P0

#### 场景 6.4：倒计时显示 - 危险状态（≤ 30 秒）
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.update_timer.emit(15)`
  2. 检查 `#timer-display` 的 CSS 类包含 `danger`
- **预期结果**：计时器变为危险样式（红色 + 闪烁）
- **优先级**：P0

#### 场景 6.5：倒计时 - 时间归零
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.update_timer.emit(0)`
  2. 检查 `#timer-display` 的文本为 "00:00"
  3. 检查 CSS 类包含 `danger`
- **预期结果**：计时器显示 00:00 并进入危险状态
- **优先级**：P1

#### 场景 6.6：倒计时 - 未初始化状态
- **前置条件**：页面刚加载，未收到任何 timer 信号
- **测试步骤**：
  1. 检查 `#timer-display` 的初始文本
- **预期结果**：计时器显示 "--" 或占位符
- **优先级**：P1

#### 场景 6.7：倒计时 - 无效值处理（null）
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 通过 `runJavaScript` 调用计时器更新函数，传入 `null`
  2. 检查计时器显示 "--"
- **预期结果**：无效值时显示占位符，不崩溃
- **优先级**：P1

#### 场景 6.8：倒计时 - 负数处理
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 通过 `runJavaScript` 调用计时器更新函数，传入负数
  2. 检查 JS 不崩溃
- **预期结果**：负数被处理为 0 或显示 "00:00"，不崩溃
- **优先级**：P2

#### 场景 6.9：倒计时连续更新
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 连续发射 `update_timer` 信号：600 → 599 → 598
  2. 每次检查显示值是否正确更新
- **预期结果**：每次更新后显示正确的时间
- **优先级**：P1

#### 场景 6.10：倒计时状态切换
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `update_timer(120)` → 检查无 warning/danger 类
  2. 发射 `update_timer(45)` → 检查有 warning 类
  3. 发射 `update_timer(10)` → 检查有 danger 类
  4. 发射 `update_timer(120)` → 检查 warning/danger 类被移除
- **预期结果**：CSS 类随时间变化正确切换
- **优先级**：P1

---

### 功能模块 7：加载状态模块（loading.js）

#### 场景 7.1：显示加载状态
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.show_loading.emit("正在生成案件...", True)`
  2. 检查 `#loading-overlay` 是否有 `active` 类
  3. 检查 `#loading-text` 的文本为 "正在生成案件..."
- **预期结果**：加载遮罩可见，文本正确
- **优先级**：P0

#### 场景 7.2：隐藏加载状态
- **前置条件**：加载状态已显示
- **测试步骤**：
  1. 先显示加载
  2. 发射 `bridge.hide_loading.emit()`
  3. 检查 `#loading-overlay` 没有 `active` 类
- **预期结果**：加载遮罩不可见
- **优先级**：P0

#### 场景 7.3：加载进度更新
- **前置条件**：加载状态已显示
- **测试步骤**：
  1. 显示加载
  2. 发射 `bridge.update_loading_progress.emit(30)`
  3. 检查 `#loading-status` 文本包含 "30"
- **预期结果**：加载状态显示已等待时间
- **优先级**：P1

#### 场景 7.4：加载中取消按钮 - 可取消
- **前置条件**：加载状态已显示，cancellable 为 True
- **测试步骤**：
  1. 发射 `bridge.show_loading.emit("处理中", True)`
  2. 检查 `#loading-cancel` 按钮可见
  3. 通过 `runJavaScript` 点击取消按钮
  4. 监听 `bridge.cancel_requested` 信号
  5. 检查加载状态被隐藏
- **预期结果**：取消按钮点击后触发 `cancel_requested` 信号，加载隐藏
- **优先级**：P0

#### 场景 7.5：加载中取消按钮 - 不可取消
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.show_loading.emit("处理中", False)`
  2. 检查 `#loading-cancel` 按钮是否隐藏或禁用
- **预期结果**：不可取消时取消按钮不可见/不可点击
- **优先级**：P1

#### 场景 7.6：加载状态 - 默认文本
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.show_loading.emit("", True)` 或不传文本
  2. 检查 `#loading-text` 显示默认文本（如 "正在处理..."）
- **预期结果**：无文本时使用默认值
- **优先级**：P2

#### 场景 7.7：加载状态 - 重复显示不冲突
- **前置条件**：加载状态已显示
- **测试步骤**：
  1. 先显示加载 "第一次"
  2. 再显示加载 "第二次"
  3. 检查 `#loading-text` 为 "第二次"
- **预期结果**：后一次显示覆盖前一次
- **优先级**：P2

---

### 功能模块 8：模态框模块（modal.js）

#### 场景 8.1：显示对话框
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.show_dialog.emit("提示", "案件已保存")`
  2. 检查 `#modal` 是否有 `active` 类
  3. 检查 `#modal-title` 的文本为 "提示"
  4. 检查 `#modal-body` 包含 "案件已保存"
- **预期结果**：模态框可见，标题和内容正确
- **优先级**：P0

#### 场景 8.2：关闭模态框 - 点击关闭按钮
- **前置条件**：模态框已显示
- **测试步骤**：
  1. 显示模态框
  2. 通过 `runJavaScript` 点击 `#modal-close`
  3. 检查 `#modal` 没有 `active` 类
- **预期结果**：模态框关闭
- **优先级**：P1

#### 场景 8.3：关闭模态框 - 点击遮罩层
- **前置条件**：模态框已显示
- **测试步骤**：
  1. 显示模态框
  2. 通过 `runJavaScript` 点击 `#modal-backdrop`
  3. 检查模态框关闭
- **预期结果**：点击遮罩层关闭模态框
- **优先级**：P1

#### 场景 8.4：关闭模态框 - Escape 键
- **前置条件**：模态框已显示
- **测试步骤**：
  1. 显示模态框
  2. 模拟按下 Escape 键
  3. 检查模态框关闭
- **预期结果**：Escape 键关闭模态框
- **优先级**：P1

#### 场景 8.5：显示结局对话框
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.show_ending_dialog.emit("审讯结果", "你成功找到了真相")`
  2. 检查模态框显示
  3. 检查是否包含"重新开始"和"返回主菜单"按钮
- **预期结果**：结局对话框显示，包含操作按钮
- **优先级**：P1

#### 场景 8.6：结局对话框 - 重新开始
- **前置条件**：结局对话框已显示
- **测试步骤**：
  1. 显示结局对话框
  2. 点击"重新开始"按钮
  3. 监听 `bridge.restart_requested` 信号
- **预期结果**：`restart_requested` 信号被触发
- **优先级**：P1

#### 场景 8.7：结局对话框 - 返回主菜单
- **前置条件**：结局对话框已显示
- **测试步骤**：
  1. 显示结局对话框
  2. 点击"返回主菜单"按钮
  3. 监听 `bridge.return_to_menu_requested` 信号
- **预期结果**：`return_to_menu_requested` 信号被触发
- **优先级**：P1

#### 场景 8.8：存档列表对话框
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 发射 `bridge.show_save_list.emit([{"id":"s1","name":"存档1"},{"id":"s2","name":"存档2"}])`
  2. 检查模态框显示
  3. 检查是否包含存档列表
- **预期结果**：存档列表正确显示
- **优先级**：P1

---

### 功能模块 9：主应用入口（app.js）

#### 场景 9.1：App 初始化 - DOM 事件处理器注册
- **前置条件**：页面已加载
- **测试步骤**：
  1. 通过 `runJavaScript` 检查各按钮的事件监听器是否已注册
  2. 检查 `#btn-generate` 是否有点击监听
  3. 检查 `#btn-save` 是否有点击监听
  4. 检查 `#btn-load` 是否有点击监听
  5. 检查 `#btn-settings` 是否有点击监听
- **预期结果**：所有导航按钮已注册事件监听器
- **优先级**：P0

#### 场景 9.2：App 初始化 - Bridge 信号处理器注册
- **前置条件**：页面已加载，Bridge 已连接
- **测试步骤**：
  1. 通过 `runJavaScript` 检查 Bridge 信号的连接数
  2. 验证 `add_message` 信号已连接
  3. 验证 `update_suspect` 信号已连接
  4. 验证 `update_timer` 信号已连接
  5. 验证 `update_evidence_list` 信号已连接
- **预期结果**：所有 Bridge 信号已连接到对应的 JS 处理函数
- **优先级**：P0

#### 场景 9.3：导航按钮 - 生成案件
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 通过 `runJavaScript` 点击 `#btn-generate`
  2. 监听 `bridge.generate_case_requested` 信号
- **预期结果**：`generate_case_requested` 信号被触发
- **优先级**：P0

#### 场景 9.4：导航按钮 - 存档
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 点击 `#btn-save`
  2. 监听 `bridge.save_requested` 信号
- **预期结果**：`save_requested` 信号被触发
- **优先级**：P0

#### 场景 9.5：导航按钮 - 读档
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 点击 `#btn-load`
  2. 监听 `bridge.load_requested` 信号
- **预期结果**：`load_requested` 信号被触发
- **优先级**：P0

#### 场景 9.6：导航按钮 - 设置
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 点击 `#btn-settings`
  2. 监听 `bridge.settings_requested` 信号
- **预期结果**：`settings_requested` 信号被触发
- **优先级**：P0

#### 场景 9.7：initGameState 信号处理
- **前置条件**：Bridge 已连接
- **测试步骤**：
  1. 构造完整的游戏状态字典
  2. 发射 `bridge.init_game_state.emit(state_dict)`
  3. 检查嫌疑人列表是否更新
  4. 检查证据列表是否更新
  5. 检查计时器是否更新
  6. 检查聊天输入是否启用
- **预期结果**：所有 UI 组件根据初始化数据正确更新
- **优先级**：P0

---

### 功能模块 10：端到端集成场景

#### 场景 10.1：完整审讯流程 - 选择嫌疑人 → 发送消息 → 收到回复
- **前置条件**：Bridge 已连接，游戏已初始化
- **测试步骤**：
  1. 初始化游戏状态
  2. 选择嫌疑人（触发 `suspect_selected`）
  3. Python 端回复 `update_suspect` 信号更新嫌疑人信息
  4. 在输入框输入问题
  5. 点击发送
  6. Python 端回复 `add_message` 信号显示嫌疑人回答
  7. 检查聊天区域有 2 条消息（玩家 + 嫌疑人）
- **预期结果**：完整双向通信流程正常
- **优先级**：P0

#### 场景 10.2：施压流程 - 施压 → 压力增加 → UI 更新
- **前置条件**：嫌疑人已选中
- **测试步骤**：
  1. 点击施压按钮
  2. Python 端处理并回复 `update_suspect` 信号（压力增加 10）
  3. 检查压力条和数值更新
- **预期结果**：施压后压力值正确增加，UI 反映变化
- **优先级**：P0

#### 场景 10.3：出示证据流程 - 点击证据 → 信号传递 → 消息反馈
- **前置条件**：证据列表已加载
- **测试步骤**：
  1. 点击证据卡片
  2. Python 端收到 `evidence_presented` 信号
  3. Python 端回复 `add_message` 显示证据出示的系统消息
- **预期结果**：证据出示后聊天区域有反馈
- **优先级**：P0

#### 场景 10.4：倒计时 + 时间耗尽流程
- **前置条件**：游戏进行中
- **测试步骤**：
  1. 连续发送 `update_timer` 信号递减
  2. 从 60 → 30 → 10 → 0
  3. 检查各阶段的计时器样式变化
  4. 时间为 0 时检查是否显示时间到对话框
- **预期结果**：计时器样式正确变化，时间到时触发结局
- **优先级**：P1

#### 场景 10.5：生成案件完整流程
- **前置条件**：应用已启动
- **测试步骤**：
  1. 点击"生成案件"
  2. Python 端显示加载 `show_loading`
  3. 生成完成后发送 `init_game_state`
  4. 发送 `hide_loading`
  5. 检查 UI 已初始化
- **预期结果**：生成案件流程完整，UI 正确更新
- **优先级**：P1

---

## 三、测试覆盖矩阵

| 功能点 | 正常路径 | 异常路径 | 边界条件 |
|--------|----------|----------|----------|
| **Bridge 初始化** | ✓ 场景2.1 | ✓ 场景2.11-2.13 | ✓ 场景2.12 |
| **JS→Python 通信** | ✓ 场景2.2-2.5 | — | ✓ 空字符串/负索引(已有阶段0测试) |
| **Python→JS 通信** | ✓ 场景2.6-2.10 | ✓ 场景2.13 | — |
| **Bridge 重试机制** | ✓ 场景2.11 | ✓ 场景2.12 | ✓ 场景2.13 |
| **聊天-发送消息** | ✓ 场景3.1 | ✓ 场景3.7-3.8 | — |
| **聊天-接收消息** | ✓ 场景3.2-3.3 | ✓ 场景3.10(XSS) | — |
| **聊天-清空** | ✓ 场景3.4 | — | — |
| **聊天-输入状态** | ✓ 场景3.5-3.6 | — | — |
| **嫌疑人-信息更新** | ✓ 场景4.1 | — | ✓ 场景4.11 |
| **嫌疑人-压力值** | ✓ 场景4.2-4.5 | ✓ 场景4.8-4.9 | ✓ 场景4.6-4.7 |
| **嫌疑人-选择** | ✓ 场景4.10 | — | — |
| **嫌疑人-施压/共情** | ✓ 场景4.12-4.13 | — | — |
| **证据-列表加载** | ✓ 场景5.1-5.2 | ✓ 场景5.4 | ✓ 场景5.5 |
| **证据-点击响应** | ✓ 场景5.3 | — | — |
| **证据-新证据标记** | ✓ 场景5.6 | — | — |
| **证据-标签** | ✓ 场景5.7 | — | — |
| **倒计时-显示** | ✓ 场景6.1-6.2 | ✓ 场景6.7-6.8 | ✓ 场景6.5-6.6 |
| **倒计时-状态样式** | ✓ 场景6.3-6.4 | — | ✓ 场景6.10 |
| **倒计时-连续更新** | ✓ 场景6.9 | — | — |
| **加载-显示/隐藏** | ✓ 场景7.1-7.2 | — | ✓ 场景7.7 |
| **加载-进度** | ✓ 场景7.3 | — | — |
| **加载-取消** | ✓ 场景7.4 | ✓ 场景7.5 | — |
| **模态框-显示/关闭** | ✓ 场景8.1-8.3 | — | — |
| **模态框-结局** | ✓ 场景8.5-8.7 | — | — |
| **模态框-存档列表** | ✓ 场景8.8 | — | — |
| **App-初始化** | ✓ 场景9.1-9.2 | — | — |
| **App-导航** | ✓ 场景9.3-9.6 | — | — |
| **App-游戏初始化** | ✓ 场景9.7 | — | — |
| **E2E-审讯流程** | ✓ 场景10.1 | — | — |
| **E2E-施压流程** | ✓ 场景10.2 | — | — |
| **E2E-证据流程** | ✓ 场景10.3 | — | — |
| **E2E-倒计时流程** | ✓ 场景10.4 | — | ✓ 时间归零 |
| **E2E-生成案件** | ✓ 场景10.5 | — | — |
| **文件结构** | ✓ 场景1.1 | — | ✓ 场景1.3-1.4 |

---

## 四、测试文件规划

| 测试文件 | 覆盖模块 | 优先级 |
|----------|----------|--------|
| `tests/test_js_modules.py` | 文件结构（场景 1.x） | P0 |
| `tests/test_bridge_comm.py` | Bridge 双向通信（场景 2.x） | P0 |
| `tests/test_js_chat.py` | 聊天模块（场景 3.x） | P0 |
| `tests/test_js_suspect.py` | 嫌疑人模块（场景 4.x） | P0 |
| `tests/test_js_evidence.py` | 证据模块（场景 5.x） | P0 |
| `tests/test_js_timer.py` | 倒计时模块（场景 6.x） | P0 |
| `tests/test_js_loading.py` | 加载状态模块（场景 7.x） | P0 |
| `tests/test_js_modal.py` | 模态框模块（场景 8.x） | P1 |
| `tests/test_js_app.py` | 主应用入口（场景 9.x） | P0 |
| `tests/test_e2e_web.py` | 端到端集成（场景 10.x） | P0/P1 |

---

## 五、风险点

### 5.1 高风险

1. **QWebChannel 异步时序**：`runJavaScript` 和信号传递都是异步的，测试中需要正确等待。使用 `qtbot.waitSignal` / `qtbot.waitUntil` 确保时序正确，但超时设置需合理（推荐 3000ms）。
2. **QWebEngineView 初始化延迟**：WebView 页面加载需要时间，Bridge 连接可能在页面完全加载后才可用。需要在测试中等待页面 `loadFinished` 信号。
3. **JS 作用域隔离**：如果 JS 模块使用 IIFE 或闭包，`runJavaScript` 可能无法直接访问内部变量。需要确保模块通过全局命名空间暴露必要的接口。

### 5.2 中风险

4. **CI/CD 环境问题**：QWebEngineView 依赖 GPU 和显示服务（X11/Wayland），在无头 CI 环境中可能无法运行。需要配置 `QT_QPA_PLATFORM=offscreen` 或使用 `xvfb`。
5. **信号参数类型**：Python 信号发射的参数类型（如 `list`、`dict`）在传递到 JS 端后可能变为 JSON 对象。测试中需验证类型转换正确。
6. **JS 执行错误**：`runJavaScript` 中 JS 代码出错不会抛出 Python 异常，只是静默失败。需要通过返回值和 `console.log` 捕获检查。

### 5.3 低风险

7. **浏览器兼容性**：QWebEngineView 基于 Chromium，JS 特性支持较新，但仍需注意不使用过新的 API。
8. **性能基准**：大量 DOM 操作（如 20+ 证据卡片）的性能测试需要基准值，避免因环境差异导致误判。

---

## 六、补充说明

### 6.1 与现有测试的关系

- 阶段 0 的 `test_web_bridge.py` 测试 Python 端信号/槽，阶段 2 测试在此基础上增加 **JS 端验证**
- 阶段 0 的 `test_web_init.py` 测试窗口初始化，阶段 2 测试在此基础上增加 **JS 模块加载验证**
- 阶段 1 的 `test_web_structure.py` / `test_web_animations.py` 测试 HTML/CSS 结构，阶段 2 不影响这些测试

### 6.2 Fixture 设计

新增以下 fixture 供阶段 2 测试使用：

```python
@pytest.fixture
def web_window(qtbot):
    """创建 WebMainWindow 并等待页面加载完成。"""
    window = WebMainWindow()
    qtbot.addWidget(window)
    qtbot.waitSignal(window.web_view.loadFinished, timeout=10000)
    return window

@pytest.fixture
def connected_bridge(web_window, qtbot):
    """返回已连接 Bridge 的 WebMainWindow，确保 JS Bridge 已就绪。"""
    # 等待 Bridge 连接
    qtbot.waitUntil(
        lambda: web_window.web_view.page().runJavaScript(
            "window.TheBox && window.TheBox.bridge && window.TheBox.bridge.isConnected",
            lambda r: r is True
        ),
        timeout=5000
    )
    return web_window
```

### 6.3 标记规范

- `@pytest.mark.real_api`：需要真实 API Key 的测试
- `@pytest.mark.slow`：执行时间超过 2 秒的测试
- `@pytest.mark.webview`：需要 QWebEngineView 的测试（用于 CI 环境跳过）
