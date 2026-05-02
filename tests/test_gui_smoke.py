from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton

from ui.main_window import MainWindow


@pytest.fixture
def simple_case_data(mock_case_simple):
    return mock_case_simple


@pytest.fixture
def main_window(qtbot, simple_case_data):
    with patch("core.suspect_agent.llm_client") as mock_llm:
        mock_llm.is_initialized = False
        window = MainWindow(case_data=simple_case_data)
        qtbot.addWidget(window)
        yield window


class TestMainWindowLoads:
    def test_window_loads_and_shows(self, main_window):
        main_window.show()
        assert main_window.isVisible()

    def test_window_title(self, main_window):
        assert main_window.windowTitle() == "The Box: Local Verdict"


class TestSuspectCombo:
    def test_combo_has_correct_item_count(self, main_window, simple_case_data):
        assert main_window.suspect_combo.count() == len(simple_case_data["suspects"])

    def test_combo_items_match_suspect_names(self, main_window, simple_case_data):
        for i, suspect in enumerate(simple_case_data["suspects"]):
            assert main_window.suspect_combo.itemText(i) == suspect["name"]

    def test_selecting_suspect_updates_label(self, main_window, simple_case_data):
        main_window.suspect_combo.setCurrentIndex(1)
        assert main_window.suspect_display.name_label.text() == simple_case_data["suspects"][1]["name"]

    def test_selecting_suspect_updates_pressure_bar(self, main_window):
        main_window.suspect_combo.setCurrentIndex(0)
        assert main_window.suspect_display.pressure_bar.value() == 50


class TestChatInput:
    def test_input_field_exists(self, main_window):
        assert isinstance(main_window.chat_widget.input_field, QLineEdit)

    def test_send_button_exists(self, main_window):
        assert isinstance(main_window.chat_widget.send_button, QPushButton)

    def test_type_and_send_with_mock_engine(self, main_window, qtbot):
        main_window.chat_widget.input_field.setText("你好")
        with patch.object(main_window, "_start_worker") as mock_start:
            qtbot.mouseClick(main_window.chat_widget.send_button, Qt.LeftButton)
            mock_start.assert_called_once_with("chat", "你好")
        assert main_window.chat_widget.input_field.text() == ""

    def test_send_empty_does_nothing(self, main_window, qtbot):
        mock_engine = MagicMock()
        main_window.engine = mock_engine
        main_window.chat_widget.input_field.setText("")
        qtbot.mouseClick(main_window.chat_widget.send_button, Qt.LeftButton)
        mock_engine.submit_action.assert_not_called()

    def test_send_whitespace_only_does_nothing(self, main_window, qtbot):
        mock_engine = MagicMock()
        main_window.engine = mock_engine
        main_window.chat_widget.input_field.setText("   ")
        qtbot.mouseClick(main_window.chat_widget.send_button, Qt.LeftButton)
        mock_engine.submit_action.assert_not_called()


class TestMenuBar:
    def test_menu_bar_has_case_menu(self, main_window):
        menu_bar = main_window.menuBar()
        menu_titles = [action.text() for action in menu_bar.actions()]
        assert "案件" in menu_titles

    def test_case_menu_has_generate_action(self, main_window):
        menu_bar = main_window.menuBar()
        case_action = next(a for a in menu_bar.actions() if a.text() == "案件")
        case_menu = case_action.menu()
        action_texts = [a.text() for a in case_menu.actions()]
        assert "生成新案件" in action_texts

    def test_case_menu_has_load_action(self, main_window):
        menu_bar = main_window.menuBar()
        case_action = next(a for a in menu_bar.actions() if a.text() == "案件")
        case_menu = case_action.menu()
        action_texts = [a.text() for a in case_menu.actions()]
        assert "加载预置案件" in action_texts

    def test_click_generate_case_does_not_crash(self, main_window):
        menu_bar = main_window.menuBar()
        case_action = next(a for a in menu_bar.actions() if a.text() == "案件")
        case_menu = case_action.menu()
        generate_action = next(a for a in case_menu.actions() if a.text() == "生成新案件")
        with patch("ui.main_window.AdminDialog") as mock_dialog_cls:
            mock_dialog = MagicMock()
            mock_dialog.exec.return_value = 0
            mock_dialog_cls.return_value = mock_dialog
            generate_action.trigger()
        assert True


class TestUIComponents:
    def test_chat_display_is_readonly(self, main_window):
        assert main_window.chat_widget.chat_display.isReadOnly()

    def test_pressure_bar_range(self, main_window):
        assert main_window.suspect_display.pressure_bar.minimum() == 0
        assert main_window.suspect_display.pressure_bar.maximum() == 100

    def test_timer_label_exists(self, main_window):
        assert isinstance(main_window.timer_label, QLabel)

    def test_evidence_panel_exists(self, main_window):
        assert main_window.evidence_panel is not None

    def test_suspect_display_exists(self, main_window):
        assert main_window.suspect_display is not None

    def test_toolbar_exists(self, main_window):
        from PySide6.QtWidgets import QToolBar
        toolbar = main_window.findChild(QToolBar, "审讯操作")
        assert toolbar is not None


class TestUpdateUIFromEngine:
    def test_update_with_new_message_player(self, main_window):
        events = [
            {
                "type": "new_message",
                "role": "player",
                "content": "你在哪里？",
                "suspect_name": None,
            }
        ]
        main_window.update_ui_from_engine(events)
        assert "你在哪里？" in main_window.chat_widget.chat_display.toPlainText()

    def test_update_with_new_message_suspect(self, main_window):
        events = [
            {
                "type": "new_message",
                "role": "suspect",
                "content": "我在家",
                "suspect_name": "李四",
            }
        ]
        main_window.update_ui_from_engine(events)
        assert "我在家" in main_window.chat_widget.chat_display.toPlainText()

    def test_update_with_suspect_update_changes_pressure(self, main_window):
        events = [
            {
                "type": "suspect_update",
                "suspect_index": 0,
                "pressure": 75,
                "secret_triggered": None,
            }
        ]
        main_window.update_ui_from_engine(events)
        assert main_window.suspect_display.pressure_bar.value() == 75

    def test_update_with_timer_tick(self, main_window):
        events = [
            {
                "type": "timer_tick",
                "time_left": 300,
            }
        ]
        main_window.update_ui_from_engine(events)
        assert "300" in main_window.timer_label.text()

    def test_update_with_state_change(self, main_window):
        events = [
            {
                "type": "state_change",
                "new_state": "interrogating",
                "verdict_reason": None,
            }
        ]
        main_window.update_ui_from_engine(events)
        assert "interrogating" in main_window.chat_widget.chat_display.toPlainText()
