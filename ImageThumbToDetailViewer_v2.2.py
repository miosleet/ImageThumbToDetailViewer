#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RAW 图片批量筛选器

依赖：
    pip install PySide6 Pillow rawpy

支持：
    JPG/JPEG/PNG/BMP/GIF/TIF/TIFF/WEBP

RAW：
    ARW/CR2/CR3/NEF/NRW/DNG/RAF/RW2
    ORF/PEF/SR2/SRF/3FR/ERF/KDC/MRW
    RAW/RWL/X3F/IIQ/MOS/MEF/ARI

运行：
    python raw_photo_browser.py
"""

import os
import re
import sys
import shutil
import ctypes
from pathlib import Path

from PIL import Image, ImageOps
import rawpy

from PySide6.QtCore import (
    Qt,
    QRect,
    QSize,
    QPoint,
    QThread,
    Signal,
    QObject,
    QTimer,
)

from PySide6.QtGui import (
    QImage,
    QPainter,
    QPen,
    QBrush,
    QColor,
    QShortcut,
    QKeySequence,
)

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QLabel,
    QFileDialog,
    QMessageBox,
    QAbstractScrollArea,
    QSizePolicy,
)


# ============================================================
# 支持的图片格式
# ============================================================

IMAGE_EXTS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
    ".webp",

    # RAW
    ".arw",
    ".cr2",
    ".cr3",
    ".nef",
    ".nrw",
    ".dng",
    ".raf",
    ".rw2",
    ".orf",
    ".pef",
    ".sr2",
    ".srf",
    ".3fr",
    ".erf",
    ".kdc",
    ".mrw",
    ".raw",
    ".rwl",
    ".x3f",
    ".iiq",
    ".mos",
    ".mef",
    ".ari",
}


RAW_EXTS = {
    ".arw",
    ".cr2",
    ".cr3",
    ".nef",
    ".nrw",
    ".dng",
    ".raf",
    ".rw2",
    ".orf",
    ".pef",
    ".sr2",
    ".srf",
    ".3fr",
    ".erf",
    ".kdc",
    ".mrw",
    ".raw",
    ".rwl",
    ".x3f",
    ".iiq",
    ".mos",
    ".mef",
    ".ari",
}


def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS


# ============================================================
# 系统原生文件操作
#
# 用于「复制/移动到指定文件夹」以及「移动到回收站」。
# 借助 Windows 自带的文件操作，遇到同名文件时
# 会弹出系统原生的冲突对话框，由用户选择如何处理。
# ============================================================

FO_MOVE = 0x0001
FO_COPY = 0x0002
FO_DELETE = 0x0003

FOF_SILENT = 0x0004
FOF_NOCONFIRMATION = 0x0010
FOF_ALLOWUNDO = 0x0040       # 删除时送入回收站
FOF_NOCONFIRMMKDIR = 0x0200
FOF_NOERRORUI = 0x0400


def _build_shell_struct():
    """
    构造 SHFILEOPSTRUCTW。

    非 Windows 平台或不可用时返回 None。
    """

    try:
        from ctypes import wintypes

        class SHFILEOPSTRUCTW(ctypes.Structure):

            _fields_ = [
                ("hwnd", wintypes.HWND),
                ("wFunc", wintypes.UINT),
                ("pFrom", wintypes.LPCWSTR),
                ("pTo", wintypes.LPCWSTR),
                ("fFlags", ctypes.c_uint16),
                ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", ctypes.c_void_p),
                ("lpszProgressTitle", wintypes.LPCWSTR),
            ]

        return SHFILEOPSTRUCTW

    except Exception:

        return None


_SHFILEOPSTRUCTW = _build_shell_struct()


def _shell_operation(
    wfunc,
    sources,
    destination,
    flags,
    title,
):
    """
    调用 SHFileOperationW。

    destination 为 None 时表示不需要目标路径（例如删除）。

    返回 (result, aborted)：
        result == 0 表示操作成功执行。
        aborted 为 True 表示用户中途取消。
    """

    if _SHFILEOPSTRUCTW is None:

        raise RuntimeError(
            "当前系统不支持原生文件操作"
        )

    # 统一转成绝对路径，避免相对路径导致操作失败
    src_paths = [
        os.path.abspath(str(s))
        for s in sources
    ]

    # pFrom / pTo 需要以双 \0 结尾
    p_from = "\0".join(src_paths) + "\0\0"

    if destination is None:

        p_to = None

    else:

        p_to = (
            os.path.abspath(str(destination))
            + "\0\0"
        )

    op = _SHFILEOPSTRUCTW()

    op.hwnd = None
    op.wFunc = wfunc
    op.pFrom = p_from
    op.pTo = p_to
    op.fFlags = flags
    op.fAnyOperationsAborted = False
    op.hNameMappings = None
    op.lpszProgressTitle = title

    func = ctypes.windll.shell32.SHFileOperationW

    func.argtypes = [
        ctypes.POINTER(_SHFILEOPSTRUCTW)
    ]

    func.restype = ctypes.c_int

    result = func(ctypes.byref(op))

    print(
        f"[原生文件操作] wFunc={wfunc} "
        f"result={result} "
        f"aborted={bool(op.fAnyOperationsAborted)}",
        flush=True,
    )

    return result, bool(op.fAnyOperationsAborted)


def shell_file_operation(
    wfunc,
    sources,
    destination,
    title,
):
    """
    复制 / 移动到指定文件夹。
    """

    return _shell_operation(
        wfunc,
        sources,
        destination,
        FOF_NOCONFIRMMKDIR,
        title,
    )


def shell_delete_to_recycle_bin(sources):
    """
    将文件移动到回收站。

    使用 FOF_ALLOWUNDO，并抑制系统自带的确认框
    （确认由程序自己弹出）。
    """

    return _shell_operation(
        FO_DELETE,
        sources,
        None,
        FOF_ALLOWUNDO
        | FOF_NOCONFIRMATION
        | FOF_SILENT
        | FOF_NOERRORUI,
        "",
    )


def powershell_recycle(paths):
    """
    备用方案：通过 PowerShell 的
    Microsoft.VisualBasic 将文件移动到回收站。

    返回进程退出码，0 表示成功。
    """

    import subprocess

    joined = ",".join(
        "'" + str(p).replace("'", "''") + "'"
        for p in paths
    )

    script = (
        "Add-Type -AssemblyName Microsoft.VisualBasic; "
        f"@({joined}) | ForEach-Object {{ "
        "[Microsoft.VisualBasic.FileIO.FileSystem]::"
        "DeleteFile($_, 'OnlyErrorDialogs', "
        "'SendToRecycleBin') }"
    )

    proc = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
        ],
        capture_output=True,
        text=True,
    )

    return proc.returncode


# ============================================================
# 图片读取
# ============================================================

def pil_to_qimage(im: Image.Image) -> QImage:
    """
    Pillow -> QImage。

    使用 copy()，使 QImage 脱离 Pillow 图像的内存生命周期。
    """

    im = ImageOps.exif_transpose(im)

    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGB")

    if im.mode == "RGBA":
        data = im.tobytes("raw", "RGBA")

        qimage = QImage(
            data,
            im.width,
            im.height,
            im.width * 4,
            QImage.Format.Format_RGBA8888,
        )

    else:
        data = im.tobytes("raw", "RGB")

        qimage = QImage(
            data,
            im.width,
            im.height,
            im.width * 3,
            QImage.Format.Format_RGB888,
        )

    return qimage.copy()


def raw_to_pil(
    path: str,
    full: bool = False,
) -> Image.Image:
    """
    RAW 文件读取。

    full=False（默认）：
        优先读取相机 RAW 文件内部的 JPEG 缩略图，
        没有可用缩略图时再进行 half_size RAW 解码，
        速度快，用于网格预览。

    full=True：
        跳过缩略图，直接进行完整分辨率 RAW 解码，
        画质最高，用于单图模式。
    """

    with rawpy.imread(path) as raw:

        # ----------------------------------------------------
        # 预览模式：优先读取 RAW 内嵌缩略图
        # ----------------------------------------------------

        if not full:

            try:
                thumb = raw.extract_thumb()

                if (
                    thumb.format
                    == rawpy.ThumbFormat.JPEG
                ):
                    from io import BytesIO

                    return Image.open(
                        BytesIO(thumb.data)
                    ).convert("RGB")

                if (
                    thumb.format
                    == rawpy.ThumbFormat.BITMAP
                ):
                    return Image.fromarray(
                        thumb.data
                    ).convert("RGB")

            except Exception:
                pass

        # ----------------------------------------------------
        # RAW 解码
        #
        # full=True 时使用完整分辨率。
        # ----------------------------------------------------

        rgb = raw.postprocess(
            use_camera_wb=True,
            half_size=not full,
            no_auto_bright=False,
            output_bps=8,
        )

        return Image.fromarray(rgb).convert("RGB")


def load_image(
    path: str,
    full: bool = False,
) -> QImage:

    ext = Path(path).suffix.lower()

    if ext in RAW_EXTS:
        return pil_to_qimage(
            raw_to_pil(path, full=full)
        )

    with Image.open(path) as im:

        return pil_to_qimage(
            im.copy()
        )


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

        for n, (index, path) in enumerate(
            self._queue,
            1
        ):

            if not self._running:
                break

            try:

                filename = Path(path).name

                print(
                    f"[读取] {n}/{total}  {filename}",
                    flush=True,
                )

                image = load_image(
                    path,
                    full=self._full,
                )

                self.loaded.emit(
                    index,
                    image,
                )

                print(
                    f"[显示] {n}/{total}  {filename}",
                    flush=True,
                )

            except Exception as e:

                message = (
                    f"{type(e).__name__}: {e}"
                )

                print(
                    f"[失败] {n}/{total}  "
                    f"{Path(path).name} -> {message}",
                    flush=True,
                )

                self.failed.emit(
                    index,
                    message,
                )

        self.finished.emit()


# ============================================================
# 图片虚拟显示区域
# ============================================================

class PhotoView(QAbstractScrollArea):

    checkedChanged = Signal()

    visibleRangeChanged = Signal(
        int,
        int,
    )

    # --------------------------------------------------------
    # 缩放档位
    #
    # 0.10 -> 约 10 列
    # 0.12 -> 约 8 列
    # 0.145 -> 约 7 列
    # 0.175 -> 约 6 列
    # 0.21 -> 约 5 列
    # 0.255 -> 约 4 列
    # 0.31 -> 3 列
    # 0.47 -> 2 列
    # 0.58 -> 1 列
    #
    # 3列和2列分别只有一个档位。
    #
    # 1列之后进入放大模式。
    # --------------------------------------------------------

    ZOOM_LEVELS = [
        0.10,
        0.12,
        0.145,
        0.175,
        0.21,
        0.255,

        # 3列
        0.31,

        # 2列
        0.47,

        # 1列
        0.58,

        # 单图进一步放大
        0.82,
        1.00,
        1.25,
        1.55,
        1.90,
        2.40,
        3.00,
        4.00,
    ]

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setFrameShape(
            QAbstractScrollArea.Shape.NoFrame
        )

        self.setBackgroundRole(
            self.palette().ColorRole.Base
        )

        self.setMouseTracking(True)

        self.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus
        )

        # ----------------------------------------------------
        # 文件
        # ----------------------------------------------------

        self.paths = []

        # 已勾选的图片 index
        self.checked = set()

        # 已读取图片
        self.images = {}

        # 读取失败
        self.errors = {}

        # 单图模式下的完整画质图片
        self.hq_images = {}

        # 完整画质读取失败的 index
        self.hq_failed = set()

        # 当前缩放档位
        self.zoom_index = 0

        # 最小列数
        self.min_columns = 10

        # 图片缓存数量
        self.max_cache = 80

        # ----------------------------------------------------
        # Shift 连选
        # ----------------------------------------------------

        self.last_clicked_index = None

        # ----------------------------------------------------
        # 可视区域缓存
        # ----------------------------------------------------

        self._last_visible = (
            -1,
            -1,
        )

        self.verticalScrollBar().valueChanged.connect(
            self.viewport().update
        )

        self.horizontalScrollBar().valueChanged.connect(
            self.viewport().update
        )

    # ========================================================
    # 缩放
    # ========================================================

    @property
    def zoom(self):
        return self.ZOOM_LEVELS[
            self.zoom_index
        ]

    # ========================================================
    # 设置文件
    # ========================================================

    def set_files(self, paths):

        self.paths = paths

        self.images.clear()
        self.errors.clear()
        self.checked.clear()

        self.hq_images.clear()
        self.hq_failed.clear()

        self.zoom_index = 0

        self.last_clicked_index = None

        self._update_scrollbars()

        self.viewport().update()

    # ========================================================
    # 设置图片
    # ========================================================

    def set_image(
        self,
        index,
        image,
    ):

        self.images[index] = image

        # ----------------------------------------------------
        # 控制内存中的图片数量
        # ----------------------------------------------------

        if len(self.images) > self.max_cache:

            lo, hi = self.visible_range()

            if lo <= hi:
                center = (
                    lo + hi
                ) // 2
            else:
                center = 0

            old = max(
                self.images.keys(),
                key=lambda i: abs(
                    i - center
                ),
            )

            if old != index:
                self.images.pop(
                    old,
                    None,
                )

        self.viewport().update()

    # ========================================================
    # 设置错误
    # ========================================================

    def set_error(
        self,
        index,
        error,
    ):

        self.errors[index] = error

        self.viewport().update()

    # ========================================================
    # 设置完整画质图片（单图模式）
    # ========================================================

    def set_hq_image(
        self,
        index,
        image,
    ):

        self.hq_images[index] = image

        # ----------------------------------------------------
        # 完整画质图片占用内存较大，只保留少量缓存
        # ----------------------------------------------------

        if len(self.hq_images) > 3:

            lo, hi = self.visible_range()

            if lo <= hi:
                center = (lo + hi) // 2
            else:
                center = 0

            old = max(
                self.hq_images.keys(),
                key=lambda i: abs(i - center),
            )

            if old != index:
                self.hq_images.pop(
                    old,
                    None,
                )

        self.viewport().update()

    # ========================================================
    # 当前列数
    # ========================================================

    def columns(self):

        # ----------------------------------------------------
        # 1列
        # ----------------------------------------------------

        if self.zoom >= 0.55:
            return 1

        # ----------------------------------------------------
        # 3列
        # ----------------------------------------------------

        if 0.30 <= self.zoom < 0.40:
            return 3

        # ----------------------------------------------------
        # 2列
        # ----------------------------------------------------

        if 0.40 <= self.zoom < 0.55:
            return 2

        # ----------------------------------------------------
        # 其他档位按照原逻辑计算
        # ----------------------------------------------------

        return max(
            1,
            round(
                self.min_columns
                / (self.zoom / 0.10)
            ),
        )

    # ========================================================
    # 每个图片格子的宽度
    # ========================================================

    def tile_width(self):

        columns = self.columns()

        # ----------------------------------------------------
        # 单图模式
        # ----------------------------------------------------

        if columns == 1:

            return max(
                1,
                int(
                    self.viewport().width()
                    * self.zoom
                ),
            )

        # ----------------------------------------------------
        # 多图模式
        # ----------------------------------------------------

        return max(
            1,
            int(
                self.viewport().width()
                / columns
            ),
        )

    # ========================================================
    # 每个图片格子的高度
    # ========================================================

    def tile_height(self):

        return self.tile_width()

    # ========================================================
    # 内容区域大小
    # ========================================================

    def content_size(self):

        columns = self.columns()

        tile_width = self.tile_width()
        tile_height = self.tile_height()

        if self.paths:

            rows = (
                len(self.paths)
                + columns
                - 1
            ) // columns

        else:

            rows = 0

        return QSize(
            max(
                1,
                columns * tile_width,
            ),
            max(
                1,
                rows * tile_height,
            ),
        )

    # ========================================================
    # 更新滚动条
    # ========================================================

    def _update_scrollbars(self):

        size = self.content_size()

        viewport_width = (
            self.viewport().width()
        )

        viewport_height = (
            self.viewport().height()
        )

        self.horizontalScrollBar().setRange(
            0,
            max(
                0,
                size.width()
                - viewport_width,
            ),
        )

        self.verticalScrollBar().setRange(
            0,
            max(
                0,
                size.height()
                - viewport_height,
            ),
        )

        self.horizontalScrollBar().setPageStep(
            viewport_width
        )

        self.verticalScrollBar().setPageStep(
            viewport_height
        )

    # ========================================================
    # 窗口大小变化
    # ========================================================

    def resizeEvent(self, event):

        super().resizeEvent(event)

        self._update_scrollbars()

        self.viewport().update()

    # ========================================================
    # 鼠标滚轮
    # ========================================================

    def wheelEvent(self, event):

        modifiers = event.modifiers()

        # ====================================================
        # Ctrl + 滚轮：缩放
        # ====================================================

        if (
            modifiers
            & Qt.KeyboardModifier.ControlModifier
        ):

            delta = event.angleDelta().y()

            if delta == 0:
                event.accept()
                return

            old_zoom_index = self.zoom_index

            # ------------------------------------------------
            # 记录缩放前，可视区域左上角的第一张图
            #
            # 缩放后需要保证这张图仍然位于第一行，
            # 并且其所在行紧贴窗口最上边。
            # ------------------------------------------------

            old_columns = self.columns()

            old_tile_height = max(
                1,
                self.tile_height(),
            )

            old_scroll_x = (
                self.horizontalScrollBar().value()
            )

            old_scroll_y = (
                self.verticalScrollBar().value()
            )

            first_index = (
                old_scroll_y // old_tile_height
            ) * old_columns

            if self.paths:

                first_index = min(
                    first_index,
                    len(self.paths) - 1,
                )

            mouse_pos = (
                event.position().toPoint()
            )

            old_content_x = (
                old_scroll_x
                + mouse_pos.x()
            )

            if delta > 0:

                self.zoom_index = min(
                    len(self.ZOOM_LEVELS) - 1,
                    self.zoom_index + 1,
                )

            else:

                self.zoom_index = max(
                    0,
                    self.zoom_index - 1,
                )

            if self.zoom_index != old_zoom_index:

                old_zoom = (
                    self.ZOOM_LEVELS[
                        old_zoom_index
                    ]
                )

                new_zoom = self.zoom

                # ------------------------------------------------
                # 重新计算内容尺寸
                # ------------------------------------------------

                self._update_scrollbars()

                # ------------------------------------------------
                # 垂直方向：
                #
                # 让缩放前第一张图所在的这一行紧贴窗口最上边。
                # 滚动值对齐到整行，避免顶部露出半行。
                # ------------------------------------------------

                new_columns = self.columns()

                new_tile_height = max(
                    1,
                    self.tile_height(),
                )

                target_y = (
                    first_index // new_columns
                ) * new_tile_height

                max_y = (
                    self.verticalScrollBar().maximum()
                )

                if target_y > max_y:

                    target_y = max_y

                # 向下对齐到整行
                target_y = (
                    target_y // new_tile_height
                ) * new_tile_height

                self.verticalScrollBar().setValue(
                    target_y
                )

                # ------------------------------------------------
                # 水平方向：
                #
                # 保持鼠标所在位置作为缩放锚点。
                # ------------------------------------------------

                if old_zoom != 0:

                    scale = (
                        new_zoom
                        / old_zoom
                    )

                    new_x = int(
                        old_content_x
                        * scale
                        - mouse_pos.x()
                    )

                    self.horizontalScrollBar().setValue(
                        max(
                            0,
                            min(
                                self.horizontalScrollBar().maximum(),
                                new_x,
                            ),
                        )
                    )

                self.viewport().update()

            event.accept()
            return

        # ====================================================
        # 非 Ctrl 模式
        #
        # 单图模式：
        #     小幅像素滚动
        #
        # 多图模式：
        #     每次滚动一行
        # ====================================================

        vertical_delta = (
            event.angleDelta().y()
        )

        horizontal_delta = (
            event.angleDelta().x()
        )

        # 某些高精度鼠标/触控板可能没有 angleDelta，
        # 使用 pixelDelta 作为备用。
        pixel_delta = event.pixelDelta()

        if vertical_delta == 0:

            vertical_delta = pixel_delta.y()

        if horizontal_delta == 0:

            horizontal_delta = pixel_delta.x()

        # ====================================================
        # 垂直滚动
        # ====================================================

        if vertical_delta != 0:

            columns = self.columns()

            # ------------------------------------------------
            # 单图模式
            #
            # 不再一次跳一整行。
            # 每个滚轮刻度移动约 45 像素。
            # ------------------------------------------------

            if columns == 1:

                if abs(vertical_delta) >= 120:

                    steps = max(
                        1,
                        abs(vertical_delta)
                        // 120,
                    )

                    move_pixels = (
                        45
                        * steps
                    )

                else:

                    move_pixels = max(
                        10,
                        abs(vertical_delta)
                        // 2,
                    )

            # ------------------------------------------------
            # 多图模式
            #
            # 每次滚动一个图片格高度。
            # ------------------------------------------------

            else:

                rows = max(
                    1,
                    abs(vertical_delta)
                    // 120,
                )

                move_pixels = (
                    self.tile_height()
                    * rows
                )

            # Qt 中向上滚动 delta > 0
            direction = (
                -1
                if vertical_delta > 0
                else 1
            )

            bar = (
                self.verticalScrollBar()
            )

            bar.setValue(
                bar.value()
                + direction
                * move_pixels
            )

        # ====================================================
        # 横向滚动
        # ====================================================

        if horizontal_delta != 0:

            if abs(horizontal_delta) >= 120:

                steps = max(
                    1,
                    abs(horizontal_delta)
                    // 120,
                )

                move_pixels = (
                    45
                    * steps
                )

            else:

                move_pixels = max(
                    10,
                    abs(horizontal_delta)
                    // 2,
                )

            direction = (
                -1
                if horizontal_delta > 0
                else 1
            )

            bar = (
                self.horizontalScrollBar()
            )

            bar.setValue(
                bar.value()
                + direction
                * move_pixels
            )

        event.accept()

    # ========================================================
    # 可视区域
    # ========================================================

    def visible_range(self):

        if not self.paths:

            return (
                0,
                -1,
            )

        columns = self.columns()

        tile_height = (
            self.tile_height()
        )

        top = (
            self.verticalScrollBar().value()
        )

        bottom = (
            top
            + self.viewport().height()
        )

        first_row = max(
            0,
            top
            // max(
                1,
                tile_height,
            )
            - 1,
        )

        last_row = min(
            (
                len(self.paths)
                - 1
            )
            // columns,

            bottom
            // max(
                1,
                tile_height,
            )
            + 1,
        )

        return (
            first_row * columns,
            min(
                len(self.paths) - 1,
                (last_row + 1)
                * columns
                - 1,
            ),
        )

    # ========================================================
    # 获取图片格子矩形
    # ========================================================

    def _tile_rect(self, index):

        columns = self.columns()

        tile_width = (
            self.tile_width()
        )

        tile_height = (
            self.tile_height()
        )

        row, column = divmod(
            index,
            columns,
        )

        return QRect(
            column * tile_width,
            row * tile_height,
            tile_width,
            tile_height,
        )

    # ========================================================
    # 鼠标点击
    # ========================================================

    def mousePressEvent(self, event):

        if (
            event.button()
            == Qt.MouseButton.LeftButton
        ):

            index = self.index_at(
                event.position().toPoint()
            )

            if index is not None:

                shift_pressed = bool(
                    event.modifiers()
                    & Qt.KeyboardModifier.ShiftModifier
                )

                # =================================================
                # Shift + 点击
                #
                # 按照文件管理器的范围选择逻辑：
                # 上一次点击的位置 -> 当前点击位置
                # 中间全部选中。
                # =================================================

                if (
                    shift_pressed
                    and self.last_clicked_index
                    is not None
                ):

                    start = min(
                        self.last_clicked_index,
                        index,
                    )

                    end = max(
                        self.last_clicked_index,
                        index,
                    )

                    for i in range(
                        start,
                        end + 1,
                    ):

                        self.checked.add(i)

                # =================================================
                # 普通点击
                #
                # 整个图片格子都是勾选区域。
                # =================================================

                else:

                    if index in self.checked:

                        self.checked.remove(
                            index
                        )

                    else:

                        self.checked.add(
                            index
                        )

                # 当前点击位置成为下一次 Shift 选择的锚点
                self.last_clicked_index = index

                self.checkedChanged.emit()

                self.viewport().update()

                event.accept()

                return

        super().mousePressEvent(event)

    # ========================================================
    # 根据鼠标位置获取图片 index
    # ========================================================

    def index_at(self, pos):

        x = (
            pos.x()
            + self.horizontalScrollBar().value()
        )

        y = (
            pos.y()
            + self.verticalScrollBar().value()
        )

        tile_width = (
            self.tile_width()
        )

        tile_height = (
            self.tile_height()
        )

        if (
            tile_width <= 0
            or tile_height <= 0
        ):
            return None

        column = (
            x // tile_width
        )

        row = (
            y // tile_height
        )

        index = (
            row * self.columns()
            + column
        )

        if (
            0 <= index
            < len(self.paths)
        ):

            return index

        return None

    # ========================================================
    # 绘制
    # ========================================================

    def paintEvent(self, event):

        painter = QPainter(
            self.viewport()
        )

        painter.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform,
            True,
        )

        painter.fillRect(
            self.viewport().rect(),
            QColor(
                25,
                25,
                25,
            ),
        )

        lo, hi = (
            self.visible_range()
        )

        if (
            lo,
            hi,
        ) != self._last_visible:

            self._last_visible = (
                lo,
                hi,
            )

            self.visibleRangeChanged.emit(
                lo,
                hi,
            )

        if hi < lo:

            painter.end()

            return

        # ----------------------------------------------------
        # 把内容坐标移动到滚动位置
        # ----------------------------------------------------

        scroll_x = (
            self.horizontalScrollBar().value()
        )

        scroll_y = (
            self.verticalScrollBar().value()
        )

        painter.translate(
            -scroll_x,
            -scroll_y,
        )

        # 单图模式下优先使用完整画质图片
        single_mode = self.columns() == 1

        for i in range(
            lo,
            hi + 1,
        ):

            rect = self._tile_rect(i)

            if single_mode:

                image = self.hq_images.get(i)

                if image is None:
                    image = self.images.get(i)

            else:

                image = self.images.get(i)

            # =================================================
            # 图片
            # =================================================

            if (
                image is not None
                and not image.isNull()
            ):

                target = rect

                scaled = image.scaled(
                    target.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

                x = (
                    rect.left()
                    + (
                        rect.width()
                        - scaled.width()
                    )
                    // 2
                )

                y = (
                    rect.top()
                    + (
                        rect.height()
                        - scaled.height()
                    )
                    // 2
                )

                painter.drawImage(
                    QPoint(
                        x,
                        y,
                    ),
                    scaled,
                )

            # =================================================
            # 读取失败
            # =================================================

            elif i in self.errors:

                painter.fillRect(
                    rect,
                    QColor(
                        75,
                        25,
                        25,
                    ),
                )

                painter.setPen(
                    QColor(
                        255,
                        150,
                        150,
                    )
                )

                painter.drawText(
                    rect.adjusted(
                        8,
                        8,
                        -8,
                        -8,
                    ),
                    Qt.AlignmentFlag.AlignCenter,
                    "读取失败\n"
                    + Path(
                        self.paths[i]
                    ).name,
                )

            # =================================================
            # 尚未读取
            # =================================================

            else:

                painter.fillRect(
                    rect,
                    QColor(
                        40,
                        40,
                        40,
                    ),
                )

                painter.setPen(
                    QColor(
                        140,
                        140,
                        140,
                    )
                )

                painter.drawText(
                    rect.adjusted(
                        5,
                        5,
                        -5,
                        -5,
                    ),
                    Qt.AlignmentFlag.AlignCenter,
                    "读取中…",
                )

            # =================================================
            # 左下角 checkbox
            # =================================================

            checkbox = QRect(
                rect.left() + 7,
                rect.bottom() - 31,
                24,
                24,
            )

            painter.setPen(
                QPen(
                    QColor(
                        235,
                        235,
                        235,
                    ),
                    2,
                )
            )

            painter.setBrush(
                QBrush(
                    QColor(
                        35,
                        35,
                        35,
                        190,
                    )
                )
            )

            painter.drawRect(
                checkbox
            )

            # =================================================
            # 勾选标记
            # =================================================

            if i in self.checked:

                painter.setPen(
                    QPen(
                        QColor(
                            80,
                            220,
                            100,
                        ),
                        3,
                    )
                )

                painter.drawLine(
                    checkbox.left() + 5,
                    checkbox.top() + 12,
                    checkbox.left() + 10,
                    checkbox.top() + 18,
                )

                painter.drawLine(
                    checkbox.left() + 10,
                    checkbox.top() + 18,
                    checkbox.left() + 20,
                    checkbox.top() + 6,
                )

            # =================================================
            # 文件名
            # =================================================

            filename = Path(
                self.paths[i]
            ).name

            text_rect = QRect(
                checkbox.right() + 8,
                rect.bottom() - 31,
                max(
                    20,
                    rect.right()
                    - checkbox.right()
                    - 14,
                ),
                25,
            )

            font = painter.font()

            # 根据缩放适当调整字体
            font.setPointSize(
                max(
                    7,
                    min(
                        11,
                        int(
                            8
                            + self.zoom * 2
                        ),
                    ),
                )
            )

            painter.setFont(font)

            # 白色字体
            painter.setPen(
                QColor(
                    255,
                    255,
                    255,
                )
            )

            elided_filename = (
                painter.fontMetrics().elidedText(
                    filename,
                    Qt.TextElideMode.ElideRight,
                    text_rect.width(),
                )
            )

            painter.drawText(
                text_rect,
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignVCenter,
                elided_filename,
            )

        painter.end()


# ============================================================
# 主窗口
# ============================================================

class MainWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle(
            "RAW 图片批量筛选器"
        )

        self.resize(
            1400,
            900,
        )

        self.folder = None

        self.loader_thread = None
        self.loader = None

        # 单图模式：完整画质读取线程
        self.hq_thread = None
        self.hq_loader = None

        # ====================================================
        # 主 Widget
        # ====================================================

        root = QWidget()

        self.setCentralWidget(
            root
        )

        layout = QVBoxLayout(
            root
        )

        layout.setContentsMargins(
            4,
            4,
            4,
            4,
        )

        layout.setSpacing(4)

        # ====================================================
        # 顶部工具栏
        # ====================================================

        top = QHBoxLayout()

        # ----------------------------------------------------
        # 打开文件夹
        # ----------------------------------------------------

        self.open_btn = QPushButton(
            "打开文件夹"
        )

        self.open_btn.clicked.connect(
            self.open_folder
        )

        top.addWidget(
            self.open_btn
        )

        # ----------------------------------------------------
        # 当前文件夹
        # ----------------------------------------------------

        self.path_label = QLabel(
            "未选择文件夹"
        )

        self.path_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        top.addWidget(
            self.path_label
        )

        # ----------------------------------------------------
        # 文件名输入框
        # ----------------------------------------------------

        self.name_edit = QLineEdit()

        self.name_edit.setPlaceholderText(
            "输入文件名或片段，英文/中文逗号分隔，例如：4143,4144,4145"
        )

        self.name_edit.returnPressed.connect(
            self.match_names
        )

        top.addWidget(
            self.name_edit,
            2,
        )

        # ----------------------------------------------------
        # 匹配文件名
        # ----------------------------------------------------

        self.match_btn = QPushButton(
            "匹配文件名"
        )

        self.match_btn.clicked.connect(
            self.match_names
        )

        top.addWidget(
            self.match_btn
        )

        # ----------------------------------------------------
        # 复制到新筛选文件夹
        # ----------------------------------------------------

        self.filter_btn = QPushButton(
            "复制到新筛选文件夹"
        )

        self.filter_btn.clicked.connect(
            self.copy_to_new_folder
        )

        top.addWidget(
            self.filter_btn
        )

        # ----------------------------------------------------
        # 复制到指定文件夹
        # ----------------------------------------------------

        self.copy_to_btn = QPushButton(
            "复制到指定文件夹"
        )

        self.copy_to_btn.clicked.connect(
            self.copy_to_folder
        )

        top.addWidget(
            self.copy_to_btn
        )

        # ----------------------------------------------------
        # 移动到新筛选文件夹
        # ----------------------------------------------------

        self.move_new_btn = QPushButton(
            "移动到新筛选文件夹"
        )

        self.move_new_btn.clicked.connect(
            self.move_to_new_folder
        )

        top.addWidget(
            self.move_new_btn
        )

        # ----------------------------------------------------
        # 移动到指定文件夹
        # ----------------------------------------------------

        self.move_to_btn = QPushButton(
            "移动到指定文件夹"
        )

        self.move_to_btn.clicked.connect(
            self.move_to_folder
        )

        top.addWidget(
            self.move_to_btn
        )

        # ----------------------------------------------------
        # 移动到回收站
        # ----------------------------------------------------

        self.recycle_btn = QPushButton(
            "移动到回收站"
        )

        self.recycle_btn.clicked.connect(
            self.move_to_recycle_bin
        )

        top.addWidget(
            self.recycle_btn
        )

        layout.addLayout(
            top
        )

        # ====================================================
        # 操作提示
        # ====================================================

        self.info = QLabel(
            "Ctrl + 滚轮：缩放；"
            "普通滚轮：滚动；"
            "横向滚轮：左右移动；"
            "Shift + 点击：范围选择；"
            "点击图片任意位置：勾选/取消"
        )

        layout.addWidget(
            self.info
        )

        # ====================================================
        # 图片视图
        # ====================================================

        self.view = PhotoView()

        self.view.checkedChanged.connect(
            self.sync_checked_to_edit
        )

        self.view.visibleRangeChanged.connect(
            self.ensure_visible_loaded
        )

        self.view.visibleRangeChanged.connect(
            self.ensure_hq_loaded
        )

        layout.addWidget(
            self.view,
            1,
        )

        # ====================================================
        # 快捷键
        #
        # Ctrl+C：复制到指定文件夹
        # Ctrl+X：移动到指定文件夹
        # Del / Backspace：移动到回收站（仅图片视图聚焦时）
        # ====================================================

        self.copy_shortcut = QShortcut(
            QKeySequence("Ctrl+C"),
            self,
        )

        self.copy_shortcut.activated.connect(
            self.copy_to_folder
        )

        self.move_shortcut = QShortcut(
            QKeySequence("Ctrl+X"),
            self,
        )

        self.move_shortcut.activated.connect(
            self.move_to_folder
        )

        self.del_shortcut = QShortcut(
            QKeySequence("Del"),
            self.view,
        )

        self.del_shortcut.setContext(
            Qt.ShortcutContext.WidgetShortcut
        )

        self.del_shortcut.activated.connect(
            self.move_to_recycle_bin
        )

        self.backspace_shortcut = QShortcut(
            QKeySequence("Backspace"),
            self.view,
        )

        self.backspace_shortcut.setContext(
            Qt.ShortcutContext.WidgetShortcut
        )

        self.backspace_shortcut.activated.connect(
            self.move_to_recycle_bin
        )

        self.statusBar().showMessage(
            "请选择一个图片文件夹"
        )

    # ========================================================
    # 打开文件夹
    # ========================================================

    def open_folder(self):

        folder = QFileDialog.getExistingDirectory(
            self,
            "选择图片文件夹",
            str(Path.home()),
        )

        if not folder:
            return

        self.load_folder(
            Path(folder)
        )

    # ========================================================
    # 加载文件夹
    # ========================================================

    def load_folder(
        self,
        folder: Path,
    ):

        self.stop_loader()

        # ----------------------------------------------------
        # 只读取当前文件夹
        # 不进入子文件夹
        # ----------------------------------------------------

        files = [
            path
            for path in folder.iterdir()
            if (
                path.is_file()
                and is_image_file(path)
            )
        ]

        files.sort(
            key=lambda p: p.name.lower()
        )

        self.folder = folder

        self.path_label.setText(
            str(folder)
        )

        self.view.set_files(
            [
                str(path)
                for path in files
            ]
        )

        self.name_edit.clear()

        print(
            "=" * 72
        )

        print(
            f"[文件夹] {folder}"
        )

        print(
            f"[总计] {len(files)} 张图片"
        )

        print(
            "=" * 72,
            flush=True,
        )

        if not files:

            self.statusBar().showMessage(
                "该文件夹中没有支持的图片"
            )

            return

        self.statusBar().showMessage(
            f"共 {len(files)} 张图片，正在按需读取"
        )

        # 首次读取当前可视区域
        self.ensure_visible_loaded(
            *self.view.visible_range()
        )

    # ========================================================
    # 按需加载图片
    # ========================================================

    def ensure_visible_loaded(
        self,
        lo,
        hi,
    ):

        if (
            not self.view.paths
            or hi < lo
        ):
            return

        # ----------------------------------------------------
        # 当前可视区域 + 少量预读
        # ----------------------------------------------------

        lo2 = max(
            0,
            lo
            - self.view.columns() * 2,
        )

        hi2 = min(
            len(self.view.paths) - 1,
            hi
            + self.view.columns() * 2,
        )

        missing = [
            (
                i,
                self.view.paths[i],
            )
            for i in range(
                lo2,
                hi2 + 1,
            )
            if (
                i not in self.view.images
                and i not in self.view.errors
            )
        ]

        if not missing:
            return

        # 当前已有读取线程
        if self.loader_thread is not None:
            return

        self.loader_thread = QThread(
            self
        )

        self.loader = ImageLoader()

        self.loader.set_queue(
            missing
        )

        self.loader.moveToThread(
            self.loader_thread
        )

        self.loader_thread.started.connect(
            self.loader.run
        )

        self.loader.loaded.connect(
            self.view.set_image
        )

        self.loader.failed.connect(
            self.view.set_error
        )

        self.loader.finished.connect(
            self.loader_thread.quit
        )

        self.loader.finished.connect(
            self.loader_finished
        )

        self.loader_thread.finished.connect(
            self.loader_thread.deleteLater
        )

        self.loader_thread.start()

        total = len(
            self.view.paths
        )

        self.statusBar().showMessage(
            f"当前读取/显示："
            f"{lo2 + 1}~{hi2 + 1} / {total}"
        )

    # ========================================================
    # 读取线程完成
    # ========================================================

    def loader_finished(self):

        self.loader = None

        self.loader_thread = None

        QTimer.singleShot(
            0,
            lambda: self.ensure_visible_loaded(
                *self.view.visible_range()
            ),
        )

    # ========================================================
    # 单图模式：按需读取完整画质图片
    # ========================================================

    def ensure_hq_loaded(self):

        if (
            not self.view.paths
            or self.view.columns() != 1
        ):
            return

        # ----------------------------------------------------
        # 当前实际可见的图片（单图模式下一行一张）
        # ----------------------------------------------------

        scroll_y = (
            self.view.verticalScrollBar().value()
        )

        tile_height = max(
            1,
            self.view.tile_height(),
        )

        viewport_height = (
            self.view.viewport().height()
        )

        first_row = scroll_y // tile_height

        last_row = min(
            len(self.view.paths) - 1,
            (scroll_y + viewport_height - 1)
            // tile_height,
        )

        needed = []

        for i in range(
            first_row,
            last_row + 1,
        ):

            path = self.view.paths[i]

            # ------------------------------------------------
            # 非 RAW 图片本身已经是完整画质，无需重复读取
            # ------------------------------------------------

            if (
                Path(path).suffix.lower()
                not in RAW_EXTS
            ):
                continue

            if (
                i in self.view.hq_images
                or i in self.view.hq_failed
            ):
                continue

            needed.append(
                (i, path)
            )

        if not needed:
            return

        # 已有完整画质读取线程在运行
        if self.hq_thread is not None:
            return

        self.hq_thread = QThread(self)

        self.hq_loader = ImageLoader(full=True)

        self.hq_loader.set_queue(needed)

        self.hq_loader.moveToThread(
            self.hq_thread
        )

        self.hq_thread.started.connect(
            self.hq_loader.run
        )

        self.hq_loader.loaded.connect(
            self.on_hq_loaded
        )

        self.hq_loader.failed.connect(
            self.on_hq_failed
        )

        self.hq_loader.finished.connect(
            self.hq_thread.quit
        )

        self.hq_loader.finished.connect(
            self.hq_finished
        )

        self.hq_thread.finished.connect(
            self.hq_thread.deleteLater
        )

        self.hq_thread.start()

    # ========================================================
    # 完整画质读取完成
    # ========================================================

    def on_hq_loaded(self, index, image):

        # 忽略已失效（例如切换文件夹后）的读取结果
        if self.sender() is not self.hq_loader:
            return

        self.view.set_hq_image(index, image)

    # ========================================================
    # 完整画质读取失败
    # ========================================================

    def on_hq_failed(self, index, error):

        if self.sender() is not self.hq_loader:
            return

        self.view.hq_failed.add(index)

        if 0 <= index < len(self.view.paths):
            name = Path(self.view.paths[index]).name
        else:
            name = str(index)

        print(
            f"[完整画质失败] {name} -> {error}",
            flush=True,
        )

    # ========================================================
    # 完整画质读取线程完成
    # ========================================================

    def hq_finished(self):

        self.hq_loader = None

        self.hq_thread = None

        QTimer.singleShot(
            0,
            self.ensure_hq_loaded,
        )

    # ========================================================
    # 停止读取线程
    # ========================================================

    def stop_loader(self):

        if self.loader is not None:

            self.loader.stop()

        if self.loader_thread is not None:

            self.loader_thread.quit()

            self.loader_thread.wait(
                1500
            )

        self.loader = None

        self.loader_thread = None

        # ----------------------------------------------------
        # 完整画质读取线程
        # ----------------------------------------------------

        if self.hq_loader is not None:

            self.hq_loader.stop()

        if self.hq_thread is not None:

            self.hq_thread.quit()

            self.hq_thread.wait(
                1500
            )

        self.hq_loader = None

        self.hq_thread = None

    # ========================================================
    # 拆分输入文件名
    # ========================================================

    @staticmethod
    def split_tokens(text):

        return [
            x.strip()
            for x in re.split(
                r"[,，]",
                text,
            )
            if x.strip()
        ]

    # ========================================================
    # 匹配文件名
    # ========================================================

    def match_names(self):

        if not self.view.paths:
            return

        tokens = self.split_tokens(
            self.name_edit.text()
        )

        if not tokens:

            self.name_edit.clear()

            self.view.checked.clear()

            self.view.viewport().update()

            return

        matched = []

        lower_names = [
            Path(path).name.lower()
            for path in self.view.paths
        ]

        used = set()

        # ----------------------------------------------------
        # 每个输入项：
        #
        # 1. 完整文件名优先
        # 2. 文件名包含该字符串
        #
        # 每个 token 最多匹配一个文件
        # ----------------------------------------------------

        for token in tokens:

            token_lower = (
                token.lower()
            )

            candidates = []

            # ------------------------------------------------
            # 完整文件名
            # ------------------------------------------------

            for i, name in enumerate(
                lower_names
            ):

                if (
                    i not in used
                    and name == token_lower
                ):

                    candidates.append(i)

            # ------------------------------------------------
            # 文件名包含 token
            # ------------------------------------------------

            if not candidates:

                for i, name in enumerate(
                    lower_names
                ):

                    if (
                        i not in used
                        and token_lower in name
                    ):

                        candidates.append(i)

            if candidates:

                index = candidates[0]

                used.add(index)

                matched.append(
                    index
                )

        self.view.checked = set(
            matched
        )

        self.view.last_clicked_index = (
            matched[-1]
            if matched
            else None
        )

        self.name_edit.setText(
            ",".join(
                Path(
                    self.view.paths[i]
                ).name
                for i in matched
            )
        )

        self.view.viewport().update()

        print(
            f"[匹配] 输入 {len(tokens)} 项，"
            f"成功匹配 {len(matched)} 项",
            flush=True,
        )

    # ========================================================
    # 勾选状态同步到输入框
    # ========================================================

    def sync_checked_to_edit(self):

        names = [
            Path(
                self.view.paths[i]
            ).name
            for i in sorted(
                self.view.checked
            )
        ]

        self.name_edit.setText(
            ",".join(names)
        )

    # ========================================================
    # 查找下一个筛选目录
    # ========================================================

    def next_filter_folder(self):

        assert self.folder is not None

        number = 1

        while True:

            candidate = (
                self.folder
                / f"筛选_{number:02d}"
            )

            if not candidate.exists():

                return candidate

            number += 1

    # ========================================================
    # 获取当前要处理的文件 index
    # ========================================================

    def selected_indices(self):

        # 先根据输入框内容重新匹配
        self.match_names()

        return sorted(
            self.view.checked
        )

    # ========================================================
    # 操作完成：提示 + 清空勾选
    # ========================================================

    def _after_transfer(
        self,
        title,
        message,
        status,
        success,
        reload=False,
    ):

        QMessageBox.information(
            self,
            title,
            message,
        )

        self.statusBar().showMessage(
            status
        )

        # 成功后取消所有勾选并清空输入框
        if success:

            self.view.checked.clear()

            self.view.last_clicked_index = None

            self.name_edit.clear()

            self.view.viewport().update()

        # 移动成功后刷新列表（源文件已不在原文件夹）
        if reload and self.folder is not None:

            self.load_folder(self.folder)

    # ========================================================
    # 复制 / 剪贴到新筛选文件夹
    #
    # 新建 筛选_xx 文件夹：
    # 从 1 开始取最小的、当前未被占用的编号。
    # ========================================================

    def _transfer_to_new_folder(self, move):

        if self.folder is None:

            QMessageBox.warning(
                self,
                "提示",
                "请先打开图片文件夹。",
            )

            return

        indices = self.selected_indices()

        if not indices:

            QMessageBox.information(
                self,
                "提示",
                "没有匹配到任何文件。",
            )

            return

        target = self.next_filter_folder()

        target.mkdir(
            parents=True,
            exist_ok=False,
        )

        verb = "移动" if move else "复制"

        count = 0

        failed = []

        for index in indices:

            source = Path(
                self.view.paths[index]
            )

            destination = (
                target
                / source.name
            )

            try:

                if move:

                    shutil.move(
                        str(source),
                        str(destination),
                    )

                else:

                    shutil.copy2(
                        source,
                        destination,
                    )

                count += 1

                print(
                    f"[{verb}] "
                    f"{count}/{len(indices)}  "
                    f"{source.name}",
                    flush=True,
                )

            except Exception as e:

                failed.append(
                    (
                        source.name,
                        str(e),
                    )
                )

                print(
                    f"[{verb}失败] "
                    f"{source.name}: {e}",
                    flush=True,
                )

        # ----------------------------------------------------
        # 完成提示
        # ----------------------------------------------------

        message = (
            f"已{verb} {count} 个文件到：\n"
            f"{target}"
        )

        if failed:

            message += (
                f"\n\n失败 {len(failed)} 个。"
            )

        self._after_transfer(
            f"{verb}完成",
            message,
            f"{verb}完成：{count} 个文件 -> "
            f"{target.name}",
            count > 0,
            reload=move,
        )

    # ========================================================
    # 复制到新筛选文件夹
    # ========================================================

    def copy_to_new_folder(self):

        self._transfer_to_new_folder(move=False)

    # ========================================================
    # 移动到新筛选文件夹
    # ========================================================

    def move_to_new_folder(self):

        self._transfer_to_new_folder(move=True)

    # ========================================================
    # 复制 / 移动到指定文件夹
    #
    # 使用系统自带的文件操作，
    # 遇到同名文件时弹出系统原生的冲突对话框，
    # 由用户选择如何处理。
    # ========================================================

    def _transfer_to_folder(self, move):

        indices = self.selected_indices()

        if not indices:

            QMessageBox.information(
                self,
                "提示",
                "没有匹配到任何文件。",
            )

            return

        verb = "移动" if move else "复制"

        target = QFileDialog.getExistingDirectory(
            self,
            f"选择要{verb}到的文件夹",
            str(Path.home()),
        )

        if not target:

            return

        sources = [
            self.view.paths[index]
            for index in indices
        ]

        native_ok = False

        try:

            result, aborted = shell_file_operation(
                FO_MOVE if move else FO_COPY,
                sources,
                target,
                f"正在{verb}...",
            )

            native_ok = (
                result == 0
                and not aborted
            )

        except Exception as e:

            print(
                f"[原生文件操作异常] {e}",
                flush=True,
            )

        # ----------------------------------------------------
        # 原生操作失败时，退回 Python 方案（带冲突提示）
        # ----------------------------------------------------

        if not native_ok:

            print(
                "[原生文件操作失败，改用 Python 方案]",
                flush=True,
            )

            count, skipped, failed = (
                self._python_transfer(
                    sources,
                    target,
                    move,
                )
            )

            if count == 0 and skipped == 0:

                QMessageBox.warning(
                    self,
                    "提示",
                    f"{verb}未完成。",
                )

                return

            message = (
                f"已{verb} {count} 个文件到：\n"
                f"{target}"
            )

            if skipped:

                message += (
                    f"\n\n跳过 {skipped} 个。"
                )

            if failed:

                message += (
                    f"\n\n失败 {len(failed)} 个。"
                )

            self._after_transfer(
                f"{verb}完成",
                message,
                f"{verb}完成：{count} 个文件 -> "
                f"{Path(target).name}",
                True,
                reload=move,
            )

            return

        self._after_transfer(
            f"{verb}完成",
            f"{verb}操作已完成。\n"
            f"目标文件夹：\n{target}",
            f"{verb}完成 -> {target}",
            True,
            reload=move,
        )

    # ========================================================
    # Python 复制 / 移动（带冲突提示，作为原生操作的备用）
    # ========================================================

    def _python_transfer(
        self,
        sources,
        target,
        move,
    ):

        replace_all = False
        skip_all = False

        count = 0
        skipped = 0
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
                    box.setIcon(
                        QMessageBox.Icon.Question
                    )
                    box.setText(
                        "目标文件夹中已存在同名文件：\n"
                        f"{src_path.name}"
                    )

                    btn_yes = box.addButton(
                        "替换",
                        QMessageBox.ButtonRole.YesRole,
                    )
                    btn_yes_all = box.addButton(
                        "全部替换",
                        QMessageBox.ButtonRole.YesRole,
                    )
                    btn_no = box.addButton(
                        "跳过",
                        QMessageBox.ButtonRole.NoRole,
                    )
                    btn_no_all = box.addButton(
                        "全部跳过",
                        QMessageBox.ButtonRole.NoRole,
                    )

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

                    shutil.move(
                        str(src_path),
                        str(dst_path),
                    )

                else:

                    shutil.copy2(
                        src_path,
                        dst_path,
                    )

                count += 1

            except Exception as e:

                failed.append(
                    (
                        src_path.name,
                        str(e),
                    )
                )

                print(
                    f"[Python 文件操作失败] "
                    f"{src_path.name}: {e}",
                    flush=True,
                )

        return count, skipped, failed

    # ========================================================
    # 复制到指定文件夹
    # ========================================================

    def copy_to_folder(self):

        self._transfer_to_folder(move=False)

    # ========================================================
    # 移动到指定文件夹
    # ========================================================

    def move_to_folder(self):

        self._transfer_to_folder(move=True)

    # ========================================================
    # 移动到回收站
    # ========================================================

    def move_to_recycle_bin(self):

        indices = self.selected_indices()

        if not indices:

            QMessageBox.information(
                self,
                "提示",
                "没有匹配到任何文件。",
            )

            return

        # ----------------------------------------------------
        # 确认弹窗（默认「是」，回车选择「是」）
        # ----------------------------------------------------

        answer = QMessageBox.question(
            self,
            "移动到回收站",
            f"确定将选中的 {len(indices)} 个文件"
            f"移动到回收站吗？",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if (
            answer
            != QMessageBox.StandardButton.Yes
        ):

            return

        sources = [
            self.view.paths[index]
            for index in indices
        ]

        # ----------------------------------------------------
        # 原生操作
        # ----------------------------------------------------

        ok = False

        try:

            result, aborted = (
                shell_delete_to_recycle_bin(
                    sources
                )
            )

            ok = result == 0 and not aborted

        except Exception as e:

            print(
                f"[原生删除异常] {e}",
                flush=True,
            )

        # ----------------------------------------------------
        # 原生失败时，退回 PowerShell 方案
        # ----------------------------------------------------

        if not ok:

            print(
                "[原生删除失败，改用 PowerShell 方案]",
                flush=True,
            )

            try:

                ok = (
                    powershell_recycle(sources)
                    == 0
                )

            except Exception as e:

                print(
                    f"[PowerShell 回收站异常] {e}",
                    flush=True,
                )

        if not ok:

            QMessageBox.warning(
                self,
                "提示",
                "移动到回收站未完成。",
            )

            return

        self._after_transfer(
            "已移动到回收站",
            f"已将 {len(sources)} 个文件"
            f"移动到回收站。",
            f"已移动到回收站："
            f"{len(sources)} 个文件",
            True,
            reload=True,
        )

    # ========================================================
    # 关闭窗口
    # ========================================================

    def closeEvent(
        self,
        event,
    ):

        self.stop_loader()

        event.accept()


# ============================================================
# 程序入口
# ============================================================

def main():

    app = QApplication(
        sys.argv
    )

    app.setApplicationName(
        "RAW 图片批量筛选器"
    )

    window = MainWindow()

    window.show()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":

    main()