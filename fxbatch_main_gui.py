# fxbatch_main_gui.py — FXbatch v05 (Complete Integrated Application)
from __future__ import annotations

import configparser
import ctypes
import logging
from logging.handlers import RotatingFileHandler
import os
from os import path
from queue import Queue, Empty
from random import choice
import shutil
import sys
from threading import Thread, Event
import time
import webbrowser
import customtkinter as ctk

from widgets import (
    WidgetCreator,
    ThemeDivider,
    HEAD_FONT,
    BODY_FONT,
    MONO_FONT,
    COLOR_BG,
    COLOR_SURFACE,
    COLOR_SURFACE_2,
    COLOR_BORDER,
    COLOR_BORDER_2,
    COLOR_TEXT,
    COLOR_TEXT_3,
    COLOR_MUTED,
    COLOR_BRAND,
    COLOR_BRAND_HOVER,
    COLOR_ON_BRAND,
    COLOR_SUCCESS,
    COLOR_SUCCESS_BG,
    CORNER_RADIUS,
    BORDER_WIDTH,
)
from image_compressor import (
    SUPPORTED_EXTENSIONS,
    list_supported_images,
    format_size,
    encode_sample_in_memory,
    process_images_in_folder,
)

APP_VERSION = "2.0.0"
APP_DISPLAY_VERSION = "2.0.0"
DEFAULT_BATCH_FOLDER = "LowRes"


def _setup_app_logger() -> logging.Logger:
    app_logger = logging.getLogger("FXbatch")
    if app_logger.handlers:
        return app_logger

    app_logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    appdata = os.environ.get("APPDATA") or path.expanduser("~")
    log_dir = path.join(appdata, "FXbatch")
    try:
        os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(
            path.join(log_dir, "fxbatch.log"), maxBytes=1_000_000, backupCount=2, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        app_logger.addHandler(file_handler)
    except OSError:
        pass

    if not getattr(sys, "frozen", False):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        app_logger.addHandler(console_handler)

    return app_logger


logger = _setup_app_logger()


class ImageCompressorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.path = path
        self.sys = sys

        # Runtime State
        self.is_processing = False
        self.cancel_event = Event()
        self.image_files: list[str] = []
        self.sample_image: str | None = None
        self.cached_sample_img = None
        self.sample_orig_size = 0
        self.sample_dpi_val = 72.0
        self.current_preview = None
        self.current_theme = "Dark"
        self.is_loaded_state = False
        self._preview_worker_id = 0
        self._warmup_start_time = 0.0
        self._warmup_duration = 2.5
        self._warmup_target = 0.10
        self._display_progress = 0.0
        self._real_progress = 0.0

        self.previous_input_folder = ""
        self.previous_output_folder = ""

        # UI Variables
        self.input_folder_path = ctk.StringVar(value="")
        self.output_folder_path = ctk.StringVar(value="")
        self.quality = ctk.IntVar(value=60)
        self.resize_percent = ctk.IntVar(value=40)
        self.sample_image_info = ctk.StringVar(value="No folder selected")
        self.image_types = ["JPG", "PNG", "WEBP"]
        self.selected_image_type = ctk.StringVar(value="JPG")
        self.image_dpi = ctk.StringVar(value="72")
        self.initial_dpi = "72"
        self.batch_folder_name = DEFAULT_BATCH_FOLDER
        self.startup_theme_mode = "Dark"
        self.settings_window: SettingsWindow | None = None

        # Setup OS integration & configuration
        self.set_taskbar_icon()
        self.setup_window()
        self.load_config()

        # Build exact UI from widgets.py (WidgetCreator)
        self.widget_creator = WidgetCreator(
            self,
            ctk,
            self.quality.get(),
            self.resize_percent.get(),
            self.image_dpi.get(),
        )
        self.main_body = self.widget_creator.create_widgets()

        # Apply startup appearance mode & update button toggles
        self.set_theme(self.startup_theme_mode)

        # Set default empty state
        self.set_empty_state()

        # Bind events
        self.bind_events()

        # Thread-safe UI dispatch queue (Python 3.12+ safe)
        self.ui_queue: Queue[tuple] = Queue()
        self._poll_ui_queue()

        # Defer Drag-and-Drop initialization until after window has rendered
        self.after(20, self._deferred_init_dnd)

    def dispatch_ui(self, func, *args, **kwargs):
        """Thread-safe UI dispatcher that works seamlessly from background threads in Python 3.12+."""
        self.ui_queue.put((func, args, kwargs))

    def _poll_ui_queue(self):
        """Processes queued UI actions safely on the main Tkinter thread."""
        try:
            while True:
                func, args, kwargs = self.ui_queue.get_nowait()
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Error executing queued UI task: {e}")
        except Empty:
            pass
        if self.winfo_exists():
            self.after(20, self._poll_ui_queue)

    # ------------------------------------------------------------------
    # Window Setup, Icons & Paths
    # ------------------------------------------------------------------
    @staticmethod
    def get_bundle_dir() -> str:
        if getattr(sys, "frozen", False):
            return sys._MEIPASS
        return path.dirname(path.abspath(__file__))

    def get_config_path(self) -> str:
        """Persist user settings in %APPDATA%\\FXbatch when frozen, or local dir in dev."""
        if getattr(sys, "frozen", False):
            appdata = os.environ.get("APPDATA") or path.expanduser("~")
            config_dir = path.join(appdata, "FXbatch")
            os.makedirs(config_dir, exist_ok=True)
            user_cfg = path.join(config_dir, "config.ini")
            bundled_cfg = path.join(self.get_bundle_dir(), "config.ini")
            if not path.exists(user_cfg) and path.exists(bundled_cfg):
                try:
                    shutil.copy2(bundled_cfg, user_cfg)
                except OSError:
                    pass
            return user_cfg
        return path.join(self.get_bundle_dir(), "config.ini")

    def get_icon_path(self) -> str | None:
        base = self.get_bundle_dir()
        candidates = [
            path.join(base, "Design", "Logos", "favicon.ico"),
            path.join(base, "icons", "fx.ico"),
            path.join(base, "icons", "fx.png"),
        ]
        for c in candidates:
            if path.exists(c):
                return c
        return None

    def set_taskbar_icon(self):
        if sys.platform.startswith("win"):
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    f"fxdesignz.fxbatch.resizer.{APP_VERSION}"
                )
            except Exception:
                pass

    def setup_window(self):
        self.title(f"FXbatch Resizer {APP_DISPLAY_VERSION}")
        w, h = 920, 820
        self.geometry(f"{w}x{h}")
        self.minsize(920, 760)
        self.configure(fg_color=COLOR_BG)
        self.center_window(w, h)

        icon_path = self.get_icon_path()
        if icon_path and sys.platform.startswith("win") and icon_path.endswith(".ico"):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

    def center_window(self, width: int, height: int):
        try:
            scaling_factor = self._get_window_scaling()
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            x = int(((screen_width / 2) - (width / 2)) * scaling_factor)
            y = int(((screen_height / 2) - (height / 2)) * scaling_factor)
            self.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Configuration & Theme Management
    # ------------------------------------------------------------------
    def load_config(self):
        self.config = configparser.ConfigParser()
        config_path = self.get_config_path()
        if path.exists(config_path):
            self.config.read(config_path)
        else:
            self.config["Help"] = {"help_url": "help.html"}
            self.config["Settings"] = {
                "quality": "60",
                "resize": "40",
                "dpi": "72",
                "batch_folder": DEFAULT_BATCH_FOLDER,
                "version": APP_VERSION,
                "theme_mode": "Dark",
            }
            try:
                with open(config_path, "w") as configfile:
                    self.config.write(configfile)
            except OSError:
                pass

        self.quality.set(self.config.getint("Settings", "quality", fallback=60))
        self.resize_percent.set(self.config.getint("Settings", "resize", fallback=40))
        dpi_str = self.config.get("Settings", "dpi", fallback="72")
        self.image_dpi.set(dpi_str)
        self.initial_dpi = dpi_str
        self.batch_folder_name = self.config.get("Settings", "batch_folder", fallback=DEFAULT_BATCH_FOLDER)
        self.startup_theme_mode = self.config.get("Settings", "theme_mode", fallback="Dark")

    def set_theme(self, mode: str):
        self.current_theme = mode
        ctk.set_appearance_mode(mode)
        self._update_theme_switch_ui()

    def _update_theme_switch_ui(self):
        resolved = ctk.get_appearance_mode()
        if resolved == "Light":
            if hasattr(self, "btn_light") and hasattr(self, "btn_dark"):
                self.btn_light.configure(
                    fg_color=COLOR_BRAND,
                    hover_color=COLOR_BRAND_HOVER,
                    text_color=COLOR_ON_BRAND,
                )
                self.btn_dark.configure(
                    fg_color="transparent",
                    hover_color=COLOR_SURFACE,
                    text_color=COLOR_MUTED,
                )
        else:
            if hasattr(self, "btn_light") and hasattr(self, "btn_dark"):
                self.btn_dark.configure(
                    fg_color=COLOR_BRAND,
                    hover_color=COLOR_BRAND_HOVER,
                    text_color=COLOR_ON_BRAND,
                )
                self.btn_light.configure(
                    fg_color="transparent",
                    hover_color=COLOR_SURFACE,
                    text_color=COLOR_MUTED,
                )

    # ------------------------------------------------------------------
    # Drag-and-Drop & Events
    # ------------------------------------------------------------------
    def bind_events(self):
        self.input_entry.bind("<FocusOut>", self.validate_input_folder)
        self.output_entry.bind("<FocusOut>", self.validate_output_folder)
        self.input_entry.bind("<Return>", self.validate_input_folder)
        self.output_entry.bind("<Return>", self.validate_output_folder)

    def _deferred_init_dnd(self):
        try:
            from tkinterdnd2 import TkinterDnD, DND_FILES
            TkinterDnD._require(self)

            def register_target(widget, callback):
                if widget is None:
                    return
                targets = [widget]
                for attr in ("_entry", "_canvas", "_label", "_textbox"):
                    inner = getattr(widget, attr, None)
                    if inner is not None:
                        targets.append(inner)

                for t in targets:
                    try:
                        if not hasattr(t, "drop_target_register"):
                            t.__class__.__bases__ += (TkinterDnD.DnDWrapper,)
                        t.drop_target_register(DND_FILES)
                        t.dnd_bind("<<Drop>>", callback)
                    except Exception:
                        try:
                            self.tk.call("tkdnd::drop_target", "register", t._w, DND_FILES)
                            cmd = t._register(callback, self._dnd_substitute, needcleanup=1)
                            t.tk.call("bind", t._w, "<<Drop>>", cmd)
                        except Exception:
                            pass

            register_target(self.input_entry, self._handle_input_drop)
            register_target(self.output_entry, self._handle_output_drop)
            register_target(self.dropzone_frame, self._handle_input_drop)
            register_target(self.image_preview_frame, self._handle_input_drop)
            register_target(self.preview_card, self._handle_input_drop)
            register_target(self.main_body, self._handle_input_drop)
            register_target(self, self._handle_input_drop)

        except Exception as e:
            logger.warning(f"DnD initialization failed: {e}")

    def _parse_dropped_path(self, raw_data: str) -> str | None:
        if not raw_data:
            return None
        cleaned = raw_data.strip()
        unbraced = cleaned.strip("{}").strip('"').strip("'")
        if path.exists(unbraced):
            return unbraced
        try:
            parts = self.tk.splitlist(cleaned)
            if parts:
                first = parts[0].strip("{}").strip('"').strip("'")
                if path.exists(first):
                    return first
        except Exception:
            pass
        return unbraced if unbraced else None

    def _handle_input_drop(self, event):
        raw_data = getattr(event, "data", None) or str(event)
        dropped = self._parse_dropped_path(raw_data)
        if not dropped:
            return

        def _process():
            if path.isdir(dropped):
                self.input_folder_path.set(dropped)
                self.validate_input_folder()
            elif path.isfile(dropped) and dropped.lower().endswith(SUPPORTED_EXTENSIONS):
                parent_dir = path.dirname(dropped)
                self.input_folder_path.set(parent_dir)
                self.validate_input_folder(preferred_sample=dropped)
            else:
                self.show_centered_messagebox(
                    "Invalid Drop",
                    "Please drop a folder or a supported image file.",
                    icon="warning",
                )

        self.after(20, _process)

    def _handle_output_drop(self, event):
        raw_data = getattr(event, "data", None) or str(event)
        dropped = self._parse_dropped_path(raw_data)
        if not dropped:
            return

        def _process():
            if path.isdir(dropped):
                self.output_folder_path.set(dropped)
                self.validate_output_folder()
            elif path.isfile(dropped):
                self.output_folder_path.set(path.dirname(dropped))
                self.validate_output_folder()

        self.after(20, _process)

    # ------------------------------------------------------------------
    # Folder Browsing & Validation
    # ------------------------------------------------------------------
    def browse_input_folder(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory()
        if folder:
            self.input_folder_path.set(folder)
            self.validate_input_folder()

    def browse_output_folder(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder_path.set(folder)
            self.validate_output_folder()

    def set_default_output_folder(self):
        in_folder = self.input_folder_path.get().strip()
        if in_folder and path.isdir(in_folder):
            self.output_folder_path.set(path.join(in_folder, self.batch_folder_name))
        else:
            self.output_folder_path.set("")

    def validate_input_folder(self, event=None, preferred_sample: str | None = None):
        folder_path = self.input_folder_path.get().strip()
        if folder_path == self.previous_input_folder and not preferred_sample:
            return

        if not folder_path or folder_path == "No folder selected":
            self.set_empty_state()
            return

        if path.isdir(folder_path):
            self.image_files = list_supported_images(folder_path)
            if self.image_files:
                self.previous_input_folder = folder_path
                self.set_default_output_folder()
                self.pick_random_image(preferred_sample=preferred_sample)
                self.set_loaded_state()
                self.clear_log()
                self.log_text.insert(
                    "end",
                    f"Loaded input directory: {folder_path}\nFound {len(self.image_files)} supported image(s).\nReady for batch conversion.\n",
                )
            else:
                self.show_centered_messagebox(
                    "Warning",
                    "The selected folder doesn't contain any supported image files.",
                    icon="warning",
                )
                self.set_empty_state()
        else:
            self.show_centered_messagebox(
                "Error",
                "Invalid folder path. Please enter a valid directory.",
                icon="cancel",
            )
            self.set_empty_state()

    def validate_output_folder(self, event=None):
        folder_path = self.output_folder_path.get().strip()
        if folder_path == self.previous_output_folder or not folder_path:
            return

        parent_dir = path.dirname(folder_path)
        if not path.isdir(folder_path) and not path.isdir(parent_dir):
            self.show_centered_messagebox(
                "Error",
                "The parent directory of the output folder does not exist.",
                icon="cancel",
            )
            self.set_default_output_folder()
        else:
            self.previous_output_folder = folder_path

    def validate_dpi(self, P: str) -> bool:
        if P == "":
            return True
        return P.isdigit() and 1 <= int(P) <= 3000

    def on_dpi_focusout(self, event=None):
        current_value = self.image_dpi.get().strip()
        if not current_value.isdigit() or not (1 <= int(current_value) <= 3000):
            self.image_dpi.set(self.initial_dpi)
        else:
            self.initial_dpi = current_value
        self.dpi_entry.update()
        self.update_sample_image_info()

    # ------------------------------------------------------------------
    # Visual States: Empty vs Loaded (Filled)
    # ------------------------------------------------------------------
    def set_empty_state(self):
        self.is_loaded_state = False
        self.image_files = []
        self.sample_image = None
        self.cached_sample_img = None
        self.previous_input_folder = ""
        self.previous_output_folder = ""

        # Paths
        self.input_folder_path.set("")
        self.output_folder_path.set("")

        # Header
        self.sample_filename_label.configure(text="No sample image", text_color=COLOR_MUTED)
        self.status_pill.configure(fg_color=COLOR_SURFACE_2)
        self.status_pill_label.configure(text="• AWAITING FOLDER", text_color=COLOR_MUTED)
        self.resample_button.configure(border_color=COLOR_BORDER, text_color=COLOR_MUTED, state="disabled")

        # Preview Container: Show dropzone, hide image
        self.preview_dims_label.configure(text="no sample loaded")
        self.image_preview.grid_forget()
        self.dropzone_frame.grid(row=0, column=0, sticky="nsew")

        # Metric Cards (reset to '—')
        for title, (card, v_lbl, s_lbl) in self.metric_cards.items():
            v_lbl.configure(text="—", text_color=COLOR_MUTED)
            s_lbl.configure(text="")

        # Action Bar & CTA
        self.status_dot.configure(text_color=COLOR_MUTED)
        fmt = self.selected_image_type.get().replace(".", "").upper()
        q = self.quality.get()
        r = self.resize_percent.get()
        dpi = self.image_dpi.get() or "72"
        self.status_summary_label.configure(
            text=f"Waiting for folder  ·  {fmt} · quality {q} · resize {r}% · {dpi} DPI"
        )
        self.process_button.configure(
            fg_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER,
            hover_color=COLOR_BORDER_2,
            text_color=COLOR_MUTED,
            state="disabled",
        )
        self.clear_log()
        self.log_text.insert(
            "end",
            "Welcome to FXbatch Resizer 2.0.0\n"
            "• Drop a folder anywhere or click Browse to select input folder.\n"
            "• Adjust Quality, Format, Resize %, and DPI on the left.\n"
            "• Real-time sample analysis will display expected file reductions.\n",
        )

    def set_loaded_state(self):
        self.is_loaded_state = True

        # Header Status Pill
        file_count = len(self.image_files)
        self.status_pill.configure(fg_color=COLOR_SUCCESS_BG)
        self.status_pill_label.configure(text=f"• READY ({file_count} FILES)", text_color=COLOR_SUCCESS)
        self.resample_button.configure(border_color=COLOR_BORDER_2, text_color=COLOR_TEXT, state="normal")

        # Preview Container: Show image, hide dropzone
        self.dropzone_frame.grid_forget()
        self.image_preview.grid(row=0, column=0, sticky="nsew")

        # Action Bar & CTA
        self.status_dot.configure(text_color=COLOR_SUCCESS)
        self.process_button.configure(
            fg_color=COLOR_BRAND,
            border_color=COLOR_BRAND,
            hover_color=COLOR_BRAND_HOVER,
            text_color=COLOR_ON_BRAND,
            state="normal",
        )

    def clear_log(self):
        self.log_text.delete("1.0", "end")

    # ------------------------------------------------------------------
    # Sample Image Handling & Real-Time Stats
    # ------------------------------------------------------------------
    def pick_random_image(self, preferred_sample: str | None = None):
        folder = self.input_folder_path.get().strip()
        if not folder or not path.isdir(folder):
            self.set_empty_state()
            return

        if not self.image_files:
            self.image_files = list_supported_images(folder)

        if not self.image_files:
            self.set_empty_state()
            return

        if preferred_sample and path.exists(preferred_sample):
            self.sample_image = preferred_sample
        else:
            self.sample_image = path.join(folder, choice(self.image_files))

        self._load_and_cache_sample(self.sample_image)
        self.update_sample_image_info()

    def _load_and_cache_sample(self, image_path: str):
        from PIL import Image, ImageOps

        try:
            self.sample_orig_size = path.getsize(image_path)
            self.sample_filename_label.configure(text=path.basename(image_path), text_color=COLOR_TEXT)
            with Image.open(image_path) as img:
                dpi = img.info.get("dpi", (72, 72))
                raw_dpi = dpi[0] if isinstance(dpi, tuple) else dpi
                self.sample_dpi_val = float(raw_dpi) if hasattr(raw_dpi, "numerator") else float(raw_dpi)

                transposed = ImageOps.exif_transpose(img)
                self.cached_sample_img = transposed.copy()

                # Scale thumbnail to fill the ~540x300 preview card area nicely
                thumb = transposed.copy()
                thumb.thumbnail((540, 300), Image.LANCZOS)
                ctk_image = ctk.CTkImage(light_image=thumb, dark_image=thumb, size=thumb.size)

            self.image_preview.configure(image=ctk_image, text="")
            self.current_preview = ctk_image
        except Exception as e:
            logger.warning(f"Error loading sample image: {e}")
            self.cached_sample_img = None
            self.image_preview.configure(image=None, text="Error loading sample image preview")

    def update_sample_image_info(self, *args):
        if not self.cached_sample_img or not self.sample_image:
            return

        self._preview_worker_id += 1
        current_id = self._preview_worker_id

        filename = path.basename(self.sample_image)
        orig_w, orig_h = self.cached_sample_img.size
        orig_size = self.sample_orig_size
        sample_dpi = self.sample_dpi_val

        quality = self.quality.get()
        resize_pct = self.resize_percent.get()
        img_type = self.selected_image_type.get().replace(".", "").lower()
        dpi_str = self.image_dpi.get() or "72"
        cached_ref = self.cached_sample_img

        def _compute():
            try:
                new_w, new_h, exact_bytes = encode_sample_in_memory(
                    cached_ref, quality, resize_pct, dpi_str, img_type
                )
                reduction_pct = (1.0 - (exact_bytes / orig_size)) * 100.0 if orig_size > 0 else 0.0

                if current_id == self._preview_worker_id:
                    self.dispatch_ui(
                        self._apply_sample_stats,
                        filename,
                        orig_w,
                        orig_h,
                        orig_size,
                        new_w,
                        new_h,
                        exact_bytes,
                        reduction_pct,
                        sample_dpi,
                        dpi_str,
                        img_type,
                        quality,
                        resize_pct,
                    )
            except Exception as e:
                logger.warning(f"Error computing sample stats: {e}")

        Thread(target=_compute, daemon=True).start()

    def _apply_sample_stats(
        self,
        filename: str,
        orig_w: int,
        orig_h: int,
        orig_size: int,
        new_w: int,
        new_h: int,
        exact_bytes: int,
        reduction_pct: float,
        sample_dpi: float,
        dpi_str: str,
        img_type: str,
        quality: int,
        resize_pct: int,
    ):
        # Header filename & preview dimensions
        self.sample_filename_label.configure(text=filename, text_color=COLOR_TEXT)
        self.preview_dims_label.configure(text=f"{orig_w} × {orig_h}  →  {new_w} × {new_h}")

        # Metric Cards:
        # 1. ORIGINAL
        _, v1, s1 = self.metric_cards["ORIGINAL"]
        v1.configure(text=f"{orig_w} × {orig_h}", text_color=COLOR_TEXT)
        s1.configure(text=format_size(orig_size))

        # 2. OUTPUT
        _, v2, s2 = self.metric_cards["OUTPUT"]
        v2.configure(text=f"{new_w} × {new_h}", text_color=COLOR_TEXT)
        fmt_spec = f"{img_type.upper()} · Lossless" if img_type == "png" else f"{img_type.upper()} · Q{quality}"
        s2.configure(text=fmt_spec)

        # 3. NEW SIZE
        _, v3, s3 = self.metric_cards["NEW SIZE"]
        v3.configure(text=format_size(exact_bytes), text_color=COLOR_TEXT)
        s3.configure(text="est. output")

        # 4. REDUCTION
        _, v4, s4 = self.metric_cards["REDUCTION"]
        red_text = f"{reduction_pct:.1f}%"
        red_color = COLOR_SUCCESS if reduction_pct > 0 else COLOR_TEXT
        v4.configure(text=red_text, text_color=red_color)
        s4.configure(text="vs original")

        # 5. SAMPLE DPI
        _, v5, s5 = self.metric_cards["SAMPLE DPI"]
        v5.configure(text=dpi_str, text_color=COLOR_TEXT)
        s5.configure(text="unchanged" if int(sample_dpi) == int(dpi_str or 72) else "target DPI")

        # Action Bar Status
        self.status_summary_label.configure(
            text=f"Ready to convert  ·  {img_type.upper()} · quality {quality} · resize {resize_pct}% · {dpi_str} DPI"
        )
        self.status_dot.configure(text_color=COLOR_SUCCESS)

        # Legacy compatibility string
        self.sample_image_info.set(
            f"File: {filename}\nOriginal: {orig_w}x{orig_h} ({format_size(orig_size)})\n"
            f"Output: {new_w}x{new_h} ({format_size(exact_bytes)})\nReduction: {reduction_pct:.1f}%"
        )

    # ------------------------------------------------------------------
    # Batch Image Processing Execution
    # ------------------------------------------------------------------
    def process_images(self):
        input_folder = self.input_folder_path.get().strip()
        output_folder = self.output_folder_path.get().strip()

        if not input_folder or not path.isdir(input_folder):
            self.show_centered_messagebox("Error", "Please select a valid input folder.", icon="cancel")
            return

        if not self.image_files:
            self.image_files = list_supported_images(input_folder)

        if not self.image_files:
            self.show_centered_messagebox(
                "Warning",
                "The selected folder contains no supported images to process.",
                icon="warning",
            )
            self.set_empty_state()
            return

        if not output_folder:
            output_folder = path.join(input_folder, self.batch_folder_name)
            self.output_folder_path.set(output_folder)

        # Source overwrite check
        if path.normcase(path.abspath(input_folder)) == path.normcase(path.abspath(output_folder)):
            resp = self.show_centered_messagebox(
                "Overwrite Warning",
                "Output folder is the same as Input folder! Original files may be overwritten. Continue?",
                icon="warning",
                option_1="Cancel",
                option_2="Overwrite",
            )
            if resp != "Overwrite":
                return

        quality = self.quality.get()
        resize_percent = self.resize_percent.get()
        image_type = self.selected_image_type.get().replace(".", "").lower()
        dpi = self.image_dpi.get() or "72"

        self.clear_log()
        self.log_text.insert("end", f"Starting batch conversion of {len(self.image_files)} image(s)...\n")
        self.log_text.see("end")

        self._warmup_start_time = time.monotonic()
        self._warmup_duration = 2.5
        self._warmup_target = 0.10
        self._display_progress = 0.0
        self._real_progress = 0.0
        self.progress_bar.set(0.0)

        # Swap Action Bar status text with live progress frame
        self.summary_frame.grid_remove()
        self.progress_frame.grid(row=0, column=1, columnspan=2, sticky="ew", padx=(10, 20))
        self.process_button.configure(state="disabled")

        self.is_processing = True
        self.cancel_event.clear()

        # Start 2.5s animated warmup ticker to simulate activity while threads spawn
        self._tick_warmup_animation()

        Thread(
            target=self.run_processing,
            args=(input_folder, output_folder, quality, resize_percent, image_type, dpi),
            daemon=True,
        ).start()

    def _tick_warmup_animation(self):
        """Simulates smooth progress activity for 2.5s while worker threads initialize."""
        if not self.is_processing:
            return

        elapsed = time.monotonic() - self._warmup_start_time
        if elapsed < self._warmup_duration:
            # Quadratic ease-out over 2.5s
            ratio = elapsed / self._warmup_duration
            eased = 1.0 - (1.0 - ratio) ** 2
            simulated_val = eased * self._warmup_target

            # Always display at least simulated warmup, or real progress if ahead
            self._display_progress = max(self._display_progress, simulated_val, self._real_progress)
            self.progress_bar.set(self._display_progress)
            self.after(35, self._tick_warmup_animation)
        else:
            # Warmup period finished: smoothly follow real progress without jumping back
            self._display_progress = max(self._display_progress, self._real_progress)
            self.progress_bar.set(self._display_progress)

    def cancel_processing(self):
        self.cancel_event.set()
        self.log_text.insert("end", "\n===============================================================\n")
        self.log_text.insert("end", "  CANCELLING BATCH CONVERSION...\n")
        self.log_text.insert("end", "  Stopping worker processes. Please wait...\n")
        self.log_text.insert("end", "===============================================================\n")
        self.log_text.see("1.0")
        try:
            self.log_text.yview_moveto(0.0)
        except Exception:
            pass

    def _on_worker_progress(self, progress: float, current_idx: int, total_files: int, filename: str, start_time: float):
        self._real_progress = progress
        elapsed_warmup = time.monotonic() - self._warmup_start_time

        if elapsed_warmup >= self._warmup_duration:
            # Past 2.5s warmup: progress bar smoothly follows actual worker completion
            self._display_progress = max(self._display_progress, progress)
            self.progress_bar.set(self._display_progress)
        else:
            # During warmup: advance immediately if actual progress overtakes simulated progress
            if progress > self._display_progress:
                self._display_progress = progress
                self.progress_bar.set(self._display_progress)

        elapsed = max(0.001, time.monotonic() - start_time)
        rate = current_idx / elapsed
        eta = max(0.0, (total_files - current_idx) / rate) if rate > 0 else 0.0

        status_line = (
            f"Processing {current_idx}/{total_files} ({progress * 100:.0f}%) "
            f"• {rate:.1f} img/s • ETA: {eta:.1f}s — {filename}\n"
        )
        self.log_text.delete("1.0", "end")
        self.log_text.insert("end", status_line)

    def run_processing(self, input_folder, output_folder, quality, resize_percent, image_type, dpi):
        start_time = time.monotonic()

        def progress_callback(progress: float, current_idx: int, total_files: int, filename: str = ""):
            self.dispatch_ui(
                self._on_worker_progress,
                progress,
                current_idx,
                total_files,
                filename,
                start_time,
            )

        try:
            results = process_images_in_folder(
                input_folder,
                output_folder,
                quality,
                resize_percent,
                dpi,
                progress_callback,
                self.cancel_event,
                image_type,
            )

            elapsed = time.monotonic() - start_time
            ok_results = [r for r in results if r.status == "ok"]
            err_results = [r for r in results if r.status == "error"]

            input_bytes = sum(r.input_bytes for r in ok_results)
            output_bytes = sum(r.output_bytes for r in ok_results)
            saved_bytes = input_bytes - output_bytes
            saved_pct = (saved_bytes / input_bytes * 100.0) if input_bytes > 0 else 0.0

            if self.cancel_event.is_set():
                summary = (
                    "===============================================================\n"
                    "  [CANCELLED] BATCH CONVERSION CANCELLED BY USER\n"
                    "===============================================================\n"
                    f"  Files completed before cancel: {len(ok_results)}\n"
                    f"  Elapsed time:                  {elapsed:.2f} seconds\n"
                    f"  Output folder:                 {output_folder}\n"
                    "===============================================================\n"
                )
                self.dispatch_ui(self._finish_batch_ui, summary, "Cancelled", "Batch process was cancelled.", "cancel", output_folder, False)
            elif err_results:
                error_lines = "\n".join(f"  - {r.filename}: {r.error}" for r in err_results[:10])
                summary = (
                    "===============================================================\n"
                    f"  [COMPLETED WITH ERRORS] Processed: {len(ok_results)} | Failed: {len(err_results)}\n"
                    "===============================================================\n"
                    f"  Succeeded:             {len(ok_results)} file(s)\n"
                    f"  Failed:                {len(err_results)} file(s)\n"
                    f"  Processing time:       {elapsed:.2f} seconds\n"
                    f"  Total size reduction:  {saved_pct:.1f}% ({format_size(saved_bytes)})\n"
                    f"  Output folder:         {output_folder}\n"
                    f"\nErrors:\n{error_lines}\n"
                    "===============================================================\n"
                )
                self.dispatch_ui(
                    self._finish_batch_ui,
                    summary,
                    "Completed with Errors",
                    f"Processed {len(ok_results)} files, but {len(err_results)} failed.",
                    "warning",
                    output_folder,
                    len(ok_results) > 0,
                )
            else:
                summary = (
                    "===============================================================\n"
                    "  [SUCCESS] BATCH CONVERSION COMPLETED SUCCESSFULLY\n"
                    "===============================================================\n"
                    f"  Total files processed: {len(ok_results)}\n"
                    f"  Processing time:       {elapsed:.2f} seconds\n"
                    f"  Original images size:  {format_size(input_bytes)}\n"
                    f"  Converted images size: {format_size(output_bytes)}\n"
                    f"  Total size reduction:  {saved_pct:.1f}% ({format_size(saved_bytes)})\n"
                    f"  Output folder:         {output_folder}\n"
                    "===============================================================\n"
                )
                self.dispatch_ui(
                    self._finish_batch_ui,
                    summary,
                    "Success",
                    "Batch conversion completed successfully!",
                    "check",
                    output_folder,
                    True,
                )
        except Exception as e:
            logger.error(f"Error during batch processing: {e}", exc_info=True)
            err_msg = (
                "===============================================================\n"
                "  [ERROR] AN ERROR OCCURRED DURING BATCH PROCESSING\n"
                "===============================================================\n"
                f"  Details: {e}\n"
                "===============================================================\n"
            )
            self.dispatch_ui(self._finish_batch_ui, err_msg, "Error", err_msg, "cancel", output_folder, False)

    def _finish_batch_ui(self, log_summary: str, title: str, msg: str, icon: str, output_folder: str, offer_open: bool):
        self.is_processing = False
        self._display_progress = 0.0
        self._real_progress = 0.0

        # Restore Action Bar
        self.progress_frame.grid_remove()
        self.summary_frame.grid(row=0, column=1, sticky="w")
        self.process_button.configure(state="normal")

        self.log_text.delete("1.0", "end")
        self.log_text.insert("end", log_summary)
        self.log_text.see("1.0")
        try:
            self.log_text.yview_moveto(0.0)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Modals, Help & Settings
    # ------------------------------------------------------------------
    def show_help(self):
        help_url = self.config.get("Help", "help_url", fallback="help.html")
        if help_url.startswith(("http://", "https://")):
            webbrowser.open(help_url)
        else:
            help_file_path = path.join(self.get_bundle_dir(), help_url)
            if not path.exists(help_file_path) and getattr(sys, "frozen", False):
                help_file_path = path.join(path.dirname(sys.executable), help_url)
            if help_file_path and path.exists(help_file_path):
                webbrowser.open("file://" + help_file_path)
            else:
                self.show_centered_messagebox("Error", "Help file not found.", icon="cancel")

    def show_settings(self):
        if self.settings_window is None or not self.settings_window.winfo_exists():
            self.settings_window = SettingsWindow(self)
            self.settings_window.after(100, self.settings_window.lift)
            self.settings_window.after(200, self.settings_window.focus_force)
        else:
            self.settings_window.lift()
            self.settings_window.focus_force()

    def show_centered_messagebox(self, title: str, message: str, icon: str = "info", option_1: str = "OK", option_2: str | None = None):
        from CTkMessagebox import CTkMessagebox

        kwargs = dict(
            master=self,
            title=title,
            message=message,
            icon=icon,
            option_1=option_1,
            corner_radius=CORNER_RADIUS,
        )
        if option_2:
            kwargs["option_2"] = option_2

        msg = CTkMessagebox(**kwargs)
        try:
            main_x, main_y = self.winfo_x(), self.winfo_y()
            main_w, main_h = self.winfo_width(), self.winfo_height()
            msg.update_idletasks()
            msg_w, msg_h = msg.winfo_width(), msg.winfo_height()
            x = main_x + (main_w - msg_w) // 2
            y = main_y + (main_h - msg_h) // 2
            msg.geometry(f"+{x}+{y}")
        except Exception:
            pass

        try:
            res = msg.get()
            return res if res is not None else option_1
        except Exception:
            return option_1

    def update_batch_folder_name(self, new_batch_folder_name: str):
        self.batch_folder_name = new_batch_folder_name
        self.set_default_output_folder()


# ---------------------------------------------------------------------------
# SETTINGS WINDOW (Styled with FXbatch v05 tokens & new startup theme option)
# ---------------------------------------------------------------------------
class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, master: ImageCompressorApp):
        super().__init__(master)
        self.master = master
        self.title("Settings — FXbatch")
        self.geometry("450x405")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG)

        self.default_values = {
            "quality": "60",
            "resize": "40",
            "dpi": "72",
            "batch_folder": DEFAULT_BATCH_FOLDER,
            "version": APP_VERSION,
            "theme_mode": "Dark",
        }

        icon_path = master.get_icon_path()
        if icon_path and sys.platform.startswith("win") and icon_path.endswith(".ico"):
            self.after(250, lambda: self.iconbitmap(icon_path))

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.create_widgets()
        self.center_window()

        self.lift()
        self.attributes("-topmost", True)
        self.after_idle(self.attributes, "-topmost", False)
        self.focus_force()

    def create_widgets(self):
        # Card container
        self.card = ctk.CTkFrame(
            self,
            fg_color=COLOR_SURFACE,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            corner_radius=CORNER_RADIUS,
        )
        self.card.pack(padx=5, pady=5, fill="both", expand=True)
        self.card.grid_columnconfigure(0, weight=1)
        self.card.grid_columnconfigure(1, weight=1)

        # Header Title
        title_lbl = ctk.CTkLabel(
            self.card,
            text="SETTINGS",
            font=ctk.CTkFont(family=HEAD_FONT, size=12, weight="bold"),
            text_color=COLOR_TEXT,
            anchor="w",
        )
        title_lbl.grid(row=0, column=0, columnspan=2, padx=18, pady=(16, 8), sticky="w")

        div = ThemeDivider(self.card, height=1)
        div.grid(row=1, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 14))

        # Row 2: FXbatch Version (Matches 2.0.0)
        ctk.CTkLabel(
            self.card,
            text="FXBATCH VERSION:",
            font=ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_TEXT_3,
            anchor="e",
        ).grid(row=2, column=0, padx=(18, 12), pady=6, sticky="e")

        ver_lbl = ctk.CTkLabel(
            self.card,
            text=APP_VERSION,
            font=ctk.CTkFont(family=MONO_FONT, size=11, weight="bold"),
            text_color="#FFFFFF",
            anchor="w",
        )
        ver_lbl.grid(row=2, column=1, padx=(0, 18), pady=6, sticky="w")

        # Row 3: Startup Theme Option (Light / Dark / System)
        ctk.CTkLabel(
            self.card,
            text="STARTUP THEME:",
            font=ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_TEXT_3,
            anchor="e",
        ).grid(row=3, column=0, padx=(18, 12), pady=6, sticky="e")

        self.theme_var = ctk.StringVar(
            value=self.master.config.get("Settings", "theme_mode", fallback="Dark").capitalize()
        )
        theme_menu = ctk.CTkOptionMenu(
            self.card,
            variable=self.theme_var,
            values=["Dark", "Light", "System"],
            height=30,
            width=140,
            corner_radius=CORNER_RADIUS,
            font=ctk.CTkFont(family=MONO_FONT, size=11),
            fg_color=COLOR_SURFACE_2,
            button_color=COLOR_SURFACE_2,
            button_hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT,
            dropdown_fg_color=COLOR_SURFACE,
            dropdown_text_color=COLOR_TEXT,
            dropdown_hover_color=COLOR_SURFACE_2,
        )
        theme_menu.grid(row=3, column=1, padx=(0, 18), pady=6, sticky="w")

        # Row 4: Image Compression (Quality)
        self.quality_var = ctk.StringVar(value=self.get_display_value("quality", 10, 100))
        self.create_setting_row("DEFAULT QUALITY:", self.quality_var, 4, 10, 100, "quality", width=70)

        # Row 5: Image Resize %
        self.resize_var = ctk.StringVar(value=self.get_display_value("resize", 10, 100))
        self.create_setting_row("DEFAULT RESIZE %:", self.resize_var, 5, 10, 100, "resize", width=70)

        # Row 6: Image DPI
        self.dpi_var = ctk.StringVar(value=self.get_display_value("dpi", 72, 3000))
        self.create_setting_row("DEFAULT DPI:", self.dpi_var, 6, 72, 3000, "dpi", width=70)

        # Row 7: Output Folder Name
        self.batch_folder_var = ctk.StringVar(
            value=self.master.config.get("Settings", "batch_folder", fallback=DEFAULT_BATCH_FOLDER)
        )
        ctk.CTkLabel(
            self.card,
            text="SUBFOLDER NAME:",
            font=ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_TEXT_3,
            anchor="e",
        ).grid(row=7, column=0, padx=(18, 12), pady=6, sticky="e")

        folder_entry = ctk.CTkEntry(
            self.card,
            textvariable=self.batch_folder_var,
            width=140,
            height=30,
            corner_radius=CORNER_RADIUS,
            font=ctk.CTkFont(family=MONO_FONT, size=11),
            fg_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            text_color=COLOR_TEXT,
        )
        folder_entry.grid(row=7, column=1, padx=(0, 18), pady=6, sticky="w")

        # Row 8: Action Buttons (Save & Cancel)
        btn_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        btn_frame.grid(row=8, column=0, columnspan=2, pady=(31, 22), padx=18, sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            command=self.destroy,
            height=34,
            corner_radius=CORNER_RADIUS,
            font=ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            fg_color="transparent",
            hover_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER_2,
            border_width=BORDER_WIDTH,
            text_color=COLOR_TEXT_3,
        )
        cancel_btn.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        save_btn = ctk.CTkButton(
            btn_frame,
            text="Save Settings",
            command=self.save_settings,
            height=34,
            corner_radius=CORNER_RADIUS,
            font=ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            fg_color=COLOR_BRAND,
            hover_color=COLOR_BRAND_HOVER,
            text_color=COLOR_ON_BRAND,
        )
        save_btn.grid(row=0, column=1, padx=(6, 0), sticky="ew")

    def create_setting_row(self, label_text: str, variable: ctk.StringVar, row: int, min_val: int, max_val: int, key: str, width: int = 70):
        ctk.CTkLabel(
            self.card,
            text=label_text,
            font=ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_TEXT_3,
            anchor="e",
        ).grid(row=row, column=0, padx=(18, 12), pady=6, sticky="e")

        entry = ctk.CTkEntry(
            self.card,
            textvariable=variable,
            width=width,
            height=30,
            corner_radius=CORNER_RADIUS,
            font=ctk.CTkFont(family=MONO_FONT, size=11),
            fg_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            text_color=COLOR_TEXT,
            validate="key",
            validatecommand=(self.register(self.validate_numeric_input), "%P"),
        )
        entry.grid(row=row, column=1, padx=(0, 18), pady=6, sticky="w")
        entry.bind("<FocusOut>", lambda e, v=variable, mn=min_val, mx=max_val, k=key: self.on_focus_out_validate(v, mn, mx, k))

    def validate_numeric_input(self, P: str) -> bool:
        return P.isdigit() or P == ""

    def get_display_value(self, key: str, min_value: int, max_value: int) -> str:
        value = self.master.config["Settings"].get(key, self.default_values[key])
        return self.validate_input(value, min_value, max_value, key)

    def on_focus_out_validate(self, variable, min_value: int, max_value: int, key: str):
        current = variable.get().strip()
        validated = self.validate_input(current, min_value, max_value, key)
        if current != validated:
            variable.set(validated)

    def validate_input(self, value: str, min_value: int, max_value: int, key: str) -> str:
        if not value.strip():
            return self.default_values[key]
        try:
            clamped = max(min_value, min(int(value), max_value))
            return str(clamped)
        except ValueError:
            return self.default_values[key]

    def save_settings(self):
        self.on_focus_out_validate(self.quality_var, 10, 100, "quality")
        self.on_focus_out_validate(self.resize_var, 10, 100, "resize")
        self.on_focus_out_validate(self.dpi_var, 72, 3000, "dpi")

        theme_mode = self.theme_var.get().strip().capitalize()
        if theme_mode not in ("Dark", "Light", "System"):
            theme_mode = "Dark"

        new_folder = self.batch_folder_var.get().strip() or DEFAULT_BATCH_FOLDER

        # Write to config
        self.master.config["Settings"]["quality"] = self.quality_var.get()
        self.master.config["Settings"]["resize"] = self.resize_var.get()
        self.master.config["Settings"]["dpi"] = self.dpi_var.get()
        self.master.config["Settings"]["version"] = APP_VERSION
        self.master.config["Settings"]["theme_mode"] = theme_mode
        self.master.config["Settings"]["batch_folder"] = new_folder

        try:
            with open(self.master.get_config_path(), "w") as configfile:
                self.master.config.write(configfile)
        except OSError as e:
            logger.warning(f"Could not save config.ini: {e}")

        # Update master runtime variables
        self.master.update_batch_folder_name(new_folder)
        self.master.startup_theme_mode = theme_mode
        self.master.set_theme(theme_mode)

        self.destroy()

    def center_window(self, w: int = 450, h: int = 405):
        self.update_idletasks()
        x = (self.master.winfo_width() // 2) - (w // 2) + self.master.winfo_x()
        y = (self.master.winfo_height() // 2) - (h // 2) + self.master.winfo_y()
        self.geometry(f"{w}x{h}+{x}+{y}")


if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        from multiprocessing import freeze_support
        freeze_support()

    app = ImageCompressorApp()
    app.mainloop()
