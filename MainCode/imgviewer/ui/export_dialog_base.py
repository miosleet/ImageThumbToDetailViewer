# -*- coding: utf-8 -*-

"""
导出弹窗公共基类。

批量导出与单图导出的配置弹窗共享「目标格式」「文件大小」等
通用配置行的构建，以及格式 / 体积参数的解析逻辑，统一放在此处。
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class ExportDialogBase(QDialog):

    @staticmethod
    def _section(title):
        """构建「标题行 + 内容」的标准分区容器，返回 (容器, 纵向布局)。"""

        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel(title)
        label.setObjectName("Title")
        layout.addWidget(label)

        return box, layout

    @staticmethod
    def _hint(text):
        """构建灰色说明文字标签。"""

        label = QLabel(text)
        label.setObjectName("Hint")
        label.setWordWrap(True)
        return label

    def _build_format_row(self):
        """构建「目标格式」标题行与 jpg / png 单选行。"""

        box, layout = self._section("目标格式")

        row = QHBoxLayout()
        row.setSpacing(16)
        self.jpg_radio = QRadioButton("jpg")
        self.png_radio = QRadioButton("png")
        self.jpg_radio.setChecked(True)   # 默认 jpg

        self.format_group = QButtonGroup(self)
        self.format_group.addButton(self.jpg_radio)
        self.format_group.addButton(self.png_radio)

        row.addWidget(self.jpg_radio)
        row.addWidget(self.png_radio)
        row.addStretch(1)
        layout.addLayout(row)

        return box

    def _build_size_row(self):
        """构建「文件大小」标题行与 MB 输入行。"""

        box, layout = self._section("文件大小")

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(QLabel("不超过"))
        self.size_edit = QLineEdit()
        self.size_edit.setPlaceholderText("留空则按最高品质导出")
        self.size_edit.setFixedWidth(160)
        row.addWidget(self.size_edit)
        row.addWidget(QLabel("MB"))
        row.addStretch(1)
        layout.addLayout(row)

        layout.addWidget(self._hint(
            "JPG 通过品质控制体积；PNG 为无损格式，体积仅由分辨率决定。"
        ))

        return box

    def current_ext(self):
        """返回当前目标格式对应的文件后缀。"""

        return ".jpg" if self.jpg_radio.isChecked() else ".png"

    def _collect_format(self):
        """返回 (格式名, 后缀)，供导出配置使用。"""

        fmt = "JPEG" if self.jpg_radio.isChecked() else "PNG"
        return fmt, ".jpg" if fmt == "JPEG" else ".png"

    @staticmethod
    def _parse_max_bytes(text):
        """把 MB 文本解析为字节数：留空返回 None，非法或非正抛出 ValueError。"""

        text = text.strip()
        if not text:
            return None

        megabytes = float(text)
        if megabytes <= 0:
            raise ValueError
        return int(megabytes * 1024 * 1024)

    def _choose_folder(self):
        """弹出文件夹选择窗口，返回所选路径；未选择返回 None。"""

        folder = QFileDialog.getExistingDirectory(
            self, "选择输出文件夹", str(self.folder)
        )
        return Path(folder) if folder else None
