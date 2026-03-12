"""Result row widget."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from qfluentwidgets import BodyLabel, CardWidget, PushButton, StrongBodyLabel


class ResultCard(QWidget):
    reveal_clicked = Signal(str)

    def __init__(self, result):
        super().__init__()
        self.result = result
        self.setup_ui()

    def setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        container = CardWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(8, 8, 8, 8)
        row.setSpacing(10)

        left = QVBoxLayout()
        left.setSpacing(2)

        name_lbl = StrongBodyLabel(self.result.name)
        left.addWidget(name_lbl)

        path_lbl = BodyLabel(self.result.path)
        path_lbl.setWordWrap(True)
        left.addWidget(path_lbl)

        if self.result.snippet:
            snippet_lbl = BodyLabel(self.result.snippet)
            snippet_lbl.setWordWrap(True)
            left.addWidget(snippet_lbl)

        row.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(4)
        right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        score_lbl = BodyLabel(f"{self.result.score:.2f}")
        score_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(score_lbl)

        open_btn = PushButton("打开")
        open_btn.clicked.connect(lambda: self.reveal_clicked.emit(self.result.path))
        right.addWidget(open_btn)

        row.addLayout(right)
        outer.addWidget(container)
