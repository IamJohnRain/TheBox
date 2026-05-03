# BUG-3: 日志查询页面 + 启动参数日志级别 — 优化方案

> 优先级: **P2** (新功能增强)  
> 影响范围: 前端 JS + 后端 Python  
> 可并行: **否** — 依赖 BUG-2 的日志框架就绪  
> 负责 Agent: Agent-B (BUG-2 完成后)

---

## 1. 问题描述

1. 用户无法在界面上查看操作日志，只能查看 `logs/thebox.log` 文件
2. 日志级别无法通过启动参数动态设置，当前硬编码为 INFO
3. 缺少一个可视化的日志查询界面

## 2. 需求分析

### 2.1 启动参数

- 支持 `--log-level` 参数设置日志级别
- 默认值为 `INFO`
- 可选值：`DEBUG`, `INFO`, `WARNING`, `ERROR`
- 需兼容 Qt 的命令行参数（使用 `parse_known_args`）

### 2.2 日志查询页面

- 在 Web UI 中新增日志查看面板
- 支持按级别过滤（ALL / DEBUG / INFO / WARNING / ERROR）
- 实时推送新日志（通过 WebBridge 信号）
- 支持自动滚动到底部
- 支持清空显示
- 支持暂停/恢复自动滚动
- 不同级别用不同颜色标识

---

## 3. 详细优化方案

### 3.1 Step 1: 启动参数支持日志级别

**文件**: `main.py`

**修改后**：

```python
import argparse
import sys
import logging

from PySide6.QtWidgets import QApplication

from core.db import init_db
from core.logger import setup_logger
from ui.web_main_window import WebMainWindow


def main():
    # 先解析自定义参数（避免与 Qt 参数冲突）
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="设置日志级别 (默认: INFO)",
    )
    args, remaining = parser.parse_known_args()

    # 根据参数设置日志级别
    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    setup_logger(level=log_level)

    init_db()

    # 将剩余参数传给 QApplication
    sys.argv = [sys.argv[0]] + remaining
    app = QApplication(sys.argv)
    window = WebMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

**使用方式**：
```bash
python main.py --log-level DEBUG
python main.py --log-level WARNING
python main.py                    # 默认 INFO
```

### 3.2 Step 2: 修改 `setup_logger()` 接受 level 参数

**文件**: `core/logger.py`

**修改后**：

```python
import logging
import logging.handlers
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "thebox.log"


def setup_logger(level=logging.INFO):
    logger = logging.getLogger("thebox")
    logger.setLevel(level)

    if not logger.handlers:
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s"
            )
        )
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
        )
        logger.addHandler(console_handler)

    # 更新已有 handler 的级别
    for handler in logger.handlers:
        handler.setLevel(level)

    return logger


logger = setup_logger()
```

### 3.3 Step 3: 新增 WebBridgeLogHandler

**新文件**: `core/log_handler.py`

```python
"""自定义日志 Handler，将日志通过 WebBridge 推送到前端。"""

import logging
import logging.handlers
from typing import Optional, Callable


class WebBridgeLogHandler(logging.Handler):
    """将日志记录通过回调函数推送到 Web 前端。

    使用回调而非直接引用 WebBridge，避免循环依赖。
    """

    def __init__(self, callback: Optional[Callable[[str, str], None]] = None):
        super().__init__()
        self._callback = callback
        self._throttle_count = 0
        self._throttle_limit = 10  # 每秒最多推送 10 条
        self._last_second = 0

    def set_callback(self, callback: Callable[[str, str], None]):
        """设置日志推送回调。"""
        self._callback = callback

    def emit(self, record: logging.LogRecord):
        if self._callback is None:
            return

        try:
            msg = self.format(record)
            level = record.levelname

            import time
            current_second = int(time.time())
            if current_second != self._last_second:
                self._throttle_count = 0
                self._last_second = current_second

            self._throttle_count += 1
            if self._throttle_count > self._throttle_limit:
                if self._throttle_count == self._throttle_limit + 1:
                    self._callback("WARNING", f"[... 已节流，本秒日志过多 ...]")
                return

            self._callback(level, msg)
        except Exception:
            self.handleError(record)
```

### 3.4 Step 4: 在 WebMainWindow 中注册 LogHandler

**文件**: `ui/web_main_window.py` — `__init__()` 中新增

```python
from core.log_handler import WebBridgeLogHandler

class WebMainWindow(QMainWindow):
    def __init__(self, case_data=None):
        super().__init__()
        # ... 现有初始化 ...

        # 注册日志推送 Handler
        self._log_handler = WebBridgeLogHandler()
        self._log_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
        )
        self._log_handler.setLevel(logging.DEBUG)
        self._log_handler.set_callback(self._on_log_message)
        logging.getLogger("thebox").addHandler(self._log_handler)

    def _on_log_message(self, level: str, message: str):
        """日志推送回调，通过 WebBridge 发送到前端。"""
        self.bridge.log_message.emit(level, message)
```

### 3.5 Step 5: 新增 WebBridge 信号

**文件**: `ui/web_bridge.py`

```python
# === Python → JS 信号 === 部分
log_message = Signal(str, str)  # level, message
```

### 3.6 Step 6: 前端日志查看器

**新文件**: `ui/web/js/log-viewer.js`

```javascript
/**
 * @fileoverview 日志查看器模块。
 *
 * 管理日志面板的显示、过滤、自动滚动等功能。
 */
class LogViewer {
    constructor() {
        this.panel = document.getElementById('log-panel');
        this.toggleBtn = document.getElementById('log-toggle-btn');
        this.logList = document.getElementById('log-list');
        this.filterBtns = document.querySelectorAll('.log-filter-btn');
        this.clearBtn = document.getElementById('log-clear-btn');
        this.scrollBtn = document.getElementById('log-scroll-btn');

        this._logs = [];
        this._currentFilter = 'ALL';
        this._autoScroll = true;
        this._maxLogs = 1000;  // 最大保留日志条数
        this._isExpanded = false;

        this._bindEvents();
    }

    _bindEvents() {
        // 折叠/展开按钮
        if (this.toggleBtn) {
            this.toggleBtn.addEventListener('click', () => this.toggle());
        }

        // 级别过滤按钮
        this.filterBtns.forEach((btn) => {
            btn.addEventListener('click', () => {
                this.filterBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this._currentFilter = btn.getAttribute('data-level') || 'ALL';
                this._renderLogs();
            });
        });

        // 清空按钮
        if (this.clearBtn) {
            this.clearBtn.addEventListener('click', () => this.clear());
        }

        // 滚动到底部按钮
        if (this.scrollBtn) {
            this.scrollBtn.addEventListener('click', () => {
                this._autoScroll = true;
                this._scrollToBottom();
            });
        }

        // 监听滚动，判断是否在底部
        if (this.logList) {
            this.logList.addEventListener('scroll', () => {
                const isAtBottom = this.logList.scrollHeight - this.logList.scrollTop <= this.logList.clientHeight + 30;
                this._autoScroll = isAtBottom;
                if (this.scrollBtn) {
                    this.scrollBtn.style.display = isAtBottom ? 'none' : 'flex';
                }
            });
        }
    }

    toggle() {
        this._isExpanded = !this._isExpanded;
        if (this.panel) {
            this.panel.classList.toggle('expanded', this._isExpanded);
        }
        if (this.toggleBtn) {
            this.toggleBtn.textContent = this._isExpanded ? '▼ 日志' : '▲ 日志';
        }
    }

    addLog(level, message) {
        const timestamp = new Date().toLocaleTimeString('zh-CN', {
            hour: '2-digit', minute: '2-digit', second: '2-digit'
        });

        this._logs.push({ level, message, timestamp });

        // 限制最大条数
        if (this._logs.length > this._maxLogs) {
            this._logs = this._logs.slice(-this._maxLogs);
        }

        // 如果当前过滤允许显示，则添加到 DOM
        if (this._shouldShow(level)) {
            this._appendLogEntry({ level, message, timestamp });
        }

        // 更新摘要
        this._updateSummary(level);
    }

    _shouldShow(level) {
        if (this._currentFilter === 'ALL') return true;
        const levelOrder = ['DEBUG', 'INFO', 'WARNING', 'ERROR'];
        const currentIdx = levelOrder.indexOf(this._currentFilter);
        const logIdx = levelOrder.indexOf(level);
        return logIdx >= currentIdx;
    }

    _appendLogEntry(log) {
        if (!this.logList) return;

        const entry = document.createElement('div');
        entry.className = `log-entry log-${log.level.toLowerCase()}`;
        entry.innerHTML = `
            <span class="log-timestamp">${log.timestamp}</span>
            <span class="log-level log-level-${log.level.toLowerCase()}">${log.level}</span>
            <span class="log-message">${this._escapeHtml(log.message)}</span>
        `;
        this.logList.appendChild(entry);

        if (this._autoScroll) {
            this._scrollToBottom();
        }

        // 限制 DOM 中最大条目数
        while (this.logList.children.length > this._maxLogs) {
            this.logList.removeChild(this.logList.firstChild);
        }
    }

    _renderLogs() {
        if (!this.logList) return;
        this.logList.innerHTML = '';
        this._logs.forEach((log) => {
            if (this._shouldShow(log.level)) {
                this._appendLogEntry(log);
            }
        });
    }

    clear() {
        this._logs = [];
        if (this.logList) {
            this.logList.innerHTML = '';
        }
    }

    _scrollToBottom() {
        if (this.logList) {
            requestAnimationFrame(() => {
                this.logList.scrollTop = this.logList.scrollHeight;
            });
        }
    }

    _updateSummary(level) {
        const summary = document.getElementById('log-summary');
        if (summary) {
            const levelClass = `log-level-${level.toLowerCase()}`;
            summary.className = `log-summary ${levelClass}`;
            summary.textContent = `[${level}] ${this._logs[this._logs.length - 1]?.message?.substring(0, 60) || ''}`;
        }
    }

    _escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}
```

### 3.7 Step 7: HTML 中增加日志面板

**文件**: `ui/web/index.html` — 在 `</main>` 之后、`loading-overlay` 之前新增

```html
<!-- ============================================================
     Log Panel (Bottom)
     ============================================================ -->
<div class="log-panel" id="log-panel">
    <div class="log-panel-header">
        <button class="log-toggle-btn" id="log-toggle-btn">▲ 日志</button>
        <span class="log-summary" id="log-summary"></span>
        <div class="log-panel-controls" id="log-panel-controls" style="display: none;">
            <div class="log-filter-group">
                <button class="log-filter-btn active" data-level="ALL">全部</button>
                <button class="log-filter-btn" data-level="DEBUG">DEBUG</button>
                <button class="log-filter-btn" data-level="INFO">INFO</button>
                <button class="log-filter-btn" data-level="WARNING">WARN</button>
                <button class="log-filter-btn" data-level="ERROR">ERROR</button>
            </div>
            <button class="log-action-btn" id="log-clear-btn">清空</button>
            <button class="log-action-btn log-scroll-btn" id="log-scroll-btn" style="display: none;">↓ 底部</button>
        </div>
    </div>
    <div class="log-list" id="log-list"></div>
</div>
```

### 3.8 Step 8: 日志面板样式

**新文件**: `ui/web/css/log-viewer.css`

```css
/* Log Panel - Bottom Collapsible */
.log-panel {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 32px;
    background: var(--color-bg-secondary);
    border-top: 1px solid rgba(0, 245, 255, 0.1);
    z-index: var(--z-sticky);
    transition: height 0.3s ease;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.log-panel.expanded {
    height: 240px;
}

.log-panel-header {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: 0 var(--space-4);
    height: 32px;
    flex-shrink: 0;
    border-bottom: 1px solid rgba(0, 245, 255, 0.05);
}

.log-toggle-btn {
    background: none;
    border: none;
    color: var(--color-text-secondary);
    font-size: var(--font-size-xs);
    cursor: pointer;
    padding: var(--space-1) var(--space-2);
    font-family: var(--font-mono);
    white-space: nowrap;
}

.log-toggle-btn:hover {
    color: var(--color-accent-cyan);
}

.log-summary {
    flex: 1;
    font-size: var(--font-size-xs);
    font-family: var(--font-mono);
    color: var(--color-text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.log-panel-controls {
    display: flex;
    align-items: center;
    gap: var(--space-2);
}

.log-panel.expanded .log-panel-controls {
    display: flex;
}

.log-filter-group {
    display: flex;
    gap: 2px;
    background: var(--color-bg-primary);
    border-radius: var(--layout-border-radius-sm);
    padding: 2px;
}

.log-filter-btn {
    padding: 2px 8px;
    font-size: 10px;
    font-family: var(--font-mono);
    border: none;
    background: transparent;
    color: var(--color-text-muted);
    cursor: pointer;
    border-radius: 3px;
    transition: all var(--transition-fast);
}

.log-filter-btn.active {
    background: var(--color-accent-cyan);
    color: var(--color-bg-primary);
}

.log-filter-btn:hover:not(.active) {
    color: var(--color-text-primary);
}

.log-action-btn {
    padding: 2px 8px;
    font-size: 10px;
    font-family: var(--font-mono);
    border: 1px solid rgba(0, 245, 255, 0.2);
    background: transparent;
    color: var(--color-text-muted);
    cursor: pointer;
    border-radius: 3px;
}

.log-action-btn:hover {
    border-color: var(--color-accent-cyan);
    color: var(--color-accent-cyan);
}

/* Log List */
.log-list {
    flex: 1;
    overflow-y: auto;
    padding: var(--space-2);
    font-family: var(--font-mono);
    font-size: 11px;
    line-height: 1.6;
}

.log-entry {
    display: flex;
    gap: var(--space-2);
    padding: 1px var(--space-2);
    border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}

.log-entry:hover {
    background: rgba(255, 255, 255, 0.03);
}

.log-timestamp {
    color: var(--color-text-muted);
    flex-shrink: 0;
}

.log-level {
    flex-shrink: 0;
    font-weight: var(--font-weight-semibold);
    min-width: 50px;
}

.log-level-debug { color: var(--color-text-muted); }
.log-level-info { color: var(--color-accent-cyan-dim); }
.log-level-warning { color: var(--color-warning); }
.log-level-error { color: var(--color-danger); }

.log-message {
    color: var(--color-text-secondary);
    word-break: break-all;
}

.log-summary.log-level-debug { color: var(--color-text-muted); }
.log-summary.log-level-info { color: var(--color-accent-cyan-dim); }
.log-summary.log-level-warning { color: var(--color-warning); }
.log-summary.log-level-error { color: var(--color-danger); }
```

### 3.9 Step 9: 集成到 app.js

**文件**: `ui/web/js/app.js`

```javascript
// initModules() 中新增
let logViewer;

function initModules() {
    // ... 现有模块 ...
    logViewer = new LogViewer();
    window.logViewer = logViewer;
}

// bindBridgeEvents() 中新增
bridge.on('logMessage', (data) => {
    if (!data) return;
    logViewer.addLog(data.level, data.message);
});
```

**文件**: `ui/web/js/bridge.js` — `_setupSignalListeners()` 中新增

```javascript
this.pythonBridge.log_message.connect((level, message) => {
    this._trigger('logMessage', { level, message });
});
```

**文件**: `ui/web/index.html` — 在 CSS 和 JS 引用中新增

```html
<link rel="stylesheet" href="css/log-viewer.css">
<!-- ... -->
<script src="js/log-viewer.js"></script>
```

---

## 4. 验收测试

**测试文件**: `tests/test_fix_log_viewer.py`

### 4.1 单元测试

```python
# 测试1: --log-level 参数解析
def test_log_level_argument():
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args, _ = parser.parse_known_args(["--log-level", "DEBUG"])
    assert args.log_level == "DEBUG"

# 测试2: setup_logger 接受 level 参数
def test_setup_logger_level():
    import logging
    from core.logger import setup_logger
    logger = setup_logger(level=logging.DEBUG)
    assert logger.level == logging.DEBUG

# 测试3: WebBridgeLogHandler 节流
def test_log_handler_throttle():
    from core.log_handler import WebBridgeLogHandler
    received = []
    handler = WebBridgeLogHandler(callback=lambda l, m: received.append((l, m)))
    handler.setLevel(logging.DEBUG)
    # 短时间内发送大量日志
    for i in range(20):
        handler.emit(logging.LogRecord("test", logging.INFO, "", 0, f"msg {i}", (), None))
    # 验证节流生效
    assert len(received) <= 12  # 10 + 1条节流提示

# 测试4: log_message 信号正确传递
def test_log_message_signal(qtbot):
    from ui.web_bridge import WebBridge
    bridge = WebBridge()
    received = []
    bridge.log_message.connect(lambda l, m: received.append((l, m)))
    bridge.log_message.emit("INFO", "测试消息")
    assert len(received) == 1
    assert received[0] == ("INFO", "测试消息")
```

### 4.2 手动验收

| 场景 | 操作 | 预期结果 |
|------|------|---------|
| 启动参数 | `python main.py --log-level DEBUG` | 控制台显示 DEBUG 级别日志 |
| 日志面板 | 点击底部"▲ 日志" | 面板展开，显示日志列表 |
| 过滤 | 点击"ERROR"过滤按钮 | 只显示 ERROR 级别日志 |
| 实时推送 | 执行操作（施压/存档等） | 日志面板实时显示新日志 |
| 清空 | 点击"清空"按钮 | 日志列表清空 |
| 节流 | 短时间大量日志 | 显示节流提示，不卡顿 |

---

## 5. 涉及文件清单

| 文件 | 修改类型 | 修改内容 |
|------|---------|---------|
| `main.py` | 修改 | 增加 `--log-level` 参数解析 |
| `core/logger.py` | 修改 | `setup_logger()` 接受 level 参数，handler 级别同步更新 |
| `core/log_handler.py` | **新增** | `WebBridgeLogHandler` 自定义 Handler |
| `ui/web_bridge.py` | 修改 | 新增 `log_message` 信号 |
| `ui/web_main_window.py` | 修改 | `__init__()` 注册 LogHandler，新增 `_on_log_message()` 回调 |
| `ui/web/js/bridge.js` | 修改 | 新增 `log_message` 信号监听 |
| `ui/web/js/log-viewer.js` | **新增** | 日志查看器模块 |
| `ui/web/js/app.js` | 修改 | 集成 LogViewer，监听 logMessage 事件 |
| `ui/web/index.html` | 修改 | 新增日志面板 HTML、CSS/JS 引用 |
| `ui/web/css/log-viewer.css` | **新增** | 日志面板样式 |
| `tests/test_fix_log_viewer.py` | **新增** | 验收测试 |

---

## 6. 分步实施顺序

1. **Step 1-2**: 启动参数 + logger 改造（约 20min）
2. **Step 3-5**: WebBridgeLogHandler + 信号（约 30min）
3. **Step 6-9**: 前端日志查看器（约 60min）
4. 验收测试（约 20min）

必须在 BUG-2 完成后再开工。
