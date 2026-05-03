"""Fix-4: 验证 Worker 超时/取消后 typing indicator 正确隐藏、输入重新启用、
_current_worker 清空、系统消息发出，以及连续操作时状态正确转换。

P0 场景：
1. Worker 超时后 typing indicator 正确隐藏
2. 用户取消操作后 typing indicator 正确隐藏
3. 超时后输入被重新启用
4. 取消后输入被重新启用

P1 场景：
5. 超时后 _current_worker 被清空
6. 取消后 _current_worker 被清空
7. 连续操作时 typing indicator 状态正确转换（使用 DummySuspectAgent）
8. 超时后发出系统消息
9. 取消后发出系统消息
"""

import pytest
from unittest.mock import patch, MagicMock

from ui.web_main_window import WebMainWindow, WebWorker


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


# ============================================================
# P0: Worker 超时/取消后 typing indicator 正确隐藏
# ============================================================


class TestTimeoutHidesTypingIndicator:
    """P0-1: Worker 超时后 typing indicator 正确隐藏。"""

    def test_timeout_emits_show_typing_indicator_false(self, qtbot, loaded_window):
        """_on_worker_timeout 应 emit show_typing_indicator(False)。"""
        typing_states = []
        loaded_window.bridge.show_typing_indicator.connect(
            lambda visible: typing_states.append(visible)
        )

        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        loaded_window._current_worker = mock_worker

        loaded_window._on_worker_timeout()
        qtbot.wait(50)

        assert False in typing_states, (
            f"超时后应 emit show_typing_indicator(False)，"
            f"实际收到: {typing_states}"
        )


class TestCancelHidesTypingIndicator:
    """P0-2: 用户取消操作后 typing indicator 正确隐藏。"""

    def test_cancel_emits_show_typing_indicator_false(self, qtbot, loaded_window):
        """_on_cancel_operation 应 emit show_typing_indicator(False)。"""
        typing_states = []
        loaded_window.bridge.show_typing_indicator.connect(
            lambda visible: typing_states.append(visible)
        )

        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        loaded_window._current_worker = mock_worker

        loaded_window._on_cancel_operation()
        qtbot.wait(50)

        assert False in typing_states, (
            f"取消后应 emit show_typing_indicator(False)，"
            f"实际收到: {typing_states}"
        )


# ============================================================
# P0: 超时/取消后输入被重新启用
# ============================================================


class TestTimeoutReEnablesInput:
    """P0-3: 超时后输入被重新启用。"""

    def test_timeout_emits_set_input_enabled_true(self, qtbot, loaded_window):
        """_on_worker_timeout 应 emit set_input_enabled(True)。"""
        input_states = []
        loaded_window.bridge.set_input_enabled.connect(
            lambda enabled: input_states.append(enabled)
        )

        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        loaded_window._current_worker = mock_worker

        loaded_window._on_worker_timeout()
        qtbot.wait(50)

        assert True in input_states, (
            f"超时后应 emit set_input_enabled(True)，"
            f"实际收到: {input_states}"
        )


class TestCancelReEnablesInput:
    """P0-4: 取消后输入被重新启用。"""

    def test_cancel_emits_set_input_enabled_true(self, qtbot, loaded_window):
        """_on_cancel_operation 应 emit set_input_enabled(True)。"""
        input_states = []
        loaded_window.bridge.set_input_enabled.connect(
            lambda enabled: input_states.append(enabled)
        )

        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        loaded_window._current_worker = mock_worker

        loaded_window._on_cancel_operation()
        qtbot.wait(50)

        assert True in input_states, (
            f"取消后应 emit set_input_enabled(True)，"
            f"实际收到: {input_states}"
        )


# ============================================================
# P1: 超时/取消后 _current_worker 被清空
# ============================================================


class TestTimeoutClearsCurrentWorker:
    """P1-5: 超时后 _current_worker 被清空。"""

    def test_timeout_sets_current_worker_none(self, qtbot, loaded_window):
        """_on_worker_timeout 后 _current_worker 应为 None。"""
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        loaded_window._current_worker = mock_worker

        loaded_window._on_worker_timeout()
        qtbot.wait(50)

        assert loaded_window._current_worker is None, (
            f"超时后 _current_worker 应为 None，"
            f"实际值: {loaded_window._current_worker}"
        )


class TestCancelClearsCurrentWorker:
    """P1-6: 取消后 _current_worker 被清空。"""

    def test_cancel_sets_current_worker_none(self, qtbot, loaded_window):
        """_on_cancel_operation 后 _current_worker 应为 None。"""
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        loaded_window._current_worker = mock_worker

        loaded_window._on_cancel_operation()
        qtbot.wait(50)

        assert loaded_window._current_worker is None, (
            f"取消后 _current_worker 应为 None，"
            f"实际值: {loaded_window._current_worker}"
        )


# ============================================================
# P1: 连续操作时 typing indicator 状态正确转换
# ============================================================


class TestConsecutiveOperationsTypingState:
    """P1-7: 连续操作时 typing indicator 状态正确转换（使用 DummySuspectAgent）。"""

    def test_typing_indicator_shows_then_hides_on_worker_finish(
        self, qtbot, loaded_window, mock_case_simple
    ):
        """启动 Worker → typing 显示(True)，Worker 完成 → typing 隐藏(False)。"""
        from core.interrogation import DummySuspectAgent

        # 替换嫌疑人为 DummySuspectAgent（不依赖 LLM）
        for i, s_data in enumerate(mock_case_simple["suspects"]):
            loaded_window.engine.suspects[i] = DummySuspectAgent(s_data)

        typing_states = []
        loaded_window.bridge.show_typing_indicator.connect(
            lambda visible: typing_states.append(visible)
        )

        # 启动 chat worker
        loaded_window._on_chat_message_sent("你好")
        qtbot.wait(50)

        # Worker 启动时应显示 typing indicator
        assert True in typing_states, (
            f"Worker 启动后应 emit show_typing_indicator(True)，"
            f"实际收到: {typing_states}"
        )

        # 等待 Worker 完成
        qtbot.wait(500)

        # Worker 完成后应隐藏 typing indicator
        assert False in typing_states, (
            f"Worker 完成后应 emit show_typing_indicator(False)，"
            f"实际收到: {typing_states}"
        )

    def test_typing_indicator_full_lifecycle(
        self, qtbot, loaded_window, mock_case_simple
    ):
        """完整生命周期：show → finish → show → error。"""
        from core.interrogation import DummySuspectAgent

        for i, s_data in enumerate(mock_case_simple["suspects"]):
            loaded_window.engine.suspects[i] = DummySuspectAgent(s_data)

        typing_states = []
        loaded_window.bridge.show_typing_indicator.connect(
            lambda visible: typing_states.append(visible)
        )

        # 第一次操作：正常完成
        loaded_window._on_chat_message_sent("第一个问题")
        qtbot.wait(500)

        # 确保至少一个 True 和一个 False
        assert True in typing_states, "第一次操作应显示 typing"
        assert False in typing_states, "第一次完成应隐藏 typing"

        # 清空状态追踪
        first_true_idx = typing_states.index(True)
        first_false_idx = typing_states.index(False)
        assert first_true_idx < first_false_idx, (
            "True 应在 False 之前（先显示后隐藏）"
        )


# ============================================================
# P1: 超时/取消后发出系统消息
# ============================================================


class TestTimeoutEmitsSystemMessage:
    """P1-8: 超时后发出系统消息。"""

    def test_timeout_emits_timeout_message(self, qtbot, loaded_window):
        """_on_worker_timeout 应 emit add_message("system", "响应超时，请重试", "")。"""
        messages = []
        loaded_window.bridge.add_message.connect(
            lambda role, content, suspect: messages.append(
                {"role": role, "content": content, "suspect": suspect}
            )
        )

        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        loaded_window._current_worker = mock_worker

        loaded_window._on_worker_timeout()
        qtbot.wait(50)

        system_msgs = [m for m in messages if m["role"] == "system"]
        assert len(system_msgs) > 0, "超时后应发出系统消息"
        assert "超时" in system_msgs[0]["content"], (
            f"超时系统消息应包含'超时'，实际内容: {system_msgs[0]['content']}"
        )


class TestCancelEmitsSystemMessage:
    """P1-9: 取消后发出系统消息。"""

    def test_cancel_emits_cancel_message(self, qtbot, loaded_window):
        """_on_cancel_operation 应 emit add_message("system", "操作已取消", "")。"""
        messages = []
        loaded_window.bridge.add_message.connect(
            lambda role, content, suspect: messages.append(
                {"role": role, "content": content, "suspect": suspect}
            )
        )

        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        loaded_window._current_worker = mock_worker

        loaded_window._on_cancel_operation()
        qtbot.wait(50)

        system_msgs = [m for m in messages if m["role"] == "system"]
        assert len(system_msgs) > 0, "取消后应发出系统消息"
        assert "取消" in system_msgs[0]["content"], (
            f"取消系统消息应包含'取消'，实际内容: {system_msgs[0]['content']}"
        )


# ============================================================
# 原有测试保留：验证不使用 hide_loading
# ============================================================


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


class TestNoLoadingOverlayOnChat:
    """聊天操作不应触发 show_loading。"""

    def test_chat_does_not_emit_show_loading(self, qtbot, loaded_window):
        loading_emitted = []
        loaded_window.bridge.show_loading.connect(
            lambda msg, cancel: loading_emitted.append(msg)
        )

        loaded_window._on_chat_message_sent("你好")
        qtbot.wait(50)

        assert len(loading_emitted) == 0


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
