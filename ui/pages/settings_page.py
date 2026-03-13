"""Settings page."""

import yaml
from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from config import get_config_path
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PasswordLineEdit,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    StrongBodyLabel,
    SwitchButton,
)
from ui.widgets.path_tag import PathTag
from utils import autostart


class SettingsPage(QWidget):
    FIELD_LABEL_WIDTH = 96

    TEXT_SETTINGS = "\u8bbe\u7f6e"
    TEXT_STARTUP = "\u542f\u52a8"
    TEXT_AUTO_START = "\u5f00\u673a\u81ea\u542f\u52a8"
    TEXT_AUTO_INDEX = "\u81ea\u52a8\u5efa\u7acb\u65b0\u6587\u4ef6\u7d22\u5f15"
    TEXT_INDEXING = "\u7d22\u5f15"
    TEXT_DISABLE_LARGE_FILE_PROTECTION = "\u5173\u95ed\u5927\u6587\u4ef6\u4fdd\u62a4\uff08\u4e0d\u63a8\u8350\uff09"
    TEXT_EMBEDDING = "\u5411\u91cf\u63a5\u53e3"
    TEXT_API_URL = "\u63a5\u53e3\u5730\u5740"
    TEXT_API_KEY = "\u63a5\u53e3\u5bc6\u94a5"
    TEXT_MODEL = "\u6a21\u578b"
    TEXT_QUERY_PREFIX = "（bge-m3专属）query前缀"
    TEXT_QUERY_PREFIX_FAILED = "切换 query 前缀失败：{error}"
    TEXT_DIM_INVALID = "向量维度必须是正整数"
    TEXT_DIM_POSITIVE = "向量维度必须大于 0"
    TEXT_EMBEDDING_DIM = "\u5411\u91cf\u7ef4\u5ea6"
    TEXT_SAVE = "\u4fdd\u5b58"
    TEXT_INDEX_PATHS = "\u7d22\u5f15\u8def\u5f84"
    TEXT_PATH_HINT = "\u672a\u8bbe\u7f6e\u8def\u5f84\u65f6\u6267\u884c\u5168\u76d8\u626b\u63cf"
    TEXT_PATH_PLACEHOLDER = "\u7edd\u5bf9\u8def\u5f84\uff0c\u4f8b\u5982 D:/Projects"
    TEXT_ADD = "\u6dfb\u52a0"
    TEXT_EXCLUSIONS = "\u6392\u9664\u89c4\u5219"
    TEXT_EXCLUSION_HINT = "\u9ed8\u8ba4\u4f1a\u6392\u9664\u7cfb\u7edf\u76ee\u5f55\u3001\u9690\u85cf\u76ee\u5f55\u4e0e\u6784\u5efa\u7f13\u5b58\u76ee\u5f55"
    TEXT_EXCLUSION_PLACEHOLDER = "\u76ee\u5f55\u540d\u6216\u7edd\u5bf9\u8def\u5f84"
    TEXT_INPUT_ERROR = "\u8f93\u5165\u9519\u8bef"
    TEXT_SUCCESS = "\u6210\u529f"
    TEXT_EMBEDDING_SAVED = "\u5411\u91cf\u63a5\u53e3\u914d\u7f6e\u5df2\u4fdd\u5b58\u3002\n\u82e5\u4fee\u6539\u4e86\u5411\u91cf\u7ef4\u5ea6\uff0c\u8bf7\u5728\u7d22\u5f15\u9875\u91cd\u5efa\u8868\u540e\u91cd\u65b0\u7d22\u5f15\u3002"
    TEXT_UNSUPPORTED = "\u4e0d\u652f\u6301"
    TEXT_AUTOSTART_UNSUPPORTED = "\u5f53\u524d\u5e73\u53f0\u6682\u4e0d\u652f\u6301\u5f00\u673a\u81ea\u542f"
    TEXT_ERROR = "\u9519\u8bef"
    TEXT_AUTOSTART_FAILED = "\u8bbe\u7f6e\u5f00\u673a\u81ea\u542f\u5931\u8d25\uff1a{error}\n\nWindows \u9700\u8981\u7ba1\u7406\u5458\u6743\u9650\uff0c\u82e5\u53d6\u6d88 UAC \u63d0\u793a\u4f1a\u8bbe\u7f6e\u5931\u8d25\u3002"
    TEXT_APPLIED = "\u5df2\u5e94\u7528"
    TEXT_AUTOSTART_APPLIED = "\u5f00\u673a\u81ea\u542f\u5df2\u7acb\u5373\u751f\u6548"
    TEXT_AUTO_INDEX_FAILED = "\u5207\u6362\u81ea\u52a8\u5efa\u7acb\u65b0\u6587\u4ef6\u7d22\u5f15\u5931\u8d25\uff1a{error}"

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("background: transparent")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        title = StrongBodyLabel(self.TEXT_SETTINGS)
        outer.addWidget(title)

        scroll = ScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent")

        container = QWidget()
        container.setStyleSheet("background: transparent")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self._build_startup_section(layout)
        self._build_indexing_section(layout)
        self._build_embedding_section(layout)
        self._build_paths_section(layout)
        self._build_exclusion_section(layout)

        layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll, 1)

        self._load_paths()
        self._load_exclusions()

    def _build_startup_section(self, parent_layout: QVBoxLayout):
        section = QVBoxLayout()
        section.setSpacing(8)
        section.addWidget(StrongBodyLabel(self.TEXT_STARTUP))

        self.auto_start_switch = SwitchButton()
        self.auto_start_switch.setChecked(self.cfg.auto_start)
        self.auto_start_switch.checkedChanged.connect(self._toggle_auto_start)
        section.addWidget(self._make_switch_row(self.TEXT_AUTO_START, self.auto_start_switch))

        self.auto_index_switch = SwitchButton()
        self.auto_index_switch.setChecked(self.cfg.auto_index_new_files)
        self.auto_index_switch.checkedChanged.connect(self._toggle_auto_index_new_files)
        section.addWidget(self._make_switch_row(self.TEXT_AUTO_INDEX, self.auto_index_switch))

        container = QWidget()
        container.setLayout(section)
        parent_layout.addWidget(container)

    def _build_embedding_section(self, parent_layout: QVBoxLayout):
        section = QVBoxLayout()
        section.setSpacing(8)
        section.addWidget(StrongBodyLabel(self.TEXT_EMBEDDING))

        self.api_url_input = LineEdit()
        self.api_url_input.setText(self.cfg.embedding.api_base_url)
        section.addWidget(self._make_input_row(self.TEXT_API_URL, self.api_url_input))

        self.api_key_input = PasswordLineEdit()
        self.api_key_input.setPlaceholderText("sk-***")
        self.api_key_input.setText(self.cfg.embedding.api_key)
        section.addWidget(self._make_input_row(self.TEXT_API_KEY, self.api_key_input))

        self.model_input = LineEdit()
        self.model_input.setText(self.cfg.embedding.model)
        section.addWidget(self._make_input_row(self.TEXT_MODEL, self.model_input))



        self.embedding_dim_input = LineEdit()
        self.embedding_dim_input.setValidator(QIntValidator(1, 100000, self))
        self.embedding_dim_input.setText(str(self.cfg.embedding.embedding_dim))
        section.addWidget(self._make_input_row(self.TEXT_EMBEDDING_DIM, self.embedding_dim_input))

        self.query_prefix_switch = SwitchButton()
        self.query_prefix_switch.setChecked(self.cfg.embedding.query_prefix_enabled)
        self.query_prefix_switch.checkedChanged.connect(self._toggle_query_prefix_enabled)
        section.addWidget(self._make_switch_row(self.TEXT_QUERY_PREFIX, self.query_prefix_switch))

        save_row = QHBoxLayout()
        save_row.setContentsMargins(self.FIELD_LABEL_WIDTH + 8, 0, 0, 0)
        save_btn = PrimaryPushButton(self.TEXT_SAVE)
        save_btn.clicked.connect(self._save_embedding_config)
        save_row.addWidget(save_btn)
        save_row.addStretch(1)
        section.addLayout(save_row)

        container = QWidget()
        container.setLayout(section)
        parent_layout.addWidget(container)

    def _build_indexing_section(self, parent_layout: QVBoxLayout):
        section = QVBoxLayout()
        section.setSpacing(8)
        section.addWidget(StrongBodyLabel(self.TEXT_INDEXING))

        self.disable_large_file_protection_switch = SwitchButton()
        self.disable_large_file_protection_switch.setChecked(
            self.cfg.indexing.disable_large_file_protection
        )
        self.disable_large_file_protection_switch.checkedChanged.connect(
            self._toggle_disable_large_file_protection
        )
        section.addWidget(
            self._make_switch_row(
                self.TEXT_DISABLE_LARGE_FILE_PROTECTION,
                self.disable_large_file_protection_switch,
            )
        )

        container = QWidget()
        container.setLayout(section)
        parent_layout.addWidget(container)

    def _build_paths_section(self, parent_layout: QVBoxLayout):
        section = QVBoxLayout()
        section.setSpacing(8)
        section.addWidget(StrongBodyLabel(self.TEXT_INDEX_PATHS))

        self.paths_container = QVBoxLayout()
        self.paths_container.setSpacing(2)
        section.addLayout(self.paths_container)

        self.full_scan_hint = CaptionLabel(self.TEXT_PATH_HINT)
        section.addWidget(self.full_scan_hint)

        add_path_row = QHBoxLayout()
        self.new_path_input = LineEdit()
        self.new_path_input.setPlaceholderText(self.TEXT_PATH_PLACEHOLDER)
        add_path_btn = PushButton(self.TEXT_ADD)
        add_path_btn.clicked.connect(self._add_path)
        add_path_row.addWidget(self.new_path_input, 1)
        add_path_row.addWidget(add_path_btn)
        section.addLayout(add_path_row)

        container = QWidget()
        container.setLayout(section)
        parent_layout.addWidget(container)

    def _build_exclusion_section(self, parent_layout: QVBoxLayout):
        section = QVBoxLayout()
        section.setSpacing(8)
        section.addWidget(StrongBodyLabel(self.TEXT_EXCLUSIONS))
        section.addWidget(CaptionLabel(self.TEXT_EXCLUSION_HINT))

        self.exclusions_container = QVBoxLayout()
        self.exclusions_container.setSpacing(2)
        section.addLayout(self.exclusions_container)

        add_excl_row = QHBoxLayout()
        self.new_exclusion_input = LineEdit()
        self.new_exclusion_input.setPlaceholderText(self.TEXT_EXCLUSION_PLACEHOLDER)
        add_excl_btn = PushButton(self.TEXT_ADD)
        add_excl_btn.clicked.connect(self._add_exclusion)
        add_excl_row.addWidget(self.new_exclusion_input, 1)
        add_excl_row.addWidget(add_excl_btn)
        section.addLayout(add_excl_row)

        container = QWidget()
        container.setLayout(section)
        parent_layout.addWidget(container)

    def _make_input_row(self, title: str, editor: QWidget) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        label = BodyLabel(title)
        label.setFixedWidth(self.FIELD_LABEL_WIDTH)
        row_layout.addWidget(label)

        if hasattr(editor, "setMinimumWidth"):
            editor.setMinimumWidth(420)
        row_layout.addWidget(editor, 1)
        return row

    def _make_switch_row(self, title: str, switch: SwitchButton) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        label = BodyLabel(title)
        row_layout.addWidget(label)
        row_layout.addStretch(1)
        row_layout.addWidget(switch)
        return row

    def _read_cfg(self) -> dict:
        cfg_path = get_config_path()
        if cfg_path.exists():
            with cfg_path.open("r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def _write_cfg(self, data: dict):
        cfg_path = get_config_path()
        with cfg_path.open("w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True)

    def _save_embedding_config(self):
        dim_text = self.embedding_dim_input.text().strip()
        if not dim_text:
            InfoBar.warning(
                title=self.TEXT_INPUT_ERROR,
                content=self.TEXT_DIM_INVALID,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
            return

        embedding_dim = int(dim_text)
        if embedding_dim <= 0:
            InfoBar.warning(
                title=self.TEXT_INPUT_ERROR,
                content=self.TEXT_DIM_POSITIVE,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
            return

        data = self._read_cfg()
        data.setdefault("embedding", {})
        data["embedding"]["api_base_url"] = self.api_url_input.text()
        data["embedding"]["api_key"] = self.api_key_input.text()
        data["embedding"]["model"] = self.model_input.text()
        data["embedding"]["embedding_dim"] = embedding_dim
        self._write_cfg(data)
        self.cfg.embedding.api_base_url = data["embedding"]["api_base_url"]
        self.cfg.embedding.api_key = data["embedding"]["api_key"]
        self.cfg.embedding.model = data["embedding"]["model"]
        self.cfg.embedding.embedding_dim = embedding_dim
        InfoBar.success(
                title=self.TEXT_SUCCESS,
                content=self.TEXT_EMBEDDING_SAVED,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )

    def _toggle_auto_start(self, enabled: bool):
        try:
            autostart.set_enabled(enabled)
        except NotImplementedError:
            InfoBar.warning(
                title=self.TEXT_UNSUPPORTED,
                content=self.TEXT_AUTOSTART_UNSUPPORTED,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
            self.auto_start_switch.blockSignals(True)
            self.auto_start_switch.setChecked(False)
            self.auto_start_switch.blockSignals(False)
            return
        except Exception as e:
            InfoBar.error(
                title=self.TEXT_ERROR,
                content=self.TEXT_AUTOSTART_FAILED.format(error=e,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            ),
            )
            self.auto_start_switch.blockSignals(True)
            self.auto_start_switch.setChecked(not enabled)
            self.auto_start_switch.blockSignals(False)
            return

        data = self._read_cfg()
        data.setdefault("app", {})["auto_start"] = enabled
        self._write_cfg(data)
        InfoBar.success(
                title=self.TEXT_APPLIED,
                content=self.TEXT_AUTOSTART_APPLIED,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )

    def _toggle_query_prefix_enabled(self, enabled: bool):
        from services import Services

        try:
            data = self._read_cfg()
            data.setdefault("embedding", {})["query_prefix_enabled"] = enabled
            self._write_cfg(data)
            self.cfg.embedding.query_prefix_enabled = enabled
            Services.set_query_prefix_enabled(enabled)
        except Exception as e:
            InfoBar.error(
                title=self.TEXT_ERROR,
                content=self.TEXT_QUERY_PREFIX_FAILED.format(error=e,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            ),
            )
            self.query_prefix_switch.blockSignals(True)
            self.query_prefix_switch.setChecked(not enabled)
            self.query_prefix_switch.blockSignals(False)

    def _toggle_auto_index_new_files(self, enabled: bool):
        from services import Services

        try:
            if enabled:
                Services.start_file_watcher()
            else:
                Services.stop_file_watcher()
        except Exception as e:
            InfoBar.error(
                title=self.TEXT_ERROR,
                content=self.TEXT_AUTO_INDEX_FAILED.format(error=e,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            ),
            )
            self.auto_index_switch.blockSignals(True)
            self.auto_index_switch.setChecked(not enabled)
            self.auto_index_switch.blockSignals(False)
            return

        data = self._read_cfg()
        data.setdefault("app", {})["auto_index_new_files"] = enabled
        self._write_cfg(data)
        self.cfg.auto_index_new_files = enabled

    def _toggle_disable_large_file_protection(self, enabled: bool):
        data = self._read_cfg()
        data.setdefault("indexing", {})["disable_large_file_protection"] = enabled
        self._write_cfg(data)
        self.cfg.indexing.disable_large_file_protection = enabled

    def _add_path(self):
        path = self.new_path_input.text().strip()
        if not path:
            return
        data = self._read_cfg()
        paths = data.setdefault("indexing", {}).setdefault("include_paths", [])
        if path not in paths:
            paths.append(path)
            self._write_cfg(data)
        self._load_paths()
        self.new_path_input.clear()

    def _remove_path(self, path):
        data = self._read_cfg()
        paths = data.get("indexing", {}).get("include_paths", [])
        if path in paths:
            paths.remove(path)
            self._write_cfg(data)
        self._load_paths()

    def _add_exclusion(self):
        rule = self.new_exclusion_input.text().strip()
        if not rule:
            return
        data = self._read_cfg()
        rules = data.setdefault("indexing", {}).setdefault("user_exclusions", [])
        if rule not in rules:
            rules.append(rule)
            self._write_cfg(data)
        self._load_exclusions()
        self.new_exclusion_input.clear()

    def _remove_exclusion(self, rule):
        data = self._read_cfg()
        rules = data.get("indexing", {}).get("user_exclusions", [])
        if rule in rules:
            rules.remove(rule)
            self._write_cfg(data)
        self._load_exclusions()

    def _load_paths(self):
        while self.paths_container.count():
            item = self.paths_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        data = self._read_cfg()
        paths = data.get("indexing", {}).get("include_paths", [])
        self.full_scan_hint.setVisible(not paths)

        for p in paths:
            tag = PathTag(p, removable=True)
            tag.remove_clicked.connect(self._remove_path)
            self.paths_container.addWidget(tag)

    def _load_exclusions(self):
        while self.exclusions_container.count():
            item = self.exclusions_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        data = self._read_cfg()
        rules = data.get("indexing", {}).get("user_exclusions", [])

        for r in rules:
            tag = PathTag(r, removable=True)
            tag.remove_clicked.connect(self._remove_exclusion)
            self.exclusions_container.addWidget(tag)
