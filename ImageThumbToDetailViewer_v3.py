#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
选片助手工作台（ImageThumbToDetailViewer v3）

Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International
Public License (CC BY-NC-SA 4.0)

SPDX-License-Identifier: CC-BY-NC-SA-4.0

Copyright (c) 2026 MioSleet(澪霰)

本作品（选片助手工作台 / ImageThumbToDetailViewer）采用 CC BY-NC-SA 4.0 协议授权：
署名、非商业性使用、相同方式共享。

依赖：
    pip install PySide6 Pillow rawpy

支持格式（普通图片）：
    JPG/JPEG/PNG/BMP/GIF/TIF/TIFF/WEBP

支持格式（RAW）：
    ARW/CR2/CR3/NEF/NRW/DNG/RAF/RW2/ORF/PEF/SR2/SRF
    3FR/ERF/KDC/MRW/RAW/RWL/X3F/IIQ/MOS/MEF/ARI

运行：
    python ImageThumbToDetailViewer_v3.py
"""

import ctypes
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps
import rawpy

from PySide6.QtCore import Qt, QObject, QPoint, QRect, QSize, QThread, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QKeySequence,
    QPainter,
    QPen,
    QShortcut,
)
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QFileDialog,
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


# ============================================================
# 支持的图片格式
# ============================================================

RAW_EXTS = {
    ".arw", ".cr2", ".cr3", ".nef", ".nrw", ".dng", ".raf", ".rw2",
    ".orf", ".pef", ".sr2", ".srf", ".3fr", ".erf", ".kdc", ".mrw",
    ".raw", ".rwl", ".x3f", ".iiq", ".mos", ".mef", ".ari",
}

COMMON_EXTS = {
    ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp",
}

IMAGE_EXTS = COMMON_EXTS | RAW_EXTS


def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS


# ============================================================
# 系统原生文件操作（复制 / 移动 / 送入回收站）
#
# 借助 Windows 自带的文件操作，遇到同名文件时
# 会弹出系统原生的冲突对话框，由用户选择如何处理。
# ============================================================

FO_MOVE = 0x0001
FO_COPY = 0x0002
FO_DELETE = 0x0003

FOF_SILENT = 0x0004
FOF_NOCONFIRMATION = 0x0010
FOF_ALLOWUNDO = 0x0040          # 删除时送入回收站
FOF_NOCONFIRMMKDIR = 0x0200
FOF_NOERRORUI = 0x0400

try:
    from ctypes import wintypes as _wt

    class _SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", _wt.HWND),
            ("wFunc", _wt.UINT),
            ("pFrom", _wt.LPCWSTR),
            ("pTo", _wt.LPCWSTR),
            ("fFlags", ctypes.c_uint16),
            ("fAnyOperationsAborted", _wt.BOOL),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", _wt.LPCWSTR),
        ]
except Exception:
    _SHFILEOPSTRUCTW = None


def _shell_operation(wfunc, sources, destination, flags):
    """
    调用 SHFileOperationW。

    destination 为 None 表示不需要目标路径（例如删除）。
    返回 (result, aborted)，result == 0 表示成功。
    """

    if _SHFILEOPSTRUCTW is None:
        raise RuntimeError("当前系统不支持原生文件操作")

    # pFrom / pTo 需要以双 \0 结尾
    p_from = "\0".join(os.path.abspath(str(s)) for s in sources) + "\0\0"
    p_to = None if destination is None else os.path.abspath(str(destination)) + "\0\0"

    op = _SHFILEOPSTRUCTW()
    op.hwnd = None
    op.wFunc = wfunc
    op.pFrom = p_from
    op.pTo = p_to
    op.fFlags = flags
    op.fAnyOperationsAborted = False
    op.hNameMappings = None
    op.lpszProgressTitle = None

    func = ctypes.windll.shell32.SHFileOperationW
    func.argtypes = [ctypes.POINTER(_SHFILEOPSTRUCTW)]
    func.restype = ctypes.c_int
    result = func(ctypes.byref(op))

    print(f"[原生文件操作] wFunc={wfunc} result={result} "
          f"aborted={bool(op.fAnyOperationsAborted)}", flush=True)

    return result, bool(op.fAnyOperationsAborted)


def shell_file_operation(wfunc, sources, destination):
    """复制 / 移动到指定文件夹。"""
    return _shell_operation(wfunc, sources, destination, FOF_NOCONFIRMMKDIR)


def shell_delete_to_recycle_bin(sources):
    """移动到回收站（系统确认框由程序自己弹出，故此处抑制）。"""
    return _shell_operation(
        FO_DELETE,
        sources,
        None,
        FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI,
    )


def powershell_recycle(paths):
    """
    备用方案：通过 PowerShell 的 Microsoft.VisualBasic
    将文件移动到回收站。返回进程退出码，0 表示成功。
    """

    import subprocess

    joined = ",".join("'" + str(p).replace("'", "''") + "'" for p in paths)
    script = (
        "Add-Type -AssemblyName Microsoft.VisualBasic; "
        f"@({joined}) | ForEach-Object {{ "
        "[Microsoft.VisualBasic.FileIO.FileSystem]::"
        "DeleteFile($_, 'OnlyErrorDialogs', 'SendToRecycleBin') }"
    )

    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
    )
    return proc.returncode


# ============================================================
# 图片读取
# ============================================================

def pil_to_qimage(im: Image.Image) -> QImage:
    """Pillow -> QImage。copy() 使 QImage 脱离 Pillow 的内存生命周期。"""

    im = ImageOps.exif_transpose(im)
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGB")

    if im.mode == "RGBA":
        data = im.tobytes("raw", "RGBA")
        return QImage(data, im.width, im.height, im.width * 4,
                      QImage.Format.Format_RGBA8888).copy()

    data = im.tobytes("raw", "RGB")
    return QImage(data, im.width, im.height, im.width * 3,
                  QImage.Format.Format_RGB888).copy()


def raw_to_pil(path: str, full: bool = False) -> Image.Image:
    """
    RAW 读取。

    full=False：优先用内嵌缩略图，否则 half_size 解码（快，用于网格预览）。
    full=True ：跳过缩略图，完整分辨率解码（最高画质，用于单图模式）。
    """

    with rawpy.imread(path) as raw:

        if not full:
            try:
                thumb = raw.extract_thumb()
                if thumb.format == rawpy.ThumbFormat.JPEG:
                    from io import BytesIO
                    return Image.open(BytesIO(thumb.data)).convert("RGB")
                if thumb.format == rawpy.ThumbFormat.BITMAP:
                    return Image.fromarray(thumb.data).convert("RGB")
            except Exception:
                pass

        rgb = raw.postprocess(
            use_camera_wb=True,
            half_size=not full,
            no_auto_bright=False,
            output_bps=8,
        )
        return Image.fromarray(rgb).convert("RGB")


def load_image(path: str, full: bool = False) -> QImage:
    if Path(path).suffix.lower() in RAW_EXTS:
        return pil_to_qimage(raw_to_pil(path, full=full))
    with Image.open(path) as im:
        return pil_to_qimage(im.copy())


# ============================================================
# 后台图片读取线程
# ============================================================

class ImageLoader(QObject):

    loaded = Signal(int, QImage)
    failed = Signal(int, str)
    finished = Signal()

    def __init__(self, full=False):
        super().__init__()
        self._queue = []
        self._running = True
        self._full = full

    def set_queue(self, queue):
        self._queue = list(queue)

    def stop(self):
        self._running = False

    def run(self):

        total = len(self._queue)

        for n, (index, path) in enumerate(self._queue, 1):

            if not self._running:
                break

            name = Path(path).name

            try:
                print(f"[读取] {n}/{total}  {name}", flush=True)
                image = load_image(path, full=self._full)
                self.loaded.emit(index, image)
                print(f"[显示] {n}/{total}  {name}", flush=True)

            except Exception as e:
                message = f"{type(e).__name__}: {e}"
                print(f"[失败] {n}/{total}  {name} -> {message}", flush=True)
                self.failed.emit(index, message)

        self.finished.emit()


# ============================================================
# 图片虚拟显示区域
# ============================================================

class PhotoView(QAbstractScrollArea):

    checkedChanged = Signal()
    visibleRangeChanged = Signal(int, int)

    # 缩放档位：0.10~0.255 为多列网格，0.31 / 0.47 / 0.58 为 3/2/1 列，
    # 0.58 之后为单图放大。
    ZOOM_LEVELS = [
        0.10, 0.12, 0.145, 0.175, 0.21, 0.255,
        0.31, 0.47, 0.58,
        0.82, 1.00, 1.25, 1.55, 1.90, 2.40, 3.00, 4.00,
    ]

    def __init__(self, parent=None):

        super().__init__(parent)
        self.setFrameShape(QAbstractScrollArea.Shape.NoFrame)
        self.setBackgroundRole(self.palette().ColorRole.Base)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.paths = []            # 文件路径
        self.checked = set()       # 勾选的 index
        self.images = {}           # 预览图
        self.errors = {}           # 读取失败信息
        self.hq_images = {}        # 单图模式的完整画质图
        self.hq_failed = set()     # 完整画质读取失败
        self.zoom_index = 0
        self.min_columns = 10
        self.max_cache = 80
        self.last_clicked_index = None
        self._last_visible = (-1, -1)

        # 列表最前端的占位格数量（用于缩放时的横向微调，取值 0 ~ 列数-1）
        self.placeholder = 0

        self.verticalScrollBar().valueChanged.connect(self.viewport().update)
        self.horizontalScrollBar().valueChanged.connect(self.viewport().update)

    # --------------------------------------------------------
    # 缩放 / 尺寸
    # --------------------------------------------------------

    @property
    def zoom(self):
        return self.ZOOM_LEVELS[self.zoom_index]

    def columns(self):

        if self.zoom >= 0.55:
            return 1
        if 0.30 <= self.zoom < 0.40:
            return 3
        if 0.40 <= self.zoom < 0.55:
            return 2
        return max(1, round(self.min_columns / (self.zoom / 0.10)))

    def tile_size(self):
        """单个图片格子的边长（宽度与高度相同）。"""

        columns = self.columns()
        if columns == 1:
            return max(1, int(self.viewport().width() * self.zoom))
        return max(1, self.viewport().width() // columns)

    def content_size(self):

        columns = self.columns()
        size = self.tile_size()
        total = len(self.paths) + self.placeholder
        rows = (total + columns - 1) // columns if total else 0
        return QSize(max(1, columns * size), max(1, rows * size))

    def _update_scrollbars(self):

        size = self.content_size()
        width, height = self.viewport().width(), self.viewport().height()

        self.horizontalScrollBar().setRange(0, max(0, size.width() - width))
        self.verticalScrollBar().setRange(0, max(0, size.height() - height))
        self.horizontalScrollBar().setPageStep(width)
        self.verticalScrollBar().setPageStep(height)

    # --------------------------------------------------------
    # 数据
    # --------------------------------------------------------

    def set_files(self, paths):

        self.paths = paths
        self.images.clear()
        self.errors.clear()
        self.checked.clear()
        self.hq_images.clear()
        self.hq_failed.clear()
        self.zoom_index = 0
        self.last_clicked_index = None
        self.placeholder = 0

        self._update_scrollbars()
        self.viewport().update()

    def _store_cached(self, cache, index, image, limit):
        """写入缓存并淘汰离可视中心最远的一张。"""

        cache[index] = image

        if len(cache) > limit:
            lo, hi = self.visible_range()
            center = (lo + hi) // 2 if lo <= hi else 0
            farthest = max(cache, key=lambda i: abs(i - center))
            if farthest != index:
                cache.pop(farthest, None)

        self.viewport().update()

    def set_image(self, index, image):
        self._store_cached(self.images, index, image, self.max_cache)

    def set_error(self, index, error):
        self.errors[index] = error
        self.viewport().update()

    def set_hq_image(self, index, image):
        self._store_cached(self.hq_images, index, image, 3)

    # --------------------------------------------------------
    # 布局
    # --------------------------------------------------------

    def visible_range(self):

        if not self.paths:
            return 0, -1

        columns = self.columns()
        tile = max(1, self.tile_size())
        top = self.verticalScrollBar().value()
        bottom = top + self.viewport().height()

        total = len(self.paths) + self.placeholder
        total_rows = (total + columns - 1) // columns

        first_row = max(0, top // tile - 1)
        last_row = min(total_rows - 1, bottom // tile + 1)

        # 位置 -> index（占位格占据最前面的若干位置，故需减去占位格数量）
        first_index = max(0, first_row * columns - self.placeholder)
        first_index = min(first_index, len(self.paths) - 1)
        last_index = min(
            len(self.paths) - 1,
            (last_row + 1) * columns - 1 - self.placeholder,
        )

        return first_index, last_index

    def _tile_rect(self, index):

        columns = self.columns()
        size = self.tile_size()
        row, column = divmod(index + self.placeholder, columns)
        return QRect(column * size, row * size, size, size)

    def index_at(self, pos):

        size = self.tile_size()
        if size <= 0:
            return None

        x = pos.x() + self.horizontalScrollBar().value()
        y = pos.y() + self.verticalScrollBar().value()
        position = (y // size) * self.columns() + (x // size)
        index = position - self.placeholder

        return index if 0 <= index < len(self.paths) else None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scrollbars()
        self.viewport().update()

    # --------------------------------------------------------
    # 交互
    # --------------------------------------------------------

    def mousePressEvent(self, event):

        if event.button() == Qt.MouseButton.LeftButton:

            index = self.index_at(event.position().toPoint())

            if index is not None:

                shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)

                if shift and self.last_clicked_index is not None:
                    start, end = sorted((self.last_clicked_index, index))
                    self.checked.update(range(start, end + 1))
                elif index in self.checked:
                    self.checked.discard(index)
                else:
                    self.checked.add(index)

                self.last_clicked_index = index
                self.checkedChanged.emit()
                self.viewport().update()
                event.accept()
                return

        super().mousePressEvent(event)

    @staticmethod
    def _wheel_step(delta):
        """滚轮增量 -> 像素移动量。"""
        if abs(delta) >= 120:
            return 45 * max(1, abs(delta) // 120)
        return max(10, abs(delta) // 2)

    def wheelEvent(self, event):

        # ====================================================
        # Ctrl + 滚轮：缩放
        #
        # 以鼠标所指的图片为锚点：通过上下滚动 + 在最前端插入占位格
        # （相当于横向移动），使缩放前鼠标下的那张图缩放后仍在鼠标下。
        # ====================================================

        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:

            delta = event.angleDelta().y()
            if delta == 0:
                event.accept()
                return

            old_index = self.zoom_index
            old_columns = self.columns()
            old_tile = max(1, self.tile_size())
            old_placeholder = self.placeholder
            old_scroll_x = self.horizontalScrollBar().value()
            old_scroll_y = self.verticalScrollBar().value()

            mouse = event.position().toPoint()
            old_content_x = old_scroll_x + mouse.x()

            # 鼠标在图片格内的纵向相对位置（缩放后按比例保持）
            offset_ratio = ((old_scroll_y + mouse.y()) % old_tile) / old_tile

            # 鼠标当前所指的图片（落在占位格上则为 None）
            anchor = self.index_at(mouse)

            step = 1 if delta > 0 else -1
            self.zoom_index = max(0, min(len(self.ZOOM_LEVELS) - 1, self.zoom_index + step))

            if self.zoom_index != old_index:

                old_zoom = self.ZOOM_LEVELS[old_index]
                new_zoom = self.zoom
                new_columns = self.columns()
                new_tile = max(1, self.tile_size())

                if anchor is not None:

                    # 鼠标所在列
                    column = min(max(mouse.x() // new_tile, 0), new_columns - 1)

                    # 占位格数量：让 anchor 恰好落在鼠标所在列；
                    # 超过一行的部分整行去掉，避免出现纯占位的空行
                    placeholder = (column - anchor) % new_columns

                    # anchor 加上占位格后的行
                    row = (anchor + placeholder) // new_columns

                    # 目标滚动位置：保持鼠标在格内的相对偏移
                    target_y = row * new_tile + int(offset_ratio * new_tile) - mouse.y()

                    # 已在最上端仍要向上 → 去掉所有占位格
                    if old_scroll_y == 0 and target_y < 0:
                        placeholder = 0
                        target_y = 0

                    self.placeholder = placeholder
                    self._update_scrollbars()
                    self.verticalScrollBar().setValue(
                        max(0, min(self.verticalScrollBar().maximum(), target_y))
                    )

                    # 多列模式横向由占位格决定；单列模式保持鼠标横向锚点
                    if new_columns == 1 and old_zoom != 0:
                        new_x = int(old_content_x * (new_zoom / old_zoom) - mouse.x())
                        self.horizontalScrollBar().setValue(
                            max(0, min(self.horizontalScrollBar().maximum(), new_x))
                        )
                    else:
                        self.horizontalScrollBar().setValue(0)

                else:

                    # 鼠标不在图片上：沿用「第一张图保持第一行」
                    first_index = max(
                        0, (old_scroll_y // old_tile) * old_columns - old_placeholder
                    )
                    if self.paths:
                        first_index = min(first_index, len(self.paths) - 1)

                    self.placeholder = 0
                    self._update_scrollbars()

                    target_y = (first_index // new_columns) * new_tile
                    target_y = min(target_y, self.verticalScrollBar().maximum())
                    target_y = (target_y // new_tile) * new_tile
                    self.verticalScrollBar().setValue(target_y)

                    if old_zoom != 0:
                        new_x = int(old_content_x * (new_zoom / old_zoom) - mouse.x())
                        self.horizontalScrollBar().setValue(
                            max(0, min(self.horizontalScrollBar().maximum(), new_x))
                        )

                self.viewport().update()

            event.accept()
            return

        # ====================================================
        # 普通滚轮：滚动
        #
        # 单图模式小幅滚动，多图模式每次一行。
        # ====================================================

        vertical_delta = event.angleDelta().y()
        horizontal_delta = event.angleDelta().x()
        pixel = event.pixelDelta()

        if vertical_delta == 0:
            vertical_delta = pixel.y()
        if horizontal_delta == 0:
            horizontal_delta = pixel.x()

        # 已在最上端仍向上滚动 → 去掉所有占位格
        if (
            vertical_delta > 0
            and self.placeholder > 0
            and self.verticalScrollBar().value() == 0
        ):
            self.placeholder = 0
            self._update_scrollbars()

        if vertical_delta != 0:

            if self.columns() == 1:
                move = self._wheel_step(vertical_delta)
            else:
                move = self.tile_size() * max(1, abs(vertical_delta) // 120)

            bar = self.verticalScrollBar()
            bar.setValue(bar.value() + (-1 if vertical_delta > 0 else 1) * move)

        if horizontal_delta != 0:
            move = self._wheel_step(horizontal_delta)
            bar = self.horizontalScrollBar()
            bar.setValue(bar.value() + (-1 if horizontal_delta > 0 else 1) * move)

        event.accept()

    # --------------------------------------------------------
    # 绘制
    # --------------------------------------------------------

    def paintEvent(self, event):

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.fillRect(self.viewport().rect(), QColor(25, 25, 25))

        lo, hi = self.visible_range()

        if (lo, hi) != self._last_visible:
            self._last_visible = (lo, hi)
            self.visibleRangeChanged.emit(lo, hi)

        if hi < lo:
            painter.end()
            return

        painter.translate(
            -self.horizontalScrollBar().value(),
            -self.verticalScrollBar().value(),
        )

        single = self.columns() == 1

        for i in range(lo, hi + 1):
            self._paint_tile(painter, i, single)

        painter.end()

    def _paint_tile(self, painter, index, single):

        rect = self._tile_rect(index)

        # 单图模式优先使用完整画质图片
        image = self.hq_images.get(index) if single else None
        if image is None:
            image = self.images.get(index)

        if image is not None and not image.isNull():

            scaled = image.scaled(
                rect.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawImage(
                QPoint(
                    rect.left() + (rect.width() - scaled.width()) // 2,
                    rect.top() + (rect.height() - scaled.height()) // 2,
                ),
                scaled,
            )

        elif index in self.errors:

            painter.fillRect(rect, QColor(75, 25, 25))
            painter.setPen(QColor(255, 150, 150))
            painter.drawText(
                rect.adjusted(8, 8, -8, -8),
                Qt.AlignmentFlag.AlignCenter,
                "读取失败\n" + Path(self.paths[index]).name,
            )

        else:

            painter.fillRect(rect, QColor(40, 40, 40))
            painter.setPen(QColor(140, 140, 140))
            painter.drawText(
                rect.adjusted(5, 5, -5, -5),
                Qt.AlignmentFlag.AlignCenter,
                "读取中…",
            )

        box = QRect(rect.left() + 7, rect.bottom() - 31, 24, 24)
        self._paint_checkbox(painter, index, box)
        self._paint_filename(painter, index, rect, box)

    def _paint_checkbox(self, painter, index, box):

        painter.setPen(QPen(QColor(235, 235, 235), 2))
        painter.setBrush(QBrush(QColor(35, 35, 35, 190)))
        painter.drawRect(box)

        if index in self.checked:
            painter.setPen(QPen(QColor(80, 220, 100), 3))
            painter.drawLine(box.left() + 5, box.top() + 12,
                             box.left() + 10, box.top() + 18)
            painter.drawLine(box.left() + 10, box.top() + 18,
                             box.left() + 20, box.top() + 6)

    def _paint_filename(self, painter, index, rect, box):

        text_rect = QRect(
            box.right() + 8,
            rect.bottom() - 31,
            max(20, rect.right() - box.right() - 14),
            25,
        )

        font = painter.font()
        font.setPointSize(max(7, min(11, int(8 + self.zoom * 2))))
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))

        name = Path(self.paths[index]).name
        text = painter.fontMetrics().elidedText(
            name, Qt.TextElideMode.ElideRight, text_rect.width()
        )
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            text,
        )


# ============================================================
# 主窗口
# ============================================================

class MainWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("选片助手工作台")
        self.resize(1400, 900)

        self.folder = None
        self.loader_thread = None
        self.loader = None
        self.hq_thread = None
        self.hq_loader = None

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ----------------------------------------------------
        # 工具栏
        # ----------------------------------------------------

        # 第一行：打开 / 路径 / 文件名 / 匹配 / 全选 / 全不选
        top = QHBoxLayout()

        self.open_btn = QPushButton("打开文件夹")
        self.open_btn.clicked.connect(self.open_folder)
        top.addWidget(self.open_btn)

        self.path_label = QLabel("未选择文件夹")
        self.path_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        top.addWidget(self.path_label)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(
            "输入文件名或片段，英文/中文逗号分隔，例如：4143,4144,4145"
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

        layout.addLayout(top)

        # 第二行：复制 / 移动 / 回收站 / 拼接导出
        second = QHBoxLayout()

        for text, slot in (
            ("复制到新筛选文件夹", self.copy_to_new_folder),
            ("复制到指定文件夹 (Ctrl+C)", self.copy_to_folder),
            ("移动到新筛选文件夹", self.move_to_new_folder),
            ("移动到指定文件夹 (Ctrl+X)", self.move_to_folder),
            ("移动到回收站 (Del / Backspace)", self.move_to_recycle_bin),
            ("导出拼接缩略图 (Ctrl+S)", self.stitch_selected),
        ):
            button = QPushButton(text)
            button.clicked.connect(slot)
            second.addWidget(button)

        layout.addLayout(second)

        layout.addWidget(QLabel(
            "Ctrl + 滚轮：缩放；普通滚轮：滚动；横向滚轮：左右移动；"
            "Shift + 点击：范围选择；点击图片任意位置：勾选/取消；"
        ))

        # ----------------------------------------------------
        # 图片视图
        # ----------------------------------------------------

        self.view = PhotoView()
        self.view.checkedChanged.connect(self.sync_checked_to_edit)
        self.view.visibleRangeChanged.connect(self.ensure_visible_loaded)
        self.view.visibleRangeChanged.connect(self.ensure_hq_loaded)
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

        folder = QFileDialog.getExistingDirectory(
            self, "选择图片文件夹", str(Path.home())
        )
        if folder:
            self.load_folder(Path(folder))

    def load_folder(self, folder: Path):

        self.stop_loader()

        files = sorted(
            (p for p in folder.iterdir() if p.is_file() and is_image_file(p)),
            key=lambda p: p.name.lower(),
        )

        self.folder = folder
        self.path_label.setText(str(folder))
        self.view.set_files([str(p) for p in files])
        self.name_edit.clear()

        print("=" * 72)
        print(f"[文件夹] {folder}")
        print(f"[总计] {len(files)} 张图片")
        print("=" * 72, flush=True)

        if not files:
            self.statusBar().showMessage("该文件夹中没有支持的图片")
            return

        self.statusBar().showMessage(f"共 {len(files)} 张图片，正在按需读取")
        self.ensure_visible_loaded(*self.view.visible_range())

    def _run_loader(self, loader, thread, on_loaded, on_failed, on_finished):
        """把 loader 放到独立线程中运行并连接信号。"""

        loader.moveToThread(thread)
        thread.started.connect(loader.run)
        loader.loaded.connect(on_loaded)
        loader.failed.connect(on_failed)
        loader.finished.connect(thread.quit)
        loader.finished.connect(on_finished)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def ensure_visible_loaded(self, lo, hi):

        if not self.view.paths or hi < lo:
            return

        # 可视区域 + 少量预读
        pad = self.view.columns() * 2
        lo2 = max(0, lo - pad)
        hi2 = min(len(self.view.paths) - 1, hi + pad)

        missing = [
            (i, self.view.paths[i])
            for i in range(lo2, hi2 + 1)
            if i not in self.view.images and i not in self.view.errors
        ]

        if not missing or self.loader_thread is not None:
            return

        self.loader_thread = QThread(self)
        self.loader = ImageLoader()
        self.loader.set_queue(missing)

        self._run_loader(
            self.loader, self.loader_thread,
            self.view.set_image, self.view.set_error, self.loader_finished,
        )

        self.statusBar().showMessage(
            f"当前读取/显示：{lo2 + 1}~{hi2 + 1} / {len(self.view.paths)}"
        )

    def loader_finished(self):

        self.loader = None
        self.loader_thread = None
        QTimer.singleShot(
            0, lambda: self.ensure_visible_loaded(*self.view.visible_range())
        )

    def ensure_hq_loaded(self):
        """单图模式下，为当前可见的 RAW 读取完整画质。"""

        if not self.view.paths or self.view.columns() != 1:
            return

        tile = max(1, self.view.tile_size())
        scroll_y = self.view.verticalScrollBar().value()
        first_row = scroll_y // tile
        last_row = min(
            len(self.view.paths) - 1,
            (scroll_y + self.view.viewport().height() - 1) // tile,
        )

        needed = []
        for i in range(first_row, last_row + 1):
            path = self.view.paths[i]
            # 非 RAW 本身已是完整画质
            if Path(path).suffix.lower() not in RAW_EXTS:
                continue
            if i in self.view.hq_images or i in self.view.hq_failed:
                continue
            needed.append((i, path))

        if not needed or self.hq_thread is not None:
            return

        self.hq_thread = QThread(self)
        self.hq_loader = ImageLoader(full=True)
        self.hq_loader.set_queue(needed)

        self._run_loader(
            self.hq_loader, self.hq_thread,
            self.on_hq_loaded, self.on_hq_failed, self.hq_finished,
        )

    def on_hq_loaded(self, index, image):
        # 忽略已失效（例如切换文件夹后）的读取结果
        if self.sender() is not self.hq_loader:
            return
        self.view.set_hq_image(index, image)

    def on_hq_failed(self, index, error):

        if self.sender() is not self.hq_loader:
            return

        self.view.hq_failed.add(index)
        name = (
            Path(self.view.paths[index]).name
            if 0 <= index < len(self.view.paths)
            else str(index)
        )
        print(f"[完整画质失败] {name} -> {error}", flush=True)

    def hq_finished(self):

        self.hq_loader = None
        self.hq_thread = None
        QTimer.singleShot(0, self.ensure_hq_loaded)

    def stop_loader(self):

        for loader in (self.loader, self.hq_loader):
            if loader is not None:
                loader.stop()

        for thread in (self.loader_thread, self.hq_thread):
            if thread is not None:
                thread.quit()
                thread.wait(1500)

        self.loader = self.hq_loader = None
        self.loader_thread = self.hq_thread = None

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

        indices = self.selected_indices()

        if not indices:
            QMessageBox.information(self, "提示", "没有匹配到任何文件。")
            return

        # 当前档位的一行列数（放大显示时为 1）
        columns = self.view.columns()

        rows = (len(indices) + columns - 1) // columns
        cell = 3840 / columns
        width = 3840
        height = int(round(rows * cell))

        # 防止拼接图过大导致内存问题
        if width * height > 150_000_000:
            QMessageBox.warning(
                self,
                "提示",
                f"拼接图尺寸过大（{width} × {height}）。\n"
                "请减少选中数量，或先缩小到列数更多的档位再导出。",
            )
            return

        canvas = QImage(width, height, QImage.Format.Format_RGB32)
        canvas.fill(QColor(25, 25, 25))

        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        font = painter.font()
        font.setPixelSize(min(48, max(12, int(cell * 0.045))))
        painter.setFont(font)

        failed = 0

        for position, index in enumerate(indices):

            row, column = divmod(position, columns)
            left = int(round(column * cell))
            right = int(round((column + 1) * cell))
            top = int(round(row * cell))
            bottom = int(round((row + 1) * cell))
            rect = QRect(left, top, right - left, bottom - top)

            # 优先复用已加载的预览图，缺失时按需读取
            image = self.view.images.get(index)

            if image is None:
                try:
                    image = load_image(self.view.paths[index])
                except Exception as e:
                    failed += 1
                    print(f"[拼接] 读取失败 {self.view.paths[index]}: {e}", flush=True)
                    image = None

            if image is not None and not image.isNull():

                scaled = image.scaled(
                    rect.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                painter.drawImage(
                    QPoint(
                        rect.left() + (rect.width() - scaled.width()) // 2,
                        rect.top() + (rect.height() - scaled.height()) // 2,
                    ),
                    scaled,
                )

            # 文件名（底部半透明条）
            bar_height = max(18, int(cell * 0.06))
            bar = QRect(
                rect.left(),
                rect.bottom() - bar_height + 1,
                rect.width(),
                bar_height,
            )
            painter.fillRect(bar, QColor(0, 0, 0, 150))
            painter.setPen(QColor(255, 255, 255))

            name = Path(self.view.paths[index]).name
            text = painter.fontMetrics().elidedText(
                name, Qt.TextElideMode.ElideRight, bar.width() - 12
            )
            painter.drawText(
                bar.adjusted(6, 0, -6, 0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                text,
            )

        painter.end()

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
    # 文件搬运
    # --------------------------------------------------------

    def selected_indices(self):

        self.match_names()
        return sorted(self.view.checked)

    def next_filter_folder(self):
        """返回最小的、当前未被占用的「筛选_xx」目录。"""

        number = 1
        while (self.folder / f"筛选_{number:02d}").exists():
            number += 1
        return self.folder / f"筛选_{number:02d}"

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

        indices = self.selected_indices()

        if not indices:
            QMessageBox.information(self, "提示", "没有匹配到任何文件。")
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

        indices, _, verb = collected

        target = self.next_filter_folder()
        target.mkdir(parents=True, exist_ok=False)

        operation = shutil.move if move else shutil.copy2
        count, failed = 0, []

        for index in indices:

            source = Path(self.view.paths[index])

            try:
                operation(str(source), str(target / source.name))
                count += 1
                print(f"[{verb}] {count}/{len(indices)}  {source.name}", flush=True)

            except Exception as e:
                failed.append((source.name, str(e)))
                print(f"[{verb}失败] {source.name}: {e}", flush=True)

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
        """
        复制 / 移动到指定文件夹。

        优先使用系统原生操作（自带冲突对话框），
        失败时退回 Python 方案。
        """

        collected = self._collect(move)
        if collected is None:
            return

        _, sources, verb = collected

        target = QFileDialog.getExistingDirectory(
            self, f"选择要{verb}到的文件夹", str(Path.home())
        )
        if not target:
            return

        native_ok = False

        try:
            result, aborted = shell_file_operation(
                FO_MOVE if move else FO_COPY, sources, target
            )
            native_ok = result == 0 and not aborted
        except Exception as e:
            print(f"[原生文件操作异常] {e}", flush=True)

        if not native_ok:

            print("[原生文件操作失败，改用 Python 方案]", flush=True)

            count, skipped, failed = self._python_transfer(sources, target, move)

            if count == 0 and skipped == 0:
                QMessageBox.warning(self, "提示", f"{verb}未完成。")
                return

            message = f"已{verb} {count} 个文件到：\n{target}"
            if skipped:
                message += f"\n\n跳过 {skipped} 个。"
            if failed:
                message += f"\n\n失败 {len(failed)} 个。"

            self._after_transfer(
                f"{verb}完成",
                message,
                f"{verb}完成：{count} 个文件 -> {Path(target).name}",
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

    def _python_transfer(self, sources, target, move):
        """Python 复制 / 移动，遇到同名文件时询问用户。"""

        replace_all = skip_all = False
        count = skipped = 0
        failed = []

        for src in sources:

            src_path = Path(src)
            dst_path = Path(target) / src_path.name

            if dst_path.exists():

                if skip_all:
                    skipped += 1
                    continue

                if not replace_all:

                    box = QMessageBox(self)
                    box.setWindowTitle("文件冲突")
                    box.setIcon(QMessageBox.Icon.Question)
                    box.setText(f"目标文件夹中已存在同名文件：\n{src_path.name}")

                    btn_yes = box.addButton("替换", QMessageBox.ButtonRole.YesRole)
                    btn_yes_all = box.addButton("全部替换", QMessageBox.ButtonRole.YesRole)
                    btn_no = box.addButton("跳过", QMessageBox.ButtonRole.NoRole)
                    btn_no_all = box.addButton("全部跳过", QMessageBox.ButtonRole.NoRole)

                    box.exec()
                    clicked = box.clickedButton()

                    if clicked is btn_yes_all:
                        replace_all = True
                    elif clicked is btn_no_all:
                        skip_all = True
                        skipped += 1
                        continue
                    elif clicked is btn_no:
                        skipped += 1
                        continue

            try:
                if move:
                    shutil.move(str(src_path), str(dst_path))
                else:
                    shutil.copy2(src_path, dst_path)
                count += 1

            except Exception as e:
                failed.append((src_path.name, str(e)))
                print(f"[Python 文件操作失败] {src_path.name}: {e}", flush=True)

        return count, skipped, failed

    def move_to_recycle_bin(self):
        """将选中文件移动到回收站（需确认）。"""

        indices = self.selected_indices()

        if not indices:
            QMessageBox.information(self, "提示", "没有匹配到任何文件。")
            return

        # 默认「是」，回车即选择「是」
        answer = QMessageBox.question(
            self,
            "移动到回收站",
            f"确定将选中的 {len(indices)} 个文件移动到回收站吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        sources = [self.view.paths[i] for i in indices]

        ok = False

        try:
            result, aborted = shell_delete_to_recycle_bin(sources)
            ok = result == 0 and not aborted
        except Exception as e:
            print(f"[原生删除异常] {e}", flush=True)

        if not ok:
            print("[原生删除失败，改用 PowerShell 方案]", flush=True)
            try:
                ok = powershell_recycle(sources) == 0
            except Exception as e:
                print(f"[PowerShell 回收站异常] {e}", flush=True)

        if not ok:
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
        self.stop_loader()
        event.accept()


# ============================================================
# 程序入口
# ============================================================

def main():

    app = QApplication(sys.argv)
    app.setApplicationName("选片助手工作台")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
