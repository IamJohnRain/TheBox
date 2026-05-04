"""WebBridge 通信桥接测试。"""

import pytest
from PySide6.QtCore import QObject

from ui.web_bridge import WebBridge


class TestWebBridgeSignals:
    """WebBridge 信号定义测试。"""

    def test_bridge_is_qobject(self):
        """WebBridge 继承自 QObject。"""
        bridge = WebBridge()
        assert isinstance(bridge, QObject)

    def test_python_to_js_signals_exist(self):
        """Python→JS 信号全部定义。"""
        bridge = WebBridge()
        expected_signals = [
            "init_game_state",
            "update_suspect",
            "add_message",
            "update_timer",
            "update_evidence_list",
            "set_input_enabled",
            "show_dialog",
            "clear_chat",
            "show_loading",
            "hide_loading",
            "update_loading_progress",
            "show_save_list",
            "set_game_interactive",
            "show_ending_dialog",
            "restart_requested",
            "return_to_menu_requested",
            "review_requested",
            "show_review",
            "case_briefing_requested",
            "show_case_briefing",
        ]
        for signal_name in expected_signals:
            assert hasattr(bridge, signal_name), f"Missing signal: {signal_name}"

    def test_js_to_python_signals_exist(self):
        """JS→Python 信号全部定义。"""
        bridge = WebBridge()
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
        ]
        for signal_name in expected_signals:
            assert hasattr(bridge, signal_name), f"Missing signal: {signal_name}"


class TestWebBridgeSlots:
    """WebBridge 槽函数测试。"""

    def test_send_message_emits_signal(self, qtbot):
        """sendMessage 发射 message_sent 信号。"""
        bridge = WebBridge()
        with qtbot.waitSignal(bridge.message_sent, timeout=1000) as blocker:
            bridge.sendMessage("test message")
        assert blocker.args == ["test message"]

    def test_select_suspect_emits_signal(self, qtbot):
        """selectSuspect 发射 suspect_selected 信号。"""
        bridge = WebBridge()
        with qtbot.waitSignal(bridge.suspect_selected, timeout=1000) as blocker:
            bridge.selectSuspect(0)
        assert blocker.args == [0]

    def test_present_evidence_emits_signal(self, qtbot):
        """presentEvidence 发射 evidence_presented 信号。"""
        bridge = WebBridge()
        with qtbot.waitSignal(bridge.evidence_presented, timeout=1000) as blocker:
            bridge.presentEvidence("evidence_001")
        assert blocker.args == ["evidence_001"]

    def test_apply_pressure_emits_signal(self, qtbot):
        """applyPressure 发射 pressure_applied 信号。"""
        bridge = WebBridge()
        with qtbot.waitSignal(bridge.pressure_applied, timeout=1000):
            bridge.applyPressure()

    def test_apply_empathy_emits_signal(self, qtbot):
        """applyEmpathy 发射 empathy_applied 信号。"""
        bridge = WebBridge()
        with qtbot.waitSignal(bridge.empathy_applied, timeout=1000):
            bridge.applyEmpathy()

    def test_request_save_emits_signal(self, qtbot):
        """requestSave 发射 save_requested 信号。"""
        bridge = WebBridge()
        with qtbot.waitSignal(bridge.save_requested, timeout=1000):
            bridge.requestSave()

    def test_request_load_emits_signal(self, qtbot):
        """requestLoad 发射 load_requested 信号。"""
        bridge = WebBridge()
        with qtbot.waitSignal(bridge.load_requested, timeout=1000):
            bridge.requestLoad()

    def test_request_settings_emits_signal(self, qtbot):
        """requestSettings 发射 settings_requested 信号。"""
        bridge = WebBridge()
        with qtbot.waitSignal(bridge.settings_requested, timeout=1000):
            bridge.requestSettings()

    def test_request_generate_case_emits_signal(self, qtbot):
        """requestGenerateCase 发射 generate_case_requested 信号。"""
        bridge = WebBridge()
        with qtbot.waitSignal(bridge.generate_case_requested, timeout=1000):
            bridge.requestGenerateCase()

    def test_cancel_operation_emits_signal(self, qtbot):
        """cancelOperation 发射 cancel_requested 信号。"""
        bridge = WebBridge()
        with qtbot.waitSignal(bridge.cancel_requested, timeout=1000):
            bridge.cancelOperation()

    def test_select_save_emits_signal(self, qtbot):
        """selectSave 发射 save_selected 信号。"""
        bridge = WebBridge()
        with qtbot.waitSignal(bridge.save_selected, timeout=1000) as blocker:
            bridge.selectSave("session_123")
        assert blocker.args == ["session_123"]

    def test_request_restart_emits_signal(self, qtbot):
        """requestRestart 发射 restart_requested 信号。"""
        bridge = WebBridge()
        with qtbot.waitSignal(bridge.restart_requested, timeout=1000):
            bridge.requestRestart()

    def test_request_return_to_menu_emits_signal(self, qtbot):
        """requestReturnToMenu 发射 return_to_menu_requested 信号。"""
        bridge = WebBridge()
        with qtbot.waitSignal(bridge.return_to_menu_requested, timeout=1000):
            bridge.requestReturnToMenu()

    def test_request_review_emits_signal(self, qtbot):
        """requestReview 发射 review_requested 信号。"""
        bridge = WebBridge()
        with qtbot.waitSignal(bridge.review_requested, timeout=1000):
            bridge.requestReview()

    def test_request_case_briefing_emits_signal(self, qtbot):
        """requestCaseBriefing 发射 case_briefing_requested 信号。"""
        bridge = WebBridge()
        with qtbot.waitSignal(bridge.case_briefing_requested, timeout=1000):
            bridge.requestCaseBriefing()

    def test_set_game_interactive_signal_exists(self):
        """set_game_interactive 信号定义。"""
        bridge = WebBridge()
        assert hasattr(bridge, "set_game_interactive")

    def test_show_review_signal_exists(self):
        """show_review 信号定义。"""
        bridge = WebBridge()
        assert hasattr(bridge, "show_review")

    def test_show_case_briefing_signal_exists(self):
        """show_case_briefing 信号定义。"""
        bridge = WebBridge()
        assert hasattr(bridge, "show_case_briefing")


class TestWebBridgeSlotEdgeCases:
    """WebBridge 槽函数边界测试。"""

    def test_send_empty_string(self, qtbot):
        """空字符串仍能发射信号。"""
        bridge = WebBridge()
        with qtbot.waitSignal(bridge.message_sent, timeout=1000) as blocker:
            bridge.sendMessage("")
        assert blocker.args == [""]

    def test_select_negative_index(self, qtbot):
        """负数索引不崩溃。"""
        bridge = WebBridge()
        with qtbot.waitSignal(bridge.suspect_selected, timeout=1000) as blocker:
            bridge.selectSuspect(-1)
        assert blocker.args == [-1]

    def test_select_large_index(self, qtbot):
        """超大索引不崩溃。"""
        bridge = WebBridge()
        with qtbot.waitSignal(bridge.suspect_selected, timeout=1000) as blocker:
            bridge.selectSuspect(999)
        assert blocker.args == [999]

    def test_present_empty_evidence_id(self, qtbot):
        """空证据 ID 不崩溃。"""
        bridge = WebBridge()
        with qtbot.waitSignal(bridge.evidence_presented, timeout=1000) as blocker:
            bridge.presentEvidence("")
        assert blocker.args == [""]
