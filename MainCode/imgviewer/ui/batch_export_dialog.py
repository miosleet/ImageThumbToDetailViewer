# -*- coding: utf-8 -*-

"""
多图「图片调整导出」配置弹窗。
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..theme import set_button_role
from .export_dialog_base import ExportDialogBase


class BatchExportDialog(ExportDialogBase):
    """
    多张图片「图片调整导出」的配置弹窗。

    配置项均以「标题行 + 下方可选行」的形式排列：
        1. 目标格式：jpg / png（默认 jpg）
        2. 长边最大像素：留空则不调整分辨率；输入则等比缩放，
                        使每张图最长边等于该数值，短边按比例缩放
        3. 文件大小：手动输入 MB，导出后体积尽量大但不超过该值
        4. 输出文件：选择输出文件夹（文件名沿用原文件名）
    """

    def __init__(self, count, folder=None, parent=None):

        super().__init__(parent)

        self.count = count
        self.folder = Path(folder) if folder else Path.home()
        self.options = None               # 点击导出后写入的配置

        self.setWindowTitle("图片调整导出")
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(16)

        root.addWidget(self._build_format_row())
        root.addWidget(self._build_long_edge_row())
        root.addWidget(self._build_size_row())
        root.addWidget(self._build_output_row())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        ok_button.setText("开始导出")
        cancel_button.setText("取消")
        set_button_role(ok_button, "primary")
        ok_button.setMinimumWidth(96)
        cancel_button.setMinimumWidth(80)
        # 开始导出不绑定 Enter，也不设默认按钮
        ok_button.setAutoDefault(False)
        ok_button.setDefault(False)
        cancel_button.setAutoDefault(False)
        cancel_button.setDefault(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # --------------------------------------------------------
    # 界面构建
    # --------------------------------------------------------

    def _build_long_edge_row(self):
        """构建「长边最大像素」标题行与单值输入行。"""

        box, layout = self._section("长边最大像素")

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(QLabel("长边"))
        self.long_edge_edit = QLineEdit()
        self.long_edge_edit.setPlaceholderText("留空则不调整分辨率")
        self.long_edge_edit.setFixedWidth(160)
        row.addWidget(self.long_edge_edit)
        row.addWidget(QLabel("px"))
        row.addStretch(1)
        layout.addLayout(row)

        layout.addWidget(self._hint("输入后每张图的最长边缩放到该数值，短边按比例缩放。"))

        return box

    def _build_output_row(self):
        """构建「输出文件」标题行与输出文件夹选择行。"""

        box, layout = self._section("输出文件")

        # 文件夹：点击路径弹出选择窗口（默认当前所在文件夹）
        folder_row = QHBoxLayout()
        folder_row.setSpacing(10)
        folder_row.addWidget(QLabel("文件夹"))
        self.folder_button = QPushButton(str(self.folder))
        self.folder_button.setToolTip("点击选择输出文件夹")
        set_button_role(self.folder_button, "field")
        self.folder_button.clicked.connect(self.choose_output_folder)
        folder_row.addWidget(self.folder_button, 1)
        layout.addLayout(folder_row)

        layout.addWidget(self._hint("文件名沿用原文件名，同名文件自动添加序号。"))

        return box

    def choose_output_folder(self):
        """弹出文件夹选择窗口，更新输出文件夹。"""

        folder = self._choose_folder()
        if folder is None:
            return

        self.folder = folder
        self.folder_button.setText(str(self.folder))

    # --------------------------------------------------------
    # 收集配置
    # --------------------------------------------------------

    def accept(self):
        """校验输入并收集配置写入 self.options，然后关闭窗口。"""

        options = {}

        # 目标格式
        options["format"], options["ext"] = self._collect_format()

        # 长边最大像素（留空则不调整分辨率）
        options["long_edge"] = None
        text = self.long_edge_edit.text().strip()

        if text:
            try:
                long_edge = int(text)
            except ValueError:
                long_edge = 0

            if long_edge <= 0:
                QMessageBox.warning(self, "提示", "长边最大像素请输入正整数（px）。")
                return

            options["long_edge"] = long_edge

        # 文件大小
        try:
            options["max_bytes"] = self._parse_max_bytes(self.size_edit.text())
        except ValueError:
            QMessageBox.warning(self, "提示", "文件大小请输入正数（MB）。")
            return

        # 输出文件
        options["output_dir"] = str(self.folder)

        self.options = options
        super().accept()
