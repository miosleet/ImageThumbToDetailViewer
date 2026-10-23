# -*- coding: utf-8 -*-

"""
调整导出落盘。

单图导出负责把渲染结果按切片规则切分并写出；
批量导出负责逐张读取、缩放、编码并写出。
两者都不涉及界面弹窗，仅返回结果供主窗口提示。
"""

from pathlib import Path

from PySide6.QtCore import QRect

from ..image_export import (
    convert_batch_image,
    encode_with_limit,
    unique_folder,
    unique_stem,
)
from ..image_io import qimage_to_pil


def export_single_slices(export, options, source_stem):
    """
    单图导出：按切片参数把渲染结果切分并写出。

    返回 (count, failed, target_dir)；
    failed 为 [(文件名, 错误信息)] 列表。
    """

    x_count, x_gap, y_count, y_gap = options["slices"]
    res_w, res_h = export.width(), export.height()

    slice_w = (res_w - (x_count - 1) * x_gap) / x_count
    slice_h = (res_h - (y_count - 1) * y_gap) / y_count
    sliced = x_count != 1 or y_count != 1

    # 发生切分时，自动导出到以原图名命名的新文件夹（重名追加 (x)）
    target_dir = Path(options["output_dir"])
    if sliced:
        target_dir = unique_folder(target_dir, source_stem)
        target_dir.mkdir(parents=True, exist_ok=False)
    else:
        target_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    failed = []

    for row in range(y_count):
        for col in range(x_count):

            left = max(0, min(res_w - 1, round((slice_w + x_gap) * col)))
            top = max(0, min(res_h - 1, round((slice_h + y_gap) * row)))
            right = min(res_w, round(left + slice_w))
            bottom = min(res_h, round(top + slice_h))

            if right <= left or bottom <= top:
                continue

            piece = export.copy(QRect(left, top, right - left, bottom - top))
            pil_image = qimage_to_pil(piece)

            base = (
                f"{options['output_stem']}_slice_{row * x_count + col}"
                if sliced else options["output_stem"]
            )
            stem = unique_stem(target_dir, base, options["ext"])
            target = target_dir / f"{stem}{options['ext']}"

            try:
                data, quality = encode_with_limit(
                    pil_image, options["format"], options["max_bytes"]
                )
                with open(target, "wb") as f:
                    f.write(data)
                count += 1
                note = f"，品质 {quality}" if quality else ""
                print(
                    f"[导出] {target.name}  {len(data) / 1024:.0f} KB{note}",
                    flush=True,
                )
            except Exception as e:
                failed.append((target.name, str(e)))
                print(f"[导出失败] {target.name}: {e}", flush=True)

    return count, failed, target_dir


def export_batch(paths, indices, options, on_progress=None, should_stop=None):
    """
    多图导出：按长边像素等比缩放导出。

    on_progress(current, total) 每处理完一张回调一次；
    should_stop() 返回 True 时提前结束（用于窗口关闭）。

    返回 (count, failed, target_dir)。
    """

    target_dir = Path(options["output_dir"])
    target_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    failed = []
    total = len(indices)

    for position, index in enumerate(indices, 1):

        if should_stop is not None and should_stop():
            break

        path = paths[index]
        print(f"[导出] {position}/{total}  {Path(path).name}", flush=True)

        try:
            output, size, quality = convert_batch_image(
                path,
                target_dir,
                options["format"],
                options["ext"],
                options["long_edge"],
                options["max_bytes"],
            )
            count += 1
            note = f"，品质 {quality}" if quality else ""
            print(
                f"[导出完成] {output.name}  {size / 1024:.0f} KB{note}",
                flush=True,
            )

        except Exception as e:
            failed.append((Path(path).name, str(e)))
            print(f"[导出失败] {Path(path).name}: {e}", flush=True)

        if on_progress is not None:
            on_progress(position, total)

    return count, failed, target_dir
