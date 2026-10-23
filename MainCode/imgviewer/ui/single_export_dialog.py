# -*- coding: utf-8 -*-

"""
单图「图片调整导出」配置弹窗。
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QIntValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..image_export import unique_stem
from ..theme import set_button_role
from .export_dialog_base import ExportDialogBase
from .image_edit_view import ImageEditView


class SingleExportDialog(ExportDialogBase):
    """
    单张图片「图片调整导出」的配置弹窗。

    尺寸与主窗口一致，分为左右两块：
        左：预览窗（ImageEditView），可视化缩放 / 旋转 / 移动图片；
        右：编辑窗，包含 分辨率 / 切片 / 目标格式 / 文件大小 / 输出文件。
    """

    def __init__(self, image: QImage, source_stem, folder=None, parent=None):

        super().__init__(parent)

        self.source_size = (image.width(), image.height())
        self.source_stem = source_stem
        self.folder = Path(folder) if folder else Path.home()
        self.initial_folder = self.folder
        self.options = None
        self._syncing = False
        self._name_edited = False

        self.setWindowTitle("图片调整导出")

        # 标题栏增加最小化 / 最大化（全屏）按钮
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
        )

        self.preview = ImageEditView(image, image.width(), image.height())

        editor = QWidget()
        editor.setObjectName("Editor")
        editor_layout = QVBoxLayout(editor)
        editor_layout.setContentsMargins(18, 18, 18, 16)
        editor_layout.setSpacing(16)

        editor_layout.addWidget(self._build_resolution_row())
        editor_layout.addWidget(self._build_slice_row())
        editor_layout.addWidget(self._build_format_row())
        editor_layout.addWidget(self._build_size_row())
        editor_layout.addWidget(self._build_output_row())
        editor_layout.addStretch(1)

        # 原图未完全覆盖输出图时的红字提示（位于开始导出按钮上一行）
        self.cover_warning = QLabel("原图未完全覆盖输出图")
        self.cover_warning.setObjectName("Warning")
        self.cover_warning.setVisible(not self.preview.is_covered())
        editor_layout.addWidget(self.cover_warning)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        button_row.addStretch(1)

        # 开始导出 / 还原为初始 / 取消，均不绑定 Enter
        ok_button = QPushButton("开始导出")
        set_button_role(ok_button, "primary")
        ok_button.setMinimumWidth(96)
        ok_button.setAutoDefault(False)
        ok_button.setDefault(False)
        ok_button.clicked.connect(self.accept)
        button_row.addWidget(ok_button)

        self.reset_button = QPushButton("还原为初始")
        self.reset_button.setMinimumWidth(96)
        self.reset_button.setAutoDefault(False)
        self.reset_button.setDefault(False)
        self.reset_button.clicked.connect(self.reset_all)
        button_row.addWidget(self.reset_button)

        cancel_button = QPushButton("取消")
        cancel_button.setMinimumWidth(80)
        cancel_button.setAutoDefault(False)
        cancel_button.setDefault(False)
        cancel_button.clicked.connect(self.reject)
        button_row.addWidget(cancel_button)

        editor_layout.addLayout(button_row)

        self.preview.coverageChanged.connect(self.on_coverage_changed)

        editor.setFixedWidth(380)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self.preview, 1)
        root.addWidget(editor, 0)

        # 格式变化时更新后缀并刷新默认文件名
        self.jpg_radio.toggled.connect(self.on_format_changed)
        self.png_radio.toggled.connect(self.on_format_changed)

        self.refresh_output_name()

        if parent is not None:
            self.resize(parent.size())

    # --------------------------------------------------------
    # 界面构建
    # --------------------------------------------------------

    def _build_resolution_row(self):
        """构建「分辨率」标题行与宽高输入行（含等比锁定）。"""

        box, layout = self._section("分辨率")

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(QLabel("宽"))
        self.width_edit = QLineEdit(str(self.source_size[0]))
        self.width_edit.setFixedWidth(90)
        row.addWidget(self.width_edit)

        self.lock_check = QCheckBox("等比")
        self.lock_check.setChecked(True)
        self.lock_check.setToolTip("勾选后修改宽或高，另一项按原始比例同步变化")
        row.addWidget(self.lock_check)

        row.addWidget(QLabel("高"))
        self.height_edit = QLineEdit(str(self.source_size[1]))
        self.height_edit.setFixedWidth(90)
        row.addWidget(self.height_edit)
        row.addStretch(1)
        layout.addLayout(row)

        layout.addWidget(self._hint(
            "取消等比后可分别设置宽高，左侧导出区域会同步改变长宽比。"
        ))

        self.lock_check.toggled.connect(self.on_lock_toggled)
        self.width_edit.textEdited.connect(self.on_width_edited)
        self.height_edit.textEdited.connect(self.on_height_edited)

        return box

    def _build_slice_row(self):
        """构建「切片」标题行与 X / Y 数量、间隔输入行。"""

        box, layout = self._section("切片")

        x_row = QHBoxLayout()
        x_row.setSpacing(8)
        x_row.addWidget(QLabel("X数量"))
        self.x_count_edit = QLineEdit("1")
        self.x_count_edit.setFixedWidth(70)
        self.x_count_edit.setValidator(QIntValidator(1, 99999, self))
        x_row.addWidget(self.x_count_edit)
        x_row.addWidget(QLabel("X间隔"))
        self.x_gap_edit = QLineEdit("0")
        self.x_gap_edit.setFixedWidth(70)
        self.x_gap_edit.setValidator(QIntValidator(0, 99999, self))
        x_row.addWidget(self.x_gap_edit)
        x_row.addWidget(QLabel("px"))
        x_row.addStretch(1)
        layout.addLayout(x_row)

        y_row = QHBoxLayout()
        y_row.setSpacing(8)
        y_row.addWidget(QLabel("Y数量"))
        self.y_count_edit = QLineEdit("1")
        self.y_count_edit.setFixedWidth(70)
        self.y_count_edit.setValidator(QIntValidator(1, 99999, self))
        y_row.addWidget(self.y_count_edit)
        y_row.addWidget(QLabel("Y间隔"))
        self.y_gap_edit = QLineEdit("0")
        self.y_gap_edit.setFixedWidth(70)
        self.y_gap_edit.setValidator(QIntValidator(0, 99999, self))
        y_row.addWidget(self.y_gap_edit)
        y_row.addWidget(QLabel("px"))
        y_row.addStretch(1)
        layout.addLayout(y_row)

        layout.addWidget(self._hint("数量≥1，间隔≥0（单位：px）；默认 1×1 即不切分。"))

        for edit in (self.x_count_edit, self.x_gap_edit,
                     self.y_count_edit, self.y_gap_edit):
            edit.textChanged.connect(self._refresh_slices)

        return box

    def _build_output_row(self):
        """构建「输出文件」标题行与输出文件夹 / 文件名选择行。"""

        box, layout = self._section("输出文件")

        folder_row = QHBoxLayout()
        folder_row.setSpacing(10)
        folder_row.addWidget(QLabel("文件夹"))
        self.folder_button = QPushButton(str(self.folder))
        self.folder_button.setToolTip("点击选择输出文件夹")
        set_button_role(self.folder_button, "field")
        self.folder_button.clicked.connect(self.choose_output_folder)
        folder_row.addWidget(self.folder_button, 1)
        layout.addLayout(folder_row)

        name_row = QHBoxLayout()
        name_row.setSpacing(10)
        name_row.addWidget(QLabel("文件名"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("文件名（不含后缀）")
        name_row.addWidget(self.name_edit, 1)

        self.suffix_label = QLabel(self.current_ext())
        self.suffix_label.setObjectName("Hint")
        self.suffix_label.setToolTip("后缀跟随目标格式，不可修改")
        name_row.addWidget(self.suffix_label)
        layout.addLayout(name_row)

        self.name_edit.textEdited.connect(self.on_name_edited)

        return box

    # --------------------------------------------------------
    # 交互 / 联动
    # --------------------------------------------------------

    def refresh_output_name(self):
        """
        重新计算默认文件名：{原文件名 + 冲突序号} + 后缀。

        仅在用户尚未手动修改过文件名时生效。
        """

        if self._name_edited:
            return

        stem = unique_stem(self.folder, self.source_stem, self.current_ext())
        self.name_edit.setText(stem)

    def choose_output_folder(self):
        """弹出文件夹选择窗口，更新输出文件夹并刷新默认文件名。"""

        folder = self._choose_folder()
        if folder is None:
            return

        self.folder = folder
        self.folder_button.setText(str(self.folder))
        self.refresh_output_name()

    def on_format_changed(self, checked=False):
        """切换目标格式时更新后缀显示，并刷新默认文件名。"""

        self.suffix_label.setText(self.current_ext())
        self.refresh_output_name()

    def on_name_edited(self, text):
        """记录用户已手动修改文件名，之后不再自动刷新。"""

        self._name_edited = True

    def on_lock_toggled(self, checked):
        """等比锁定：勾选时按原图比例同步高度。"""

        if checked:
            self._sync_other(self.width_edit.text(), self.height_edit,
                             width_to_height=True)
        self._refresh_output_size()

    def on_width_edited(self, text):
        """编辑宽度：等比时同步高度，随后刷新导出区域长宽比。"""

        if not self._syncing and self.lock_check.isChecked():
            self._sync_other(text, self.height_edit, width_to_height=True)
        self._refresh_output_size()

    def on_height_edited(self, text):
        """编辑高度：等比时同步宽度，随后刷新导出区域长宽比。"""

        if not self._syncing and self.lock_check.isChecked():
            self._sync_other(text, self.width_edit, width_to_height=False)
        self._refresh_output_size()

    def _sync_other(self, text, other, width_to_height):
        """按原始宽高比把另一输入框同步为等比值。"""

        try:
            value = int(text)
        except ValueError:
            return

        if value <= 0:
            return

        src_w, src_h = self.source_size
        self._syncing = True
        if width_to_height:
            other.setText(str(max(1, round(value * src_h / src_w))))
        else:
            other.setText(str(max(1, round(value * src_w / src_h))))
        self._syncing = False

    def _refresh_output_size(self):
        """把当前宽高同步给预览窗，用于调整导出区域的长宽比。"""

        try:
            width = int(self.width_edit.text())
            height = int(self.height_edit.text())
        except ValueError:
            return

        if width <= 0 or height <= 0:
            return

        self.preview.set_output_size(width, height)

    @staticmethod
    def _read_int(edit, default):
        """读取输入框中的整数，无法解析时返回默认值。"""

        try:
            return int(edit.text())
        except ValueError:
            return default

    def _refresh_slices(self):
        """把切片参数同步给预览窗以绘制切片线与间隔遮罩。"""

        self.preview.set_slices(
            self._read_int(self.x_count_edit, 1),
            self._read_int(self.x_gap_edit, 0),
            self._read_int(self.y_count_edit, 1),
            self._read_int(self.y_gap_edit, 0),
        )

    def on_coverage_changed(self, covered):
        """覆盖状态变化时，切换红字提示的显示。"""

        self.cover_warning.setVisible(not covered)

    def reset_all(self):
        """确认后撤销所有修改，恢复到刚导入、尚未编辑的状态。"""

        box = QMessageBox(self)
        box.setWindowTitle("提示")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText("是否确定要还原？还原后丢失所有修改内容。")
        btn_yes = box.addButton("还原", QMessageBox.ButtonRole.YesRole)
        box.addButton("取消", QMessageBox.ButtonRole.NoRole)
        set_button_role(btn_yes, "primary")
        box.setDefaultButton(btn_yes)
        box.exec()

        if box.clickedButton() is not btn_yes:
            return

        # 预览窗：撤销缩放 / 旋转 / 平移与导出区域、切分
        self.preview.reset()

        # 编辑窗：恢复各项输入
        self.width_edit.setText(str(self.source_size[0]))
        self.height_edit.setText(str(self.source_size[1]))
        self.lock_check.setChecked(True)
        self.x_count_edit.setText("1")
        self.x_gap_edit.setText("0")
        self.y_count_edit.setText("1")
        self.y_gap_edit.setText("0")
        self.jpg_radio.setChecked(True)
        self.suffix_label.setText(self.current_ext())
        self.size_edit.clear()
        self.folder = self.initial_folder
        self.folder_button.setText(str(self.folder))

        self._name_edited = False
        self.refresh_output_name()

        self._refresh_output_size()
        self._refresh_slices()

    # --------------------------------------------------------
    # 收集配置
    # --------------------------------------------------------

    def accept(self):
        """校验输入、渲染导出画面并收集配置，然后关闭窗口。"""

        options = {}

        # 目标格式
        options["format"], options["ext"] = self._collect_format()

        # 分辨率
        try:
            width = int(self.width_edit.text())
            height = int(self.height_edit.text())
        except ValueError:
            QMessageBox.warning(self, "提示", "分辨率请输入正整数。")
            return

        if width <= 0 or height <= 0:
            QMessageBox.warning(self, "提示", "分辨率请输入正整数。")
            return

        # 切片
        x_count = self._read_int(self.x_count_edit, 1)
        x_gap = self._read_int(self.x_gap_edit, 0)
        y_count = self._read_int(self.y_count_edit, 1)
        y_gap = self._read_int(self.y_gap_edit, 0)

        if x_count < 1 or y_count < 1 or x_gap < 0 or y_gap < 0:
            QMessageBox.warning(self, "提示", "切片数量需≥1，间隔需≥0。")
            return

        slice_w = (width - (x_count - 1) * x_gap) / x_count
        slice_h = (height - (y_count - 1) * y_gap) / y_count

        if slice_w < 1 or slice_h < 1:
            QMessageBox.warning(
                self, "提示", "切片间隔过大，单张尺寸不足 1px，请减小间隔或数量。"
            )
            return

        # 文件大小
        try:
            options["max_bytes"] = self._parse_max_bytes(self.size_edit.text())
        except ValueError:
            QMessageBox.warning(self, "提示", "文件大小请输入正数（MB）。")
            return

        # 输出文件
        stem = self.name_edit.text().strip()
        if not stem:
            QMessageBox.warning(self, "提示", "请输入文件名。")
            return
        if any(ch in stem for ch in '\\/:*?"<>|'):
            QMessageBox.warning(
                self, "提示", '文件名不能包含 \\ / : * ? " < > | 字符。'
            )
            return

        # 原图未完全覆盖输出图时，导出前额外确认
        if not self.preview.is_covered():
            box = QMessageBox(self)
            box.setWindowTitle("提示")
            box.setIcon(QMessageBox.Icon.Warning)
            box.setText(
                "原图未完全覆盖输出图。\n"
                "未覆盖区域将以黑色填充，是否仍要导出？"
            )
            btn_ok = box.addButton("仍然导出", QMessageBox.ButtonRole.YesRole)
            box.addButton("取消", QMessageBox.ButtonRole.NoRole)
            set_button_role(btn_ok, "primary")
            box.setDefaultButton(btn_ok)
            box.exec()
            if box.clickedButton() is not btn_ok:
                return

        # 渲染导出画面
        self.preview.set_output_size(width, height)
        image = self.preview.render_export()

        options["output_dir"] = str(self.folder)
        options["output_stem"] = stem
        options["image"] = image
        options["slices"] = (x_count, x_gap, y_count, y_gap)

        self.options = options
        super().accept()
