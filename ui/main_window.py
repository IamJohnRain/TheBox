import logging
import uuid
from typing import List, Optional

from PySide6.QtCore import QTimer, QThread, Signal, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core import db
from core.interrogation import InterrogationEngine
from schemas.events import UIEvent
from ui.admin_dialog import AdminDialog
from ui.chat_widget import ChatWidget
from ui.evidence_panel import EvidencePanel
from ui.settings_dialog import SettingsDialog
from ui.suspect_display import SuspectDisplay

logger = logging.getLogger("thebox")


class Worker(QThread):
    """Background thread worker for running engine actions that may involve LLM calls."""

    finished = Signal(list)
    error = Signal(str)

    def __init__(
        self, engine: InterrogationEngine, action: str, content: str, evidence_id: Optional[str] = None
    ) -> None:
        super().__init__()
        self._engine = engine
        self._action = action
        self._content = content
        self._evidence_id = evidence_id

    def run(self) -> None:
        """Execute the engine action in a background thread."""
        try:
            events = self._engine.submit_action(self._action, self._content, evidence_id=self._evidence_id)
            self.finished.emit(events)
        except Exception as exc:
            logger.error(f"Worker error: {exc}")
            self.error.emit(str(exc))


class MainWindow(QMainWindow):
    """Main application window for The Box: Local Verdict."""

    def __init__(self, case_data: Optional[dict] = None) -> None:
        super().__init__()
        self.setWindowTitle("The Box: Local Verdict")
        self.resize(1100, 700)

        self.engine: Optional[InterrogationEngine] = None
        self._current_worker: Optional[Worker] = None

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(4, 4, 4, 4)

        self.suspect_combo = QComboBox()
        self.suspect_combo.setEnabled(True)
        self.suspect_combo.currentIndexChanged.connect(self._on_suspect_changed)
        left_layout.addWidget(self.suspect_combo)

        self.suspect_display = SuspectDisplay()
        left_layout.addWidget(self.suspect_display)

        left_layout.addStretch()
        main_layout.addWidget(left_panel)

        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(4, 4, 4, 4)

        self.chat_widget = ChatWidget()
        self.chat_widget.message_sent.connect(self._on_chat_message_sent)
        center_layout.addWidget(self.chat_widget)

        self.timer_label = QLabel("剩余时间: --")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(self.timer_label)

        main_layout.addWidget(center_panel, stretch=1)

        self.evidence_panel = EvidencePanel()
        self.evidence_panel.evidence_selected.connect(self._on_evidence_selected)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.evidence_panel)

        self._build_toolbar()
        self._build_menu()
        self._build_timer()

        if case_data is not None:
            self.load_case(case_data)

    def _build_toolbar(self) -> None:
        """Build the action toolbar with pressure and empathy buttons."""
        toolbar = QToolBar("审讯操作")
        toolbar.setObjectName("审讯操作")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        pressure_action = toolbar.addAction("施压")
        pressure_action.setToolTip("对嫌疑人施压，增加压力值")
        pressure_action.triggered.connect(self._on_pressure)

        empathy_action = toolbar.addAction("共情")
        empathy_action.setToolTip("对嫌疑人表示共情，降低压力值")
        empathy_action.triggered.connect(self._on_empathy)

    def _build_menu(self) -> None:
        """Build the menu bar."""
        menu_bar = self.menuBar()

        game_menu = menu_bar.addMenu("游戏")
        self._save_action = game_menu.addAction("存档")
        self._save_action.triggered.connect(self._on_save_game)
        self._save_action.setEnabled(False)
        self._load_action = game_menu.addAction("读档")
        self._load_action.triggered.connect(self._on_load_game)

        settings_menu = menu_bar.addMenu("设置")
        llm_settings_action = settings_menu.addAction("LLM 设置")
        llm_settings_action.triggered.connect(self._on_llm_settings)

        case_menu = menu_bar.addMenu("案件")
        generate_action = case_menu.addAction("生成新案件")
        generate_action.triggered.connect(self._on_generate_case)
        load_action = case_menu.addAction("加载预置案件")
        load_action.triggered.connect(self._on_load_case)

    def _on_llm_settings(self) -> None:
        """Open the LLM settings dialog."""
        dialog = SettingsDialog(self)
        dialog.settings_saved.connect(self._on_settings_saved)
        dialog.exec()

    def _on_settings_saved(self) -> None:
        """Handle settings save - reinitialize engine LLM if active."""
        if self.engine is not None and hasattr(self.engine, "suspect_agent"):
            try:
                self.engine.suspect_agent._ensure_llm_client()
            except Exception as exc:
                logger.warning(f"Engine reinit after settings change: {exc}")

    def _build_timer(self) -> None:
        """Initialize the countdown timer."""
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._on_timer_tick)

    def load_case(self, case_data: dict) -> None:
        """Load a case into the engine and update the UI."""
        self.engine = InterrogationEngine(case_data)

        self.suspect_combo.blockSignals(True)
        self.suspect_combo.clear()
        for suspect in self.engine.suspects:
            self.suspect_combo.addItem(suspect.name)
        self.suspect_combo.blockSignals(False)

        self.chat_widget.clear_chat()
        self.suspect_display.clear()
        self.evidence_panel.load_evidences(case_data.get("evidences", []))

        self.timer_label.setText(f"剩余时间: {self.engine.time_left}s")
        self._set_input_enabled(True)
        self._save_action.setEnabled(True)

        self._countdown_timer.stop()

        if self.engine.suspects:
            self.suspect_combo.setCurrentIndex(0)
            self._on_suspect_changed(0)

    def _on_suspect_changed(self, index: int) -> None:
        """Handle suspect selection change."""
        if self.engine is None or index < 0:
            return
        info = self.engine.select_suspect(index)
        self.suspect_display.update_suspect(info["name"], info["pressure"])

        if self.engine.state == "interrogating":
            self._countdown_timer.start()

    def _on_chat_message_sent(self, text: str) -> None:
        """Handle chat message sent from ChatWidget."""
        if self.engine is None:
            return
        self._start_worker("chat", text)

    def _on_pressure(self) -> None:
        """Handle pressure toolbar button click."""
        if self.engine is None:
            return
        self._start_worker("pressure", "对嫌疑人施压")

    def _on_empathy(self) -> None:
        """Handle empathy toolbar button click."""
        if self.engine is None:
            return
        self._start_worker("empathy", "对嫌疑人表示共情")

    def _on_evidence_selected(self, evidence_id: str) -> None:
        """Handle evidence selection from the evidence panel."""
        if self.engine is None:
            return
        evidence = self.engine._find_evidence(evidence_id)
        evidence_name = evidence.get("name", evidence_id) if evidence else evidence_id
        reply = QMessageBox.question(
            self,
            "出示证据",
            f"确定要出示证据「{evidence_name}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._start_worker("present_evidence", f"出示证据: {evidence_name}", evidence_id=evidence_id)

    def _on_generate_case(self) -> None:
        """Open the admin dialog to generate a new case."""
        dialog = AdminDialog(self)
        dialog.case_generated.connect(self.load_case)
        dialog.exec()

    def _on_load_case(self) -> None:
        """Placeholder for loading a preset case."""
        logger.info("加载预置案件功能尚未实现")

    def _on_save_game(self) -> None:
        """Save the current game session to the database."""
        if self.engine is None:
            return
        try:
            session_id = str(uuid.uuid4())
            case_id = self.engine.case.get("case_id", "unknown")
            engine_state_dict = self.engine.to_dict()
            db.save_full_session(session_id, case_id, engine_state_dict)
            QMessageBox.information(self, "存档成功", f"游戏已保存！\n存档ID: {session_id[:8]}...")
        except Exception as exc:
            logger.error(f"存档失败: {exc}")
            QMessageBox.critical(self, "存档失败", f"保存失败: {exc}")

    def _on_load_game(self) -> None:
        """Load a saved game session from the database."""
        try:
            sessions = db.list_sessions()
        except Exception as exc:
            logger.error(f"获取存档列表失败: {exc}")
            QMessageBox.critical(self, "读档失败", f"无法读取存档列表: {exc}")
            return

        if not sessions:
            QMessageBox.information(self, "读档", "没有找到任何存档。")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("选择存档")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)

        label = QLabel("请选择要加载的存档：")
        layout.addWidget(label)

        list_widget = QListWidget()
        for session in sessions:
            display_text = f"[{session['saved_at']}] 案件: {session['case_id']} (ID: {session['session_id'][:8]}...)"
            list_widget.addItem(display_text)

        layout.addWidget(list_widget)

        from PySide6.QtWidgets import QDialogButtonBox

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        list_widget.itemDoubleClicked.connect(lambda: dialog.accept())

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        current_row = list_widget.currentRow()
        if current_row < 0:
            return

        selected_session = sessions[current_row]
        session_id = selected_session["session_id"]

        try:
            result = db.load_full_session(session_id)
            if result is None:
                QMessageBox.warning(self, "读档失败", "存档数据未找到。")
                return

            case_id, engine_state_dict = result

            case_data = db.load_case(case_id)
            if case_data is None:
                QMessageBox.warning(self, "读档失败", f"关联的案件数据未找到: {case_id}")
                return

            self.engine = InterrogationEngine.from_dict(engine_state_dict, case_data)

            self.suspect_combo.blockSignals(True)
            self.suspect_combo.clear()
            for suspect in self.engine.suspects:
                self.suspect_combo.addItem(suspect.name)
            self.suspect_combo.blockSignals(False)

            self.chat_widget.clear_chat()
            self.suspect_display.clear()
            self.evidence_panel.load_evidences(case_data.get("evidences", []))

            self.timer_label.setText(f"剩余时间: {self.engine.time_left}s")
            self._set_input_enabled(True)
            self._save_action.setEnabled(True)

            self._countdown_timer.stop()

            if self.engine.current_suspect_index < len(self.engine.suspects):
                self.suspect_combo.setCurrentIndex(self.engine.current_suspect_index)
                self._on_suspect_changed(self.engine.current_suspect_index)

            QMessageBox.information(self, "读档成功", "存档已成功加载！")
        except Exception as exc:
            logger.error(f"读档失败: {exc}")
            QMessageBox.critical(self, "读档失败", f"加载存档失败: {exc}")

    def _start_worker(self, action: str, content: str, evidence_id: Optional[str] = None) -> None:
        """Start a background worker thread for an engine action."""
        if self._current_worker is not None and self._current_worker.isRunning():
            logger.warning("上一个操作仍在进行中，请稍候")
            return
        if self.engine is None:
            return

        self._set_input_enabled(False)
        self._current_worker = Worker(self.engine, action, content, evidence_id)
        self._current_worker.finished.connect(self._on_worker_finished)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.start()

    def _on_worker_finished(self, events: List[UIEvent]) -> None:
        """Handle worker completion with returned events."""
        self.update_ui_from_engine(events)
        self._set_input_enabled(True)
        self._current_worker = None

    def _on_worker_error(self, error_msg: str) -> None:
        """Handle worker error."""
        logger.error(f"操作失败: {error_msg}")
        self.chat_widget.add_message("system", f"操作失败: {error_msg}")
        self._set_input_enabled(True)
        self._current_worker = None

    def _on_timer_tick(self) -> None:
        """Handle countdown timer tick."""
        if self.engine is None:
            self._countdown_timer.stop()
            return
        events = self.engine.tick(1)
        self.update_ui_from_engine(events)
        if self.engine.state not in ("interrogating", "selecting"):
            self._countdown_timer.stop()

    def update_ui_from_engine(self, events: List[UIEvent]) -> None:
        """Process a list of UIEvents and update the interface."""
        for event in events:
            if event["type"] == "new_message":
                role = event["role"]
                content = event["content"]
                suspect = event.get("suspect_name") or ""
                self.chat_widget.add_message(role, content, suspect_name=suspect)
            elif event["type"] == "suspect_update":
                pressure = event["pressure"]
                if self.engine is not None:
                    suspect = self.engine.suspects[self.engine.current_suspect_index]
                    self.suspect_display.update_suspect(suspect.name, pressure)
            elif event["type"] == "state_change":
                new_state = event["new_state"]
                self.chat_widget.add_message("system", f"[状态变更] {new_state}")
                if new_state in ("verdict", "breakdown"):
                    self._handle_ending(event)
            elif event["type"] == "timer_tick":
                self.timer_label.setText(f"剩余时间: {event['time_left']}s")

    def _handle_ending(self, state_event: UIEvent) -> None:
        """Handle the game ending state by showing the outcome dialog."""
        self._countdown_timer.stop()
        self._set_input_enabled(False)

        new_state = state_event["new_state"]
        if new_state == "breakdown":
            message = "破案成功！真凶已经崩溃认罪。"
        elif new_state == "verdict":
            message = "时间耗尽！律师介入，案件被迫终止。"
        else:
            message = f"游戏结束: {new_state}"

        dialog = QMessageBox(self)
        dialog.setWindowTitle("审讯结束")
        dialog.setText(message)
        restart_button = dialog.addButton("重新开始", QMessageBox.ButtonRole.AcceptRole)
        menu_button = dialog.addButton("返回主菜单", QMessageBox.ButtonRole.RejectRole)
        dialog.exec()

        clicked = dialog.clickedButton()
        if clicked == restart_button:
            self._restart()
        elif clicked == menu_button:
            self._return_to_menu()

    def _restart(self) -> None:
        """Restart the current case from the beginning."""
        if self.engine is None:
            return
        case_data = self.engine.case
        self.load_case(case_data)

    def _return_to_menu(self) -> None:
        """Reset the UI to the initial empty state."""
        self.engine = None
        self.suspect_combo.clear()
        self.chat_widget.clear_chat()
        self.suspect_display.clear()
        self.evidence_panel.clear_evidences()
        self.timer_label.setText("剩余时间: --")
        self._countdown_timer.stop()
        self._set_input_enabled(False)
        self._save_action.setEnabled(False)

    def _set_input_enabled(self, enabled: bool) -> None:
        """Enable or disable all input controls."""
        self.chat_widget.set_input_enabled(enabled)
        self.suspect_combo.setEnabled(enabled and self.engine is not None)
