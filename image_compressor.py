# image_compressor.py — FXbatch v04 (Pure Native Scaling)
from __future__ import annotations
import io
import multiprocessing
import os
import time
from typing import Callable, NamedTuple
from PIL import Image, ImageFile, ImageOps

ImageFile.LOAD_TRUNCATED_IMAGES = True
Image.MAX_IMAGE_PIXELS = None

SUPPORTED_EXTENSIONS = (
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tga", ".tif", ".tiff"
)


class ProcessResult(NamedTuple):
    status: str
    filename: str
    input_bytes: int
    output_bytes: int
    error: str = ""


def _prepare_image_for_format(img: Image.Image, fmt: str) -> Image.Image:
    """Flatten alpha/palette transparency onto white ONLY when needed for JPEG."""
    if fmt == "jpg":
        if img.mode == "RGB":
            return img
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            rgba = img.convert("RGBA")
            bg = Image.new("RGB", rgba.size, (255, 255, 255))
            bg.paste(rgba, mask=rgba.split()[3])
            return bg
        return img.convert("RGB")
    elif fmt == "webp":
        if img.mode in ("RGB", "RGBA"):
            return img
        if img.mode == "P":
            return img.convert("RGBA" if "transparency" in img.info else "RGB")
        return img.convert("RGB")
    return img


def compress_and_resize_image(args) -> ProcessResult:
    input_path, output_path, quality, resize_percent, dpi_tuple, fmt = args
    filename = os.path.basename(input_path)
    input_bytes = 0
    try:
        input_bytes = os.path.getsize(input_path)
    except OSError:
        pass

    try:
        with Image.open(input_path) as img:
            img = ImageOps.exif_transpose(img)

            if resize_percent != 100:
                new_width = max(1, int(img.width * resize_percent / 100))
                new_height = max(1, int(img.height * resize_percent / 100))
                img = img.resize((new_width, new_height), Image.LANCZOS)

            fmt_norm = "jpg" if fmt in ("jpg", "jpeg") else fmt
            if fmt_norm == "jpg":
                if img.mode != "RGB":
                    img = _prepare_image_for_format(img, fmt_norm)
                img.save(output_path, format="JPEG", quality=quality, optimize=True, dpi=dpi_tuple)
            elif fmt_norm == "png":
                img.save(output_path, format="PNG", optimize=True, dpi=dpi_tuple)
            elif fmt_norm == "webp":
                if img.mode not in ("RGB", "RGBA"):
                    img = _prepare_image_for_format(img, fmt_norm)
                img.save(output_path, format="WEBP", quality=quality, method=4, dpi=dpi_tuple)
            else:
                raise ValueError(f"Unsupported image type: {fmt}")

        output_bytes = os.path.getsize(output_path)
        return ProcessResult(
            status="ok",
            filename=filename,
            input_bytes=input_bytes,
            output_bytes=output_bytes,
            error="",
        )
    except Exception as e:
        return ProcessResult(
            status="error",
            filename=filename,
            input_bytes=input_bytes,
            output_bytes=0,
            error=str(e),
        )


def list_supported_images(folder_path: str) -> list[str]:
    if not os.path.isdir(folder_path):
        return []
    with os.scandir(folder_path) as it:
        return [
            entry.name for entry in it
            if entry.is_file() and entry.name.lower().endswith(SUPPORTED_EXTENSIONS)
        ]


def build_unique_output_path(output_folder: str, input_filename: str, ext: str, used_names: set[str]) -> str:
    stem, orig_ext = os.path.splitext(input_filename)
    candidate = f"{stem}.{ext}"
    if candidate.lower() in used_names:
        clean_orig = orig_ext.lstrip(".").lower()
        candidate = f"{stem}_{clean_orig}.{ext}"
        counter = 2
        while candidate.lower() in used_names:
            candidate = f"{stem}_{clean_orig}_{counter}.{ext}"
            counter += 1
    used_names.add(candidate.lower())
    return os.path.join(output_folder, candidate)


def process_images_in_folder(
    folder_path: str,
    output_folder: str,
    quality: int,
    resize_percent: int,
    dpi: str | int,
    progress_callback: Callable[..., None] | None,
    cancel_event,
    image_type: str,
) -> list[ProcessResult]:
    os.makedirs(output_folder, exist_ok=True)
    fmt = image_type.lower()
    dpi_val = max(1, int(dpi or 72))
    dpi_tuple = (dpi_val, dpi_val)

    input_entries = []
    with os.scandir(folder_path) as it:
        for entry in it:
            if entry.is_file() and entry.name.lower().endswith(SUPPORTED_EXTENSIONS):
                input_entries.append(entry.name)

    total_files = len(input_entries)
    if total_files == 0:
        return []

    used_names: set[str] = set()
    args_list = [
        (
            os.path.join(folder_path, fname),
            build_unique_output_path(output_folder, fname, fmt, used_names),
            quality,
            resize_percent,
            dpi_tuple,
            fmt,
        )
        for fname in input_entries
    ]

    # Automatically utilizes all available CPU cores/threads on any architecture (Intel P/E or AMD Zen)
    num_cores = os.cpu_count() or 4
    chunksize = max(1, min(8, total_files // (num_cores * 2)))

    results: list[ProcessResult] = []
    last_ui_update = 0.0

    with multiprocessing.Pool(processes=num_cores) as pool:
        for i, res in enumerate(
            pool.imap_unordered(compress_and_resize_image, args_list, chunksize=chunksize), 1
        ):
            results.append(res)

            if cancel_event is not None and cancel_event.is_set():
                pool.terminate()
                pool.join()
                break

            now = time.monotonic()
            if (now - last_ui_update) >= 0.05 or i == total_files:
                last_ui_update = now
                if progress_callback:
                    try:
                        progress_callback(i / total_files, i, total_files, res.filename)
                    except TypeError:
                        progress_callback(i / total_files, i, total_files)

    return results


def encode_sample_in_memory(pil_img: Image.Image, quality: int, resize_percent: int, dpi: str | int, image_type: str) -> tuple[int, int, int]:
    orig_w, orig_h = pil_img.size
    new_w = max(1, int(orig_w * resize_percent / 100))
    new_h = max(1, int(orig_h * resize_percent / 100))

    work_img = pil_img.resize((new_w, new_h), Image.LANCZOS) if resize_percent != 100 else pil_img.copy()
    fmt = image_type.lower()
    fmt_norm = "jpg" if fmt in ("jpg", "jpeg") else fmt
    work_img = _prepare_image_for_format(work_img, fmt_norm)

    dpi_val = max(1, int(dpi or 72))
    buf = io.BytesIO()

    if fmt_norm == "jpg":
        work_img.save(buf, format="JPEG", quality=quality, optimize=True, dpi=(dpi_val, dpi_val))
    elif fmt_norm == "png":
        work_img.save(buf, format="PNG", optimize=True, dpi=(dpi_val, dpi_val))
    elif fmt_norm == "webp":
        work_img.save(buf, format="WEBP", quality=quality, method=4, dpi=(dpi_val, dpi_val))

    return new_w, new_h, buf.tell()


def format_size(size_bytes: float) -> str:
    size = float(max(0, size_bytes))
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"