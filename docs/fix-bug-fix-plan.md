# Bug 修复方案：存档/读档、独立对话上下文、出示证件、移除蒙版

> 修复原则：**测试驱动开发（TDD）**——先编写能复现问题的失败测试，再实现修复使测试通过。

## 目录

1. [问题总览](#1-问题总览)
2. [修复顺序与依赖关系](#2-修复顺序与依赖关系)
3. [Fix-4：移除审讯操作蒙版](#3-fix-4移除审讯操作蒙版)
4. [Fix-3：修复出示证件功能](#4-fix-3修复出示证件功能)
5. [Fix-1：修复存档/读档功能](#5-fix-1修复存档读档功能)
6. [Fix-2：嫌疑人独立对话上下文](#6-fix-2嫌疑人独立对话上下文)
7. [Agent 调度总表](#7-agent-调度总表)

---

## 1. 问题总览

| # | 问题 | 根因 | 影响范围 |
|---|------|------|----------|
| Fix-4 | 审讯操作弹全屏蒙版，用户体验差 | `_start_worker()` 同时 emit `show_loading` + `show_typing_indicator`，用户要求只保留 typing indicator | `web_main_window.py` |
| Fix-3 | 出示证件显示"未知证据"，确认后无反应 | `EvidenceData` 字段为 `name`，但 `evidence.js` 读取 `evidence.title`（undefined） | `evidence.js` |
| Fix-1 | 存档无时间/命名；读档列表全显示"未命名存档"/"未知日期"；读档后计时器/聊天不恢复 | Python 发送 `created_at`，JS 读取 `session.date`；`time_left`（snake_case）≠ `timeLeft`（camelCase）；未 emit `clear_chat`；未恢复聊天历史 | `web_main_window.py`, `app.js` |
| Fix-2 | 切换嫌疑人时所有消息混在一起 | 前端 `ChatManager` 使用单一 `#chat-container`，无按嫌疑人分组 | `chat.js`, `app.js` |

---

## 2. 修复顺序与依赖关系

```
Fix-4 ──→ Fix-3 ──→ Fix-1 ──→ Fix-2 ──→ @review ──→ @test
```

- Fix-4 和 Fix-3 互相独立，可并行
- Fix-1 依赖 Fix-4（修改同一文件 `web_main_window.py`）
- Fix-2 依赖 Fix-1（修改同一文件 `app.js`）
- 每个修复都遵循：**先写失败测试 → 再改代码 → 测试通过**

---

## 3. Fix-4：移除审讯操作蒙版

### 3.1 问题复现测试

**文件：** `tests/test_fix4_remove_overlay.py`

```python
"""Fix-4: 验证审讯操作不再触发全屏 Loading Overlay，仅保留 Typing Indicator。

TDD 第一步：先写能复现问题的失败测试。
当前 _start_worker() 会 emit show_loading，这些测试在修复前会 FAIL。
"""

import pytest
from unittest.mock import patch, MagicMock

from ui.web_main_window import WebMainWindow


@pytest.fixture
def window(qtbot):
    w = WebMainWindow()
    qtbot.addWidget(w)
    qtbot.wait(500)
    return w


@pytest.fixture
def loaded_window(qtbot, window, mock_case_simple):
    with patch("core.suspect_agent.llm_client"):
        window.load_case(mock_case_simple)
    from schemas.interface_definitions import SuspectAgentProtocol
    for i, s_data in enumerate(mock_case_simple["suspects"]):
        mock_agent = MagicMock(spec=SuspectAgentProtocol)
        mock_agent.name = s_data["name"]
        mock_agent.pressure = 50
        mock_agent.memory = []
        mock_agent.respond.return_value = {
            "reply": "我是无辜的",
            "pressure_change": 0,
            "secret_triggered": None,
        }
        window.engine.suspects[i] = mock_agent
    qtbot.wait(100)
    return window


class TestNoLoadingOverlayOnChat:
    """聊天操作不应触发 show_loading。"""

    def test_chat_does_not_emit_show_loading(self, qtbot, loaded_window):
        """_on_chat_message_sent 不应 emit show_loading 信号。"""
        loading_emitted = []
        loaded_window.bridge.show_loading.connect(
            lambda msg, cancel: loading_emitted.append(msg)
        )

        loaded_window._on_chat_message_sent("你好")
        qtbot.wait(50)

        assert len(loading_emitted) == 0, (
            f"show_loading 不应被触发，但收到了: {loading_emitted}"
        )

    def test_chat_emits_typing_indicator(self, qtbot, loaded_window):
        """_on_chat_message_sent 应触发 show_typing_indicator(True)。"""
        typing_states = []
        loaded_window.bridge.show_typing_indicator.connect(
            lambda visible: typing_states.append(visible)
        )

        loaded_window._on_chat_message_sent("你好")
        qtbot.wait(50)

        assert True in typing_states, "show_typing_indicator(True) 应被触发"


class TestNoLoadingOverlayOnPressure:
    """施压操作不应触发 show_loading。"""

    def test_pressure_does_not_emit_show_loading(self, qtbot, loaded_window):
        loading_emitted = []
        loaded_window.bridge.show_loading.connect(
            lambda msg, cancel: loading_emitted.append(msg)
        )

        loaded_window._on_pressure()
        qtbot.wait(50)

        assert len(loading_emitted) == 0


class TestNoLoadingOverlayOnEmpathy:
    """共情操作不应触发 show_loading。"""

    def test_empathy_does_not_emit_show_loading(self, qtbot, loaded_window):
        loading_emitted = []
        loaded_window.bridge.show_loading.connect(
            lambda msg, cancel: loading_emitted.append(msg)
        )

        loaded_window._on_empathy()
        qtbot.wait(50)

        assert len(loading_emitted) == 0


class TestNoLoadingOverlayOnEvidence:
    """出示证据操作不应触发 show_loading。"""

    def test_evidence_does_not_emit_show_loading(self, qtbot, loaded_window, mock_case_simple):
        loading_emitted = []
        loaded_window.bridge.show_loading.connect(
            lambda msg, cancel: loading_emitted.append(msg)
        )

        evidence_id = mock_case_simple["evidences"][0]["id"]
        loaded_window._on_evidence_selected(evidence_id)
        qtbot.wait(50)

        assert len(loading_emitted) == 0


class TestNoHideLoadingOnWorkerFinish:
    """Worker 完成/错误/超时/取消不应 emit hide_loading。"""

    def test_worker_finish_no_hide_loading(self, qtbot, loaded_window):
        hide_emitted = []
        loaded_window.bridge.hide_loading.connect(
            lambda: hide_emitted.append(True)
        )

        loaded_window._on_worker_finished([])
        qtbot.wait(50)

        assert len(hide_emitted) == 0

    def test_worker_error_no_hide_loading(self, qtbot, loaded_window):
        hide_emitted = []
        loaded_window.bridge.hide_loading.connect(
            lambda: hide_emitted.append(True)
        )

        loaded_window._on_worker_error("测试错误")
        qtbot.wait(50)

        assert len(hide_emitted) == 0

    def test_worker_timeout_no_hide_loading(self, qtbot, loaded_window):
        hide_emitted = []
        loaded_window.bridge.hide_loading.connect(
            lambda: hide_emitted.append(True)
        )

        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = False
        loaded_window._current_worker = mock_worker

        loaded_window._on_worker_timeout()
        qtbot.wait(50)

        assert len(hide_emitted) == 0

    def test_cancel_no_hide_loading(self, qtbot, loaded_window):
        hide_emitted = []
        loaded_window.bridge.hide_loading.connect(
            lambda: hide_emitted.append(True)
        )

        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = False
        loaded_window._current_worker = mock_worker

        loaded_window._on_cancel_operation()
        qtbot.wait(50)

        assert len(hide_emitted) == 0


class TestTypingIndicatorStillWorks:
    """Typing indicator 在 Worker 生命周期中仍然正常工作。"""

    def test_worker_finish_hides_typing(self, qtbot, loaded_window):
        typing_states = []
        loaded_window.bridge.show_typing_indicator.connect(
            lambda visible: typing_states.append(visible)
        )

        loaded_window._on_worker_finished([])
        qtbot.wait(50)

        assert False in typing_states, "show_typing_indicator(False) 应在完成时触发"

    def test_worker_error_hides_typing(self, qtbot, loaded_window):
        typing_states = []
        loaded_window.bridge.show_typing_indicator.connect(
            lambda visible: typing_states.append(visible)
        )

        loaded_window._on_worker_error("错误")
        qtbot.wait(50)

        assert False in typing_states
```

### 3.2 修复代码

**文件：** `ui/web_main_window.py`

#### 3.2.1 `_start_worker()` 方法

删除以下行：
```python
# 删除这行
self.bridge.show_loading.emit(loading_msg, True)
```

删除以下代码块（超时定时器）：
```python
# 删除整个 _timeout_timer 创建
self._timeout_timer = QTimer(self)
self._timeout_timer.setSingleShot(True)
self._timeout_timer.timeout.connect(self._on_worker_timeout)
self._timeout_timer.start(LLM_TIMEOUT_SECONDS * 1000)
```

删除以下代码块（进度定时器）：
```python
# 删除整个 _progress_timer 创建
self._progress_timer = QTimer(self)
self._progress_timer.setInterval(1000)
self._progress_timer.timeout.connect(self._update_loading_progress)
self._progress_timer.start()
```

保留：
```python
self.bridge.show_typing_indicator.emit(True)
self.bridge.set_input_enabled.emit(False)
```

#### 3.2.2 `_on_worker_finished()` 方法

删除：
```python
self.bridge.hide_loading.emit()
```

#### 3.2.3 `_on_worker_error()` 方法

删除：
```python
self.bridge.hide_loading.emit()
```

#### 3.2.4 `_on_worker_timeout()` 方法

删除：
```python
self.bridge.hide_loading.emit()
```

#### 3.2.5 `_on_cancel_operation()` 方法

删除：
```python
self.bridge.hide_loading.emit()
```

#### 3.2.6 `_cleanup_after_worker()` 方法

删除 `_timeout_timer` 和 `_progress_timer` 相关代码：
```python
# 删除
if self._timeout_timer:
    self._timeout_timer.stop()
    self._timeout_timer = None
if self._progress_timer:
    self._progress_timer.stop()
    self._progress_timer = None
```

#### 3.2.7 `_update_loading_progress()` 方法

删除整个方法。

#### 3.2.8 `__init__` 中

删除 `self._timeout_timer = None` 和 `self._progress_timer = None` 初始化（如存在）。

### 3.3 需同步更新的已有测试

**文件：** `tests/test_web_integration.py`

- `TestWebMainWindowChat::test_chat_shows_loading` — 此测试验证 `show_loading` 被触发，修复后应删除或改为验证 `show_loading` **不被**触发
- `TestWebMainWindowWorker::test_cleanup_after_worker` — 验证 `_timeout_timer` 和 `_progress_timer` 的 stop 调用，修复后应删除
- `TestWebMainWindowWorker::test_cleanup_sets_timers_to_none` — 验证定时器设为 None，修复后应删除
- `TestWebMainWindowWorker::test_cleanup_with_none_timers` — 验证定时器为 None 时不崩溃，修复后应删除

---

## 4. Fix-3：修复出示证件功能

### 4.1 问题复现测试

**文件：** `tests/test_fix3_evidence_fields.py`

```python
"""Fix-3: 验证证据卡片使用正确的字段名。

TDD 第一步：先写能复现问题的失败测试。
当前 evidence.js 使用 evidence.title（不存在），应使用 evidence.name。
由于 JS 测试需要 WebView 环境，这里用 Python 验证数据结构一致性。
"""

import json
import pytest


class TestEvidenceDataFieldConsistency:
    """验证证据数据结构与前端 JS 读取的字段名一致。"""

    def test_evidence_has_name_field(self, mock_case_simple):
        """证据数据包含 'name' 字段（非 'title'）。"""
        for evidence in mock_case_simple["evidences"]:
            assert "name" in evidence, (
                f"证据 {evidence.get('id', '?')} 缺少 'name' 字段"
            )

    def test_evidence_has_id_field(self, mock_case_simple):
        """证据数据包含 'id' 字段。"""
        for evidence in mock_case_simple["evidences"]:
            assert "id" in evidence, (
                f"证据缺少 'id' 字段"
            )

    def test_evidence_has_description_field(self, mock_case_simple):
        """证据数据包含 'description' 字段。"""
        for evidence in mock_case_simple["evidences"]:
            assert "description" in evidence, (
                f"证据 {evidence.get('id', '?')} 缺少 'description' 字段"
            )

    def test_evidence_has_related_suspect_field(self, mock_case_simple):
        """证据数据包含 'related_suspect' 字段。"""
        for evidence in mock_case_simple["evidences"]:
            assert "related_suspect" in evidence, (
                f"证据 {evidence.get('id', '?')} 缺少 'related_suspect' 字段"
            )


class TestEvidenceJSFieldMapping:
    """验证 evidence.js 读取的字段名与后端数据一致。

    通过静态分析 evidence.js 源码确认字段名。
    """

    @pytest.fixture
    def evidence_js_content(self):
        with open("ui/web/js/evidence.js", "r", encoding="utf-8") as f:
            return f.read()

    def test_js_uses_evidence_name_not_title(self, evidence_js_content):
        """evidence.js 应使用 evidence.name 而非 evidence.title。"""
        # 不应出现 evidence.title
        assert "evidence.title" not in evidence_js_content, (
            "evidence.js 不应使用 evidence.title，应使用 evidence.name"
        )

    def test_js_uses_evidence_id(self, evidence_js_content):
        """evidence.js 应使用 evidence.id。"""
        assert "evidence.id" in evidence_js_content, (
            "evidence.js 应使用 evidence.id"
        )

    def test_js_uses_evidence_name(self, evidence_js_content):
        """evidence.js 应使用 evidence.name。"""
        assert "evidence.name" in evidence_js_content, (
            "evidence.js 应使用 evidence.name"
        )

    def test_js_does_not_use_evidence_tag(self, evidence_js_content):
        """evidence.js 不应使用 evidence.tag（后端数据无此字段）。"""
        assert "evidence.tag" not in evidence_js_content, (
            "evidence.js 不应使用 evidence.tag，后端 EvidenceData 无此字段"
        )
```

### 4.2 修复代码

**文件：** `ui/web/js/evidence.js`

#### 4.2.1 `_addEvidenceCard()` 方法

```diff
- <h4 class="evidence-title">${this._escapeHtml(evidence.title || '未知证据')}</h4>
+ <h4 class="evidence-title">${this._escapeHtml(evidence.name || '未知证据')}</h4>
```

```diff
- ${evidence.tag ? `<span class="evidence-tag">${this._escapeHtml(evidence.tag)}</span>` : ''}
```
（删除整行，因为 `EvidenceData` 无 `tag` 字段）

#### 4.2.2 `_onEvidenceClick()` 方法

```diff
- `确定要出示「${evidence.title || '未知证据'}」吗？`,
+ `确定要出示「${evidence.name || '未知证据'}」吗？`,
```

#### 4.2.3 `_onEvidenceClick()` fallback confirm 分支

```diff
- const confirmed = confirm(`确定要出示「${evidence.title || '未知证据'}」吗？`);
+ const confirmed = confirm(`确定要出示「${evidence.name || '未知证据'}」吗？`);
```

---

## 5. Fix-1：修复存档/读档功能

### 5.1 问题复现测试

**文件：** `tests/test_fix1_save_load.py`

```python
"""Fix-1: 验证存档/读档功能完整修复。

TDD 第一步：先写能复现问题的失败测试。
修复前的问题：
1. 存档成功提示只显示 UUID，无案件名称和时间
2. 读档列表字段名不匹配：Python 发送 created_at，JS 读取 session.date
3. 读档后 state dict 中 time_left (snake_case) 与 JS 的 timeLeft (camelCase) 不匹配
4. 读档后未 emit clear_chat 清除旧消息
5. 读档后未恢复聊天历史
6. 读档后未传递 caseTitle
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from ui.web_main_window import WebMainWindow


@pytest.fixture
def window(qtbot):
    w = WebMainWindow()
    qtbot.addWidget(w)
    qtbot.wait(500)
    return w


@pytest.fixture
def loaded_window(qtbot, window, mock_case_simple):
    with patch("core.suspect_agent.llm_client"):
        window.load_case(mock_case_simple)
    from schemas.interface_definitions import SuspectAgentProtocol
    for i, s_data in enumerate(mock_case_simple["suspects"]):
        mock_agent = MagicMock(spec=SuspectAgentProtocol)
        mock_agent.name = s_data["name"]
        mock_agent.pressure = 50
        mock_agent.memory = []
        mock_agent.respond.return_value = {
            "reply": "我是无辜的",
            "pressure_change": 0,
            "secret_triggered": None,
        }
        window.engine.suspects[i] = mock_agent
    qtbot.wait(100)
    return window


class TestSaveGameShowsCaseTitleAndTime:
    """存档成功提示应包含案件名称和格式化时间。"""

    def test_save_dialog_contains_case_title(self, qtbot, loaded_window, mock_case_simple):
        """存档成功对话框包含案件标题。"""
        with patch("core.db.save_full_session"):
            dialogs = []
            loaded_window.bridge.show_dialog.connect(
                lambda t, m: dialogs.append({"title": t, "message": m})
            )

            loaded_window._on_save_game()
            qtbot.wait(100)

            assert len(dialogs) > 0
            assert mock_case_simple["title"] in dialogs[0]["message"], (
                f"存档提示应包含案件标题 '{mock_case_simple['title']}'，"
                f"实际内容: {dialogs[0]['message']}"
            )

    def test_save_dialog_contains_formatted_time(self, qtbot, loaded_window):
        """存档成功对话框包含格式化时间。"""
        with patch("core.db.save_full_session"):
            dialogs = []
            loaded_window.bridge.show_dialog.connect(
                lambda t, m: dialogs.append({"title": t, "message": m})
            )

            loaded_window._on_save_game()
            qtbot.wait(100)

            assert len(dialogs) > 0
            # 验证包含时间格式（YYYY-MM-DD HH:MM）
            import re
            time_pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}"
            assert re.search(time_pattern, dialogs[0]["message"]), (
                f"存档提示应包含格式化时间，实际内容: {dialogs[0]['message']}"
            )


class TestLoadGameFieldNames:
    """读档列表字段名应与 JS 前端匹配。"""

    def test_load_list_has_name_field(self, qtbot, loaded_window, mock_case_simple):
        """读档列表每项包含 'name' 字段（非 session_id 前缀）。"""
        mock_sessions = [
            {
                "session_id": "sess_001",
                "case_id": mock_case_simple["case_id"],
                "saved_at": "2026-05-03T14:30:00",
            }
        ]
        with patch("core.db.list_sessions", return_value=mock_sessions), \
             patch("core.db.load_case", return_value=mock_case_simple):
            save_lists = []
            loaded_window.bridge.show_save_list.connect(
                lambda s: save_lists.append(s)
            )

            loaded_window._on_load_game()
            qtbot.wait(100)

            assert len(save_lists) > 0
            session = save_lists[0][0]
            assert "name" in session, (
                f"读档列表项应包含 'name' 字段，实际字段: {list(session.keys())}"
            )
            assert mock_case_simple["title"] in session["name"], (
                f"name 字段应包含案件标题，实际值: {session['name']}"
            )

    def test_load_list_has_date_field(self, qtbot, loaded_window, mock_case_simple):
        """读档列表每项包含 'date' 字段（非 'created_at'）。"""
        mock_sessions = [
            {
                "session_id": "sess_001",
                "case_id": mock_case_simple["case_id"],
                "saved_at": "2026-05-03T14:30:00",
            }
        ]
        with patch("core.db.list_sessions", return_value=mock_sessions), \
             patch("core.db.load_case", return_value=mock_case_simple):
            save_lists = []
            loaded_window.bridge.show_save_list.connect(
                lambda s: save_lists.append(s)
            )

            loaded_window._on_load_game()
            qtbot.wait(100)

            assert len(save_lists) > 0
            session = save_lists[0][0]
            assert "date" in session, (
                f"读档列表项应包含 'date' 字段（前端读取 session.date），"
                f"实际字段: {list(session.keys())}"
            )
            assert session["date"] != "", (
                "date 字段不应为空"
            )

    def test_load_list_has_summary_field(self, qtbot, loaded_window, mock_case_simple):
        """读档列表每项包含 'summary' 字段。"""
        mock_sessions = [
            {
                "session_id": "sess_001",
                "case_id": mock_case_simple["case_id"],
                "saved_at": "2026-05-03T14:30:00",
            }
        ]
        with patch("core.db.list_sessions", return_value=mock_sessions), \
             patch("core.db.load_case", return_value=mock_case_simple):
            save_lists = []
            loaded_window.bridge.show_save_list.connect(
                lambda s: save_lists.append(s)
            )

            loaded_window._on_load_game()
            qtbot.wait(100)

            assert len(save_lists) > 0
            session = save_lists[0][0]
            assert "summary" in session, (
                f"读档列表项应包含 'summary' 字段，实际字段: {list(session.keys())}"
            )

    def test_load_list_date_is_formatted(self, qtbot, loaded_window, mock_case_simple):
        """date 字段应为人类可读格式（非 ISO 格式）。"""
        mock_sessions = [
            {
                "session_id": "sess_001",
                "case_id": mock_case_simple["case_id"],
                "saved_at": "2026-05-03T14:30:00.123456",
            }
        ]
        with patch("core.db.list_sessions", return_value=mock_sessions), \
             patch("core.db.load_case", return_value=mock_case_simple):
            save_lists = []
            loaded_window.bridge.show_save_list.connect(
                lambda s: save_lists.append(s)
            )

            loaded_window._on_load_game()
            qtbot.wait(100)

            session = save_lists[0][0]
            # 不应包含 ISO 格式的 T 和毫秒
            assert "T" not in session["date"], (
                f"date 应为可读格式，非 ISO 格式，实际值: {session['date']}"
            )


class TestLoadGameUsesCamelCaseState:
    """读档后 init_game_state 的 state dict 应使用 camelCase。"""

    def test_state_has_timeLeft_not_time_left(self, qtbot, loaded_window, mock_case_simple):
        """state dict 包含 timeLeft（camelCase），非 time_left（snake_case）。"""
        engine_state = loaded_window.engine.to_dict()

        with patch("core.db.load_full_session",
                   return_value=(mock_case_simple["case_id"], engine_state)), \
             patch("core.db.load_case", return_value=mock_case_simple), \
             patch("core.suspect_agent.llm_client"):

            states = []
            loaded_window.bridge.init_game_state.connect(
                lambda s: states.append(s)
            )

            loaded_window._on_save_selected("sess_001")
            qtbot.wait(100)

            assert len(states) > 0
            state = states[0]
            assert "timeLeft" in state, (
                f"state 应包含 'timeLeft'（JS 读取 state.timeLeft），"
                f"实际字段: {list(state.keys())}"
            )

    def test_state_has_caseTitle(self, qtbot, loaded_window, mock_case_simple):
        """state dict 包含 caseTitle。"""
        engine_state = loaded_window.engine.to_dict()

        with patch("core.db.load_full_session",
                   return_value=(mock_case_simple["case_id"], engine_state)), \
             patch("core.db.load_case", return_value=mock_case_simple), \
             patch("core.suspect_agent.llm_client"):

            states = []
            loaded_window.bridge.init_game_state.connect(
                lambda s: states.append(s)
            )

            loaded_window._on_save_selected("sess_001")
            qtbot.wait(100)

            assert len(states) > 0
            state = states[0]
            assert "caseTitle" in state, (
                f"state 应包含 'caseTitle'，实际字段: {list(state.keys())}"
            )
            assert state["caseTitle"] == mock_case_simple["title"]


class TestLoadGameClearsOldChat:
    """读档后应清除旧聊天消息。"""

    def test_load_emits_clear_chat_before_init(self, qtbot, loaded_window, mock_case_simple):
        """选择存档后 emit clear_chat 信号。"""
        engine_state = loaded_window.engine.to_dict()

        with patch("core.db.load_full_session",
                   return_value=(mock_case_simple["case_id"], engine_state)), \
             patch("core.db.load_case", return_value=mock_case_simple), \
             patch("core.suspect_agent.llm_client"):

            clear_called = []
            loaded_window.bridge.clear_chat.connect(
                lambda: clear_called.append(True)
            )

            loaded_window._on_save_selected("sess_001")
            qtbot.wait(100)

            assert len(clear_called) > 0, "读档后应 emit clear_chat 清除旧消息"


class TestLoadGameRestoresChatHistory:
    """读档后应恢复每个嫌疑人的聊天历史。"""

    def test_load_restores_suspect_memory(self, qtbot, loaded_window, mock_case_simple):
        """读档后通过 add_message 恢复聊天历史。"""
        # 给嫌疑人添加一些聊天记录
        loaded_window.engine.suspects[0].memory = [
            {"role": "user", "content": "你在哪里？"},
            {"role": "assistant", "content": "我在家。"},
        ]
        loaded_window.engine.suspects[1].memory = [
            {"role": "user", "content": "你认识老张吗？"},
            {"role": "assistant", "content": "认识。"},
        ]

        engine_state = loaded_window.engine.to_dict()

        with patch("core.db.load_full_session",
                   return_value=(mock_case_simple["case_id"], engine_state)), \
             patch("core.db.load_case", return_value=mock_case_simple), \
             patch("core.suspect_agent.llm_client"):

            messages = []
            loaded_window.bridge.add_message.connect(
                lambda role, content, suspect: messages.append(
                    {"role": role, "content": content, "suspect": suspect}
                )
            )

            loaded_window._on_save_selected("sess_001")
            qtbot.wait(100)

            # 应有聊天历史消息被恢复
            assert len(messages) > 0, "读档后应恢复聊天历史"

            # 验证第一个嫌疑人的消息被恢复
            player_msgs = [m for m in messages if m["role"] == "player" and "你在哪里" in m["content"]]
            assert len(player_msgs) > 0, "应恢复第一个嫌疑人的对话"

            suspect_msgs = [m for m in messages if m["role"] == "suspect" and "我在家" in m["content"]]
            assert len(suspect_msgs) > 0, "应恢复第一个嫌疑人的回复"
```

### 5.2 修复代码

**文件：** `ui/web_main_window.py`

#### 5.2.1 `_on_save_game()` 方法

```python
def _on_save_game(self):
    """存档。"""
    if self.engine is None:
        return
    try:
        session_id = str(uuid.uuid4())
        case_id = self.engine.case.get("case_id", "unknown")
        case_title = self.engine.case.get("title", "未知案件")
        engine_state_dict = self.engine.to_dict()
        db.save_full_session(session_id, case_id, engine_state_dict)

        from datetime import datetime as dt
        now_str = dt.now().strftime("%Y-%m-%d %H:%M")
        self.bridge.show_dialog.emit(
            "存档成功", f"「{case_title}」已保存\n{now_str}"
        )
    except Exception as exc:
        logger.error(f"存档失败: {exc}")
        self.bridge.show_dialog.emit("存档失败", f"保存失败: {exc}")
```

#### 5.2.2 `_on_load_game()` 方法

```python
def _on_load_game(self):
    """读档 - 显示存档列表。"""
    try:
        sessions = db.list_sessions()
        formatted_sessions = []
        for s in sessions:
            case_id = s.get("case_id", "")
            case_data = db.load_case(case_id)
            case_title = case_data.get("title", "未知案件") if case_data else "未知案件"

            saved_at = s.get("saved_at", "")
            try:
                from datetime import datetime as dt
                parsed = dt.fromisoformat(saved_at)
                date_str = parsed.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                date_str = saved_at

            formatted_sessions.append({
                "session_id": s["session_id"],
                "name": f"{case_title} - {date_str}",
                "date": date_str,
                "summary": "",
            })
        self.bridge.show_save_list.emit(formatted_sessions)
    except Exception as exc:
        logger.error(f"获取存档列表失败: {exc}")
        self.bridge.show_dialog.emit("读档失败", f"无法读取存档列表: {exc}")
```

#### 5.2.3 `_on_save_selected()` 方法

```python
def _on_save_selected(self, session_id):
    """选择存档后加载。"""
    try:
        result = db.load_full_session(session_id)
        if result is None:
            self.bridge.show_dialog.emit("读档失败", "存档数据不存在")
            return

        case_id, engine_state_dict = result
        case_data = db.load_case(case_id)
        if case_data is None:
            self.bridge.show_dialog.emit("读档失败", f"关联案件未找到: {case_id}")
            return

        self.engine = InterrogationEngine.from_dict(engine_state_dict, case_data)

        self.bridge.clear_chat.emit()

        state = {
            "suspects": [
                {"name": s.name, "pressure": s.pressure}
                for s in self.engine.suspects
            ],
            "evidences": case_data.get("evidences", []),
            "timeLeft": self.engine.time_left,
            "current_suspect_index": self.engine.current_suspect_index,
            "state": self.engine.state,
            "case_id": case_id,
            "caseTitle": case_data.get("title", ""),
        }

        self.bridge.init_game_state.emit(state)
        self.bridge.set_input_enabled.emit(True)

        for suspect in self.engine.suspects:
            for msg in suspect.memory:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "user":
                    self.bridge.add_message.emit("player", content, "审讯员")
                elif role == "assistant":
                    self.bridge.add_message.emit("suspect", content, suspect.name)

        if self.engine.state == "interrogating":
            self._countdown_timer.start()
    except Exception as exc:
        logger.error(f"加载存档失败: {exc}")
        self.bridge.show_dialog.emit("读档失败", f"加载失败: {exc}")
```

#### 5.2.4 `load_case()` 方法

同步修改 `load_case()` 中的 state dict，使用 camelCase：

```python
state = {
    "suspects": [
        {"name": s.name, "pressure": s.pressure}
        for s in self.engine.suspects
    ],
    "evidences": case_data.get("evidences", []),
    "timeLeft": self.engine.time_left,              # camelCase
    "current_suspect_index": 0,
    "state": self.engine.state,
    "case_id": case_data.get("case_id", ""),
    "caseTitle": case_data.get("title", ""),        # 新增
}
```

**文件：** `ui/web/js/app.js`

#### 5.2.5 `initGameState` 事件处理

```javascript
bridge.on('initGameState', (data) => {
    if (!data || !data.state) return;
    const state = data.state;

    if (state.suspects) {
        suspectManager.loadSuspects(state.suspects);
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
});
```

### 5.3 需同步更新的已有测试

**文件：** `tests/test_web_integration.py`

- `TestWebMainWindowCaseLoading::test_load_case_emits_init_game_state` — 断言 `time_left` 改为 `timeLeft`
- `TestWebMainWindowSaveLoad::test_load_game_with_sessions` — 验证返回字段包含 `name`、`date`、`summary`

---

## 6. Fix-2：嫌疑人独立对话上下文

### 6.1 问题复现测试

**文件：** `tests/test_fix2_per_suspect_chat.py`

```python
"""Fix-2: 验证每个嫌疑人有独立的对话上下文。

TDD 第一步：先写能复现问题的失败测试。
当前 ChatManager 使用单一容器，切换嫌疑人时消息不切换。
由于这是前端 JS 逻辑，通过静态分析验证代码结构。
"""

import pytest


class TestChatJSPerSuspectContext:
    """验证 chat.js 实现了按嫌疑人分组的消息存储。"""

    @pytest.fixture
    def chat_js_content(self):
        with open("ui/web/js/chat.js", "r", encoding="utf-8") as f:
            return f.read()

    def test_chat_manager_has_messages_by_suspect(self, chat_js_content):
        """ChatManager 应有 _messagesBySuspect 属性。"""
        assert "_messagesBySuspect" in chat_js_content, (
            "ChatManager 应定义 _messagesBySuspect 用于按嫌疑人分组存储消息"
        )

    def test_chat_manager_has_current_suspect(self, chat_js_content):
        """ChatManager 应有 _currentSuspect 属性。"""
        assert "_currentSuspect" in chat_js_content, (
            "ChatManager 应定义 _currentSuspect 跟踪当前显示的嫌疑人"
        )

    def test_chat_manager_has_switch_suspect_method(self, chat_js_content):
        """ChatManager 应有 switchSuspect() 方法。"""
        assert "switchSuspect" in chat_js_content, (
            "ChatManager 应定义 switchSuspect() 方法用于切换嫌疑人对话"
        )

    def test_switch_suspect_clears_container(self, chat_js_content):
        """switchSuspect() 应清空聊天容器。"""
        # 检查 switchSuspect 方法内是否清空了 container
        assert "switchSuspect" in chat_js_content
        # 方法内应包含清空逻辑
        switch_start = chat_js_content.index("switchSuspect")
        switch_section = chat_js_content[switch_start:switch_start + 500]
        assert "innerHTML" in switch_section or "textContent" in switch_section or "removeChild" in switch_section, (
            "switchSuspect() 应清空聊天容器"
        )


class TestAppJSSuspectSwitch:
    """验证 app.js 在嫌疑人切换时调用 switchSuspect。"""

    @pytest.fixture
    def app_js_content(self):
        with open("ui/web/js/app.js", "r", encoding="utf-8") as f:
            return f.read()

    def test_suspect_selector_calls_switch_suspect(self, app_js_content):
        """嫌疑人选择器 change 事件应调用 chatManager.switchSuspect()。"""
        assert "switchSuspect" in app_js_content, (
            "app.js 应在嫌疑人切换时调用 chatManager.switchSuspect()"
        )

    def test_init_game_state_sets_suspect_context(self, app_js_content):
        """initGameState 应设置初始嫌疑人上下文。"""
        # 检查 initGameState 处理中是否调用了 switchSuspect
        assert "switchSuspect" in app_js_content, (
            "app.js 应在 initGameState 时调用 chatManager.switchSuspect()"
        )
```

### 6.2 修复代码

**文件：** `ui/web/js/chat.js`

完整重写 `ChatManager` 类：

```javascript
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

        this.container.innerHTML = '';

        const defaultMsgs = this._messagesBySuspect['_default'] || [];
        for (const msg of defaultMsgs) {
            if (msg.role === 'system') {
                this._renderMessage(msg.role, msg.content, msg.suspectName, msg.time);
            }
        }

        const msgs = this._messagesBySuspect[suspectName] || [];
        for (const msg of msgs) {
            this._renderMessage(msg.role, msg.content, msg.suspectName, msg.time);
        }

        if (msgs.length === 0 && defaultMsgs.length === 0) {
            const placeholder = document.createElement('div');
            placeholder.className = 'message message-system';
            placeholder.innerHTML = `<div class="message-content">与 ${this._escapeHtml(suspectName || '嫌疑人')} 的对话将在这里显示...</div>`;
            this.container.appendChild(placeholder);
        }
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
        this.container.innerHTML = '';
        this._typingEl = null;
        this._messagesBySuspect = {};
        this._currentSuspect = null;

        const placeholder = document.createElement('div');
        placeholder.className = 'message message-system';
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
```

**文件：** `ui/web/js/app.js`

#### 6.2.1 嫌疑人选择器 change 事件

```javascript
const suspectSelector = document.getElementById('suspect-selector');
if (suspectSelector) {
    suspectSelector.addEventListener('change', (e) => {
        const index = parseInt(e.target.value, 10);
        if (!isNaN(index) && index >= 0) {
            if (window.bridge) window.bridge.selectSuspect(index);
            suspectManager.selectSuspect(index);

            const suspect = suspectManager.suspects[index];
            if (suspect && suspect.name) {
                chatManager.switchSuspect(suspect.name);
            }
        }
    });
}
```

#### 6.2.2 `initGameState` 事件处理

在末尾添加：

```javascript
const idx = state.current_suspect_index || 0;
if (state.suspects && state.suspects[idx]) {
    chatManager.switchSuspect(state.suspects[idx].name);
}
```

---

## 7. Agent 调度总表

| Step | Agent | 任务 | 依赖 | Prompt 摘要 |
|------|-------|------|------|-------------|
| 1a | @dev | 编写 Fix-4 失败测试 | 无 | 编写 `test_fix4_remove_overlay.py`，验证 `show_loading` 不被 emit |
| 1b | @dev | 编写 Fix-3 失败测试 | 无 | 编写 `test_fix3_evidence_fields.py`，验证 JS 使用 `evidence.name` |
| 2a | @dev | 实现 Fix-4 代码修复 | 1a | 修改 `web_main_window.py`，移除 `show_loading`/`hide_loading` emit，清理定时器 |
| 2b | @dev | 实现 Fix-3 代码修复 | 1b | 修改 `evidence.js`，`evidence.title`→`evidence.name`，删除 `evidence.tag` |
| 2c | @dev | 更新已有测试 Fix-4 | 2a | 修改 `test_web_integration.py`，删除/更新 `show_loading` 相关断言 |
| 3 | @dev | 编写 Fix-1 失败测试 | 2a | 编写 `test_fix1_save_load.py`，验证字段名、camelCase、clear_chat、聊天恢复 |
| 4 | @dev | 实现 Fix-1 代码修复 | 3 | 修改 `web_main_window.py` + `app.js`，修复存档/读档全流程 |
| 4b | @dev | 更新已有测试 Fix-1 | 4 | 修改 `test_web_integration.py`，更新 `time_left`→`timeLeft` 断言 |
| 5 | @dev | 编写 Fix-2 失败测试 | 4 | 编写 `test_fix2_per_suspect_chat.py`，验证按嫌疑人分组 |
| 6 | @dev | 实现 Fix-2 代码修复 | 5 | 修改 `chat.js` + `app.js`，添加 `_messagesBySuspect` + `switchSuspect` |
| 7 | @review | 全量代码审查 | 6 | 审查全部改动，运行 flake8 + py_compile |
| 8 | @test | 场景用例设计 | 7 | 输出测试场景设计文档 |
| 9 | @test | 测试用例开发 | 8 评审通过 | 编写 + 运行自动化测试 |
| 10 | @dev | BUG 修复 | 9 (如有) | 修复测试发现的问题 |
| 11 | @review | 最终验收 | 9-10 | 确认所有测试通过 |

### 每个 Agent 任务的详细 Prompt

#### Step 1a: @dev — 编写 Fix-4 失败测试

```
## 任务
编写测试文件 `tests/test_fix4_remove_overlay.py`，验证审讯操作不应触发全屏 Loading Overlay。

## 背景
当前 `WebMainWindow._start_worker()` 会同时 emit `show_loading` 和 `show_typing_indicator`。
用户要求移除蒙版，只保留 typing indicator。

## 测试文件内容
（见上方 §3.1 的完整测试代码）

## 要求
1. 创建 `tests/test_fix4_remove_overlay.py`
2. 运行 `uv run pytest tests/test_fix4_remove_overlay.py -v` 确认测试 FAIL（因为当前代码仍 emit show_loading）
3. 如果测试意外 PASS，说明测试逻辑有误，需修正
4. 只写测试，不修改任何源代码
```

#### Step 1b: @dev — 编写 Fix-3 失败测试

```
## 任务
编写测试文件 `tests/test_fix3_evidence_fields.py`，验证 evidence.js 使用正确的字段名。

## 背景
后端 `EvidenceData` 有 `name`、`id`、`description`、`related_suspect` 字段。
前端 `evidence.js` 错误地使用 `evidence.title`（undefined）和 `evidence.tag`（undefined）。

## 测试文件内容
（见上方 §4.1 的完整测试代码）

## 要求
1. 创建 `tests/test_fix3_evidence_fields.py`
2. 运行 `uv run pytest tests/test_fix3_evidence_fields.py -v` 确认测试 FAIL
3. 只写测试，不修改任何源代码
```

#### Step 2a: @dev — 实现 Fix-4 代码修复

```
## 任务
修改 `ui/web_main_window.py`，移除 Loading Overlay 相关代码，只保留 Typing Indicator。

## 具体改动
（见上方 §3.2 的完整改动说明）

## 要求
1. 按改动说明逐项修改
2. 运行 `uv run pytest tests/test_fix4_remove_overlay.py -v` 确认测试 PASS
3. 运行 `uv run flake8 ui/web_main_window.py --max-line-length=120` 确认无 lint 错误
4. 运行 `python3 -m py_compile ui/web_main_window.py` 确认语法正确
```

#### Step 2b: @dev — 实现 Fix-3 代码修复

```
## 任务
修改 `ui/web/js/evidence.js`，修复字段名。

## 具体改动
（见上方 §4.2 的完整改动说明）

## 要求
1. 将所有 `evidence.title` 替换为 `evidence.name`
2. 删除 `evidence.tag` 引用
3. 运行 `uv run pytest tests/test_fix3_evidence_fields.py -v` 确认测试 PASS
4. 确认文件中不再有 `evidence.title` 和 `evidence.tag` 引用
```

#### Step 2c: @dev — 更新已有测试 Fix-4

```
## 任务
更新 `tests/test_web_integration.py` 中与 Fix-4 冲突的已有测试。

## 具体改动
1. 删除 `TestWebMainWindowChat::test_chat_shows_loading`（不再验证 show_loading）
2. 删除 `TestWebMainWindowWorker::test_cleanup_after_worker`（不再有 _timeout_timer/_progress_timer）
3. 删除 `TestWebMainWindowWorker::test_cleanup_sets_timers_to_none`
4. 删除 `TestWebMainWindowWorker::test_cleanup_with_none_timers`

## 要求
1. 运行 `uv run pytest tests/test_web_integration.py -v` 确认所有测试 PASS
```

#### Step 3: @dev — 编写 Fix-1 失败测试

```
## 任务
编写测试文件 `tests/test_fix1_save_load.py`，验证存档/读档功能修复。

## 背景
（见上方 §5.1 的完整背景说明）

## 测试文件内容
（见上方 §5.1 的完整测试代码）

## 要求
1. 创建 `tests/test_fix1_save_load.py`
2. 运行 `uv run pytest tests/test_fix1_save_load.py -v` 确认测试 FAIL
3. 只写测试，不修改任何源代码
```

#### Step 4: @dev — 实现 Fix-1 代码修复

```
## 任务
修改 `ui/web_main_window.py` 和 `ui/web/js/app.js`，修复存档/读档功能。

## 具体改动
（见上方 §5.2 的完整改动说明）

## 要求
1. 修改 `_on_save_game()`：提示包含案件名称和格式化时间
2. 修改 `_on_load_game()`：发送 `name`、`date`、`summary` 字段
3. 修改 `_on_save_selected()`：使用 camelCase、emit clear_chat、恢复聊天历史
4. 修改 `load_case()`：使用 camelCase state dict
5. 修改 `app.js`：兼容 timeLeft/time_left
6. 运行 `uv run pytest tests/test_fix1_save_load.py -v` 确认测试 PASS
7. 运行 `uv run flake8 ui/web_main_window.py --max-line-length=120`
```

#### Step 4b: @dev — 更新已有测试 Fix-1

```
## 任务
更新 `tests/test_web_integration.py` 中与 Fix-1 冲突的已有测试。

## 具体改动
1. `TestWebMainWindowCaseLoading::test_load_case_emits_init_game_state`：断言 `time_left` 改为 `timeLeft`
2. `TestWebMainWindowSaveLoad::test_load_game_with_sessions`：验证返回字段包含 `name`、`date`、`summary`

## 要求
1. 运行 `uv run pytest tests/test_web_integration.py -v` 确认所有测试 PASS
```

#### Step 5: @dev — 编写 Fix-2 失败测试

```
## 任务
编写测试文件 `tests/test_fix2_per_suspect_chat.py`，验证嫌疑人独立对话上下文。

## 测试文件内容
（见上方 §6.1 的完整测试代码）

## 要求
1. 创建 `tests/test_fix2_per_suspect_chat.py`
2. 运行 `uv run pytest tests/test_fix2_per_suspect_chat.py -v` 确认测试 FAIL
3. 只写测试，不修改任何源代码
```

#### Step 6: @dev — 实现 Fix-2 代码修复

```
## 任务
修改 `ui/web/js/chat.js` 和 `ui/web/js/app.js`，实现按嫌疑人分组的对话上下文。

## 具体改动
（见上方 §6.2 的完整改动说明）

## 要求
1. `chat.js`：添加 `_messagesBySuspect`、`_currentSuspect`、`switchSuspect()` 方法
2. `app.js`：嫌疑人切换时调用 `chatManager.switchSuspect()`
3. `app.js`：`initGameState` 设置初始嫌疑人上下文
4. 运行 `uv run pytest tests/test_fix2_per_suspect_chat.py -v` 确认测试 PASS
```

#### Step 7: @review — 全量代码审查

```
## 任务
审查 Fix-1/2/3/4 的全部代码改动。

## 审查范围
1. `ui/web_main_window.py`
2. `ui/web/js/evidence.js`
3. `ui/web/js/chat.js`
4. `ui/web/js/app.js`
5. `tests/test_fix4_remove_overlay.py`
6. `tests/test_fix3_evidence_fields.py`
7. `tests/test_fix1_save_load.py`
8. `tests/test_fix2_per_suspect_chat.py`
9. `tests/test_web_integration.py`（更新部分）

## 审查清单
（见 §5 审查清单）

## 要求
1. 运行 `uv run pytest tests/ -v --tb=short`
2. 运行 `uv run flake8 core ui --max-line-length=120`
3. 运行 `python3 -m py_compile ui/web_main_window.py`
4. 输出审查报告
```

#### Step 8: @test — 场景用例设计

```
## 任务
为 4 个修复项编写测试场景用例设计文档。

## 测试范围
- Fix-4: 移除 Loading Overlay
- Fix-3: 证据字段名修复
- Fix-1: 存档/读档完整流程
- Fix-2: 嫌疑人独立对话上下文

## 要求
1. 按场景用例设计规范输出文档
2. 包含测试覆盖矩阵
3. 标注优先级（P0/P1/P2）
4. 提交 PM 评审
```

#### Step 9: @test — 测试用例开发

```
## 任务
根据评审通过的场景用例，编写自动化测试用例。

## 要求
1. Mock 所有 LLM 调用
2. 使用 tmp_path fixture 创建临时数据库
3. 覆盖正常路径和异常路径
4. 运行 `uv run pytest tests/ -v --tb=short` 确认全部通过
5. 运行 `uv run pytest --cov=core --cov=ui --cov-report=term` 检查覆盖率
```
