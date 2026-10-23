# -*- coding: utf-8 -*-

"""
现代化深色主题。

统一的自绘控件样式：圆角、无原生白底方框按钮，
层次分明的灰阶配色 + 单一蓝色强调色，整体简洁、现代。
"""

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QPushButton

from .constants import COLOR_ACCENT, COLOR_BG, COLOR_SURFACE, COLOR_TEXT


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
