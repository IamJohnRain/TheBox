"""资源路径辅助工具，兼容开发环境和打包环境。"""

import sys
from pathlib import Path

from PySide6.QtCore import QUrl


def get_resource_url(relative_path: str) -> QUrl:
    """获取资源 URL，兼容开发环境和打包环境。

    Args:
        relative_path: 相对于 ui/web/ 目录的路径，如 "index.html", "css/style.css"

    Returns:
        QUrl 对象，可直接用于 QWebEngineView.setUrl()
    """
    if getattr(sys, "frozen", False):
        # 打包环境：使用 Qt 资源系统
        return QUrl(f"qrc:///ui/web/{relative_path}")
    else:
        # 开发环境：使用本地文件
        base_path = Path(__file__).parent
        full_path = base_path / "web" / relative_path
        return QUrl.fromLocalFile(str(full_path))


def get_html_url() -> QUrl:
    """获取主页面 URL。"""
    return get_resource_url("index.html")
