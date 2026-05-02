"""Settings dialog for configuring LLM provider, API key, base URL, and model."""

import logging

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.config import get_api_key, get_settings, save_settings
from core.providers import (
    get_provider_default_model,
    get_provider_list,
    get_provider_models,
)

logger = logging.getLogger("thebox")


class SettingsDialog(QDialog):
    """Dialog for configuring LLM provider, API key, base URL, and model."""

    settings_saved = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._providers = get_provider_list()
        self._setup_ui()
        self._load_current_settings()

    def _setup_ui(self) -> None:
        self.setWindowTitle("LLM 设置")
        self.setMinimumWidth(520)
        self.setMinimumHeight(320)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(12)

        # Provider selector
        self.provider_combo = QComboBox()
        for p in self._providers:
            self.provider_combo.addItem(p["name"], p["id"])
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        form.addRow("Provider:", self.provider_combo)

        # API Key
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("输入 API Key")
        form.addRow("API Key:", self.api_key_input)

        # Base URL
        self.base_url_input = QLineEdit()
        self.base_url_input.setPlaceholderText("https://api.example.com/v1")
        form.addRow("Base URL:", self.base_url_input)

        # Model selector (editable combo)
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.lineEdit().setPlaceholderText("输入或选择模型名称")
        form.addRow("模型:", self.model_combo)

        layout.addLayout(form)

        # Buttons
        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 8, 0, 0)

        self.test_button = QPushButton("测试连接")
        self.test_button.clicked.connect(self._on_test_connection)
        button_layout.addWidget(self.test_button)

        button_layout.addStretch()

        self.save_button = QPushButton("保存")
        self.save_button.clicked.connect(self._on_save)
        button_layout.addWidget(self.save_button)

        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addWidget(button_row)

    def _load_current_settings(self) -> None:
        """Load current settings and populate the form."""
        settings = get_settings()
        provider_id = settings["provider"]

        # Set provider combo
        for i in range(self.provider_combo.count()):
            if self.provider_combo.itemData(i) == provider_id:
                self.provider_combo.setCurrentIndex(i)
                break

        # Set base URL
        self.base_url_input.setText(settings["base_url"])

        # Set model
        self._refresh_model_list(provider_id)
        current_model = settings["model"]
        idx = self.model_combo.findText(current_model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        else:
            self.model_combo.setEditText(current_model)

        # Load API key
        api_key = get_api_key(provider_id=provider_id)
        if api_key:
            self.api_key_input.setText(api_key)

    def _on_provider_changed(self, index: int) -> None:
        """Update base URL and model list when provider changes."""
        provider_id = self.provider_combo.currentData()
        if provider_id is None:
            return

        from core.providers import get_provider_base_url

        # Update base URL
        url = get_provider_base_url(provider_id)
        self.base_url_input.setText(url)

        # Update model list
        default_model = get_provider_default_model(provider_id)
        self._refresh_model_list(provider_id)
        idx = self.model_combo.findText(default_model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        else:
            self.model_combo.setEditText(default_model)

        # Load API key for this provider
        api_key = get_api_key(provider_id=provider_id)
        if api_key:
            self.api_key_input.setText(api_key)
        else:
            self.api_key_input.clear()

    def _refresh_model_list(self, provider_id: str) -> None:
        """Refresh the model combo box items for a given provider."""
        self.model_combo.clear()
        models = get_provider_models(provider_id)
        for m in models:
            self.model_combo.addItem(m)

    def _on_test_connection(self) -> None:
        """Test the connection to the configured LLM endpoint."""
        api_key = self.api_key_input.text().strip()
        base_url = self.base_url_input.text().strip()
        model = self.model_combo.currentText().strip()

        if not api_key:
            QMessageBox.warning(self, "测试失败", "API Key 不能为空。")
            return
        if not base_url:
            QMessageBox.warning(self, "测试失败", "Base URL 不能为空。")
            return
        if not model:
            QMessageBox.warning(self, "测试失败", "模型名称不能为空。")
            return

        self.test_button.setEnabled(False)
        self.test_button.setText("测试中...")

        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            content = response.choices[0].message.content
            QMessageBox.information(
                self, "连接成功",
                f"连接成功！模型响应: {content[:50] if content else '(空响应)'}"
            )
        except Exception as exc:
            logger.error(f"连接测试失败: {exc}")
            QMessageBox.critical(self, "连接失败", f"连接测试失败:\n{exc}")
        finally:
            self.test_button.setEnabled(True)
            self.test_button.setText("测试连接")

    def _on_save(self) -> None:
        """Validate and save settings."""
        provider_id = self.provider_combo.currentData()
        api_key = self.api_key_input.text().strip()
        base_url = self.base_url_input.text().strip()
        model = self.model_combo.currentText().strip()

        if not api_key:
            QMessageBox.warning(self, "保存失败", "API Key 不能为空。")
            return
        if not base_url:
            QMessageBox.warning(self, "保存失败", "Base URL 不能为空。")
            return
        if not model:
            QMessageBox.warning(self, "保存失败", "模型名称不能为空。")
            return

        save_settings(provider_id, base_url, model, api_key)

        # Re-initialize the global LLM client
        try:
            from core.llm_client import llm_client

            llm_client.reinitialize(provider_id, api_key, base_url, model)
        except Exception as exc:
            logger.warning(f"LLMClient 重新初始化失败: {exc}")

        self.settings_saved.emit()
        QMessageBox.information(self, "保存成功", "LLM 设置已保存。")
        self.accept()
