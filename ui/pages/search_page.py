"""Search page."""

from pathlib import Path

import yaml

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from qfluentwidgets import (
    BodyLabel,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    MessageBoxBase,
    PasswordLineEdit,
    PrimaryPushButton,
    ScrollArea,
    StrongBodyLabel,
)
from config import get_config_path
from ui.widgets.result_card import ResultCard
from utils.file_open import reveal_in_file_manager
from workers.search_worker import SearchWorker


class ApiKeyPromptDialog(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.title_label = StrongBodyLabel("需要 API Key", self)
        self.body_label = BodyLabel("当前未配置有效的 API Key，请先输入后再搜索。", self)
        self.api_key_input = PasswordLineEdit(self)
        self.api_key_input.setPlaceholderText("sk-***")

        self.viewLayout.addWidget(self.title_label)
        self.viewLayout.addWidget(self.body_label)
        self.viewLayout.addWidget(self.api_key_input)

        self.widget.setMinimumWidth(420)
        self.yesButton.setText("保存并搜索")
        self.cancelButton.setText("取消")

    def validate(self) -> bool:
        api_key = self.api_key_input.text().strip()
        if api_key and api_key != "sk-your-api-key-here":
            return True

        InfoBar.warning(
            title="API Key 无效",
            content="请输入有效的 API Key。",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self,
        )
        return False


class SearchPage(QWidget):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.current_worker = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        top_row = QHBoxLayout()
        title = StrongBodyLabel("搜索")
        title.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        self.search_input = LineEdit()
        self.search_input.setPlaceholderText("搜索文件名或内容")
        self.search_input.returnPressed.connect(self._on_search)

        self.search_button = PrimaryPushButton("搜索")
        self.search_button.clicked.connect(self._on_search)

        top_row.addWidget(title)
        top_row.addWidget(self.search_input, 1)
        top_row.addWidget(self.search_button)
        layout.addLayout(top_row)

        self.status_label = BodyLabel("输入关键词开始搜索")
        layout.addWidget(self.status_label)

        self.results_scroll = ScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setStyleSheet("border: none; background: transparent;")

        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(6)
        self.results_layout.addStretch()

        self.results_scroll.setWidget(self.results_container)
        layout.addWidget(self.results_scroll, 1)

    def _on_search(self):
        query = self.search_input.text().strip()
        if not query:
            return

        if not self._ensure_api_key():
            return

        if self.current_worker is not None:
            try:
                if self.current_worker.isRunning():
                    self.current_worker.quit()
                    self.current_worker.wait(2000)
            except RuntimeError:
                pass
            self.current_worker = None

        self._clear_results()
        self.status_label.setText("搜索中...")
        self.search_button.setEnabled(False)

        self.current_worker = SearchWorker(query)
        self.current_worker.results_ready.connect(self._on_results)
        self.current_worker.error_occurred.connect(self._on_error)
        self.current_worker.finished.connect(lambda: self.search_button.setEnabled(True))
        self.current_worker.finished.connect(self._on_worker_done)
        self.current_worker.start()

    def _ensure_api_key(self) -> bool:
        api_key = self.cfg.embedding.api_key.strip()
        if api_key and api_key != "sk-your-api-key-here":
            return True

        dialog = ApiKeyPromptDialog(self)
        if dialog.exec() != 1:
            self.status_label.setText("未配置 API Key，已取消搜索")
            return False

        self._save_api_key(dialog.api_key_input.text().strip())
        return True

    def _save_api_key(self, api_key: str) -> None:
        cfg_path = get_config_path()
        data = {}

        if cfg_path.exists():
            with cfg_path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

        data.setdefault("embedding", {})
        data["embedding"]["api_key"] = api_key

        with cfg_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

        self.cfg.embedding.api_key = api_key

        from services import Services

        if Services._search_engine is not None:
            Services._search_engine._embedder._headers["Authorization"] = f"Bearer {api_key}"
        if Services._pipeline is not None:
            Services._pipeline._embedder._headers["Authorization"] = f"Bearer {api_key}"

    def _on_results(self, results, query_time):
        count = len(results)
        self.status_label.setText(f"找到 {count} 条结果，用时 {query_time:.0f} ms")

        if not results:
            empty = BodyLabel("未找到匹配文件")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.results_layout.insertWidget(0, empty)
            return

        for result in results:
            card = ResultCard(result)
            card.reveal_clicked.connect(self._reveal_file)
            self.results_layout.insertWidget(self.results_layout.count() - 1, card)

    def _on_error(self, error):
        self.status_label.setText(f"错误: {error}")

    def _on_worker_done(self):
        self.current_worker = None

    def _clear_results(self):
        while self.results_layout.count() > 1:
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _reveal_file(self, path: str):
        reveal_in_file_manager(Path(path))
