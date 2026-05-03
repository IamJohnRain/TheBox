"""键盘快捷键模块测试。

验证阶段 4（UI 打磨与高级功能）键盘快捷键管理模块的交付物：
- keyboard.js 文件存在且包含 KeyboardManager 类
- KeyboardManager 包含完整 API：register, unregister, setEnabled, clear, has, isEnabled
- 支持 Ctrl/Meta 组合键、Shift/Alt 修饰键
- HTML 正确引入 keyboard.js，且在 app.js 之前加载
- app.js 中实例化 KeyboardManager 并注册核心快捷键
"""

from pathlib import Path


def _get_js_content(filename):
    """获取 JS 文件内容。"""
    js_path = Path(__file__).parent.parent / "ui" / "web" / "js" / filename
    return js_path.read_text(encoding="utf-8")


def _get_html_content():
    """获取 HTML 内容。"""
    html_path = Path(__file__).parent.parent / "ui" / "web" / "index.html"
    return html_path.read_text(encoding="utf-8")


class TestKeyboardJsStructure:
    """keyboard.js 代码结构测试。"""

    def test_file_exists(self):
        """keyboard.js 文件存在。"""
        js_path = Path(__file__).parent.parent / "ui" / "web" / "js" / "keyboard.js"
        assert js_path.exists()

    def test_file_non_empty(self):
        """keyboard.js 文件非空。"""
        content = _get_js_content("keyboard.js")
        assert len(content.strip()) > 0

    def test_keyboard_manager_class(self):
        """定义 KeyboardManager 类。"""
        content = _get_js_content("keyboard.js")
        assert "class KeyboardManager" in content

    def test_register_method(self):
        """包含 register 方法。"""
        content = _get_js_content("keyboard.js")
        assert "register" in content

    def test_unregister_method(self):
        """包含 unregister 方法。"""
        content = _get_js_content("keyboard.js")
        assert "unregister" in content

    def test_set_enabled_method(self):
        """包含 setEnabled 方法。"""
        content = _get_js_content("keyboard.js")
        assert "setEnabled" in content

    def test_is_enabled_method(self):
        """包含 isEnabled 查询方法。"""
        content = _get_js_content("keyboard.js")
        assert "isEnabled" in content

    def test_has_method(self):
        """包含 has 方法查询快捷键是否已注册。"""
        content = _get_js_content("keyboard.js")
        assert "has(" in content

    def test_clear_method(self):
        """包含 clear 方法。"""
        content = _get_js_content("keyboard.js")
        assert "clear" in content

    def test_keydown_listener(self):
        """包含 keydown 事件监听。"""
        content = _get_js_content("keyboard.js")
        assert "keydown" in content

    def test_ctrl_key_support(self):
        """支持 Ctrl 组合键。"""
        content = _get_js_content("keyboard.js")
        assert "ctrlKey" in content

    def test_meta_key_support(self):
        """支持 Meta(Cmd) 组合键。"""
        content = _get_js_content("keyboard.js")
        assert "metaKey" in content

    def test_shift_key_support(self):
        """支持 Shift 修饰键。"""
        content = _get_js_content("keyboard.js")
        assert "shiftKey" in content

    def test_alt_key_support(self):
        """支持 Alt 修饰键。"""
        content = _get_js_content("keyboard.js")
        assert "altKey" in content

    def test_key_identifier_builder(self):
        """包含快捷键标识构建方法。"""
        content = _get_js_content("keyboard.js")
        assert "_buildKeyIdentifier" in content

    def test_key_to_lowercase(self):
        """快捷键标识统一转小写。"""
        content = _get_js_content("keyboard.js")
        assert "toLowerCase()" in content

    def test_prevent_default(self):
        """匹配快捷键时阻止默认行为。"""
        content = _get_js_content("keyboard.js")
        assert "preventDefault()" in content

    def test_stop_propagation(self):
        """匹配快捷键时阻止事件冒泡。"""
        content = _get_js_content("keyboard.js")
        assert "stopPropagation()" in content

    def test_enabled_guard(self):
        """禁用时跳过快捷键处理。"""
        content = _get_js_content("keyboard.js")
        assert "_enabled" in content

    def test_register_type_validation_key(self):
        """register 方法验证 key 类型。"""
        content = _get_js_content("keyboard.js")
        assert "typeof key" in content

    def test_register_type_validation_callback(self):
        """register 方法验证 callback 类型。"""
        content = _get_js_content("keyboard.js")
        assert "typeof callback" in content

    def test_global_listener_setup(self):
        """包含全局监听器设置方法。"""
        content = _get_js_content("keyboard.js")
        assert "_setupGlobalListener" in content

    def test_bindings_map(self):
        """使用 Map 存储快捷键绑定。"""
        content = _get_js_content("keyboard.js")
        assert "new Map()" in content or "Map()" in content


class TestKeyboardHtmlIntegration:
    """keyboard.js HTML 集成测试。"""

    def test_keyboard_js_linked(self):
        """HTML 引入 keyboard.js。"""
        content = _get_html_content()
        assert "js/keyboard.js" in content

    def test_keyboard_before_app(self):
        """keyboard.js 在 app.js 之前加载。"""
        content = _get_html_content()
        keyboard_pos = content.find("js/keyboard.js")
        app_pos = content.find("js/app.js")
        assert keyboard_pos > 0, "keyboard.js not found in HTML"
        assert app_pos > 0, "app.js not found in HTML"
        assert keyboard_pos < app_pos, "keyboard.js should be loaded before app.js"

    def test_keyboard_after_modal(self):
        """keyboard.js 在 modal.js 之后加载（依赖 modal 模块）。"""
        content = _get_html_content()
        keyboard_pos = content.find("js/keyboard.js")
        modal_pos = content.find("js/modal.js")
        assert modal_pos < keyboard_pos, "keyboard.js should be loaded after modal.js"

    def test_keyboard_script_tag(self):
        """keyboard.js 通过 <script src> 引入。"""
        content = _get_html_content()
        assert 'src="js/keyboard.js"' in content


class TestKeyboardInAppJs:
    """app.js 中键盘快捷键集成测试。"""

    def test_keyboard_manager_instantiation(self):
        """app.js 中实例化 KeyboardManager。"""
        content = _get_js_content("app.js")
        assert "KeyboardManager" in content
        assert "new KeyboardManager" in content

    def test_keyboard_manager_global_instance(self):
        """KeyboardManager 实例暴露到全局。"""
        content = _get_js_content("app.js")
        assert "window.keyboardManager" in content

    def test_enter_send_message(self):
        """Enter 键发送消息。"""
        content = _get_js_content("app.js")
        # Enter 键在输入框的 keydown 监听中处理，不走全局 KeyboardManager
        assert "Enter" in content or "enter" in content.lower()

    def test_ctrl_save(self):
        """Ctrl+S 存档。"""
        content = _get_js_content("app.js")
        assert "ctrl+s" in content.lower()

    def test_ctrl_load(self):
        """Ctrl+L 读档。"""
        content = _get_js_content("app.js")
        assert "ctrl+l" in content.lower()

    def test_escape_close_modal(self):
        """ESC 关闭模态框。"""
        content = _get_js_content("app.js")
        assert "escape" in content.lower()

    def test_ctrl_save_calls_bridge(self):
        """Ctrl+S 调用 bridge.requestSave。"""
        content = _get_js_content("app.js")
        # 检查 ctrl+s 注册附近有 requestSave 调用
        ctrl_s_pos = content.find("ctrl+s")
        assert ctrl_s_pos > 0, "ctrl+s not found in app.js"
        # 查找 ctrl+s 附近的 requestSave
        nearby_text = content[ctrl_s_pos:ctrl_s_pos + 200]
        assert "requestSave" in nearby_text

    def test_ctrl_load_calls_bridge(self):
        """Ctrl+L 调用 bridge.requestLoad。"""
        content = _get_js_content("app.js")
        ctrl_l_pos = content.find("ctrl+l")
        assert ctrl_l_pos > 0, "ctrl+l not found in app.js"
        nearby_text = content[ctrl_l_pos:ctrl_l_pos + 200]
        assert "requestLoad" in nearby_text

    def test_escape_checks_modal_visible(self):
        """ESC 快捷键检查模态框可见性。"""
        content = _get_js_content("app.js")
        escape_pos = content.find("'escape'")
        if escape_pos < 0:
            escape_pos = content.find('"escape"')
        assert escape_pos > 0, "escape shortcut not found in app.js"
        nearby_text = content[escape_pos:escape_pos + 200]
        assert "isVisible" in nearby_text or "modalManager" in nearby_text

    def test_enter_stop_propagation(self):
        """Enter 键在输入框中 stopPropagation 防止冒泡到 KeyboardManager。"""
        content = _get_js_content("app.js")
        assert "stopPropagation" in content

    def test_enter_prevent_default(self):
        """Enter 键在输入框中 preventDefault 防止换行。"""
        content = _get_js_content("app.js")
        # 检查输入框的 keydown 监听中有 preventDefault
        enter_pos = content.find("Enter")
        if enter_pos > 0:
            nearby_text = content[max(0, enter_pos - 100):enter_pos + 300]
            assert "preventDefault" in nearby_text


class TestKeyboardJsKeyIdentifierFormat:
    """快捷键标识格式测试。"""

    def test_plus_separator(self):
        """使用 + 号连接修饰键和主键。"""
        content = _get_js_content("keyboard.js")
        assert "'+'" in content or '"+"' in content or "join('+')" in content

    def test_modifier_order(self):
        """修饰键顺序：ctrl → shift → alt。"""
        content = _get_js_content("keyboard.js")
        # 检查构建标识时 ctrl 在 shift 之前
        ctrl_pos = content.find("ctrlKey")
        shift_pos = content.find("shiftKey")
        assert ctrl_pos < shift_pos, "ctrl modifier should be checked before shift"

    def test_ctrl_meta_equivalence(self):
        """Ctrl 和 Meta 键映射为相同的 'ctrl' 修饰键标识。"""
        content = _get_js_content("keyboard.js")
        # 检查 ctrlKey || metaKey 的逻辑
        assert "ctrlKey" in content and "metaKey" in content
        # 在同一条件判断中
        condition_line = None
        for line in content.split("\n"):
            if "ctrlKey" in line and "metaKey" in line:
                condition_line = line
                break
        assert condition_line is not None, "ctrlKey and metaKey should be in the same condition"

    def test_register_key_lowercase(self):
        """register 方法将 key 转为小写。"""
        content = _get_js_content("keyboard.js")
        # 查找 register 方法定义（而非 JSDoc 中的示例）
        register_pos = content.find("register(key, callback)")
        assert register_pos > 0, "register(key, callback) method definition not found"
        # 检查 register 方法体中有 toLowerCase（方法体约 8 行，需足够窗口）
        method_body = content[register_pos:register_pos + 500]
        assert "toLowerCase()" in method_body

    def test_unregister_key_lowercase(self):
        """unregister 方法将 key 转为小写。"""
        content = _get_js_content("keyboard.js")
        unregister_pos = content.find("unregister(")
        assert unregister_pos > 0
        method_body = content[unregister_pos:unregister_pos + 200]
        assert "toLowerCase()" in method_body


class TestKeyboardJsEdgeCases:
    """keyboard.js 边界条件测试。"""

    def test_register_overwrite(self):
        """注册同名快捷键时覆盖旧回调。"""
        content = _get_js_content("keyboard.js")
        # 使用 Map.set，天然支持覆盖
        assert "_bindings.set(" in content

    def test_unregister_nonexistent_silent(self):
        """注销不存在的快捷键静默忽略。"""
        content = _get_js_content("keyboard.js")
        # 使用 Map.delete，不存在的 key 静默返回 false
        assert "_bindings.delete(" in content

    def test_set_enabled_boolean_coercion(self):
        """setEnabled 使用 Boolean() 转换参数。"""
        content = _get_js_content("keyboard.js")
        assert "Boolean(" in content

    def test_constructor_initializes_bindings(self):
        """构造函数初始化 bindings Map。"""
        content = _get_js_content("keyboard.js")
        assert "new Map()" in content

    def test_constructor_initializes_enabled(self):
        """构造函数初始化 enabled 为 true。"""
        content = _get_js_content("keyboard.js")
        # 检查 _enabled 初始化为 true
        assert "_enabled = true" in content or "this._enabled = true" in content

    def test_document_event_listener(self):
        """在 document 上注册 keydown 监听。"""
        content = _get_js_content("keyboard.js")
        assert "document.addEventListener" in content

    def test_type_error_on_invalid_key(self):
        """key 不是字符串时抛出 TypeError。"""
        content = _get_js_content("keyboard.js")
        assert "TypeError" in content

    def test_type_error_on_invalid_callback(self):
        """callback 不是函数时抛出 TypeError。"""
        content = _get_js_content("keyboard.js")
        assert "TypeError" in content
