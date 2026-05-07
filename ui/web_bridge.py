"""Python 与 JavaScript 的通信桥接模块。

通过 QWebChannel 暴露信号和槽，实现 Python ↔ JS 双向通信。
"""

from PySide6.QtCore import QObject, Signal, Slot


class WebBridge(QObject):
    """Python 与 JavaScript 的通信桥接。

    所有 Python → JS 的更新通过信号（Signal）发送。
    所有 JS → Python 的操作通过槽（Slot）接收。
    """

    # === JS → Python 信号 ===
    message_sent = Signal(str)
    suspect_selected = Signal(int)
    evidence_presented = Signal(str)
    pressure_applied = Signal()
    empathy_applied = Signal()
    save_requested = Signal()
    load_requested = Signal()
    settings_requested = Signal()
    generate_case_requested = Signal()
    cancel_requested = Signal()
    save_selected = Signal(str)
    save_to_slot_requested = Signal(int)
    delete_save_requested = Signal(int)
    submit_settings_requested = Signal(str, str, str, str)
    test_connection_requested = Signal(str, str, str)
    submit_case_generation_requested = Signal(str, str)
    submit_case_generation_safe_requested = Signal(str, str)
    cancel_case_generation_requested = Signal()

    # === Python → JS 信号 ===
    # 游戏状态
    init_game_state = Signal(dict)
    init_full_state = Signal(dict)
    init_messages = Signal(list)
    update_suspect = Signal(str, int)  # name, pressure
    add_message = Signal(str, str, str)  # role, content, suspect_name
    update_timer = Signal(int)  # time_left
    update_evidence_list = Signal(list)  # evidences
    set_input_enabled = Signal(bool)
    show_dialog = Signal(str, str)  # title, message
    clear_chat = Signal()

    # 加载状态
    show_loading = Signal(str, bool)  # message, cancellable
    hide_loading = Signal()
    update_loading_progress = Signal(int)  # elapsed_seconds

    # Typing indicator
    show_typing_indicator = Signal(bool)  # visible

    # 存档列表
    show_save_list = Signal(list)  # sessions
    show_save_slots = Signal(dict)  # slot data for save/load UI

    # 游戏交互控制
    set_game_interactive = Signal(bool)  # 控制所有游戏操作

    # 结局对话框
    show_ending_dialog = Signal(str, str)  # title, message
    restart_requested = Signal()
    return_to_menu_requested = Signal()

    # 案件资料
    case_briefing_requested = Signal()
    show_case_briefing = Signal(dict)  # case_briefing_data

    # 复盘相关
    review_requested = Signal()
    show_review = Signal(dict)  # review_data

    # 设置对话框
    show_settings_modal = Signal(dict)  # settings_data
    settings_test_result = Signal(bool, str)  # success, message
    settings_saved = Signal()

    # 案件生成对话框
    show_generate_modal = Signal()
    case_generation_progress = Signal(str)  # status_message
    case_generation_complete = Signal(dict)  # case_data
    case_generation_error = Signal(str)  # error_message

    # 供词和恐惧更新
    confession_update = Signal(int, int, float)  # suspect_index, level, progress
    fear_update = Signal(int, int, str)  # suspect_index, fear_value, reason
    interaction_limits_update = Signal(int, int, int, int)  # suspect_index, chat, pressure, empathy

    # === JS → Python 槽 ===

    @Slot(str)
    def sendMessage(self, text: str):
        """发送聊天消息。"""
        self.message_sent.emit(text)

    @Slot(int)
    def selectSuspect(self, index: int):
        """选择嫌疑人。"""
        self.suspect_selected.emit(index)

    @Slot(str)
    def presentEvidence(self, evidence_id: str):
        """出示证据。"""
        self.evidence_presented.emit(evidence_id)

    @Slot()
    def applyPressure(self):
        """施压操作。"""
        self.pressure_applied.emit()

    @Slot()
    def applyEmpathy(self):
        """共情操作。"""
        self.empathy_applied.emit()

    @Slot()
    def requestSave(self):
        """请求存档。"""
        self.save_requested.emit()

    @Slot()
    def requestLoad(self):
        """请求读档。"""
        self.load_requested.emit()

    @Slot()
    def requestSettings(self):
        """请求打开设置。"""
        self.settings_requested.emit()

    @Slot()
    def requestGenerateCase(self):
        """请求生成案件。"""
        self.generate_case_requested.emit()

    @Slot()
    def cancelOperation(self):
        """取消当前操作。"""
        self.cancel_requested.emit()

    @Slot(str)
    def selectSave(self, session_id: str):
        """选择存档。"""
        self.save_selected.emit(session_id)

    @Slot(int)
    def saveToSlot(self, slot_number: int):
        """保存到指定槽位。"""
        self.save_to_slot_requested.emit(slot_number)

    @Slot(int)
    def deleteSave(self, slot_number: int):
        """删除指定槽位存档。"""
        self.delete_save_requested.emit(slot_number)

    @Slot()
    def requestRestart(self):
        """请求重新开始。"""
        self.restart_requested.emit()

    @Slot()
    def requestReturnToMenu(self):
        """请求返回主菜单。"""
        self.return_to_menu_requested.emit()

    @Slot(str, str, str, str)
    def submitSettings(self, provider: str, api_key: str, base_url: str, model: str):
        """提交设置表单。"""
        self.submit_settings_requested.emit(provider, api_key, base_url, model)

    @Slot(str, str, str)
    def testConnection(self, api_key: str, base_url: str, model: str):
        """测试 LLM 连接。"""
        self.test_connection_requested.emit(api_key, base_url, model)

    @Slot(str, str)
    def submitCaseGeneration(self, background: str, model: str):
        """提交案件生成请求。"""
        self.submit_case_generation_requested.emit(background, model)

    @Slot(str, str)
    def submitCaseGenerationSafe(self, background: str, model: str):
        """提交安全模式案件生成请求。"""
        self.submit_case_generation_safe_requested.emit(background, model)

    @Slot()
    def cancelCaseGeneration(self):
        """取消案件生成。"""
        self.cancel_case_generation_requested.emit()

    @Slot()
    def requestReview(self):
        """请求复盘报告。"""
        self.review_requested.emit()

    @Slot()
    def requestCaseBriefing(self):
        """请求查看案件资料。"""
        self.case_briefing_requested.emit()
