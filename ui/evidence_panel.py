import logging

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDockWidget, QListWidget, QListWidgetItem, QWidget

logger = logging.getLogger("thebox")


class EvidencePanel(QDockWidget):
    """Dockable panel listing case evidences; emits a signal on selection."""

    evidence_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("证据面板", parent)
        self._evidence_ids: list[str] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create the internal list widget and wire the click handler."""
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.setWidget(self.list_widget)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """Map the clicked list row back to an evidence ID and emit it."""
        row = self.list_widget.row(item)
        if 0 <= row < len(self._evidence_ids):
            self.evidence_selected.emit(self._evidence_ids[row])

    def load_evidences(self, evidences: list) -> None:
        """Populate the list with evidence items.

        Each evidence dict must contain at least ``id``, ``name``, and
        ``description`` keys.

        Args:
            evidences: A list of evidence dictionaries.
        """
        self.clear_evidences()
        for ev in evidences:
            ev_id = ev.get("id", "")
            ev_name = ev.get("name", "")
            ev_desc = ev.get("description", "")
            self.list_widget.addItem(f"{ev_name} — {ev_desc}")
            self._evidence_ids.append(ev_id)

    def clear_evidences(self) -> None:
        """Remove all evidence items from the list."""
        self.list_widget.clear()
        self._evidence_ids.clear()
