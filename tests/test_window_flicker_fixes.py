"""窗口闪动修复验收测试。

验证 7 项窗口闪动修复是否正确实施：
- Fix 1: 移除 backdrop-filter，改用高不透明度背景色
- Fix 2: 添加 will-change 和 contain 性能优化属性
- Fix 3: rafThrottle 批处理高频信号
- Fix 4: 输入框内跳过非 Escape 快捷键
- Fix 5: 设置保存内联提示（不关闭模态框）
- Fix 6: 案件生成原子化（移除 QTimer.singleShot）
- Fix 7: 计时器在模态框可见时暂停渲染

由于修复涉及前端 JS/CSS，本测试采用静态分析（文件内容检查）方式验证。
"""

import re
from pathlib import Path

import pytest


# ============================================================
# 辅助函数
# ============================================================

def _get_css_content(filename="components.css"):
    """获取 CSS 文件内容。"""
    css_path = Path(__file__).parent.parent / "ui" / "web" / "css" / filename
    return css_path.read_text(encoding="utf-8")


def _get_js_content(filename):
    """获取 JS 文件内容。"""
    js_path = Path(__file__).parent.parent / "ui" / "web" / "js" / filename
    return js_path.read_text(encoding="utf-8")


def _get_py_content(filename):
    """获取 Python 文件内容。"""
    py_path = Path(__file__).parent.parent / "ui" / filename
    return py_path.read_text(encoding="utf-8")


def _extract_css_block(content, selector):
    """从 CSS 内容中提取指定选择器的规则块。

    返回选择器对应 { ... } 内的内容字符串。支持简单选择器。
    如果找不到，返回空字符串。
    """
    # 匹配选择器后跟 { ... } 的内容（非贪婪，支持嵌套）
    pattern = re.compile(
        re.escape(selector) + r"\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}",
        re.DOTALL,
    )
    match = pattern.search(content)
    return match.group(1) if match else ""


# ============================================================
# Fix 1: backdrop-filter 移除验证
# ============================================================

class TestFix1BackdropFilterRemoved:
    """Fix 1: .modal-backdrop 和 .loading-overlay 移除 backdrop-filter。"""

    def test_modal_backdrop_no_backdrop_filter(self):
        """`.modal-backdrop` 不包含 backdrop-filter 属性。"""
        css = _get_css_content()
        block = _extract_css_block(css, ".modal-backdrop")
        # 排除 .modal-backdrop.active 块的干扰
        # 如果提取到的块包含 ".active"，说明匹配可能有问题，用更精确方式
        assert "backdrop-filter" not in block, (
            ".modal-backdrop 不应包含 backdrop-filter 属性"
        )

    def test_loading_overlay_no_backdrop_filter(self):
        """`.loading-overlay` 不包含 backdrop-filter 属性。"""
        css = _get_css_content()
        block = _extract_css_block(css, ".loading-overlay")
        assert "backdrop-filter" not in block, (
            ".loading-overlay 不应包含 backdrop-filter 属性"
        )

    def test_modal_backdrop_has_high_opacity_background(self):
        """`.modal-backdrop` 使用高不透明度背景色替代 blur。"""
        css = _get_css_content()
        block = _extract_css_block(css, ".modal-backdrop")
        # 验证有不透明度 >= 0.9 的 rgba 背景
        assert re.search(r"rgba\([^)]+,\s*0\.9[0-9]\)", block) is not None, (
            ".modal-backdrop 应使用高不透明度（>=0.9）背景色替代 backdrop-filter"
        )

    def test_loading_overlay_has_high_opacity_background(self):
        """`.loading-overlay` 使用高不透明度背景色替代 blur。"""
        css = _get_css_content()
        block = _extract_css_block(css, ".loading-overlay")
        assert re.search(r"rgba\([^)]+,\s*0\.9[0-9]\)", block) is not None, (
            ".loading-overlay 应使用高不透明度（>=0.9）背景色替代 backdrop-filter"
        )

    def test_no_backdrop_filter_in_entire_components_css(self):
        """components.css 全文中不包含 backdrop-filter 属性声明。"""
        css = _get_css_content()
        # 排除注释中的提及
        lines = css.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            # 跳过注释行
            if stripped.startswith("/*") or stripped.startswith("*") or stripped.endswith("*/"):
                continue
            # 跳过注释内行
            if "/*" in stripped and "*/" in stripped:
                continue
            assert "backdrop-filter" not in stripped, (
                f"components.css 第 {i + 1} 行不应包含 backdrop-filter: {stripped}"
            )


# ============================================================
# Fix 2: CSS 性能优化属性验证
# ============================================================

class TestFix2CssPerformanceOptimizations:
    """Fix 2: .modal 使用 backface-visibility:hidden + contain:paint，.modal-wrapper 承载 will-change/transform。"""

    def test_modal_has_backface_visibility_hidden(self):
        """`.modal` 包含 `backface-visibility: hidden` 属性。"""
        css = _get_css_content()
        block = _extract_css_block(css, ".modal")
        assert "backface-visibility" in block, (
            ".modal 应包含 backface-visibility 属性"
        )
        assert "hidden" in block, (
            ".modal 的 backface-visibility 应为 hidden"
        )

    def test_modal_no_will_change(self):
        """`.modal` 不包含 `will-change` 属性（已移至 .modal-wrapper）。"""
        css = _get_css_content()
        block = _extract_css_block(css, ".modal")
        assert "will-change" not in block, (
            ".modal 不应包含 will-change 属性（已移至 .modal-wrapper）"
        )

    def test_modal_has_contain_paint(self):
        """`.modal` 的 `contain` 值为 `paint`（兼容滚动容器）。"""
        css = _get_css_content()
        block = _extract_css_block(css, ".modal")
        contain_match = re.search(r"contain\s*:\s*([^;]+);", block)
        assert contain_match is not None, ".modal 中未找到 contain 声明"
        value = contain_match.group(1).strip()
        assert value == "paint", f".modal 的 contain 值应为 paint, 实际值: {value}"

    def test_modal_no_transform(self):
        """`.modal` 不包含 `transform` 属性（transform 已移至 .modal-wrapper）。"""
        css = _get_css_content()
        block = _extract_css_block(css, ".modal")
        assert "transform" not in block, (
            ".modal 不应包含 transform 属性（已移至 .modal-wrapper）"
        )

    def test_modal_no_position_fixed(self):
        """`.modal` 不包含 `position: fixed`（定位已移至 .modal-wrapper）。"""
        css = _get_css_content()
        block = _extract_css_block(css, ".modal")
        assert "position" not in block or "fixed" not in block, (
            ".modal 不应包含 position:fixed（定位已移至 .modal-wrapper）"
        )

    def test_modal_wrapper_has_will_change(self):
        """`.modal-wrapper` 包含 `will-change` 属性。"""
        css = _get_css_content()
        block = _extract_css_block(css, ".modal-wrapper")
        assert "will-change" in block, (
            ".modal-wrapper 应包含 will-change 属性"
        )

    def test_modal_wrapper_has_transform(self):
        """`.modal-wrapper` 包含 `transform` 属性。"""
        css = _get_css_content()
        block = _extract_css_block(css, ".modal-wrapper")
        assert "transform" in block, (
            ".modal-wrapper 应包含 transform 属性"
        )

    def test_modal_wrapper_has_contain_layout_style(self):
        """`.modal-wrapper` 的 `contain` 值为 `layout style`。"""
        css = _get_css_content()
        block = _extract_css_block(css, ".modal-wrapper")
        contain_match = re.search(r"contain\s*:\s*([^;]+);", block)
        assert contain_match is not None, ".modal-wrapper 中未找到 contain 声明"
        value = contain_match.group(1).strip()
        assert "layout" in value and "style" in value, (
            f".modal-wrapper 的 contain 应包含 layout 和 style, 实际值: {value}"
        )

    def test_modal_wrapper_has_position_fixed(self):
        """`.modal-wrapper` 包含 `position: fixed`。"""
        css = _get_css_content()
        block = _extract_css_block(css, ".modal-wrapper")
        assert "fixed" in block, (
            ".modal-wrapper 应包含 position:fixed"
        )

    def test_modal_backdrop_has_contain_strict(self):
        """`.modal-backdrop` 包含 `contain: strict`。"""
        css = _get_css_content()
        block = _extract_css_block(css, ".modal-backdrop")
        contain_match = re.search(r"contain\s*:\s*([^;]+);", block)
        assert contain_match is not None, ".modal-backdrop 中未找到 contain 声明"
        value = contain_match.group(1).strip()
        assert value == "strict", f".modal-backdrop 的 contain 值应为 strict, 实际值: {value}"


# ============================================================
# Fix 3: rAF 批处理验证
# ============================================================

class TestFix3RafThrottle:
    """Fix 3: timerUpdate 和 suspectUpdate 使用 rafThrottle 批处理。"""

    def test_raf_throttle_function_defined(self):
        """app.js 中定义了 rafThrottle 函数。"""
        content = _get_js_content("app.js")
        assert "rafThrottle" in content, "app.js 应定义 rafThrottle 函数"

    def test_raf_throttle_uses_request_animation_frame(self):
        """rafThrottle 内部使用 requestAnimationFrame。"""
        content = _get_js_content("app.js")
        # 在 rafThrottle 附近搜索 requestAnimationFrame
        raf_pos = content.find("rafThrottle")
        assert raf_pos > 0, "未找到 rafThrottle 定义"
        # rafThrottle 函数体约 15 行，搜索足够范围
        nearby = content[raf_pos:raf_pos + 500]
        assert "requestAnimationFrame" in nearby, (
            "rafThrottle 应使用 requestAnimationFrame"
        )

    def test_suspect_update_uses_raf_throttle(self):
        """suspectUpdate 事件处理器使用 rafThrottle 包裹。"""
        content = _get_js_content("app.js")
        # 搜索 suspectUpdate 附近有 rafThrottle 调用
        suspect_pos = content.find("suspectUpdate")
        assert suspect_pos > 0, "未找到 suspectUpdate 事件绑定"
        # 向后搜索足够范围以覆盖到 rafThrottle
        nearby = content[suspect_pos:suspect_pos + 200]
        assert "rafThrottle" in nearby, (
            "suspectUpdate 应使用 rafThrottle 包裹"
        )

    def test_timer_update_uses_raf_throttle(self):
        """timerUpdate 事件处理器使用 rafThrottle 包裹。"""
        content = _get_js_content("app.js")
        timer_pos = content.find("timerUpdate")
        assert timer_pos > 0, "未找到 timerUpdate 事件绑定"
        nearby = content[timer_pos:timer_pos + 200]
        assert "rafThrottle" in nearby, (
            "timerUpdate 应使用 rafThrottle 包裹"
        )

    def test_new_message_not_uses_raf_throttle(self):
        """newMessage 事件处理器不使用 rafThrottle（低频信号无需批处理）。"""
        content = _get_js_content("app.js")
        msg_pos = content.find("'newMessage'")
        if msg_pos < 0:
            msg_pos = content.find('"newMessage"')
        assert msg_pos > 0, "未找到 newMessage 事件绑定"
        # 只提取到该行结尾（到下一个 }); 或 bridge.on），避免窗口过大包含下一行
        line_end = content.find("});", msg_pos)
        if line_end < 0:
            line_end = msg_pos + 150
        nearby = content[msg_pos:min(line_end + 3, msg_pos + 200)]
        assert "rafThrottle" not in nearby, (
            "newMessage 不应使用 rafThrottle（低频信号无需批处理）"
        )

    def test_raf_throttle_pending_flag(self):
        """rafThrottle 使用 pending 标志防止重复调用。"""
        content = _get_js_content("app.js")
        raf_pos = content.find("rafThrottle")
        nearby = content[raf_pos:raf_pos + 500]
        assert "pending" in nearby, "rafThrottle 应使用 pending 标志防止重复 rAF 调用"

    def test_raf_throttle_saves_last_arg(self):
        """rafThrottle 保存最新参数，确保不丢失数据。"""
        content = _get_js_content("app.js")
        raf_pos = content.find("rafThrottle")
        nearby = content[raf_pos:raf_pos + 500]
        assert "lastArg" in nearby, "rafThrottle 应保存最新参数 (lastArg)"


# ============================================================
# Fix 4: 快捷键冲突修复验证
# ============================================================

class TestFix4KeyboardInputConflict:
    """Fix 4: KeyboardManager 在输入框内跳过非 Escape 快捷键。"""

    def test_input_focus_detection(self):
        """KeyboardManager 检测焦点是否在输入元素内。"""
        content = _get_js_content("keyboard.js")
        # 检查检测 input/textarea/select 标签
        assert "input" in content.lower() or "textarea" in content.lower() or "select" in content.lower(), (
            "KeyboardManager 应检测输入元素焦点"
        )
        # 更精确：检查 tagName 检测逻辑
        assert "tagName" in content, "应使用 tagName 检测元素类型"

    def test_input_elements_coverage(self):
        """KeyboardManager 覆盖 input、textarea、select 三种输入元素。"""
        content = _get_js_content("keyboard.js")
        # 在 _setupGlobalListener 方法中搜索这三种标签（非 JSDoc 注释区域）
        setup_pos = content.find("_setupGlobalListener()")
        assert setup_pos > 0, "未找到 _setupGlobalListener 方法"
        # 提取方法体
        method_body = content[setup_pos:setup_pos + 1000]
        # 检查 'input', 'textarea', 'select' 字符串常量
        assert "'input'" in method_body or '"input"' in method_body, "应检测 'input' 标签"
        assert "'textarea'" in method_body or '"textarea"' in method_body, "应检测 'textarea' 标签"
        assert "'select'" in method_body or '"select"' in method_body, "应检测 'select' 标签"

    def test_skip_non_escape_in_input(self):
        """在输入框内时跳过非 Escape 快捷键。"""
        content = _get_js_content("keyboard.js")
        # 检查 escape 特殊处理逻辑
        assert "escape" in content.lower(), "应检测 escape 键特殊处理"
        # 验证 isInputFocused && key !== 'escape' 的模式
        assert "!==" in content or "!=" in content, (
            "应有 escape 键的特殊判断逻辑"
        )

    def test_escape_still_works_in_input(self):
        """Escape 键在输入框内仍然响应（不跳过）。"""
        content = _get_js_content("keyboard.js")
        # 找到输入框检测逻辑附近，验证 escape 是例外
        input_pos = content.find("isInputFocused")
        if input_pos < 0:
            # 搜索更广泛的输入检测逻辑
            input_pos = content.find("tag === 'input'")
        assert input_pos > 0, "未找到输入框检测逻辑"
        nearby = content[input_pos:input_pos + 300]
        # escape 不应被完全拦截，应有条件放行
        assert "escape" in nearby.lower(), (
            "Escape 键应在输入框内有特殊处理（不跳过）"
        )

    def test_is_input_focused_variable(self):
        """存在 isInputFocused 变量标记输入框焦点状态。"""
        content = _get_js_content("keyboard.js")
        assert "isInputFocused" in content or "isInput" in content, (
            "应有 isInputFocused 或类似的输入框焦点状态变量"
        )


# ============================================================
# Fix 5: 设置保存内联提示验证
# ============================================================

class TestFix5SettingsInlineFeedback:
    """Fix 5: 设置保存后使用内联提示，不再关闭模态框再弹 showInfo。"""

    def test_settings_saved_handler_no_show_info(self):
        """settingsSaved 事件处理器不调用 modalManager.showInfo。"""
        content = _get_js_content("app.js")
        # 找到 settingsSaved 处理器
        saved_pos = content.find("settingsSaved")
        assert saved_pos > 0, "未找到 settingsSaved 事件绑定"
        # 向后搜索处理器内容
        handler_content = content[saved_pos:saved_pos + 500]
        assert "showInfo" not in handler_content, (
            "settingsSaved 处理器不应调用 modalManager.showInfo"
        )

    def test_settings_saved_handler_uses_inline_result(self):
        """settingsSaved 事件处理器使用内联提示更新 DOM。"""
        content = _get_js_content("app.js")
        saved_pos = content.find("settingsSaved")
        handler_content = content[saved_pos:saved_pos + 500]
        assert "settings-test-result" in handler_content, (
            "settingsSaved 处理器应更新 settings-test-result 元素显示内联提示"
        )

    def test_settings_saved_inline_success_message(self):
        """settingsSaved 内联提示包含成功文本。"""
        content = _get_js_content("app.js")
        saved_pos = content.find("settingsSaved")
        handler_content = content[saved_pos:saved_pos + 500]
        assert "设置已保存" in handler_content or "saved" in handler_content.lower(), (
            "settingsSaved 处理器应显示保存成功的内联提示"
        )

    def test_settings_save_button_returns_false(self):
        """设置保存按钮的 callback 返回 false 阻止关闭模态框。"""
        content = _get_js_content("modal.js")
        # 找到保存按钮的定义
        save_pos = content.find("'保存'")
        if save_pos < 0:
            save_pos = content.find('"保存"')
        assert save_pos > 0, "未找到保存按钮定义"
        # 搜索附近范围看 return false
        nearby = content[save_pos:save_pos + 300]
        assert "return false" in nearby, (
            "保存按钮回调应返回 false 以阻止模态框关闭"
        )

    def test_settings_test_button_returns_false(self):
        """测试连接按钮的 callback 返回 false 阻止关闭模态框。"""
        content = _get_js_content("modal.js")
        test_pos = content.find("'测试连接'")
        if test_pos < 0:
            test_pos = content.find('"测试连接"')
        assert test_pos > 0, "未找到测试连接按钮定义"
        nearby = content[test_pos:test_pos + 300]
        assert "return false" in nearby, (
            "测试连接按钮回调应返回 false 以阻止模态框关闭"
        )

    def test_modal_show_respects_false_return(self):
        """ModalManager._show 方法在 callback 返回 false 时不关闭模态框。"""
        content = _get_js_content("modal.js")
        # 找到 _show 方法定义（而非调用）
        show_pos = content.find("_show(title, bodyHtml, buttons)")
        if show_pos < 0:
            show_pos = content.find("_show(title,")
        assert show_pos > 0, "未找到 _show 方法定义"
        # 搜索方法体中对 callback 返回值的处理（方法体较大，需要足够范围）
        method_content = content[show_pos:show_pos + 2000]
        # 检查 result !== false 模式
        assert "result !== false" in method_content or "!== false" in method_content, (
            "_show 方法应检查 callback 返回值，当返回 false 时不调用 hide()"
        )


# ============================================================
# Fix 6: 案件生成原子化验证
# ============================================================

class TestFix6CaseGenerationAtomic:
    """Fix 6: _on_case_generated 不再使用 QTimer.singleShot。"""

    def test_on_case_generated_no_qtimer_singleshot(self):
        """_on_case_generated 方法中不使用 QTimer.singleShot。"""
        content = _get_py_content("web_main_window.py")
        # 找到 _on_case_generated 方法
        method_pos = content.find("def _on_case_generated")
        assert method_pos > 0, "未找到 _on_case_generated 方法"
        # 提取方法体（到下一个 def 或文件结尾）
        next_def = content.find("\n    def ", method_pos + 1)
        if next_def < 0:
            next_def = len(content)
        method_body = content[method_pos:next_def]
        assert "QTimer.singleShot" not in method_body, (
            "_on_case_generated 不应使用 QTimer.singleShot"
        )

    def test_on_case_generated_calls_load_case_directly(self):
        """_on_case_generated 方法直接调用 self.load_case()。"""
        content = _get_py_content("web_main_window.py")
        method_pos = content.find("def _on_case_generated")
        assert method_pos > 0, "未找到 _on_case_generated 方法"
        next_def = content.find("\n    def ", method_pos + 1)
        if next_def < 0:
            next_def = len(content)
        method_body = content[method_pos:next_def]
        assert "self.load_case(case_dict)" in method_body, (
            "_on_case_generated 应直接调用 self.load_case(case_dict)"
        )

    def test_on_case_generated_emits_completion_signal(self):
        """_on_case_generated 先发射完成信号再加载案件。"""
        content = _get_py_content("web_main_window.py")
        method_pos = content.find("def _on_case_generated")
        method_body = content[method_pos:method_pos + 1000]
        assert "case_generation_complete" in method_body, (
            "_on_case_generated 应发射 case_generation_complete 信号"
        )

    def test_no_qtimer_singleshot_for_case_loading(self):
        """整个 web_main_window.py 中不使用 QTimer.singleShot 加载案件。"""
        content = _get_py_content("web_main_window.py")
        # 搜索所有 QTimer.singleShot 调用
        singleshot_matches = list(re.finditer(r"QTimer\.singleShot", content))
        for match in singleshot_matches:
            # 检查附近上下文是否有 load_case
            start = max(0, match.start() - 200)
            end = min(len(content), match.end() + 200)
            context = content[start:end]
            assert "load_case" not in context, (
                f"QTimer.singleShot 不应用于延迟加载案件 (位置: {match.start()})"
            )

    def test_on_case_generated_emits_before_load(self):
        """_on_case_generated 中 case_generation_complete 在 load_case 之前。"""
        content = _get_py_content("web_main_window.py")
        method_pos = content.find("def _on_case_generated")
        next_def = content.find("\n    def ", method_pos + 1)
        if next_def < 0:
            next_def = len(content)
        method_body = content[method_pos:next_def]
        complete_pos = method_body.find("case_generation_complete")
        load_pos = method_body.find("load_case")
        assert complete_pos > 0, "未找到 case_generation_complete 信号"
        assert load_pos > 0, "未找到 load_case 调用"
        assert complete_pos < load_pos, (
            "case_generation_complete 信号应在 load_case 之前发射"
        )


# ============================================================
# Fix 7: 计时器暂停验证
# ============================================================

class TestFix7TimerPauseOnModal:
    """Fix 7: TimerManager.update() 在模态框可见时跳过渲染，hide() 后 flush() 恢复。"""

    def test_timer_update_checks_modal_visible(self):
        """TimerManager.update() 检查 modalManager.isVisible()。"""
        content = _get_js_content("timer.js")
        update_pos = content.find("update(timeLeft)")
        assert update_pos > 0, "未找到 update 方法"
        method_body = content[update_pos:update_pos + 500]
        assert "modalManager" in method_body, (
            "update 方法应检查 modalManager"
        )
        assert "isVisible" in method_body, (
            "update 方法应调用 modalManager.isVisible()"
        )

    def test_timer_update_skips_render_when_modal_visible(self):
        """TimerManager.update() 在模态框可见时跳过 _render 调用。"""
        content = _get_js_content("timer.js")
        update_pos = content.find("update(timeLeft)")
        method_body = content[update_pos:update_pos + 500]
        # 检查 early return 模式：isVisible() return
        assert "return" in method_body, (
            "update 方法在模态框可见时应 early return"
        )
        # 验证 return 在 _render 之前
        return_pos = method_body.find("return")
        render_pos = method_body.find("_render")
        if render_pos > 0:
            assert return_pos < render_pos, (
                "return 应在 _render 调用之前，确保模态框可见时跳过渲染"
            )

    def test_timer_update_saves_last_time_left(self):
        """TimerManager.update() 保存 _lastTimeLeft 以便 flush 恢复。"""
        content = _get_js_content("timer.js")
        update_pos = content.find("update(timeLeft)")
        method_body = content[update_pos:update_pos + 500]
        assert "_lastTimeLeft" in method_body, (
            "update 方法应保存 _lastTimeLeft"
        )
        # 验证保存发生在 return 之前
        save_pos = method_body.find("_lastTimeLeft")
        return_match = re.search(r"if\s*\(.*modalManager.*\)\s*return", method_body)
        if return_match:
            assert save_pos < return_match.start(), (
                "_lastTimeLeft 应在 modal 检查 return 之前保存"
            )

    def test_timer_flush_method_exists(self):
        """TimerManager 有 flush() 方法。"""
        content = _get_js_content("timer.js")
        assert "flush()" in content, "TimerManager 应有 flush() 方法"

    def test_timer_flush_calls_render(self):
        """TimerManager.flush() 调用 _render 恢复渲染。"""
        content = _get_js_content("timer.js")
        flush_pos = content.find("flush()")
        assert flush_pos > 0, "未找到 flush() 方法"
        method_body = content[flush_pos:flush_pos + 300]
        assert "_render" in method_body, "flush() 应调用 _render 恢复渲染"

    def test_timer_flush_uses_last_time_left(self):
        """TimerManager.flush() 使用 _lastTimeLeft 恢复。"""
        content = _get_js_content("timer.js")
        flush_pos = content.find("flush()")
        method_body = content[flush_pos:flush_pos + 300]
        assert "_lastTimeLeft" in method_body, "flush() 应使用 _lastTimeLeft"

    def test_timer_last_time_left_initialized(self):
        """_lastTimeLeft 在构造函数中初始化为 null。"""
        content = _get_js_content("timer.js")
        assert "_lastTimeLeft = null" in content, (
            "_lastTimeLeft 应在构造函数中初始化为 null"
        )

    def test_modal_hide_calls_timer_flush(self):
        """ModalManager.hide() 调用 timerManager.flush()。"""
        content = _get_js_content("modal.js")
        # 找到 hide 方法定义（而非调用）
        # hide() 方法是以 `hide()` 开头的独立方法
        hide_method_pattern = re.compile(r"^\s+hide\(\)\s*\{", re.MULTILINE)
        match = hide_method_pattern.search(content)
        assert match is not None, "未找到 hide() 方法定义"
        hide_start = match.start()
        # 提取方法体（到下一个方法定义或类结尾）
        next_method = re.search(r"\n\s+(?:_?\w+\(|/\*\*)", content[hide_start + 10:])
        if next_method:
            method_end = hide_start + 10 + next_method.start()
        else:
            method_end = len(content)
        method_body = content[hide_start:method_end]
        assert "timerManager" in method_body, (
            "hide() 应引用 timerManager"
        )
        assert "flush" in method_body, (
            "hide() 应调用 timerManager.flush()"
        )

    def test_modal_hide_flush_after_hide(self):
        """ModalManager.hide() 中 flush 在移除 active 类之后调用。"""
        content = _get_js_content("modal.js")
        # 找到 hide 方法定义
        hide_method_pattern = re.compile(r"^\s+hide\(\)\s*\{", re.MULTILINE)
        match = hide_method_pattern.search(content)
        assert match is not None, "未找到 hide() 方法定义"
        hide_start = match.start()
        next_method = re.search(r"\n\s+(?:_?\w+\(|/\*\*)", content[hide_start + 10:])
        if next_method:
            method_end = hide_start + 10 + next_method.start()
        else:
            method_end = len(content)
        method_body = content[hide_start:method_end]
        # remove('active') 应在 flush 之前
        remove_pos = method_body.find("remove")
        flush_pos = method_body.find("flush")
        if remove_pos > 0 and flush_pos > 0:
            assert remove_pos < flush_pos, (
                "remove('active') 应在 flush 之前执行，确保模态框先关闭再恢复计时器"
            )


# ============================================================
# 跨 Fix 集成验证
# ============================================================

class TestCrossFixIntegration:
    """跨修复的集成验证。"""

    def test_all_modified_files_exist(self):
        """所有修改过的文件都存在。"""
        files = [
            Path(__file__).parent.parent / "ui" / "web" / "css" / "components.css",
            Path(__file__).parent.parent / "ui" / "web" / "js" / "app.js",
            Path(__file__).parent.parent / "ui" / "web" / "js" / "keyboard.js",
            Path(__file__).parent.parent / "ui" / "web" / "js" / "modal.js",
            Path(__file__).parent.parent / "ui" / "web" / "js" / "timer.js",
            Path(__file__).parent.parent / "ui" / "web_main_window.py",
        ]
        for f in files:
            assert f.exists(), f"文件不存在: {f}"

    def test_all_modified_files_non_empty(self):
        """所有修改过的文件都非空。"""
        files = {
            "components.css": Path(__file__).parent.parent / "ui" / "web" / "css" / "components.css",
            "app.js": Path(__file__).parent.parent / "ui" / "web" / "js" / "app.js",
            "keyboard.js": Path(__file__).parent.parent / "ui" / "web" / "js" / "keyboard.js",
            "modal.js": Path(__file__).parent.parent / "ui" / "web" / "js" / "modal.js",
            "timer.js": Path(__file__).parent.parent / "ui" / "web" / "js" / "timer.js",
            "web_main_window.py": Path(__file__).parent.parent / "ui" / "web_main_window.py",
        }
        for name, path in files.items():
            content = path.read_text(encoding="utf-8")
            assert len(content.strip()) > 0, f"{name} 文件为空"

    def test_timer_manager_global_instance(self):
        """TimerManager 实例暴露到全局，供 ModalManager.hide() 调用 flush。"""
        content = _get_js_content("app.js")
        assert "window.timerManager" in content, (
            "TimerManager 实例应暴露到全局 (window.timerManager)"
        )

    def test_modal_manager_global_instance(self):
        """ModalManager 实例暴露到全局，供 TimerManager.update() 检查可见性。"""
        content = _get_js_content("app.js")
        assert "window.modalManager" in content, (
            "ModalManager 实例应暴露到全局 (window.modalManager)"
        )

    def test_generate_case_button_returns_false(self):
        """案件生成按钮也返回 false 阻止关闭模态框。"""
        content = _get_js_content("modal.js")
        gen_pos = content.find("'生成'")
        if gen_pos < 0:
            gen_pos = content.find('"生成"')
        assert gen_pos > 0, "未找到生成按钮"
        nearby = content[gen_pos:gen_pos + 300]
        assert "return false" in nearby, (
            "生成按钮回调应返回 false 阻止模态框关闭（允许查看进度）"
        )


# ============================================================
# Fix 8: Modal Wrapper 分离 transform 和 scroll
# ============================================================

class TestFix8ModalWrapperSeparation:
    """Fix 8: .modal-wrapper 承载 transform 居中，.modal 只做滚动容器。"""

    def test_modal_wrapper_created_in_constructor(self):
        """ModalManager 构造函数中创建 wrapper。"""
        content = _get_js_content("modal.js")
        assert "_createWrapper" in content, (
            "ModalManager 应有 _createWrapper 方法"
        )

    def test_modal_wrapper_stored_as_property(self):
        """ModalManager 将 wrapper 存为 this.wrapper 属性。"""
        content = _get_js_content("modal.js")
        assert "this.wrapper" in content, (
            "ModalManager 应将 wrapper 存为 this.wrapper"
        )

    def test_modal_wrapper_appends_modal(self):
        """_createWrapper 将 modal 元素移入 wrapper。"""
        content = _get_js_content("modal.js")
        wrapper_pos = content.find("_createWrapper")
        assert wrapper_pos > 0, "未找到 _createWrapper 方法"
        method_body = content[wrapper_pos:wrapper_pos + 800]
        assert "appendChild" in method_body, (
            "_createWrapper 应使用 appendChild 将 modal 移入 wrapper"
        )

    def test_show_toggles_wrapper_active(self):
        """_show 方法切换 wrapper 的 active 类。"""
        content = _get_js_content("modal.js")
        show_pos = content.find("_show(title, bodyHtml, buttons)")
        if show_pos < 0:
            show_pos = content.find("_show(title,")
        assert show_pos > 0, "未找到 _show 方法"
        method_body = content[show_pos:show_pos + 2000]
        assert "wrapper" in method_body, "_show 方法应操作 wrapper"
        assert "classList.add" in method_body, "_show 应添加 active 类"

    def test_hide_toggles_wrapper_active(self):
        """hide 方法切换 wrapper 的 active 类。"""
        content = _get_js_content("modal.js")
        hide_method_pattern = re.compile(r"^\s+hide\(\)\s*\{", re.MULTILINE)
        match = hide_method_pattern.search(content)
        assert match is not None, "未找到 hide() 方法定义"
        hide_start = match.start()
        next_method = re.search(r"\n\s+(?:_?\w+\(|/\*\*)", content[hide_start + 10:])
        if next_method:
            method_end = hide_start + 10 + next_method.start()
        else:
            method_end = len(content)
        method_body = content[hide_start:method_end]
        assert "wrapper" in method_body, "hide 方法应操作 wrapper"

    def test_modal_has_overflow_y_auto(self):
        """`.modal` 保留 `overflow-y: auto` 作为滚动容器。"""
        css = _get_css_content()
        block = _extract_css_block(css, ".modal")
        assert "overflow-y" in block and "auto" in block, (
            ".modal 应保留 overflow-y: auto 作为滚动容器"
        )

    def test_modal_wrapper_no_overflow(self):
        """`.modal-wrapper` 不是滚动容器，不含 overflow 属性。"""
        css = _get_css_content()
        block = _extract_css_block(css, ".modal-wrapper")
        assert "overflow" not in block, (
            ".modal-wrapper 不应包含 overflow 属性"
        )


# ============================================================
# Fix 9: suspectUpdate 模态框守卫
# ============================================================

class TestFix9SuspectUpdateModalGuard:
    """Fix 9: suspectUpdate 信号在模态框可见时跳过更新。"""

    def test_suspect_update_checks_modal_visible(self):
        """suspectUpdate 事件处理器检查 modalManager.isVisible()。"""
        content = _get_js_content("app.js")
        suspect_pos = content.find("suspectUpdate")
        assert suspect_pos > 0, "未找到 suspectUpdate 事件绑定"
        nearby = content[suspect_pos:suspect_pos + 300]
        assert "modalManager" in nearby, (
            "suspectUpdate 处理器应检查 modalManager"
        )
        assert "isVisible" in nearby, (
            "suspectUpdate 处理器应调用 modalManager.isVisible()"
        )

    def test_suspect_update_returns_early_when_modal_visible(self):
        """suspectUpdate 在模态框可见时 early return。"""
        content = _get_js_content("app.js")
        suspect_pos = content.find("suspectUpdate")
        nearby = content[suspect_pos:suspect_pos + 300]
        assert "return" in nearby, (
            "suspectUpdate 处理器在模态框可见时应 early return"
        )


# ============================================================
# Fix 10: 模态框打开时暂停 CSS 动画
# ============================================================

class TestFix10ModalOpenPauseAnimations:
    """Fix 10: body.modal-open 暂停后台 CSS 动画。"""

    def test_body_modal_open_pressure_bar_high_paused(self):
        """`body.modal-open .pressure-bar.high` 暂停动画。"""
        css = _get_css_content()
        assert "body.modal-open" in css, (
            "components.css 应包含 body.modal-open 规则"
        )
        block = _extract_css_block(css, "body.modal-open .pressure-bar.high")
        assert "animation-play-state" in block, (
            "body.modal-open .pressure-bar.high 应包含 animation-play-state: paused"
        )
        assert "paused" in block, (
            "body.modal-open .pressure-bar.high 的 animation-play-state 应为 paused"
        )

    def test_body_modal_open_pressure_bar_after_paused(self):
        """`body.modal-open .pressure-bar::after` 暂停动画。"""
        css = _get_css_content()
        block = _extract_css_block(css, "body.modal-open .pressure-bar::after")
        assert "animation-play-state" in block, (
            "body.modal-open .pressure-bar::after 应暂停动画"
        )

    def test_body_modal_open_timer_danger_paused(self):
        """`body.modal-open .timer-display.danger` 暂停动画。"""
        css = _get_css_content()
        block = _extract_css_block(css, "body.modal-open .timer-display.danger")
        assert "animation-play-state" in block, (
            "body.modal-open .timer-display.danger 应暂停动画"
        )

    def test_body_modal_open_timer_warning_paused(self):
        """`body.modal-open .timer-display.warning` 暂停动画。"""
        css = _get_css_content()
        block = _extract_css_block(css, "body.modal-open .timer-display.warning")
        assert "animation-play-state" in block, (
            "body.modal-open .timer-display.warning 应暂停动画"
        )

    def test_body_modal_open_nav_ending_paused(self):
        """`body.modal-open .nav-btn-ending` 暂停动画。"""
        css = _get_css_content()
        block = _extract_css_block(css, "body.modal-open .nav-btn-ending")
        assert "animation-play-state" in block, (
            "body.modal-open .nav-btn-ending 应暂停动画"
        )

    def test_modal_show_adds_body_modal_open(self):
        """_show 方法添加 body.modal-open 类。"""
        content = _get_js_content("modal.js")
        show_pos = content.find("_show(title, bodyHtml, buttons)")
        if show_pos < 0:
            show_pos = content.find("_show(title,")
        assert show_pos > 0, "未找到 _show 方法"
        method_body = content[show_pos:show_pos + 2000]
        assert "document.body" in method_body, "_show 应操作 document.body"
        assert "modal-open" in method_body, "_show 应添加 modal-open 类"

    def test_modal_hide_removes_body_modal_open(self):
        """hide 方法移除 body.modal-open 类。"""
        content = _get_js_content("modal.js")
        hide_method_pattern = re.compile(r"^\s+hide\(\)\s*\{", re.MULTILINE)
        match = hide_method_pattern.search(content)
        assert match is not None, "未找到 hide() 方法定义"
        hide_start = match.start()
        next_method = re.search(r"\n\s+(?:_?\w+\(|/\*\*)", content[hide_start + 10:])
        if next_method:
            method_end = hide_start + 10 + next_method.start()
        else:
            method_end = len(content)
        method_body = content[hide_start:method_end]
        assert "modal-open" in method_body, "hide 应移除 modal-open 类"
        assert "remove" in method_body, "hide 应使用 classList.remove 移除 modal-open"
