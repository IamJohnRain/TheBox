"""Fix-1: 验证存档/读档功能完整修复。

P0 场景：
1. 存档列表为空时
2. saved_at 为空字符串时降级处理
3. saved_at 为非 ISO 格式时降级处理
4. saved_at 为 None 时降级处理

P1 场景：
5. 读档后聊天历史为空时无消息恢复
6. 读档后 current_suspect_index 正确保留
7. 读档后 state dict 中无 snake_case 键泄露
8. 存档后 case_title 丢失时降级
9. 读档后 clear_chat 在 init_game_state 之前发出
10. 存档时 engine.to_dict() 包含完整数据
"""

import pytest
import re
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
        mock_agent.fear = 50
        mock_agent.defiance = 50
        mock_agent.confession_level = 0
        mock_agent.respond.return_value = {
            "reply": "我是无辜的",
            "secret_triggered": None,
        }
        mock_agent.respond_evidence.return_value = {
            "reply": "我是无辜的",
            "secret_triggered": None,
        }
        window.engine.suspects[i] = mock_agent
    qtbot.wait(100)
    return window


# ============================================================
# P0: 存档列表为空时
# ============================================================


class TestEmptySessionList:
    """P0-1: 存档列表为空时。"""

    def test_empty_session_list_emits_empty_save_list(self, qtbot, loaded_window):
        """存档列表为空时应 emit show_save_list([]) 而非报错。"""
        with patch("core.db.list_sessions", return_value=[]):
            save_lists = []
            loaded_window.bridge.show_save_list.connect(
                lambda s: save_lists.append(s)
            )

            loaded_window._on_load_game()
            qtbot.wait(100)

            assert len(save_lists) > 0, "即使列表为空也应 emit show_save_list"
            assert save_lists[0] == [], (
                f"空列表应 emit show_save_list([])，实际值: {save_lists[0]}"
            )


# ============================================================
# P0: saved_at 降级处理
# ============================================================


class TestSavedAtEmptyString:
    """P0-2: saved_at 为空字符串时降级处理。"""

    def test_saved_at_empty_string_date_not_empty(self, qtbot, loaded_window, mock_case_simple):
        """saved_at 为空字符串时，date 应降级为空字符串而不崩溃。"""
        mock_sessions = [
            {
                "session_id": "sess_001",
                "case_id": mock_case_simple["case_id"],
                "saved_at": "",
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

            assert len(save_lists) > 0, "应正常 emit show_save_list"
            session = save_lists[0][0]
            assert "date" in session, "应包含 date 字段"
            # saved_at 为空字符串，date 应为空字符串（降级处理）
            assert session["date"] == "", (
                f"saved_at 为空时 date 应为空字符串，实际值: {session['date']}"
            )


class TestSavedAtNonISOFormat:
    """P0-3: saved_at 为非 ISO 格式时降级处理。"""

    def test_saved_at_non_iso_date_is_raw_value(self, qtbot, loaded_window, mock_case_simple):
        """saved_at 为非 ISO 格式时，date 应降级为原始字符串而不崩溃。"""
        mock_sessions = [
            {
                "session_id": "sess_001",
                "case_id": mock_case_simple["case_id"],
                "saved_at": "2026/05/03 14:30",
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

            assert len(save_lists) > 0, "应正常 emit show_save_list，不崩溃"
            session = save_lists[0][0]
            assert "date" in session
            # 非 ISO 格式降级为原始字符串
            assert session["date"] == "2026/05/03 14:30", (
                f"非 ISO 格式应降级为原始字符串，实际值: {session['date']}"
            )


class TestSavedAtNone:
    """P0-4: saved_at 为 None 时降级处理。"""

    def test_saved_at_none_no_crash(self, qtbot, loaded_window, mock_case_simple):
        """saved_at 为 None 时，应不崩溃并正常 emit show_save_list。"""
        mock_sessions = [
            {
                "session_id": "sess_001",
                "case_id": mock_case_simple["case_id"],
                "saved_at": None,
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

            assert len(save_lists) > 0, "应正常 emit show_save_list，不崩溃"
            session = save_lists[0][0]
            assert "date" in session, "应包含 date 字段"
            # saved_at=None → s.get("saved_at", "") returns None (key exists)
            # → dt.fromisoformat(None) raises TypeError → date_str = saved_at = None
            # This is the current behavior: date falls back to the raw value
            assert session["date"] is None or session["date"] == "", (
                f"saved_at 为 None 时 date 应降级，实际值: {session['date']}"
            )


# ============================================================
# P1: 读档后聊天历史为空时无消息恢复
# ============================================================


class TestLoadEmptyChatHistory:
    """P1-5: 读档后聊天历史为空时无消息恢复。"""

    def test_no_add_message_when_memory_empty(self, qtbot, loaded_window, mock_case_simple):
        """嫌疑人 memory 为空时，读档后不应 emit add_message。"""
        # 确保所有嫌疑人 memory 为空
        for s in loaded_window.engine.suspects:
            s.memory = []

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

            assert len(messages) == 0, (
                f"聊天历史为空时不应 emit add_message，实际: {messages}"
            )


# ============================================================
# P1: 读档后 current_suspect_index 正确保留
# ============================================================


class TestLoadPreservesCurrentSuspectIndex:
    """P1-6: 读档后 current_suspect_index 正确保留。"""

    def test_current_suspect_index_preserved(self, qtbot, loaded_window, mock_case_simple):
        """读档后 init_game_state 的 current_suspect_index 应与保存时一致。"""
        # 切换到第二个嫌疑人
        loaded_window.engine.current_suspect_index = 1

        engine_state = loaded_window.engine.to_dict()
        assert engine_state["current_suspect_index"] == 1

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
            assert state["current_suspect_index"] == 1, (
                f"current_suspect_index 应为 1，实际值: {state['current_suspect_index']}"
            )


# ============================================================
# P1: 读档后 state dict 中无 snake_case 键泄露
# ============================================================


class TestNoSnakeCaseLeakInState:
    """P1-7: 读档后 state dict 中无 snake_case 键泄露。"""

    def test_state_no_time_left_key(self, qtbot, loaded_window, mock_case_simple):
        """init_game_state 的 state dict 中不应包含 time_left（snake_case）。"""
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
            assert "time_left" not in state, (
                f"state 不应包含 snake_case 'time_left'，"
                f"实际字段: {list(state.keys())}"
            )

    def test_state_no_case_title_key(self, qtbot, loaded_window, mock_case_simple):
        """init_game_state 的 state dict 中不应包含 case_title（snake_case）。"""
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
            assert "case_title" not in state, (
                f"state 不应包含 snake_case 'case_title'，"
                f"实际字段: {list(state.keys())}"
            )


# ============================================================
# P1: 存档后 case_title 丢失时降级
# ============================================================


class TestSaveCaseTitleMissingFallback:
    """P1-8: 存档后 case_title 丢失时降级。"""

    def test_case_title_missing_fallback_to_unknown(self, qtbot, loaded_window):
        """engine.case 中无 title 时，存档对话框应显示 '未知案件'。"""
        # 移除 case title
        loaded_window.engine.case.pop("title", None)

        with patch("core.db.save_full_session"):
            dialogs = []
            loaded_window.bridge.show_dialog.connect(
                lambda t, m: dialogs.append({"title": t, "message": m})
            )

            loaded_window._on_save_game()
            qtbot.wait(100)

            assert len(dialogs) > 0
            assert "未知案件" in dialogs[0]["message"], (
                f"case_title 缺失时应降级为 '未知案件'，"
                f"实际内容: {dialogs[0]['message']}"
            )


# ============================================================
# P1: 读档后 clear_chat 在 init_game_state 之前发出
# ============================================================


class TestClearChatBeforeInitGameState:
    """P1-9: 读档后不再需要冗余 clear_chat 信号（BUG-1 修复）。"""

    def test_no_redundant_clear_chat_before_init_game_state(self, qtbot, loaded_window, mock_case_simple):
        """_on_save_selected 中不应再 emit clear_chat（switchSuspect 已处理清空逻辑）。"""
        engine_state = loaded_window.engine.to_dict()

        with patch("core.db.load_full_session",
                   return_value=(mock_case_simple["case_id"], engine_state)), \
             patch("core.db.load_case", return_value=mock_case_simple), \
             patch("core.suspect_agent.llm_client"):

            signal_order = []

            loaded_window.bridge.clear_chat.connect(
                lambda: signal_order.append("clear_chat")
            )
            loaded_window.bridge.init_game_state.connect(
                lambda s: signal_order.append("init_game_state")
            )

            loaded_window._on_save_selected("sess_001")
            qtbot.wait(100)

            assert "clear_chat" not in signal_order, (
                "BUG-1 修复: _on_save_selected 不应 emit clear_chat，"
                "switchSuspect 已处理清空逻辑，避免双重清空导致页面闪动"
            )
            assert "init_game_state" in signal_order, "应 emit init_game_state"


# ============================================================
# P1: 存档时 engine.to_dict() 包含完整数据
# ============================================================


class TestEngineToDictCompleteData:
    """P1-10: 存档时 engine.to_dict() 包含完整数据。"""

    def test_to_dict_contains_all_required_keys(self, loaded_window):
        """engine.to_dict() 应包含所有必要字段。"""
        state = loaded_window.engine.to_dict()

        required_keys = [
            "suspects_states",
            "presented_evidence_ids",
            "time_left",
            "current_suspect_index",
            "state",
        ]
        for key in required_keys:
            assert key in state, (
                f"engine.to_dict() 应包含 '{key}'，"
                f"实际字段: {list(state.keys())}"
            )

    def test_to_dict_suspects_states_complete(self, loaded_window):
        """每个 suspect state 应包含 name, pressure, memory。"""
        state = loaded_window.engine.to_dict()

        for i, suspect_state in enumerate(state["suspects_states"]):
            assert "name" in suspect_state, (
                f"suspect_states[{i}] 缺少 'name'"
            )
            assert "pressure" in suspect_state, (
                f"suspect_states[{i}] 缺少 'pressure'"
            )
            assert "memory" in suspect_state, (
                f"suspect_states[{i}] 缺少 'memory'"
            )

    def test_to_dict_time_left_matches_engine(self, loaded_window):
        """to_dict() 的 time_left 应与 engine.time_left 一致。"""
        state = loaded_window.engine.to_dict()
        assert state["time_left"] == loaded_window.engine.time_left

    def test_to_dict_current_suspect_index_matches(self, loaded_window):
        """to_dict() 的 current_suspect_index 应与 engine 一致。"""
        state = loaded_window.engine.to_dict()
        assert state["current_suspect_index"] == loaded_window.engine.current_suspect_index


# ============================================================
# 原有测试保留
# ============================================================


class TestSaveGameShowsCaseTitleAndTime:
    """存档成功提示应包含案件名称和格式化时间。"""

    def test_save_dialog_contains_case_title(self, qtbot, loaded_window, mock_case_simple):
        with patch("core.db.save_full_session"):
            dialogs = []
            loaded_window.bridge.show_dialog.connect(
                lambda t, m: dialogs.append({"title": t, "message": m})
            )

            loaded_window._on_save_game()
            qtbot.wait(100)

            assert len(dialogs) > 0
            assert mock_case_simple["title"] in dialogs[0]["message"]

    def test_save_dialog_contains_formatted_time(self, qtbot, loaded_window):
        with patch("core.db.save_full_session"):
            dialogs = []
            loaded_window.bridge.show_dialog.connect(
                lambda t, m: dialogs.append({"title": t, "message": m})
            )

            loaded_window._on_save_game()
            qtbot.wait(100)

            assert len(dialogs) > 0
            time_pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}"
            assert re.search(time_pattern, dialogs[0]["message"])


class TestLoadGameUsesCamelCaseState:
    """读档后 init_game_state 的 state dict 应使用 camelCase。"""

    def test_state_has_timeLeft_not_time_left(self, qtbot, loaded_window, mock_case_simple):
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
            assert "timeLeft" in state

    def test_state_has_caseTitle(self, qtbot, loaded_window, mock_case_simple):
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
            assert "caseTitle" in state
            assert state["caseTitle"] == mock_case_simple["title"]


class TestLoadGameRestoresChatHistory:
    """读档后应恢复每个嫌疑人的聊天历史。"""

    def test_load_restores_suspect_memory(self, qtbot, loaded_window, mock_case_simple):
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

            assert len(messages) > 0, "读档后应恢复聊天历史"

            player_msgs = [m for m in messages if m["role"] == "player" and "你在哪里" in m["content"]]
            assert len(player_msgs) > 0, "应恢复第一个嫌疑人的对话"

            suspect_msgs = [m for m in messages if m["role"] == "suspect" and "我在家" in m["content"]]
            assert len(suspect_msgs) > 0, "应恢复第一个嫌疑人的回复"
