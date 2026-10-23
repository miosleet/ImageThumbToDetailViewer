# -*- coding: utf-8 -*-

"""
系统原生文件操作（复制 / 移动 / 送入回收站）。

借助 Windows 自带的文件操作，遇到同名文件时
会弹出系统原生的冲突对话框，由用户选择如何处理。
"""

import ctypes
import os
import subprocess


FO_MOVE = 0x0001
FO_COPY = 0x0002
FO_DELETE = 0x0003

FOF_SILENT = 0x0004
FOF_NOCONFIRMATION = 0x0010
FOF_ALLOWUNDO = 0x0040          # 删除时送入回收站
FOF_NOCONFIRMMKDIR = 0x0200
FOF_NOERRORUI = 0x0400

try:
    from ctypes import wintypes as _wt

    class _SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", _wt.HWND),
            ("wFunc", _wt.UINT),
            ("pFrom", _wt.LPCWSTR),
            ("pTo", _wt.LPCWSTR),
            ("fFlags", ctypes.c_uint16),
            ("fAnyOperationsAborted", _wt.BOOL),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", _wt.LPCWSTR),
        ]
except Exception:
    _SHFILEOPSTRUCTW = None


def _shell_operation(wfunc, sources, destination, flags):
    """
    调用 SHFileOperationW。

    destination 为 None 表示不需要目标路径（例如删除）。
    返回 (result, aborted)，result == 0 表示成功。
    """

    if _SHFILEOPSTRUCTW is None:
        raise RuntimeError("当前系统不支持原生文件操作")

    # pFrom / pTo 需要以双 \0 结尾
    p_from = "\0".join(os.path.abspath(str(s)) for s in sources) + "\0\0"
    p_to = None if destination is None else os.path.abspath(str(destination)) + "\0\0"

    op = _SHFILEOPSTRUCTW()
    op.hwnd = None
    op.wFunc = wfunc
    op.pFrom = p_from
    op.pTo = p_to
    op.fFlags = flags
    op.fAnyOperationsAborted = False
    op.hNameMappings = None
    op.lpszProgressTitle = None

    func = ctypes.windll.shell32.SHFileOperationW
    func.argtypes = [ctypes.POINTER(_SHFILEOPSTRUCTW)]
    func.restype = ctypes.c_int
    result = func(ctypes.byref(op))

    print(f"[原生文件操作] wFunc={wfunc} result={result} "
          f"aborted={bool(op.fAnyOperationsAborted)}", flush=True)

    return result, bool(op.fAnyOperationsAborted)


def shell_file_operation(wfunc, sources, destination):
    """复制 / 移动到指定文件夹。"""
    return _shell_operation(wfunc, sources, destination, FOF_NOCONFIRMMKDIR)


def shell_delete_to_recycle_bin(sources):
    """移动到回收站（系统确认框由程序自己弹出，故此处抑制）。"""
    return _shell_operation(
        FO_DELETE,
        sources,
        None,
        FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI,
    )


def powershell_recycle(paths):
    """
    备用方案：通过 PowerShell 的 Microsoft.VisualBasic
    将文件移动到回收站。返回进程退出码，0 表示成功。
    """

    joined = ",".join("'" + str(p).replace("'", "''") + "'" for p in paths)
    script = (
        "Add-Type -AssemblyName Microsoft.VisualBasic; "
        f"@({joined}) | ForEach-Object {{ "
        "[Microsoft.VisualBasic.FileIO.FileSystem]::"
        "DeleteFile($_, 'OnlyErrorDialogs', 'SendToRecycleBin') }"
    )

    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
    )
    return proc.returncode
