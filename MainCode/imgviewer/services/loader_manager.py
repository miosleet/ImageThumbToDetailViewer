# -*- coding: utf-8 -*-

"""
图片加载线程编排。

负责网格预览与单图完整画质的后台读取：创建线程、连接信号、
按可视范围补读、在读取结束后继续处理下一批，以及退出时的清理。
"""

import gc
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from ..constants import PREVIEW_MAX_EDGE
from ..loader import ImageLoader


class LoaderManager(QObject):
    """管理预览图与完整画质两条加载链路。"""

    statusMessage = Signal(str)

    def __init__(self, view, parent=None):

        super().__init__(parent)

        self.view = view

        self.loader_thread = None
        self.loader = None
        self.hq_thread = None
        self.hq_loader = None

    # --------------------------------------------------------
    # 预览图
    # --------------------------------------------------------

    def load_visible(self, lo, hi):

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
            self.view.set_image, self.view.set_error, self._loader_finished,
        )

        self.statusMessage.emit(
            f"当前读取/显示：{lo2 + 1}~{hi2 + 1} / {len(self.view.paths)}"
        )

    def _loader_finished(self):

        self.loader = None
        self.loader_thread = None
        gc.collect()
        QTimer.singleShot(
            0, lambda: self.load_visible(*self.view.visible_range())
        )

    # --------------------------------------------------------
    # 完整画质
    # --------------------------------------------------------

    def load_hq(self):
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
            self._on_hq_loaded, self._on_hq_failed, self._hq_finished,
        )

    def _on_hq_loaded(self, index, image):
        # 忽略已失效（例如切换文件夹后）的读取结果
        if self.sender() is not self.hq_loader:
            return
        self.view.set_hq_image(index, image)

    def _on_hq_failed(self, index, error):

        if self.sender() is not self.hq_loader:
            return

        self.view.hq_failed.add(index)
        name = (
            Path(self.view.paths[index]).name
            if 0 <= index < len(self.view.paths)
            else str(index)
        )
        print(f"[完整画质失败] {name} -> {error}", flush=True)

    def _hq_finished(self):

        self.hq_loader = None
        self.hq_thread = None
        gc.collect()
        QTimer.singleShot(0, self.load_hq)

    # --------------------------------------------------------
    # 通用
    # --------------------------------------------------------

    @staticmethod
    def _run_loader(loader, thread, on_loaded, on_failed, on_finished):
        """把 loader 放到独立线程中运行并连接信号。"""

        loader.moveToThread(thread)
        thread.started.connect(loader.run)
        loader.loaded.connect(on_loaded)
        loader.failed.connect(on_failed)
        loader.finished.connect(thread.quit)
        loader.finished.connect(on_finished)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def stop(self):

        for loader in (self.loader, self.hq_loader):
            if loader is not None:
                loader.stop()

        for thread in (self.loader_thread, self.hq_thread):
            if thread is not None:
                thread.quit()
                thread.wait(1500)

        self.loader = self.hq_loader = None
        self.loader_thread = self.hq_thread = None
