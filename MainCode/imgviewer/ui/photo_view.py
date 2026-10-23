# -*- coding: utf-8 -*-

"""
图片虚拟显示区域。

按需绘制可视范围内的缩略图，支持多列网格 / 单图模式切换、
Ctrl + 滚轮缩放、Shift 范围勾选。
"""

from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractScrollArea

from ..constants import COLOR_ACCENT, VIEW_BG
from ..image_io import draw_image_centered


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

            draw_image_centered(painter, image, rect)

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
