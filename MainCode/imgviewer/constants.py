# -*- coding: utf-8 -*-

"""
全局常量。

集中存放配色、支持的图片格式与预览分辨率，
供主题、图片读写与界面模块共同使用。
"""

from pathlib import Path

from PySide6.QtGui import QColor


# ============================================================
# 配色常量（供代码内自绘与样式表共用，保持一致）
# ============================================================

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
