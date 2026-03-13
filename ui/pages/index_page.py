"""Index page."""

from config import get_config_path
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    CheckBox,
    PlainTextEdit,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    StrongBodyLabel,
)
from workers.index_worker import IndexWorker


class IndexPage(QWidget):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.current_worker = None
        self.stop_worker = None
        self.setup_ui()
        self._refresh_index_status()

    def setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        title = StrongBodyLabel("索引")
        outer.addWidget(title)

        status_group = CardWidget()
        status_layout = QVBoxLayout(status_group)
        status_layout.setContentsMargins(16, 12, 16, 12)
        status_layout.addWidget(BodyLabel("状态"))

        self.status_label = BodyLabel("加载中...")
        status_layout.addWidget(self.status_label)

        self.progress_bar = ProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        status_layout.addWidget(self.progress_bar)

        self.progress_details = BodyLabel("")
        status_layout.addWidget(self.progress_details)

        outer.addWidget(status_group)

        action_group = CardWidget()
        action_layout = QVBoxLayout(action_group)
        action_layout.setContentsMargins(16, 12, 16, 12)
        action_layout.addWidget(BodyLabel("操作"))

        btn_row = QHBoxLayout()
        self.start_button = PrimaryPushButton("开始索引")
        self.start_button.clicked.connect(self._start_index)

        self.stop_button = PushButton("停止")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_index)

        btn_row.addWidget(self.start_button)
        btn_row.addWidget(self.stop_button)
        btn_row.addStretch()
        action_layout.addLayout(btn_row)

        self.docs_toggle = CheckBox("索引文档内容 (PDF / DOCX / TXT / MD)")
        self.docs_toggle.setChecked(self.cfg.indexing.enable_content_docs)
        self.docs_toggle.toggled.connect(self._toggle_docs)
        action_layout.addWidget(self.docs_toggle)

        self.code_toggle = CheckBox("索引代码内容")
        self.code_toggle.setChecked(self.cfg.indexing.enable_content_code)
        self.code_toggle.toggled.connect(self._toggle_code)
        action_layout.addWidget(self.code_toggle)

        outer.addWidget(action_group)

        danger_group = CardWidget()
        danger_layout = QHBoxLayout(danger_group)
        danger_layout.setContentsMargins(16, 12, 16, 12)
        danger_layout.setSpacing(8)

        danger_title = BodyLabel("数据维护")
        danger_layout.addWidget(danger_title)

        clear_btn = PushButton("清空索引")
        clear_btn.clicked.connect(self._clear_index)

        drop_btn = PushButton("重建表")
        drop_btn.clicked.connect(self._drop_tables)

        danger_layout.addSpacing(8)
        danger_layout.addWidget(clear_btn)
        danger_layout.addWidget(drop_btn)
        danger_layout.addStretch()

        outer.addWidget(danger_group)

        self.error_display = PlainTextEdit()
        self.error_display.setReadOnly(True)
        self.error_display.setVisible(False)
        self.error_display.setMaximumHeight(120)
        outer.addWidget(self.error_display)

        outer.addStretch()

    def _start_index(self):
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.error_display.setVisible(False)
        self.error_display.clear()

        self.current_worker = IndexWorker("start")
        self.current_worker.progress_updated.connect(self._update_progress)
        self.current_worker.indexing_complete.connect(self._on_index_complete)
        self.current_worker.error_occurred.connect(self._on_index_error)
        self.current_worker.finished.connect(self.current_worker.deleteLater)
        self.current_worker.start()

    def _stop_index(self):
        self.stop_worker = IndexWorker("stop")
        self.stop_worker.finished.connect(self.stop_worker.deleteLater)
        self.stop_worker.start()
        self.stop_button.setEnabled(False)

    def _update_progress(self, progress):
        total = progress["total_files_discovered"]
        indexed = progress["files_indexed"]
        chunks = progress["chunks_indexed"]

        if total > 0:
            percent = int((indexed / total) * 100)
            self.progress_bar.setValue(percent)
            self.progress_details.setText(f"{indexed}/{total} 文件，{chunks} 内容块")
        else:
            self.progress_bar.setValue(0)
            self.progress_details.setText(f"{indexed} 文件，{chunks} 内容块")

        if progress["is_running"]:
            self.status_label.setText("索引中...")
        elif progress["is_complete"]:
            self.status_label.setText("完成")

        if progress["errors"]:
            self.error_display.setVisible(True)
            self.error_display.setPlainText("\n".join(progress["errors"]))

    def _on_index_complete(self):
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self._refresh_index_status()

    def _on_index_error(self, error):
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.error_display.setVisible(True)
        self.error_display.appendPlainText(error)
        self._refresh_index_status()

    def _refresh_index_status(self):
        try:
            from services import Services

            pipeline = Services.get_pipeline()
            file_count = pipeline._filenames_repo.count()
        except Exception:
            self.status_label.setText("状态读取失败")
            self.progress_details.setText("")
            self.progress_bar.setValue(0)
            return

        if file_count > 0:
            self.status_label.setText("已建立索引")
        else:
            self.status_label.setText("未建立索引")
        self.progress_details.setText(f"当前已索引 {file_count} 个文件")
        self.progress_bar.setValue(0)

    def _toggle_docs(self, checked):
        self._write_cfg("indexing", "enable_content_docs", checked)

    def _toggle_code(self, checked):
        self._write_cfg("indexing", "enable_content_code", checked)

    def _write_cfg(self, section, key, value):
        import yaml

        cfg_path = get_config_path()
        data = {}
        if cfg_path.exists():
            with cfg_path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        data.setdefault(section, {})[key] = value
        with cfg_path.open("w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True)

    def _clear_index(self):
        if QMessageBox.question(self, "确认", "确定清空所有索引数据吗？") != QMessageBox.StandardButton.Yes:
            return
        try:
            from services import Services

            pipeline = Services.get_pipeline()
            pipeline._filenames_repo.clear()
            pipeline._chunks_repo.clear()
            self.status_label.setText("已清空")
            self.progress_bar.setValue(0)
            self.progress_details.setText("")
            self._refresh_index_status()
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))

    def _drop_tables(self):
        if QMessageBox.question(self, "确认", "确定重建索引表吗？") != QMessageBox.StandardButton.Yes:
            return
        try:
            from services import Services

            pipeline = Services.get_pipeline()
            pipeline._filenames_repo.drop()
            pipeline._chunks_repo.drop()
            self.status_label.setText("已重建")
            self.progress_bar.setValue(0)
            self.progress_details.setText("")
            self._refresh_index_status()
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))
