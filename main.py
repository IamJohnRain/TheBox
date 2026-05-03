import sys

from PySide6.QtWidgets import QApplication

from core.db import init_db
from ui.web_main_window import WebMainWindow


def main():
    init_db()
    app = QApplication(sys.argv)
    window = WebMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
