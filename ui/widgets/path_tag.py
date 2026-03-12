"""Path tag widget."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget

from qfluentwidgets import BodyLabel, FluentIcon as FIF, TransparentToolButton


class PathTag(QWidget):
    remove_clicked = Signal(str)

    def __init__(self, path: str, removable: bool = False):
        super().__init__()
        self.path = path
        self.removable = removable
        self._setup()

    def _setup(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)

        label = BodyLabel(self.path)
        label.setWordWrap(True)
        layout.addWidget(label, 1)

        if self.removable:
            btn = TransparentToolButton(FIF.DELETE, self)
            btn.setFixedSize(22, 22)
            btn.setToolTip("移除")
            btn.clicked.connect(lambda: self.remove_clicked.emit(self.path))
            layout.addWidget(btn)
