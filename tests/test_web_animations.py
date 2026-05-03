"""动画效果测试。"""

from pathlib import Path


def _get_animations_content():
    """获取 animations.css 内容。"""
    css_path = Path(__file__).parent.parent / "ui" / "web" / "css" / "animations.css"
    return css_path.read_text(encoding="utf-8")


def _get_components_content():
    """获取 components.css 内容。"""
    css_path = Path(__file__).parent.parent / "ui" / "web" / "css" / "components.css"
    return css_path.read_text(encoding="utf-8")


class TestAnimationKeyframes:
    """动画 keyframes 定义测试。"""

    def test_fade_in_animation(self):
        """存在淡入动画。"""
        content = _get_animations_content()
        assert "fadeIn" in content or "fade-in" in content

    def test_spin_animation(self):
        """存在旋转动画（加载指示器）。"""
        content = _get_animations_content()
        assert "spin" in content.lower() or "rotate" in content.lower()

    def test_pulse_animation(self):
        """存在脉冲动画。"""
        content = _get_animations_content()
        assert "pulse" in content.lower()

    def test_blink_animation(self):
        """存在闪烁动画（倒计时）。"""
        content = _get_animations_content()
        assert "blink" in content.lower() or "flash" in content.lower()

    def test_keyframes_have_start_end(self):
        """keyframes 包含 0% 和 100% 关键帧。"""
        content = _get_animations_content()
        # 至少有一个完整的 keyframes 定义
        assert "@keyframes" in content
        assert "0%" in content
        assert "100%" in content


class TestComponentAnimations:
    """组件动画效果测试。"""

    def test_message_animation(self):
        """消息有动画效果。"""
        content = _get_components_content()
        assert "animation" in content

    def test_pressure_bar_transition(self):
        """压力条有过渡动画。"""
        content = _get_components_content()
        assert "transition" in content

    def test_button_hover_effect(self):
        """按钮有悬停效果。"""
        content = _get_components_content()
        assert ":hover" in content

    def test_loading_spinner(self):
        """加载指示器有旋转动画。"""
        content = _get_components_content()
        # 检查 spinner 相关样式
        assert "spinner" in content.lower() or "loading" in content.lower()
