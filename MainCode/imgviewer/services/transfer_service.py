# -*- coding: utf-8 -*-

"""
文件搬运。

负责新建「筛选_xx」文件夹、复制 / 移动到指定文件夹（优先系统原生操作）、
以及移动到回收站。界面确认框由调用方负责。
"""

import shutil
from pathlib import Path
from typing import List, NamedTuple, Tuple

from PySide6.QtWidgets import QMessageBox

from ..file_ops import (
    FO_COPY,
    FO_MOVE,
    powershell_recycle,
    shell_delete_to_recycle_bin,
    shell_file_operation,
)
from ..theme import set_button_role


class TransferOutcome(NamedTuple):
    """指定文件夹复制 / 移动的结果。"""

    native: bool                 # 是否由系统原生操作完成
    count: int                   # 成功数量
    skipped: int                 # 因同名跳过数量（仅 Python 方案）
    failed: List[Tuple[str, str]]  # [(文件名, 错误信息)]


def next_filter_folder(folder):
    """返回最小的、当前未被占用的「筛选_xx」目录。"""

    number = 1
    while (folder / f"筛选_{number:02d}").exists():
        number += 1
    return folder / f"筛选_{number:02d}"


def transfer_to_new_folder(folder, sources, move):
    """
    复制 / 移动到新建的「筛选_xx」文件夹。

    返回 (target, count, failed)。
    """

    target = next_filter_folder(folder)
    target.mkdir(parents=True, exist_ok=False)

    verb = "移动" if move else "复制"
    operation = shutil.move if move else shutil.copy2
    count, failed = 0, []

    for source in sources:

        source = Path(source)

        try:
            operation(str(source), str(target / source.name))
            count += 1
            print(f"[{verb}] {count}/{len(sources)}  {source.name}", flush=True)

        except Exception as e:
            failed.append((source.name, str(e)))
            print(f"[{verb}失败] {source.name}: {e}", flush=True)

    return target, count, failed


def transfer_to_folder(parent, sources, target, move):
    """
    复制 / 移动到指定文件夹。

    优先使用系统原生操作（自带冲突对话框），
    失败时退回 Python 方案。
    """

    native_ok = False

    try:
        result, aborted = shell_file_operation(
            FO_MOVE if move else FO_COPY, sources, target
        )
        native_ok = result == 0 and not aborted
    except Exception as e:
        print(f"[原生文件操作异常] {e}", flush=True)

    if native_ok:
        return TransferOutcome(True, len(sources), 0, [])

    print("[原生文件操作失败，改用 Python 方案]", flush=True)

    count, skipped, failed = python_transfer(parent, sources, target, move)
    return TransferOutcome(False, count, skipped, failed)


def python_transfer(parent, sources, target, move):
    """Python 复制 / 移动，遇到同名文件时询问用户。"""

    replace_all = skip_all = False
    count = skipped = 0
    failed = []

    for src in sources:

        src_path = Path(src)
        dst_path = Path(target) / src_path.name

        if dst_path.exists():

            if skip_all:
                skipped += 1
                continue

            if not replace_all:

                box = QMessageBox(parent)
                box.setWindowTitle("文件冲突")
                box.setIcon(QMessageBox.Icon.Question)
                box.setText(f"目标文件夹中已存在同名文件：\n{src_path.name}")

                btn_yes = box.addButton("替换", QMessageBox.ButtonRole.YesRole)
                btn_yes_all = box.addButton("全部替换", QMessageBox.ButtonRole.YesRole)
                btn_no = box.addButton("跳过", QMessageBox.ButtonRole.NoRole)
                btn_no_all = box.addButton("全部跳过", QMessageBox.ButtonRole.NoRole)

                set_button_role(btn_yes, "primary")

                box.exec()
                clicked = box.clickedButton()

                if clicked is btn_yes_all:
                    replace_all = True
                elif clicked is btn_no_all:
                    skip_all = True
                    skipped += 1
                    continue
                elif clicked is btn_no:
                    skipped += 1
                    continue

        try:
            if move:
                shutil.move(str(src_path), str(dst_path))
            else:
                shutil.copy2(src_path, dst_path)
            count += 1

        except Exception as e:
            failed.append((src_path.name, str(e)))
            print(f"[Python 文件操作失败] {src_path.name}: {e}", flush=True)

    return count, skipped, failed


def recycle_files(sources):
    """把文件移动到回收站，返回是否成功。"""

    ok = False

    try:
        result, aborted = shell_delete_to_recycle_bin(sources)
        ok = result == 0 and not aborted
    except Exception as e:
        print(f"[原生删除异常] {e}", flush=True)

    if not ok:
        print("[原生删除失败，改用 PowerShell 方案]", flush=True)
        try:
            ok = powershell_recycle(sources) == 0
        except Exception as e:
            print(f"[PowerShell 回收站异常] {e}", flush=True)

    return ok
