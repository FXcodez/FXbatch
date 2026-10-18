# image_compressor.py — FXbatch v2.5.0 Multi-Core Image & Icon Processing Engine
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
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tga", ".tif", ".tiff", ".avif", ".ico"
)

OUTPUT_FORMATS = ("JPG", "PNG", "WEBP", "AVIF", "ICO")

ICO_SIZES = ("bundle", "256", "128", "64", "48", "32", "16")

RESAMPLE_FILTERS = {
    "lanczos": Image.LANCZOS,
    "bicubic": Image.BICUBIC,
    "bilinear": Image.BILINEAR,
    "nearest": Image.NEAREST,
}


class ProcessResult(NamedTuple):
    status: str  # "ok", "skipped", "error"
    filename: str
    input_bytes: int
    output_bytes: int
    error: str = ""


def _crop_to_square(img: Image.Image) -> Image.Image:
    """Center-crop an image to a 1:1 square ratio to avoid icon stretching."""
    w, h = img.size
    if w == h:
        return img
    min_edge = min(w, h)
    left = (w - min_edge) // 2
    top = (h - min_edge) // 2
    return img.crop((left, top, left + min_edge, top + min_edge))


def _generate_favicon_package(
    img: Image.Image,
    output_dir: str,
    base_stem: str,
    is_single: bool,
    resample_filter,
    primary_output_path: str = "",
) -> int:
    """Generates a complete web favicon bundle:
    - favicon.ico (multi-resolution 16, 32, 48px)
    - favicon-16x16.png
    - favicon-32x32.png
    - apple-touch-icon.png (180x180)
    For single image: standard web root filenames.
    For batch images: prefixed with base_stem.
    Returns total auxiliary bytes written (excluding primary_output_path if identical).
    """
    square = _crop_to_square(img)
    rgba = _prepare_image_for_format(square, "ico")

    prefix = "" if is_single else f"{base_stem}_"

    ico_path = os.path.join(output_dir, f"{prefix}favicon.ico")
    p16_path = os.path.join(output_dir, f"{prefix}favicon-16x16.png")
    p32_path = os.path.join(output_dir, f"{prefix}favicon-32x32.png")
    apple_path = os.path.join(output_dir, f"{prefix}apple-touch-icon.png")

    # 1. Multi-resolution favicon.ico (16, 32, 48px)
    rgba.save(ico_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])

    # 2. 16x16 PNG
    img_16 = rgba.resize((16, 16), resample_filter)
    img_16.save(p16_path, format="PNG", optimize=True)

    # 3. 32x32 PNG
    img_32 = rgba.resize((32, 32), resample_filter)
    img_32.save(p32_path, format="PNG", optimize=True)

    # 4. 180x180 apple-touch-icon PNG
    img_apple = rgba.resize((180, 180), resample_filter)
    img_apple.save(apple_path, format="PNG", optimize=True)

    extra_bytes = os.path.getsize(p16_path) + os.path.getsize(p32_path) + os.path.getsize(apple_path)
    if not primary_output_path or os.path.normcase(os.path.abspath(primary_output_path)) != os.path.normcase(os.path.abspath(ico_path)):
        extra_bytes += os.path.getsize(ico_path)

    return extra_bytes


def compute_target_dimensions(orig_w: int, orig_h: int, mode: str, params: dict) -> tuple[int, int]:
    """Calculate target (width, height) based on sizing mode and parameters."""
    if orig_w <= 0 or orig_h <= 0:
        return (1, 1)

    if mode == "percent":
        pct = max(5, min(int(params.get("percent", 40)), 200))
        new_w = max(1, int(orig_w * pct / 100))
        new_h = max(1, int(orig_h * pct / 100))
        return (new_w, new_h)

    elif mode == "bounding_box":
        max_w = max(16, int(params.get("max_width", 1920)))
        max_h = max(16, int(params.get("max_height", 1080)))
        scale = min(max_w / orig_w, max_h / orig_h)
        new_w = max(1, int(orig_w * scale))
        new_h = max(1, int(orig_h * scale))
        return (new_w, new_h)

    elif mode == "fixed_width":
        target_w = max(16, int(params.get("fixed_width", 1200)))
        scale = target_w / orig_w
        new_h = max(1, int(orig_h * scale))
        return (target_w, new_h)

    elif mode == "fixed_height":
        target_h = max(16, int(params.get("fixed_height", 800)))
        scale = target_h / orig_h
        new_w = max(1, int(orig_w * scale))
        return (new_w, target_h)

    elif mode == "ico":
        ico_size = str(params.get("ico_size", "bundle")).lower()
        if ico_size == "bundle" or not ico_size.isdigit():
            return (256, 256)
        sz = max(16, min(int(ico_size), 256))
        return (sz, sz)

    return (orig_w, orig_h)


def _prepare_image_for_format(img: Image.Image, fmt: str) -> Image.Image:
    """Prepares image color mode and alpha channels for specific encoding standards."""
    fmt = fmt.lower()
    if fmt in ("jpg", "jpeg"):
        if img.mode == "RGB":
            return img
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            rgba = img.convert("RGBA")
            bg = Image.new("RGB", rgba.size, (255, 255, 255))
            bg.paste(rgba, mask=rgba.split()[3])
            return bg
        return img.convert("RGB")

    elif fmt in ("webp", "avif"):
        if img.mode in ("RGB", "RGBA"):
            return img
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            return img.convert("RGBA")
        return img.convert("RGB")

    elif fmt == "ico":
        # Windows icons support 32-bit RGBA
        return img.convert("RGBA")

    elif fmt == "png":
        return img

    return img


def build_output_filename(
    input_filename: str,
    target_ext: str,
    template: str = "{name}",
    orig_w: int = 0,
    orig_h: int = 0,
    new_w: int = 0,
    new_h: int = 0,
    quality: int = 60,
) -> str:
    """Renders filename using naming tokens such as {name}, {w}, {h}, {quality}."""
    stem, _ = os.path.splitext(input_filename)
    clean_ext = target_ext.lstrip(".").lower()

    safe_template = template if template and "{name}" in template else "{name}"
    rendered = safe_template.format(
        name=stem,
        w=new_w,
        h=new_h,
        orig_w=orig_w,
        orig_h=orig_h,
        quality=quality,
    )
    # Sanitize forbidden filename characters
    for char in '<>:"/\\|?*':
        rendered = rendered.replace(char, "_")

    return f"{rendered.strip()}.{clean_ext}"


def compress_and_resize_image(args) -> ProcessResult:
    (
        input_path,
        output_path,
        quality,
        resize_mode,
        resize_params,
        dpi_tuple,
        fmt,
        filter_name,
        should_skip,
    ) = args

    filename = os.path.basename(input_path)
    input_bytes = 0
    try:
        input_bytes = os.path.getsize(input_path)
    except OSError:
        pass

    if should_skip:
        return ProcessResult(
            status="skipped",
            filename=filename,
            input_bytes=input_bytes,
            output_bytes=0,
            error="Skipped (already exists)",
        )

    try:
        fmt_norm = "jpg" if fmt in ("jpg", "jpeg") else fmt.lower()
        resample_filter = RESAMPLE_FILTERS.get(filter_name.lower(), Image.LANCZOS)

        with Image.open(input_path) as img:
            img = ImageOps.exif_transpose(img)
            orig_w, orig_h = img.size

            extra_bytes = 0
            # Sizing mode transformation
            if fmt_norm == "ico":
                # Ensure 1:1 square crop for ICO conversion
                img = _crop_to_square(img)
                ico_size = str(resize_params.get("ico_size", "bundle")).lower()

                img = _prepare_image_for_format(img, fmt_norm)

                if ico_size == "bundle":
                    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
                    img.save(output_path, format="ICO", sizes=sizes)
                else:
                    target_sz = max(16, min(int(ico_size), 256))
                    img = img.resize((target_sz, target_sz), resample_filter)
                    img.save(output_path, format="ICO")

                create_favicon = bool(resize_params.get("create_favicon", False))
                if create_favicon:
                    is_single = bool(resize_params.get("is_single_image", False))
                    base_stem, _ = os.path.splitext(filename)
                    output_dir = os.path.dirname(output_path)
                    extra_bytes = _generate_favicon_package(
                        img,
                        output_dir=output_dir,
                        base_stem=base_stem,
                        is_single=is_single,
                        resample_filter=resample_filter,
                        primary_output_path=output_path,
                    )
            else:
                new_w, new_h = compute_target_dimensions(orig_w, orig_h, resize_mode, resize_params)
                if (new_w, new_h) != (orig_w, orig_h):
                    img = img.resize((new_w, new_h), resample_filter)

                img = _prepare_image_for_format(img, fmt_norm)

                if fmt_norm == "jpg":
                    img.save(output_path, format="JPEG", quality=quality, optimize=True, dpi=dpi_tuple)
                elif fmt_norm == "png":
                    img.save(output_path, format="PNG", optimize=True, dpi=dpi_tuple)
                elif fmt_norm == "webp":
                    img.save(output_path, format="WEBP", quality=quality, method=4, dpi=dpi_tuple)
                elif fmt_norm == "avif":
                    img.save(output_path, format="AVIF", quality=quality)
                else:
                    raise ValueError(f"Unsupported format: {fmt}")

        output_bytes = os.path.getsize(output_path) + extra_bytes
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
        return sorted([
            entry.name for entry in it
            if entry.is_file() and entry.name.lower().endswith(SUPPORTED_EXTENSIONS)
        ])


def process_images_in_folder(
    folder_path: str,
    output_folder: str,
    quality: int,
    resize_mode: str,
    resize_params: dict,
    dpi: str | int,
    progress_callback: Callable[..., None] | None,
    cancel_event,
    image_type: str,
    resample_filter: str = "lanczos",
    collision_policy: str = "overwrite",
    filename_template: str = "{name}",
) -> list[ProcessResult]:
    os.makedirs(output_folder, exist_ok=True)
    fmt = image_type.lower().replace(".", "")
    dpi_val = max(1, int(dpi or 72))
    dpi_tuple = (dpi_val, dpi_val)

    input_entries = list_supported_images(folder_path)
    total_files = len(input_entries)
    if total_files == 0:
        return []

    used_names: set[str] = set()
    args_list = []
    is_single = (total_files == 1)
    task_resize_params = dict(resize_params)
    task_resize_params["is_single_image"] = is_single

    for fname in input_entries:
        in_path = os.path.join(folder_path, fname)
        # Sizing estimation for naming tokens
        base_name = build_output_filename(fname, fmt, filename_template, quality=quality)
        out_path = os.path.join(output_folder, base_name)
        should_skip = False

        if collision_policy == "skip" and (os.path.exists(out_path) or out_path.lower() in used_names):
            should_skip = True
        elif collision_policy == "rename":
            stem, ext = os.path.splitext(base_name)
            candidate = base_name
            counter = 1
            while os.path.exists(os.path.join(output_folder, candidate)) or candidate.lower() in used_names:
                candidate = f"{stem}_{counter}{ext}"
                counter += 1
            base_name = candidate
            out_path = os.path.join(output_folder, base_name)

        used_names.add(out_path.lower())
        args_list.append((
            in_path,
            out_path,
            quality,
            resize_mode,
            task_resize_params,
            dpi_tuple,
            fmt,
            resample_filter,
            should_skip,
        ))

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
                        progress_callback(i / total_files, i, total_files, res.filename, res.status)
                    except TypeError:
                        try:
                            progress_callback(i / total_files, i, total_files, res.filename)
                        except Exception:
                            pass
                    except Exception:
                        pass

        if cancel_event is None or not cancel_event.is_set():
            pool.close()
            pool.join()

    return results


def encode_sample_in_memory(
    pil_img: Image.Image,
    quality: int,
    resize_mode: str,
    resize_params: dict,
    dpi: str | int,
    image_type: str,
    filter_name: str = "lanczos",
) -> tuple[int, int, int, bool]:
    """Encodes a sample in RAM for real-time telemetry metrics.
    Returns: (new_width, new_height, compressed_bytes, is_original_square)"""
    orig_w, orig_h = pil_img.size
    is_square = (orig_w == orig_h)
    fmt = image_type.lower().replace(".", "")
    fmt_norm = "jpg" if fmt in ("jpg", "jpeg") else fmt
    resample_filter = RESAMPLE_FILTERS.get(filter_name.lower(), Image.LANCZOS)

    work_img = pil_img.copy()

    if fmt_norm == "ico":
        work_img = _crop_to_square(work_img)
        ico_size = str(resize_params.get("ico_size", "bundle")).lower()
        if ico_size == "bundle":
            new_w, new_h = (256, 256)
        else:
            target_sz = max(16, min(int(ico_size), 256))
            new_w, new_h = (target_sz, target_sz)
            work_img = work_img.resize((new_w, new_h), resample_filter)
    else:
        new_w, new_h = compute_target_dimensions(orig_w, orig_h, resize_mode, resize_params)
        if (new_w, new_h) != (orig_w, orig_h):
            work_img = work_img.resize((new_w, new_h), resample_filter)

    work_img = _prepare_image_for_format(work_img, fmt_norm)
    dpi_val = max(1, int(dpi or 72))
    buf = io.BytesIO()

    if fmt_norm == "jpg":
        work_img.save(buf, format="JPEG", quality=quality, optimize=False, dpi=(dpi_val, dpi_val))
    elif fmt_norm == "png":
        work_img.save(buf, format="PNG", optimize=False, dpi=(dpi_val, dpi_val))
    elif fmt_norm == "webp":
        work_img.save(buf, format="WEBP", quality=quality, method=3, dpi=(dpi_val, dpi_val))
    elif fmt_norm == "avif":
        work_img.save(buf, format="AVIF", quality=quality)
    extra_bytes = 0
    if fmt_norm == "ico":
        work_img.save(buf, format="ICO")
        if resize_params.get("create_favicon", False):
            fav_buf = io.BytesIO()
            fav_rgba = _prepare_image_for_format(_crop_to_square(pil_img), "ico")
            fav_rgba.save(fav_buf, format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
            for sz in (16, 32, 180):
                fav_rgba.resize((sz, sz), resample_filter).save(fav_buf, format="PNG")
            extra_bytes = fav_buf.tell()

    return new_w, new_h, buf.tell() + extra_bytes, is_square


def format_size(size_bytes: float) -> str:
    size = float(max(0, size_bytes))
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"
