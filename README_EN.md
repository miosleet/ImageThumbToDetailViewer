# ImageThumbToDetailViewer (选片助手工作台)

A desktop tool for the photo-review workflow: thumbnail browsing, full-size viewing, and batch selection, plus batch copy / move of the selected images to a folder or the recycle bin, exporting the selected images as a single image, and converting the selected images by format / file size / resolution. Supports RAW.

Built with **PySide6**.

---

## Features

### Browsing
- **Open Folder (打开文件夹)**: lists every supported image in the folder (current folder only, no recursion into subfolders), sorted by file name.
- **Thumbnail grid**: shows thumbnails as a grid. Virtualized rendering that only draws the visible tiles; images are loaded on demand in a background thread, so large folders won't freeze the UI.
- **Zoom (Ctrl + wheel)**: steps through zoom levels, from a dense grid of about 10 columns up to single-image magnification (up to about 4x), and keeps the image under the cursor in the same spot after zooming.
- **Full-quality single image**: in 1-image-per-row mode (including magnification), RAW files are re-decoded at full resolution in the background and swapped in, keeping the large view sharp;

### Selecting
- **Click** anywhere on a tile: check / uncheck.
- **Shift + click**: range selection (file-manager style).
- **Match by file name (Enter)**: type file names or fragments, separated by English / Chinese commas. An exact file-name match takes priority, then substring matching; each entry matches at most one file. The matches become the current selection, and manual selections are also written back to the input box.
- **Select All (Ctrl + A)**: check every image in the current folder in one click.
- **Deselect All (Esc)**: clear the selection.

### Copy/Move/Delete
- **Copy to New Filter Folder / Move to New Filter Folder**: create `筛选_XX` next to the current folder, using the smallest unused number. After a move, the thumbnail grid is refreshed.
- **Copy to Folder (Ctrl + C) / Move to Folder (Ctrl + X)**: copy or move the selected images to any destination folder. Uses the native system copy / move; on a name conflict it pops up the system's own conflict dialog (replace / skip / keep both). If the native call is unavailable, it falls back to a built-in conflict dialog (replace / replace all / skip / skip all).
- **Move to Recycle Bin (Del/Backspace)**: shows a confirmation dialog first, then sends the files to the recycle bin. After that, the thumbnail grid is refreshed.

### Export Stitched Thumbnails
- **Export Stitched Thumbnails (Ctrl + S)**: stitches the selected images into one big image (total width 3840) using the current zoom level's column count; each cell is a thumbnail with its file name, and the height grows with the number of rows (a single column when magnified). Can be exported as PNG / JPEG.

### Format / Size / Resolution Conversion
- **Format Size Resolution Conversion**: converts the selected images to JPG / PNG and can adjust resolution and file size at the same time. Clicking it opens a settings dialog whose options are laid out as a "title row + content row":
  - **Target format**: jpg / png, default jpg.
  - **Resolution**: adjustable only when exactly 1 image is selected; the two inputs are pre-filled with that image's original width / height. A "等比" (keep aspect ratio) checkbox between width and height keeps the original aspect ratio in sync when either is edited; unchecking it reveals a "Resize mode" row — black bars / white bars / stretch / crop — for non-proportional scaling. With multiple images selected, only the title row is kept and the content shows "adjusting the resolution is only available when 1 image is selected".
  - **File size**: an optional upper limit in MB; the output is made as large as possible while staying under that value (judged on the resized image): for JPG the quality is searched to approach the limit, while PNG is lossless so its size depends only on the resolution; leaving it blank exports at the highest quality without size conversion.
  - **Output file**: choose the output folder (defaults to the current folder); clicking the folder path opens a folder picker. When exactly 1 image is selected the file name can be edited (the extension follows the target format and cannot be changed) and defaults to "{original name + conflict index}" — e.g. `aaa.png` to jpg becomes `aaa.jpg`, or `aaa(1).jpg` / `aaa(2).jpg` if those already exist. With multiple images only the folder can be chosen and the file name is hidden, using the same auto-avoid logic.

---

## Shortcuts

| Shortcut | Action |
| --- | --- |
| Wheel | Scroll vertically |
| Horizontal wheel (if available) | Pan left / right |
| Ctrl + wheel | Zoom in / out |
| Click a tile | Check / uncheck |
| Shift + click | Range select |
| Ctrl + A | Select all |
| Esc | Deselect all |
| Ctrl + S | Export stitched thumbnails |
| Ctrl + C | Copy to folder |
| Ctrl + X | Move to folder |
| Del / Backspace | Move to recycle bin (when the image view has focus) |
| Enter (in the name box) | Match names |

---

## Supported formats

- **Common images**: JPG, JPEG, PNG, BMP, GIF, TIF, TIFF, WEBP
- **RAW**: ARW, CR2, CR3, NEF, NRW, DNG, RAF, RW2, ORF, PEF, SR2, SRF, 3FR, ERF, KDC, MRW, RAW, RWL, X3F, IIQ, MOS, MEF, ARI

---

## Requirements

- **Windows** (native copy / move and the recycle bin rely on the Windows shell)
- Python 3.10+ to run from source
- Packages: `PySide6`, `Pillow`, `rawpy`

---

## Running

### From source
```bash
pip install PySide6 Pillow rawpy
python ImageThumbToDetailViewer_v3.py
```

### Prebuilt single-file exe
Double-click `dist/ImageThumbToDetailViewer.exe`. It is built in windowed mode and **shows no console window**.

---

## License

This project is licensed under **CC BY-NC-SA 4.0**
(Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International).

- **Attribution**: when you use, redistribute, or adapt it, give appropriate credit, provide the source, and indicate whether changes were made.
- **NonCommercial**: you may not use it for commercial purposes.
- **ShareAlike**: any modification or derivative work must be released under the same license.

See [LICENSE](LICENSE) for the full text, or visit
https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode .

---

## Author

**MioSleet**

- GitHub: https://github.com/miosleet
- Bilibili: https://space.bilibili.com/12788388 (密苏里秘书舰_澪霰)
- Douyin: MioSleet (澪霰就是零线)
