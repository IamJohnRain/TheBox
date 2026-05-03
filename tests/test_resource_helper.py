"""资源路径辅助工具测试。"""

import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QUrl


class TestGetResourceUrl:
    """get_resource_url() 测试。"""

    def test_returns_local_file_url_in_dev_env(self):
        """开发环境返回本地文件 URL。"""
        from ui.resource_helper import get_resource_url

        url = get_resource_url("index.html")
        assert url.scheme() == "file"
        assert url.toLocalFile().endswith("ui/web/index.html")

    def test_returns_qrc_url_in_frozen_env(self, monkeypatch):
        """打包环境返回 qrc URL。"""
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        try:
            from ui.resource_helper import get_resource_url

            url = get_resource_url("index.html")
            assert url.scheme() == "qrc"
            assert url.path() == "/ui/web/index.html"
        finally:
            monkeypatch.delattr(sys, "frozen", raising=False)

    def test_subdirectory_resource(self):
        """子目录资源路径正确解析。"""
        from ui.resource_helper import get_resource_url

        url = get_resource_url("css/style.css")
        assert "ui/web/css/style.css" in url.toLocalFile()

    def test_js_subdirectory_resource(self):
        """JS 子目录资源路径正确解析。"""
        from ui.resource_helper import get_resource_url

        url = get_resource_url("js/app.js")
        assert "ui/web/js/app.js" in url.toLocalFile()


class TestGetHtmlUrl:
    """get_html_url() 测试。"""

    def test_returns_qurl(self):
        """返回 QUrl 对象。"""
        from ui.resource_helper import get_html_url

        url = get_html_url()
        assert isinstance(url, QUrl)

    def test_points_to_index_html(self):
        """URL 指向 index.html。"""
        from ui.resource_helper import get_html_url

        url = get_html_url()
        assert url.toLocalFile().endswith("ui/web/index.html")

    def test_file_exists_in_dev_env(self):
        """开发环境对应的文件实际存在。"""
        from ui.resource_helper import get_html_url

        url = get_html_url()
        local_path = Path(url.toLocalFile())
        assert local_path.exists(), f"File not found: {local_path}"

    def test_returns_qrc_url_in_frozen_env(self, monkeypatch):
        """打包环境返回 qrc URL。"""
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        try:
            from ui.resource_helper import get_html_url

            url = get_html_url()
            assert url.scheme() == "qrc"
            assert url.path() == "/ui/web/index.html"
        finally:
            monkeypatch.delattr(sys, "frozen", raising=False)
