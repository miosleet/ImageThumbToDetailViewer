# -*- coding: utf-8 -*-

"""
拼接缩略图渲染。

把选中的图片按指定列数拼成一张总宽 3840 的大图，
每格为一张缩略图并带文件名，高度随行数自然增长。
"""

from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter

from ..constants import VIEW_BG
from ..image_io import draw_image_centered, load_image


# 防止拼接图过大导致内存问题
STITCH_MAX_PIXELS = 150_000_000
STITCH_WIDTH = 3840

# 拼接图底部署名行：整行 200px，文字高度 100px，不占用图片格子
STITCH_FOOTER_TEXT = "导出使用工具：选图助手-Made by : 澪霰MioSleet"
STITCH_FOOTER_HEIGHT = 200
STITCH_FOOTER_TEXT_HEIGHT = 100
STITCH_FOOTER_MARGIN = 40


def stitch_size(count, columns):
    """返回拼接图尺寸（含底部署名行）。"""

    rows = (count + columns - 1) // columns
    cell = STITCH_WIDTH / columns
    height = int(round(rows * cell)) + STITCH_FOOTER_HEIGHT
    return STITCH_WIDTH, height


def render_stitch(paths, indices, columns, get_image,
                  on_progress=None, should_stop=None):
    """
    渲染拼接图。

    get_image(index) 用于优先复用界面缓存的完整画质图 / 预览图；
    缓存缺失时按需读取原图。

    on_progress(current, total) 每处理完一张回调一次；
    should_stop() 返回 True 时提前结束（用于窗口关闭）。

    返回 (canvas, width, height, failed)：
    尺寸超限时 canvas 为 None，由调用方提示用户。
    """

    width, height = stitch_size(len(indices), columns)
    cell = STITCH_WIDTH / columns

    if width * height > STITCH_MAX_PIXELS:
        return None, width, height, 0

    canvas = QImage(width, height, QImage.Format.Format_RGB32)
    canvas.fill(VIEW_BG)

    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    font = painter.font()
    font.setPixelSize(min(48, max(12, int(cell * 0.045))))
    painter.setFont(font)

    failed = 0
    total = len(indices)

    for position, index in enumerate(indices):

        if should_stop is not None and should_stop():
            break

        row, column = divmod(position, columns)
        left = int(round(column * cell))
        right = int(round((column + 1) * cell))
        top = int(round(row * cell))
        bottom = int(round((row + 1) * cell))
        rect = QRect(left, top, right - left, bottom - top)

        # 优先复用完整画质图，其次预览图，缺失时按需读取
        image = get_image(index)

        if image is None:
            try:
                image = load_image(paths[index])
            except Exception as e:
                failed += 1
                print(f"[拼接] 读取失败 {paths[index]}: {e}", flush=True)
                image = None

        if image is not None and not image.isNull():

            draw_image_centered(painter, image, rect)

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

        name = Path(paths[index]).name
        text = painter.fontMetrics().elidedText(
            name, Qt.TextElideMode.ElideRight, bar.width() - 12
        )
        painter.drawText(
            bar.adjusted(6, 0, -6, 0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            text,
        )

        if on_progress is not None:
            on_progress(position + 1, total)

    # --------------------------------------------------------
    # 底部署名行：在最下方新增一行，不覆盖图片
    # --------------------------------------------------------

    footer_top = height - STITCH_FOOTER_HEIGHT
    painter.fillRect(
        QRect(0, footer_top, width, STITCH_FOOTER_HEIGHT), VIEW_BG
    )

    footer_font = painter.font()
    footer_font.setPixelSize(STITCH_FOOTER_TEXT_HEIGHT)
    painter.setFont(footer_font)
    painter.setPen(QColor(255, 255, 255))
    painter.drawText(
        QRect(
            STITCH_FOOTER_MARGIN,
            footer_top,
            width - STITCH_FOOTER_MARGIN * 2,
            STITCH_FOOTER_HEIGHT,
        ),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        STITCH_FOOTER_TEXT,
    )

    painter.end()

    return canvas, width, height, failed
