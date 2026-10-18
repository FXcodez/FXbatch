# fxbatch_main_gui.py — FXbatch v2.5.0 Main Application & Settings Engine
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
from PIL import Image

from widgets import (
    WidgetCreator,
    ThemeDivider,
    CTkTooltip,
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
    COLOR_WARNING,
    CORNER_RADIUS,
    BORDER_WIDTH,
)
from image_compressor import (
    SUPPORTED_EXTENSIONS,
    OUTPUT_FORMATS,
    list_supported_images,
    format_size,
    compute_target_dimensions,
    encode_sample_in_memory,
    process_images_in_folder,
)

APP_VERSION = "2.5.0"
APP_DISPLAY_VERSION = "2.5.0"
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
        self._start_time = 0.0

        self.previous_input_folder = ""
        self.previous_output_folder = ""
        self.last_completed_output_folder = ""

        # UI Variables
        self.input_folder_path = ctk.StringVar(value="")
        self.output_folder_path = ctk.StringVar(value="")
        self.quality = ctk.IntVar(value=60)
        self.resize_percent = ctk.IntVar(value=40)
        self.bbox_max_w = ctk.StringVar(value="1920")
        self.bbox_max_h = ctk.StringVar(value="1080")
        self.fixed_width = ctk.StringVar(value="1200")
        self.fixed_height = ctk.StringVar(value="800")
        self.ico_size_choice = ctk.StringVar(value="Bundle (16-256 px)")
        self.selected_filter = ctk.StringVar(value="Lanczos (High Quality)")
        self.collision_policy = ctk.StringVar(value="Overwrite")
        self.filename_template = ctk.StringVar(value="{name}")
        self.auto_open_folder = ctk.BooleanVar(value=False)
        self.create_favicon = ctk.BooleanVar(value=False)

        # Progress simulation & smoothing state
        self._warmup_start_time = 0.0
        self._warmup_duration = 2.5
        self._warmup_target = 0.10
        self._display_progress = 0.0
        self._real_progress = 0.0

        self.image_types = list(OUTPUT_FORMATS)
        self.selected_image_type = ctk.StringVar(value="JPG")
        self.selected_resize_mode = ctk.StringVar(value="Percentage (%)")

        self.image_dpi = ctk.StringVar(value="72")
        self.initial_dpi = "72"
        self.batch_folder_name = DEFAULT_BATCH_FOLDER
        self.startup_theme_mode = "Dark"
        self.settings_window: SettingsWindow | None = None

        # Setup OS integration & configuration
        self.set_taskbar_icon()
        self.setup_window()
        self.load_config()
        self._load_theme_icons()

        # Build UI from widgets.py (WidgetCreator)
        self.widget_creator = WidgetCreator(self, ctk)
        self.main_body = self.widget_creator.create_widgets()

        # Apply startup appearance mode
        self.set_theme(self.startup_theme_mode)

        # Set default empty state
        self.set_empty_state()

        # Bind events
        self.bind_events()

        # Thread-safe UI dispatch queue (Python 3.12+ safe)
        self.ui_queue: Queue[tuple] = Queue()
        self._poll_ui_queue()

        # Defer Drag-and-Drop initialization
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
            path.join(base, "icons", "favicon.ico"),
            path.join(base, "icons", "Favicon.png"),
            path.join(base, "Design", "Logos", "favicon.ico"),
            path.join(base, "icons", "fx.ico"),
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
        w, h = 940, 830
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
            self.config["Help"] = {"help_url": "changes/help.html"}
            self.config["Settings"] = {
                "quality": "60",
                "resize": "40",
                "resize_mode": "percent",
                "max_width": "1920",
                "max_height": "1080",
                "fixed_width": "1200",
                "fixed_height": "800",
                "ico_size": "bundle",
                "resample_filter": "lanczos",
                "collision_policy": "overwrite",
                "filename_template": "{name}",
                "auto_open_folder": "false",
                "dpi": "72",
                "batch_folder": DEFAULT_BATCH_FOLDER,
                "version": APP_VERSION,
                "theme_mode": "Dark",
                "create_favicon": "false",
            }
            try:
                with open(config_path, "w") as configfile:
                    self.config.write(configfile)
            except OSError:
                pass

        settings = self.config["Settings"] if "Settings" in self.config else {}
        self.quality.set(int(settings.get("quality", 60)))
        self.resize_percent.set(int(settings.get("resize", 40)))
        self.bbox_max_w.set(settings.get("max_width", "1920"))
        self.bbox_max_h.set(settings.get("max_height", "1080"))
        self.fixed_width.set(settings.get("fixed_width", "1200"))
        self.fixed_height.set(settings.get("fixed_height", "800"))
        self.filename_template.set(settings.get("filename_template", "{name}"))
        self.collision_policy.set(settings.get("collision_policy", "Overwrite").capitalize())
        self.auto_open_folder.set(settings.get("auto_open_folder", "false").lower() in ("true", "1"))
        self.create_favicon.set(settings.get("create_favicon", "false").lower() in ("true", "1"))

        dpi_str = settings.get("dpi", "72")
        self.image_dpi.set(dpi_str)
        self.initial_dpi = dpi_str
        self.batch_folder_name = settings.get("batch_folder", DEFAULT_BATCH_FOLDER)
        self.startup_theme_mode = settings.get("theme_mode", "Dark")

    def _load_theme_icons(self):
        base = self.get_bundle_dir()
        icons_dir = path.join(base, "icons")
        sun_w = path.join(icons_dir, "theme_sun_white.png")
        sun_d = path.join(icons_dir, "theme_sun_dark.png")
        moon_w = path.join(icons_dir, "theme_moon_white.png")
        moon_d = path.join(icons_dir, "theme_moon_dark.png")

        if not (path.exists(sun_w) and path.exists(moon_d)):
            self._generate_theme_icons(icons_dir)

        self.sun_icon = ctk.CTkImage(
            light_image=Image.open(sun_d),
            dark_image=Image.open(sun_w),
            size=(20, 20),
        )
        self.moon_icon = ctk.CTkImage(
            light_image=Image.open(moon_d),
            dark_image=Image.open(moon_w),
            size=(20, 20),
        )

    def _generate_theme_icons(self, icons_dir: str):
        from PIL import ImageDraw, ImageChops
        import math
        os.makedirs(icons_dir, exist_ok=True)
        canvas_size = 128
        target_size = (20, 20)
        c_white = (245, 245, 245, 255)
        c_dark = (35, 35, 35, 255)

        def make_sun(color):
            img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            center = canvas_size / 2
            r_core = canvas_size * 0.23
            ray_start = canvas_size * 0.32
            ray_end = canvas_size * 0.45
            ray_w = int(canvas_size * 0.085)
            r_cap = ray_w / 2
            for i in range(8):
                angle = i * (math.pi / 4)
                cos_a, sin_a = math.cos(angle), math.sin(angle)
                x1, y1 = center + ray_start * cos_a, center + ray_start * sin_a
                x2, y2 = center + ray_end * cos_a, center + ray_end * sin_a
                draw.line([(x1, y1), (x2, y2)], fill=color, width=ray_w)
                draw.ellipse([x2 - r_cap, y2 - r_cap, x2 + r_cap, y2 + r_cap], fill=color)
                draw.ellipse([x1 - r_cap, y1 - r_cap, x1 + r_cap, y1 + r_cap], fill=color)
            draw.ellipse([center - r_core, center - r_core, center + r_core, center + r_core], fill=color)
            return img.resize(target_size, Image.Resampling.LANCZOS)

        def make_moon(color):
            img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
            mask_outer = Image.new("L", (canvas_size, canvas_size), 0)
            d_outer = ImageDraw.Draw(mask_outer)
            r_outer = canvas_size * 0.38
            cx, cy = canvas_size * 0.50, canvas_size * 0.50
            d_outer.ellipse([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer], fill=255)

            mask_inner = Image.new("L", (canvas_size, canvas_size), 0)
            d_inner = ImageDraw.Draw(mask_inner)
            r_inner = canvas_size * 0.35
            offset_dist = canvas_size * 0.20
            cut_angle = -math.radians(40)
            cut_x = cx + offset_dist * math.cos(cut_angle)
            cut_y = cy + offset_dist * math.sin(cut_angle)
            d_inner.ellipse([cut_x - r_inner, cut_y - r_inner, cut_x + r_inner, cut_y + r_inner], fill=255)

            crescent_mask = ImageChops.subtract(mask_outer, mask_inner)
            solid = Image.new("RGBA", (canvas_size, canvas_size), color)
            img.paste(solid, (0, 0), crescent_mask)
            bbox = img.getbbox()
            if bbox:
                cropped = img.crop(bbox)
                w, h = cropped.size
                centered = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
                centered.paste(cropped, ((canvas_size - w) // 2, (canvas_size - h) // 2))
                img = centered
            return img.resize(target_size, Image.Resampling.LANCZOS)

        try:
            make_sun(c_white).save(path.join(icons_dir, "theme_sun_white.png"))
            make_sun(c_dark).save(path.join(icons_dir, "theme_sun_dark.png"))
            make_moon(c_white).save(path.join(icons_dir, "theme_moon_white.png"))
            make_moon(c_dark).save(path.join(icons_dir, "theme_moon_dark.png"))
        except Exception as e:
            logger.warning(f"Could not save generated theme icons: {e}")

    def get_current_theme_icon(self):
        resolved = ctk.get_appearance_mode()
        return self.moon_icon if resolved == "Light" else self.sun_icon

    def toggle_theme(self):
        current = ctk.get_appearance_mode()
        new_mode = "Light" if current == "Dark" else "Dark"
        self.set_theme(new_mode)

    def set_theme(self, mode: str):
        self.current_theme = mode
        ctk.set_appearance_mode(mode)
        self._update_theme_switch_ui()

    def _update_theme_switch_ui(self):
        resolved = ctk.get_appearance_mode()
        if hasattr(self, "theme_toggle_btn"):
            icon = self.moon_icon if resolved == "Light" else self.sun_icon
            self.theme_toggle_btn.configure(image=icon)

    def reset_to_default_settings(self):
        """Reset all UI sidebar controls back to the defaults specified in settings (config.ini)."""
        settings = self.config["Settings"] if "Settings" in self.config else {}

        default_quality = int(settings.get("quality", 60))
        default_resize = int(settings.get("resize", 40))
        default_dpi = settings.get("dpi", "72")
        default_filter_key = settings.get("resample_filter", "lanczos").lower()
        default_mode_key = settings.get("resize_mode", "percent").lower()
        default_max_w = settings.get("max_width", "1920")
        default_max_h = settings.get("max_height", "1080")
        default_fixed_w = settings.get("fixed_width", "1200")
        default_fixed_h = settings.get("fixed_height", "800")
        default_ico = settings.get("ico_size", "bundle").lower()

        # 1. Reset format to .JPG
        self.selected_image_type.set(".JPG")
        self.widget_creator.on_image_type_changed("JPG", trigger_update=False)

        # 2. Reset mode
        mode_map = {
            "percent": "Percentage (%)",
            "bounding_box": "Bounding Box (Max WxH)",
            "fixed_width": "Fixed Width",
            "fixed_height": "Fixed Height",
            "ico": "ICO Resolution",
        }
        target_mode_str = mode_map.get(default_mode_key, "Percentage (%)")
        self.selected_resize_mode.set(target_mode_str)
        self.widget_creator.on_resize_mode_changed(target_mode_str, trigger_update=False)

        # 3. Reset Quality
        self.quality.set(default_quality)
        if hasattr(self.widget_creator, "quality_slider") and self.widget_creator.quality_slider:
            self.widget_creator.quality_slider.set(default_quality)

        # 4. Reset Resize %
        self.resize_percent.set(default_resize)
        if hasattr(self.widget_creator, "resize_slider") and self.widget_creator.resize_slider:
            self.widget_creator.resize_slider.set(default_resize)

        # 5. Reset Dimensions & Sizing parameters
        self.bbox_max_w.set(default_max_w)
        self.bbox_max_h.set(default_max_h)
        self.fixed_width.set(default_fixed_w)
        self.fixed_height.set(default_fixed_h)

        # 6. Reset ICO preset choice
        ico_labels = {
            "bundle": "Bundle (16-256 px)",
            "16": "16 x 16 px",
            "32": "32 x 32 px",
            "48": "48 x 48 px",
            "64": "64 x 64 px",
            "128": "128 x 128 px",
            "256": "256 x 256 px",
        }
        self.ico_size_choice.set(ico_labels.get(default_ico, "Bundle (16-256 px)"))
        self.create_favicon.set(settings.get("create_favicon", "false").lower() in ("true", "1"))

        # 7. Reset DPI
        self.image_dpi.set(default_dpi)

        # 8. Reset Filter
        filter_labels = {
            "lanczos": "Lanczos (High Quality)",
            "bicubic": "Bicubic",
            "bilinear": "Bilinear",
            "nearest": "Nearest (Pixel Art)",
        }
        self.selected_filter.set(filter_labels.get(default_filter_key, "Lanczos (High Quality)"))

        # 9. Refresh sample image analysis
        self.update_sample_image_info()

        # Brief notification in activity log
        self.log_text.insert("end", "[INFO] Settings reset to default values.\n")
        self.log_text.see("end")

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
                    f"Loaded input directory: {folder_path}\n"
                    f"Found {len(self.image_files)} supported image(s).\n"
                    f"Ready for batch conversion.\n",
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

        self.input_folder_path.set("")
        self.output_folder_path.set("")

        self.sample_filename_label.configure(text="No sample image", text_color=COLOR_MUTED)
        self.status_pill.configure(fg_color=COLOR_SURFACE_2)
        self.status_pill_label.configure(text="• AWAITING FOLDER", text_color=COLOR_MUTED)
        self.aspect_warning_pill.pack_forget()
        self.resample_button.configure(border_color=COLOR_BORDER, text_color=COLOR_MUTED, state="disabled")

        self.image_preview.grid_forget()
        self.dropzone_frame.grid(row=0, column=0, sticky="nsew")

        for title, (card, v_lbl, s_lbl) in self.metric_cards.items():
            v_lbl.configure(text="—", text_color=COLOR_MUTED)
            s_lbl.configure(text="")

        self.status_dot.configure(text_color=COLOR_MUTED)
        self.open_folder_btn.pack_forget()
        self.status_summary_label.pack(side="left")
        self.status_summary_label.configure(
            text="Waiting for folder  ·  JPG · quality 60 · resize 40% · 72 DPI"
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
            f"Welcome to FXbatch Resizer {APP_VERSION}\n"
            "• Drop a folder anywhere or click Browse to select input folder.\n"
            "• Select Output Format (.JPG, .PNG, .WEBP, .AVIF, .ICO).\n"
            "• Choose Resize Mode: Percentage, Bounding Box, Width, Height, or ICO.\n"
            "• Real-time sample analysis will display expected dimensions and savings.\n",
        )

    def set_loaded_state(self):
        self.is_loaded_state = True
        self.open_folder_btn.pack_forget()
        file_count = len(self.image_files)
        self.status_pill.configure(fg_color=COLOR_SUCCESS_BG)
        self.status_pill_label.configure(text=f"• READY ({file_count} FILES)", text_color=COLOR_SUCCESS)
        self.resample_button.configure(border_color=COLOR_BORDER_2, text_color=COLOR_TEXT, state="normal")

        self.dropzone_frame.grid_forget()
        self.image_preview.grid(row=0, column=0, sticky="nsew")

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

    def copy_log_to_clipboard(self):
        content = self.log_text.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(content)

    def open_output_folder(self):
        folder = self.last_completed_output_folder or self.output_folder_path.get().strip()
        if folder and path.isdir(folder):
            if sys.platform.startswith("win"):
                os.startfile(folder)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", folder])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", folder])

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

                thumb = transposed.copy()
                thumb.thumbnail((540, 300), Image.LANCZOS)
                ctk_image = ctk.CTkImage(light_image=thumb, dark_image=thumb, size=thumb.size)

            self.image_preview.configure(image=ctk_image, text="")
            self.current_preview = ctk_image
        except Exception as e:
            logger.warning(f"Error loading sample image: {e}")
            self.cached_sample_img = None
            self.image_preview.configure(image=None, text="Error loading sample image preview")

    def get_current_resize_mode_key(self) -> str:
        mode_str = self.selected_resize_mode.get().lower()
        if "bound" in mode_str:
            return "bounding_box"
        elif "width" in mode_str:
            return "fixed_width"
        elif "height" in mode_str:
            return "fixed_height"
        elif "ico" in mode_str:
            return "ico"
        return "percent"

    def get_current_resize_params(self) -> dict:
        ico_raw = self.ico_size_choice.get().split()[0].lower()
        return {
            "percent": self.resize_percent.get(),
            "max_width": int(self.bbox_max_w.get().strip() or "1920"),
            "max_height": int(self.bbox_max_h.get().strip() or "1080"),
            "fixed_width": int(self.fixed_width.get().strip() or "1200"),
            "fixed_height": int(self.fixed_height.get().strip() or "800"),
            "ico_size": "bundle" if "bundle" in ico_raw else ico_raw,
            "create_favicon": self.create_favicon.get(),
        }

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
        img_type = self.selected_image_type.get().replace(".", "").lower()
        resize_mode = self.get_current_resize_mode_key()
        resize_params = self.get_current_resize_params()
        dpi_str = self.image_dpi.get() or "72"
        filter_name = self.selected_filter.get().split()[0].lower()
        cached_ref = self.cached_sample_img

        def _compute():
            try:
                new_w, new_h, exact_bytes, is_square = encode_sample_in_memory(
                    cached_ref, quality, resize_mode, resize_params, dpi_str, img_type, filter_name
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
                        resize_mode,
                        is_square,
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
        resize_mode: str,
        is_square: bool,
    ):
        self.sample_filename_label.configure(text=filename, text_color=COLOR_TEXT)

        # Non-square ICO warning badge check
        if img_type == "ico" and not is_square:
            self.aspect_warning_pill.pack(side="left", padx=(0, 8))
        else:
            self.aspect_warning_pill.pack_forget()

        # 1. ORIGINAL
        _, v1, s1 = self.metric_cards["ORIGINAL"]
        v1.configure(text=f"{orig_w} × {orig_h}", text_color=COLOR_TEXT)
        s1.configure(text=format_size(orig_size))

        # 2. OUTPUT
        _, v2, s2 = self.metric_cards["OUTPUT"]
        v2.configure(text=f"{new_w} × {new_h}", text_color=COLOR_TEXT)
        if img_type == "png":
            fmt_spec = "PNG · Lossless"
        elif img_type == "ico":
            ico_spec = self.ico_size_choice.get().split()[0]
            if self.create_favicon.get():
                fmt_spec = f"ICO · {ico_spec} + Favicon"
            else:
                fmt_spec = f"ICO · {ico_spec}"
        else:
            fmt_spec = f"{img_type.upper()} · Q{quality}"
        s2.configure(text=fmt_spec)

        # 3. NEW SIZE
        _, v3, s3 = self.metric_cards["NEW SIZE"]
        v3.configure(text=format_size(exact_bytes), text_color=COLOR_TEXT)
        s3.configure(text="est. output")

        # 4. REDUCTION
        _, v4, s4 = self.metric_cards["REDUCTION"]
        if reduction_pct >= 0:
            red_text = f"{reduction_pct:.1f}%"
            red_color = COLOR_SUCCESS if reduction_pct > 0 else COLOR_TEXT
            sub_lbl = "vs original"
        else:
            red_text = f"+{abs(reduction_pct):.1f}%"
            red_color = COLOR_WARNING
            sub_lbl = "upscaled"
        v4.configure(text=red_text, text_color=red_color)
        s4.configure(text=sub_lbl)

        # 5. SAMPLE DPI
        _, v5, s5 = self.metric_cards["SAMPLE DPI"]
        v5.configure(text=dpi_str, text_color=COLOR_TEXT)
        s5.configure(text="unchanged" if int(sample_dpi) == int(dpi_str or 72) else "target DPI")

        # Action Bar Status
        self.status_summary_label.configure(
            text=f"Ready to convert  ·  {img_type.upper()} · {fmt_spec} · {dpi_str} DPI"
        )
        self.status_dot.configure(text_color=COLOR_SUCCESS)

    # ------------------------------------------------------------------
    # Batch Processing Execution
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

        # STRICT SAME-FOLDER BLOCK (Protect source files and eliminate WinError 32)
        if path.normcase(path.abspath(input_folder)) == path.normcase(path.abspath(output_folder)):
            self.show_centered_messagebox(
                "Same Folder Not Allowed",
                "The Output folder cannot be the same as the Input folder.\n\n"
                "To protect your original source images from being overwritten, "
                "please choose a different destination folder or use the default subfolder.",
                icon="cancel",
            )
            return

        quality = self.quality.get()
        image_type = self.selected_image_type.get().replace(".", "").lower()
        dpi = self.image_dpi.get() or "72"
        resize_mode = self.get_current_resize_mode_key()
        resize_params = self.get_current_resize_params()
        filter_name = self.selected_filter.get().split()[0].lower()
        policy = self.collision_policy.get().lower()
        template = self.filename_template.get().strip() or "{name}"

        self.clear_log()
        self.log_text.insert("end", f"Starting batch conversion of {len(self.image_files)} image(s)...\n")
        self.log_text.see("end")

        self.open_folder_btn.pack_forget()
        self.status_summary_label.pack(side="left")

        self.summary_frame.grid_remove()
        self.progress_frame.grid(row=0, column=0, sticky="ew")

        # Warmup progress bar simulation for 2.5s
        self._warmup_start_time = time.monotonic()
        self._warmup_duration = 2.5
        self._warmup_target = 0.10
        self._display_progress = 0.0
        self._real_progress = 0.0
        self.progress_bar.set(0.0)

        self.cancel_button.configure(state="normal", text="Cancel")
        self.process_button.configure(state="disabled")

        self.is_processing = True
        self.cancel_event.clear()
        self._start_time = time.monotonic()

        # Start 2.5s animated warmup ticker to simulate activity while threads spawn
        self._tick_warmup_animation()

        Thread(
            target=self.run_processing,
            args=(
                input_folder,
                output_folder,
                quality,
                resize_mode,
                resize_params,
                dpi,
                image_type,
                filter_name,
                policy,
                template,
            ),
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
        self.cancel_button.configure(state="disabled", text="Cancelling...")
        self.log_text.delete("1.0", "end")
        self.log_text.insert("end", "[CANCEL] Halting worker processes. Please wait...\n")
        self.log_text.see("end")

    def _on_worker_progress(self, progress: float, current_idx: int, total_files: int, filename: str, status: str = "ok"):
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

        elapsed = max(0.001, time.monotonic() - self._start_time)
        rate = current_idx / elapsed
        eta = max(0.0, (total_files - current_idx) / rate) if rate > 0 else 0.0

        # Show progress in a single continuously updated line in activity log
        status_line = (
            f"Converting {current_idx}/{total_files} ({progress * 100:.0f}%) "
            f"• {rate:.1f} img/s • ETA: {eta:.1f}s — {filename}\n"
        )
        self.log_text.delete("1.0", "end")
        self.log_text.insert("end", status_line)

        # Telemetry in Action Bar
        self.status_summary_label.configure(
            text=f"Converting {current_idx}/{total_files} ({progress * 100:.0f}%) · {rate:.1f} img/s · ETA: {eta:.1f}s"
        )

    def run_processing(
        self,
        input_folder: str,
        output_folder: str,
        quality: int,
        resize_mode: str,
        resize_params: dict,
        dpi: str,
        image_type: str,
        filter_name: str,
        policy: str,
        template: str,
    ):
        start_time = time.monotonic()

        def progress_callback(progress: float, current_idx: int, total_files: int, filename: str = "", status: str = "ok"):
            self.dispatch_ui(
                self._on_worker_progress,
                progress,
                current_idx,
                total_files,
                filename,
                status,
            )

        try:
            results = process_images_in_folder(
                input_folder,
                output_folder,
                quality,
                resize_mode,
                resize_params,
                dpi,
                progress_callback,
                self.cancel_event,
                image_type,
                filter_name,
                policy,
                template,
            )

            elapsed = time.monotonic() - start_time
            ok_results = [r for r in results if r.status == "ok"]
            skipped_results = [r for r in results if r.status == "skipped"]
            err_results = [r for r in results if r.status == "error"]

            input_bytes = sum(r.input_bytes for r in ok_results)
            output_bytes = sum(r.output_bytes for r in ok_results)
            saved_bytes = input_bytes - output_bytes
            saved_pct = (saved_bytes / input_bytes * 100.0) if input_bytes > 0 else 0.0

            if self.cancel_event.is_set():
                summary = (
                    "\n===============================================================\n"
                    "  [CANCELLED] BATCH CONVERSION STOPPED BY USER\n"
                    "===============================================================\n"
                    f"  Files completed before cancel: {len(ok_results)}\n"
                    f"  Elapsed time:                  {elapsed:.2f} seconds\n"
                    f"  Output folder:                 {output_folder}\n"
                    "===============================================================\n"
                )
                self.dispatch_ui(self._finish_batch_ui, summary, output_folder, False)
            elif err_results:
                error_lines = "\n".join(f"  - {r.filename}: {r.error}" for r in err_results[:10])
                summary = (
                    "\n===============================================================\n"
                    f"  [COMPLETED WITH ERRORS] OK: {len(ok_results)} | Skipped: {len(skipped_results)} | Failed: {len(err_results)}\n"
                    "===============================================================\n"
                    f"  Succeeded:             {len(ok_results)} file(s)\n"
                    f"  Failed:                {len(err_results)} file(s)\n"
                    f"  Skipped:               {len(skipped_results)} file(s)\n"
                    f"  Processing time:       {elapsed:.2f} seconds\n"
                    f"  Total size reduction:  {saved_pct:.1f}% ({format_size(saved_bytes)})\n"
                    f"  Output folder:         {output_folder}\n"
                    f"\nErrors:\n{error_lines}\n"
                    "===============================================================\n"
                )
                self.dispatch_ui(self._finish_batch_ui, summary, output_folder, len(ok_results) > 0)
            else:
                summary = (
                    "\n===============================================================\n"
                    "  [SUCCESS] BATCH CONVERSION COMPLETED SUCCESSFULLY\n"
                    "===============================================================\n"
                    f"  Total files converted: {len(ok_results)}\n"
                    f"  Skipped files:         {len(skipped_results)}\n"
                    f"  Processing time:       {elapsed:.2f} seconds\n"
                    f"  Original size:         {format_size(input_bytes)}\n"
                    f"  Converted size:        {format_size(output_bytes)}\n"
                    f"  Total size reduction:  {saved_pct:.1f}% ({format_size(saved_bytes)})\n"
                    f"  Output folder:         {output_folder}\n"
                    "===============================================================\n"
                )
                self.dispatch_ui(self._finish_batch_ui, summary, output_folder, True)
        except Exception as e:
            logger.error(f"Error during batch processing: {e}", exc_info=True)
            err_msg = (
                "\n===============================================================\n"
                "  [ERROR] AN ERROR OCCURRED DURING BATCH PROCESSING\n"
                "===============================================================\n"
                f"  Details: {e}\n"
                "===============================================================\n"
            )
            self.dispatch_ui(self._finish_batch_ui, err_msg, output_folder, False)

    def _finish_batch_ui(self, log_summary: str, output_folder: str, success: bool):
        self.is_processing = False
        self._display_progress = 0.0
        self._real_progress = 0.0
        self.last_completed_output_folder = output_folder

        self.progress_frame.grid_remove()
        self.summary_frame.grid(row=0, column=0, sticky="w")
        self.process_button.configure(state="normal")

        # Replace log content with clean final report and scroll to the top
        self.log_text.delete("1.0", "end")
        self.log_text.insert("end", log_summary.strip() + "\n")
        self.log_text.see("1.0")
        try:
            self.log_text.yview_moveto(0.0)
        except Exception:
            pass

        # Show 'Open Output Folder' CTA button in summary area
        self.status_summary_label.configure(text=f"Batch complete · Saved to: {path.basename(output_folder)}")
        self.open_folder_btn.pack(side="left", padx=(10, 0))

        # Auto open folder if enabled in settings
        if success and self.auto_open_folder.get():
            self.open_output_folder()

    # ------------------------------------------------------------------
    # Modals, Help & Settings
    # ------------------------------------------------------------------
    def show_help(self):
        help_url = self.config.get("Help", "help_url", fallback="changes/help.html")
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
# SETTINGS WINDOW (v2.5.0 with Collision Policy, Naming Tokens & Light Theme Fix)
# ---------------------------------------------------------------------------
class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, master: ImageCompressorApp):
        super().__init__(master)
        self.master = master
        self.title("Settings — FXbatch 2.5.0")
        self.geometry("480x475")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG)

        self.default_values = {
            "quality": "60",
            "resize": "40",
            "dpi": "72",
            "batch_folder": DEFAULT_BATCH_FOLDER,
            "version": APP_VERSION,
            "theme_mode": "Dark",
            "collision_policy": "Overwrite",
            "filename_template": "{name}",
            "auto_open_folder": "false",
            "create_favicon": "false",
        }

        icon_path = master.get_icon_path()
        if icon_path and sys.platform.startswith("win") and icon_path.endswith(".ico"):
            self.after(250, lambda: self.iconbitmap(icon_path))

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Unmap>", lambda e: CTkTooltip.hide_active())
        self.bind("<FocusOut>", lambda e: CTkTooltip.hide_active())
        self.create_widgets()
        self.center_window(480, 475)

        self.lift()
        self.attributes("-topmost", True)
        self.after_idle(self.attributes, "-topmost", False)
        self.focus_force()

    def destroy(self):
        CTkTooltip.hide_active()
        super().destroy()

    def create_widgets(self):
        self.card = ctk.CTkFrame(
            self,
            fg_color=COLOR_SURFACE,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            corner_radius=CORNER_RADIUS,
        )
        self.card.pack(padx=6, pady=6, fill="both", expand=True)
        self.card.grid_columnconfigure(0, weight=1)
        self.card.grid_columnconfigure(1, weight=1)

        title_lbl = ctk.CTkLabel(
            self.card,
            text="SETTINGS",
            font=ctk.CTkFont(family=HEAD_FONT, size=12, weight="bold"),
            text_color=COLOR_TEXT,
            anchor="w",
        )
        title_lbl.grid(row=0, column=0, columnspan=2, padx=18, pady=(10, 4), sticky="w")

        div = ThemeDivider(self.card, height=1)
        div.grid(row=1, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 6))

        # Row 2: FXbatch Version (Light-theme adaptive COLOR_TEXT fix!)
        ctk.CTkLabel(
            self.card,
            text="FXBATCH VERSION:",
            font=ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_TEXT_3,
            anchor="e",
        ).grid(row=2, column=0, padx=(18, 22), pady=2, sticky="e")

        ver_lbl = ctk.CTkLabel(
            self.card,
            text=APP_VERSION,
            font=ctk.CTkFont(family=MONO_FONT, size=11, weight="bold"),
            text_color=COLOR_TEXT,
            anchor="w",
        )
        ver_lbl.grid(row=2, column=1, padx=(0, 18), pady=2, sticky="w")

        # Row 3: Startup Theme
        theme_lbl = ctk.CTkLabel(
            self.card,
            text="STARTUP THEME:",
            font=ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_TEXT_3,
            anchor="e",
        )
        theme_lbl.grid(row=3, column=0, padx=(18, 22), pady=2, sticky="e")

        self.theme_var = ctk.StringVar(
            value=self.master.config.get("Settings", "theme_mode", fallback="Dark").capitalize()
        )
        theme_menu = ctk.CTkOptionMenu(
            self.card,
            variable=self.theme_var,
            values=["Dark", "Light", "System"],
            height=28,
            width=150,
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
        theme_menu.grid(row=3, column=1, padx=(0, 18), pady=2, sticky="w")
        theme_tip = (
            "Default UI theme applied when FXbatch opens:\n"
            "• Dark: Modern dark theme (Default)\n"
            "• Light: Clean bright theme\n"
            "• System: Follows your Windows appearance setting"
        )
        CTkTooltip(theme_lbl, theme_tip)
        CTkTooltip(theme_menu, theme_tip)

        # Row 4: Collision Policy (Overwrite as default!)
        collision_lbl = ctk.CTkLabel(
            self.card,
            text="COLLISION POLICY:",
            font=ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_TEXT_3,
            anchor="e",
        )
        collision_lbl.grid(row=4, column=0, padx=(18, 22), pady=2, sticky="e")

        self.collision_var = ctk.StringVar(
            value=self.master.collision_policy.get().capitalize()
        )
        collision_menu = ctk.CTkOptionMenu(
            self.card,
            variable=self.collision_var,
            values=["Overwrite", "Auto-Rename", "Skip Existing"],
            height=28,
            width=150,
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
        collision_menu.grid(row=4, column=1, padx=(0, 18), pady=2, sticky="w")
        collision_tip = (
            "Action taken if an output file already exists in destination:\n"
            "• Overwrite: Replaces the existing file (Default)\n"
            "• Auto-Rename: Appends an index number (e.g. photo_1.jpg)\n"
            "• Skip Existing: Preserves the original file and skips processing"
        )
        CTkTooltip(collision_lbl, collision_tip)
        CTkTooltip(collision_menu, collision_tip)

        # Row 5: Naming Template Tokens
        template_lbl = ctk.CTkLabel(
            self.card,
            text="NAMING TEMPLATE:",
            font=ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_TEXT_3,
            anchor="e",
        )
        template_lbl.grid(row=5, column=0, padx=(18, 22), pady=2, sticky="e")

        self.template_var = ctk.StringVar(value=self.master.filename_template.get())
        template_entry = ctk.CTkEntry(
            self.card,
            textvariable=self.template_var,
            width=150,
            height=28,
            corner_radius=CORNER_RADIUS,
            font=ctk.CTkFont(family=MONO_FONT, size=11),
            fg_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            text_color=COLOR_TEXT,
        )
        template_entry.grid(row=5, column=1, padx=(0, 18), pady=2, sticky="w")
        template_tip = (
            "Filename pattern for exported files using variable tokens:\n"
            "• {name}: Original filename without extension (Required)\n"
            "• {w}: Converted width in pixels\n"
            "• {h}: Converted height in pixels\n"
            "• {orig_w}: Original source width in pixels\n"
            "• {orig_h}: Original source height in pixels\n"
            "• {quality}: Compression quality value (10 to 100)\n\n"
            "Common patterns:\n"
            "• {name}_{w}x{h}    (e.g., photo_1920x1080.jpg)\n"
            "• {name}_lowres     (e.g., photo_lowres.jpg)\n"
            "• {name}_thumb      (e.g., photo_thumb.jpg)\n"
            "• {name}_q{quality} (e.g., photo_q60.jpg)"
        )
        CTkTooltip(template_lbl, template_tip)
        CTkTooltip(template_entry, template_tip)

        # Row 6: Auto Open Output Folder Checkbox
        auto_open_lbl = ctk.CTkLabel(
            self.card,
            text="OPEN DESTINATION:",
            font=ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_TEXT_3,
            anchor="e",
        )
        auto_open_lbl.grid(row=6, column=0, padx=(18, 22), pady=2, sticky="e")

        self.auto_open_var = ctk.BooleanVar(value=self.master.auto_open_folder.get())
        auto_open_chk = ctk.CTkCheckBox(
            self.card,
            text="Open folder when finished",
            variable=self.auto_open_var,
            font=ctk.CTkFont(family=BODY_FONT, size=11),
            text_color=COLOR_TEXT,
            corner_radius=CORNER_RADIUS,
            fg_color=COLOR_BRAND,
            hover_color=COLOR_BRAND_HOVER,
        )
        auto_open_chk.grid(row=6, column=1, padx=(0, 18), pady=2, sticky="w")
        auto_open_tip = (
            "When checked, File Explorer opens the destination folder\n"
            "automatically as soon as batch processing finishes.\n"
            "Default: Off (button appears in status bar after completion)."
        )
        CTkTooltip(auto_open_lbl, auto_open_tip)
        CTkTooltip(auto_open_chk, auto_open_tip)

        # Row 7: Default Quality
        self.quality_var = ctk.StringVar(value=self.get_display_value("quality", 10, 100))
        q_lbl, q_entry = self.create_setting_row("DEFAULT QUALITY:", self.quality_var, 7, 10, 100, "quality", width=64)
        q_tip = (
            "Default compression quality for JPEG, WebP, and AVIF (10 to 100).\n"
            "Default: 60 (balanced file size and image fidelity).\n"
            "Higher values increase sharpness but produce larger files."
        )
        CTkTooltip(q_lbl, q_tip)
        CTkTooltip(q_entry, q_tip)

        # Row 8: Default Resize %
        self.resize_var = ctk.StringVar(value=self.get_display_value("resize", 5, 200))
        r_lbl, r_entry = self.create_setting_row("DEFAULT RESIZE %:", self.resize_var, 8, 5, 200, "resize", width=64)
        r_tip = (
            "Default scaling percentage applied to images (5% to 200%).\n"
            "Default: 40%.\n"
            "Values under 100% reduce size; values over 100% upscale images."
        )
        CTkTooltip(r_lbl, r_tip)
        CTkTooltip(r_entry, r_tip)

        # Row 9: Default DPI (1-3000)
        self.dpi_var = ctk.StringVar(value=self.get_display_value("dpi", 1, 3000))
        d_lbl, d_entry = self.create_setting_row("DEFAULT DPI:", self.dpi_var, 9, 1, 3000, "dpi", width=64)
        d_tip = (
            "Default print resolution metadata in dots per inch (1 to 3000).\n"
            "Default: 72 DPI (standard for digital screens and web use).\n"
            "Set to 300 DPI for high-resolution print workflows."
        )
        CTkTooltip(d_lbl, d_tip)
        CTkTooltip(d_entry, d_tip)

        # Row 10: Subfolder Name
        self.batch_folder_var = ctk.StringVar(
            value=self.master.config.get("Settings", "batch_folder", fallback=DEFAULT_BATCH_FOLDER)
        )
        folder_lbl = ctk.CTkLabel(
            self.card,
            text="SUBFOLDER NAME:",
            font=ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_TEXT_3,
            anchor="e",
        )
        folder_lbl.grid(row=10, column=0, padx=(18, 22), pady=2, sticky="e")

        folder_entry = ctk.CTkEntry(
            self.card,
            textvariable=self.batch_folder_var,
            width=150,
            height=28,
            corner_radius=CORNER_RADIUS,
            font=ctk.CTkFont(family=MONO_FONT, size=11),
            fg_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            text_color=COLOR_TEXT,
        )
        folder_entry.grid(row=10, column=1, padx=(0, 18), pady=2, sticky="w")
        folder_tip = (
            "Name of the subfolder automatically created inside the source directory\n"
            "when 'LowRes Subfolder' output destination mode is active.\n"
            "Default: 'LowRes'."
        )
        CTkTooltip(folder_lbl, folder_tip)
        CTkTooltip(folder_entry, folder_tip)

        # Row 11: Create Favicon Package Checkbox
        fav_lbl = ctk.CTkLabel(
            self.card,
            text="FAVICON PACKAGE:",
            font=ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_TEXT_3,
            anchor="e",
        )
        fav_lbl.grid(row=11, column=0, padx=(18, 22), pady=2, sticky="e")

        self.favicon_var = ctk.BooleanVar(value=self.master.create_favicon.get())
        favicon_chk = ctk.CTkCheckBox(
            self.card,
            text="Generate favicon bundle for icons",
            variable=self.favicon_var,
            font=ctk.CTkFont(family=BODY_FONT, size=11),
            text_color=COLOR_TEXT,
            corner_radius=CORNER_RADIUS,
            fg_color=COLOR_BRAND,
            hover_color=COLOR_BRAND_HOVER,
        )
        favicon_chk.grid(row=11, column=1, padx=(0, 18), pady=2, sticky="w")
        fav_tip = (
            "When checked, icon exports automatically generate a complete web favicon bundle:\n"
            "favicon.ico (16/32/48 multi-size), favicon-16x16.png, favicon-32x32.png, apple-touch-icon.png.\n"
            "Default: Off."
        )
        CTkTooltip(fav_lbl, fav_tip)
        CTkTooltip(favicon_chk, fav_tip)

        # Row 12: Action Buttons (Increased font size by 1 pt: 11 -> 12, 20px top padding)
        btn_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        btn_frame.grid(row=12, column=0, columnspan=2, pady=(20, 10), padx=18, sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            command=self.destroy,
            height=32,
            corner_radius=CORNER_RADIUS,
            font=ctk.CTkFont(family=HEAD_FONT, size=12, weight="bold"),
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
            height=32,
            corner_radius=CORNER_RADIUS,
            font=ctk.CTkFont(family=HEAD_FONT, size=12, weight="bold"),
            fg_color=COLOR_BRAND,
            hover_color=COLOR_BRAND_HOVER,
            text_color=COLOR_ON_BRAND,
        )
        save_btn.grid(row=0, column=1, padx=(6, 0), sticky="ew")

    def create_setting_row(self, label_text: str, variable: ctk.StringVar, row: int, min_val: int, max_val: int, key: str, width: int = 64):
        lbl = ctk.CTkLabel(
            self.card,
            text=label_text,
            font=ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_TEXT_3,
            anchor="e",
        )
        lbl.grid(row=row, column=0, padx=(18, 22), pady=2, sticky="e")

        entry = ctk.CTkEntry(
            self.card,
            textvariable=variable,
            width=width,
            height=28,
            corner_radius=CORNER_RADIUS,
            font=ctk.CTkFont(family=MONO_FONT, size=11),
            fg_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            text_color=COLOR_TEXT,
            justify="center",
        )
        entry.grid(row=row, column=1, padx=(0, 18), pady=2, sticky="w")
        entry.bind("<FocusOut>", lambda e, v=variable, mn=min_val, mx=max_val, k=key: self.on_focus_out_validate(v, mn, mx, k))
        return lbl, entry

    def get_display_value(self, key: str, min_value: int, max_value: int) -> str:
        value = self.master.config["Settings"].get(key, self.default_values[key]) if "Settings" in self.master.config else self.default_values[key]
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
        self.on_focus_out_validate(self.resize_var, 5, 200, "resize")
        self.on_focus_out_validate(self.dpi_var, 1, 3000, "dpi")

        theme_mode = self.theme_var.get().strip().capitalize()
        if theme_mode not in ("Dark", "Light", "System"):
            theme_mode = "Dark"

        new_folder = self.batch_folder_var.get().strip() or DEFAULT_BATCH_FOLDER
        policy = self.collision_var.get().strip().capitalize()
        template = self.template_var.get().strip() or "{name}"
        auto_open = self.auto_open_var.get()
        create_fav = self.favicon_var.get()

        if "Settings" not in self.master.config:
            self.master.config["Settings"] = {}

        self.master.config["Settings"]["quality"] = self.quality_var.get()
        self.master.config["Settings"]["resize"] = self.resize_var.get()
        self.master.config["Settings"]["dpi"] = self.dpi_var.get()
        self.master.config["Settings"]["version"] = APP_VERSION
        self.master.config["Settings"]["theme_mode"] = theme_mode
        self.master.config["Settings"]["batch_folder"] = new_folder
        self.master.config["Settings"]["collision_policy"] = policy
        self.master.config["Settings"]["filename_template"] = template
        self.master.config["Settings"]["auto_open_folder"] = str(auto_open).lower()
        self.master.config["Settings"]["create_favicon"] = str(create_fav).lower()

        try:
            with open(self.master.get_config_path(), "w") as configfile:
                self.master.config.write(configfile)
        except OSError as e:
            logger.warning(f"Could not save config.ini: {e}")

        # Update master runtime state
        self.master.update_batch_folder_name(new_folder)
        self.master.startup_theme_mode = theme_mode
        self.master.collision_policy.set(policy)
        self.master.filename_template.set(template)
        self.master.auto_open_folder.set(auto_open)
        self.master.create_favicon.set(create_fav)
        self.master.set_theme(theme_mode)

        self.destroy()

    def center_window(self, w: int = 480, h: int = 475):
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
