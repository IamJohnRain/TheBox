"""WebView 初始化与 WebMainWindow 测试。"""

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView

from ui.web_bridge import WebBridge
from ui.web_main_window import WebMainWindow


class TestWebEngineAvailability:
    """QWebEngineView 可用性测试。"""

    def test_webengine_importable(self):
        """QWebEngineView 可正常导入。"""
        assert QWebEngineView is not None

    def test_webchannel_importable(self):
        """QWebChannel 可正常导入。"""
        assert QWebChannel is not None


class TestWebMainWindowCreation:
    """WebMainWindow 实例创建测试。"""

    def test_window_creation(self, qtbot):
        """WebMainWindow 能创建实例。"""
        window = WebMainWindow()
        assert window is not None
        assert isinstance(window, WebMainWindow)

    def test_web_view_exists(self, qtbot):
        """web_view 属性存在且为 QWebEngineView 类型。"""
        window = WebMainWindow()
        assert hasattr(window, "web_view")
        assert isinstance(window.web_view, QWebEngineView)

    def test_bridge_exists(self, qtbot):
        """bridge 属性存在且为 WebBridge 类型。"""
        window = WebMainWindow()
        assert hasattr(window, "bridge")
        assert isinstance(window.bridge, WebBridge)

    def test_channel_exists(self, qtbot):
        """channel 属性存在且为 QWebChannel 类型。"""
        window = WebMainWindow()
        assert hasattr(window, "channel")
        assert isinstance(window.channel, QWebChannel)

    def test_window_title(self, qtbot):
        """窗口标题正确。"""
        window = WebMainWindow()
        assert window.windowTitle() == "The Box: Local Verdict"

    def test_window_size(self, qtbot):
        """窗口默认尺寸为 1280x800。"""
        window = WebMainWindow()
        assert window.width() == 1280
        assert window.height() == 800

    def test_central_widget_is_webview(self, qtbot):
        """中心部件是 QWebEngineView。"""
        window = WebMainWindow()
        assert window.centralWidget() is window.web_view


class TestWebChannelRegistration:
    """QWebChannel 对象注册测试。"""

    def test_bridge_registered(self, qtbot):
        """WebBridge 以 'bridge' 名称注册到 QWebChannel。"""
        window = WebMainWindow()
        registered = window.channel.registeredObjects()
        assert "bridge" in registered
        assert registered["bridge"] is window.bridge

    def test_channel_bound_to_page(self, qtbot):
        """QWebChannel 绑定到 QWebEnginePage。"""
        window = WebMainWindow()
        page = window.web_view.page()
        assert page.webChannel() is window.channel


class TestHtmlFile:
    """HTML 文件验证测试。"""

    def test_index_html_exists(self):
        """index.html 文件存在。"""
        from pathlib import Path

        from ui.resource_helper import get_html_url

        url = get_html_url()
        local_path = Path(url.toLocalFile())
        assert local_path.exists()

    def test_index_html_contains_doctype(self):
        """index.html 包含 DOCTYPE 声明。"""
        from pathlib import Path

        from ui.resource_helper import get_html_url

        url = get_html_url()
        local_path = Path(url.toLocalFile())
        content = local_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content

    def test_index_html_contains_charset(self):
        """index.html 包含 UTF-8 charset。"""
        from pathlib import Path

        from ui.resource_helper import get_html_url

        url = get_html_url()
        local_path = Path(url.toLocalFile())
        content = local_path.read_text(encoding="utf-8")
        assert 'charset="UTF-8"' in content or "charset=UTF-8" in content

    def test_index_html_contains_qwebchannel(self):
        """index.html 包含 qwebchannel.js 引用。"""
        from pathlib import Path

        from ui.resource_helper import get_html_url

        url = get_html_url()
        local_path = Path(url.toLocalFile())
        content = local_path.read_text(encoding="utf-8")
        assert "qwebchannel.js" in content

    def test_index_html_contains_bridge_init(self):
        """index.html 包含 QWebChannel 初始化代码。"""
        from pathlib import Path

        from ui.resource_helper import get_html_url

        url = get_html_url()
        local_path = Path(url.toLocalFile())
        content = local_path.read_text(encoding="utf-8")
        assert "QWebChannel" in content
