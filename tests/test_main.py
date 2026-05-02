"""Tests for the main window (MainWindow).

Uses pytest-qt's qtbot fixture to drive the Qt UI.
"""

from unittest.mock import MagicMock, patch

import pytest

from core.interrogation import DummySuspectAgent
from ui.main_window import MainWindow


@pytest.fixture
def main_window(qtbot, tmp_path, monkeypatch):
    """Create a MainWindow instance for testing."""
    monkeypatch.setattr("core.config.CONFIG_FILE", tmp_path / ".thebox_config.json")
    monkeypatch.delenv("THEBOX_MODEL", raising=False)
    with patch("core.config.keyring"):
        window = MainWindow()
        qtbot.addWidget(window)
        yield window


SAMPLE_CASE = {
    "case_id": "test-case-001",
    "title": "测试案件",
    "victim": "受害者A",
    "cause_of_death": "中毒",
    "crime_scene": "办公室",
    "truth": "嫌疑人甲下毒",
    "suspects": [
        {
            "name": "嫌疑人甲",
            "role": "同事",
            "personality": "紧张",
            "knowledge": "知道办公室布局",
            "forbidden_to_reveal": ["下毒"],
        },
        {
            "name": "嫌疑人乙",
            "role": "邻居",
            "personality": "冷静",
            "knowledge": "听到争吵声",
            "forbidden_to_reveal": ["看到凶手"],
        },
    ],
    "evidences": [
        {
            "id": "ev-001",
            "name": "毒药瓶",
            "description": "在嫌疑人甲桌子下发现的毒药瓶",
            "related_suspect": "嫌疑人甲",
        }
    ],
    "interrogation_time_limit_sec": 300,
}


def _load_case_with_dummy(main_window):
    """Load a case with DummySuspectAgent for testing without LLM."""
    main_window.load_case(SAMPLE_CASE)
    main_window.engine.suspects = [
        DummySuspectAgent(s, SAMPLE_CASE["title"]) for s in SAMPLE_CASE["suspects"]
    ]


class TestMainWindow:
    """Test suite for MainWindow M3 implementation."""

    def test_window_title(self, main_window):
        """Test that the main window title is 'The Box: Local Verdict'."""
        assert main_window.windowTitle() == "The Box: Local Verdict"

    def test_menu_bar_has_case_menu(self, main_window):
        """Test that the menu bar contains a '案件' menu."""
        menu_bar = main_window.menuBar()
        menu_titles = [action.text() for action in menu_bar.actions()]
        assert "案件" in menu_titles

    def test_generate_case_opens_dialog(self, main_window):
        """Test that clicking '案件'->'生成新案件' opens AdminDialog."""
        menu_bar = main_window.menuBar()
        case_action = next(a for a in menu_bar.actions() if a.text() == "案件")
        case_menu = case_action.menu()
        generate_action = next(a for a in case_menu.actions() if a.text() == "生成新案件")
        with patch("ui.main_window.AdminDialog") as mock_dialog_cls:
            mock_dialog = MagicMock()
            mock_dialog.exec.return_value = 0
            mock_dialog_cls.return_value = mock_dialog
            generate_action.trigger()

    def test_load_case_populates_combo(self, main_window):
        """Test that loading a case populates the suspect combo box."""
        _load_case_with_dummy(main_window)
        assert main_window.suspect_combo.count() == 2
        assert main_window.suspect_combo.itemText(0) == "嫌疑人甲"
        assert main_window.suspect_combo.itemText(1) == "嫌疑人乙"

    def test_load_case_resets_chat(self, main_window):
        """Test that loading a case clears the chat history."""
        main_window.chat_widget.chat_display.append("old message")
        _load_case_with_dummy(main_window)
        assert main_window.chat_widget.chat_display.toPlainText() == ""

    def test_load_case_updates_timer(self, main_window):
        """Test that loading a case updates the timer label."""
        _load_case_with_dummy(main_window)
        assert "300" in main_window.timer_label.text()

    def test_engine_is_none_initially(self, main_window):
        """Test that the engine is None before a case is loaded."""
        assert main_window.engine is None

    def test_engine_created_after_load(self, main_window):
        """Test that the engine is created after loading a case."""
        _load_case_with_dummy(main_window)
        assert main_window.engine is not None

    def test_select_suspect_updates_name(self, main_window):
        """Test that selecting a suspect updates the suspect name label."""
        _load_case_with_dummy(main_window)
        main_window.suspect_combo.setCurrentIndex(0)
        assert "嫌疑人甲" in main_window.suspect_display.name_label.text()

    def test_select_suspect_updates_pressure(self, main_window):
        """Test that selecting a suspect updates the pressure bar."""
        _load_case_with_dummy(main_window)
        main_window.suspect_combo.setCurrentIndex(0)
        assert main_window.suspect_display.pressure_bar.value() == 50

    def test_chat_sends_message(self, main_window, qtbot):
        """Test that sending a message adds it to the chat display."""
        _load_case_with_dummy(main_window)
        main_window.suspect_combo.setCurrentIndex(0)
        events = main_window.engine.submit_action("chat", "你好")
        main_window.update_ui_from_engine(events)
        chat_text = main_window.chat_widget.chat_display.toPlainText()
        assert "你好" in chat_text

    def test_update_ui_from_engine(self, main_window):
        """Test that update_ui_from_engine processes events correctly."""
        events = [
            {
                "type": "new_message",
                "role": "system",
                "content": "测试消息",
                "suspect_name": None,
            }
        ]
        main_window.update_ui_from_engine(events)
        assert "测试消息" in main_window.chat_widget.chat_display.toPlainText()
