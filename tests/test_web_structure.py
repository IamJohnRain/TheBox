"""前端 UI 结构与样式测试。"""

import pytest
from pathlib import Path

from ui.resource_helper import get_html_url


def _get_html_content():
    """获取 index.html 内容。"""
    url = get_html_url()
    local_path = Path(url.toLocalFile())
    return local_path.read_text(encoding="utf-8")


def _get_css_content(filename):
    """获取 CSS 文件内容。"""
    css_path = Path(__file__).parent.parent / "ui" / "web" / "css" / filename
    return css_path.read_text(encoding="utf-8")


class TestFileStructure:
    """前端资源文件结构测试。"""

    def test_index_html_exists(self):
        """index.html 存在。"""
        url = get_html_url()
        local_path = Path(url.toLocalFile())
        assert local_path.exists()

    def test_style_css_exists(self):
        """style.css 存在。"""
        css_path = Path(__file__).parent.parent / "ui" / "web" / "css" / "style.css"
        assert css_path.exists()

    def test_animations_css_exists(self):
        """animations.css 存在。"""
        css_path = Path(__file__).parent.parent / "ui" / "web" / "css" / "animations.css"
        assert css_path.exists()

    def test_components_css_exists(self):
        """components.css 存在。"""
        css_path = Path(__file__).parent.parent / "ui" / "web" / "css" / "components.css"
        assert css_path.exists()

    def test_icons_directory_not_empty(self):
        """图标目录非空。"""
        icons_path = Path(__file__).parent.parent / "ui" / "web" / "assets" / "icons"
        svg_files = list(icons_path.glob("*.svg"))
        assert len(svg_files) >= 7


class TestHtmlStructure:
    """HTML 结构完整性测试。"""

    def test_doctype(self):
        """包含 DOCTYPE 声明。"""
        content = _get_html_content()
        assert "<!DOCTYPE html>" in content

    def test_lang_attribute(self):
        """设置中文语言。"""
        content = _get_html_content()
        assert 'lang="zh-CN"' in content

    def test_charset(self):
        """包含 UTF-8 charset。"""
        content = _get_html_content()
        assert "UTF-8" in content

    def test_viewport(self):
        """包含 viewport 设置。"""
        content = _get_html_content()
        assert "viewport" in content

    def test_title(self):
        """标题包含 The Box。"""
        content = _get_html_content()
        assert "The Box" in content

    def test_app_container(self):
        """存在 #app 根容器。"""
        content = _get_html_content()
        assert 'id="app"' in content

    def test_navbar(self):
        """存在导航栏元素。"""
        content = _get_html_content()
        assert "navbar" in content

    def test_sidebar_left(self):
        """存在左侧面板。"""
        content = _get_html_content()
        assert "sidebar-left" in content or "panel-left" in content

    def test_chat_area(self):
        """存在中央聊天区。"""
        content = _get_html_content()
        assert "chat-area" in content or "panel-center" in content

    def test_sidebar_right(self):
        """存在右侧证据面板。"""
        content = _get_html_content()
        assert "sidebar-right" in content or "panel-right" in content

    def test_loading_overlay(self):
        """存在加载指示器。"""
        content = _get_html_content()
        assert 'id="loading-overlay"' in content

    def test_modal_container(self):
        """存在模态框容器。"""
        content = _get_html_content()
        assert "modal" in content.lower()

    def test_chat_input(self):
        """存在消息输入框。"""
        content = _get_html_content()
        assert "message-input" in content or "chat-input" in content

    def test_send_button(self):
        """存在发送按钮。"""
        content = _get_html_content()
        assert "btn-send" in content or "send" in content.lower()

    def test_timer_element(self):
        """存在倒计时元素。"""
        content = _get_html_content()
        assert "timer" in content

    def test_pressure_button(self):
        """存在施压按钮。"""
        content = _get_html_content()
        assert "pressure" in content.lower()

    def test_empathy_button(self):
        """存在共情按钮。"""
        content = _get_html_content()
        assert "empathy" in content.lower()

    def test_evidence_list(self):
        """存在证据列表容器。"""
        content = _get_html_content()
        assert "evidence" in content.lower()

    def test_css_links(self):
        """正确引入 CSS 文件。"""
        content = _get_html_content()
        assert "css/style.css" in content
        assert "css/animations.css" in content
        assert "css/components.css" in content

    def test_qwebchannel_script(self):
        """包含 qwebchannel.js 引用。"""
        content = _get_html_content()
        assert "qwebchannel.js" in content


class TestCssVariables:
    """CSS 变量定义测试。"""

    def test_root_selector(self):
        """存在 :root 选择器。"""
        content = _get_css_content("style.css")
        assert ":root" in content

    def test_color_bg_primary(self):
        """定义主背景色变量。"""
        content = _get_css_content("style.css")
        assert "--color-bg-primary" in content

    def test_color_bg_secondary(self):
        """定义次背景色变量。"""
        content = _get_css_content("style.css")
        assert "--color-bg-secondary" in content

    def test_color_text_primary(self):
        """定义主文字色变量。"""
        content = _get_css_content("style.css")
        assert "--color-text-primary" in content

    def test_color_accent_cyan(self):
        """定义霓虹青强调色变量。"""
        content = _get_css_content("style.css")
        assert "--color-accent-cyan" in content

    def test_color_accent_purple(self):
        """定义紫色强调色变量。"""
        content = _get_css_content("style.css")
        assert "--color-accent-purple" in content

    def test_color_danger(self):
        """定义危险色变量。"""
        content = _get_css_content("style.css")
        assert "--color-danger" in content

    def test_color_success(self):
        """定义成功色变量。"""
        content = _get_css_content("style.css")
        assert "--color-success" in content

    def test_font_family(self):
        """定义字体族变量。"""
        content = _get_css_content("style.css")
        assert "--font-family" in content

    def test_layout_sidebar_width(self):
        """定义左侧面板宽度变量。"""
        content = _get_css_content("style.css")
        assert "--layout-sidebar-width" in content

    def test_layout_evidence_width(self):
        """定义右侧面板宽度变量。"""
        content = _get_css_content("style.css")
        assert "--layout-evidence-width" in content

    def test_layout_nav_height(self):
        """定义导航栏高度变量。"""
        content = _get_css_content("style.css")
        assert "--layout-nav-height" in content


class TestResponsiveLayout:
    """响应式布局测试。"""

    def test_media_queries_exist(self):
        """CSS 包含 @media 查询。"""
        content = _get_css_content("style.css")
        assert "@media" in content

    def test_tablet_breakpoint(self):
        """存在平板断点。"""
        content = _get_css_content("style.css")
        assert "1024" in content or "768" in content
