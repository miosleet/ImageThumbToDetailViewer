# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（Windows / macOS 通用）。

用法（在各自平台上执行，PyInstaller 不支持跨平台交叉编译）：
    Windows: python -m PyInstaller --noconfirm --clean ImageThumbToDetailViewer.spec
    macOS  : python -m PyInstaller --noconfirm --clean ImageThumbToDetailViewer.spec

产物：
    Windows: dist/ImageThumbToDetailViewer_v3.2.exe（单文件，无控制台窗口）
    macOS  : dist/ImageThumbToDetailViewer_v3.2.app（应用包，无控制台窗口）
"""

import sys
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []
tmp_ret = collect_all('rawpy')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# 程序图标：Windows 用 .ico，macOS 用 .icns（均放在项目根目录）
ICON = 'Icon.icns' if sys.platform == 'darwin' else 'Icon.ico'


a = Analysis(
    ['MainCode/ImageThumbToDetailViewer_v3.2.py'],
    pathex=['MainCode'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'tkinter', 'scipy', 'pandas', 'IPython', 'pytest'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ImageThumbToDetailViewer_v3.2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)

if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='ImageThumbToDetailViewer_v3.2.app',
        icon=ICON,
        bundle_identifier='com.miosleet.imagethumbtodetailviewer',
    )