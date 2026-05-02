import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QToolBar

from core.interrogation import DummySuspectAgent
from ui.admin_dialog import AdminDialog
from ui.main_window import MainWindow


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "mock_cases"


@pytest.fixture
def simple_case_data():
    with open(FIXTURES_DIR / "simple.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def main_window(qtbot, simple_case_data):
    with patch("core.suspect_agent.llm_client") as mock_llm:
        mock_llm.is_initialized = False
        window = MainWindow(case_data=simple_case_data)
        qtbot.addWidget(window)
        window.engine.suspects = [
            DummySuspectAgent(s, simple_case_data["title"])
            for s in simple_case_data["suspects"]
        ]
        yield window


class TestGenerateCaseViaAdminDialog:
    def test_generate_case_via_admin_dialog(self, main_window, qtbot, simple_case_data):
        dialog = AdminDialog(main_window)
        qtbot.addWidget(dialog)
        dialog.show()

        dialog.story_input.setPlainText("工厂谋杀案")

        signal_received = []
        dialog.case_generated.connect(lambda d: signal_received.append(d))

        with patch("ui.admin_dialog.generate_case", return_value=simple_case_data):
            qtbot.mouseClick(dialog.generate_button, Qt.LeftButton)

        assert len(signal_received) == 1
        assert signal_received[0]["case_id"] == simple_case_data["case_id"]

        dialog.case_generated.connect(main_window.load_case)
        with patch("core.suspect_agent.llm_client") as mock_llm:
            mock_llm.is_initialized = False
            main_window.load_case(simple_case_data)

        assert main_window.suspect_combo.count() == len(simple_case_data["suspects"])
        for i, suspect in enumerate(simple_case_data["suspects"]):
            assert main_window.suspect_combo.itemText(i) == suspect["name"]


class TestSelectSuspectAndChat:
    def test_select_suspect_and_chat(self, main_window, qtbot):
        main_window.suspect_combo.setCurrentIndex(0)
        assert main_window.suspect_display.name_label.text() == "李四"

        main_window.chat_widget.input_field.setText("你好")
        qtbot.mouseClick(main_window.chat_widget.send_button, Qt.LeftButton)

        qtbot.waitUntil(lambda: main_window._current_worker is None, timeout=5000)

        chat_text = main_window.chat_widget.chat_display.toPlainText()
        assert "你好" in chat_text
        assert "我是无辜的" in chat_text
        assert main_window.suspect_display.pressure_bar.value() == 50


class TestPressureButton:
    def test_pressure_button(self, main_window, qtbot):
        main_window.suspect_combo.setCurrentIndex(0)
        initial_pressure = main_window.suspect_display.pressure_bar.value()

        toolbar = main_window.findChild(QToolBar, "审讯操作")
        pressure_action = next(a for a in toolbar.actions() if a.text() == "施压")
        pressure_action.trigger()

        qtbot.waitUntil(lambda: main_window._current_worker is None, timeout=5000)

        assert main_window.suspect_display.pressure_bar.value() == initial_pressure + 10


class TestEmpathyButton:
    def test_empathy_button(self, main_window, qtbot):
        main_window.suspect_combo.setCurrentIndex(0)
        initial_pressure = main_window.suspect_display.pressure_bar.value()

        toolbar = main_window.findChild(QToolBar, "审讯操作")
        empathy_action = next(a for a in toolbar.actions() if a.text() == "共情")
        empathy_action.trigger()

        qtbot.waitUntil(lambda: main_window._current_worker is None, timeout=5000)

        assert main_window.suspect_display.pressure_bar.value() == initial_pressure - 5


class TestEvidencePanelInteraction:
    def test_evidence_panel_interaction(self, main_window, qtbot, simple_case_data):
        evidences = simple_case_data["evidences"]
        assert main_window.evidence_panel.list_widget.count() == len(evidences)

        for i, ev in enumerate(evidences):
            item_text = main_window.evidence_panel.list_widget.item(i).text()
            assert ev["name"] in item_text

        signal_args = []
        main_window.evidence_panel.evidence_selected.connect(
            lambda eid: signal_args.append(eid)
        )

        mock_events = [
            {
                "type": "new_message",
                "role": "player",
                "content": f"出示证据: {evidences[0]['name']}",
                "suspect_name": None,
            },
            {
                "type": "new_message",
                "role": "suspect",
                "content": "我是无辜的",
                "suspect_name": "李四",
            },
            {
                "type": "suspect_update",
                "suspect_index": 0,
                "pressure": 70,
                "secret_triggered": None,
            },
        ]

        with patch.object(
            main_window.engine, "submit_action", return_value=mock_events
        ) as mock_submit:
            with patch(
                "ui.main_window.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ):
                main_window.evidence_panel.evidence_selected.emit(evidences[0]["id"])
                qtbot.waitUntil(
                    lambda: main_window._current_worker is None, timeout=5000
                )

            mock_submit.assert_called_once()
            call_args = mock_submit.call_args
            assert call_args[0][0] == "present_evidence"
            assert call_args[1]["evidence_id"] == evidences[0]["id"]

        assert evidences[0]["id"] in signal_args
        chat_text = main_window.chat_widget.chat_display.toPlainText()
        assert evidences[0]["name"] in chat_text


class TestSuspectDisplayUpdates:
    def test_suspect_display_updates(self, main_window, simple_case_data):
        main_window.suspect_combo.setCurrentIndex(0)
        assert main_window.suspect_display.name_label.text() == "李四"
        assert main_window.suspect_display.pressure_bar.value() == 50

        events = [
            {
                "type": "suspect_update",
                "suspect_index": 0,
                "pressure": 80,
                "secret_triggered": None,
            }
        ]
        main_window.update_ui_from_engine(events)
        assert main_window.suspect_display.pressure_bar.value() == 80

        events_high = [
            {
                "type": "suspect_update",
                "suspect_index": 0,
                "pressure": 90,
                "secret_triggered": None,
            }
        ]
        main_window.update_ui_from_engine(events_high)
        assert main_window.suspect_display.pressure_bar.value() == 90


class TestCountdownTimer:
    def test_countdown_timer(self, main_window, simple_case_data):
        time_limit = simple_case_data["interrogation_time_limit_sec"]
        assert str(time_limit) in main_window.timer_label.text()

        main_window._countdown_timer.stop()
        main_window._on_timer_tick()
        assert str(time_limit - 1) in main_window.timer_label.text()

        main_window._on_timer_tick()
        assert str(time_limit - 2) in main_window.timer_label.text()


class TestTimeoutEnding:
    def test_timeout_ending(self, main_window):
        main_window.engine.time_left = 1
        main_window.engine.state = "interrogating"

        with patch("ui.main_window.QMessageBox") as mock_msgbox_cls:
            mock_dialog = MagicMock()
            mock_msgbox_cls.return_value = mock_dialog
            mock_msgbox_cls.StandardButton = QMessageBox.StandardButton
            mock_msgbox_cls.ButtonRole = QMessageBox.ButtonRole
            main_window._on_timer_tick()
            mock_dialog.setText.assert_called_once()
            message = mock_dialog.setText.call_args[0][0]
            assert "律师介入" in message

        assert main_window.engine.state == "verdict"


class TestBreakdownEnding:
    def test_breakdown_ending(self, main_window):
        events = [
            {
                "type": "state_change",
                "new_state": "breakdown",
                "verdict_reason": "李四 泄露了秘密",
            }
        ]
        with patch("ui.main_window.QMessageBox") as mock_msgbox_cls:
            mock_dialog = MagicMock()
            mock_msgbox_cls.return_value = mock_dialog
            mock_msgbox_cls.StandardButton = QMessageBox.StandardButton
            mock_msgbox_cls.ButtonRole = QMessageBox.ButtonRole
            main_window.update_ui_from_engine(events)
            mock_dialog.setText.assert_called_once()
            message = mock_dialog.setText.call_args[0][0]
            assert "破案成功" in message
