# -*- coding: utf-8 -*-

"""
图片读取。

负责 PIL 与 QImage 的互转、RAW 解码、按最长边降采样读取，
以及统一的 load_image 入口。
"""

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps
import rawpy

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QImage, QImageReader, QPainter

from .constants import RAW_EXTS


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


def draw_image_centered(painter: QPainter, image: QImage, rect: QRect):
    """在 rect 内等比缩放并居中绘制 image（保持长宽比，不拉伸）。"""

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
