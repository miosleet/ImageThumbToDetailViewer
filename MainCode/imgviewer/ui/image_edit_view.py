# -*- coding: utf-8 -*-

"""
单图「图片调整导出」——可视化编辑预览控件。
"""

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QTransform
from PySide6.QtWidgets import QWidget


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
