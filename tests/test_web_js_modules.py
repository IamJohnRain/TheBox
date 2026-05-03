"""JavaScript 模块测试。

验证阶段 2（JavaScript 通信层与核心模块）的交付物：
- 8 个 JS 文件存在且非空
- HTML 正确引入所有 JS 文件，且加载顺序正确
- 各 JS 模块包含预期的类定义、方法签名和关键逻辑
"""

import pytest
from pathlib import Path

from ui.resource_helper import get_html_url


def _get_html_content():
    """获取 index.html 内容。"""
    url = get_html_url()
    local_path = Path(url.toLocalFile())
    return local_path.read_text(encoding="utf-8")


def _get_js_content(filename):
    """获取 JS 文件内容。"""
    js_path = Path(__file__).parent.parent / "ui" / "web" / "js" / filename
    return js_path.read_text(encoding="utf-8")


class TestJsFileStructure:
    """JS 文件结构测试。"""

    def test_bridge_js_exists(self):
        """bridge.js 存在。"""
        js_path = Path(__file__).parent.parent / "ui" / "web" / "js" / "bridge.js"
        assert js_path.exists()

    def test_chat_js_exists(self):
        """chat.js 存在。"""
        js_path = Path(__file__).parent.parent / "ui" / "web" / "js" / "chat.js"
        assert js_path.exists()

    def test_suspect_js_exists(self):
        """suspect.js 存在。"""
        js_path = Path(__file__).parent.parent / "ui" / "web" / "js" / "suspect.js"
        assert js_path.exists()

    def test_evidence_js_exists(self):
        """evidence.js 存在。"""
        js_path = Path(__file__).parent.parent / "ui" / "web" / "js" / "evidence.js"
        assert js_path.exists()

    def test_timer_js_exists(self):
        """timer.js 存在。"""
        js_path = Path(__file__).parent.parent / "ui" / "web" / "js" / "timer.js"
        assert js_path.exists()

    def test_loading_js_exists(self):
        """loading.js 存在。"""
        js_path = Path(__file__).parent.parent / "ui" / "web" / "js" / "loading.js"
        assert js_path.exists()

    def test_modal_js_exists(self):
        """modal.js 存在。"""
        js_path = Path(__file__).parent.parent / "ui" / "web" / "js" / "modal.js"
        assert js_path.exists()

    def test_app_js_exists(self):
        """app.js 存在。"""
        js_path = Path(__file__).parent.parent / "ui" / "web" / "js" / "app.js"
        assert js_path.exists()


class TestJsFilesNonEmpty:
    """JS 文件非空测试。"""

    @pytest.mark.parametrize("filename", [
        "bridge.js", "chat.js", "suspect.js", "evidence.js",
        "timer.js", "loading.js", "modal.js", "app.js",
    ])
    def test_js_file_non_empty(self, filename):
        """JS 文件非空。"""
        content = _get_js_content(filename)
        assert len(content.strip()) > 0, f"{filename} is empty"


class TestJsHtmlIntegration:
    """JS 文件在 HTML 中的引入测试。"""

    def test_bridge_js_linked(self):
        """HTML 引入 bridge.js。"""
        content = _get_html_content()
        assert "js/bridge.js" in content

    def test_chat_js_linked(self):
        """HTML 引入 chat.js。"""
        content = _get_html_content()
        assert "js/chat.js" in content

    def test_suspect_js_linked(self):
        """HTML 引入 suspect.js。"""
        content = _get_html_content()
        assert "js/suspect.js" in content

    def test_evidence_js_linked(self):
        """HTML 引入 evidence.js。"""
        content = _get_html_content()
        assert "js/evidence.js" in content

    def test_timer_js_linked(self):
        """HTML 引入 timer.js。"""
        content = _get_html_content()
        assert "js/timer.js" in content

    def test_loading_js_linked(self):
        """HTML 引入 loading.js。"""
        content = _get_html_content()
        assert "js/loading.js" in content

    def test_modal_js_linked(self):
        """HTML 引入 modal.js。"""
        content = _get_html_content()
        assert "js/modal.js" in content

    def test_app_js_linked(self):
        """HTML 引入 app.js。"""
        content = _get_html_content()
        assert "js/app.js" in content

    def test_bridge_js_loaded_first(self):
        """bridge.js 在其他模块之前加载。"""
        content = _get_html_content()
        bridge_pos = content.find("js/bridge.js")
        app_pos = content.find("js/app.js")
        assert bridge_pos < app_pos

    def test_app_js_loaded_last(self):
        """app.js 在其他模块之后加载。"""
        content = _get_html_content()
        app_pos = content.find("js/app.js")
        # app.js 应该是最后一个应用 script 标签
        last_script_pos = content.rfind("</script>")
        # app.js 的 script 标签应该在最后一个 </script> 之前
        assert app_pos < last_script_pos

    def test_js_scripts_use_script_tag(self):
        """JS 文件通过 <script src> 引入。"""
        content = _get_html_content()
        assert '<script src="js/bridge.js">' in content or 'src="js/bridge.js"' in content

    def test_qwebchannel_loaded_before_bridge(self):
        """qwebchannel.js 在 bridge.js 之前加载。"""
        content = _get_html_content()
        qweb_pos = content.find("qwebchannel.js")
        bridge_pos = content.find("js/bridge.js")
        assert qweb_pos < bridge_pos


class TestBridgeJsStructure:
    """bridge.js 代码结构测试。"""

    def test_webbridge_class(self):
        """定义 WebBridge 类。"""
        content = _get_js_content("bridge.js")
        assert "class WebBridge" in content

    def test_init_method(self):
        """包含 init 方法。"""
        content = _get_js_content("bridge.js")
        assert "init()" in content

    def test_retry_mechanism(self):
        """包含重试机制。"""
        content = _get_js_content("bridge.js")
        assert "_maxRetries" in content or "maxRetries" in content
        assert "_initRetries" in content or "initRetries" in content

    def test_signal_listeners(self):
        """包含信号监听器设置。"""
        content = _get_js_content("bridge.js")
        assert "_setupSignalListeners" in content

    def test_on_method(self):
        """包含事件注册方法。"""
        content = _get_js_content("bridge.js")
        assert "on(" in content

    def test_off_method(self):
        """包含事件移除方法。"""
        content = _get_js_content("bridge.js")
        assert "off(" in content

    def test_trigger_method(self):
        """包含事件触发方法。"""
        content = _get_js_content("bridge.js")
        assert "_trigger" in content

    def test_send_message_method(self):
        """包含 sendMessage 方法。"""
        content = _get_js_content("bridge.js")
        assert "sendMessage" in content

    def test_select_suspect_method(self):
        """包含 selectSuspect 方法。"""
        content = _get_js_content("bridge.js")
        assert "selectSuspect" in content

    def test_present_evidence_method(self):
        """包含 presentEvidence 方法。"""
        content = _get_js_content("bridge.js")
        assert "presentEvidence" in content

    def test_cancel_operation_method(self):
        """包含 cancelOperation 方法。"""
        content = _get_js_content("bridge.js")
        assert "cancelOperation" in content

    def test_apply_pressure_method(self):
        """包含 applyPressure 方法。"""
        content = _get_js_content("bridge.js")
        assert "applyPressure" in content

    def test_apply_empathy_method(self):
        """包含 applyEmpathy 方法。"""
        content = _get_js_content("bridge.js")
        assert "applyEmpathy" in content

    def test_request_save_method(self):
        """包含 requestSave 方法。"""
        content = _get_js_content("bridge.js")
        assert "requestSave" in content

    def test_request_load_method(self):
        """包含 requestLoad 方法。"""
        content = _get_js_content("bridge.js")
        assert "requestLoad" in content

    def test_request_settings_method(self):
        """包含 requestSettings 方法。"""
        content = _get_js_content("bridge.js")
        assert "requestSettings" in content

    def test_request_generate_case_method(self):
        """包含 requestGenerateCase 方法。"""
        content = _get_js_content("bridge.js")
        assert "requestGenerateCase" in content

    def test_select_save_method(self):
        """包含 selectSave 方法。"""
        content = _get_js_content("bridge.js")
        assert "selectSave" in content

    def test_request_restart_method(self):
        """包含 requestRestart 方法。"""
        content = _get_js_content("bridge.js")
        assert "requestRestart" in content

    def test_request_return_to_menu_method(self):
        """包含 requestReturnToMenu 方法。"""
        content = _get_js_content("bridge.js")
        assert "requestReturnToMenu" in content

    def test_global_bridge_instance(self):
        """导出全局 bridge 实例。"""
        content = _get_js_content("bridge.js")
        assert "window.bridge" in content

    def test_qwebchannel_usage(self):
        """使用 QWebChannel API。"""
        content = _get_js_content("bridge.js")
        assert "QWebChannel" in content

    def test_python_bridge_reference(self):
        """引用 pythonBridge 对象。"""
        content = _get_js_content("bridge.js")
        assert "pythonBridge" in content

    def test_signal_connect_calls(self):
        """包含信号 connect 调用。"""
        content = _get_js_content("bridge.js")
        assert ".connect(" in content

    def test_init_game_state_signal(self):
        """监听 init_game_state 信号。"""
        content = _get_js_content("bridge.js")
        assert "init_game_state" in content

    def test_add_message_signal(self):
        """监听 add_message 信号。"""
        content = _get_js_content("bridge.js")
        assert "add_message" in content

    def test_update_suspect_signal(self):
        """监听 update_suspect 信号。"""
        content = _get_js_content("bridge.js")
        assert "update_suspect" in content

    def test_update_timer_signal(self):
        """监听 update_timer 信号。"""
        content = _get_js_content("bridge.js")
        assert "update_timer" in content

    def test_update_evidence_list_signal(self):
        """监听 update_evidence_list 信号。"""
        content = _get_js_content("bridge.js")
        assert "update_evidence_list" in content

    def test_set_input_enabled_signal(self):
        """监听 set_input_enabled 信号。"""
        content = _get_js_content("bridge.js")
        assert "set_input_enabled" in content

    def test_show_dialog_signal(self):
        """监听 show_dialog 信号。"""
        content = _get_js_content("bridge.js")
        assert "show_dialog" in content

    def test_clear_chat_signal(self):
        """监听 clear_chat 信号。"""
        content = _get_js_content("bridge.js")
        assert "clear_chat" in content

    def test_show_loading_signal(self):
        """监听 show_loading 信号。"""
        content = _get_js_content("bridge.js")
        assert "show_loading" in content

    def test_hide_loading_signal(self):
        """监听 hide_loading 信号。"""
        content = _get_js_content("bridge.js")
        assert "hide_loading" in content

    def test_update_loading_progress_signal(self):
        """监听 update_loading_progress 信号。"""
        content = _get_js_content("bridge.js")
        assert "update_loading_progress" in content

    def test_show_save_list_signal(self):
        """监听 show_save_list 信号。"""
        content = _get_js_content("bridge.js")
        assert "show_save_list" in content

    def test_show_ending_dialog_signal(self):
        """监听 show_ending_dialog 信号。"""
        content = _get_js_content("bridge.js")
        assert "show_ending_dialog" in content

    def test_callback_validation(self):
        """on() 方法验证回调类型。"""
        content = _get_js_content("bridge.js")
        assert "typeof callback" in content or "typeof callback !== 'function'" in content

    def test_retry_interval(self):
        """包含重试间隔配置。"""
        content = _get_js_content("bridge.js")
        assert "_retryInterval" in content or "retryInterval" in content

    def test_attempt_init_method(self):
        """包含 _attemptInit 方法。"""
        content = _get_js_content("bridge.js")
        assert "_attemptInit" in content

    def test_handle_init_failure_method(self):
        """包含 _handleInitFailure 方法。"""
        content = _get_js_content("bridge.js")
        assert "_handleInitFailure" in content


class TestChatJsStructure:
    """chat.js 代码结构测试。"""

    def test_chat_manager_class(self):
        """定义 ChatManager 类。"""
        content = _get_js_content("chat.js")
        assert "class ChatManager" in content

    def test_add_message_method(self):
        """包含 addMessage 方法。"""
        content = _get_js_content("chat.js")
        assert "addMessage" in content

    def test_clear_method(self):
        """包含 clear 方法。"""
        content = _get_js_content("chat.js")
        assert "clear" in content

    def test_set_input_enabled_method(self):
        """包含 setInputEnabled 方法。"""
        content = _get_js_content("chat.js")
        assert "setInputEnabled" in content

    def test_set_title_method(self):
        """包含 setTitle 方法。"""
        content = _get_js_content("chat.js")
        assert "setTitle" in content

    def test_get_input_text_method(self):
        """包含 getInputText 方法。"""
        content = _get_js_content("chat.js")
        assert "getInputText" in content

    def test_scroll_to_bottom(self):
        """包含自动滚动到底部逻辑。"""
        content = _get_js_content("chat.js")
        assert "_scrollToBottom" in content or "scrollToBottom" in content

    def test_escape_html(self):
        """包含 HTML 转义防 XSS。"""
        content = _get_js_content("chat.js")
        assert "_escapeHtml" in content or "escapeHtml" in content

    def test_message_role_types(self):
        """支持不同消息角色类型。"""
        content = _get_js_content("chat.js")
        assert "message-player" in content or "player" in content
        assert "message-suspect" in content or "suspect" in content
        assert "message-system" in content or "system" in content

    def test_empty_message_guard(self):
        """过滤空消息。"""
        content = _get_js_content("chat.js")
        assert "trim()" in content


class TestSuspectJsStructure:
    """suspect.js 代码结构测试。"""

    def test_suspect_manager_class(self):
        """定义 SuspectManager 类。"""
        content = _get_js_content("suspect.js")
        assert "class SuspectManager" in content

    def test_load_suspects_method(self):
        """包含 loadSuspects 方法。"""
        content = _get_js_content("suspect.js")
        assert "loadSuspects" in content

    def test_update_suspect_method(self):
        """包含 updateSuspect 方法。"""
        content = _get_js_content("suspect.js")
        assert "updateSuspect" in content

    def test_select_suspect_method(self):
        """包含 selectSuspect 方法。"""
        content = _get_js_content("suspect.js")
        assert "selectSuspect" in content

    def test_clear_method(self):
        """包含 clear 方法。"""
        content = _get_js_content("suspect.js")
        assert "clear" in content

    def test_pressure_bar_update(self):
        """包含压力条更新逻辑。"""
        content = _get_js_content("suspect.js")
        assert "_updatePressure" in content or "updatePressure" in content

    def test_pressure_class_levels(self):
        """压力级别分类（低/中/高）。"""
        content = _get_js_content("suspect.js")
        assert "low" in content
        assert "medium" in content
        assert "high" in content

    def test_status_badge_update(self):
        """包含状态徽章更新。"""
        content = _get_js_content("suspect.js")
        assert "_updateStatusBadge" in content or "statusBadge" in content

    def test_action_buttons_enabled(self):
        """包含操作按钮启用/禁用逻辑。"""
        content = _get_js_content("suspect.js")
        assert "_setActionButtonsEnabled" in content or "setActionButtonsEnabled" in content


class TestEvidenceJsStructure:
    """evidence.js 代码结构测试。"""

    def test_evidence_manager_class(self):
        """定义 EvidenceManager 类。"""
        content = _get_js_content("evidence.js")
        assert "class EvidenceManager" in content

    def test_load_evidences_method(self):
        """包含 loadEvidences 方法。"""
        content = _get_js_content("evidence.js")
        assert "loadEvidences" in content

    def test_clear_method(self):
        """包含 clear 方法。"""
        content = _get_js_content("evidence.js")
        assert "clear" in content

    def test_evidence_card_creation(self):
        """包含证据卡片创建逻辑。"""
        content = _get_js_content("evidence.js")
        assert "_addEvidenceCard" in content or "addEvidenceCard" in content

    def test_evidence_click_handler(self):
        """包含证据点击处理。"""
        content = _get_js_content("evidence.js")
        assert "_onEvidenceClick" in content or "onEvidenceClick" in content

    def test_present_evidence_via_bridge(self):
        """点击证据后通过 bridge 出示证据。"""
        content = _get_js_content("evidence.js")
        assert "presentEvidence" in content

    def test_escape_html(self):
        """包含 HTML 转义防 XSS。"""
        content = _get_js_content("evidence.js")
        assert "_escapeHtml" in content or "escapeHtml" in content

    def test_keyboard_support(self):
        """证据卡片支持键盘操作。"""
        content = _get_js_content("evidence.js")
        assert "keypress" in content or "keydown" in content


class TestTimerJsStructure:
    """timer.js 代码结构测试。"""

    def test_timer_manager_class(self):
        """定义 TimerManager 类。"""
        content = _get_js_content("timer.js")
        assert "class TimerManager" in content

    def test_update_method(self):
        """包含 update 方法。"""
        content = _get_js_content("timer.js")
        assert "update" in content

    def test_clear_method(self):
        """包含 clear 方法。"""
        content = _get_js_content("timer.js")
        assert "clear" in content

    def test_time_formatting(self):
        """时间格式化为 MM:SS。"""
        content = _get_js_content("timer.js")
        assert "padStart" in content

    def test_danger_class(self):
        """30秒以下添加危险样式。"""
        content = _get_js_content("timer.js")
        assert "danger" in content

    def test_warning_class(self):
        """60秒以下添加警告样式。"""
        content = _get_js_content("timer.js")
        assert "warning" in content


class TestLoadingJsStructure:
    """loading.js 代码结构测试。"""

    def test_loading_manager_class(self):
        """定义 LoadingManager 类。"""
        content = _get_js_content("loading.js")
        assert "class LoadingManager" in content

    def test_show_method(self):
        """包含 show 方法。"""
        content = _get_js_content("loading.js")
        assert "show" in content

    def test_hide_method(self):
        """包含 hide 方法。"""
        content = _get_js_content("loading.js")
        assert "hide" in content

    def test_update_progress_method(self):
        """包含 updateProgress 方法。"""
        content = _get_js_content("loading.js")
        assert "updateProgress" in content

    def test_cancel_button_binding(self):
        """取消按钮绑定 cancelOperation。"""
        content = _get_js_content("loading.js")
        assert "cancelOperation" in content

    def test_cancellable_parameter(self):
        """show 方法支持 cancellable 参数。"""
        content = _get_js_content("loading.js")
        assert "cancellable" in content

    def test_progress_timer(self):
        """包含进度更新定时器。"""
        content = _get_js_content("loading.js")
        assert "_startProgressUpdate" in content or "setInterval" in content

    def test_stop_progress_timer(self):
        """包含停止进度定时器。"""
        content = _get_js_content("loading.js")
        assert "_stopProgressUpdate" in content or "clearInterval" in content


class TestModalJsStructure:
    """modal.js 代码结构测试。"""

    def test_modal_manager_class(self):
        """定义 ModalManager 类。"""
        content = _get_js_content("modal.js")
        assert "class ModalManager" in content

    def test_show_info_method(self):
        """包含 showInfo 方法。"""
        content = _get_js_content("modal.js")
        assert "showInfo" in content

    def test_show_confirm_method(self):
        """包含 showConfirm 方法。"""
        content = _get_js_content("modal.js")
        assert "showConfirm" in content

    def test_show_save_list_method(self):
        """包含 showSaveList 方法。"""
        content = _get_js_content("modal.js")
        assert "showSaveList" in content

    def test_show_ending_dialog_method(self):
        """包含 showEndingDialog 方法。"""
        content = _get_js_content("modal.js")
        assert "showEndingDialog" in content

    def test_hide_method(self):
        """包含 hide 方法。"""
        content = _get_js_content("modal.js")
        assert "hide" in content

    def test_esc_key_close(self):
        """支持 ESC 键关闭模态框。"""
        content = _get_js_content("modal.js")
        assert "Escape" in content

    def test_backdrop_click_close(self):
        """支持点击遮罩层关闭。"""
        content = _get_js_content("modal.js")
        assert "backdrop" in content

    def test_confirm_callback(self):
        """确认对话框支持确认回调。"""
        content = _get_js_content("modal.js")
        assert "_confirmCallback" in content or "confirmCallback" in content

    def test_escape_html(self):
        """包含 HTML 转义防 XSS。"""
        content = _get_js_content("modal.js")
        assert "_escapeHtml" in content or "escapeHtml" in content

    def test_save_item_click_handler(self):
        """存档列表项点击调用 bridge.selectSave。"""
        content = _get_js_content("modal.js")
        assert "selectSave" in content


class TestAppJsStructure:
    """app.js 代码结构测试。"""

    def test_dom_content_loaded(self):
        """包含 DOMContentLoaded 事件监听。"""
        content = _get_js_content("app.js")
        assert "DOMContentLoaded" in content

    def test_bridge_init(self):
        """包含 Bridge 初始化。"""
        content = _get_js_content("app.js")
        # bridge.init() may span multiple lines (e.g. window.bridge\n  .init())
        assert "bridge" in content and ".init()" in content

    def test_module_initialization(self):
        """包含各模块初始化。"""
        content = _get_js_content("app.js")
        assert "ChatManager" in content
        assert "SuspectManager" in content
        assert "EvidenceManager" in content
        assert "TimerManager" in content

    def test_loading_manager_initialization(self):
        """包含 LoadingManager 初始化。"""
        content = _get_js_content("app.js")
        assert "LoadingManager" in content

    def test_modal_manager_initialization(self):
        """包含 ModalManager 初始化。"""
        content = _get_js_content("app.js")
        assert "ModalManager" in content

    def test_event_binding(self):
        """包含事件绑定。"""
        content = _get_js_content("app.js")
        assert "addEventListener" in content

    def test_bridge_event_binding(self):
        """包含 Bridge 信号事件绑定。"""
        content = _get_js_content("app.js")
        assert "bindBridgeEvents" in content

    def test_ui_event_binding(self):
        """包含 UI 事件绑定。"""
        content = _get_js_content("app.js")
        assert "bindUIEvents" in content

    def test_init_game_state_handler(self):
        """处理 initGameState 事件。"""
        content = _get_js_content("app.js")
        assert "initGameState" in content

    def test_new_message_handler(self):
        """处理 newMessage 事件。"""
        content = _get_js_content("app.js")
        assert "newMessage" in content

    def test_suspect_update_handler(self):
        """处理 suspectUpdate 事件。"""
        content = _get_js_content("app.js")
        assert "suspectUpdate" in content

    def test_timer_update_handler(self):
        """处理 timerUpdate 事件。"""
        content = _get_js_content("app.js")
        assert "timerUpdate" in content

    def test_evidence_update_handler(self):
        """处理 evidenceUpdate 事件。"""
        content = _get_js_content("app.js")
        assert "evidenceUpdate" in content

    def test_input_enabled_handler(self):
        """处理 inputEnabled 事件。"""
        content = _get_js_content("app.js")
        assert "inputEnabled" in content

    def test_show_dialog_handler(self):
        """处理 showDialog 事件。"""
        content = _get_js_content("app.js")
        assert "showDialog" in content

    def test_clear_chat_handler(self):
        """处理 clearChat 事件。"""
        content = _get_js_content("app.js")
        assert "clearChat" in content

    def test_show_loading_handler(self):
        """处理 showLoading 事件。"""
        content = _get_js_content("app.js")
        assert "showLoading" in content

    def test_hide_loading_handler(self):
        """处理 hideLoading 事件。"""
        content = _get_js_content("app.js")
        assert "hideLoading" in content

    def test_loading_progress_handler(self):
        """处理 loadingProgress 事件。"""
        content = _get_js_content("app.js")
        assert "loadingProgress" in content

    def test_show_save_list_handler(self):
        """处理 showSaveList 事件。"""
        content = _get_js_content("app.js")
        assert "showSaveList" in content

    def test_show_ending_dialog_handler(self):
        """处理 showEndingDialog 事件。"""
        content = _get_js_content("app.js")
        assert "showEndingDialog" in content

    def test_global_module_instances(self):
        """模块实例暴露到全局。"""
        content = _get_js_content("app.js")
        assert "window.chatManager" in content
        assert "window.suspectManager" in content
        assert "window.evidenceManager" in content
        assert "window.timerManager" in content
        assert "window.loadingManager" in content
        assert "window.modalManager" in content

    def test_iife_pattern(self):
        """使用 IIFE 避免全局污染。"""
        content = _get_js_content("app.js")
        assert "(function" in content or "(()" in content

    def test_strict_mode(self):
        """使用严格模式。"""
        content = _get_js_content("app.js")
        assert "use strict" in content

    def test_send_message_handler(self):
        """包含发送消息处理。"""
        content = _get_js_content("app.js")
        assert "sendMessage" in content

    def test_suspect_selector_change(self):
        """嫌疑人选择器 change 事件。"""
        content = _get_js_content("app.js")
        assert "suspect-selector" in content
        assert "change" in content


class TestJsModuleCrossReferences:
    """JS 模块间交叉引用测试。"""

    def test_evidence_references_bridge(self):
        """evidence.js 引用 bridge 出示证据。"""
        content = _get_js_content("evidence.js")
        assert "window.bridge" in content

    def test_evidence_references_modal(self):
        """evidence.js 引用 modalManager 确认。"""
        content = _get_js_content("evidence.js")
        assert "modalManager" in content

    def test_loading_references_bridge(self):
        """loading.js 引用 bridge 取消操作。"""
        content = _get_js_content("loading.js")
        assert "window.bridge" in content

    def test_modal_references_bridge(self):
        """modal.js 引用 bridge 选择存档。"""
        content = _get_js_content("modal.js")
        assert "window.bridge" in content

    def test_app_references_all_modules(self):
        """app.js 引用所有模块。"""
        content = _get_js_content("app.js")
        assert "chatManager" in content
        assert "suspectManager" in content
        assert "evidenceManager" in content
        assert "timerManager" in content
        assert "loadingManager" in content
        assert "modalManager" in content
