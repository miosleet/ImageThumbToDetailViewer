#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
选片助手工作台（ImageThumbToDetailViewer v3.2）

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
    python ImageThumbToDetailViewer_v3.2.py

代码结构（imgviewer 包）：
    constants        全局常量
    theme            深色主题与样式
    image_io         图片读取与格式转换
    image_export     导出编码与批量转换
    file_ops         系统原生文件操作
    loader           后台图片读取线程
    ui               主窗口与各界面
    services         加载编排 / 拼接 / 导出 / 搬运
"""

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from imgviewer.theme import STYLE_SHEET, apply_dark_palette
from imgviewer.ui.main_window import MainWindow


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
