# -*- coding: utf-8 -*-

"""
图片调整导出。

读取完整图像、按需缩放、控制导出文件大小，
并提供批量导出的单张转换入口。
"""

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from .constants import RAW_EXTS
from .image_io import raw_to_pil


def load_source_image(path: str) -> Image.Image:
    """
    以完整分辨率读取一张图片，返回完成 EXIF 方向校正的 PIL 图像。

    RAW 走 rawpy 完整解码；普通图片直接读取并应用 EXIF 方向，
    以保证转换时使用的图像与界面中看到的朝向一致。
    """

    if Path(path).suffix.lower() in RAW_EXTS:
        return raw_to_pil(path, full=True)

    with Image.open(path) as im:
        return ImageOps.exif_transpose(im).copy()


def resize_to_long_edge(image: Image.Image, long_edge: int) -> Image.Image:
    """
    等比缩放图片，使最长边等于 long_edge，短边按比例缩放（允许放大）。

    长边为宽时按宽命中，长边为高时按高命中。
    """

    width, height = image.size

    if width >= height:
        new_w = long_edge
        new_h = max(1, round(height * long_edge / width))
    else:
        new_h = long_edge
        new_w = max(1, round(width * long_edge / height))

    return image.resize((new_w, new_h), Image.LANCZOS)


def encode_image(image: Image.Image, fmt: str, quality: int = None) -> bytes:
    """
    把 PIL 图像编码为指定格式的字节数据。

    fmt 为 "JPEG" 或 "PNG"；quality 仅对 JPEG 有效（对应 PS 中的品质，1~100）。
    PNG 为无损格式，统一使用 optimize 尽量减小体积。
    """

    buffer = BytesIO()

    if fmt == "JPEG":
        if image.mode != "RGB":
            image = image.convert("RGB")
        quality = quality if quality else 100
        image.save(
            buffer,
            format="JPEG",
            quality=quality,
            # 品质 95 以上不做色度子采样，保证最高画质
            subsampling=0 if quality >= 95 else 2,
        )
    else:
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")
        image.save(buffer, format="PNG", optimize=True)

    return buffer.getvalue()


def find_jpeg_quality(image: Image.Image, max_bytes: int):
    """
    二分查找 JPEG 品质：在文件体积小于 max_bytes 的前提下，返回尽量大的品质值。

    返回 (quality, data)：quality 为命中的品质，data 为对应编码字节；
    若最低品质仍超过限制，则 quality 为 None，data 为最小体积的编码结果。
    """

    low, high = 1, 100
    best_quality = None
    best_data = None

    while low <= high:

        middle = (low + high) // 2
        data = encode_image(image, "JPEG", middle)

        if len(data) < max_bytes:
            best_quality, best_data = middle, data
            low = middle + 1
        else:
            high = middle - 1

    if best_data is None:
        best_data = encode_image(image, "JPEG", 1)

    return best_quality, best_data


def encode_with_limit(image: Image.Image, fmt: str, max_bytes: int):
    """
    按目标格式与体积上限编码，返回 (data, quality)。

    JPEG 在给定体积上限下二分查找最高品质；PNG 为无损格式，
    体积仅由分辨率决定，故忽略上限（返回的 quality 为 None）。
    """

    if fmt == "JPEG":
        if max_bytes:
            quality, data = find_jpeg_quality(image, max_bytes)
            return data, quality
        return encode_image(image, "JPEG", 100), None

    return encode_image(image, "PNG"), None


def unique_stem(folder, stem: str, ext: str) -> str:
    """
    在 folder 中为「stem + ext」求一个不冲突的文件名（不含后缀部分）。

    规则：无冲突时返回 stem；否则依次尝试 stem(1)、stem(2)…，
    例如 aaa.jpg 已存在则返回 aaa(1)，同理 aaa(1).jpg 也存在则返回 aaa(2)。
    """

    folder = Path(folder)

    if not (folder / f"{stem}{ext}").exists():
        return stem

    index = 1
    while (folder / f"{stem}({index}){ext}").exists():
        index += 1

    return f"{stem}({index})"


def unique_folder(parent, name: str) -> Path:
    """
    在 parent 下为 name 求一个不冲突的文件夹路径。

    规则：无冲突时返回 parent/name；否则依次尝试 name(1)、name(2)…
    """

    parent = Path(parent)

    if not (parent / name).exists():
        return parent / name

    index = 1
    while (parent / f"{name}({index})").exists():
        index += 1

    return parent / f"{name}({index})"


def convert_batch_image(path, output_dir, fmt, ext, long_edge, max_bytes):
    """
    批量导出中的单张处理：读取完整图像 -> 按长边等比缩放（可选）
    -> 按体积限制编码 -> 写出到 output_dir。

    返回 (输出路径, 字节数, 使用的品质)；文件名沿用原文件名，
    在目标文件夹内自动避让同名文件（aaa -> aaa(1) -> aaa(2)…）。
    """

    image = load_source_image(path)

    if long_edge:
        image = resize_to_long_edge(image, long_edge)

    data, quality = encode_with_limit(image, fmt, max_bytes)

    stem = unique_stem(output_dir, Path(path).stem, ext)
    target = Path(output_dir) / f"{stem}{ext}"

    with open(target, "wb") as f:
        f.write(data)

    return target, len(data), quality
