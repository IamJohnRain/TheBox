# WebView UI 重构实施方案

## 文档目的

本文档指导 AI Agent 团队将 The Box: Local Verdict 项目从 PySide6 原生 UI 重构为基于 QWebEngineView 的现代化暗黑科技风格界面。

**技术选型**：
- WebView：QWebEngineView（PySide6-WebEngine）
- 前端：原生 HTML/CSS/JavaScript（无框架）
- 通信：QWebChannel（Python ↔ JS 双向通信）
- 风格：暗黑科技风（赛博朋克/侦探主题）

**核心原则**：
- 测试驱动开发（TDD）
- 保持后端业务逻辑不变
- 分阶段交付，每阶段可独立验收
- 用户操作反馈及时，避免"卡顿"感知

---

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                     WebMainWindow (QMainWindow)                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                QWebEngineView                             │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │          index.html (暗黑科技风 UI)                   │  │  │
│  │  │  ┌───────────┬─────────────────┬─────────────────┐  │  │  │
│  │  │  │  左侧面板  │    中央聊天区    │   右侧证据面板   │  │  │  │
│  │  │  │           │                 │                 │  │  │  │
│  │  │  │ 嫌疑人选择 │   聊天消息流     │   证据卡片列表   │  │  │  │
│  │  │  │ 头像/压力条│   输入框/发送    │   点击出示证据   │  │  │  │
│  │  │  │ 施压/共情  │   倒计时        │                 │  │  │  │
│  │  │  │           │   加载指示器     │                 │  │  │  │
│  │  │  └───────────┴─────────────────┴─────────────────┘  │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              ↕ QWebChannel                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                  WebBridge (QObject)                       │  │
│  │  Python → JS: updateSuspect(), addMessage(), updateTimer() │  │
│  │              showLoading(), hideLoading()                  │  │
│  │  JS → Python: sendMessage(), selectSuspect(), presentEvidence() │  │
│  │               cancelOperation()                            │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              InterrogationEngine (不变)                     │  │
│  │              SuspectAgent (不变)                            │  │
│  │              core/* (不变)                                  │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 新增文件结构

```
TheBox/
├── ui/
│   ├── web/                          # 新增：前端资源目录
│   │   ├── index.html                # 主页面
│   │   ├── css/
│   │   │   ├── style.css             # 主样式（暗黑科技风）
│   │   │   ├── animations.css        # 动画效果
│   │   │   └── components.css        # 组件样式
│   │   ├── js/
│   │   │   ├── app.js                # 主应用逻辑
│   │   │   ├── bridge.js             # QWebChannel 通信桥接
│   │   │   ├── chat.js               # 聊天模块
│   │   │   ├── suspect.js            # 嫌疑人模块
│   │   │   ├── evidence.js           # 证据模块
│   │   │   ├── timer.js              # 倒计时模块
│   │   │   ├── loading.js            # 加载状态模块（新增）
│   │   │   └── modal.js              # 模态框模块（新增）
│   │   └── assets/                   # 前端静态资源
│   │       ├── icons/                # SVG 图标
│   │       └── sounds/               # 音效（可选）
│   ├── web_main_window.py            # 新增：WebView 主窗口
│   ├── web_bridge.py                 # 新增：Python-JS 通信桥接
│   └── resource_helper.py            # 新增：资源路径辅助工具
├── tests/
│   ├── test_web_bridge.py            # 新增：桥接层测试
│   ├── test_web_main_window.py       # 新增：主窗口测试
│   ├── test_web_integration.py       # 新增：集成测试
│   └── test_web_loading.py           # 新增：加载状态测试
├── assets/
│   └── styles/                       # 可选：QSS 备份
├── resources.qrc                     # 新增：Qt 资源文件
└── requirements.txt                  # 修改：添加 pyside6-webengine
```

---

## 关键技术决策

### 1. 资源路径管理（解决打包后路径问题）

**问题**：`Path(__file__).parent` 在 PyInstaller 打包后指向临时目录，前端资源无法加载。

**解决方案**：使用 Qt 资源系统（.qrc）+ 运行时路径检测

```python
# ui/resource_helper.py
import sys
from pathlib import Path
from PySide6.QtCore import QUrl

def get_resource_url(relative_path: str) -> QUrl:
    """获取资源 URL，兼容开发环境和打包环境"""
    if getattr(sys, 'frozen', False):
        # 打包环境：使用 Qt 资源系统
        return QUrl(f"qrc:///ui/web/{relative_path}")
    else:
        # 开发环境：使用本地文件
        base_path = Path(__file__).parent
        full_path = base_path / "web" / relative_path
        return QUrl.fromLocalFile(str(full_path))

def get_html_url() -> QUrl:
    """获取主页面 URL"""
    return get_resource_url("index.html")
```

**资源文件配置** (`resources.qrc`)：
```xml
<!DOCTYPE RCC>
<RCC version="1.0">
    <qresource prefix="/ui/web">
        <file>ui/web/index.html</file>
        <file>ui/web/css/style.css</file>
        <file>ui/web/css/animations.css</file>
        <file>ui/web/css/components.css</file>
        <file>ui/web/js/app.js</file>
        <file>ui/web/js/bridge.js</file>
        <file>ui/web/js/chat.js</file>
        <file>ui/web/js/suspect.js</file>
        <file>ui/web/js/evidence.js</file>
        <file>ui/web/js/timer.js</file>
        <file>ui/web/js/loading.js</file>
        <file>ui/web/js/modal.js</file>
    </qresource>
</RCC>
```

### 2. LLM 调用用户体验（加载状态与超时处理）

**问题**：LLM 调用可能耗时数十秒，用户无反馈会感觉页面"卡住"。

**解决方案**：加载指示器 + 超时机制 + 取消操作

**WebBridge 新增信号**：
```python
# Python → JS 信号
show_loading = Signal(str, bool)   # message, cancellable
hide_loading = Signal()
update_loading_progress = Signal(int)  # elapsed_seconds

# JS → Python 信号
cancel_requested = Signal()
```

**超时处理机制**：
```python
# WebMainWindow 中
LLM_TIMEOUT_SECONDS = 60  # LLM 调用超时时间

def _start_worker(self, action, content, evidence_id=None):
    # 显示加载状态
    self.bridge.show_loading.emit("正在审讯中...", True)
    self.bridge.set_input_enabled.emit(False)
    
    # 启动超时计时器
    self._timeout_timer = QTimer(self)
    self._timeout_timer.setSingleShot(True)
    self._timeout_timer.timeout.connect(self._on_worker_timeout)
    self._timeout_timer.start(LLM_TIMEOUT_SECONDS * 1000)
    
    # 启动进度更新计时器
    self._progress_timer = QTimer(self)
    self._progress_timer.setInterval(1000)
    self._progress_timer.timeout.connect(self._update_loading_progress)
    self._progress_timer.start()
    
    # 创建并启动 Worker
    ...

def _on_worker_timeout(self):
    if self._current_worker and self._current_worker.isRunning():
        self._current_worker.terminate()
        self._cleanup_after_worker()
        self.bridge.hide_loading.emit()
        self.bridge.add_message.emit("system", "响应超时，请重试", "")
        self.bridge.set_input_enabled.emit(True)

def _on_cancel_operation(self):
    """用户取消操作"""
    if self._current_worker and self._current_worker.isRunning():
        self._current_worker.terminate()
        self._cleanup_after_worker()
        self.bridge.hide_loading.emit()
        self.bridge.add_message.emit("system", "操作已取消", "")
        self.bridge.set_input_enabled.emit(True)
```

### 3. 状态同步机制

**问题**：`load_case` 后前端状态初始化不完整。

**解决方案**：统一的状态初始化信号

```python
# WebBridge 新增信号
init_game_state = Signal(dict)  # 包含嫌疑人列表、证据列表、倒计时等完整状态

# WebMainWindow.load_case 中
def load_case(self, case_data):
    self.engine = InterrogationEngine(case_data)
    
    # 构建完整初始状态
    state = {
        "suspects": [{"name": s.name, "pressure": s.pressure} for s in self.engine.suspects],
        "evidences": case_data.get("evidences", []),
        "time_left": self.engine.time_left,
        "current_suspect_index": 0,
    }
    
    # 一次性发送完整状态
    self.bridge.init_game_state.emit(state)
    self.bridge.set_input_enabled.emit(True)
```

---

## 分阶段实施计划

---

## 阶段 0：环境准备与基础设施

### 目标
搭建 WebView 开发环境，创建基础文件结构，验证 QWebEngineView 可用，建立资源管理机制。

### 验收标准
- [ ] `requirements.txt` 包含 `pyside6-webengine`
- [ ] 能启动一个空白 QWebEngineView 窗口显示 "Hello WebView"
- [ ] QWebChannel 通信基础测试通过
- [ ] 资源路径辅助工具实现并测试通过
- [ ] 所有现有测试不受影响

### Agent 任务分解

#### @test（场景用例设计 → 评审 → 测试开发）

**场景用例设计 Prompt**：
```
为 WebView UI 重构的阶段 0（环境准备）设计测试场景用例。

功能模块：WebView 基础设施

需要覆盖的测试点：
1. QWebEngineView 能否正常初始化
2. QWebChannel 能否注册对象
3. Python → JS 信号能否触发
4. JS → Python Slot 能否调用
5. 现有 PySide6 原生 UI 测试是否仍然通过
6. 依赖安装是否正确
7. 资源路径辅助工具在开发环境和打包环境下是否正确

输出格式：
- 场景用例设计文档（含前置条件、测试步骤、预期结果、优先级）
- 测试覆盖矩阵
- 风险点分析
```

**测试开发 Prompt**（评审通过后）：
```
为阶段 0 编写自动化验收测试。

1. `tests/test_web_channel.py`：
   - test_bridge_signal_emission：测试 WebBridge 的 Python→JS 信号能正常发射
   - test_bridge_slot_invocation：测试 JS→Python 的 Slot 能正常调用
   - test_bridge双向通信：测试完整的 Python→JS→Python 循环

2. `tests/test_web_init.py`（pytest-qt）：
   - test_webengine_available：测试 QWebEngineView 可导入
   - test_web_window_creation：测试 WebMainWindow 能创建实例
   - test_webview_loads_html：测试 WebView 能加载 HTML 内容

3. `tests/test_resource_helper.py`：
   - test_get_resource_url_dev：测试开发环境资源路径
   - test_get_resource_url_frozen：模拟打包环境资源路径

4. 确保现有测试通过：
   - 运行 `pytest tests/ -m "not slow" -v` 确认无回归

验收命令：`pytest tests/test_web_channel.py tests/test_web_init.py tests/test_resource_helper.py -v`
```

#### @dev（开发实现）

**开发 Prompt**：
```
实现 WebView UI 重构的基础设施。

1. 更新 `requirements.txt`：
   - 添加 `pyside6-webengine>=6.5.0`

2. 创建 `ui/resource_helper.py`：
   ```python
   import sys
   from pathlib import Path
   from PySide6.QtCore import QUrl
   
   def get_resource_url(relative_path: str) -> QUrl:
       """获取资源 URL，兼容开发环境和打包环境"""
       if getattr(sys, 'frozen', False):
           return QUrl(f"qrc:///ui/web/{relative_path}")
       else:
           base_path = Path(__file__).parent
           full_path = base_path / "web" / relative_path
           return QUrl.fromLocalFile(str(full_path))
   
   def get_html_url() -> QUrl:
       """获取主页面 URL"""
       return get_resource_url("index.html")
   ```

3. 创建 `ui/web_bridge.py`：
   ```python
   from PySide6.QtCore import QObject, Signal, Slot
   
   class WebBridge(QObject):
       """Python与JavaScript的通信桥接"""
       
       # === JS → Python 信号 ===
       message_sent = Signal(str)
       suspect_selected = Signal(int)
       evidence_presented = Signal(str)
       pressure_applied = Signal()
       empathy_applied = Signal()
       save_requested = Signal()
       load_requested = Signal()
       settings_requested = Signal()
       generate_case_requested = Signal()
       cancel_requested = Signal()  # 新增：取消操作
       
       # === Python → JS 信号 ===
       # 游戏状态
       init_game_state = Signal(dict)  # 新增：初始化完整游戏状态
       update_suspect = Signal(str, int)  # name, pressure
       add_message = Signal(str, str, str)  # role, content, suspect_name
       update_timer = Signal(int)  # time_left
       update_evidence_list = Signal(list)  # evidences
       set_input_enabled = Signal(bool)
       show_dialog = Signal(str, str)  # title, message
       clear_chat = Signal()
       
       # 加载状态（新增）
       show_loading = Signal(str, bool)  # message, cancellable
       hide_loading = Signal()
       update_loading_progress = Signal(int)  # elapsed_seconds
       
       # 存档列表（新增）
       show_save_list = Signal(list)  # sessions
       
       @Slot(str)
       def sendMessage(self, text: str):
           self.message_sent.emit(text)
       
       @Slot(int)
       def selectSuspect(self, index: int):
           self.suspect_selected.emit(index)
       
       @Slot(str)
       def presentEvidence(self, evidence_id: str):
           self.evidence_presented.emit(evidence_id)
       
       @Slot()
       def applyPressure(self):
           self.pressure_applied.emit()
       
       @Slot()
       def applyEmpathy(self):
           self.empathy_applied.emit()
       
       @Slot()
       def requestSave(self):
           self.save_requested.emit()
       
       @Slot()
       def requestLoad(self):
           self.load_requested.emit()
       
       @Slot()
       def requestSettings(self):
           self.settings_requested.emit()
       
        @Slot()
        def requestGenerateCase(self):
            self.generate_case_requested.emit()

        @Slot()
        def cancelOperation(self):
            """取消当前操作"""
            self.cancel_requested.emit()

        @Slot(str)
        def selectSave(self, session_id: str):
            """选择存档（由前端模态框调用）"""
            self.save_selected.emit(session_id)
    ```

4. 创建 `ui/web_main_window.py` 框架：
   ```python
   from PySide6.QtCore import QUrl, QTimer
   from PySide6.QtWebEngineWidgets import QWebEngineView
   from PySide6.QtWebChannel import QWebChannel
   from PySide6.QtWidgets import QMainWindow
   
   from ui.web_bridge import WebBridge
   from ui.resource_helper import get_html_url
   
   class WebMainWindow(QMainWindow):
       """基于 WebView 的主窗口"""
       
       def __init__(self, case_data=None):
           super().__init__()
           self.setWindowTitle("The Box: Local Verdict")
           self.resize(1280, 800)
           
           # 创建 WebView
           self.web_view = QWebEngineView()
           
           # 设置通信通道
           self.bridge = WebBridge()
           self.channel = QWebChannel()
           self.channel.registerObject("bridge", self.bridge)
           self.web_view.page().setWebChannel(self.channel)
           
           # 加载 HTML（使用资源辅助工具）
           self.web_view.setUrl(get_html_url())
           
           # 设置中心部件
           self.setCentralWidget(self.web_view)
   ```

5. 创建 `ui/web/index.html` 基础结构：
   ```html
   <!DOCTYPE html>
   <html lang="zh-CN">
   <head>
       <meta charset="UTF-8">
       <meta name="viewport" content="width=device-width, initial-scale=1.0">
       <title>The Box: Local Verdict</title>
   </head>
   <body>
       <div id="app">
           <h1>The Box: Local Verdict</h1>
           <p>WebView 基础加载成功</p>
       </div>
       
       <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
       <script>
           // 基础通信测试
           new QWebChannel(qt.webChannelTransport, function(channel) {
               window.bridge = channel.objects.bridge;
               console.log("Bridge connected");
           });
       </script>
   </body>
   </html>
   ```

6. 创建 `resources.qrc` 资源文件

7. 运行自检清单确认实现质量
```

#### @review（评审验证）

**评审 Prompt**：
```
验证阶段 0 交付物：

1. 检查 `requirements.txt` 包含 `pyside6-webengine>=6.5.0`
2. 运行 `uv pip install -r requirements.txt` 安装依赖
3. 运行 `pytest tests/test_web_channel.py tests/test_web_init.py tests/test_resource_helper.py -v` 全部通过
4. 运行 `pytest tests/ -m "not slow" -v` 确认无回归
5. 检查代码：
   - WebBridge 的信号和 Slot 定义完整（包含加载状态信号）
   - WebMainWindow 能正常创建
   - QWebChannel 注册正确
   - resource_helper.py 实现正确
6. 运行 `python -c "from ui.web_main_window import WebMainWindow; print('Import OK')"` 验证导入

全部满足后输出 "阶段0验收通过"。
```

---

## 阶段 1：前端 UI 框架与暗黑科技风格

### 目标
创建完整的 HTML 页面结构，实现暗黑科技风格的 CSS 样式系统，包含加载指示器组件。

### 验收标准
- [ ] HTML 页面包含三栏布局（左侧嫌疑人、中间聊天、右侧证据）
- [ ] CSS 实现暗黑科技风格（深色背景、霓虹高亮、赛博朋克元素）
- [ ] 加载指示器组件实现并样式正确
- [ ] 响应式布局适配不同窗口尺寸
- [ ] 动画效果流畅（消息淡入、进度条过渡等）
- [ ] 前端资源文件结构正确

### Agent 任务分解

#### @test（场景用例设计 → 评审 → 测试开发）

**场景用例设计 Prompt**：
```
为阶段 1（前端 UI 框架）设计测试场景用例。

功能模块：前端 UI 结构与样式

需要覆盖的测试点：
1. HTML 结构完整性（必要的 DOM 元素存在）
2. CSS 变量定义正确（颜色、字体、间距）
3. 三栏布局响应式表现
4. 暗黑科技风格视觉元素
5. 加载指示器组件结构和样式
6. 动画效果触发条件
7. 跨浏览器兼容性（WebView 内核）

输出：场景用例设计文档
```

**测试开发 Prompt**（评审通过后）：
```
为阶段 1 编写验收测试。

1. `tests/test_web_structure.py`（使用 pytest-qt + JavaScript 执行）：
   - test_html_structure：验证必要 DOM 元素存在（#app, .panel-left, .panel-center, .panel-right）
   - test_css_variables：验证 CSS 变量定义正确
   - test_responsive_layout：验证窗口尺寸变化时布局自适应
   - test_dark_theme_colors：验证暗色主题配色应用
   - test_loading_indicator_structure：验证加载指示器 DOM 结构

2. `tests/test_web_animations.py`：
   - test_message_fade_in：验证消息添加时有淡入动画
   - test_pressure_bar_transition：验证压力条变化有过渡动画

验收命令：`pytest tests/test_web_structure.py tests/test_web_animations.py -v`
```

#### @ui（UI 设计与实现）

**UI 设计 Prompt**：
```
设计并实现 The Box: Local Verdict 的暗黑科技风格前端 UI。

## 设计规范

### 配色方案
- 主背景：#0a0e17（深蓝黑）
- 次背景：#111827（深灰蓝）
- 卡片背景：#1a2332（暗蓝灰）
- 主文字：#e0e0e0（浅灰）
- 次文字：#8892a0（中灰）
- 主强调色：#00f5ff（霓虹青）
- 次强调色：#b388ff（紫色）
- 危险色：#ff4757（红色）
- 成功色：#00e676（绿色）

### 布局结构
```
┌─────────────────────────────────────────────────────────────┐
│  顶部导航栏：LOGO + 菜单按钮（生成案件/存档/读档/设置）         │
├───────────┬───────────────────────────┬─────────────────────┤
│           │                           │                     │
│  左侧面板  │      中央聊天区            │    右侧证据面板      │
│  280px    │      flex: 1              │    300px            │
│           │                           │                     │
│  ┌─────┐  │  ┌─────────────────────┐  │  ┌───────────────┐  │
│  │选择器│  │  │                     │  │  │   证据卡片 1   │  │
│  ├─────┤  │  │     聊天消息流       │  │  ├───────────────┤  │
│  │头像 │  │  │                     │  │  │   证据卡片 2   │  │
│  │压力条│  │  │                     │  │  ├───────────────┤  │
│  ├─────┤  │  ├─────────────────────┤  │  │   证据卡片 3   │  │
│  │施压 │  │  │  输入框    [发送]    │  │  └───────────────┘  │
│  │共情 │  │  ├─────────────────────┤  │                     │
│  └─────┘  │  │     倒计时: XXs      │  │                     │
│           │  ├─────────────────────┤  │                     │
│           │  │  加载指示器（隐藏）   │  │                     │
│           │  └─────────────────────┘  │                     │
└───────────┴───────────────────────────┴─────────────────────┘
```

### 组件样式要求

1. **顶部导航栏**：
   - 高度 56px，背景半透明毛玻璃效果
   - Logo 带霓虹青发光效果
   - 菜单按钮悬停时有光晕动画

2. **嫌疑人卡片**：
   - 头像圆形，带霓虹青边框和发光阴影
   - 压力条渐变色（绿→黄→红），带脉冲动画
   - 状态徽章（就绪/审讯中/崩溃）

3. **聊天消息**：
   - 玩家消息靠右，渐变蓝色背景
   - 嫌疑人消息靠左，深色卡片背景
   - 系统消息居中，灰色斜体
   - 消息出现时有淡入上移动画

4. **证据卡片**：
   - 深色背景，紫色边框
   - 悬停时边框发光，轻微上浮
   - 点击时有涟漪效果

5. **操作按钮**：
   - 施压按钮：红色渐变，带闪电图标
   - 共情按钮：绿色渐变，带心形图标
   - 按钮点击时有按压反馈动画

6. **倒计时**：
   - 霓虹青数字，带发光效果
   - 剩余 30 秒时变红闪烁

7. **加载指示器**（新增）：
   - 全屏半透明遮罩（rgba(0,0,0,0.7)）
   - 中央显示旋转动画 + 提示文字
   - 可选取消按钮
   - 显示已等待时间
   - 淡入淡出动画

### 文件输出
1. `ui/web/index.html` - 主页面结构
2. `ui/web/css/style.css` - 主样式
3. `ui/web/css/animations.css` - 动画定义
4. `ui/web/css/components.css` - 组件样式
5. `ui/web/assets/icons/` - SVG 图标文件

### 集成说明
- HTML 中通过 `<link>` 引入 CSS 文件
- 使用 `qrc:///qtwebchannel/qwebchannel.js` 引入通信库
- 所有样式使用 CSS 变量，便于主题切换
```

#### @dev（集成实现）

**开发 Prompt**：
```
集成 @ui 交付的前端资源到项目中。

1. 创建目录结构：
   - `ui/web/`
   - `ui/web/css/`
   - `ui/web/js/`
   - `ui/web/assets/`

2. 将 @ui 交付的 HTML/CSS 文件放入对应目录

3. 修改 `ui/web_main_window.py`：
   - 使用 `get_html_url()` 加载 HTML
   - 确保资源路径正确

4. 更新 `resources.qrc` 包含所有前端资源

5. 验证前端资源能正常加载显示
```

#### @review（评审验证）

**评审 Prompt**：
```
验证阶段 1 交付物：

1. 检查文件结构：
   - `ui/web/index.html` 存在且结构完整
   - `ui/web/css/style.css` 存在且包含 CSS 变量定义
   - `ui/web/css/animations.css` 存在
   - `ui/web/css/components.css` 存在

2. 运行测试：
   - `pytest tests/test_web_structure.py -v` 全部通过
   - `pytest tests/test_web_animations.py -v` 全部通过

3. 视觉验证（通过截图或描述）：
   - 暗黑科技风格是否正确应用
   - 三栏布局是否正确
   - 加载指示器样式是否正确
   - 动画效果是否流畅

4. 代码质量：
   - CSS 使用变量，便于维护
   - HTML 语义化标签
   - 无内联样式（除必要情况）

全部满足后输出 "阶段1验收通过"。
```

---

## 阶段 2：JavaScript 通信层与核心模块

### 目标
实现 JavaScript 端的通信桥接和核心功能模块（聊天、嫌疑人、证据、倒计时、加载状态）。

### 验收标准
- [ ] JS 能通过 QWebChannel 调用 Python 方法
- [ ] Python 信号能触发 JS 函数更新 UI
- [ ] 聊天消息收发正常
- [ ] 嫌疑人切换和信息更新正常
- [ ] 证据列表加载和点击响应正常
- [ ] 倒计时显示和更新正常
- [ ] 加载状态显示和隐藏正常
- [ ] Bridge 初始化有重试机制

### Agent 任务分解

#### @test（场景用例设计 → 评审 → 测试开发）

**场景用例设计 Prompt**：
```
为阶段 2（JavaScript 通信层）设计测试场景用例。

功能模块：JS-Python 通信与核心功能

需要覆盖的测试场景：

1. 通信层测试
   - 场景1：Bridge 初始化成功
   - 场景2：Bridge 初始化失败后重试
   - 场景3：Python 信号触发 JS 回调
   - 场景4：JS 调用 Python Slot 成功
   - 场景5：通信异常处理

2. 聊天模块测试
   - 场景6：发送消息到 Python
   - 场景7：接收消息并显示
   - 场景8：消息类型区分显示（玩家/嫌疑人/系统）
   - 场景9：空消息不发送
   - 场景10：长消息自动换行

3. 嫌疑人模块测试
   - 场景11：嫌疑人列表加载
   - 场景12：嫌疑人切换
   - 场景13：压力条更新
   - 场景14：头像根据压力变化

4. 证据模块测试
   - 场景15：证据列表加载
   - 场景16：证据点击响应
   - 场景17：证据确认对话框

5. 倒计时模块测试
   - 场景18：倒计时显示
   - 场景19：倒计时每秒更新
   - 场景20：倒计时归零处理

6. 加载状态模块测试（新增）
   - 场景21：加载指示器显示
   - 场景22：加载指示器隐藏
   - 场景23：取消按钮响应
   - 场景24：进度更新显示

输出：场景用例设计文档（含优先级 P0/P1/P2）
```

**测试开发 Prompt**（评审通过后）：
```
为阶段 2 编写验收测试。

1. `tests/test_web_bridge.py`：
   - test_bridge_initialization：测试 Bridge 初始化
   - test_bridge_retry_on_failure：测试初始化失败后重试
   - test_python_to_js_signal：测试 Python→JS 信号传递
   - test_js_to_python_slot：测试 JS→Python Slot 调用
   - test_bidirectional_communication：测试完整双向通信循环

2. `tests/test_web_chat.py`（通过 JavaScript 执行验证）：
   - test_send_message：验证 JS 发送消息到 Python
   - test_receive_message：验证 Python 消息在 JS 端显示
   - test_message_types：验证不同角色消息样式不同
   - test_empty_message_not_sent：验证空消息不发送

3. `tests/test_web_suspect.py`：
   - test_suspect_list_load：验证嫌疑人列表加载
   - test_suspect_switch：验证嫌疑人切换
   - test_pressure_update：验证压力条更新
   - test_avatar_change：验证头像随压力变化

4. `tests/test_web_evidence.py`：
   - test_evidence_list_load：验证证据列表加载
   - test_evidence_click：验证证据点击响应
   - test_evidence_confirm_dialog：验证确认对话框

5. `tests/test_web_timer.py`：
   - test_timer_display：验证倒计时显示
   - test_timer_update：验证倒计时更新
   - test_timer_zero：验证倒计时归零处理

6. `tests/test_web_loading.py`（新增）：
   - test_loading_show：验证加载指示器显示
   - test_loading_hide：验证加载指示器隐藏
   - test_loading_cancel：验证取消按钮响应
   - test_loading_progress：验证进度更新

验收命令：`pytest tests/test_web_*.py -v`
```

#### @dev（开发实现）

**开发 Prompt**：
```
实现 JavaScript 通信层和核心功能模块。

1. 创建 `ui/web/js/bridge.js`：
   ```javascript
   /**
    * QWebChannel 通信桥接模块
    * 负责 Python ↔ JavaScript 双向通信
    */
   class WebBridge {
       constructor() {
           this.pythonBridge = null;
           this.callbacks = {};
           this._initRetries = 0;
           this._maxRetries = 3;
       }
   
       /**
        * 初始化 QWebChannel 连接（带重试机制）
        * @returns {Promise} 连接完成的 Promise
        */
       init() {
           return new Promise((resolve, reject) => {
               this._attemptInit(resolve, reject);
           });
       }
   
       _attemptInit(resolve, reject) {
           new QWebChannel(qt.webChannelTransport, (channel) => {
               this.pythonBridge = channel.objects.bridge;
               if (this.pythonBridge) {
                   this._setupSignalListeners();
                   console.log('Bridge initialized successfully');
                   resolve(this.pythonBridge);
               } else {
                   this._handleInitFailure(resolve, reject);
               }
           });
       }
   
       _handleInitFailure(resolve, reject) {
           this._initRetries++;
           if (this._initRetries < this._maxRetries) {
               console.warn(`Bridge init failed, retrying (${this._initRetries}/${this._maxRetries})`);
               setTimeout(() => this._attemptInit(resolve, reject), 1000);
           } else {
               reject(new Error("Bridge initialization failed after " + this._maxRetries + " attempts"));
           }
       }
   
       /**
        * 设置 Python 信号监听器
        */
       _setupSignalListeners() {
           // 游戏状态初始化（新增）
           this.pythonBridge.init_game_state.connect((state) => {
               this._trigger('initGameState', { state });
           });
   
           // 嫌疑人更新信号
           this.pythonBridge.update_suspect.connect((name, pressure) => {
               this._trigger('suspectUpdate', { name, pressure });
           });
   
           // 新消息信号
           this.pythonBridge.add_message.connect((role, content, suspectName) => {
               this._trigger('newMessage', { role, content, suspectName });
           });
   
           // 倒计时更新信号
           this.pythonBridge.update_timer.connect((timeLeft) => {
               this._trigger('timerUpdate', { timeLeft });
           });
   
           // 证据列表更新信号
           this.pythonBridge.update_evidence_list.connect((evidences) => {
               this._trigger('evidenceUpdate', { evidences });
           });
   
           // 输入状态信号
           this.pythonBridge.set_input_enabled.connect((enabled) => {
               this._trigger('inputEnabled', { enabled });
           });
   
           // 对话框信号
           this.pythonBridge.show_dialog.connect((title, message) => {
               this._trigger('showDialog', { title, message });
           });
   
           // 清空聊天信号
           this.pythonBridge.clear_chat.connect(() => {
               this._trigger('clearChat');
           });
   
           // 加载状态信号（新增）
           this.pythonBridge.show_loading.connect((message, cancellable) => {
               this._trigger('showLoading', { message, cancellable });
           });
   
           this.pythonBridge.hide_loading.connect(() => {
               this._trigger('hideLoading');
           });
   
           this.pythonBridge.update_loading_progress.connect((elapsedSeconds) => {
               this._trigger('loadingProgress', { elapsedSeconds });
           });
   
           // 存档列表信号（新增）
           this.pythonBridge.show_save_list.connect((sessions) => {
               this._trigger('showSaveList', { sessions });
           });
       }
   
       /**
        * 注册事件回调
        * @param {string} event - 事件名称
        * @param {Function} callback - 回调函数
        */
       on(event, callback) {
           if (!this.callbacks[event]) {
               this.callbacks[event] = [];
           }
           this.callbacks[event].push(callback);
       }
   
       /**
        * 触发事件
        * @param {string} event - 事件名称
        * @param {Object} data - 事件数据
        */
       _trigger(event, data) {
           if (this.callbacks[event]) {
               this.callbacks[event].forEach(cb => cb(data));
           }
       }
   
       // === JS → Python 方法调用 ===
   
       sendMessage(text) {
           if (this.pythonBridge && text.trim()) {
               this.pythonBridge.sendMessage(text);
           }
       }
   
       selectSuspect(index) {
           if (this.pythonBridge) {
               this.pythonBridge.selectSuspect(index);
           }
       }
   
       presentEvidence(evidenceId) {
           if (this.pythonBridge) {
               this.pythonBridge.presentEvidence(evidenceId);
           }
       }
   
       applyPressure() {
           if (this.pythonBridge) {
               this.pythonBridge.applyPressure();
           }
       }
   
       applyEmpathy() {
           if (this.pythonBridge) {
               this.pythonBridge.applyEmpathy();
           }
       }
   
       requestSave() {
           if (this.pythonBridge) {
               this.pythonBridge.requestSave();
           }
       }
   
       requestLoad() {
           if (this.pythonBridge) {
               this.pythonBridge.requestLoad();
           }
       }
   
       requestSettings() {
           if (this.pythonBridge) {
               this.pythonBridge.requestSettings();
           }
       }
   
        requestGenerateCase() {
            if (this.pythonBridge) {
                this.pythonBridge.requestGenerateCase();
            }
        }

        selectSave(sessionId) {
            if (this.pythonBridge) {
                this.pythonBridge.selectSave(sessionId);
            }
        }

        cancelOperation() {
            if (this.pythonBridge) {
                this.pythonBridge.cancelOperation();
            }
        }
    }

    // 导出全局实例
    window.bridge = new WebBridge();
    ```

2. 创建 `ui/web/js/loading.js`（新增）：
   ```javascript
   /**
    * 加载状态模块
    * 管理加载指示器的显示和交互
    */
   class LoadingManager {
       constructor() {
           this.overlay = document.getElementById('loading-overlay');
           this.messageEl = document.getElementById('loading-message');
           this.progressEl = document.getElementById('loading-progress');
           this.cancelBtn = document.getElementById('loading-cancel');
           this.isVisible = false;
           this._setupEventListeners();
       }
   
       _setupEventListeners() {
           if (this.cancelBtn) {
               this.cancelBtn.addEventListener('click', () => {
                   window.bridge.cancelOperation();
                   this.hide();
               });
           }
       }
   
       /**
        * 显示加载指示器
        * @param {string} message - 提示消息
        * @param {boolean} cancellable - 是否可取消
        */
       show(message, cancellable = true) {
           this.messageEl.textContent = message;
           this.progressEl.textContent = '0秒';
           
           if (this.cancelBtn) {
               this.cancelBtn.style.display = cancellable ? 'block' : 'none';
           }
           
           this.overlay.classList.add('visible');
           this.isVisible = true;
       }
   
       /**
        * 隐藏加载指示器
        */
       hide() {
           this.overlay.classList.remove('visible');
           this.isVisible = false;
       }
   
       /**
        * 更新进度
        * @param {number} elapsedSeconds - 已等待秒数
        */
       updateProgress(elapsedSeconds) {
           if (this.isVisible && this.progressEl) {
               this.progressEl.textContent = `${elapsedSeconds}秒`;
           }
       }
   }
   ```

3. 创建 `ui/web/js/modal.js`：
   ```javascript
   /**
    * 模态框模块
    * 管理自定义对话框和存档选择
    */
   class ModalManager {
       constructor() {
           this.modalOverlay = document.getElementById('modal-overlay');
           this.modalTitle = document.getElementById('modal-title');
           this.modalContent = document.getElementById('modal-content');
           this.modalButtons = document.getElementById('modal-buttons');
           this._currentCallback = null;
           this._setupEventListeners();
       }
   
       _setupEventListeners() {
           // ESC 关闭
           document.addEventListener('keydown', (e) => {
               if (e.key === 'Escape' && this.isVisible()) {
                   this.hide();
               }
           });
           
           // 点击遮罩关闭
           this.modalOverlay?.addEventListener('click', (e) => {
               if (e.target === this.modalOverlay) {
                   this.hide();
               }
           });
       }
   
       isVisible() {
           return this.modalOverlay?.classList.contains('visible');
       }
   
       /**
        * 显示信息对话框
        * @param {string} title - 标题
        * @param {string} message - 消息
        */
       showInfo(title, message) {
           this._show(title, message, [
               { text: '确定', primary: true, action: () => this.hide() }
           ]);
       }
   
       /**
        * 显示确认对话框
        * @param {string} title - 标题
        * @param {string} message - 消息
        * @param {Function} onConfirm - 确认回调
        */
       showConfirm(title, message, onConfirm) {
           this._show(title, message, [
               { text: '取消', action: () => this.hide() },
               { text: '确认', primary: true, action: () => { this.hide(); onConfirm(); } }
           ]);
       }
   
       /**
        * 显示存档选择对话框（新增）
        * @param {Array} sessions - 存档列表
        */
       showSaveList(sessions) {
           let content = '<div class="save-list">';
           if (sessions.length === 0) {
               content += '<p class="no-saves">没有找到存档</p>';
           } else {
               sessions.forEach((session, index) => {
                   content += `
                       <div class="save-item" data-index="${index}">
                           <span class="save-name">${session.case_id || '未知案件'}</span>
                           <span class="save-time">${session.created_at || ''}</span>
                       </div>
                   `;
               });
           }
           content += '</div>';
           
           this._show('选择存档', content, [
               { text: '取消', action: () => this.hide() }
           ]);
           
            // 绑定存档项点击
            document.querySelectorAll('.save-item').forEach((item, index) => {
                item.addEventListener('click', () => {
                    this.hide();
                    window.bridge.selectSave(sessions[index].session_id);
                });
            });
       }
   
       _show(title, content, buttons) {
           if (!this.modalOverlay) return;
           
           this.modalTitle.textContent = title;
           this.modalContent.innerHTML = content;
           this.modalButtons.innerHTML = '';
           
           buttons.forEach(btn => {
               const button = document.createElement('button');
               button.textContent = btn.text;
               button.className = btn.primary ? 'btn-primary' : 'btn-secondary';
               button.addEventListener('click', btn.action);
               this.modalButtons.appendChild(button);
           });
           
           this.modalOverlay.classList.add('visible');
       }
   
       hide() {
           this.modalOverlay?.classList.remove('visible');
       }
   }
   ```

4. 更新 `ui/web/js/chat.js`（保持原有实现）

5. 更新 `ui/web/js/suspect.js`（保持原有实现）

6. 更新 `ui/web/js/evidence.js`（修改为使用模态框）：
   ```javascript
   class EvidenceManager {
       // ... 原有代码 ...
   
       _handleEvidenceClick(evidence) {
           // 使用模态框替代原生 confirm
           window.modalManager.showConfirm(
               '出示证据',
               `确定要出示证据「${evidence.name}」吗？`,
               () => {
                   window.bridge.presentEvidence(evidence.id);
               }
           );
       }
   
       // ... 其他代码不变 ...
   }
   ```

7. 更新 `ui/web/js/timer.js`（保持原有实现）

8. 更新 `ui/web/js/app.js`：
   ```javascript
   document.addEventListener('DOMContentLoaded', async () => {
       // 初始化 Bridge（带重试）
       try {
           await window.bridge.init();
           console.log('Bridge initialized successfully');
       } catch (error) {
           console.error('Failed to initialize bridge:', error);
           alert('无法连接到后端，请重启程序');
           return;
       }
   
       // 初始化各模块
       const chatManager = new ChatManager('chat-container', 'message-input', 'btn-send');
       const suspectManager = new SuspectManager();
       const evidenceManager = new EvidenceManager('evidence-list');
       const timerManager = new TimerManager('timer');
       const loadingManager = new LoadingManager();
       const modalManager = new ModalManager();
       
       // 暴露模态框管理器到全局
       window.modalManager = modalManager;
   
       // 绑定游戏状态初始化（新增）
       window.bridge.on('initGameState', (data) => {
           const state = data.state;
           suspectManager.loadSuspects(state.suspects);
           evidenceManager.loadEvidences(state.evidences);
           timerManager.update(state.time_left);
           if (state.suspects.length > 0) {
               suspectManager.updateSuspect(state.suspects[0].name, state.suspects[0].pressure);
           }
       });
   
       // 绑定 Bridge 事件
       window.bridge.on('suspectUpdate', (data) => {
           suspectManager.updateSuspect(data.name, data.pressure);
       });
   
       window.bridge.on('newMessage', (data) => {
           chatManager.addMessage(data.role, data.content, data.suspectName);
       });
   
       window.bridge.on('timerUpdate', (data) => {
           timerManager.update(data.timeLeft);
       });
   
       window.bridge.on('evidenceUpdate', (data) => {
           evidenceManager.loadEvidences(data.evidences);
       });
   
       window.bridge.on('inputEnabled', (data) => {
           chatManager.setInputEnabled(data.enabled);
       });
   
       window.bridge.on('showDialog', (data) => {
           modalManager.showInfo(data.title, data.message);
       });
   
       window.bridge.on('clearChat', () => {
           chatManager.clear();
           suspectManager.clear();
           evidenceManager.clear();
           timerManager.clear();
       });
   
       // 加载状态事件（新增）
       window.bridge.on('showLoading', (data) => {
           loadingManager.show(data.message, data.cancellable);
       });
   
       window.bridge.on('hideLoading', () => {
           loadingManager.hide();
       });
   
       window.bridge.on('loadingProgress', (data) => {
           loadingManager.updateProgress(data.elapsedSeconds);
       });
   
       // 存档列表事件（新增）
       window.bridge.on('showSaveList', (data) => {
           modalManager.showSaveList(data.sessions);
       });
   
       // 绑定操作按钮
       document.getElementById('btn-pressure')?.addEventListener('click', () => {
           window.bridge.applyPressure();
       });
   
       document.getElementById('btn-empathy')?.addEventListener('click', () => {
           window.bridge.applyEmpathy();
       });
   
       // 绑定菜单按钮
       document.getElementById('btn-generate')?.addEventListener('click', () => {
           window.bridge.requestGenerateCase();
       });
   
       document.getElementById('btn-save')?.addEventListener('click', () => {
           window.bridge.requestSave();
       });
   
       document.getElementById('btn-load')?.addEventListener('click', () => {
           window.bridge.requestLoad();
       });
   
       document.getElementById('btn-settings')?.addEventListener('click', () => {
           window.bridge.requestSettings();
       });
   
       console.log('Application initialized');
   });
   ```

9. 更新 `ui/web/index.html` 引入所有 JS 模块

10. 运行自检清单确认实现质量
```

#### @review（评审验证）

**评审 Prompt**：
```
验证阶段 2 交付物：

1. 检查文件结构：
   - `ui/web/js/bridge.js` 存在且实现完整（含重试机制）
   - `ui/web/js/loading.js` 存在且实现完整
   - `ui/web/js/modal.js` 存在且实现完整
   - `ui/web/js/chat.js` 存在且实现完整
   - `ui/web/js/suspect.js` 存在且实现完整
   - `ui/web/js/evidence.js` 存在且实现完整
   - `ui/web/js/timer.js` 存在且实现完整
   - `ui/web/js/app.js` 存在且实现完整

2. 运行测试：
   - `pytest tests/test_web_bridge.py -v` 全部通过
   - `pytest tests/test_web_chat.py -v` 全部通过
   - `pytest tests/test_web_suspect.py -v` 全部通过
   - `pytest tests/test_web_evidence.py -v` 全部通过
   - `pytest tests/test_web_timer.py -v` 全部通过
   - `pytest tests/test_web_loading.py -v` 全部通过

3. 代码质量：
   - JavaScript 代码有 JSDoc 注释
   - 模块职责清晰分离
   - 错误处理完善
   - 无全局变量污染
   - Bridge 初始化有重试机制

4. 功能验证：
   - Python→JS 信号能触发 UI 更新
   - JS→Python Slot 能正常调用
   - 加载状态显示/隐藏正常
   - 各模块独立且可测试

全部满足后输出 "阶段2验收通过"。
```

---

## 阶段 3：后端集成与主窗口重构

### 目标
将 WebView 主窗口与现有 InterrogationEngine 集成，替换原生 UI 主窗口，实现完整的加载状态管理和存档选择功能。

### 验收标准
- [ ] WebMainWindow 能加载案件并初始化引擎
- [ ] 所有游戏操作（聊天、施压、共情、出示证据）正常工作
- [ ] 嫌疑人切换正常
- [ ] 倒计时正常运行
- [ ] 结局处理（崩溃/超时）正常
- [ ] 存档/读档功能正常（含存档选择 UI）
- [ ] LLM 调用时显示加载状态
- [ ] LLM 调用超时处理正常
- [ ] 用户可取消长时间操作
- [ ] 现有功能无回归

### Agent 任务分解

#### @test（场景用例设计 → 评审 → 测试开发）

**场景用例设计 Prompt**：
```
为阶段 3（后端集成）设计测试场景用例。

功能模块：WebView 主窗口与引擎集成

需要覆盖的测试场景：

1. 案件加载
   - 场景1：加载案件后嫌疑人列表显示
   - 场景2：加载案件后证据列表显示
   - 场景3：加载案件后倒计时显示
   - 场景4：游戏状态完整初始化

2. 审讯流程
   - 场景5：选择嫌疑人开始审讯
   - 场景6：发送消息并接收回复
   - 场景7：施压操作（压力+10）
   - 场景8：共情操作（压力-5）
   - 场景9：出示相关证据（压力+20）
   - 场景10：出示不相关证据（压力不变）
   - 场景11：嫌疑人切换

3. 游戏状态
   - 场景12：倒计时更新
   - 场景13：倒计时归零触发超时结局
   - 场景14：压力达到100触发崩溃结局
   - 场景15：操作进行中禁止重复操作

4. 加载状态管理（新增）
   - 场景16：LLM 调用时显示加载指示器
   - 场景17：LLM 调用完成后隐藏加载指示器
   - 场景18：LLM 调用超时处理
   - 场景19：用户取消操作

5. 存档/读档
   - 场景20：存档功能
   - 场景21：读档显示存档列表
   - 场景22：选择存档加载
   - 场景23：读档后状态恢复

6. 边界条件
   - 场景24：未加载案件时操作无响应
   - 场景25：空消息不发送
   - 场景26：压力边界（不低于0，不高于100）

输出：场景用例设计文档（含优先级）
```

**测试开发 Prompt**（评审通过后）：
```
为阶段 3 编写验收测试。

1. `tests/test_web_integration.py`：
   - test_load_case：测试加载案件后 UI 更新
   - test_chat_flow：测试完整聊天流程
   - test_pressure_action：测试施压操作
   - test_empathy_action：测试共情操作
   - test_present_evidence：测试出示证据
   - test_suspect_switch：测试嫌疑人切换
   - test_timer_tick：测试倒计时更新
   - test_timeout_ending：测试超时结局
   - test_breakdown_ending：测试崩溃结局
   - test_input_disabled_during_processing：测试操作中禁用输入

2. `tests/test_web_loading_integration.py`（新增）：
   - test_loading_shown_on_llm_call：测试 LLM 调用时显示加载
   - test_loading_hidden_on_complete：测试完成后隐藏加载
   - test_loading_timeout：测试超时处理
   - test_user_cancel_operation：测试用户取消操作

3. `tests/test_web_save_load.py`：
   - test_save_game：测试存档功能
   - test_load_game_shows_list：测试读档显示存档列表
   - test_select_save_to_load：测试选择存档加载
   - test_state_recovery：测试状态恢复正确性

4. `tests/test_web_boundary.py`：
   - test_no_case_no_action：测试无案件时操作无响应
   - test_empty_message_not_sent：测试空消息不发送
   - test_pressure_boundary：测试压力边界

验收命令：`pytest tests/test_web_*.py -v`
```

#### @dev（开发实现）

**开发 Prompt**：
```
实现 WebView 主窗口与 InterrogationEngine 的集成。

1. 更新 `ui/web_bridge.py`，添加存档选择相关信号：
   ```python
   # 新增信号
   show_save_list = Signal(list)  # sessions
   save_selected = Signal(str)    # session_id
   
   @Slot(str)
   def selectSave(self, session_id: str):
       """选择存档"""
       self.save_selected.emit(session_id)
   ```

2. 更新 `ui/web_main_window.py`：
   ```python
   import logging
   import uuid
   from typing import List, Optional
   
   from PySide6.QtCore import QUrl, QTimer, QThread, Signal
   from PySide6.QtWebEngineWidgets import QWebEngineView
   from PySide6.QtWebChannel import QWebChannel
   from PySide6.QtWidgets import QMainWindow, QDialog, QMessageBox
   
   from core import db
   from core.interrogation import InterrogationEngine
   from schemas.events import UIEvent
   from ui.web_bridge import WebBridge
   from ui.resource_helper import get_html_url
   from ui.admin_dialog import AdminDialog
   from ui.settings_dialog import SettingsDialog
   
   logger = logging.getLogger("thebox")
   
   # 配置常量
   LLM_TIMEOUT_SECONDS = 60
   
   
   class WebWorker(QThread):
       """后台线程 Worker，处理可能阻塞的 LLM 调用"""
       finished = Signal(list)
       error = Signal(str)
   
       def __init__(self, engine, action, content, evidence_id=None):
           super().__init__()
           self._engine = engine
           self._action = action
           self._content = content
           self._evidence_id = evidence_id
   
       def run(self):
           try:
               events = self._engine.submit_action(
                   self._action, self._content, evidence_id=self._evidence_id
               )
               self.finished.emit(events)
           except Exception as exc:
               logger.error(f"Worker error: {exc}")
               self.error.emit(str(exc))
   
   
   class WebMainWindow(QMainWindow):
       """基于 WebView 的主窗口"""
   
       def __init__(self, case_data=None):
           super().__init__()
           self.setWindowTitle("The Box: Local Verdict")
           self.resize(1280, 800)
   
           self.engine = None
           self._current_worker = None
           self._timeout_timer = None
           self._progress_timer = None
           self._elapsed_seconds = 0
   
           # 创建 WebView
           self.web_view = QWebEngineView()
   
           # 设置通信通道
           self.bridge = WebBridge()
           self.channel = QWebChannel()
           self.channel.registerObject("bridge", self.bridge)
           self.web_view.page().setWebChannel(self.channel)
   
           # 加载 HTML（使用资源辅助工具）
           self.web_view.setUrl(get_html_url())
   
           # 设置中心部件
           self.setCentralWidget(self.web_view)
   
           # 初始化倒计时
           self._countdown_timer = QTimer(self)
           self._countdown_timer.setInterval(1000)
           self._countdown_timer.timeout.connect(self._on_timer_tick)
   
           # 连接 Bridge 信号
           self._connect_bridge_signals()
   
           # 如果有初始案件数据，加载
           if case_data:
               self.web_view.loadFinished.connect(lambda: self.load_case(case_data))
   
       def _connect_bridge_signals(self):
           """连接 WebBridge 的所有信号"""
           self.bridge.message_sent.connect(self._on_chat_message_sent)
           self.bridge.suspect_selected.connect(self._on_suspect_changed)
           self.bridge.evidence_presented.connect(self._on_evidence_selected)
           self.bridge.pressure_applied.connect(self._on_pressure)
           self.bridge.empathy_applied.connect(self._on_empathy)
           self.bridge.save_requested.connect(self._on_save_game)
           self.bridge.load_requested.connect(self._on_load_game)
           self.bridge.settings_requested.connect(self._on_llm_settings)
           self.bridge.generate_case_requested.connect(self._on_generate_case)
           self.bridge.cancel_requested.connect(self._on_cancel_operation)
           self.bridge.save_selected.connect(self._on_save_selected)
   
       def load_case(self, case_data):
           """加载案件到引擎并更新 UI"""
           self.engine = InterrogationEngine(case_data)
   
           # 构建完整初始状态
           state = {
               "suspects": [{"name": s.name, "pressure": s.pressure} for s in self.engine.suspects],
               "evidences": case_data.get("evidences", []),
               "time_left": self.engine.time_left,
               "current_suspect_index": 0,
           }
   
           # 一次性发送完整状态
           self.bridge.init_game_state.emit(state)
           self.bridge.set_input_enabled.emit(True)
   
           # 如果有嫌疑人，选择第一个
           if self.engine.suspects:
               self._on_suspect_changed(0)
   
       def _on_suspect_changed(self, index):
           """处理嫌疑人切换"""
           if self.engine is None or index < 0:
               return
           
           info = self.engine.select_suspect(index)
           self.bridge.update_suspect.emit(info["name"], info["pressure"])
   
           if self.engine.state == "interrogating":
               self._countdown_timer.start()
   
       def _on_chat_message_sent(self, text):
           """处理用户发送的聊天消息"""
           if self.engine is None:
               return
           self._start_worker("chat", text)
   
       def _on_pressure(self):
           """处理施压操作"""
           if self.engine is None:
               return
           self._start_worker("pressure", "对嫌疑人施压")
   
       def _on_empathy(self):
           """处理共情操作"""
           if self.engine is None:
               return
           self._start_worker("empathy", "对嫌疑人表示共情")
   
       def _on_evidence_selected(self, evidence_id):
           """处理证据出示"""
           if self.engine is None:
               return
           
           # 使用公共 API 获取证据
           evidence = self.engine.get_evidence(evidence_id)
           evidence_name = evidence.get("name", evidence_id) if evidence else evidence_id
           
           self._start_worker("present_evidence", f"出示证据: {evidence_name}", evidence_id=evidence_id)
   
       def _start_worker(self, action, content, evidence_id=None):
           """启动后台 Worker"""
           if self._current_worker and self._current_worker.isRunning():
               logger.warning("上一个操作仍在进行中")
               return
           if self.engine is None:
               return
   
           # 显示加载状态
           self.bridge.show_loading.emit("正在审讯中...", True)
           self.bridge.set_input_enabled.emit(False)
           
           # 重置计时
           self._elapsed_seconds = 0
   
           # 启动超时计时器
           self._timeout_timer = QTimer(self)
           self._timeout_timer.setSingleShot(True)
           self._timeout_timer.timeout.connect(self._on_worker_timeout)
           self._timeout_timer.start(LLM_TIMEOUT_SECONDS * 1000)
           
           # 启动进度更新计时器
           self._progress_timer = QTimer(self)
           self._progress_timer.setInterval(1000)
           self._progress_timer.timeout.connect(self._update_loading_progress)
           self._progress_timer.start()
   
           # 创建并启动 Worker
           self._current_worker = WebWorker(self.engine, action, content, evidence_id)
           self._current_worker.finished.connect(self._on_worker_finished)
           self._current_worker.error.connect(self._on_worker_error)
           self._current_worker.start()
   
       def _update_loading_progress(self):
           """更新加载进度"""
           self._elapsed_seconds += 1
           self.bridge.update_loading_progress.emit(self._elapsed_seconds)
   
       def _on_worker_finished(self, events):
           """Worker 完成，处理事件"""
           self._cleanup_after_worker()
           self.update_ui_from_engine(events)
           self.bridge.hide_loading.emit()
           self.bridge.set_input_enabled.emit(True)
           self._current_worker = None
   
       def _on_worker_error(self, error_msg):
           """Worker 出错"""
           self._cleanup_after_worker()
           logger.error(f"操作失败: {error_msg}")
           self.bridge.hide_loading.emit()
           self.bridge.add_message.emit("system", f"操作失败: {error_msg}", "")
           self.bridge.set_input_enabled.emit(True)
           self._current_worker = None
   
       def _on_worker_timeout(self):
           """Worker 超时"""
           if self._current_worker and self._current_worker.isRunning():
               self._current_worker.terminate()
               self._cleanup_after_worker()
               self.bridge.hide_loading.emit()
               self.bridge.add_message.emit("system", "响应超时，请重试", "")
               self.bridge.set_input_enabled.emit(True)
               self._current_worker = None
   
       def _on_cancel_operation(self):
           """用户取消操作"""
           if self._current_worker and self._current_worker.isRunning():
               self._current_worker.terminate()
               self._cleanup_after_worker()
               self.bridge.hide_loading.emit()
               self.bridge.add_message.emit("system", "操作已取消", "")
               self.bridge.set_input_enabled.emit(True)
               self._current_worker = None
   
       def _cleanup_after_worker(self):
           """清理 Worker 相关资源"""
           if self._timeout_timer:
               self._timeout_timer.stop()
               self._timeout_timer = None
           if self._progress_timer:
               self._progress_timer.stop()
               self._progress_timer = None
   
       def _on_timer_tick(self):
           """倒计时更新"""
           if self.engine is None:
               self._countdown_timer.stop()
               return
           
           events = self.engine.tick(1)
           self.update_ui_from_engine(events)
           
           if self.engine.state not in ("interrogating", "selecting"):
               self._countdown_timer.stop()
   
       def update_ui_from_engine(self, events):
           """处理引擎返回的事件列表，更新 UI"""
           for event in events:
               if event["type"] == "new_message":
                   role = event["role"]
                   content = event["content"]
                   suspect = event.get("suspect_name") or ""
                   self.bridge.add_message.emit(role, content, suspect)
               
               elif event["type"] == "suspect_update":
                   pressure = event["pressure"]
                   if self.engine:
                       suspect = self.engine.suspects[self.engine.current_suspect_index]
                       self.bridge.update_suspect.emit(suspect.name, pressure)
               
               elif event["type"] == "state_change":
                   new_state = event["new_state"]
                   self.bridge.add_message.emit("system", f"[状态变更] {new_state}", "")
                   if new_state in ("verdict", "breakdown"):
                       self._handle_ending(event)
               
               elif event["type"] == "timer_tick":
                   self.bridge.update_timer.emit(event["time_left"])
   
       def _handle_ending(self, state_event):
           """处理游戏结局"""
           self._countdown_timer.stop()
           self.bridge.set_input_enabled.emit(False)
   
           new_state = state_event["new_state"]
           if new_state == "breakdown":
               message = "破案成功！真凶已经崩溃认罪。"
           elif new_state == "verdict":
               message = "时间耗尽！律师介入，案件被迫终止。"
           else:
               message = f"游戏结束: {new_state}"
   
           # 通过 Bridge 显示对话框
           self.bridge.show_dialog.emit("审讯结束", message)
   
       def _on_generate_case(self):
           """打开案件生成对话框"""
           dialog = AdminDialog(self)
           dialog.case_generated.connect(self.load_case)
           dialog.exec()
   
       def _on_llm_settings(self):
           """打开 LLM 设置对话框"""
           dialog = SettingsDialog(self)
           dialog.settings_saved.connect(self._on_settings_saved)
           dialog.exec()
   
       def _on_settings_saved(self):
           """设置保存后重新初始化 LLM"""
           if self.engine and hasattr(self.engine, "suspect_agent"):
               try:
                   self.engine.suspect_agent._ensure_llm_client()
               except Exception as exc:
                   logger.warning(f"Engine reinit: {exc}")
   
       def _on_save_game(self):
           """存档"""
           if self.engine is None:
               return
           try:
               session_id = str(uuid.uuid4())
               case_id = self.engine.case.get("case_id", "unknown")
               engine_state_dict = self.engine.to_dict()
               db.save_full_session(session_id, case_id, engine_state_dict)
               self.bridge.show_dialog.emit("存档成功", f"游戏已保存！\n存档ID: {session_id[:8]}...")
           except Exception as exc:
               logger.error(f"存档失败: {exc}")
               self.bridge.show_dialog.emit("存档失败", f"保存失败: {exc}")
   
       def _on_load_game(self):
           """读档 - 显示存档列表"""
           try:
               sessions = db.list_sessions()
               # 格式化存档列表
               formatted_sessions = [
                   {
                       "session_id": s["session_id"],
                       "case_id": s.get("case_id", "未知案件"),
                       "created_at": s.get("created_at", "")
                   }
                   for s in sessions
               ]
               self.bridge.show_save_list.emit(formatted_sessions)
           except Exception as exc:
               logger.error(f"获取存档列表失败: {exc}")
               self.bridge.show_dialog.emit("读档失败", f"无法读取存档列表: {exc}")
   
       def _on_save_selected(self, session_id):
           """选择存档后加载"""
           try:
               session_data = db.load_full_session(session_id)
               if session_data:
                   self.engine = InterrogationEngine.from_dict(session_data)
                   
                   # 构建完整状态
                   state = {
                       "suspects": [{"name": s.name, "pressure": s.pressure} for s in self.engine.suspects],
                       "evidences": self.engine.case.get("evidences", []),
                       "time_left": self.engine.time_left,
                       "current_suspect_index": self.engine.current_suspect_index,
                   }
                   
                   self.bridge.init_game_state.emit(state)
                   self.bridge.set_input_enabled.emit(True)
                   
                   if self.engine.state == "interrogating":
                       self._countdown_timer.start()
               else:
                   self.bridge.show_dialog.emit("读档失败", "存档数据不存在")
           except Exception as exc:
               logger.error(f"加载存档失败: {exc}")
               self.bridge.show_dialog.emit("读档失败", f"加载失败: {exc}")
   ```

3. 在 `InterrogationEngine` 中添加公共方法（如果不存在）：
   ```python
   def get_evidence(self, evidence_id):
       """获取证据信息（公共 API）"""
       for e in self.case.get("evidences", []):
           if e.get("id") == evidence_id:
               return e
       return None
   ```

4. 修改 `main.py` 使用 WebMainWindow：
   ```python
   import sys
   from PySide6.QtWidgets import QApplication
   from core.db import init_db
   from ui.web_main_window import WebMainWindow
   
   def main():
       init_db()
       app = QApplication(sys.argv)
       window = WebMainWindow()
       window.show()
       sys.exit(app.exec())
   
   if __name__ == "__main__":
       main()
   ```

5. 运行自检清单确认实现质量
```

#### @review（评审验证）

**评审 Prompt**：
```
验证阶段 3 交付物：

1. 运行测试：
   - `pytest tests/test_web_integration.py -v` 全部通过
   - `pytest tests/test_web_loading_integration.py -v` 全部通过
   - `pytest tests/test_web_save_load.py -v` 全部通过
   - `pytest tests/test_web_boundary.py -v` 全部通过
   - `pytest tests/ -m "not slow" -v` 无回归

2. 功能验证：
   - `python main.py` 能启动 WebView 窗口
   - 能加载案件并显示嫌疑人/证据列表
   - 能发送消息并接收回复
   - 施压/共情操作正常
   - 出示证据正常
   - 倒计时正常运行
   - 结局处理正常
   - 加载状态显示正常
   - 超时处理正常
   - 存档/读档功能正常（含存档选择 UI）

3. 代码质量：
   - WebMainWindow 与原 MainWindow 功能一致
   - QThread Worker 模式正确使用
   - 无硬编码 API Key
   - 日志使用 logging.getLogger("thebox")
   - 无访问私有属性

4. 集成检查：
   - InterrogationEngine 逻辑不变
   - AdminDialog 和 SettingsDialog 正常工作
   - 资源路径在开发和打包环境都正确

全部满足后输出 "阶段3验收通过"。
```

---

## 阶段 4：UI 打磨与高级功能

### 目标
完善 UI 细节，添加高级交互功能，优化用户体验。

### 验收标准
- [ ] 自定义模态框替代原生 alert/confirm
- [ ] 消息动画效果流畅
- [ ] 压力条动画平滑
- [ ] 头像切换有过渡效果
- [ ] 响应式布局适配
- [ ] 键盘快捷键支持
- [ ] 无障碍访问支持

### Agent 任务分解

#### @test（场景用例设计 → 评审 → 测试开发）

**场景用例设计 Prompt**：
```
为阶段 4（UI 打磨）设计测试场景用例。

功能模块：高级 UI 功能

需要覆盖的测试场景：

1. 自定义模态框
   - 场景1：确认对话框显示
   - 场景2：确认对话框回调
   - 场景3：信息对话框显示
   - 场景4：对话框关闭方式（按钮/ESC/点击遮罩）

2. 动画效果
   - 场景5：消息淡入动画
   - 场景6：压力条过渡动画
   - 场景7：头像切换动画
   - 场景8：按钮悬停动画

3. 响应式布局
   - 场景9：窗口尺寸变化布局自适应
   - 场景10：最小窗口尺寸限制

4. 键盘交互
   - 场景11：ESC 关闭对话框
   - 场景12：Enter 发送消息
   - 场景13：Tab 焦点切换

5. 无障碍
   - 场景14：屏幕阅读器支持
   - 场景15：高对比度模式

输出：场景用例设计文档
```

**测试开发 Prompt**（评审通过后）：
```
为阶段 4 编写验收测试。

1. `tests/test_web_modals.py`：
   - test_confirm_dialog_display：测试确认对话框显示
   - test_confirm_dialog_callback：测试确认对话框回调
   - test_info_dialog_display：测试信息对话框显示
   - test_dialog_close_methods：测试对话框关闭方式

2. `tests/test_web_animations.py`：
   - test_message_fade_in：测试消息淡入动画
   - test_pressure_bar_animation：测试压力条动画
   - test_avatar_transition：测试头像切换动画

3. `tests/test_web_responsive.py`：
   - test_window_resize：测试窗口尺寸变化
   - test_minimum_size：测试最小尺寸限制

4. `tests/test_web_keyboard.py`：
   - test_esc_close_dialog：测试 ESC 关闭对话框
   - test_enter_send_message：测试 Enter 发送消息

验收命令：`pytest tests/test_web_*.py -v`
```

#### @ui（UI 设计与实现）

**UI 设计 Prompt**：
```
设计并实现高级 UI 功能。

1. 自定义模态框组件：
   - 确认对话框（确认/取消）
   - 信息对话框（确定）
   - 警告对话框（带图标）
   - 支持 ESC 关闭
   - 支持点击遮罩关闭
   - 淡入淡出动画

2. 高级动画效果：
   - 消息淡入上移
   - 压力条平滑过渡
   - 头像切换过渡
   - 按钮悬停光晕
   - 卡片悬停上浮

3. 响应式优化：
   - 断点设计（1280px, 1024px, 768px）
   - 侧边栏折叠
   - 字体大小自适应

4. 键盘快捷键：
   - Enter 发送消息
   - ESC 关闭对话框
   - Ctrl+S 存档
   - Ctrl+L 读档

5. 无障碍支持：
   - ARIA 标签
   - 焦点管理
   - 高对比度模式

输出文件：
- `ui/web/css/components.css` - 组件样式
- `ui/web/js/modal.js` - 模态框模块（已在阶段2实现）
- `ui/web/js/keyboard.js` - 键盘快捷键模块
```

#### @dev（集成实现）

**开发 Prompt**：
```
集成 @ui 交付的高级功能。

1. 创建 `ui/web/js/keyboard.js`：
   - 实现键盘快捷键管理
   - 绑定常用快捷键

2. 更新 `ui/web/js/app.js`：
   - 初始化键盘快捷键
   - 替换所有原生对话框调用

3. 更新 CSS 添加动画效果

4. 测试所有高级功能
```

#### @review（评审验证）

**评审 Prompt**：
```
验证阶段 4 交付物：

1. 运行测试：
   - `pytest tests/test_web_modals.py -v` 全部通过
   - `pytest tests/test_web_animations.py -v` 全部通过
   - `pytest tests/test_web_responsive.py -v` 全部通过
   - `pytest tests/test_web_keyboard.py -v` 全部通过

2. 视觉验证：
   - 自定义模态框美观且功能正常
   - 动画效果流畅不卡顿
   - 响应式布局正确
   - 暗黑科技风格一致

3. 交互验证：
   - 键盘快捷键正常工作
   - 无障碍功能正常
   - 无原生 alert/confirm 调用

4. 性能验证：
   - 动画帧率 ≥ 30fps
   - 内存占用合理
   - 无内存泄漏

全部满足后输出 "阶段4验收通过"。
```

---

## 阶段 5：端到端测试与打包

### 目标
完成端到端测试，打包为可执行文件，编写用户文档。

### 验收标准
- [ ] 端到端测试全部通过
- [ ] PyInstaller 打包成功
- [ ] 打包后程序能正常运行
- [ ] 用户文档完整

### Agent 任务分解

#### @test（场景用例设计 → 评审 → 测试开发）

**场景用例设计 Prompt**：
```
为阶段 5（端到端测试）设计测试场景用例。

功能模块：端到端验收

需要覆盖的测试场景：

1. 完整游戏流程
   - 场景1：生成案件 → 选择嫌疑人 → 审讯 → 破案成功
   - 场景2：生成案件 → 审讯 → 超时失败
   - 场景3：生成案件 → 存档 → 读档 → 继续审讯

2. 多嫌疑人流程
   - 场景4：切换多个嫌疑人审讯
   - 场景5：对不同嫌疑人出示不同证据

3. 边界条件
   - 场景6：压力边界测试
   - 场景7：倒计时精度测试
   - 场景8：并发操作测试

4. 错误处理
   - 场景9：网络异常处理
   - 场景10：LLM 响应异常处理
   - 场景11：LLM 调用超时处理

5. 打包验证
   - 场景12：打包后程序启动
   - 场景13：打包后资源加载
   - 场景14：打包后功能完整

输出：场景用例设计文档
```

**测试开发 Prompt**（评审通过后）：
```
为阶段 5 编写端到端测试。

1. `tests/test_e2e_web.py`：
   - test_full_game_success：完整游戏流程（成功破案）
   - test_full_game_timeout：完整游戏流程（超时失败）
   - test_save_load_recovery：存档读档恢复
   - test_multi_suspect：多嫌疑人审讯
   - test_evidence_presentation：出示证据流程
   - test_pressure_boundary：压力边界测试
   - test_timer_precision：倒计时精度测试
   - test_llm_timeout_handling：LLM 超时处理

2. 性能测试：
   - test_response_time：响应时间测试
   - test_memory_usage：内存使用测试

验收命令：`pytest tests/test_e2e_web.py -v -m slow`
```

#### @dev（打包与文档）

**开发 Prompt**：
```
完成打包和文档编写。

1. 更新 `build_web.spec`（PyInstaller）：
   ```python
   # -*- mode: python ; coding: utf-8 -*-
   
   block_cipher = None
   
   a = Analysis(
       ['main.py'],
       pathex=[],
       binaries=[],
       datas=[
           ('assets', 'assets'),
       ],
       hiddenimports=[
           'PySide6.QtWebEngineWidgets',
           'PySide6.QtWebChannel',
       ],
       hookspath=[],
       hooksconfig={},
       runtime_hooks=[],
       excludes=[],
       win_no_prefer_redirects=False,
       win_private_assemblies=False,
       cipher=block_cipher,
       noarchive=False,
   )
   
   # 编译资源文件
   from PySide6.scripts import uic
   import os
   os.system('pyside6-rcc resources.qrc -o resources_rc.py')
   
   pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
   
   exe = EXE(
       pyz,
       a.scripts,
       a.binaries,
       a.zipfiles,
       a.datas,
       [],
       name='TheBox',
       debug=False,
       bootloader_ignore_signals=False,
       strip=False,
       upx=True,
       upx_exclude=[],
       runtime_tmpdir=None,
       console=False,
       disable_windowed_traceback=False,
       argv_emulation=False,
       target_arch=None,
       codesign_identity=None,
       entitlements_file=None,
       icon='assets/icons/icon.ico',
   )
   ```

2. 编写 `docs/USER_GUIDE.md`：
   - 安装说明
   - API Key 配置
   - 游戏操作说明
   - 常见问题解答

3. 测试打包：
   - 运行 `pyinstaller build_web.spec`
   - 测试打包后的程序

4. 更新 README.md
```

#### @review（最终评审）

**评审 Prompt**：
```
最终验收：

1. 运行完整测试套件：
   - `pytest tests/ -m "not slow" --cov=core --cov=ui --cov-report=html` 全部通过
   - `pytest tests/test_e2e_web.py -v -m slow` 端到端测试通过

2. 打包验证：
   - `pyinstaller build_web.spec` 成功
   - 打包后的程序能正常启动
   - 打包后的程序能正常运行游戏
   - 打包后资源加载正常

3. 文档验证：
   - README.md 包含安装说明
   - USER_GUIDE.md 内容完整

4. 代码质量：
   - `flake8 core ui --max-line-length=120` 无报错
   - 无硬编码 API Key
   - 无安全漏洞

5. 性能验证：
   - 程序启动时间 < 3 秒
   - 操作响应时间 < 1 秒
   - 内存占用 < 500MB

全部满足后输出 "项目验收完成，可交付"。
```

---

## 问题修复与方案补充

### 严重问题 (会导致功能失败)

#### 问题 1：worker.terminate() 不安全
- **位置**: `_on_worker_timeout()` (1730行), `_on_cancel_operation()` (1740行)
- **问题**: `terminate()` 强制终止线程，不执行 `finished` 信号，导致 `_cleanup_after_worker()` 不被调用，QTimer 泄漏
- **修复方案**:
```python
# 方案 A：使用中断标志位
class WebWorker(QThread):
    def __init__(self, engine, action, content, evidence_id=None):
        super().__init__()
        self._engine = engine
        self._action = action
        self._content = content
        self._evidence_id = evidence_id
        self._interrupted = False

    def interrupt(self):
        self._interrupted = True

    def run(self):
        try:
            events = self._engine.submit_action(
                self._action, self._content, evidence_id=self._evidence_id
            )
            if not self._interrupted:
                self.finished.emit(events)
        except Exception as exc:
            if not self._interrupted:
                self.error.emit(str(exc))

# 方案 B：使用 requestInterruption (Qt 5.10+)
def _on_cancel_operation(self):
    if self._current_worker and self._current_worker.isRunning():
        self._current_worker.requestInterruption()
        self._current_worker.wait(1000)  # 等待最多1秒
        self._cleanup_after_worker()
        self.bridge.hide_loading.emit()
        self.bridge.add_message.emit("system", "操作已取消", "")
        self.bridge.set_input_enabled.emit(True)
        self._current_worker = None
```

#### 问题 2：modal.js 调用方式错误
- **位置**: 1168行
- **问题**: `window.bridge.pythonBridge.selectSave()` 不存在，`pythonBridge` 不是 bridge 的属性
- **修复方案**:
```javascript
// 在 bridge.js 中添加 selectSave 方法
selectSave(sessionId) {
    if (this.pythonBridge) {
        this.pythonBridge.selectSave(sessionId);
    }
}

// 在 modal.js 中调用
showSaveList(sessions) {
    // ... 生成存档列表 HTML ...
    document.querySelectorAll('.save-item').forEach((item, index) => {
        item.addEventListener('click', () => {
            this.hide();
            window.bridge.selectSave(sessions[index].session_id);  // 修复调用方式
        });
    });
}
```

#### 问题 3：状态初始化数据不完整
- **位置**: 1617-1622行 `load_case()`
- **问题**: `init_game_state` 缺少审讯状态、案件ID 等信息，存档恢复不完整
- **修复方案**:
```python
def load_case(self, case_data):
    self.engine = InterrogationEngine(case_data)

    state = {
        "suspects": [{"name": s.name, "pressure": s.pressure} for s in self.engine.suspects],
        "evidences": case_data.get("evidences", []),
        "time_left": self.engine.time_left,
        "current_suspect_index": self.engine.current_suspect_index,
        "state": self.engine.state,  # 新增：审讯状态
        "case_id": case_data.get("case_id"),  # 新增：案件ID
    }

    self.bridge.init_game_state.emit(state)
    self.bridge.set_input_enabled.emit(True)

    if self.engine.suspects:
        self._on_suspect_changed(0)
```

#### 问题 4：访问私有属性
- **位置**: 1824行
- **问题**: 访问 `self.engine.suspect_agent._ensure_llm_client()` 违反"后端逻辑不变"原则
- **修复方案**:
```python
# 方案 A：通过公共事件机制
class InterrogationEngine:
    def reinitialize_llm(self):
        """公共方法：重新初始化 LLM"""
        self.suspect_agent._ensure_llm_client()

# 方案 B：通过信号机制重初始化
def _on_settings_saved(self):
    # 发送信号通知引擎重初始化
    self.engine.settings_updated.emit()
    # 或直接调用公共方法
    if hasattr(self.engine, 'reinitialize_llm'):
        self.engine.reinitialize_llm()
```

#### 问题 5：QTimer 线程安全
- **位置**: `_start_worker` 中创建的 QTimer
- **问题**: QTimer 在非主线程创建会导致 `QObject: Cannot create children for a parent in a different thread`
- **修复方案**:
```python
def _start_worker(self, action, content, evidence_id=None):
    if self._current_worker and self._current_worker.isRunning():
        logger.warning("上一个操作仍在进行中")
        return
    if self.engine is None:
        return

    self.bridge.show_loading.emit("正在审讯中...", True)
    self.bridge.set_input_enabled.emit(False)
    self._elapsed_seconds = 0

    # 使用 QTimer.singleShot 替代在 Worker 中创建定时器
    self._timeout_timer = QTimer(self)
    self._timeout_timer.setSingleShot(True)
    self._timeout_timer.timeout.connect(self._on_worker_timeout)
    self._timeout_timer.start(LLM_TIMEOUT_SECONDS * 1000)

    self._progress_timer = QTimer(self)
    self._progress_timer.setInterval(1000)
    self._progress_timer.timeout.connect(self._update_loading_progress)
    self._progress_timer.start()

    self._current_worker = WebWorker(self.engine, action, content, evidence_id)
    self._current_worker.finished.connect(self._on_worker_finished)
    self._current_worker.error.connect(self._on_worker_error)
    self._current_worker.start()
```

---

### 中等问题 (可能导致运行时问题)

#### 问题 6：存档列表数据结构假设
- **位置**: 1847-1853行 `_on_load_game()`
- **问题**: 假设 `db.list_sessions()` 返回固定结构，未做防御性处理
- **修复方案**:
```python
def _on_load_game(self):
    try:
        sessions = db.list_sessions()
        formatted_sessions = []
        for s in sessions:
            try:
                formatted_sessions.append({
                    "session_id": s.get("session_id", ""),
                    "case_id": s.get("case_id", "未知案件"),
                    "created_at": s.get("created_at", "")
                })
            except Exception:
                logger.warning(f"存档数据格式异常: {s}")
                continue
        self.bridge.show_save_list.emit(formatted_sessions)
    except Exception as exc:
        logger.error(f"获取存档列表失败: {exc}")
        self.bridge.show_dialog.emit("读档失败", f"无法读取存档列表: {exc}")
```

#### 问题 7：前端 HTML 元素假设
- **位置**: `LoadingManager`, `ModalManager` 构造函数
- **问题**: 假设 DOM 元素必须存在，否则 JavaScript 报错
- **修复方案**:
```javascript
class LoadingManager {
    constructor() {
        this.overlay = document.getElementById('loading-overlay');
        this.messageEl = document.getElementById('loading-message');
        this.progressEl = document.getElementById('loading-progress');
        this.cancelBtn = document.getElementById('loading-cancel');
        this.isVisible = false;
        this._setupEventListeners();
    }

    _setupEventListeners() {
        if (this.cancelBtn) {
            this.cancelBtn.addEventListener('click', () => {
                if (window.bridge) {
                    window.bridge.cancelOperation();
                }
                this.hide();
            });
        }
    }

    show(message, cancellable = true) {
        if (!this.overlay) {
            console.warn('Loading overlay not found');
            return;
        }
        // ... 后续代码 ...
    }
}
```

#### 问题 8：Worker 错误后状态不一致
- **位置**: `_on_worker_error()` (1718行)
- **问题**: 错误后 UI 重置但引擎状态可能已部分修改
- **修复方案**:
```python
def _on_worker_error(self, error_msg):
    self._cleanup_after_worker()
    logger.error(f"操作失败: {error_msg}")
    self.bridge.hide_loading.emit()
    self.bridge.add_message.emit("system", f"操作失败: {error_msg}", "")
    self.bridge.set_input_enabled.emit(True)
    self._current_worker = None

    # 同步引擎状态到 UI
    if self.engine:
        events = self.engine.get_current_state()
        self.update_ui_from_engine(events)
```

#### 问题 9：阶段1视觉验证不可执行
- **位置**: 687行
- **问题**: CLI 环境下无法截图验证
- **修复方案**:
```python
# 更新验收标准
# 原：视觉验证（通过截图或描述）
# 改：使用 pytest-screenshot 进行自动化截图对比，或添加人工验收步骤

# 在 test_web_structure.py 中添加截图测试
def test_visual_dark_theme(app, selenium):
    """验证暗黑科技风格视觉效果"""
    app.load_web_ui()
    screenshot = selenium.find_element('.panel-center').screenshot_as_png
    # 与基准截图对比，或保存供人工验收
    with open('tests/screenshots/baseline.png', 'rb') as f:
        baseline = f.read()
    # 允许一定差异（颜色压缩等）
    assert compare_images(screenshot, baseline, tolerance=0.1), "视觉风格与基准不一致"
```

---

### 轻微问题 (代码质量/文档)

#### 问题 10：风险缓解措施不具体
- **位置**: 风险表 "内存占用过高" 行
- **修复方案**: 更新风险表
```
| 内存占用过高 | 性能下降 | 1. WebView 内存限制：self.web_view.settings().setAttribute(QtWebEngineWidgets.QWebEngineSettings.LocalStorageLimit, 50 * 1024 * 1024)
|              |         | 2. HTML 资源懒加载：证据卡片使用时再加载完整内容
|              |         | 3. 及时释放：对话历史超过100条时清理早期消息 DOM
|              |         | 4. 定期 gc.collect()：在后台任务结束时显式垃圾回收
```

#### 问题 11：缺少原有测试验证
- **位置**: 阶段0验收标准
- **修复方案**: 添加原有测试验证
```python
# 阶段0验收命令更新
验收命令：`pytest tests/test_web_channel.py tests/test_web_init.py tests/test_resource_helper.py tests/test_main_window.py -v`
```

#### 问题 12：PyInstaller spec 配置不完整
- **位置**: 2259行 `runtime_tmpdir=None`
- **修复方案**:
```python
import tempfile
import sys

exe = EXE(
    # ... 其他参数 ...
    runtime_tmpdir=tempfile.gettempdir() if hasattr(sys, 'frozen') else None,
    # 或指定应用程序数据目录
    # runtime_tmpdir=QStandardPaths.writableLocation(QStandardPaths.AppDataLocation),
)
```

---

## 跨阶段通用验收脚本

```bash
# run_all_checks_web.sh

# 设置 PYTHONPATH
export PYTHONPATH=$(pwd)

# 安装依赖
uv pip install -r requirements.txt

# 编译资源文件
pyside6-rcc resources.qrc -o resources_rc.py

# 运行所有非慢速测试
pytest tests/ -m "not slow" --cov=core --cov=ui --cov-report=html

# 运行 flake8
flake8 core ui --max-line-length=120

# 检查数据库初始化
python -c "from core.db import init_db; init_db(); print('DB OK')"

# 检查 WebMainWindow 导入
python -c "from ui.web_main_window import WebMainWindow; print('WebMainWindow OK')"

# 检查资源辅助工具
python -c "from ui.resource_helper import get_html_url; print('ResourceHelper OK')"

# 检查前端资源
ls -la ui/web/index.html
ls -la ui/web/css/
ls -la ui/web/js/
```

---

## 风险与缓解措施

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| QWebEngineView 初始化慢 | 用户体验差 | 延迟加载，显示启动画面 |
| QWebChannel 通信延迟 | 操作响应慢 | 异步通信，加载状态提示 |
| 前端资源加载失败 | UI 显示异常 | 资源路径检查，使用 Qt 资源系统 |
| 跨平台兼容性 | 部分平台异常 | 平台特定代码，充分测试 |
| 内存占用过高 | 性能下降 | 资源懒加载，及时释放 |
| 打包体积过大 | 分发困难 | 使用 Qt 资源系统，精简依赖 |
| LLM 调用超时 | 用户感知卡顿 | 加载指示器 + 超时处理 + 取消操作 |
| Bridge 初始化失败 | 程序无法使用 | 重试机制 + 错误提示 |

---

## 总结

本文档提供了从阶段 0 到阶段 5 的完整 WebView UI 重构方案。每个阶段都有明确的目标、验收标准和 Agent 任务分解。通过测试驱动开发和多 Agent 协作，确保重构过程可控、质量可靠。

**关键里程碑**：
- 阶段 0：环境准备（1天）
- 阶段 1：UI 框架（2天）
- 阶段 2：通信层（2天）
- 阶段 3：后端集成（3天）
- 阶段 4：UI 打磨（2天）
- 阶段 5：测试打包（2天）

**总预计工期**：12个工作日

**关键改进点**：
1. 资源路径管理：使用 Qt 资源系统解决打包后路径问题
2. 加载状态管理：加载指示器 + 超时处理 + 取消操作
3. 状态同步机制：统一的游戏状态初始化信号
4. 存档选择 UI：前端模态框实现存档列表选择
5. Bridge 重试机制：初始化失败自动重试
6. 公共 API：避免访问私有属性
