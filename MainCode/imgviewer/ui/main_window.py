# -*- coding: utf-8 -*-

"""
主窗口：选片助手工作台。

只负责界面组装、事件绑定与结果提示；
加载线程、拼接渲染、导出落盘、文件搬运均交由 services 处理。
"""

import gc
import re
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..constants import is_image_file
from ..image_io import load_image
from ..services import export_service, stitch_service, transfer_service
from ..services.loader_manager import LoaderManager
from ..theme import set_button_role
from .batch_export_dialog import BatchExportDialog
from .photo_view import PhotoView
from .single_export_dialog import SingleExportDialog


class MainWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("选片助手工作台")
        self.resize(1440, 920)

        self.folder = None

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(14, 14, 14, 10)
        layout.setSpacing(12)

        # ----------------------------------------------------
        # 工具栏（放入圆角面板，形成现代「工作台」观感）
        # ----------------------------------------------------

        panel = QFrame()
        panel.setObjectName("Panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(14, 14, 14, 14)
        panel_layout.setSpacing(10)

        # 第一行：打开 / 路径 / 文件名 / 匹配 / 全选 / 全不选
        top = QHBoxLayout()
        top.setSpacing(8)

        self.open_btn = QPushButton("打开文件夹")
        set_button_role(self.open_btn, "primary")
        self.open_btn.clicked.connect(self.open_folder)
        top.addWidget(self.open_btn)

        self.path_label = QLabel("未选择文件夹")
        self.path_label.setObjectName("PathLabel")
        self.path_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        top.addWidget(self.path_label)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(
            "输入文件名或片段，英文/中文逗号分隔"
        )
        self.name_edit.returnPressed.connect(self.match_names)
        top.addWidget(self.name_edit, 2)

        for text, slot in (
            ("匹配文件名 (Enter)", self.match_names),
            ("全选 (Ctrl+A)", self.select_all),
            ("全不选 (Esc)", self.deselect_all),
        ):
            button = QPushButton(text)
            button.clicked.connect(slot)
            top.addWidget(button)

        panel_layout.addLayout(top)

        # 第二行：复制 / 移动 / 回收站 / 拼接导出
        second = QHBoxLayout()
        second.setSpacing(8)

        for text, slot, role in (
            ("复制到新筛选文件夹", self.copy_to_new_folder, None),
            ("复制到指定文件夹 (Ctrl+C)", self.copy_to_folder, None),
            ("移动到新筛选文件夹", self.move_to_new_folder, None),
            ("移动到指定文件夹 (Ctrl+X)", self.move_to_folder, None),
            ("移动到回收站 (Del / Backspace)", self.move_to_recycle_bin, "danger"),
            ("导出拼接缩略图 (Ctrl+S)", self.stitch_selected, None),
            ("图片调整导出 (Ctrl+Shift+S)", self.image_adjust_export, "primary"),
        ):
            button = QPushButton(text)
            if role:
                set_button_role(button, role)
            button.clicked.connect(slot)
            second.addWidget(button)

        second.addStretch(1)

        panel_layout.addLayout(second)

        layout.addWidget(panel)

        hint = QLabel(
            "Ctrl + 滚轮：缩放；普通滚轮：滚动；横向滚轮：左右移动；"
            "Shift + 点击：范围选择；点击图片任意位置：勾选/取消；"
        )
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # ----------------------------------------------------
        # 图片视图
        # ----------------------------------------------------

        self.view = PhotoView()
        self.loaders = LoaderManager(self.view, self)

        self.loaders.statusMessage.connect(self.statusBar().showMessage)
        self.view.checkedChanged.connect(self.sync_checked_to_edit)
        self.view.visibleRangeChanged.connect(self.loaders.load_visible)
        self.view.visibleRangeChanged.connect(self.loaders.load_hq)
        layout.addWidget(self.view, 1)

        # ----------------------------------------------------
        # 快捷键
        # Ctrl+A / Esc：全选 / 全不选
        # Ctrl+S：导出拼接缩略图
        # Ctrl+C / Ctrl+X：复制 / 移动到指定文件夹
        # Del / Backspace：移动到回收站（仅图片视图聚焦时）
        # ----------------------------------------------------

        self._shortcuts = []

        for keys, slot, widget in (
            ("Ctrl+A", self.select_all, self),
            ("Esc", self.deselect_all, self),
            ("Ctrl+S", self.stitch_selected, self),
            ("Ctrl+Shift+S", self.image_adjust_export, self),
            ("Ctrl+C", self.copy_to_folder, self),
            ("Ctrl+X", self.move_to_folder, self),
            ("Del", self.move_to_recycle_bin, self.view),
            ("Backspace", self.move_to_recycle_bin, self.view),
        ):
            shortcut = QShortcut(QKeySequence(keys), widget)
            if widget is self.view:
                shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
            shortcut.activated.connect(slot)
            self._shortcuts.append(shortcut)

        self.statusBar().showMessage("请选择一个图片文件夹")

    # --------------------------------------------------------
    # 文件加载
    # --------------------------------------------------------

    def open_folder(self):

        start = self.folder if self.folder is not None else Path.home()
        folder = QFileDialog.getExistingDirectory(
            self, "选择图片文件夹", str(start)
        )
        if folder:
            self.load_folder(Path(folder))

    def load_folder(self, folder: Path):

        self.loaders.stop()

        files = sorted(
            (p for p in folder.iterdir() if p.is_file() and is_image_file(p)),
            key=lambda p: p.name.lower(),
        )

        self.folder = folder
        self.path_label.setText(str(folder))
        self.path_label.setToolTip(str(folder))
        self.view.set_files([str(p) for p in files])
        self.name_edit.clear()

        # 显式触发垃圾回收，尽快释放被淘汰图片占用的内存
        gc.collect()

        print("=" * 72)
        print(f"[文件夹] {folder}")
        print(f"[总计] {len(files)} 张图片")
        print("=" * 72, flush=True)

        if not files:
            self.statusBar().showMessage("该文件夹中没有支持的图片")
            return

        self.statusBar().showMessage(f"共 {len(files)} 张图片，正在按需读取")
        self.loaders.load_visible(*self.view.visible_range())

    # --------------------------------------------------------
    # 勾选 / 匹配
    # --------------------------------------------------------

    def match_names(self):

        if not self.view.paths:
            return

        tokens = [
            t.strip()
            for t in re.split(r"[,，]", self.name_edit.text())
            if t.strip()
        ]

        if not tokens:
            self.name_edit.clear()
            self.view.checked.clear()
            self.view.viewport().update()
            return

        names = [Path(p).name.lower() for p in self.view.paths]
        used, matched = set(), []

        # 每个 token：完整文件名优先，其次文件名包含
        for token in tokens:
            token = token.lower()
            candidates = [i for i, n in enumerate(names) if i not in used and n == token]
            if not candidates:
                candidates = [i for i, n in enumerate(names) if i not in used and token in n]
            if candidates:
                used.add(candidates[0])
                matched.append(candidates[0])

        self.view.checked = set(matched)
        self.view.last_clicked_index = matched[-1] if matched else None
        self.name_edit.setText(
            ",".join(Path(self.view.paths[i]).name for i in matched)
        )
        self.view.viewport().update()

        print(f"[匹配] 输入 {len(tokens)} 项，成功匹配 {len(matched)} 项", flush=True)

    def sync_checked_to_edit(self):

        names = [Path(self.view.paths[i]).name for i in sorted(self.view.checked)]
        self.name_edit.setText(",".join(names))

    def select_all(self):
        """勾选当前文件夹中的所有图片。"""

        if not self.view.paths:
            return

        self.view.checked = set(range(len(self.view.paths)))
        self.view.last_clicked_index = len(self.view.paths) - 1
        self.view.viewport().update()
        self.sync_checked_to_edit()

    def deselect_all(self):
        """取消所有勾选。"""

        self.view.checked.clear()
        self.view.last_clicked_index = None
        self.view.viewport().update()
        self.sync_checked_to_edit()

    # --------------------------------------------------------
    # 导出拼接缩略图
    # --------------------------------------------------------

    def stitch_selected(self):
        """
        把选中的图片按当前缩放档位的列数拼接成一张总宽 3840 的大图：
        每格为一张缩略图并带文件名，高度随行数自然增长。
        放大显示时列数为 1，即每行只有一张。
        """

        indices = self._require_selection()

        if not indices:
            return

        # 当前档位的一行列数（放大显示时为 1）
        columns = self.view.columns()

        def get_image(index):
            image = self.view.hq_images.get(index)
            if image is None:
                image = self.view.images.get(index)
            return image

        canvas, width, height, failed = stitch_service.render_stitch(
            self.view.paths, indices, columns, get_image
        )

        if canvas is None:
            QMessageBox.warning(
                self,
                "提示",
                f"拼接图尺寸过大（{width} × {height}）。\n"
                "请减少选中数量，或先缩小到列数更多的档位再导出。",
            )
            return

        # 默认文件名：<当前文件夹名>_缩略图_<时间戳>
        if self.folder is not None:
            base = self.folder
            prefix = base.name
        else:
            base = Path.home()
            prefix = "拼接"

        default = base / f"{prefix}_缩略图_{datetime.now():%Y%m%d_%H%M%S}.png"

        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存拼接缩略图",
            str(default),
            "PNG (*.png);;JPEG (*.jpg *.jpeg)",
        )

        if not path:
            return

        if not canvas.save(path):
            QMessageBox.warning(self, "提示", "保存图片失败。")
            return

        message = f"已导出 {len(indices)} 张缩略图（{columns} 列）到：\n{path}"
        if failed:
            message += f"\n\n其中 {failed} 张读取失败。"

        QMessageBox.information(self, "拼接完成", message)
        self.statusBar().showMessage(
            f"拼接完成：{len(indices)} 张 -> {Path(path).name}"
        )

    # --------------------------------------------------------
    # 图片调整导出
    # --------------------------------------------------------

    def image_adjust_export(self):
        """
        「图片调整导出」入口：按选中数量分流。

        仅选中 1 张：弹出可视化编辑弹窗（可缩放 / 旋转 / 移动 / 切片）；
        选中多张：弹出批量导出弹窗（按长边像素等比缩放）。
        """

        if self.folder is None:
            QMessageBox.warning(self, "提示", "请先打开图片文件夹。")
            return

        indices = self._require_selection()

        if not indices:
            return

        if len(indices) == 1:
            self._export_single(indices[0])
        else:
            self._export_batch(indices)

    def _report_export(self, count, failed, target_dir):
        """统一弹出导出结果提示并更新状态栏。"""

        message = f"已导出 {count} 张图片到：\n{target_dir}"
        if failed:
            message += "\n\n以下文件失败：\n" + "\n".join(
                f"{name}：{error}" for name, error in failed[:10]
            )

        QMessageBox.information(self, "导出完成", message)
        self.statusBar().showMessage(f"导出完成：{count} 张 -> {target_dir.name}")

    def _export_single(self, index):
        """单张图片：可视化编辑后按需切片导出。"""

        path = self.view.paths[index]
        source_stem = Path(path).stem

        try:
            image = load_image(path, full=True)
        except Exception as e:
            QMessageBox.warning(self, "提示", f"读取图片失败：\n{e}")
            return

        dialog = SingleExportDialog(image, source_stem, self.folder, self)

        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.options is None:
            return

        options = dialog.options

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        try:
            count, failed, target_dir = export_service.export_single_slices(
                options["image"], options, source_stem
            )
        finally:
            QApplication.restoreOverrideCursor()

        self._report_export(count, failed, target_dir)

    def _export_batch(self, indices):
        """多张图片：按长边像素等比缩放导出。"""

        dialog = BatchExportDialog(len(indices), self.folder, self)

        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.options is None:
            return

        options = dialog.options

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        try:
            count, failed, target_dir = export_service.export_batch(
                self.view.paths, indices, options
            )
        finally:
            QApplication.restoreOverrideCursor()

        self._report_export(count, failed, target_dir)

    # --------------------------------------------------------
    # 文件搬运
    # --------------------------------------------------------

    def selected_indices(self):

        self.match_names()
        return sorted(self.view.checked)

    def _require_selection(self):
        """返回选中的索引列表；无选择时提示用户并返回空列表。"""

        indices = self.selected_indices()

        if not indices:
            QMessageBox.information(self, "提示", "没有匹配到任何文件。")

        return indices

    def _after_transfer(self, title, message, status, success, reload=False):

        QMessageBox.information(self, title, message)
        self.statusBar().showMessage(status)

        # 成功后取消所有勾选并清空输入框
        if success:
            self.view.checked.clear()
            self.view.last_clicked_index = None
            self.name_edit.clear()
            self.view.viewport().update()

        # 移动成功后刷新列表（源文件已不在原文件夹）
        if reload and self.folder is not None:
            self.load_folder(self.folder)

    def _collect(self, move):
        """收集待处理文件，返回 (indices, sources, verb)，无有效选择时返回 None。"""

        indices = self._require_selection()

        if not indices:
            return None

        sources = [self.view.paths[i] for i in indices]
        return indices, sources, ("移动" if move else "复制")

    def _transfer_to_new_folder(self, move):
        """复制 / 移动到新建的「筛选_xx」文件夹。"""

        if self.folder is None:
            QMessageBox.warning(self, "提示", "请先打开图片文件夹。")
            return

        collected = self._collect(move)
        if collected is None:
            return

        indices, sources, verb = collected

        target, count, failed = transfer_service.transfer_to_new_folder(
            self.folder, sources, move
        )

        message = f"已{verb} {count} 个文件到：\n{target}"
        if failed:
            message += f"\n\n失败 {len(failed)} 个。"

        self._after_transfer(
            f"{verb}完成",
            message,
            f"{verb}完成：{count} 个文件 -> {target.name}",
            count > 0,
            reload=move,
        )

    def _transfer_to_folder(self, move):
        """复制 / 移动到指定文件夹（优先系统原生操作）。"""

        collected = self._collect(move)
        if collected is None:
            return

        _, sources, verb = collected

        start = self.folder if self.folder is not None else Path.home()
        target = QFileDialog.getExistingDirectory(
            self, f"选择要{verb}到的文件夹", str(start)
        )
        if not target:
            return

        outcome = transfer_service.transfer_to_folder(
            self, sources, target, move
        )

        if not outcome.native:

            if outcome.count == 0 and outcome.skipped == 0:
                QMessageBox.warning(self, "提示", f"{verb}未完成。")
                return

            message = f"已{verb} {outcome.count} 个文件到：\n{target}"
            if outcome.skipped:
                message += f"\n\n跳过 {outcome.skipped} 个。"
            if outcome.failed:
                message += f"\n\n失败 {len(outcome.failed)} 个。"

            self._after_transfer(
                f"{verb}完成",
                message,
                f"{verb}完成：{outcome.count} 个文件 -> {Path(target).name}",
                True,
                reload=move,
            )
            return

        self._after_transfer(
            f"{verb}完成",
            f"{verb}操作已完成。\n目标文件夹：\n{target}",
            f"{verb}完成 -> {target}",
            True,
            reload=move,
        )

    def move_to_recycle_bin(self):
        """将选中文件移动到回收站（需确认）。"""

        indices = self._require_selection()

        if not indices:
            return

        # 默认「是」，回车即选择「是」
        box = QMessageBox(self)
        box.setWindowTitle("移动到回收站")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(f"确定将选中的 {len(indices)} 个文件移动到回收站吗？")
        btn_yes = box.addButton("确定", QMessageBox.ButtonRole.YesRole)
        box.addButton("取消", QMessageBox.ButtonRole.NoRole)
        set_button_role(btn_yes, "primary")
        box.setDefaultButton(btn_yes)
        box.exec()

        if box.clickedButton() is not btn_yes:
            return

        sources = [self.view.paths[i] for i in indices]

        if not transfer_service.recycle_files(sources):
            QMessageBox.warning(self, "提示", "移动到回收站未完成。")
            return

        self._after_transfer(
            "已移动到回收站",
            f"已将 {len(sources)} 个文件移动到回收站。",
            f"已移动到回收站：{len(sources)} 个文件",
            True,
            reload=True,
        )

    # --------------------------------------------------------
    # 四个按钮的入口
    # --------------------------------------------------------

    def copy_to_new_folder(self):
        self._transfer_to_new_folder(move=False)

    def move_to_new_folder(self):
        self._transfer_to_new_folder(move=True)

    def copy_to_folder(self):
        self._transfer_to_folder(move=False)

    def move_to_folder(self):
        self._transfer_to_folder(move=True)

    # --------------------------------------------------------
    # 关闭
    # --------------------------------------------------------

    def closeEvent(self, event):
        self.loaders.stop()
        event.accept()
