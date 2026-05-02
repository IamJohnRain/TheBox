import logging

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger("thebox")


class ChatWidget(QWidget):
    """Chat interface with a read-only history display and a message input row."""

    message_sent = Signal(str)

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the chat display and the input row with a send button."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display)

        input_row = QWidget()
        input_layout = QHBoxLayout(input_row)
        input_layout.setContentsMargins(0, 0, 0, 0)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("输入你的问题...")
        self.input_field.returnPressed.connect(self._on_send)
        input_layout.addWidget(self.input_field)

        self.send_button = QPushButton("发送")
        self.send_button.clicked.connect(self._on_send)
        input_layout.addWidget(self.send_button)

        layout.addWidget(input_row)

    def _on_send(self) -> None:
        """Emit the message_sent signal when the user sends a message."""
        text = self.input_field.text().strip()
        if not text:
            return
        self.input_field.clear()
        self.message_sent.emit(text)

    def add_message(self, role: str, content: str, suspect_name: str = "") -> None:
        """Append a formatted HTML message to the chat history.

        Args:
            role: The role of the speaker - "player", "suspect", or "system".
            content: The message content.
            suspect_name: The name of the suspect (used when role is "suspect").
        """
        if role == "player":
            html = f'<span style="color:#1565C0;"><b>你:</b> {content}</span>'
        elif role == "suspect":
            html = f'<span style="color:#000000;"><b>{suspect_name}:</b> {content}</span>'
        elif role == "system":
            html = f'<span style="color:#757575;"><i>{content}</i></span>'
        else:
            html = f'<b>[{role}]</b> {content}'
        self.chat_display.append(html)

    def clear_chat(self) -> None:
        """Clear all messages from the chat display."""
        self.chat_display.clear()

    def set_input_enabled(self, enabled: bool) -> None:
        """Enable or disable the input field and send button."""
        self.input_field.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
