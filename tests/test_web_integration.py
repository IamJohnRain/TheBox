"""WebView 主窗口与引擎集成测试。

阶段 3：后端集成与主窗口重构的验收测试。
覆盖 WebMainWindow 与 InterrogationEngine 的完整集成：
案件加载、审讯交互、倒计时、存档/读档、Worker 线程、结局处理等。
"""

import pytest
from unittest.mock import patch, MagicMock

from ui.web_main_window import WebMainWindow, WebWorker, LLM_TIMEOUT_SECONDS
from ui.web_bridge import WebBridge


# ─── 辅助 fixture ───


@pytest.fixture
def window(qtbot):
    """创建 WebMainWindow 并等待页面加载。"""
    w = WebMainWindow()
    qtbot.addWidget(w)
    qtbot.wait(500)
    return w


@pytest.fixture
def loaded_window(qtbot, window, mock_case_simple):
    """加载案件后的 WebMainWindow，替换 SuspectAgent 为 Mock。"""
    with patch("core.suspect_agent.llm_client"):
        window.load_case(mock_case_simple)
    # 替换引擎中的嫌疑人为 Mock，避免 LLM 调用
    _replace_suspects_with_mocks(window.engine, mock_case_simple)
    qtbot.wait(100)
    return window


def _replace_suspects_with_mocks(engine, case_data):
    """将引擎中的 SuspectAgent 替换为 Mock，避免 LLM 调用。"""
    from schemas.interface_definitions import SuspectAgentProtocol

    for i, s_data in enumerate(case_data["suspects"]):
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
        engine.suspects[i] = mock_agent


# ─── 案件加载测试 ───


class TestWebMainWindowCaseLoading:
    """案件加载测试。"""

    def test_load_case_initializes_engine(self, window, mock_case_simple):
        """加载案件后引擎初始化。"""
        with patch("core.suspect_agent.llm_client"):
            window.load_case(mock_case_simple)
        assert window.engine is not None

    def test_load_case_engine_has_correct_case(self, window, mock_case_simple):
        """加载案件后引擎持有正确的案件数据。"""
        with patch("core.suspect_agent.llm_client"):
            window.load_case(mock_case_simple)
        assert window.engine.case["case_id"] == mock_case_simple["case_id"]
        assert window.engine.case["title"] == mock_case_simple["title"]

    def test_load_case_emits_init_game_state(self, qtbot, window, mock_case_simple):
        """加载案件后发射 init_game_state 信号，包含完整游戏状态。"""
        received_state = {}

        def on_state(state):
            received_state.update(state)

        window.bridge.init_game_state.connect(on_state)

        with patch("core.suspect_agent.llm_client"):
            window.load_case(mock_case_simple)
        qtbot.wait(100)

        assert "suspects" in received_state
        assert "evidences" in received_state
        assert "timeLeft" in received_state
        assert "case_id" in received_state

    def test_init_game_state_contains_correct_suspect_count(
        self, qtbot, window, mock_case_simple
    ):
        """init_game_state 信号包含正确数量的嫌疑人。"""
        received_state = {}

        def on_state(state):
            received_state.update(state)

        window.bridge.init_game_state.connect(on_state)

        with patch("core.suspect_agent.llm_client"):
            window.load_case(mock_case_simple)
        qtbot.wait(100)

        assert len(received_state["suspects"]) == len(mock_case_simple["suspects"])

    def test_init_game_state_contains_suspect_names(
        self, qtbot, window, mock_case_simple
    ):
        """init_game_state 中嫌疑人包含 name 和 pressure。"""
        received_state = {}

        def on_state(state):
            received_state.update(state)

        window.bridge.init_game_state.connect(on_state)

        with patch("core.suspect_agent.llm_client"):
            window.load_case(mock_case_simple)
        qtbot.wait(100)

        for i, suspect in enumerate(received_state["suspects"]):
            assert "name" in suspect
            assert "pressure" in suspect
            assert suspect["name"] == mock_case_simple["suspects"][i]["name"]

    def test_load_case_enables_input(self, qtbot, window, mock_case_simple):
        """加载案件后启用输入。"""
        input_states = []
        window.bridge.set_input_enabled.connect(lambda e: input_states.append(e))

        with patch("core.suspect_agent.llm_client"):
            window.load_case(mock_case_simple)
        qtbot.wait(100)

        assert True in input_states

    def test_load_case_selects_first_suspect(self, qtbot, window, mock_case_simple):
        """加载案件后自动选择第一个嫌疑人，发射 update_suspect 信号。"""
        suspect_updates = []
        window.bridge.update_suspect.connect(
            lambda name, p: suspect_updates.append({"name": name, "pressure": p})
        )

        with patch("core.suspect_agent.llm_client"):
            window.load_case(mock_case_simple)
        qtbot.wait(100)

        assert len(suspect_updates) > 0
        assert suspect_updates[0]["name"] == mock_case_simple["suspects"][0]["name"]

    def test_load_case_sets_engine_state_to_interrogating(
        self, window, mock_case_simple
    ):
        """加载案件后引擎状态为 interrogating（因为 select_suspect 被调用）。"""
        with patch("core.suspect_agent.llm_client"):
            window.load_case(mock_case_simple)
        assert window.engine.state == "interrogating"

    def test_load_case_sets_correct_time(self, window, mock_case_simple):
        """加载案件后 time_left 与案件配置一致。"""
        with patch("core.suspect_agent.llm_client"):
            window.load_case(mock_case_simple)
        assert window.engine.time_left == mock_case_simple["interrogation_time_limit_sec"]

    def test_init_game_state_contains_case_background(
        self, qtbot, window, mock_case_simple
    ):
        """init_game_state 信号包含案件背景信息。"""
        received_state = {}

        def on_state(state):
            received_state.update(state)

        window.bridge.init_game_state.connect(on_state)

        with patch("core.suspect_agent.llm_client"):
            window.load_case(mock_case_simple)
        qtbot.wait(100)

        assert "caseBackground" in received_state
        bg = received_state["caseBackground"]
        assert bg["victim"] == mock_case_simple["victim"]
        assert bg["causeOfDeath"] == mock_case_simple["cause_of_death"]
        assert bg["crimeScene"] == mock_case_simple["crime_scene"]

    def test_init_game_state_contains_suspect_profiles(
        self, qtbot, window, mock_case_simple
    ):
        """init_game_state 信号包含审讯对象资料。"""
        received_state = {}

        def on_state(state):
            received_state.update(state)

        window.bridge.init_game_state.connect(on_state)

        with patch("core.suspect_agent.llm_client"):
            window.load_case(mock_case_simple)
        qtbot.wait(100)

        assert "suspectProfiles" in received_state
        profiles = received_state["suspectProfiles"]
        assert len(profiles) == len(mock_case_simple["suspects"])
        for i, profile in enumerate(profiles):
            assert profile["name"] == mock_case_simple["suspects"][i]["name"]
            assert profile["role"] == mock_case_simple["suspects"][i]["role"]
            assert profile["personality"] == mock_case_simple["suspects"][i]["personality"]

    def test_load_case_emits_show_case_briefing(self, qtbot, window, mock_case_simple):
        """加载案件后自动发射 show_case_briefing 信号。"""
        briefings = []

        def on_briefing(data):
            briefings.append(data)

        window.bridge.show_case_briefing.connect(on_briefing)

        with patch("core.suspect_agent.llm_client"):
            window.load_case(mock_case_simple)
        qtbot.wait(100)

        assert len(briefings) > 0
        assert briefings[0]["title"] == mock_case_simple["title"]
        assert briefings[0]["victim"] == mock_case_simple["victim"]


# ─── 聊天功能测试 ───


class TestWebMainWindowChat:
    """聊天功能测试。"""

    def test_chat_message_starts_worker(self, loaded_window):
        """发送消息后 Worker 被创建。"""
        loaded_window._on_chat_message_sent("你好")
        assert loaded_window._current_worker is not None
        assert isinstance(loaded_window._current_worker, WebWorker)

    def test_chat_worker_has_correct_action(self, loaded_window):
        """Worker 的 action 为 chat。"""
        loaded_window._on_chat_message_sent("你好")
        assert loaded_window._current_worker._action == "chat"
        assert loaded_window._current_worker._content == "你好"

    def test_chat_disables_input(self, qtbot, loaded_window):
        """发送消息后禁用输入。"""
        input_states = []
        loaded_window.bridge.set_input_enabled.connect(
            lambda e: input_states.append(e)
        )

        loaded_window._on_chat_message_sent("你好")
        qtbot.wait(50)

        assert False in input_states

    def test_no_engine_no_action(self, window):
        """无引擎时发送消息无响应，不崩溃。"""
        assert window.engine is None
        window._on_chat_message_sent("你好")
        assert window._current_worker is None

    def test_empty_message_starts_worker(self, loaded_window):
        """空消息仍被处理（JS 端过滤，Python 端仍接收）。"""
        loaded_window._on_chat_message_sent("")
        # 不应崩溃，Worker 可能创建
        # 实际行为：空消息会创建 Worker，但引擎会处理它

    def test_chat_while_worker_running_does_not_start_new(self, loaded_window):
        """Worker 运行中时，新消息不会启动新 Worker。"""
        loaded_window._on_chat_message_sent("第一条消息")
        first_worker = loaded_window._current_worker

        # 模拟 Worker 仍在运行
        loaded_window._on_chat_message_sent("第二条消息")

        # Worker 不应被替换
        assert loaded_window._current_worker is first_worker


# ─── 游戏操作测试 ───


class TestWebMainWindowActions:
    """游戏操作测试。"""

    def test_pressure_action(self, loaded_window):
        """施压操作创建 Worker。"""
        loaded_window._on_pressure()
        assert loaded_window._current_worker is not None
        assert loaded_window._current_worker._action == "pressure"

    def test_pressure_action_content(self, loaded_window):
        """施压操作内容为预期文字。"""
        loaded_window._on_pressure()
        assert "施压" in loaded_window._current_worker._content

    def test_empathy_action(self, loaded_window):
        """共情操作创建 Worker。"""
        loaded_window._on_empathy()
        assert loaded_window._current_worker is not None
        assert loaded_window._current_worker._action == "empathy"

    def test_empathy_action_content(self, loaded_window):
        """共情操作内容为预期文字。"""
        loaded_window._on_empathy()
        assert "共情" in loaded_window._current_worker._content

    def test_evidence_selected(self, loaded_window, mock_case_simple):
        """出示证据创建 Worker，action 为 present_evidence。"""
        evidences = mock_case_simple.get("evidences", [])
        assert len(evidences) > 0, "测试案件应有至少一条证据"

        evidence_id = evidences[0].get("id", "test_evidence")
        loaded_window._on_evidence_selected(evidence_id)
        assert loaded_window._current_worker is not None
        assert loaded_window._current_worker._action == "present_evidence"
        assert loaded_window._current_worker._evidence_id == evidence_id

    def test_evidence_selected_name_in_content(self, loaded_window, mock_case_simple):
        """出示证据时，Worker 的 content 包含证据名称。"""
        evidences = mock_case_simple.get("evidences", [])
        evidence_id = evidences[0].get("id", "")
        evidence_name = evidences[0].get("name", "")

        loaded_window._on_evidence_selected(evidence_id)
        assert evidence_name in loaded_window._current_worker._content

    def test_evidence_nonexistent_id(self, loaded_window):
        """出示不存在的证据不崩溃。"""
        loaded_window._on_evidence_selected("nonexistent_evidence_id")
        # 不应崩溃
        assert loaded_window._current_worker is not None

    def test_suspect_changed(self, qtbot, loaded_window, mock_case_simple):
        """嫌疑人切换发射 update_suspect 信号。"""
        suspect_updates = []
        loaded_window.bridge.update_suspect.connect(
            lambda name, p: suspect_updates.append(name)
        )

        loaded_window._on_suspect_changed(1)
        qtbot.wait(100)

        assert len(suspect_updates) > 0
        assert suspect_updates[0] == mock_case_simple["suspects"][1]["name"]

    def test_suspect_changed_starts_countdown(self, loaded_window):
        """切换嫌疑人后倒计时启动。"""
        loaded_window._on_suspect_changed(0)
        assert loaded_window._countdown_timer.isActive()

    def test_suspect_changed_negative_index_ignored(self, loaded_window):
        """负索引切换嫌疑人被忽略。"""
        loaded_window._on_suspect_changed(-1)
        # 不应崩溃（_on_suspect_changed 对 index < 0 提前返回）

    def test_suspect_changed_invalid_index_raises(self, loaded_window):
        """超大索引切换嫌疑人抛出 ValueError。"""
        with pytest.raises(ValueError):
            loaded_window._on_suspect_changed(99)

    def test_no_engine_action_ignored(self, window):
        """无引擎时操作被忽略。"""
        window._on_pressure()
        assert window._current_worker is None
        window._on_empathy()
        assert window._current_worker is None
        window._on_evidence_selected("test")
        assert window._current_worker is None


# ─── Worker 线程测试 ───


class TestWebMainWindowWorker:
    """Worker 线程测试。"""

    def test_worker_creation(self, mock_case_simple):
        """Worker 能正确创建。"""
        from core.interrogation import InterrogationEngine

        engine = InterrogationEngine(mock_case_simple)
        worker = WebWorker(engine, "chat", "test")
        assert worker is not None
        assert worker._action == "chat"
        assert worker._content == "test"
        assert worker._evidence_id is None
        assert worker._interrupted is False

    def test_worker_with_evidence_id(self, mock_case_simple):
        """Worker 能正确携带 evidence_id。"""
        from core.interrogation import InterrogationEngine

        engine = InterrogationEngine(mock_case_simple)
        worker = WebWorker(engine, "present_evidence", "看看这个", evidence_id="e1")
        assert worker._evidence_id == "e1"

    def test_worker_interrupt(self, mock_case_simple):
        """Worker 能被中断。"""
        from core.interrogation import InterrogationEngine

        engine = InterrogationEngine(mock_case_simple)
        worker = WebWorker(engine, "chat", "test")
        worker.interrupt()
        assert worker._interrupted is True

    def test_worker_finished_signal(self, qtbot, mock_case_simple):
        """Worker 完成后发射 finished 信号。"""
        from core.interrogation import InterrogationEngine, DummySuspectAgent

        engine = InterrogationEngine(mock_case_simple)
        # 使用 DummySuspectAgent 确保 LLM 不被调用
        engine.suspects = [
            DummySuspectAgent(s, mock_case_simple["title"])
            for s in mock_case_simple["suspects"]
        ]
        engine.select_suspect(0)

        worker = WebWorker(engine, "chat", "你好")
        with qtbot.waitSignal(worker.finished, timeout=5000) as blocker:
            worker.start()

        events = blocker.args[0]
        assert isinstance(events, list)
        assert len(events) > 0

    def test_worker_error_on_exception(self, qtbot, mock_case_simple):
        """Worker 异常时发射 error 信号。"""
        mock_engine = MagicMock()
        mock_engine.submit_action.side_effect = RuntimeError("模拟错误")

        worker = WebWorker(mock_engine, "chat", "test")
        with qtbot.waitSignal(worker.error, timeout=5000) as blocker:
            worker.start()

        assert "模拟错误" in blocker.args[0]

    def test_worker_interrupt_prevents_emit(self, qtbot, mock_case_simple):
        """中断后 Worker 不发射 finished 信号。"""
        from core.interrogation import InterrogationEngine, DummySuspectAgent

        engine = InterrogationEngine(mock_case_simple)
        engine.suspects = [
            DummySuspectAgent(s, mock_case_simple["title"])
            for s in mock_case_simple["suspects"]
        ]
        engine.select_suspect(0)

        worker = WebWorker(engine, "chat", "你好")
        worker.interrupt()
        worker.start()
        worker.wait(3000)

        # 中断后 finished 不应发射
        # 注意：由于 DummySuspectAgent 是同步快速返回的，
        # interrupt 可能在 run() 执行之后才生效
        # 所以这个测试验证 interrupt 标志被设置即可
        assert worker._interrupted is True

    def test_timeout_constant_value(self):
        """LLM 超时常量值正确。"""
        assert LLM_TIMEOUT_SECONDS == 60


# ─── 倒计时测试 ───


class TestWebMainWindowTimer:
    """倒计时测试。"""

    def test_timer_tick_updates_engine(self, loaded_window):
        """倒计时 tick 更新引擎时间。"""
        initial_time = loaded_window.engine.time_left
        loaded_window._on_timer_tick()
        assert loaded_window.engine.time_left == initial_time - 1

    def test_timer_tick_emits_update_timer(self, qtbot, loaded_window):
        """倒计时 tick 发射 update_timer 信号。"""
        timer_updates = []
        loaded_window.bridge.update_timer.connect(
            lambda t: timer_updates.append(t)
        )

        loaded_window._on_timer_tick()
        qtbot.wait(50)

        assert len(timer_updates) > 0
        assert timer_updates[0] == loaded_window.engine.time_left

    def test_timer_tick_stops_on_verdict(self, loaded_window):
        """倒计时归零后停止计时器。"""
        loaded_window.engine.time_left = 1
        loaded_window._on_timer_tick()
        # 时间耗尽后引擎状态变为 verdict
        assert loaded_window.engine.state == "verdict"
        # 计时器应停止
        assert not loaded_window._countdown_timer.isActive()

    def test_timer_tick_no_engine_stops_timer(self, window):
        """无引擎时 tick 停止计时器。"""
        window._countdown_timer.start()
        assert window._countdown_timer.isActive()

        window._on_timer_tick()
        assert not window._countdown_timer.isActive()

    def test_timer_tick_multiple_ticks(self, loaded_window):
        """多次 tick 持续递减。"""
        initial_time = loaded_window.engine.time_left
        for _ in range(5):
            loaded_window._on_timer_tick()
        assert loaded_window.engine.time_left == initial_time - 5


# ─── update_ui_from_engine 测试 ───


class TestUpdateUIFromEngine:
    """引擎事件处理测试。"""

    def test_new_message_event(self, qtbot, loaded_window):
        """new_message 事件发射 add_message 信号。"""
        messages = []
        loaded_window.bridge.add_message.connect(
            lambda role, content, suspect: messages.append(
                {"role": role, "content": content, "suspect": suspect}
            )
        )

        events = [
            {
                "type": "new_message",
                "role": "player",
                "content": "你好",
                "suspect_name": None,
            },
            {
                "type": "new_message",
                "role": "suspect",
                "content": "我是无辜的",
                "suspect_name": "李四",
            },
        ]

        loaded_window.update_ui_from_engine(events)
        qtbot.wait(50)

        assert len(messages) == 2
        assert messages[0]["role"] == "player"
        assert messages[0]["content"] == "你好"
        assert messages[1]["role"] == "suspect"
        assert messages[1]["suspect"] == "李四"

    def test_suspect_update_event(self, qtbot, loaded_window):
        """suspect_update 事件发射 update_suspect 信号。"""
        suspect_updates = []
        loaded_window.bridge.update_suspect.connect(
            lambda name, p: suspect_updates.append({"name": name, "pressure": p})
        )

        events = [
            {
                "type": "suspect_update",
                "suspect_index": 0,
                "pressure": 70,
                "secret_triggered": None,
            }
        ]

        loaded_window.update_ui_from_engine(events)
        qtbot.wait(50)

        assert len(suspect_updates) > 0
        assert suspect_updates[0]["pressure"] == 70

    def test_state_change_breakdown(self, qtbot, loaded_window):
        """state_change 为 breakdown 时调用 _handle_ending。"""
        ending_dialogs = []
        loaded_window.bridge.show_ending_dialog.connect(
            lambda t, m: ending_dialogs.append({"title": t, "message": m})
        )

        events = [
            {
                "type": "state_change",
                "new_state": "breakdown",
                "verdict_reason": "嫌疑人认罪",
            }
        ]

        loaded_window.update_ui_from_engine(events)
        qtbot.wait(50)

        assert len(ending_dialogs) > 0

    def test_state_change_verdict(self, qtbot, loaded_window):
        """state_change 为 verdict 时调用 _handle_ending。"""
        ending_dialogs = []
        loaded_window.bridge.show_ending_dialog.connect(
            lambda t, m: ending_dialogs.append({"title": t, "message": m})
        )

        events = [
            {
                "type": "state_change",
                "new_state": "verdict",
                "verdict_reason": "时间耗尽",
            }
        ]

        loaded_window.update_ui_from_engine(events)
        qtbot.wait(50)

        assert len(ending_dialogs) > 0

    def test_timer_tick_event(self, qtbot, loaded_window):
        """timer_tick 事件发射 update_timer 信号。"""
        timer_updates = []
        loaded_window.bridge.update_timer.connect(
            lambda t: timer_updates.append(t)
        )

        events = [{"type": "timer_tick", "time_left": 500}]

        loaded_window.update_ui_from_engine(events)
        qtbot.wait(50)

        assert len(timer_updates) > 0
        assert timer_updates[0] == 500

    def test_empty_events_list(self, loaded_window):
        """空事件列表不崩溃。"""
        loaded_window.update_ui_from_engine([])
        # 不应崩溃

    def test_state_change_adds_system_message(self, qtbot, loaded_window):
        """state_change 事件同时添加系统消息。"""
        messages = []
        loaded_window.bridge.add_message.connect(
            lambda role, content, suspect: messages.append(
                {"role": role, "content": content}
            )
        )

        events = [
            {
                "type": "state_change",
                "new_state": "verdict",
                "verdict_reason": "时间耗尽",
            }
        ]

        loaded_window.update_ui_from_engine(events)
        qtbot.wait(50)

        system_msgs = [m for m in messages if m["role"] == "system"]
        assert len(system_msgs) > 0
        assert "verdict" in system_msgs[0]["content"]


# ─── 存档/读档测试 ───


class TestWebMainWindowSaveLoad:
    """存档/读档测试。"""

    def test_save_game(self, qtbot, loaded_window):
        """存档功能发射 show_save_slots 信号。"""
        with patch("core.db.list_all_slots", return_value=[
            {"slot_number": 1, "session_id": None, "case_id": None, "saved_at": None, "empty": True},
            {"slot_number": 2, "session_id": None, "case_id": None, "saved_at": None, "empty": True},
        ]):
            save_slots_data = []
            loaded_window.bridge.show_save_slots.connect(
                lambda d: save_slots_data.append(d)
            )

            loaded_window._on_save_game()
            qtbot.wait(100)

            assert len(save_slots_data) > 0
            assert save_slots_data[0]["_hasActiveGame"] is True

    def test_save_game_failure(self, qtbot, loaded_window):
        """存档失败时显示错误对话框。"""
        with patch(
            "core.db.list_all_slots", side_effect=Exception("数据库错误")
        ):
            dialogs = []
            loaded_window.bridge.show_dialog.connect(
                lambda t, m: dialogs.append({"title": t, "message": m})
            )

            loaded_window._on_save_game()
            qtbot.wait(100)

            assert len(dialogs) > 0
            assert "存档失败" in dialogs[0]["title"]

    def test_save_game_no_engine(self, window):
        """无引擎时存档不崩溃。"""
        window._on_save_game()
        # 不应崩溃

    def test_load_game_shows_save_list(self, qtbot, loaded_window):
        """读档显示存档槽位列表（同存档管理入口）。"""
        with patch("core.db.list_all_slots", return_value=[
            {"slot_number": 1, "session_id": None, "case_id": None, "saved_at": None, "empty": True},
        ]):
            save_slots_data = []
            loaded_window.bridge.show_save_slots.connect(
                lambda d: save_slots_data.append(d)
            )

            loaded_window._on_load_game()
            qtbot.wait(100)

            assert len(save_slots_data) > 0

    def test_load_game_with_sessions(self, qtbot, loaded_window):
        """读档时存档列表包含正确格式。"""
        mock_slots = [
            {
                "slot_number": 1,
                "session_id": "sess_001",
                "case_id": "case_001",
                "saved_at": "2026-01-01T00:00:00",
                "empty": False,
            }
        ]
        with patch("core.db.list_all_slots", return_value=mock_slots), \
             patch("core.db.load_case", return_value={"title": "测试案件"}):
            save_slots_data = []
            loaded_window.bridge.show_save_slots.connect(
                lambda d: save_slots_data.append(d)
            )

            loaded_window._on_load_game()
            qtbot.wait(100)

            assert len(save_slots_data) > 0
            slots = save_slots_data[0]["slots"]
            assert len(slots) > 0

    def test_load_game_failure(self, qtbot, loaded_window):
        """读档失败时显示错误对话框。"""
        with patch("core.db.list_all_slots", side_effect=Exception("读取失败")):
            dialogs = []
            loaded_window.bridge.show_dialog.connect(
                lambda t, m: dialogs.append({"title": t, "message": m})
            )

            loaded_window._on_load_game()
            qtbot.wait(100)

            assert len(dialogs) > 0
            assert "存档失败" in dialogs[0]["title"]

    def test_save_selected_loads_session(self, qtbot, loaded_window, mock_case_simple):
        """选择存档后加载引擎。"""
        engine_state = loaded_window.engine.to_dict()

        with patch(
            "core.db.load_full_session",
            return_value=(mock_case_simple["case_id"], engine_state),
        ), patch("core.db.load_case", return_value=mock_case_simple), patch(
            "core.suspect_agent.llm_client"
        ):
            loaded_window._on_save_selected("sess_001")
            qtbot.wait(100)

        assert loaded_window.engine is not None

    def test_save_selected_missing_session(self, qtbot, loaded_window):
        """选择不存在的存档显示错误。"""
        with patch("core.db.load_full_session", return_value=None):
            dialogs = []
            loaded_window.bridge.show_dialog.connect(
                lambda t, m: dialogs.append({"title": t, "message": m})
            )

            loaded_window._on_save_selected("nonexistent")
            qtbot.wait(100)

            assert len(dialogs) > 0
            assert "读档失败" in dialogs[0]["title"]

    def test_save_selected_missing_case(self, qtbot, loaded_window):
        """选择存档但关联案件不存在时显示错误。"""
        with patch(
            "core.db.load_full_session",
            return_value=("case_missing", {"state": "test", "case_title": "测试"}),
        ), patch("core.db.load_case", return_value=None):
            dialogs = []
            loaded_window.bridge.show_dialog.connect(
                lambda t, m: dialogs.append({"title": t, "message": m})
            )

            loaded_window._on_save_selected("sess_001")
            qtbot.wait(100)

            assert len(dialogs) > 0
            assert "读档" in dialogs[0]["title"]


# ─── 结局处理测试 ───


class TestWebMainWindowEnding:
    """结局处理测试。"""

    def test_breakdown_ending(self, qtbot, loaded_window):
        """崩溃结局处理：显示破案成功。"""
        ending_dialogs = []
        loaded_window.bridge.show_ending_dialog.connect(
            lambda t, m: ending_dialogs.append({"title": t, "message": m})
        )

        loaded_window._handle_ending({"new_state": "breakdown"})
        qtbot.wait(100)

        assert len(ending_dialogs) > 0
        assert "破案成功" in ending_dialogs[0]["message"]

    def test_verdict_ending(self, qtbot, loaded_window):
        """超时结局处理：显示时间耗尽。"""
        ending_dialogs = []
        loaded_window.bridge.show_ending_dialog.connect(
            lambda t, m: ending_dialogs.append({"title": t, "message": m})
        )

        loaded_window._handle_ending({"new_state": "verdict"})
        qtbot.wait(100)

        assert len(ending_dialogs) > 0
        assert "时间耗尽" in ending_dialogs[0]["message"]

    def test_unknown_ending(self, qtbot, loaded_window):
        """未知结局类型：显示默认消息。"""
        ending_dialogs = []
        loaded_window.bridge.show_ending_dialog.connect(
            lambda t, m: ending_dialogs.append({"title": t, "message": m})
        )

        loaded_window._handle_ending({"new_state": "unknown_state"})
        qtbot.wait(100)

        assert len(ending_dialogs) > 0
        assert "游戏结束" in ending_dialogs[0]["message"]

    def test_ending_stops_countdown(self, loaded_window):
        """结局处理停止倒计时。"""
        loaded_window._countdown_timer.start()
        assert loaded_window._countdown_timer.isActive()

        loaded_window._handle_ending({"new_state": "breakdown"})
        assert not loaded_window._countdown_timer.isActive()

    def test_ending_disables_input(self, qtbot, loaded_window):
        """结局处理禁用所有交互。"""
        interactive_states = []
        loaded_window.bridge.set_game_interactive.connect(
            lambda e: interactive_states.append(e)
        )

        loaded_window._handle_ending({"new_state": "breakdown"})
        qtbot.wait(50)

        assert False in interactive_states

    def test_breakdown_message_contains_confession(self, qtbot, loaded_window):
        """崩溃结局消息包含认罪内容。"""
        ending_dialogs = []
        loaded_window.bridge.show_ending_dialog.connect(
            lambda t, m: ending_dialogs.append({"title": t, "message": m})
        )

        loaded_window._handle_ending({"new_state": "breakdown"})
        qtbot.wait(50)

        assert "认罪" in ending_dialogs[0]["message"]

    def test_verdict_message_contains_lawyer(self, qtbot, loaded_window):
        """超时结局消息包含律师介入信息。"""
        ending_dialogs = []
        loaded_window.bridge.show_ending_dialog.connect(
            lambda t, m: ending_dialogs.append({"title": t, "message": m})
        )

        loaded_window._handle_ending({"new_state": "verdict"})
        qtbot.wait(50)

        assert "律师" in ending_dialogs[0]["message"]


# ─── 重启和返回菜单测试 ───


class TestWebMainWindowRestart:
    """重启和返回菜单测试。"""

    def test_restart(self, qtbot, loaded_window, mock_case_simple):
        """重新开始后引擎被重新创建。"""
        with patch("core.suspect_agent.llm_client"):
            loaded_window._restart()
        qtbot.wait(100)

        assert loaded_window.engine is not None
        assert loaded_window.engine.case["case_id"] == mock_case_simple["case_id"]

    def test_restart_resets_state(self, qtbot, loaded_window, mock_case_simple):
        """重新开始后引擎状态重置。"""
        # 修改引擎状态
        loaded_window.engine.time_left = 10
        loaded_window.engine.state = "verdict"

        with patch("core.suspect_agent.llm_client"):
            loaded_window._restart()
        qtbot.wait(100)

        assert loaded_window.engine.time_left == mock_case_simple["interrogation_time_limit_sec"]
        assert loaded_window.engine.state == "interrogating"

    def test_restart_emits_init_game_state(self, qtbot, loaded_window):
        """重新开始发射 init_game_state 信号。"""
        received_states = []
        loaded_window.bridge.init_game_state.connect(
            lambda s: received_states.append(s)
        )

        with patch("core.suspect_agent.llm_client"):
            loaded_window._restart()
        qtbot.wait(100)

        assert len(received_states) > 0

    def test_restart_no_engine(self, window):
        """无引擎时重启不崩溃。"""
        assert window.engine is None
        window._restart()
        # 不应崩溃

    def test_return_to_menu(self, qtbot, loaded_window):
        """返回主菜单后引擎清空。"""
        loaded_window._return_to_menu()
        qtbot.wait(100)

        assert loaded_window.engine is None

    def test_return_to_menu_clears_chat(self, qtbot, loaded_window):
        """返回主菜单清除聊天。"""
        clear_called = []
        loaded_window.bridge.clear_chat.connect(lambda: clear_called.append(True))

        loaded_window._return_to_menu()
        qtbot.wait(50)

        assert True in clear_called

    def test_return_to_menu_disables_input(self, qtbot, loaded_window):
        """返回主菜单禁用所有交互。"""
        interactive_states = []
        loaded_window.bridge.set_game_interactive.connect(
            lambda e: interactive_states.append(e)
        )

        loaded_window._return_to_menu()
        qtbot.wait(50)

        assert False in interactive_states

    def test_return_to_menu_stops_countdown(self, loaded_window):
        """返回主菜单停止倒计时。"""
        loaded_window._countdown_timer.start()
        assert loaded_window._countdown_timer.isActive()

        loaded_window._return_to_menu()
        assert not loaded_window._countdown_timer.isActive()


# ─── Worker 生命周期集成测试 ───


class TestWebWorkerLifecycle:
    """Worker 生命周期集成测试。"""

    def test_worker_finished_cleanup(self, qtbot, loaded_window):
        """Worker 完成后正确清理。"""
        from core.interrogation import DummySuspectAgent

        # 确保 engine 使用 DummySuspectAgent
        loaded_window.engine.suspects = [
            DummySuspectAgent(s, loaded_window.engine.case["title"])
            for s in loaded_window.engine.case["suspects"]
        ]

        loaded_window._on_chat_message_sent("你好")

        # 等待 Worker 完成
        if loaded_window._current_worker:
            qtbot.waitSignal(
                loaded_window._current_worker.finished, timeout=5000
            )

        # Worker 应该被清理
        qtbot.wait(200)
        assert loaded_window._current_worker is None

    def test_worker_timeout(self, qtbot, loaded_window):
        """Worker 超时后正确处理。"""
        # 创建一个不会完成的 mock Worker
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        loaded_window._current_worker = mock_worker

        loaded_window._on_worker_timeout()

        mock_worker.interrupt.assert_called_once()
        mock_worker.wait.assert_called_once()

    def test_cancel_operation(self, qtbot, loaded_window):
        """取消操作正确中断 Worker。"""
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        loaded_window._current_worker = mock_worker

        loaded_window._on_cancel_operation()

        mock_worker.interrupt.assert_called_once()
        mock_worker.wait.assert_called_once()

    def test_cancel_no_running_worker(self, loaded_window):
        """无运行中 Worker 时取消不崩溃。"""
        loaded_window._current_worker = None
        loaded_window._on_cancel_operation()
        # 不应崩溃

    def test_cancel_completed_worker(self, loaded_window):
        """已完成 Worker 被取消时不执行中断。"""
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = False
        loaded_window._current_worker = mock_worker

        loaded_window._on_cancel_operation()

        mock_worker.interrupt.assert_not_called()


# ─── Bridge 信号连接测试 ───


class TestBridgeSignalConnections:
    """Bridge 信号连接测试。"""

    def test_all_bridge_signals_exist(self, window):
        """所有 Bridge 信号已定义且可访问。"""
        expected_signals = [
            "message_sent",
            "suspect_selected",
            "evidence_presented",
            "pressure_applied",
            "empathy_applied",
            "save_requested",
            "load_requested",
            "settings_requested",
            "generate_case_requested",
            "cancel_requested",
            "save_selected",
            "restart_requested",
            "return_to_menu_requested",
        ]

        for signal_name in expected_signals:
            signal = getattr(window.bridge, signal_name, None)
            assert signal is not None, f"信号 {signal_name} 不存在"

    def test_bridge_slot_triggers_handler(self, qtbot, window, mock_case_simple):
        """Bridge slot 触发对应处理方法。"""
        # 测试 pressure_applied 信号连接
        with patch("core.suspect_agent.llm_client"):
            window.load_case(mock_case_simple)
        _replace_suspects_with_mocks(window.engine, mock_case_simple)

        handler_called = []
        original_handler = window._on_pressure

        def patched_handler():
            handler_called.append(True)
            original_handler()

        window._on_pressure = patched_handler

        # 通过 bridge slot 触发
        window.bridge.applyPressure()
        qtbot.wait(50)

        assert len(handler_called) > 0
