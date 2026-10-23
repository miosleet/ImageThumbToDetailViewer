# -*- coding: utf-8 -*-

"""
后台图片读取线程。
"""

from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage

from .image_io import load_image


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
