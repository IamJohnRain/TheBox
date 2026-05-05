"""基于 WebView 的主窗口，与 InterrogationEngine 集成。

实现完整的游戏功能：案件加载、审讯交互、倒计时、存档/读档、
LLM 后台调用、游戏结局处理等。
"""

import json
import logging
import uuid
from typing import Optional

from PySide6.QtCore import QTimer, QThread, Signal
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWidgets import QMainWindow

from core import db
from core.config import get_api_key, get_settings, save_settings
from core.exceptions import ContentFilterError
from core.interrogation import InterrogationEngine
from core.providers import get_provider_list, get_provider_models
from ui.web_bridge import WebBridge
from ui.resource_helper import get_html_url

logger = logging.getLogger("thebox")

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


class TestConnectionWorker(QThread):
    """后台线程 Worker，测试 LLM 连接。"""

    finished = Signal(bool, str)

    def __init__(self, api_key, base_url, model):
        super().__init__()
        self._api_key = api_key
        self._base_url = base_url
        self._model = model

    def run(self):
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self._api_key, base_url=self._base_url)
            response = client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            content = response.choices[0].message.content
            msg = f"连接成功！模型响应: {content[:50] if content else '(空响应)'}"
            self.finished.emit(True, msg)
        except Exception as exc:
            logger.error(f"连接测试失败: {exc}")
            self.finished.emit(False, f"连接失败: {exc}")


class CaseGenerateWorker(QThread):
    """后台线程 Worker，生成案件。"""

    finished = Signal(dict)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, background, model_override=None, safe_mode=False):
        super().__init__()
        self._background = background
        self._model_override = model_override
        self._safe_mode = safe_mode
        self._interrupted = False

    def interrupt(self):
        self._interrupted = True

    def run(self):
        try:
            if self._model_override:
                from core.llm_client import LLMClient

                client = LLMClient()
                if not client.is_initialized:
                    client.initialize()
                client.set_model(self._model_override)

            from core.case_generator import generate_case

            case_dict = generate_case(
                self._background,
                progress_callback=lambda msg: self.progress.emit(msg),
                safe_mode=self._safe_mode,
            )
            if not self._interrupted:
                self.finished.emit(case_dict)
        except ContentFilterError as exc:
            if not self._interrupted:
                logger.error(f"案件生成失败(内容过滤): {exc}")
                self.error.emit(f"CONTENT_FILTER:{str(exc)}")
        except Exception as exc:
            if not self._interrupted:
                logger.error(f"案件生成失败: {exc}")
                self.error.emit(str(exc))


class ReviewWorker(QThread):
    """后台线程 Worker，生成审讯复盘报告。"""

    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, engine):
        super().__init__()
        # 保存引擎状态快照，避免线程安全问题
        self._engine_state = engine.to_dict()
        self._case_data = engine.case

    def run(self):
        try:
            from core.review_generator import generate_review

            result = generate_review(self._engine_state, self._case_data)
            if result:
                self.finished.emit(result)
            else:
                self.error.emit("复盘报告生成失败")
        except Exception as exc:
            logger.error(f"复盘生成失败: {exc}")
            self.error.emit(str(exc))


class WebMainWindow(QMainWindow):
    """基于 WebView 的主窗口。"""

    def __init__(self, case_data=None):
        super().__init__()
        self.setWindowTitle("The Box: Local Verdict")
        self.resize(1280, 800)

        self.engine: Optional[InterrogationEngine] = None
        self._current_worker: Optional[WebWorker] = None
        self._test_worker: Optional[TestConnectionWorker] = None
        self._case_gen_worker: Optional[CaseGenerateWorker] = None
        self._review_worker: Optional[ReviewWorker] = None
        self._case_gen_cancelled: bool = False

        self.web_view = QWebEngineView()

        self.bridge = WebBridge()
        self.channel = QWebChannel()
        self.channel.registerObject("bridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        self.web_view.setUrl(get_html_url())
        self.setCentralWidget(self.web_view)

        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._on_timer_tick)

        self._connect_bridge_signals()

        from core.llm_client import llm_client
        llm_client.initialize()

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
        self.bridge.save_to_slot_requested.connect(self._on_save_to_slot)
        self.bridge.delete_save_requested.connect(self._on_delete_save)
        self.bridge.restart_requested.connect(self._restart)
        self.bridge.return_to_menu_requested.connect(self._return_to_menu)
        self.bridge.submit_settings_requested.connect(self._on_submit_settings)
        self.bridge.test_connection_requested.connect(self._on_test_connection)
        self.bridge.submit_case_generation_requested.connect(
            self._on_submit_case_generation
        )
        self.bridge.submit_case_generation_safe_requested.connect(
            self._on_submit_case_generation_safe
        )
        self.bridge.cancel_case_generation_requested.connect(
            self._on_cancel_case_generation
        )
        self.bridge.review_requested.connect(self._on_review_requested)
        self.bridge.case_briefing_requested.connect(self._on_case_briefing_requested)

    def _emit_case_briefing(self, case_data):
        """发送案件资料到前端。"""
        briefing = {
            "title": case_data.get("title", ""),
            "victim": case_data.get("victim", ""),
            "causeOfDeath": case_data.get("cause_of_death", ""),
            "crimeScene": case_data.get("crime_scene", ""),
            "suspects": [
                {
                    "name": s.get("name", ""),
                    "role": s.get("role", ""),
                    "personality": s.get("personality", ""),
                }
                for s in case_data.get("suspects", [])
            ],
        }
        self.bridge.show_case_briefing.emit(briefing)

    def _on_case_briefing_requested(self):
        """处理前端请求查看案件资料。"""
        if self.engine is None:
            return
        self._emit_case_briefing(self.engine.case)

    def load_case(self, case_data):
        """加载案件到引擎并更新 UI。"""
        if "case_id" not in case_data or not case_data["case_id"]:
            case_data["case_id"] = str(uuid.uuid4())

        self.engine = InterrogationEngine(case_data)

        try:
            db.save_case(case_data)
        except Exception as exc:
            logger.warning(f"案件数据入库失败（不影响游戏）: {exc}")

        state = {
            "suspects": [
                {"name": s.name, "pressure": s.pressure}
                for s in self.engine.suspects
            ],
            "evidences": case_data.get("evidences", []),
            "timeLeft": self.engine.time_left,
            "current_suspect_index": 0,
            "state": self.engine.state,
            "case_id": case_data.get("case_id", ""),
            "caseTitle": case_data.get("title", ""),
            "caseBackground": {
                "title": case_data.get("title", ""),
                "victim": case_data.get("victim", ""),
                "causeOfDeath": case_data.get("cause_of_death", ""),
                "crimeScene": case_data.get("crime_scene", ""),
            },
            "suspectProfiles": [
                {
                    "name": s.get("name", ""),
                    "role": s.get("role", ""),
                    "personality": s.get("personality", ""),
                }
                for s in case_data.get("suspects", [])
            ],
        }

        self.bridge.init_full_state.emit({"state": state, "interactive": True})

        self._emit_case_briefing(case_data)

        if self.engine.suspects:
            self._on_suspect_changed(0)

    def _on_suspect_changed(self, index):
        """处理嫌疑人切换。"""
        logger.debug(f"切换嫌疑人: index={index}")
        if self.engine is None or index < 0:
            return

        info = self.engine.select_suspect(index)
        self.bridge.update_suspect.emit(info["name"], info["pressure"])

        if self.engine.state == "interrogating":
            self._countdown_timer.start()

    def _on_chat_message_sent(self, text):
        """处理用户发送的聊天消息。"""
        logger.debug(f"用户发送消息: {text[:50]}")
        if self.engine is None:
            return
        self._start_worker("chat", text)

    def _on_pressure(self):
        """处理施压操作。"""
        suspect_name = (
            self.engine.suspects[self.engine.current_suspect_index].name
            if self.engine
            else "N/A"
        )
        logger.debug(f"用户施压，当前嫌疑人: {suspect_name}")
        if self.engine is None:
            return
        self._start_worker("pressure", "对嫌疑人施压")

    def _on_empathy(self):
        """处理共情操作。"""
        suspect_name = (
            self.engine.suspects[self.engine.current_suspect_index].name
            if self.engine
            else "N/A"
        )
        logger.debug(f"用户共情，当前嫌疑人: {suspect_name}")
        if self.engine is None:
            return
        self._start_worker("empathy", "对嫌疑人表示共情")

    def _on_evidence_selected(self, evidence_id):
        """处理证据出示。"""
        logger.debug(f"用户出示证据: {evidence_id}")
        if self.engine is None:
            return

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

        self.bridge.set_input_enabled.emit(False)
        self.bridge.show_typing_indicator.emit(True)

        self._current_worker = WebWorker(
            self.engine, action, content, evidence_id
        )
        self._current_worker.finished.connect(self._on_worker_finished)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.start()

    def _on_worker_finished(self, events):
        """Worker 完成，处理事件。"""
        self.update_ui_from_engine(events)
        # 只有在引擎仍处于可交互状态时才启用输入
        if self.engine and self.engine.state not in ("breakdown", "verdict"):
            self.bridge.set_input_enabled.emit(True)
        self.bridge.show_typing_indicator.emit(False)
        self._current_worker = None

    def _on_worker_error(self, error_msg):
        """Worker 出错。"""
        logger.error(f"操作失败: {error_msg}")
        self.bridge.add_message.emit("system", f"操作失败: {error_msg}", "")
        self.bridge.set_input_enabled.emit(True)
        self.bridge.show_typing_indicator.emit(False)
        self._current_worker = None

    def _on_worker_timeout(self):
        """Worker 超时。"""
        if self._current_worker and self._current_worker.isRunning():
            self._current_worker.interrupt()
            self._current_worker.wait(2000)
            self.bridge.add_message.emit("system", "响应超时，请重试", "")
            self.bridge.set_input_enabled.emit(True)
            self.bridge.show_typing_indicator.emit(False)
            self._current_worker = None

    def _on_cancel_operation(self):
        """用户取消操作。"""
        if self._current_worker and self._current_worker.isRunning():
            self._current_worker.interrupt()
            self._current_worker.wait(2000)
            self.bridge.add_message.emit("system", "操作已取消", "")
            self.bridge.set_input_enabled.emit(True)
            self.bridge.show_typing_indicator.emit(False)
            self._current_worker = None

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
        self.bridge.set_game_interactive.emit(False)  # 禁用所有操作

        new_state = state_event["new_state"]
        if new_state == "breakdown":
            message = "破案成功！真凶已经崩溃认罪。"
        elif new_state == "verdict":
            message = "时间耗尽！律师介入，案件被迫终止。"
        else:
            message = f"游戏结束: {new_state}"

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
        self._countdown_timer.stop()

        self.bridge.init_full_state.emit({
            "state": {
                "suspects": [],
                "evidences": [],
                "timeLeft": 0,
                "current_suspect_index": 0,
                "state": "selecting",
                "case_id": "",
                "caseTitle": "",
            },
            "interactive": False,
        })

    # ================================================================
    # Review
    # ================================================================

    def _on_review_requested(self):
        """生成审讯复盘报告。"""
        if self.engine is None:
            return
        if self._review_worker and self._review_worker.isRunning():
            return

        self._review_worker = ReviewWorker(self.engine)
        self._review_worker.finished.connect(self._on_review_ready)
        self._review_worker.error.connect(self._on_review_error)
        self._review_worker.start()

        self.bridge.show_loading.emit("正在生成审讯复盘报告...", False)

    def _on_review_ready(self, review_data):
        """复盘报告生成成功。"""
        self._review_worker = None
        self.bridge.hide_loading.emit()

        QTimer.singleShot(350, lambda: self._emit_show_review(review_data))

    def _emit_show_review(self, review_data):
        if self.engine is not None:
            case_data = self.engine.case
            review_data["caseTruth"] = {
                "title": case_data.get("title", ""),
                "victim": case_data.get("victim", ""),
                "causeOfDeath": case_data.get("cause_of_death", ""),
                "crimeScene": case_data.get("crime_scene", ""),
                "truth": case_data.get("truth", ""),
            }

        self.bridge.show_review.emit(review_data)

    def _on_review_error(self, error_msg):
        """复盘报告生成失败。"""
        self._review_worker = None
        self.bridge.hide_loading.emit()
        QTimer.singleShot(350, lambda: self.bridge.show_dialog.emit("复盘失败", f"生成复盘报告失败: {error_msg}"))

    # ================================================================
    # Settings - WebView Modal
    # ================================================================

    def _on_llm_settings(self):
        """发送当前设置数据到前端显示设置模态框。"""
        settings = get_settings()
        provider_id = settings["provider"]
        api_key = get_api_key(provider_id=provider_id)
        providers_raw = get_provider_list()
        models = get_provider_models(provider_id)

        from core.providers import PROVIDERS

        providers = []
        for p in providers_raw:
            pid = p["id"]
            pinfo = PROVIDERS.get(pid, {})
            providers.append({
                "id": pid,
                "name": p["name"],
                "default_base_url": pinfo.get("base_url", ""),
                "default_model": pinfo.get("default_model", ""),
                "models": pinfo.get("models", []),
            })

        modal_data = {
            "provider": provider_id,
            "api_key": api_key,
            "base_url": settings["base_url"],
            "model": settings["model"],
            "providers": providers,
            "models": models,
        }
        self.bridge.show_settings_modal.emit(modal_data)

    def _on_submit_settings(self, provider, api_key, base_url, model):
        """保存设置。"""
        if not api_key or not base_url or not model:
            self.bridge.settings_test_result.emit(
                False, "API Key、Base URL 和模型名称不能为空"
            )
            return

        save_settings(provider, base_url, model, api_key)

        try:
            from core.llm_client import llm_client

            llm_client.reinitialize(provider, api_key, base_url, model)
        except Exception as exc:
            logger.warning(f"LLMClient 重新初始化失败: {exc}")

        if self.engine and hasattr(self.engine, "reinitialize_llm"):
            try:
                self.engine.reinitialize_llm()
            except Exception as exc:
                logger.warning(f"Engine reinit: {exc}")

        self.bridge.settings_saved.emit()

    def _on_test_connection(self, api_key, base_url, model):
        """在后台线程中测试 LLM 连接。"""
        if self._test_worker and self._test_worker.isRunning():
            return

        if not api_key or not base_url or not model:
            self.bridge.settings_test_result.emit(
                False, "API Key、Base URL 和模型名称不能为空"
            )
            return

        self._test_worker = TestConnectionWorker(api_key, base_url, model)
        self._test_worker.finished.connect(self._on_test_connection_result)
        self._test_worker.start()

    def _on_test_connection_result(self, success, message):
        """测试连接结果回调。"""
        self.bridge.settings_test_result.emit(success, message)
        self._test_worker = None

    # ================================================================
    # Case Generation - WebView Modal
    # ================================================================

    def _on_generate_case(self):
        """显示案件生成模态框。"""
        logger.info("请求生成新案件")
        self.bridge.show_generate_modal.emit()

    def _on_submit_case_generation(self, background, model, safe_mode=False):
        """在后台线程中生成案件。"""
        if self._case_gen_worker and self._case_gen_worker.isRunning():
            return

        if not background.strip():
            self.bridge.case_generation_error.emit('{"type":"empty","raw":"背景故事不能为空"}')
            return

        self._case_gen_cancelled = False
        self._case_gen_worker = CaseGenerateWorker(
            background, model.strip() or None, safe_mode=safe_mode
        )
        self._case_gen_worker.finished.connect(self._on_case_generated)
        self._case_gen_worker.error.connect(self._on_case_generation_error)
        self._case_gen_worker.progress.connect(self._on_case_generation_progress)
        self._case_gen_worker.start()

    def _on_submit_case_generation_safe(self, background, model):
        """在后台线程中用安全模式生成案件。"""
        self._on_submit_case_generation(background, model, safe_mode=True)

    def _on_case_generated(self, case_dict):
        """案件生成成功。"""
        if self._case_gen_cancelled:
            logger.info("案件已生成但用户已取消，丢弃结果")
            self._case_gen_worker = None
            return
        logger.info(f"案件生成成功: {case_dict.get('title', '未知')}")
        self.bridge.case_generation_complete.emit(case_dict)
        self._case_gen_worker = None
        QTimer.singleShot(350, lambda: self._deferred_load_case(case_dict))

    def _deferred_load_case(self, case_dict):
        """延迟加载案件，检查取消标志。"""
        if self._case_gen_cancelled:
            logger.info("延迟加载时用户已取消，丢弃案件结果")
            return
        self.load_case(case_dict)

    def _on_case_generation_error(self, error_msg):
        """案件生成失败。"""
        if self._case_gen_cancelled:
            logger.info("案件生成出错但用户已取消，丢弃错误")
            self._case_gen_worker = None
            return
        if error_msg.startswith("CONTENT_FILTER:"):
            raw = error_msg[len("CONTENT_FILTER:"):]
            error_json = '{"type":"content_filter","raw":' + json.dumps(raw, ensure_ascii=False) + '}'
        elif "JSON" in error_msg or "json" in error_msg or "解析" in error_msg:
            error_json = '{"type":"json_parse","raw":' + json.dumps(error_msg, ensure_ascii=False) + '}'
        elif "Schema" in error_msg or "校验" in error_msg or "schema" in error_msg.lower():
            error_json = '{"type":"schema","raw":' + json.dumps(error_msg, ensure_ascii=False) + '}'
        elif "网络" in error_msg or "Network" in error_msg or "连接" in error_msg:
            error_json = '{"type":"network","raw":' + json.dumps(error_msg, ensure_ascii=False) + '}'
        else:
            error_json = '{"type":"unknown","raw":' + json.dumps(error_msg, ensure_ascii=False) + '}'
        self.bridge.case_generation_error.emit(error_json)
        self._case_gen_worker = None

    def _on_case_generation_progress(self, status_msg):
        """案件生成进度更新。"""
        self.bridge.case_generation_progress.emit(status_msg)

    def _on_cancel_case_generation(self):
        """取消案件生成。"""
        self._case_gen_cancelled = True
        if self._case_gen_worker and self._case_gen_worker.isRunning():
            self._case_gen_worker.interrupt()
            self._case_gen_worker.wait(2000)
            self._case_gen_worker = None

    # ================================================================
    # Save / Load
    # ================================================================

    def _on_save_game(self):
        """存档管理 - 显示所有槽位供用户选择操作。"""
        try:
            slots = db.list_all_slots()
            formatted = self._format_slots(slots)
            has_active = self.engine is not None
            self.bridge.show_save_slots.emit({"slots": formatted, "_hasActiveGame": has_active})
        except Exception as exc:
            logger.error(f"获取存档列表失败: {exc}")
            self.bridge.show_dialog.emit("存档失败", f"无法读取存档列表: {exc}")

    def _on_save_to_slot(self, slot_number: int):
        """保存到指定槽位。"""
        if self.engine is None:
            return
        try:
            self._do_save_to_slot(slot_number)
        except Exception as exc:
            logger.error(f"存档失败: {exc}")
            self.bridge.show_dialog.emit("存档失败", f"保存失败: {exc}")

    def _do_save_to_slot(self, slot_number: int):
        """执行保存到指定槽位。"""
        case_id = self.engine.case.get("case_id", "unknown")
        case_title = self.engine.case.get("title", "未知案件")
        db.save_case(self.engine.case)
        engine_state_dict = self.engine.to_dict()
        db.save_session_to_slot(slot_number, case_id, engine_state_dict)
        logger.info(f"存档成功: slot={slot_number}, case={case_title}")
        from datetime import datetime as dt
        now_str = dt.now().strftime("%Y-%m-%d %H:%M")
        self.bridge.show_dialog.emit(
            "存档成功", f"「{case_title}」已保存到槽位 {slot_number}\n{now_str}"
        )

    def _on_delete_save(self, slot_number: int):
        """删除指定槽位存档。"""
        try:
            db.delete_session_by_slot(slot_number)
            logger.info(f"槽位 {slot_number} 存档已删除")
            self.bridge.show_dialog.emit("删除成功", f"槽位 {slot_number} 的存档已清除")
        except Exception as exc:
            logger.error(f"删除存档失败: {exc}")
            self.bridge.show_dialog.emit("删除失败", f"删除失败: {exc}")

    def _on_load_game(self):
        """读档 - 显示存档槽位列表（同存档管理入口）。"""
        self._on_save_game()

    def _format_slots(self, slots):
        """Format slot data for the frontend."""
        formatted = []
        for s in slots:
            slot = {
                "slot_number": s["slot_number"],
                "empty": s["empty"],
            }
            if not s["empty"]:
                case_id = s.get("case_id", "")
                case_data = db.load_case(case_id)
                if case_data:
                    case_title = case_data.get("title", "未知案件")
                else:
                    result = db.load_full_session(s["session_id"])
                    if result:
                        _, engine_state = result
                        case_title = engine_state.get("case_title", "未知案件")
                    else:
                        case_title = "未知案件"
                saved_at = s.get("saved_at", "")
                try:
                    from datetime import datetime as dt
                    parsed = dt.fromisoformat(saved_at)
                    date_str = parsed.strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError):
                    date_str = saved_at
                slot["session_id"] = s["session_id"]
                slot["name"] = case_title
                slot["date"] = date_str
            formatted.append(slot)
        return formatted

    def _on_save_selected(self, session_id):
        """选择存档后加载。"""
        logger.info(f"加载存档: session_id={session_id}")
        try:
            result = db.load_full_session(session_id)
            if result is None:
                self.bridge.show_dialog.emit("读档失败", "存档数据不存在")
                return

            case_id, engine_state_dict = result
            case_data = db.load_case(case_id)

            if case_data is None:
                case_title = engine_state_dict.get("case_title", "未知案件")
                self.bridge.show_dialog.emit(
                    "读档警告",
                    f"关联案件「{case_title}」的数据缺失，无法完整恢复。\n"
                    f"案件ID: {case_id}"
                )
                return

            self.engine = InterrogationEngine.from_dict(engine_state_dict, case_data)

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
                "caseBackground": {
                    "title": case_data.get("title", ""),
                    "victim": case_data.get("victim", ""),
                    "causeOfDeath": case_data.get("cause_of_death", ""),
                    "crimeScene": case_data.get("crime_scene", ""),
                },
                "suspectProfiles": [
                    {
                        "name": s.get("name", ""),
                        "role": s.get("role", ""),
                        "personality": s.get("personality", ""),
                    }
                    for s in case_data.get("suspects", [])
                ],
            }

            interactive = self.engine.state not in ("breakdown", "verdict")
            self.bridge.init_full_state.emit({"state": state, "interactive": interactive})

            messages = []
            for suspect in self.engine.suspects:
                for msg in suspect.memory:
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    if role == "user":
                        messages.append({"role": "player", "content": content, "suspectName": suspect.name})
                    elif role == "assistant":
                        messages.append({"role": "suspect", "content": content, "suspectName": suspect.name})

            if messages:
                self.bridge.init_messages.emit(messages)

            if self.engine.state == "interrogating":
                self._countdown_timer.start()
            elif self.engine.state in ("breakdown", "verdict"):
                if self.engine.state == "breakdown":
                    ending_msg = "破案成功！真凶已经崩溃认罪。"
                else:
                    ending_msg = "时间耗尽！律师介入，案件被迫终止。"
                QTimer.singleShot(400, lambda: self.bridge.show_ending_dialog.emit("审讯结束", ending_msg))
        except Exception as exc:
            logger.error(f"加载存档失败: {exc}")
            self.bridge.show_dialog.emit("读档失败", f"加载失败: {exc}")
