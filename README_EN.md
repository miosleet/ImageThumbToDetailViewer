# Image Batch Filter (图片批量筛选器)

A desktop tool for the photo-review workflow: thumbnail browsing, full-size viewing, and
check-and-classify, plus batch copy / move of the selected images to a folder or the recycle bin.
It also works for ordinary image formats, and has good support for camera RAW.

Built with **PySide6**.

---

## Features

### Browsing
- **Open Folder (打开文件夹)**: lists every supported image in the folder (current folder only, no
  recursion into subfolders), sorted by file name.
- **Thumbnail grid**: virtualized rendering that only draws the visible tiles; images are loaded on
  demand in a background thread, so large folders won't freeze the UI.
- **Zoom**: `Ctrl + wheel` steps through zoom levels, from a dense grid of about 10 columns up to
  single-image magnification (up to about 4x), and keeps the image under the cursor under the cursor after zooming.
- **Full-quality single image**: in 1-image-per-row mode (including magnification), RAW files are
  re-decoded at full resolution in the background and swapped in, keeping the large view sharp;

### Selecting
- **Click** anywhere on a tile: check / uncheck.
- **Shift + click**: range selection (file-manager style).
- **Match by file name**: type file names or fragments, separated by English / Chinese commas. An
  exact file-name match takes priority, then substring matching; each entry matches at most one file.
  The matches become the current selection, and manual selections are also written back to the input box.

### Batch operations
- **Copy to New Filter Folder / Move to New Filter Folder (复制到新筛选文件夹 / 移动到新筛选文件夹)**:
  create `筛选_XX` next to the current folder, using the smallest unused number.
- **Copy to Folder / Move to Folder (复制到指定文件夹 / 移动到指定文件夹)**: choose any destination
  folder. Uses the native system copy / move; on a name conflict it pops up the system's own conflict
  dialog (replace / skip / keep both). If the native call is unavailable, it falls back to a built-in
  conflict dialog (replace / replace all / skip / skip all).
- **Move to Recycle Bin (移动到回收站)**: shows a confirmation dialog first, then sends the files to
  the recycle bin.

### Quality of life
- After a successful copy, the selection and the input box are cleared automatically.
- After a move / delete, the list refreshes automatically.
- Previews and full-quality images are cached and evicted separately, so browsing large folders stays smooth.

---

## Usage

1. Click **Open Folder (打开文件夹)** and choose the folder that holds your photos.
   Thumbnails load progressively as you scroll; wait a moment for the current area to fill in.
2. Zoom and browse with `Ctrl + wheel`.
3. Pick the keepers — click tiles to check them, or type file names / fragments (comma-separated) in
   the input box and press **Enter** or click **Match Names (匹配文件名)**.
4. Send the selected images to a destination:
   - **Copy to New Filter Folder / Move to New Filter Folder** — creates `筛选_01`, `筛选_02`, … next to the source folder.
   - **Copy to Folder / Move to Folder** — choose a destination folder; name conflicts are handled by the system dialog.
   - **Move to Recycle Bin** — confirm, then delete to the recycle bin.
5. Repeat the flow. Copy keeps the originals; after a move / delete the list refreshes automatically.

---

## Shortcuts

| Shortcut | Action |
| --- | --- |
| Wheel | Scroll vertically |
| Horizontal wheel (if available) | Pan left / right |
| Ctrl + wheel | Zoom in / out |
| Click a tile | Check / uncheck |
| Shift + click | Range select |
| Ctrl + C | Copy to folder |
| Ctrl + X | Move to folder |
| Del / Backspace | Move to recycle bin (when the image view has focus) |
| Enter (in the name box) | Match names |

---

## Supported formats

- **Common images**: JPG, JPEG, PNG, BMP, GIF, TIF, TIFF, WEBP
- **RAW**: ARW, CR2, CR3, NEF, NRW, DNG, RAF, RW2, ORF, PEF, SR2, SRF, 3FR, ERF, KDC, MRW,
  RAW, RWL, X3F, IIQ, MOS, MEF, ARI

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
python raw_photo_browser_3.py
```

### Prebuilt single-file exe
Double-click `dist/RAWPhotoBrowser3.exe`. It is built in windowed mode and **shows no console window**.
