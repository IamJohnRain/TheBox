import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

logger = logging.getLogger("thebox")

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

_NORMAL_SVG = _ASSETS_DIR / "suspect_normal.svg"
_TENSE_SVG = _ASSETS_DIR / "suspect_tense.svg"
_BREAKDOWN_SVG = _ASSETS_DIR / "suspect_breakdown.svg"


class SuspectDisplay(QWidget):
    """Widget displaying a suspect portrait, name label, and pressure indicator."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the portrait, name label, and pressure bar layout."""
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.portrait_label = QLabel()
        self.portrait_label.setFixedSize(200, 200)
        self.portrait_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.portrait_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.name_label = QLabel("未选择嫌疑人")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.name_label, alignment=Qt.AlignmentFlag.AlignCenter)

        pressure_row = QWidget()
        pressure_layout = QHBoxLayout(pressure_row)
        pressure_layout.setContentsMargins(0, 0, 0, 0)

        pressure_label = QLabel("压力:")
        pressure_layout.addWidget(pressure_label)

        self.pressure_bar = QProgressBar()
        self.pressure_bar.setRange(0, 100)
        self.pressure_bar.setValue(0)
        self.pressure_bar.setTextVisible(True)
        pressure_layout.addWidget(self.pressure_bar)

        layout.addWidget(pressure_row)

    def update_suspect(self, name: str, pressure: int) -> None:
        """Update the suspect name and switch the portrait image based on pressure.

        Args:
            name: The display name of the suspect.
            pressure: The current pressure value (0-100). Values below 30 show
                      the normal expression, 30-69 the tense expression, and
                      70 or above the breakdown expression.
        """
        self.name_label.setText(name)
        self.pressure_bar.setValue(max(0, min(100, pressure)))

        if pressure < 30:
            svg_path = _NORMAL_SVG
        elif pressure < 70:
            svg_path = _TENSE_SVG
        else:
            svg_path = _BREAKDOWN_SVG

        if svg_path.exists():
            pixmap = QPixmap(str(svg_path))
            scaled = pixmap.scaled(
                200,
                200,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.portrait_label.setPixmap(scaled)
        else:
            logger.warning(f"Portrait SVG not found: {svg_path}")
            self.portrait_label.clear()

    def clear(self) -> None:
        """Reset the widget to its empty default state."""
        self.portrait_label.clear()
        self.name_label.setText("未选择嫌疑人")
        self.pressure_bar.setValue(0)
