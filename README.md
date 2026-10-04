# Image Batch Filter (图片批量筛选器)

A desktop tool for the photo-review workflow: browse shot photos as thumbnails, inspect them
full-size, mark the keepers, and batch copy / move the selection into folders or the recycle bin.
It is not RAW-only — it works for everyday images too, with first-class RAW support.

Built with **PySide6**.

---

## Features

### Browsing
- **Open a folder** and list every supported image in it (current folder only, no recursion),
  sorted by file name.
- **Thumbnail grid** that only draws the visible tiles; images are decoded on demand in a
  background thread, so the UI never blocks on a large folder.
- **Zoom** with `Ctrl + wheel`, stepping from a dense grid (~10 columns) down to 3 / 2 / 1 column,
  and single-image magnification up to 4x.
  - When zooming, the current first image stays in the first row, and the top row stays flush
    with the top of the window.
- **Full-quality single image**: in 1-image-per-row mode (including magnification), RAW files are
  re-decoded at full resolution in the background and swapped in, so the large view is sharp.
  The grid keeps using fast embedded thumbnails / half-size previews.

### Selecting
- **Click** anywhere on a tile to check / uncheck it.
- **Shift + click** for range selection (file-manager style).
- **Match by file name**: type names or fragments separated by commas (`，` also works). A full
  name match takes priority over a substring match; each token matches at most one file. The
  result becomes the selection, and any manual selection is written back into the input box.

### Batch operations
- **Copy to New Filter Folder / Move to New Filter Folder** — creates `筛选_XX` next to the current
  folder, using the smallest unused number (e.g. if `01,02,03,07` exist, the next is `04`).
- **Copy to Folder / Move to Folder** — pick any destination folder. This uses the native Windows
  copy / move, so conflicts show the system dialog (replace / skip / keep both). If the native
  call is unavailable it falls back to a built-in conflict dialog
  (Replace / Replace all / Skip / Skip all).
- **Move to Recycle Bin** — asks for confirmation first, then sends the selection to the recycle bin.

### Quality of life
- After a successful copy, the selection and the input box are cleared.
- After a move / recycle, the list refreshes automatically.
- Memory-aware caches (preview + full-quality) keep large folders responsive.

---

## Supported formats

- **Common**: JPG, JPEG, PNG, BMP, GIF, TIF, TIFF, WEBP
- **RAW**: ARW, CR2, CR3, NEF, NRW, DNG, RAF, RW2, ORF, PEF, SR2, SRF, 3FR, ERF, KDC, MRW, RAW, RWL,
  X3F, IIQ, MOS, MEF, ARI

---

## Requirements

- **Windows** (native copy / move and recycle bin use the Windows shell)
- Python 3.10+ only if you run from source
- Packages: `PySide6`, `Pillow`, `rawpy`

---

## Running

### From source
```bash
pip install PySide6 Pillow rawpy
python raw_photo_browser_3.py
```

### Prebuilt single-file exe
Just double-click `dist/RAWPhotoBrowser3.exe`. It is built in windowed mode, so no console appears.

---

## Usage

1. Click **打开文件夹 (Open Folder)** and choose the folder containing your shots.
   Thumbnails stream in as you scroll; wait a moment for the visible area to fill in.
2. Browse and zoom (`Ctrl + wheel`).
3. Select the keepers — either click the tiles, or type file names / fragments in the input box
   (comma-separated) and press **Enter** / click **匹配文件名 (Match Names)**.
4. Send the selection to a destination:
   - **复制到新筛选文件夹 / 移动到新筛选文件夹** — create `筛选_01`, `筛选_02`, … next to the source folder.
   - **复制到指定文件夹 / 移动到指定文件夹** — choose any folder; name conflicts use the system dialog.
   - **移动到回收站** — confirm, then remove to the recycle bin.
5. Repeat. Copy keeps the originals; move / recycle refresh the list.

---

## Shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl + wheel` | Zoom in / out |
| Wheel | Scroll vertically |
| Horizontal wheel | Pan left / right |
| `Shift + click` | Range select |
| Click a tile | Check / uncheck |
| `Ctrl + C` | Copy to folder |
| `Ctrl + X` | Move to folder |
| `Del` / `Backspace` | Move to recycle bin (when the image view has focus) |
| `Enter` in the name box | Match names |

---

## Notes

- RAW grid previews use the camera's embedded thumbnail (or a half-size decode) for speed; the
  single-image view upgrades to a full-resolution decode.
- **Move to Recycle Bin** confirms first with a standard Yes / No dialog; the default button is
  **Yes**, so pressing Enter confirms.
- The **Ctrl + C** / **Ctrl + X** shortcuts are window-scoped, so they also fire when the name box
  has focus. `Del` / `Backspace` are scoped to the image view to avoid interfering with text editing.
- When running from source, progress is printed to the console; the packaged exe is silent.

---

## Building a single-file exe (optional)

```bash
pip install pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name RAWPhotoBrowser3 --collect-all rawpy --exclude-module matplotlib --exclude-module tkinter --exclude-module scipy --exclude-module pandas --exclude-module IPython --exclude-module pytest raw_photo_browser_3.py
```

Output: `dist/RAWPhotoBrowser3.exe`.

---

## Files

- `raw_photo_browser_3.py` — application source (v3)
- `raw_photo_browser_2.2.py` — previous version
- `readme.md` — English documentation
- `readme_zh.md` — Chinese documentation
