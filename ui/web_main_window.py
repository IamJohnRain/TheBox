"""基于 WebView 的主窗口，与 InterrogationEngine 集成。

实现完整的游戏功能：案件加载、审讯交互、倒计时、存档/读档、
LLM 后台调用、游戏结局处理等。
"""

import logging
import uuid
from typing import Optional

from PySide6.QtCore import QTimer, QThread, Signal
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWidgets import QMainWindow

from core import db
from core.interrogation import InterrogationEngine
from ui.web_bridge import WebBridge
from ui.resource_helper import get_html_url
from ui.admin_dialog import AdminDialog
from ui.settings_dialog import SettingsDialog

logger = logging.getLogger("thebox")

# 配置常量
LLM_TIMEOUT_SECONDS = 60


class WebWorker(QThread):
    """后台线程 Worker，处理可能阻塞的 LLM 调用。"""

    finished = Signal(list)
    error = Signal(str)

    def __init__(self, engine, action, content, evidence_id=None):
        super().__init__()
        self._engine = engine
        self._action = action
        self._content = content
        self._evidence_id = evidence_id
        self._interrupted = False

    def interrupt(self):
        """请求中断 Worker。"""
        self._interrupted = True

    def run(self):
        try:
            events = self._engine.submit_action(
                self._action, self._content, evidence_id=self._evidence_id
            )
            if not self._interrupted:
                self.finished.emit(events)
        except Exception as exc:
            if not self._interrupted:
                logger.error(f"Worker error: {exc}")
                self.error.emit(str(exc))


class WebMainWindow(QMainWindow):
    """基于 WebView 的主窗口。"""

    def __init__(self, case_data=None):
        super().__init__()
        self.setWindowTitle("The Box: Local Verdict")
        self.resize(1280, 800)

        self.engine: Optional[InterrogationEngine] = None
        self._current_worker: Optional[WebWorker] = None
        self._timeout_timer: Optional[QTimer] = None
        self._progress_timer: Optional[QTimer] = None
        self._elapsed_seconds = 0

        # 创建 WebView
        self.web_view = QWebEngineView()

        # 设置通信通道
        self.bridge = WebBridge()
        self.channel = QWebChannel()
        self.channel.registerObject("bridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        # 加载 HTML
        self.web_view.setUrl(get_html_url())

        # 设置中心部件
        self.setCentralWidget(self.web_view)

        # 初始化倒计时
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._on_timer_tick)

        # 连接 Bridge 信号
        self._connect_bridge_signals()

        # 如果有初始案件数据，加载
        if case_data:
            self.web_view.loadFinished.connect(
                lambda ok: self.load_case(case_data) if ok else None
            )

    def _connect_bridge_signals(self):
        """连接 WebBridge 的所有信号。"""
        self.bridge.message_sent.connect(self._on_chat_message_sent)
        self.bridge.suspect_selected.connect(self._on_suspect_changed)
        self.bridge.evidence_presented.connect(self._on_evidence_selected)
        self.bridge.pressure_applied.connect(self._on_pressure)
        self.bridge.empathy_applied.connect(self._on_empathy)
        self.bridge.save_requested.connect(self._on_save_game)
        self.bridge.load_requested.connect(self._on_load_game)
        self.bridge.settings_requested.connect(self._on_llm_settings)
        self.bridge.generate_case_requested.connect(self._on_generate_case)
        self.bridge.cancel_requested.connect(self._on_cancel_operation)
        self.bridge.save_selected.connect(self._on_save_selected)
        self.bridge.restart_requested.connect(self._restart)
        self.bridge.return_to_menu_requested.connect(self._return_to_menu)

    def load_case(self, case_data):
        """加载案件到引擎并更新 UI。"""
        self.engine = InterrogationEngine(case_data)

        # 构建完整初始状态
        state = {
            "suspects": [
                {"name": s.name, "pressure": s.pressure}
                for s in self.engine.suspects
            ],
            "evidences": case_data.get("evidences", []),
            "time_left": self.engine.time_left,
            "current_suspect_index": 0,
            "state": self.engine.state,
            "case_id": case_data.get("case_id", ""),
        }

        # 一次性发送完整状态
        self.bridge.init_game_state.emit(state)
        self.bridge.set_input_enabled.emit(True)

        # 如果有嫌疑人，选择第一个
        if self.engine.suspects:
            self._on_suspect_changed(0)

    def _on_suspect_changed(self, index):
        """处理嫌疑人切换。"""
        if self.engine is None or index < 0:
            return

        info = self.engine.select_suspect(index)
        self.bridge.update_suspect.emit(info["name"], info["pressure"])

        if self.engine.state == "interrogating":
            self._countdown_timer.start()

    def _on_chat_message_sent(self, text):
        """处理用户发送的聊天消息。"""
        if self.engine is None:
            return
        self._start_worker("chat", text)

    def _on_pressure(self):
        """处理施压操作。"""
        if self.engine is None:
            return
        self._start_worker("pressure", "对嫌疑人施压")

    def _on_empathy(self):
        """处理共情操作。"""
        if self.engine is None:
            return
        self._start_worker("empathy", "对嫌疑人表示共情")

    def _on_evidence_selected(self, evidence_id):
        """处理证据出示。"""
        if self.engine is None:
            return

        # 获取证据信息
        evidence = self.engine.get_evidence(evidence_id)
        evidence_name = (
            evidence.get("name", evidence_id) if evidence else evidence_id
        )

        self._start_worker(
            "present_evidence",
            f"出示证据: {evidence_name}",
            evidence_id=evidence_id,
        )

    def _start_worker(self, action, content, evidence_id=None):
        """启动后台 Worker。"""
        if self._current_worker and self._current_worker.isRunning():
            logger.warning("上一个操作仍在进行中")
            return
        if self.engine is None:
            return

        # 显示加载状态
        self.bridge.show_loading.emit("正在审讯中...", True)
        self.bridge.set_input_enabled.emit(False)

        # 重置计时
        self._elapsed_seconds = 0

        # 启动超时计时器
        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(self._on_worker_timeout)
        self._timeout_timer.start(LLM_TIMEOUT_SECONDS * 1000)

        # 启动进度更新计时器
        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(1000)
        self._progress_timer.timeout.connect(self._update_loading_progress)
        self._progress_timer.start()

        # 创建并启动 Worker
        self._current_worker = WebWorker(
            self.engine, action, content, evidence_id
        )
        self._current_worker.finished.connect(self._on_worker_finished)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.start()

    def _update_loading_progress(self):
        """更新加载进度。"""
        self._elapsed_seconds += 1
        self.bridge.update_loading_progress.emit(self._elapsed_seconds)

    def _on_worker_finished(self, events):
        """Worker 完成，处理事件。"""
        self._cleanup_after_worker()
        self.update_ui_from_engine(events)
        self.bridge.hide_loading.emit()
        self.bridge.set_input_enabled.emit(True)
        self._current_worker = None

    def _on_worker_error(self, error_msg):
        """Worker 出错。"""
        self._cleanup_after_worker()
        logger.error(f"操作失败: {error_msg}")
        self.bridge.hide_loading.emit()
        self.bridge.add_message.emit("system", f"操作失败: {error_msg}", "")
        self.bridge.set_input_enabled.emit(True)
        self._current_worker = None

    def _on_worker_timeout(self):
        """Worker 超时。"""
        if self._current_worker and self._current_worker.isRunning():
            self._current_worker.interrupt()
            self._current_worker.wait(2000)
            self._cleanup_after_worker()
            self.bridge.hide_loading.emit()
            self.bridge.add_message.emit("system", "响应超时，请重试", "")
            self.bridge.set_input_enabled.emit(True)
            self._current_worker = None

    def _on_cancel_operation(self):
        """用户取消操作。"""
        if self._current_worker and self._current_worker.isRunning():
            self._current_worker.interrupt()
            self._current_worker.wait(2000)
            self._cleanup_after_worker()
            self.bridge.hide_loading.emit()
            self.bridge.add_message.emit("system", "操作已取消", "")
            self.bridge.set_input_enabled.emit(True)
            self._current_worker = None

    def _cleanup_after_worker(self):
        """清理 Worker 相关资源。"""
        if self._timeout_timer:
            self._timeout_timer.stop()
            self._timeout_timer = None
        if self._progress_timer:
            self._progress_timer.stop()
            self._progress_timer = None

    def _on_timer_tick(self):
        """倒计时更新。"""
        if self.engine is None:
            self._countdown_timer.stop()
            return

        events = self.engine.tick(1)
        self.update_ui_from_engine(events)

        if self.engine.state not in ("interrogating", "selecting"):
            self._countdown_timer.stop()

    def update_ui_from_engine(self, events):
        """处理引擎返回的事件列表，更新 UI。"""
        for event in events:
            if event["type"] == "new_message":
                role = event["role"]
                content = event["content"]
                suspect = event.get("suspect_name") or ""
                self.bridge.add_message.emit(role, content, suspect)

            elif event["type"] == "suspect_update":
                pressure = event["pressure"]
                if self.engine:
                    suspect = self.engine.suspects[
                        self.engine.current_suspect_index
                    ]
                    self.bridge.update_suspect.emit(suspect.name, pressure)

            elif event["type"] == "state_change":
                new_state = event["new_state"]
                self.bridge.add_message.emit(
                    "system", f"[状态变更] {new_state}", ""
                )
                if new_state in ("verdict", "breakdown"):
                    self._handle_ending(event)

            elif event["type"] == "timer_tick":
                self.bridge.update_timer.emit(event["time_left"])

    def _handle_ending(self, state_event):
        """处理游戏结局。"""
        self._countdown_timer.stop()
        self.bridge.set_input_enabled.emit(False)

        new_state = state_event["new_state"]
        if new_state == "breakdown":
            message = "破案成功！真凶已经崩溃认罪。"
        elif new_state == "verdict":
            message = "时间耗尽！律师介入，案件被迫终止。"
        else:
            message = f"游戏结束: {new_state}"

        # 通过 Bridge 显示对话框
        self.bridge.show_ending_dialog.emit("审讯结束", message)

    def _restart(self):
        """重新开始当前案件。"""
        if self.engine is None:
            return
        case_data = self.engine.case
        self.load_case(case_data)

    def _return_to_menu(self):
        """返回主菜单。"""
        self.engine = None
        self.bridge.clear_chat.emit()
        self.bridge.set_input_enabled.emit(False)
        self._countdown_timer.stop()

    def _on_generate_case(self):
        """打开案件生成对话框。"""
        dialog = AdminDialog(self)
        dialog.case_generated.connect(self.load_case)
        dialog.exec()

    def _on_llm_settings(self):
        """打开 LLM 设置对话框。"""
        dialog = SettingsDialog(self)
        dialog.settings_saved.connect(self._on_settings_saved)
        dialog.exec()

    def _on_settings_saved(self):
        """设置保存后重新初始化 LLM。"""
        if self.engine and hasattr(self.engine, "reinitialize_llm"):
            try:
                self.engine.reinitialize_llm()
            except Exception as exc:
                logger.warning(f"Engine reinit: {exc}")

    def _on_save_game(self):
        """存档。"""
        if self.engine is None:
            return
        try:
            session_id = str(uuid.uuid4())
            case_id = self.engine.case.get("case_id", "unknown")
            engine_state_dict = self.engine.to_dict()
            db.save_full_session(session_id, case_id, engine_state_dict)
            self.bridge.show_dialog.emit(
                "存档成功", f"游戏已保存！\n存档ID: {session_id[:8]}..."
            )
        except Exception as exc:
            logger.error(f"存档失败: {exc}")
            self.bridge.show_dialog.emit("存档失败", f"保存失败: {exc}")

    def _on_load_game(self):
        """读档 - 显示存档列表。"""
        try:
            sessions = db.list_sessions()
            formatted_sessions = [
                {
                    "session_id": s["session_id"],
                    "case_id": s.get("case_id", "未知案件"),
                    "created_at": s.get("saved_at", ""),
                }
                for s in sessions
            ]
            self.bridge.show_save_list.emit(formatted_sessions)
        except Exception as exc:
            logger.error(f"获取存档列表失败: {exc}")
            self.bridge.show_dialog.emit(
                "读档失败", f"无法读取存档列表: {exc}"
            )

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
                self.bridge.show_dialog.emit(
                    "读档失败", f"关联案件未找到: {case_id}"
                )
                return

            self.engine = InterrogationEngine.from_dict(
                engine_state_dict, case_data
            )

            # 构建完整状态
            state = {
                "suspects": [
                    {"name": s.name, "pressure": s.pressure}
                    for s in self.engine.suspects
                ],
                "evidences": case_data.get("evidences", []),
                "time_left": self.engine.time_left,
                "current_suspect_index": self.engine.current_suspect_index,
                "state": self.engine.state,
                "case_id": case_id,
            }

            self.bridge.init_game_state.emit(state)
            self.bridge.set_input_enabled.emit(True)

            if self.engine.state == "interrogating":
                self._countdown_timer.start()
        except Exception as exc:
            logger.error(f"加载存档失败: {exc}")
            self.bridge.show_dialog.emit("读档失败", f"加载失败: {exc}")
