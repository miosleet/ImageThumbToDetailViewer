#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
选片助手工作台（ImageThumbToDetailViewer v4）

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
    python ImageThumbToDetailViewer_v4.py
"""

import ctypes
import gc
import math
import os
import re
import shutil
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps
import rawpy

from PySide6.QtCore import (
    Qt,
    QObject,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    QThread,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QImageReader,
    QIntValidator,
    QKeySequence,
    QPainter,
    QPalette,
    QPen,
    QShortcut,
    QTransform,
)
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


# ============================================================
# 现代化深色主题
#
# 统一的自绘控件样式：圆角、无原生白底方框按钮，
# 层次分明的灰阶配色 + 单一蓝色强调色，整体简洁、现代。
# ============================================================

# 配色常量（供代码内自绘与样式表共用，保持一致）
COLOR_BG = "#1b1b1d"          # 窗口底色
COLOR_PANEL = "#242427"       # 面板底色
COLOR_SURFACE = "#2e2e34"     # 控件底色
COLOR_BORDER = "#34343c"      # 描边
COLOR_TEXT = "#e6e6e8"        # 主文字
COLOR_TEXT_MUTED = "#8f8f97"  # 次要文字
COLOR_ACCENT = "#3b82f6"      # 强调色
COLOR_DANGER = "#ef4444"      # 危险色

# 图片视图背景（与主题一致）
VIEW_BG = QColor(28, 28, 30)


STYLE_SHEET = """
/* ---------- 窗口 / 面板 ---------- */
QMainWindow, QDialog {
    background-color: #1b1b1d;
}
QWidget {
    color: #e6e6e8;
}
QFrame#Panel {
    background-color: #242427;
    border: 1px solid #33333a;
    border-radius: 12px;
}
QWidget#Editor {
    background-color: #202024;
    border-left: 1px solid #2f2f36;
}

/* ---------- 文本 ---------- */
QLabel {
    background: transparent;
    color: #d6d6da;
}
QLabel#PathLabel {
    color: #8f8f97;
    padding: 0 4px;
}
QLabel#Hint {
    color: #7c7c84;
}
QLabel#Title {
    color: #f0f0f2;
    font-weight: 600;
}
QLabel#Warning {
    color: #ff4d4d;
    font-weight: 600;
}

/* ---------- 按钮 ---------- */
QPushButton {
    background-color: #2e2e34;
    color: #e6e6e8;
    border: 1px solid #3a3a42;
    border-radius: 8px;
    padding: 7px 14px;
}
QPushButton:hover {
    background-color: #3a3a42;
    border-color: #4a4a54;
}
QPushButton:pressed {
    background-color: #26262b;
}
QPushButton:disabled {
    color: #6a6a72;
    background-color: #26262a;
    border-color: #303036;
}
QPushButton[class="primary"] {
    background-color: #3b82f6;
    color: #ffffff;
    border: 1px solid #3b82f6;
    font-weight: 600;
}
QPushButton[class="primary"]:hover {
    background-color: #5594f8;
    border-color: #5594f8;
}
QPushButton[class="primary"]:pressed {
    background-color: #2f6fe0;
    border-color: #2f6fe0;
}
QPushButton[class="danger"] {
    background-color: #3a2529;
    color: #ff9a9a;
    border: 1px solid #573036;
}
QPushButton[class="danger"]:hover {
    background-color: #4a2c31;
    color: #ffb3b3;
    border-color: #6e3a42;
}
QPushButton[class="danger"]:pressed {
    background-color: #331f23;
}
QPushButton[class="field"] {
    text-align: left;
    padding-left: 12px;
    color: #cfcfd4;
}

/* ---------- 输入框 ---------- */
QLineEdit {
    background-color: #1f1f22;
    color: #e6e6e8;
    border: 1px solid #34343c;
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: #3b82f6;
    selection-color: #ffffff;
}
QLineEdit:focus {
    border-color: #3b82f6;
    background-color: #222226;
}

/* ---------- 复选 / 单选 ---------- */
QCheckBox, QRadioButton {
    background: transparent;
    color: #d6d6da;
    spacing: 7px;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
}
QCheckBox::indicator {
    border: 1px solid #4a4a54;
    border-radius: 5px;
    background-color: #1f1f22;
}
QCheckBox::indicator:hover {
    border-color: #3b82f6;
}
QCheckBox::indicator:checked {
    background-color: #3b82f6;
    border-color: #3b82f6;
}
QRadioButton::indicator {
    border: 1px solid #4a4a54;
    border-radius: 8px;
    background-color: #1f1f22;
}
QRadioButton::indicator:hover {
    border-color: #3b82f6;
}
QRadioButton::indicator:checked {
    border: 1px solid #3b82f6;
    background-color: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
        stop:0 #ffffff, stop:0.45 #ffffff, stop:0.5 #3b82f6, stop:1 #3b82f6);
}

/* ---------- 滚动条 ---------- */
QScrollBar:vertical {
    background: transparent;
    width: 12px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #45454f;
    border-radius: 5px;
    min-height: 32px;
}
QScrollBar::handle:vertical:hover {
    background: #56565f;
}
QScrollBar:horizontal {
    background: transparent;
    height: 12px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: #45454f;
    border-radius: 5px;
    min-width: 32px;
}
QScrollBar::handle:horizontal:hover {
    background: #56565f;
}
QScrollBar::add-line, QScrollBar::sub-line {
    width: 0;
    height: 0;
    background: transparent;
}
QScrollBar::add-page, QScrollBar::sub-page {
    background: transparent;
}

/* ---------- 状态栏 / 提示 / 菜单 ---------- */
QStatusBar {
    background-color: #1b1b1d;
    color: #8f8f97;
    border-top: 1px solid #2a2a2f;
}
QStatusBar::item {
    border: none;
}
QToolTip {
    background-color: #2c2c32;
    color: #e6e6e8;
    border: 1px solid #3a3a42;
    border-radius: 6px;
    padding: 4px 8px;
}
QMenu {
    background-color: #242427;
    border: 1px solid #33333a;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 20px;
    border-radius: 6px;
}
QMenu::item:selected {
    background-color: #3b82f6;
    color: #ffffff;
}
"""


def set_button_role(button: QPushButton, role: str):
    """为按钮设置样式角色（primary / danger / field），并立即重新应用样式。"""

    button.setProperty("class", role)
    button.style().unpolish(button)
    button.style().polish(button)


def apply_dark_palette(app: QApplication):
    """设置应用级深色调色板，保证原生控件与自绘样式一致。"""

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(COLOR_BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(COLOR_TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor("#1f1f22"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#242427"))
    palette.setColor(QPalette.ColorRole.Text, QColor(COLOR_TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(COLOR_SURFACE))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(COLOR_TEXT))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#2c2c32"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(COLOR_TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(COLOR_ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#6f6f76"))
    app.setPalette(palette)


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
# 预览图分辨率（内存占用控制）
#
# 网格预览始终按「最长边上限」降采样读取，从而显著降低内存占用；
# 单图模式仍读取完整尺寸原图。
# 如需调整预览分辨率，修改下面这一行的 PREVIEW_MAX_EDGE 即可（单位：像素）。
# ============================================================

PREVIEW_MAX_EDGE = 1280


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


def qimage_to_pil(qimage: QImage) -> Image.Image:
    """QImage -> PIL。逐行拼接，兼容 Qt 对齐产生的行间填充。"""

    qimage = qimage.convertToFormat(QImage.Format.Format_RGB888)
    width = qimage.width()
    height = qimage.height()
    bytes_per_line = qimage.bytesPerLine()
    data = bytes(qimage.constBits()[: qimage.sizeInBytes()])

    rows = [
        data[y * bytes_per_line: y * bytes_per_line + width * 3]
        for y in range(height)
    ]
    return Image.frombytes("RGB", (width, height), b"".join(rows))


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


def downscale_pil(image: Image.Image, max_edge: int) -> Image.Image:
    """把 PIL 图像的最长边限制到 max_edge（等比且不放大）。"""

    width, height = image.size

    if max_edge <= 0 or max(width, height) <= max_edge:
        return image

    result = image.copy()
    result.thumbnail((max_edge, max_edge), Image.LANCZOS)
    return result


def read_scaled_qimage(path: str, max_edge: int):
    """
    用 QImageReader 按最长边 max_edge 等比降采样读取普通图片。

    QImageReader 可在解码阶段直接缩小（例如 JPEG 支持按比例解码），
    比「先读入完整图像再缩放」更省内存。读取失败返回 None，由调用方回退。
    """

    reader = QImageReader(path)
    reader.setAutoTransform(True)

    size = reader.size()

    if size.isValid() and max_edge > 0:
        if size.width() > max_edge or size.height() > max_edge:
            reader.setScaledSize(
                size.scaled(max_edge, max_edge, Qt.AspectRatioMode.KeepAspectRatio)
            )

    image = reader.read()

    return None if image.isNull() else image


def load_image(path: str, full: bool = False, max_edge: int = None) -> QImage:
    """
    读取图片。

    full=True ：完整分辨率读取（单图模式的最高画质）。
    max_edge  ：>0 时把最长边限制到该值（网格预览降采样，用于降低内存占用）。
    RAW 走 rawpy；普通图片在需要降采样时走 QImageReader 以在解码阶段缩小。
    """

    suffix = Path(path).suffix.lower()

    if suffix in RAW_EXTS:
        image = raw_to_pil(path, full=full)
        if not full and max_edge:
            image = downscale_pil(image, max_edge)
        return pil_to_qimage(image)

    if not full and max_edge:
        scaled = read_scaled_qimage(path, max_edge)
        if scaled is not None:
            return scaled

    with Image.open(path) as im:
        return pil_to_qimage(im.copy())


# ============================================================
# 图片调整导出
#
# 读取完整图像、按需缩放 / 裁切 / 切片、控制导出文件大小，
# 并最终写出到目标文件夹。
# ============================================================


def load_source_image(path: str) -> Image.Image:
    """
    以完整分辨率读取一张图片，返回完成 EXIF 方向校正的 PIL 图像。

    RAW 走 rawpy 完整解码；普通图片直接读取并应用 EXIF 方向，
    以保证转换时使用的图像与界面中看到的朝向一致。
    """

    if Path(path).suffix.lower() in RAW_EXTS:
        return raw_to_pil(path, full=True)

    with Image.open(path) as im:
        return ImageOps.exif_transpose(im).copy()


def resize_to_long_edge(image: Image.Image, long_edge: int) -> Image.Image:
    """
    等比缩放图片，使最长边等于 long_edge，短边按比例缩放（允许放大）。

    长边为宽时按宽命中，长边为高时按高命中。
    """

    width, height = image.size

    if width >= height:
        new_w = long_edge
        new_h = max(1, round(height * long_edge / width))
    else:
        new_h = long_edge
        new_w = max(1, round(width * long_edge / height))

    return image.resize((new_w, new_h), Image.LANCZOS)


def encode_image(image: Image.Image, fmt: str, quality: int = None) -> bytes:
    """
    把 PIL 图像编码为指定格式的字节数据。

    fmt 为 "JPEG" 或 "PNG"；quality 仅对 JPEG 有效（对应 PS 中的品质，1~100）。
    PNG 为无损格式，统一使用 optimize 尽量减小体积。
    """

    buffer = BytesIO()

    if fmt == "JPEG":
        if image.mode != "RGB":
            image = image.convert("RGB")
        quality = quality if quality else 100
        image.save(
            buffer,
            format="JPEG",
            quality=quality,
            # 品质 95 以上不做色度子采样，保证最高画质
            subsampling=0 if quality >= 95 else 2,
        )
    else:
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")
        image.save(buffer, format="PNG", optimize=True)

    return buffer.getvalue()


def find_jpeg_quality(image: Image.Image, max_bytes: int):
    """
    二分查找 JPEG 品质：在文件体积小于 max_bytes 的前提下，返回尽量大的品质值。

    返回 (quality, data)：quality 为命中的品质，data 为对应编码字节；
    若最低品质仍超过限制，则 quality 为 None，data 为最小体积的编码结果。
    """

    low, high = 1, 100
    best_quality = None
    best_data = None

    while low <= high:

        middle = (low + high) // 2
        data = encode_image(image, "JPEG", middle)

        if len(data) < max_bytes:
            best_quality, best_data = middle, data
            low = middle + 1
        else:
            high = middle - 1

    if best_data is None:
        best_data = encode_image(image, "JPEG", 1)

    return best_quality, best_data


def encode_with_limit(image: Image.Image, fmt: str, max_bytes: int):
    """
    按目标格式与体积上限编码，返回 (data, quality)。

    JPEG 在给定体积上限下二分查找最高品质；PNG 为无损格式，
    体积仅由分辨率决定，故忽略上限（返回的 quality 为 None）。
    """

    if fmt == "JPEG":
        if max_bytes:
            quality, data = find_jpeg_quality(image, max_bytes)
            return data, quality
        return encode_image(image, "JPEG", 100), None

    return encode_image(image, "PNG"), None


def unique_stem(folder, stem: str, ext: str) -> str:
    """
    在 folder 中为「stem + ext」求一个不冲突的文件名（不含后缀部分）。

    规则：无冲突时返回 stem；否则依次尝试 stem(1)、stem(2)…，
    例如 aaa.jpg 已存在则返回 aaa(1)，同理 aaa(1).jpg 也存在则返回 aaa(2)。
    """

    folder = Path(folder)

    if not (folder / f"{stem}{ext}").exists():
        return stem

    index = 1
    while (folder / f"{stem}({index}){ext}").exists():
        index += 1

    return f"{stem}({index})"


def unique_folder(parent, name: str) -> Path:
    """
    在 parent 下为 name 求一个不冲突的文件夹路径。

    规则：无冲突时返回 parent/name；否则依次尝试 name(1)、name(2)…
    """

    parent = Path(parent)

    if not (parent / name).exists():
        return parent / name

    index = 1
    while (parent / f"{name}({index})").exists():
        index += 1

    return parent / f"{name}({index})"


def convert_batch_image(path, output_dir, fmt, ext, long_edge, max_bytes):
    """
    批量导出中的单张处理：读取完整图像 -> 按长边等比缩放（可选）
    -> 按体积限制编码 -> 写出到 output_dir。

    返回 (输出路径, 字节数, 使用的品质)；文件名沿用原文件名，
    在目标文件夹内自动避让同名文件（aaa -> aaa(1) -> aaa(2)…）。
    """

    image = load_source_image(path)

    if long_edge:
        image = resize_to_long_edge(image, long_edge)

    data, quality = encode_with_limit(image, fmt, max_bytes)

    stem = unique_stem(output_dir, Path(path).stem, ext)
    target = Path(output_dir) / f"{stem}{ext}"

    with open(target, "wb") as f:
        f.write(data)

    return target, len(data), quality


# ============================================================
# 后台图片读取线程
# ============================================================

class ImageLoader(QObject):

    loaded = Signal(int, QImage)
    failed = Signal(int, str)
    finished = Signal()

    def __init__(self, full=False, max_edge=None):
        super().__init__()
        self._queue = []
        self._running = True
        self._full = full
        self._max_edge = max_edge

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
                image = load_image(path, full=self._full, max_edge=self._max_edge)
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
        painter.fillRect(self.viewport().rect(), VIEW_BG)

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

            painter.fillRect(rect, QColor(70, 32, 36))
            painter.setPen(QColor(255, 160, 160))
            painter.drawText(
                rect.adjusted(8, 8, -8, -8),
                Qt.AlignmentFlag.AlignCenter,
                "读取失败\n" + Path(self.paths[index]).name,
            )

        else:

            painter.fillRect(rect, QColor(42, 42, 46))
            painter.setPen(QColor(150, 150, 156))
            painter.drawText(
                rect.adjusted(5, 5, -5, -5),
                Qt.AlignmentFlag.AlignCenter,
                "读取中…",
            )

        box = QRect(rect.left() + 7, rect.bottom() - 31, 24, 24)
        self._paint_checkbox(painter, index, box)
        self._paint_filename(painter, index, rect, box)

    def _paint_checkbox(self, painter, index, box):

        if index in self.checked:
            # 选中：填充强调色圆角方块
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(COLOR_ACCENT)))
            painter.drawRoundedRect(box, 6, 6)
            painter.setPen(QPen(QColor(255, 255, 255), 2.4))
            painter.drawLine(box.left() + 5, box.top() + 12,
                             box.left() + 10, box.top() + 18)
            painter.drawLine(box.left() + 10, box.top() + 18,
                             box.left() + 20, box.top() + 6)
        else:
            # 未选中：半透明深色圆角方块 + 浅描边
            painter.setPen(QPen(QColor(235, 235, 235, 200), 2))
            painter.setBrush(QBrush(QColor(28, 28, 30, 170)))
            painter.drawRoundedRect(box, 6, 6)

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
# 格式 / 大小 / 分辨率转换配置弹窗
# ============================================================

class BatchExportDialog(QDialog):
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

    @staticmethod
    def _title(text):
        """生成加粗的配置项标题标签。"""

        label = QLabel(text)
        label.setObjectName("Title")
        return label

    def _build_format_row(self):
        """构建「目标格式」标题行与 jpg / png 单选行。"""

        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._title("目标格式"))

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

    def _build_long_edge_row(self):
        """构建「长边最大像素」标题行与单值输入行。"""

        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._title("长边最大像素"))

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

        hint = QLabel("输入后每张图的最长边缩放到该数值，短边按比例缩放。")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        return box

    def _build_size_row(self):
        """构建「文件大小」标题行与 MB 输入行。"""

        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._title("文件大小"))

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

        hint = QLabel("JPG 通过品质控制体积；PNG 为无损格式，体积仅由分辨率决定。")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        return box

    def _build_output_row(self):
        """构建「输出文件」标题行与输出文件夹选择行。"""

        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._title("输出文件"))

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

        hint = QLabel("文件名沿用原文件名，同名文件自动添加序号。")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        return box

    def current_ext(self):
        """返回当前目标格式对应的文件后缀。"""

        return ".jpg" if self.jpg_radio.isChecked() else ".png"

    def choose_output_folder(self):
        """弹出文件夹选择窗口，更新输出文件夹。"""

        folder = QFileDialog.getExistingDirectory(
            self, "选择输出文件夹", str(self.folder)
        )
        if not folder:
            return

        self.folder = Path(folder)
        self.folder_button.setText(str(self.folder))

    # --------------------------------------------------------
    # 收集配置
    # --------------------------------------------------------

    def accept(self):
        """校验输入并收集配置写入 self.options，然后关闭窗口。"""

        options = {}

        # 目标格式
        options["format"] = "JPEG" if self.jpg_radio.isChecked() else "PNG"
        options["ext"] = ".jpg" if options["format"] == "JPEG" else ".png"

        # 长边最大像素（留空则不调整分辨率）
        options["long_edge"] = None
        text = self.long_edge_edit.text().strip()

        if text:
            try:
                long_edge = int(text)
            except ValueError:
                QMessageBox.warning(self, "提示", "长边最大像素请输入正整数（px）。")
                return

            if long_edge <= 0:
                QMessageBox.warning(self, "提示", "长边最大像素请输入正整数（px）。")
                return

            options["long_edge"] = long_edge

        # 文件大小
        options["max_bytes"] = None
        size_text = self.size_edit.text().strip()

        if size_text:
            try:
                megabytes = float(size_text)
            except ValueError:
                QMessageBox.warning(self, "提示", "文件大小请输入数字（MB）。")
                return

            if megabytes <= 0:
                QMessageBox.warning(self, "提示", "文件大小请输入正数（MB）。")
                return

            options["max_bytes"] = int(megabytes * 1024 * 1024)

        # 输出文件
        options["output_dir"] = str(self.folder)

        self.options = options
        super().accept()


# ============================================================
# 单图「图片调整导出」——可视化编辑
# ============================================================

class ImageEditView(QWidget):
    """
    单图调整导出的左侧预览窗。

    以「导出区域」界定最终导出画面：区域内颜色正常，区域外变暗但仍可见。
    提供类似 PS 变形的交互：
        - 四角控制点：拖动等比例缩放（以对角为锚点）；
        - 四边中点控制点：拖动绕图片中心旋转；
        - 按住图片非控制点区域拖动：平移图片；
        - 滚轮：缩放整个编辑画面（导出区域中心始终位于窗口中心）。
    导出区域内还会绘制切片线（亮蓝色）与切片间隔遮罩（黑色）。
    """

    coverageChanged = Signal(bool)

    def __init__(self, image: QImage, out_w: int, out_h: int, parent=None):

        super().__init__(parent)

        self.image = image

        # 图片变换（场景坐标 == 原始图片像素坐标）
        self.image_center = QPointF(image.width() / 2, image.height() / 2)
        self.image_scale = 1.0
        self.image_angle = 0.0

        # 导出区域（场景坐标下的轴对齐矩形）
        self.export_rect = QRectF(0, 0, image.width(), image.height())

        # 输出分辨率与切片参数（切片间隔单位为「输出像素」）
        self.out_w = float(out_w)
        self.out_h = float(out_h)
        self.x_count = 1
        self.x_gap = 0
        self.y_count = 1
        self.y_gap = 0

        self.view_scale = 1.0
        self.view_pan = QPointF(0, 0)     # 视图平移（窗口像素，右键拖动）
        self._fitted = False
        self._covered = True

        # 拖拽状态
        self._drag_mode = None            # "corner" / "rotate" / "move"
        self._drag_start = QPointF()
        self._start_scale = 1.0
        self._start_angle = 0.0
        self._start_center = QPointF()
        self._anchor = QPointF()          # 角缩放时的对角锚点（场景坐标）
        self._start_dist = 1.0
        self._start_mouse_angle = 0.0

        # 右键平移查看范围的状态
        self._panning = False
        self._pan_start = QPointF()
        self._pan_start_view = QPointF()

        self.setMinimumSize(360, 300)
        self.setMouseTracking(True)

        self._refresh_coverage()

    # --------------------------------------------------------
    # 尺寸 / 参数
    # --------------------------------------------------------

    def set_output_size(self, out_w, out_h):
        """更新输出分辨率，并按新的宽高比调整导出区域（保持中心与宽度）。"""

        if out_w <= 0 or out_h <= 0:
            return

        self.out_w = float(out_w)
        self.out_h = float(out_h)

        center = self.export_rect.center()
        width = self.export_rect.width()
        height = width * self.out_h / self.out_w
        self.export_rect = QRectF(
            center.x() - width / 2, center.y() - height / 2, width, height
        )
        self._refresh_coverage()
        self.update()

    def set_slices(self, x_count, x_gap, y_count, y_gap):
        """更新切片参数（数量≥1、间隔≥0，间隔单位为输出像素）。"""

        self.x_count = max(1, int(x_count))
        self.x_gap = max(0, int(x_gap))
        self.y_count = max(1, int(y_count))
        self.y_gap = max(0, int(y_gap))
        self.update()

    # --------------------------------------------------------
    # 覆盖检测
    # --------------------------------------------------------

    @staticmethod
    def _point_in_quad(point: QPointF, quad) -> bool:
        """判断点是否落在凸四边形内（边界视为在内）。"""

        sign = 0
        count = len(quad)

        for i in range(count):
            a = quad[i]
            b = quad[(i + 1) % count]
            cross = ((b.x() - a.x()) * (point.y() - a.y())
                     - (b.y() - a.y()) * (point.x() - a.x()))
            if abs(cross) < 1e-9:
                continue
            current = 1 if cross > 0 else -1
            if sign == 0:
                sign = current
            elif current != sign:
                return False

        return True

    def is_covered(self) -> bool:
        """导出区域是否被图片完全覆盖（导出区域四角都落在图片四边形内）。"""

        quad = self._corner_points_scene()
        rect = self.export_rect
        corners = [
            QPointF(rect.left(), rect.top()),
            QPointF(rect.right(), rect.top()),
            QPointF(rect.right(), rect.bottom()),
            QPointF(rect.left(), rect.bottom()),
        ]
        return all(self._point_in_quad(point, quad) for point in corners)

    def _refresh_coverage(self):
        """重新计算覆盖状态，并在变化时发出信号。"""

        covered = self.is_covered()
        if covered != self._covered:
            self._covered = covered
            self.coverageChanged.emit(covered)
        return covered

    def reset(self):
        """恢复到刚导入的状态（撤销缩放 / 旋转 / 平移 / 导出区域 / 切分）。"""

        self.image_center = QPointF(self.image.width() / 2, self.image.height() / 2)
        self.image_scale = 1.0
        self.image_angle = 0.0
        self.export_rect = QRectF(0, 0, self.image.width(), self.image.height())
        self.out_w = float(self.image.width())
        self.out_h = float(self.image.height())
        self.x_count = 1
        self.x_gap = 0
        self.y_count = 1
        self.y_gap = 0

        self.view_pan = QPointF(0, 0)
        self._refresh_coverage()
        self.fit_view()

    # --------------------------------------------------------
    # 坐标变换
    # --------------------------------------------------------

    def _view_transform(self):
        """返回 (缩放, 平移x, 平移y)，导出区域中心默认位于窗口中心，可被右键平移。"""

        scale = self.view_scale
        center = self.export_rect.center()
        tx = self.width() / 2 - center.x() * scale + self.view_pan.x()
        ty = self.height() / 2 - center.y() * scale + self.view_pan.y()
        return scale, tx, ty

    def scene_to_widget(self, point: QPointF) -> QPointF:
        scale, tx, ty = self._view_transform()
        return QPointF(point.x() * scale + tx, point.y() * scale + ty)

    def widget_to_scene(self, point: QPointF) -> QPointF:
        scale, tx, ty = self._view_transform()
        return QPointF((point.x() - tx) / scale, (point.y() - ty) / scale)

    def _visible_scene_rect(self) -> QRectF:
        scale, tx, ty = self._view_transform()
        left = -tx / scale
        top = -ty / scale
        right = (self.width() - tx) / scale
        bottom = (self.height() - ty) / scale
        return QRectF(left, top, right - left, bottom - top)

    def image_transform(self) -> QTransform:
        transform = QTransform()
        transform.translate(self.image_center.x(), self.image_center.y())
        transform.rotate(self.image_angle)
        transform.scale(self.image_scale, self.image_scale)
        return transform

    def _corner_points_scene(self):
        transform = self.image_transform()
        half_w = self.image.width() / 2
        half_h = self.image.height() / 2
        return [
            transform.map(QPointF(-half_w, -half_h)),
            transform.map(QPointF(half_w, -half_h)),
            transform.map(QPointF(half_w, half_h)),
            transform.map(QPointF(-half_w, half_h)),
        ]

    @staticmethod
    def _midpoint(a: QPointF, b: QPointF) -> QPointF:
        return QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2)

    def _mid_points_scene(self):
        corners = self._corner_points_scene()
        return [
            self._midpoint(corners[0], corners[1]),
            self._midpoint(corners[1], corners[2]),
            self._midpoint(corners[2], corners[3]),
            self._midpoint(corners[3], corners[0]),
        ]

    def _handles(self):
        """返回 [(类型, 序号, 窗口坐标点)]，类型为 corner / rotate。"""

        handles = []
        for index, point in enumerate(self._corner_points_scene()):
            handles.append(("corner", index, self.scene_to_widget(point)))
        for index, point in enumerate(self._mid_points_scene()):
            handles.append(("rotate", index, self.scene_to_widget(point)))
        return handles

    def _image_contains_scene(self, point: QPointF) -> bool:
        inverted, ok = self.image_transform().inverted()
        if not ok:
            return False
        local = inverted.map(point)
        return (abs(local.x()) <= self.image.width() / 2
                and abs(local.y()) <= self.image.height() / 2)

    def fit_view(self):
        """把导出区域缩放到窗口内（留出边距），仅在首次显示时调用。"""

        rect = self.export_rect
        if rect.width() <= 0 or rect.height() <= 0:
            return
        margin = 0.9
        scale_x = self.width() * margin / rect.width()
        scale_y = self.height() * margin / rect.height()
        self.view_scale = max(0.01, min(scale_x, scale_y))
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._fitted:
            self._fitted = True
            self.fit_view()

    # --------------------------------------------------------
    # 绘制
    # --------------------------------------------------------

    def _draw_image(self, painter):
        painter.save()
        painter.translate(self.image_center)
        painter.rotate(self.image_angle)
        painter.scale(self.image_scale, self.image_scale)
        painter.drawImage(
            QRectF(-self.image.width() / 2, -self.image.height() / 2,
                   self.image.width(), self.image.height()),
            self.image,
        )
        painter.restore()

    def paintEvent(self, event):

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), QColor(24, 24, 26))

        scale, tx, ty = self._view_transform()

        painter.save()
        painter.translate(tx, ty)
        painter.scale(scale, scale)

        visible = self._visible_scene_rect()

        # 图片
        self._draw_image(painter)

        # 导出区域以外整体变暗
        painter.fillRect(visible, QColor(0, 0, 0, 150))

        # 导出区域内恢复正常亮度（先铺红色底再重绘图片，
        # 原图未覆盖处即露出红色，提示该区域将不被原图覆盖）
        painter.save()
        painter.setClipRect(self.export_rect)
        painter.fillRect(self.export_rect, QColor(0xFF, 0x00, 0x00))
        self._draw_image(painter)
        painter.restore()

        # 切片间隔遮罩 + 切片线
        self._paint_slices(painter)

        # 导出区域边框
        border = QPen(QColor(235, 235, 240))
        border.setCosmetic(True)
        painter.setPen(border)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.export_rect)

        painter.restore()

        # 控制点（窗口坐标，尺寸恒定）
        self._paint_handles(painter)

        # 底部操作提示
        self._paint_hint(painter)

        painter.end()

    def _paint_slices(self, painter):

        rect = self.export_rect
        if self.out_w <= 0 or self.out_h <= 0 or rect.width() <= 0:
            return

        scale_x = rect.width() / self.out_w
        scale_y = rect.height() / self.out_h

        slice_w = (self.out_w - (self.x_count - 1) * self.x_gap) / self.x_count
        slice_h = (self.out_h - (self.y_count - 1) * self.y_gap) / self.y_count

        if slice_w <= 0 or slice_h <= 0:
            return

        # 间隔遮罩（黑色）
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 220)))

        if self.x_count > 1 and self.x_gap > 0:
            step = slice_w + self.x_gap
            for i in range(self.x_count - 1):
                left = step * (i + 1) - self.x_gap
                painter.drawRect(QRectF(
                    rect.left() + left * scale_x, rect.top(),
                    self.x_gap * scale_x, rect.height(),
                ))

        if self.y_count > 1 and self.y_gap > 0:
            step = slice_h + self.y_gap
            for i in range(self.y_count - 1):
                top = step * (i + 1) - self.y_gap
                painter.drawRect(QRectF(
                    rect.left(), rect.top() + top * scale_y,
                    rect.width(), self.y_gap * scale_y,
                ))

        # 切片线（亮蓝色，1px）
        line_pen = QPen(QColor(0x38, 0x4A, 0xFF))
        line_pen.setCosmetic(True)
        painter.setPen(line_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        x_step = slice_w + self.x_gap
        for i in range(self.x_count):
            for offset in (x_step * i, x_step * i + slice_w):
                x = rect.left() + offset * scale_x
                painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))

        y_step = slice_h + self.y_gap
        for i in range(self.y_count):
            for offset in (y_step * i, y_step * i + slice_h):
                y = rect.top() + offset * scale_y
                painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))

    def _paint_handles(self, painter):

        radius = 5
        painter.setPen(QPen(QColor(0x3B, 0x82, 0xF6), 2))
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        for _, _, point in self._handles():
            painter.drawRect(QRectF(
                point.x() - radius, point.y() - radius, radius * 2, radius * 2
            ))

    def _paint_hint(self, painter):
        """在预览窗最下边绘制白色操作提示。"""

        text = ("拖动四角锚点：缩放 / 拖动四边锚点：旋转 / 左键拖动：移动图片位置 / "
                "鼠标滚轮：缩放查看 / 右键拖动：移动查看范围")

        margin = 8
        width = max(1, self.width() - margin * 2)
        flags = int(Qt.AlignmentFlag.AlignCenter) | int(Qt.TextFlag.TextWordWrap)

        bounds = painter.fontMetrics().boundingRect(
            0, 0, width, 10000, int(Qt.TextFlag.TextWordWrap), text
        )
        bar = QRectF(
            margin, self.height() - bounds.height() - margin - 6,
            width, bounds.height() + 6,
        )

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 140)))
        painter.drawRoundedRect(bar, 8, 8)

        painter.setPen(QColor(255, 255, 255))
        painter.drawText(bar, flags, text)

    # --------------------------------------------------------
    # 交互
    # --------------------------------------------------------

    @staticmethod
    def _distance(a: QPointF, b: QPointF) -> float:
        return math.hypot(a.x() - b.x(), a.y() - b.y())

    def _handle_at(self, pos: QPointF):
        for kind, index, point in self._handles():
            if self._distance(pos, point) <= 9:
                return kind, index
        return None

    def mousePressEvent(self, event):

        # 右键拖动：仅平移查看范围，不影响图片在导出图中的位置
        if event.button() == Qt.MouseButton.RightButton:
            self._panning = True
            self._pan_start = event.position()
            self._pan_start_view = QPointF(self.view_pan)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        pos = event.position()
        self._drag_start = pos
        hit = self._handle_at(pos)

        if hit is not None:
            kind, index = hit
            if kind == "corner":
                self._drag_mode = "corner"
                corners = self._corner_points_scene()
                self._anchor = corners[(index + 2) % 4]     # 对角作为缩放锚点
                self._start_scale = self.image_scale
                self._start_center = QPointF(self.image_center)
                self._start_dist = max(
                    1e-6, self._distance(self._anchor, self.widget_to_scene(pos))
                )
            else:
                self._drag_mode = "rotate"
                self._start_angle = self.image_angle
                center_w = self.scene_to_widget(self.image_center)
                self._start_mouse_angle = math.degrees(
                    math.atan2(pos.y() - center_w.y(), pos.x() - center_w.x())
                )
            return

        if self._image_contains_scene(self.widget_to_scene(pos)):
            self._drag_mode = "move"
            self._start_center = QPointF(self.image_center)
        else:
            self._drag_mode = None

    def mouseMoveEvent(self, event):

        pos = event.position()

        if self._panning:
            self.view_pan = QPointF(
                self._pan_start_view.x() + (pos.x() - self._pan_start.x()),
                self._pan_start_view.y() + (pos.y() - self._pan_start.y()),
            )
            self.update()
            return

        if self._drag_mode is None:
            self._update_cursor(pos)
            return

        if self._drag_mode == "corner":
            scene = self.widget_to_scene(pos)
            ratio = max(0.02, self._distance(self._anchor, scene) / self._start_dist)
            self.image_scale = self._start_scale * ratio
            # 保持对角锚点固定
            self.image_center = QPointF(
                self._anchor.x() + (self._start_center.x() - self._anchor.x()) * ratio,
                self._anchor.y() + (self._start_center.y() - self._anchor.y()) * ratio,
            )

        elif self._drag_mode == "rotate":
            center_w = self.scene_to_widget(self.image_center)
            angle = math.degrees(
                math.atan2(pos.y() - center_w.y(), pos.x() - center_w.x())
            )
            self.image_angle = self._start_angle + (angle - self._start_mouse_angle)

        elif self._drag_mode == "move":
            scale = self.view_scale
            self.image_center = QPointF(
                self._start_center.x() + (pos.x() - self._drag_start.x()) / scale,
                self._start_center.y() + (pos.y() - self._drag_start.y()) / scale,
            )

        self._refresh_coverage()
        self.update()

    def mouseReleaseEvent(self, event):

        if event.button() == Qt.MouseButton.RightButton and self._panning:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return

        self._drag_mode = None

    def _update_cursor(self, pos):
        hit = self._handle_at(pos)
        if hit is None:
            inside = self._image_contains_scene(self.widget_to_scene(pos))
            self.setCursor(
                Qt.CursorShape.SizeAllCursor if inside
                else Qt.CursorShape.ArrowCursor
            )
        elif hit[0] == "corner":
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)

    def wheelEvent(self, event):

        delta = event.angleDelta().y()
        if delta == 0:
            return

        # 以鼠标所在位置为中心缩放：缩放前后鼠标下的场景点保持在鼠标下
        mouse = event.position()
        scene_point = self.widget_to_scene(mouse)
        factor = 1.1 if delta > 0 else 1 / 1.1
        self.view_scale = max(0.01, min(60.0, self.view_scale * factor))

        center = self.export_rect.center()
        self.view_pan = QPointF(
            mouse.x() - self.width() / 2
            - (scene_point.x() - center.x()) * self.view_scale,
            mouse.y() - self.height() / 2
            - (scene_point.y() - center.y()) * self.view_scale,
        )
        self.update()
        event.accept()

    # --------------------------------------------------------
    # 导出渲染
    # --------------------------------------------------------

    def render_export(self) -> QImage:
        """把导出区域内的画面按输出分辨率渲染为 QImage。"""

        width = max(1, int(self.out_w))
        height = max(1, int(self.out_h))
        canvas = QImage(width, height, QImage.Format.Format_RGB888)
        canvas.fill(QColor(0, 0, 0))

        rect = self.export_rect
        if rect.width() <= 0 or rect.height() <= 0:
            return canvas

        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        scale_x = width / rect.width()
        scale_y = height / rect.height()
        painter.translate(-rect.left() * scale_x, -rect.top() * scale_y)
        painter.scale(scale_x, scale_y)

        self._draw_image(painter)

        painter.end()
        return canvas


class SingleExportDialog(QDialog):
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

    @staticmethod
    def _title(text):
        """生成加粗的配置项标题标签。"""

        label = QLabel(text)
        label.setObjectName("Title")
        return label

    def _build_resolution_row(self):
        """构建「分辨率」标题行与宽高输入行（含等比锁定）。"""

        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._title("分辨率"))

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

        hint = QLabel("取消等比后可分别设置宽高，左侧导出区域会同步改变长宽比。")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.lock_check.toggled.connect(self.on_lock_toggled)
        self.width_edit.textEdited.connect(self.on_width_edited)
        self.height_edit.textEdited.connect(self.on_height_edited)

        return box

    def _build_slice_row(self):
        """构建「切片」标题行与 X / Y 数量、间隔输入行。"""

        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._title("切片"))

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

        hint = QLabel("数量≥1，间隔≥0（单位：px）；默认 1×1 即不切分。")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        for edit in (self.x_count_edit, self.x_gap_edit,
                     self.y_count_edit, self.y_gap_edit):
            edit.textChanged.connect(self._refresh_slices)

        return box

    def _build_format_row(self):
        """构建「目标格式」标题行与 jpg / png 单选行。"""

        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._title("目标格式"))

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

        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._title("文件大小"))

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

        hint = QLabel("JPG 通过品质控制体积；PNG 为无损格式，体积仅由分辨率决定。")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        return box

    def _build_output_row(self):
        """构建「输出文件」标题行与输出文件夹 / 文件名选择行。"""

        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._title("输出文件"))

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

    def current_ext(self):
        """返回当前目标格式对应的文件后缀。"""

        return ".jpg" if self.jpg_radio.isChecked() else ".png"

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

        folder = QFileDialog.getExistingDirectory(
            self, "选择输出文件夹", str(self.folder)
        )
        if not folder:
            return

        self.folder = Path(folder)
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
        options["format"] = "JPEG" if self.jpg_radio.isChecked() else "PNG"
        options["ext"] = ".jpg" if options["format"] == "JPEG" else ".png"

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
        options["max_bytes"] = None
        size_text = self.size_edit.text().strip()

        if size_text:
            try:
                megabytes = float(size_text)
            except ValueError:
                QMessageBox.warning(self, "提示", "文件大小请输入数字（MB）。")
                return

            if megabytes <= 0:
                QMessageBox.warning(self, "提示", "文件大小请输入正数（MB）。")
                return

            options["max_bytes"] = int(megabytes * 1024 * 1024)

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


# ============================================================
# 主窗口
# ============================================================

class MainWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("选片助手工作台")
        self.resize(1440, 920)

        self.folder = None
        self.loader_thread = None
        self.loader = None
        self.hq_thread = None
        self.hq_loader = None

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
        self.path_label.setToolTip(str(folder))
        self.view.set_files([str(p) for p in files])
        self.name_edit.clear()
        self.reclaim_memory()

        print("=" * 72)
        print(f"[文件夹] {folder}")
        print(f"[总计] {len(files)} 张图片")
        print("=" * 72, flush=True)

        if not files:
            self.statusBar().showMessage("该文件夹中没有支持的图片")
            return

        self.statusBar().showMessage(f"共 {len(files)} 张图片，正在按需读取")
        self.ensure_visible_loaded(*self.view.visible_range())

    def reclaim_memory(self):
        """显式触发垃圾回收，尽快释放被淘汰图片占用的内存。"""

        gc.collect()

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
        self.loader = ImageLoader(max_edge=PREVIEW_MAX_EDGE)
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
        self.reclaim_memory()
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
            # 网格预览一律是降采样图，单图模式需重新完整读取
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
        self.reclaim_memory()
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
        canvas.fill(VIEW_BG)

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

            # 优先复用完整画质图，其次预览图，缺失时按需读取
            image = self.view.hq_images.get(index)

            if image is None:
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

        indices = self.selected_indices()

        if not indices:
            QMessageBox.information(self, "提示", "没有匹配到任何文件。")
            return

        if len(indices) == 1:
            self._export_single(indices[0])
        else:
            self._export_batch(indices)

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

        x_count, x_gap, y_count, y_gap = options["slices"]
        export = options["image"]
        res_w, res_h = export.width(), export.height()

        slice_w = (res_w - (x_count - 1) * x_gap) / x_count
        slice_h = (res_h - (y_count - 1) * y_gap) / y_count
        sliced = x_count != 1 or y_count != 1

        # 发生切分时，自动导出到以原图名命名的新文件夹（重名追加 (x)）
        target_dir = Path(options["output_dir"])
        if sliced:
            target_dir = unique_folder(target_dir, source_stem)
            target_dir.mkdir(parents=True, exist_ok=False)
        else:
            target_dir.mkdir(parents=True, exist_ok=True)

        count = 0
        failed = []

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        try:
            for row in range(y_count):
                for col in range(x_count):

                    left = max(0, min(res_w - 1, round((slice_w + x_gap) * col)))
                    top = max(0, min(res_h - 1, round((slice_h + y_gap) * row)))
                    right = min(res_w, round(left + slice_w))
                    bottom = min(res_h, round(top + slice_h))

                    if right <= left or bottom <= top:
                        continue

                    piece = export.copy(QRect(left, top, right - left, bottom - top))
                    pil_image = qimage_to_pil(piece)

                    base = (
                        f"{options['output_stem']}_slice_{row * x_count + col}"
                        if sliced else options["output_stem"]
                    )
                    stem = unique_stem(target_dir, base, options["ext"])
                    target = target_dir / f"{stem}{options['ext']}"

                    try:
                        data, quality = encode_with_limit(
                            pil_image, options["format"], options["max_bytes"]
                        )
                        with open(target, "wb") as f:
                            f.write(data)
                        count += 1
                        note = f"，品质 {quality}" if quality else ""
                        print(
                            f"[导出] {target.name}  {len(data) / 1024:.0f} KB{note}",
                            flush=True,
                        )
                    except Exception as e:
                        failed.append((target.name, str(e)))
                        print(f"[导出失败] {target.name}: {e}", flush=True)

        finally:
            QApplication.restoreOverrideCursor()

        message = f"已导出 {count} 张图片到：\n{target_dir}"
        if failed:
            message += "\n\n以下文件失败：\n" + "\n".join(
                f"{name}：{error}" for name, error in failed[:10]
            )

        QMessageBox.information(self, "导出完成", message)
        self.statusBar().showMessage(f"导出完成：{count} 张 -> {target_dir.name}")

    def _export_batch(self, indices):
        """多张图片：按长边像素等比缩放导出。"""

        dialog = BatchExportDialog(len(indices), self.folder, self)

        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.options is None:
            return

        options = dialog.options
        target_dir = Path(options["output_dir"])
        target_dir.mkdir(parents=True, exist_ok=True)

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        count = 0
        failed = []

        try:
            for position, index in enumerate(indices, 1):

                path = self.view.paths[index]
                print(f"[导出] {position}/{len(indices)}  {Path(path).name}", flush=True)

                try:
                    output, size, quality = convert_batch_image(
                        path,
                        target_dir,
                        options["format"],
                        options["ext"],
                        options["long_edge"],
                        options["max_bytes"],
                    )
                    count += 1
                    note = f"，品质 {quality}" if quality else ""
                    print(
                        f"[导出完成] {output.name}  {size / 1024:.0f} KB{note}",
                        flush=True,
                    )

                except Exception as e:
                    failed.append((Path(path).name, str(e)))
                    print(f"[导出失败] {Path(path).name}: {e}", flush=True)

        finally:
            QApplication.restoreOverrideCursor()

        message = f"已导出 {count} 张图片到：\n{target_dir}"
        if failed:
            message += "\n\n以下文件失败：\n" + "\n".join(
                f"{name}：{error}" for name, error in failed[:10]
            )

        QMessageBox.information(self, "导出完成", message)
        self.statusBar().showMessage(f"导出完成：{count} 张 -> {target_dir.name}")

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

                    set_button_role(btn_yes, "primary")

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
        box = QMessageBox(self)
        box.setWindowTitle("移动到回收站")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(f"确定将选中的 {len(indices)} 个文件移动到回收站吗？")
        btn_yes = box.addButton("确定", QMessageBox.ButtonRole.YesRole)
        btn_no = box.addButton("取消", QMessageBox.ButtonRole.NoRole)
        set_button_role(btn_yes, "primary")
        box.setDefaultButton(btn_yes)
        box.exec()

        if box.clickedButton() is not btn_yes:
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

    # 统一使用 Fusion 风格 + 深色调色板 + 自绘样式表，
    # 让按钮、输入框、弹窗等都呈现一致的现代深色外观。
    app.setStyle("Fusion")
    apply_dark_palette(app)
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setStyleSheet(STYLE_SHEET)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()