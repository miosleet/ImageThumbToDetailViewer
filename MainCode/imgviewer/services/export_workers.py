# -*- coding: utf-8 -*-

"""
导出后台线程。

拼接缩略图与多图调整导出都在独立于 UI 的线程中执行，
通过信号回传进度与结果，避免阻塞主界面。
"""

from PySide6.QtCore import QThread, Signal

from . import export_service, stitch_service


class StitchExportThread(QThread):
    """在后台渲染并保存拼接缩略图。"""

    progress = Signal(int, int)          # 当前张数, 总张数
    done = Signal(int, int, str)         # 总张数, 读取失败数, 保存路径
    failed = Signal(str)

    def __init__(self, paths, indices, columns, cached, target_path, parent=None):

        super().__init__(parent)

        self._paths = list(paths)
        self._indices = list(indices)
        self._columns = columns
        self._cached = cached
        self._target_path = target_path
        self._cancelled = False

    def cancel(self):
        """请求在下一张图片前停止（用于关闭窗口）。"""

        self._cancelled = True

    def _get_image(self, index):
        return self._cached.get(index)

    def run(self):

        try:
            canvas, width, height, failed = stitch_service.render_stitch(
                self._paths,
                self._indices,
                self._columns,
                self._get_image,
                on_progress=self.progress.emit,
                should_stop=lambda: self._cancelled,
            )

            if canvas is None:
                self.failed.emit(
                    f"拼接图尺寸过大（{width} × {height}）。\n"
                    "请减少选中数量，或先缩小到列数更多的档位再导出。"
                )
                return

            if self._cancelled:
                return

            if not canvas.save(self._target_path):
                self.failed.emit("保存图片失败。")
                return

            self.done.emit(
                len(self._indices), failed, self._target_path
            )

        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")


class BatchExportThread(QThread):
    """在后台执行多图调整导出。"""

    progress = Signal(int, int)              # 当前张数, 总张数
    done = Signal(int, object, str)          # 成功数, 失败列表, 输出目录
    failed = Signal(str)

    def __init__(self, paths, indices, options, parent=None):

        super().__init__(parent)

        self._paths = list(paths)
        self._indices = list(indices)
        self._options = dict(options)
        self._cancelled = False

    def cancel(self):
        """请求在下一张图片前停止（用于关闭窗口）。"""

        self._cancelled = True

    def run(self):

        try:
            count, failed, target_dir = export_service.export_batch(
                self._paths,
                self._indices,
                self._options,
                on_progress=self.progress.emit,
                should_stop=lambda: self._cancelled,
            )

            if self._cancelled:
                return

            self.done.emit(count, failed, str(target_dir))

        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")
