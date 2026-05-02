import logging

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.case_generator import generate_case
from core.exceptions import TheBoxError

logger = logging.getLogger("thebox")


class AdminDialog(QDialog):
    """Dialog for generating a new case from a background story via LLM."""

    case_generated = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the dialog layout with story input, model field, and buttons."""
        self.setWindowTitle("生成新案件")
        self.setMinimumWidth(480)
        self.setMinimumHeight(360)

        layout = QVBoxLayout(self)

        story_label = QLabel("背景故事:")
        layout.addWidget(story_label)

        self.story_input = QTextEdit()
        self.story_input.setPlaceholderText("请输入案件的背景故事...")
        layout.addWidget(self.story_input)

        model_row = QWidget()
        model_layout = QHBoxLayout(model_row)
        model_layout.setContentsMargins(0, 0, 0, 0)

        model_label = QLabel("模型名称:")
        model_layout.addWidget(model_label)

        self.model_input = QLineEdit()
        from core.config import get_model

        default_model = get_model()
        self.model_input.setPlaceholderText(f"默认: {default_model}")
        model_layout.addWidget(self.model_input)

        layout.addWidget(model_row)

        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)

        self.generate_button = QPushButton("生成")
        self.generate_button.clicked.connect(self._on_generate)
        button_layout.addWidget(self.generate_button)

        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addWidget(button_row)

    def _on_generate(self) -> None:
        """Validate input, synchronously generate a case, and emit or show error."""
        background = self.story_input.toPlainText().strip()
        if not background:
            QMessageBox.warning(self, "输入错误", "背景故事不能为空。")
            return

        model_override = self.model_input.text().strip() or None

        self.generate_button.setEnabled(False)
        self.generate_button.setText("正在生成...")
        self.story_input.setEnabled(False)
        self.model_input.setEnabled(False)

        try:
            if model_override:
                from core.llm_client import LLMClient

                client = LLMClient()
                if not client.is_initialized:
                    client.initialize()
                client.set_model(model_override)

            case_dict = generate_case(background)
            self.case_generated.emit(case_dict)
            self.accept()
        except TheBoxError as exc:
            logger.error(f"案件生成失败: {exc}")
            QMessageBox.critical(self, "生成失败", f"案件生成失败:\n{exc}")
            self._reset_buttons()
        except Exception as exc:
            logger.error(f"案件生成出现未知错误: {exc}")
            QMessageBox.critical(self, "生成失败", f"未知错误:\n{exc}")
            self._reset_buttons()

    def _reset_buttons(self) -> None:
        """Re-enable the generate button and input fields after a failure."""
        self.generate_button.setEnabled(True)
        self.generate_button.setText("生成")
        self.story_input.setEnabled(True)
        self.model_input.setEnabled(True)
