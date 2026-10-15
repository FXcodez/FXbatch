"""
ui_preview.py — FXbatch v05 Standalone Visual Prototype
Exact pixel-perfect CustomTkinter mockup based on FXbatch_Conversion.pen and v05/Design screenshots.

Preserves 100% backend contract and variable names matching fxbatch_main_gui.py,
widgets.py, and image_compressor.py.
"""
from __future__ import annotations

import ctypes
import os
from os import path
import sys
import tkinter as tk
from threading import Event
from PIL import Image, ImageOps
import customtkinter as ctk

# ---------------------------------------------------------------------------
# LOAD DESIGN FONTS (Oswald, Roboto, Roboto Mono)
# ---------------------------------------------------------------------------
BASE_DIR = path.dirname(path.abspath(__file__))
FONTS_DIR = path.join(BASE_DIR, "fonts")

def _register_gdi_fonts():
    """Register project TTF fonts with Windows GDI so Tkinter can use them."""
    if sys.platform.startswith("win") and path.isdir(FONTS_DIR):
        FR_PRIVATE = 0x10
        for f in os.listdir(FONTS_DIR):
            if f.lower().endswith((".ttf", ".otf")):
                font_path = path.abspath(path.join(FONTS_DIR, f))
                ctypes.windll.gdi32.AddFontResourceExW(font_path, FR_PRIVATE, 0)

_register_gdi_fonts()

def _resolve_fonts():
    try:
        r = tk.Tk()
        r.withdraw()
        avail = set(r.tk.call("font", "families"))
        r.destroy()
    except Exception:
        avail = set()

    head = "Oswald" if "Oswald" in avail else "Segoe UI"
    body = "Roboto" if "Roboto" in avail else "Segoe UI"
    mono = "Roboto Mono" if "Roboto Mono" in avail else "Consolas"
    return head, body, mono

HEAD_FONT, BODY_FONT, MONO_FONT = _resolve_fonts()

# ---------------------------------------------------------------------------
# DESIGN SYSTEM COLOR TOKENS (Light, Dark)
# ---------------------------------------------------------------------------
COLOR_BG = ("#F6F6F7", "#1A1A1A")          # $th-bg: Main background
COLOR_SURFACE = ("#FFFFFF", "#2D2D2D")     # $th-surface: Cards, sidebar, action bar
COLOR_SURFACE_2 = ("#F1F1F3", "#242424")   # $th-surface-2: Insets, dropzone, inactive controls
COLOR_BORDER = ("#E3E3E7", "#3D3D3D")      # $th-border: Subtle outlines & 1px dividers
COLOR_BORDER_2 = ("#CDCDD3", "#4A4A4A")    # $th-border-2: Interactive outlines (buttons, entries)
COLOR_TEXT = ("#16161A", "#F2F2F2")        # $th-text: Primary text & values
COLOR_TEXT_3 = ("#3C3C43", "#C9C9C9")      # $th-text-3: Secondary labels, paths, log text
COLOR_MUTED = ("#7C7C83", "#8E8E93")       # $th-muted: Placeholders, units, inactive icons
COLOR_BRAND = ("#AA182C", "#AA182C")       # $th-brand: Brand red accent & CTA
COLOR_BRAND_HOVER = ("#8B1324", "#C41F36") # Interactive hover for brand CTA
COLOR_ON_BRAND = ("#FFFFFF", "#F2F2F2")    # $th-on-brand: Text/icons over brand
COLOR_THUMB = ("#16161A", "#F2F2F2")       # $th-thumb: Slider thumb knob
COLOR_SUCCESS = ("#1E824C", "#35B36E")     # $th-success: Reduction & status green
COLOR_SUCCESS_BG = ("#E3F5EA", "#12301F")  # $th-success-bg: Pill badge background

CORNER_RADIUS = 2
BORDER_WIDTH = 1


# ---------------------------------------------------------------------------
# TRUE 1-PIXEL HARDWARE DIVIDER (Theme-Aware)
# ---------------------------------------------------------------------------
class ThemeDivider(tk.Frame):
    """A crisp 1-pixel hardware line that dynamically responds to CustomTkinter theme changes."""
    def __init__(self, master, height: int = 1, width: int | None = None, color: tuple[str, str] = COLOR_BORDER, **kwargs):
        super().__init__(master, height=height, width=width or 1, bd=0, highlightthickness=0, **kwargs)
        self.color_tuple = color
        ctk.AppearanceModeTracker.add(self._on_theme_change)
        self._on_theme_change(ctk.get_appearance_mode())

    def _on_theme_change(self, mode: str):
        color = self.color_tuple[1] if mode == "Dark" else self.color_tuple[0]
        self.configure(bg=color)


# ---------------------------------------------------------------------------
# MAIN VISUAL PROTOTYPE
# ---------------------------------------------------------------------------
class FXbatchUIPrototype(ctk.CTk):
    """
    Standalone visual prototype for FXbatch v05.
    Maintains exact variable names for seamless engine integration in Step 2.
    """

    def __init__(self):
        super().__init__()

        # -------------------------------------------------------------------
        # Backend Contract State & Variables (Exact names from v04)
        # -------------------------------------------------------------------
        self.input_folder_path = ctk.StringVar(value="")
        self.output_folder_path = ctk.StringVar(value="")
        self.quality = ctk.IntVar(value=60)
        self.resize_percent = ctk.IntVar(value=40)
        self.image_types = ["JPG", "PNG", "WEBP"]
        self.selected_image_type = ctk.StringVar(value="JPG")
        self.image_dpi = ctk.StringVar(value="72")
        self.initial_dpi = "72"
        self.sample_image_info = ctk.StringVar(value="No folder selected")
        self.batch_folder_name = "LowRes"

        # Runtime State
        self.is_processing = False
        self.cancel_event = Event()
        self.image_files: list[str] = []
        self.sample_image: str | None = None
        self.cached_sample_img: Image.Image | None = None
        self.current_preview = None
        self.current_theme = "Dark"
        self.is_loaded_state = False

        # Asset Paths
        self.base_dir = BASE_DIR
        self.sample_img_path = path.join(self.base_dir, "Design", "sample-preview.jpg")
        self.logo_light_path = path.join(self.base_dir, "Design", "Logos", "FXbatch.png")
        self.logo_dark_path = path.join(self.base_dir, "Design", "Logos", "FXbatch_rev.png")
        self.favicon_path = path.join(self.base_dir, "Design", "Logos", "favicon.ico")

        # Window Setup
        self.title("FXbatch Resizer 2.0.0")
        w, h = 920, 820
        self.geometry(f"{w}x{h}")
        self.minsize(920, 760)
        self.configure(fg_color=COLOR_BG)

        # Window Favicon
        if sys.platform.startswith("win") and path.exists(self.favicon_path):
            try:
                self.iconbitmap(self.favicon_path)
            except Exception:
                pass

        # Build Clean Layout (No extra custom title bar)
        self._build_layout()

        # Keyboard shortcut to toggle between Empty and Loaded states for inspection
        self.bind("<F2>", lambda e: self.toggle_state())

        # Initial Appearance Mode
        ctk.set_appearance_mode("Dark")
        self._update_theme_switch_ui()

        # Initial State: Empty
        self.set_empty_state()

    # =======================================================================
    # UI Layout Construction
    # =======================================================================
    def _build_layout(self):
        # Configure root grid: Main Body (Row 0, weight=1), Divider (Row 1), ActionBar (Row 2)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(0, weight=1)

        # 1. Main Body Frame (Sidebar + Analysis)
        self.main_body = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.main_body.grid(row=0, column=0, sticky="nsew")
        self.main_body.grid_rowconfigure(0, weight=1)
        self.main_body.grid_columnconfigure(0, weight=0)  # Sidebar fixed 330px
        self.main_body.grid_columnconfigure(1, weight=0)  # Divider 1px
        self.main_body.grid_columnconfigure(2, weight=1)  # Analysis expanding

        self._build_sidebar()

        self.vertical_divider = ThemeDivider(self.main_body, width=1)
        self.vertical_divider.grid(row=0, column=1, sticky="ns")

        self._build_analysis_area()

        # 2. Bottom Divider (1px)
        self.bottom_divider = ThemeDivider(self, height=1)
        self.bottom_divider.grid(row=1, column=0, sticky="ew")

        # 3. Action Bar (Height: 72px)
        self._build_action_bar()

    # -----------------------------------------------------------------------
    # 1. Configuration Sidebar (Width: 330px)
    # -----------------------------------------------------------------------
    def _build_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(
            self.main_body, width=330, fg_color=COLOR_SURFACE, corner_radius=0
        )
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_propagate(False)
        self.sidebar_frame.grid_columnconfigure(0, weight=1)
        self.sidebar_frame.grid_rowconfigure(9, weight=1)  # Row 9 absorbs all vertical space

        p = {"padx": 20}

        # Row 0: Brand Lockup with PNG/SVG Logo
        self.brand_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.brand_frame.grid(row=0, column=0, pady=(20, 16), sticky="w", **p)

        self._build_brand_logo()

        # Row 1: Section Header — SOURCE FOLDERS (with visible 1px line)
        self._create_section_header(self.sidebar_frame, 1, "SOURCE FOLDERS")

        # Row 2: INPUT FOLDER
        self.input_entry, self.input_field_frame = self._create_path_picker_row(
            self.sidebar_frame,
            row=2,
            label_text="INPUT FOLDER",
            variable=self.input_folder_path,
            browse_command=self.browse_input_folder,
        )

        # Row 3: OUTPUT FOLDER
        self.output_entry, self.output_field_frame = self._create_path_picker_row(
            self.sidebar_frame,
            row=3,
            label_text="OUTPUT FOLDER",
            variable=self.output_folder_path,
            browse_command=self.browse_output_folder,
        )

        # Row 4: Section Header — OUTPUT SETTINGS (with visible 1px line)
        self._create_section_header(self.sidebar_frame, 4, "OUTPUT SETTINGS")

        # Row 5: QUALITY Slider
        self.quality_slider, self.quality_input_box = self._create_slider_row(
            self.sidebar_frame,
            row=5,
            label_text="QUALITY",
            variable=self.quality,
            from_=10,
            to=100,
            command=self._on_quality_changed,
        )

        # Row 6: FORMAT Dropdown
        self.image_type_dropdown = self._create_format_row(
            self.sidebar_frame, row=6, label_text="FORMAT"
        )

        # Row 7: RESIZE % Slider
        self.resize_slider, self.resize_input_box = self._create_slider_row(
            self.sidebar_frame,
            row=7,
            label_text="RESIZE %",
            variable=self.resize_percent,
            from_=10,
            to=100,
            command=self._on_resize_changed,
        )

        # Row 8: RESIZE DPI Entry
        self.dpi_entry = self._create_dpi_row(
            self.sidebar_frame, row=8, label_text="RESIZE DPI"
        )

        # Row 9: Empty Expanding Row (No frame widget, rowconfigure weight=1 handles spacing)

        # Row 10: Sidebar Bottom Actions (Settings & Help)
        self.sidebar_actions = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent", height=36)
        self.sidebar_actions.grid(row=10, column=0, pady=(0, 20), sticky="ew", **p)
        self.sidebar_actions.grid_columnconfigure(0, weight=1)
        self.sidebar_actions.grid_columnconfigure(1, weight=1)

        self.settings_button = ctk.CTkButton(
            self.sidebar_actions,
            text="⚙ Settings",
            command=self.show_settings,
            height=36,
            corner_radius=CORNER_RADIUS,
            font=ctk.CTkFont(family=HEAD_FONT, size=12, weight="bold"),
            fg_color="transparent",
            hover_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER_2,
            border_width=BORDER_WIDTH,
            text_color=COLOR_TEXT_3,
        )
        self.settings_button.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self.help_button = ctk.CTkButton(
            self.sidebar_actions,
            text="ⓘ Help",
            command=self.show_help,
            height=36,
            corner_radius=CORNER_RADIUS,
            font=ctk.CTkFont(family=HEAD_FONT, size=12, weight="bold"),
            fg_color="transparent",
            hover_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER_2,
            border_width=BORDER_WIDTH,
            text_color=COLOR_TEXT_3,
        )
        self.help_button.grid(row=0, column=1, padx=(4, 0), sticky="ew")

    def _build_brand_logo(self):
        """Builds the logo header using the provided PNG logos (light and dark)."""
        if path.exists(self.logo_light_path) and path.exists(self.logo_dark_path):
            try:
                img_light = Image.open(self.logo_light_path)
                img_dark = Image.open(self.logo_dark_path)
                self.logo_image = ctk.CTkImage(light_image=img_light, dark_image=img_dark, size=(140, 26))
                self.logo_label = ctk.CTkLabel(self.brand_frame, image=self.logo_image, text="")
                self.logo_label.pack(anchor="w")
            except Exception as e:
                self._build_fallback_brand_text()
        else:
            self._build_fallback_brand_text()

        self.brand_sub = ctk.CTkLabel(
            self.brand_frame,
            text="BATCH IMAGE RESIZER 2.0.0",
            font=ctk.CTkFont(family=HEAD_FONT, size=10, weight="bold"),
            text_color=COLOR_MUTED,
        )
        self.brand_sub.pack(anchor="w", pady=(2, 0))

    def _build_fallback_brand_text(self):
        row = ctk.CTkFrame(self.brand_frame, fg_color="transparent")
        row.pack(anchor="w")
        ctk.CTkLabel(
            row, text="FX", font=ctk.CTkFont(family=HEAD_FONT, size=24, weight="bold"), text_color=COLOR_BRAND
        ).pack(side="left")
        ctk.CTkLabel(
            row, text="batch", font=ctk.CTkFont(family=HEAD_FONT, size=24, weight="bold"), text_color=COLOR_TEXT
        ).pack(side="left")

    def _create_section_header(self, parent, row: int, title: str):
        """Creates section title with a true 1-pixel hardware divider line."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=0, padx=20, pady=(10, 8), sticky="ew")
        frame.grid_columnconfigure(0, weight=1)

        label = ctk.CTkLabel(
            frame,
            text=title,
            font=ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_MUTED,
            anchor="w",
        )
        label.grid(row=0, column=0, sticky="w", pady=(0, 6))

        div = ThemeDivider(frame, height=1)
        div.grid(row=1, column=0, sticky="ew")

    def _create_path_picker_row(self, parent, row: int, label_text: str, variable: ctk.StringVar, browse_command):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=0, padx=20, pady=(0, 10), sticky="ew")
        frame.grid_columnconfigure(0, weight=1)

        label = ctk.CTkLabel(
            frame,
            text=label_text,
            font=ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_MUTED,
            anchor="w",
        )
        label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))

        row_frame = ctk.CTkFrame(frame, fg_color="transparent", height=36)
        row_frame.grid(row=1, column=0, sticky="ew")
        row_frame.grid_columnconfigure(0, weight=1)
        row_frame.grid_columnconfigure(1, weight=0)

        field_container = ctk.CTkFrame(
            row_frame,
            height=36,
            fg_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            corner_radius=CORNER_RADIUS,
        )
        field_container.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        field_container.grid_propagate(False)
        field_container.grid_columnconfigure(1, weight=1)

        folder_icon = ctk.CTkLabel(
            field_container,
            text="📁",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_MUTED,
            width=26,
        )
        folder_icon.grid(row=0, column=0, padx=(8, 2), pady=4)

        entry = ctk.CTkEntry(
            field_container,
            textvariable=variable,
            font=ctk.CTkFont(family=MONO_FONT, size=11),
            fg_color="transparent",
            border_width=0,
            text_color=COLOR_TEXT_3,
        )
        entry.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=4)

        browse_btn = ctk.CTkButton(
            row_frame,
            text="Browse",
            command=browse_command,
            width=72,
            height=36,
            corner_radius=CORNER_RADIUS,
            font=ctk.CTkFont(family=HEAD_FONT, size=12, weight="bold"),
            fg_color="transparent",
            hover_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER_2,
            border_width=BORDER_WIDTH,
            text_color=COLOR_TEXT,
        )
        browse_btn.grid(row=0, column=1, sticky="e")

        return entry, field_container

    def _create_slider_row(self, parent, row: int, label_text: str, variable: ctk.IntVar, from_: int, to: int, command):
        frame = ctk.CTkFrame(parent, fg_color="transparent", height=28)
        frame.grid(row=row, column=0, padx=20, pady=4, sticky="ew")
        frame.grid_columnconfigure(1, weight=1)

        label = ctk.CTkLabel(
            frame,
            text=label_text,
            width=70,
            font=ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_TEXT_3,
            anchor="w",
        )
        label.grid(row=0, column=0, sticky="w")

        slider = ctk.CTkSlider(
            frame,
            from_=from_,
            to=to,
            variable=variable,
            command=command,
            width=168,
            height=16,
            corner_radius=CORNER_RADIUS,
            fg_color=COLOR_BORDER,
            progress_color=COLOR_BRAND,
            button_color=COLOR_THUMB,
            button_hover_color=COLOR_BRAND,
            border_width=0,
        )
        slider.grid(row=0, column=1, padx=8, sticky="ew")

        input_var = ctk.StringVar(value=str(variable.get()))
        input_box = ctk.CTkEntry(
            frame,
            textvariable=input_var,
            width=42,
            height=24,
            corner_radius=CORNER_RADIUS,
            font=ctk.CTkFont(family=MONO_FONT, size=11),
            fg_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            text_color=COLOR_TEXT,
            justify="center",
            validate="key",
            validatecommand=(frame.register(self.validate_slider_input), "%P"),
        )
        input_box.grid(row=0, column=2, sticky="e")

        # Select full text when clicked or focused
        def _on_select_all(e=None):
            input_box.after(15, lambda: (input_box.select_range(0, "end"), input_box.icursor("end")))

        input_box.bind("<FocusIn>", _on_select_all)
        input_box.bind("<Button-1>", _on_select_all)
        if hasattr(input_box, "_entry"):
            input_box._entry.bind("<FocusIn>", _on_select_all)
            input_box._entry.bind("<Button-1>", _on_select_all)

        # Commit on FocusOut or Return key
        def _commit_input(e=None):
            self.commit_slider_input(input_var, variable, slider, from_, to, label_text)

        input_box.bind("<FocusOut>", _commit_input)
        input_box.bind("<Return>", _commit_input)
        if hasattr(input_box, "_entry"):
            input_box._entry.bind("<FocusOut>", _commit_input)
            input_box._entry.bind("<Return>", _commit_input)

        # Tracing slider variable updates
        variable.trace_add("write", lambda *args: input_var.set(str(variable.get())))

        return slider, input_box

    def _create_format_row(self, parent, row: int, label_text: str):
        frame = ctk.CTkFrame(parent, fg_color="transparent", height=32)
        frame.grid(row=row, column=0, padx=20, pady=4, sticky="ew")
        frame.grid_columnconfigure(1, weight=1)

        label = ctk.CTkLabel(
            frame,
            text=label_text,
            width=70,
            font=ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_TEXT_3,
            anchor="w",
        )
        label.grid(row=0, column=0, sticky="w")

        opt_menu = ctk.CTkOptionMenu(
            frame,
            variable=self.selected_image_type,
            values=[f".{fmt}" for fmt in self.image_types],
            command=self._on_format_changed,
            height=30,
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
        opt_menu.grid(row=0, column=1, columnspan=2, sticky="ew")
        return opt_menu

    def _create_dpi_row(self, parent, row: int, label_text: str):
        frame = ctk.CTkFrame(parent, fg_color="transparent", height=32)
        frame.grid(row=row, column=0, padx=20, pady=4, sticky="ew")
        frame.grid_columnconfigure(1, weight=1)

        label = ctk.CTkLabel(
            frame,
            text=label_text,
            width=70,
            font=ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_TEXT_3,
            anchor="w",
        )
        label.grid(row=0, column=0, sticky="w")

        dpi_entry = ctk.CTkEntry(
            frame,
            textvariable=self.image_dpi,
            width=56,
            height=30,
            corner_radius=CORNER_RADIUS,
            font=ctk.CTkFont(family=MONO_FONT, size=11),
            fg_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            text_color=COLOR_TEXT,
            justify="center",
        )
        dpi_entry.grid(row=0, column=1, sticky="w")

        # Select full text when clicked or focused
        def _on_select_all(e=None):
            dpi_entry.after(15, lambda: (dpi_entry.select_range(0, "end"), dpi_entry.icursor("end")))

        dpi_entry.bind("<FocusIn>", _on_select_all)
        dpi_entry.bind("<Button-1>", _on_select_all)
        if hasattr(dpi_entry, "_entry"):
            dpi_entry._entry.bind("<FocusIn>", _on_select_all)
            dpi_entry._entry.bind("<Button-1>", _on_select_all)

        return dpi_entry

    # -----------------------------------------------------------------------
    # 2. Analysis Area (Expanding Right Panel)
    # -----------------------------------------------------------------------
    def _build_analysis_area(self):
        self.analysis_frame = ctk.CTkFrame(
            self.main_body, fg_color=COLOR_BG, corner_radius=0
        )
        self.analysis_frame.grid(row=0, column=2, sticky="nsew", padx=20, pady=20)
        self.analysis_frame.grid_columnconfigure(0, weight=1)
        self.analysis_frame.grid_rowconfigure(1, weight=1)  # Preview card expands

        # Row 0: Analysis Header (Height: 40px)
        self._build_analysis_header()

        # Row 1: Preview Card (Expanding weight=1, height ~329px)
        self._build_preview_card()

        # Row 2: Metrics Strip (Height: 80px, 5 cards)
        self._build_metrics_strip()

        # Row 3: Activity Log Card (Height: 132px)
        self._build_activity_log()

    def _build_analysis_header(self):
        self.header_frame = ctk.CTkFrame(self.analysis_frame, height=40, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        self.header_frame.grid_columnconfigure(1, weight=1)

        # Title Block
        title_block = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        title_block.grid(row=0, column=0, sticky="w")

        self.analysis_eyebrow = ctk.CTkLabel(
            title_block,
            text="SAMPLE ANALYSIS",
            font=ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_MUTED,
            anchor="w",
        )
        self.analysis_eyebrow.pack(anchor="w")

        self.sample_filename_label = ctk.CTkLabel(
            title_block,
            text="No sample image",
            font=ctk.CTkFont(family=BODY_FONT, size=13, weight="bold"),
            text_color=COLOR_MUTED,
            anchor="w",
        )
        self.sample_filename_label.pack(anchor="w")

        # Controls Block (Status Pill + Resample Button)
        controls_block = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        controls_block.grid(row=0, column=2, sticky="e")

        # Status Pill Badge (Double-click toggles mock state)
        self.status_pill = ctk.CTkFrame(
            controls_block,
            height=26,
            corner_radius=CORNER_RADIUS,
            fg_color=COLOR_SURFACE_2,
            cursor="hand2",
        )
        self.status_pill.pack(side="left", padx=(0, 10))
        self.status_pill.bind("<Button-1>", lambda e: self.toggle_state())

        self.status_pill_label = ctk.CTkLabel(
            self.status_pill,
            text="• AWAITING FOLDER",
            font=ctk.CTkFont(family=HEAD_FONT, size=10, weight="bold"),
            text_color=COLOR_MUTED,
            padx=10,
            pady=4,
            cursor="hand2",
        )
        self.status_pill_label.pack()
        self.status_pill_label.bind("<Button-1>", lambda e: self.toggle_state())

        # Resample Preview Button
        self.resample_button = ctk.CTkButton(
            controls_block,
            text="↻ Resample Preview",
            command=self.pick_random_image,
            height=34,
            corner_radius=CORNER_RADIUS,
            font=ctk.CTkFont(family=HEAD_FONT, size=12, weight="bold"),
            fg_color="transparent",
            hover_color=COLOR_SURFACE,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            text_color=COLOR_MUTED,
        )
        self.resample_button.pack(side="left")

    def _build_preview_card(self):
        self.preview_card = ctk.CTkFrame(
            self.analysis_frame,
            fg_color=COLOR_SURFACE,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            corner_radius=CORNER_RADIUS,
        )
        self.preview_card.grid(row=1, column=0, sticky="nsew", pady=(0, 16))
        self.preview_card.grid_rowconfigure(2, weight=1)
        self.preview_card.grid_columnconfigure(0, weight=1)

        # Card Header (Height: 34px)
        header = ctk.CTkFrame(self.preview_card, height=34, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14)
        header.grid_propagate(False)
        header.grid_columnconfigure(1, weight=1)

        lbl = ctk.CTkLabel(
            header,
            text="SAMPLE PREVIEW",
            font=ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_MUTED,
        )
        lbl.grid(row=0, column=0, sticky="w", pady=8)

        self.preview_dims_label = ctk.CTkLabel(
            header,
            text="no sample loaded",
            font=ctk.CTkFont(family=MONO_FONT, size=11),
            text_color=COLOR_MUTED,
        )
        self.preview_dims_label.grid(row=0, column=2, sticky="e", pady=8)

        # Header 1px Divider
        div = ThemeDivider(self.preview_card, height=1)
        div.grid(row=1, column=0, sticky="ew")

        # Preview Container Frame
        self.image_preview_frame = ctk.CTkFrame(
            self.preview_card, fg_color=COLOR_SURFACE_2, corner_radius=0
        )
        self.image_preview_frame.grid(row=2, column=0, sticky="nsew")
        self.image_preview_frame.grid_rowconfigure(0, weight=1)
        self.image_preview_frame.grid_columnconfigure(0, weight=1)

        # 1) Empty State Dropzone Widget (Click to toggle demo state)
        self.dropzone_frame = ctk.CTkFrame(self.image_preview_frame, fg_color="transparent", cursor="hand2")
        self.dropzone_frame.grid(row=0, column=0, sticky="nsew")
        self.dropzone_frame.grid_rowconfigure(0, weight=1)
        self.dropzone_frame.grid_columnconfigure(0, weight=1)
        self.dropzone_frame.bind("<Button-1>", lambda e: self.toggle_state())

        inner_drop = ctk.CTkFrame(self.dropzone_frame, fg_color="transparent", cursor="hand2")
        inner_drop.place(relx=0.5, rely=0.5, anchor="center")
        inner_drop.bind("<Button-1>", lambda e: self.toggle_state())

        icon_lbl = ctk.CTkLabel(
            inner_drop,
            text="🖼",
            font=ctk.CTkFont(size=32),
            text_color=COLOR_BORDER_2,
            cursor="hand2",
        )
        icon_lbl.pack(pady=(0, 8))
        icon_lbl.bind("<Button-1>", lambda e: self.toggle_state())

        drop_title = ctk.CTkLabel(
            inner_drop,
            text="Drop Folder Here",
            font=ctk.CTkFont(family=BODY_FONT, size=14, weight="bold"),
            text_color=COLOR_TEXT,
            cursor="hand2",
        )
        drop_title.pack()
        drop_title.bind("<Button-1>", lambda e: self.toggle_state())

        drop_sub = ctk.CTkLabel(
            inner_drop,
            text="or Click Browse to select a folder",
            font=ctk.CTkFont(family=BODY_FONT, size=12),
            text_color=COLOR_MUTED,
            cursor="hand2",
        )
        drop_sub.pack(pady=(4, 0))
        drop_sub.bind("<Button-1>", lambda e: self.toggle_state())

        # 2) Filled State Image Display Widget
        self.image_preview = ctk.CTkLabel(
            self.image_preview_frame,
            text="",
            image=None,
        )

    def _build_metrics_strip(self):
        self.metrics_container = ctk.CTkFrame(
            self.analysis_frame, height=80, fg_color="transparent"
        )
        self.metrics_container.grid(row=2, column=0, sticky="ew", pady=(0, 16))
        for c in range(5):
            self.metrics_container.grid_columnconfigure(c, weight=1)

        cards_spec = [
            ("ORIGINAL", "—", ""),
            ("OUTPUT", "—", ""),
            ("NEW SIZE", "—", ""),
            ("REDUCTION", "—", ""),
            ("SAMPLE DPI", "—", ""),
        ]

        self.metric_cards = {}
        for idx, (title, val, sub) in enumerate(cards_spec):
            card = ctk.CTkFrame(
                self.metrics_container,
                height=80,
                fg_color=COLOR_SURFACE,
                border_color=COLOR_BORDER,
                border_width=BORDER_WIDTH,
                corner_radius=CORNER_RADIUS,
            )
            card.grid(row=0, column=idx, padx=(0 if idx == 0 else 6, 0 if idx == 4 else 6), sticky="ew")
            card.grid_propagate(False)

            lbl = ctk.CTkLabel(
                card,
                text=title,
                font=ctk.CTkFont(family=HEAD_FONT, size=10, weight="bold"),
                text_color=COLOR_MUTED,
                anchor="w",
            )
            lbl.pack(anchor="w", padx=13, pady=(10, 2))

            val_color = COLOR_SUCCESS if title == "REDUCTION" else COLOR_TEXT
            v_lbl = ctk.CTkLabel(
                card,
                text=val,
                font=ctk.CTkFont(family=MONO_FONT, size=13, weight="bold"),
                text_color=val_color,
                anchor="w",
            )
            v_lbl.pack(anchor="w", padx=13)

            s_lbl = ctk.CTkLabel(
                card,
                text=sub,
                font=ctk.CTkFont(family=MONO_FONT, size=10),
                text_color=COLOR_MUTED,
                anchor="w",
            )
            s_lbl.pack(anchor="w", padx=13, pady=(2, 0))

            self.metric_cards[title] = (card, v_lbl, s_lbl)

    def _build_activity_log(self):
        self.log_card = ctk.CTkFrame(
            self.analysis_frame,
            height=172,
            fg_color=COLOR_SURFACE,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            corner_radius=CORNER_RADIUS,
        )
        self.log_card.grid(row=3, column=0, sticky="ew")
        self.log_card.grid_propagate(False)
        self.log_card.grid_rowconfigure(1, weight=1)
        self.log_card.grid_columnconfigure(0, weight=1)

        eyebrow = ctk.CTkLabel(
            self.log_card,
            text="ACTIVITY LOG",
            font=ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_MUTED,
            anchor="w",
        )
        eyebrow.grid(row=0, column=0, sticky="w", padx=14, pady=(10, 4))

        self.log_text = ctk.CTkTextbox(
            self.log_card,
            font=ctk.CTkFont(family=MONO_FONT, size=11),
            fg_color="transparent",
            text_color=COLOR_TEXT_3,
            wrap="word",
            border_width=0,
            activate_scrollbars=True,
        )
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

    # -----------------------------------------------------------------------
    # 3. Action Bar (Height: 72px)
    # -----------------------------------------------------------------------
    def _build_action_bar(self):
        self.action_bar = ctk.CTkFrame(self, height=72, fg_color=COLOR_SURFACE, corner_radius=0)
        self.action_bar.grid(row=2, column=0, sticky="ew")
        self.action_bar.grid_propagate(False)
        self.action_bar.grid_rowconfigure(0, weight=1)  # Vertically centers all children
        self.action_bar.grid_columnconfigure(1, weight=0)
        self.action_bar.grid_columnconfigure(2, weight=1)  # Expanding spacer

        # Left: Theme Switcher [ LIGHT | DARK ] (Symmetrically Centered)
        self.theme_switch_frame = ctk.CTkFrame(
            self.action_bar,
            width=118,
            height=28,
            fg_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            corner_radius=CORNER_RADIUS,
        )
        self.theme_switch_frame.grid(row=0, column=0, padx=(20, 16), sticky="w")
        self.theme_switch_frame.grid_propagate(False)
        self.theme_switch_frame.grid_rowconfigure(0, weight=1)
        self.theme_switch_frame.grid_columnconfigure((0, 1), weight=1)

        self.btn_light = ctk.CTkButton(
            self.theme_switch_frame,
            text="LIGHT",
            corner_radius=CORNER_RADIUS,
            font=ctk.CTkFont(family=HEAD_FONT, size=10, weight="bold"),
            fg_color="transparent",
            hover_color=COLOR_SURFACE,
            text_color=COLOR_MUTED,
            command=lambda: self.set_theme("Light"),
        )
        self.btn_light.grid(row=0, column=0, padx=(2, 1), pady=2, sticky="nsew")

        self.btn_dark = ctk.CTkButton(
            self.theme_switch_frame,
            text="DARK",
            corner_radius=CORNER_RADIUS,
            font=ctk.CTkFont(family=HEAD_FONT, size=10, weight="bold"),
            fg_color=COLOR_BRAND,
            hover_color=COLOR_BRAND_HOVER,
            text_color=COLOR_ON_BRAND,
            command=lambda: self.set_theme("Dark"),
        )
        self.btn_dark.grid(row=0, column=1, padx=(1, 2), pady=2, sticky="nsew")

        # Center: Telemetry Status Summary & Dot
        self.summary_frame = ctk.CTkFrame(self.action_bar, fg_color="transparent", cursor="hand2")
        self.summary_frame.grid(row=0, column=1, sticky="w")
        self.summary_frame.bind("<Button-1>", lambda e: self.toggle_state())

        self.status_dot = ctk.CTkLabel(
            self.summary_frame,
            text="●",
            font=ctk.CTkFont(size=9),
            text_color=COLOR_MUTED,
            cursor="hand2",
        )
        self.status_dot.pack(side="left", padx=(0, 6))
        self.status_dot.bind("<Button-1>", lambda e: self.toggle_state())

        self.status_summary_label = ctk.CTkLabel(
            self.summary_frame,
            text="Waiting for folder  ·  JPG · quality 60 · resize 40% · 72 DPI",
            font=ctk.CTkFont(family=BODY_FONT, size=12),
            text_color=COLOR_TEXT_3,
            cursor="hand2",
        )
        self.status_summary_label.pack(side="left")
        self.status_summary_label.bind("<Button-1>", lambda e: self.toggle_state())

        # Right: Batch Convert Images CTA Button
        self.process_button = ctk.CTkButton(
            self.action_bar,
            text="▷ Batch Convert Images",
            command=self.process_images,
            width=200,
            height=44,
            corner_radius=CORNER_RADIUS,
            font=ctk.CTkFont(family=HEAD_FONT, size=12, weight="bold"),
            fg_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            hover_color=COLOR_BORDER_2,
            text_color=COLOR_MUTED,
        )
        self.process_button.grid(row=0, column=3, padx=20, sticky="e")

        # Hidden Progress bar (gridded when processing in Step 2)
        self.progress_frame = ctk.CTkFrame(self.action_bar, fg_color="transparent")
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.cancel_button = ctk.CTkButton(self.progress_frame, text="Cancel")

    # =======================================================================
    # State Transitions: Empty vs Loaded (Filled)
    # =======================================================================
    def toggle_state(self):
        if self.is_loaded_state:
            self.set_empty_state()
        else:
            self.set_loaded_state()

    def set_empty_state(self):
        """Matches FXbatch Dark.jpg & FXbatch Light.jpg"""
        self.is_loaded_state = False
        self.input_folder_path.set("No folder selected")
        self.output_folder_path.set("No folder selected")

        # Header
        self.sample_filename_label.configure(text="No sample image", text_color=COLOR_MUTED)
        self.status_pill.configure(fg_color=COLOR_SURFACE_2)
        self.status_pill_label.configure(text="• AWAITING FOLDER", text_color=COLOR_MUTED)
        self.resample_button.configure(
            border_color=COLOR_BORDER, text_color=COLOR_MUTED, state="disabled"
        )

        # Preview Container: Show Dropzone, hide image
        self.preview_dims_label.configure(text="no sample loaded")
        self.image_preview.grid_forget()
        self.dropzone_frame.grid(row=0, column=0, sticky="nsew")

        # Metric Cards
        for title, (card, v_lbl, s_lbl) in self.metric_cards.items():
            v_lbl.configure(text="—", text_color=COLOR_MUTED)
            s_lbl.configure(text="")

        # Activity Log
        self.log_text.delete("1.0", "end")
        self.log_text.insert(
            "end",
            "› Ready. Select an input folder and an output folder to begin.\n"
            "› Supported formats: JPG · PNG · WEBP · TIFF · BMP\n"
            "› Drag a folder onto the preview area, or use Browse to select one.\n"
        )

        # Action Bar Status
        self.status_dot.configure(text_color=COLOR_MUTED)
        self._update_status_summary("Waiting for folder")

        # CTA Disabled styling
        self.process_button.configure(
            fg_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            hover_color=COLOR_BORDER_2,
            text_color=COLOR_MUTED,
            state="disabled",
        )

    def set_loaded_state(self):
        """Matches FXbatch Dark - Image.jpg & FXbatch Light - Image.jpg"""
        self.is_loaded_state = True
        self.input_folder_path.set("E:/Temp/Test02")
        self.output_folder_path.set(r"E:/Temp/Test02\LowRes")

        # Header
        self.sample_filename_label.configure(text="5H3A2988.JPG", text_color=COLOR_TEXT)
        self.status_pill.configure(fg_color=COLOR_SUCCESS_BG)
        self.status_pill_label.configure(text="• FOLDER READY", text_color=COLOR_SUCCESS)
        self.resample_button.configure(
            border_color=COLOR_BORDER_2, text_color=COLOR_TEXT, state="normal"
        )

        # Preview Container: Hide Dropzone, show cover image
        self.preview_dims_label.configure(text="5760 × 3840  →  2304 × 1536")
        self.dropzone_frame.grid_forget()
        self._display_sample_image()

        # Metric Cards
        loaded_metrics = {
            "ORIGINAL": ("5760 × 3840", "5.7 MB", COLOR_TEXT),
            "OUTPUT": ("2304 × 1536", "JPG · Q60", COLOR_TEXT),
            "NEW SIZE": ("251.9 KB", "est. output", COLOR_TEXT),
            "REDUCTION": ("95.7%", "vs original", COLOR_SUCCESS),
            "SAMPLE DPI": ("72", "unchanged", COLOR_TEXT),
        }
        for title, (val, sub, col) in loaded_metrics.items():
            if title in self.metric_cards:
                _, v_lbl, s_lbl = self.metric_cards[title]
                v_lbl.configure(text=val, text_color=col)
                s_lbl.configure(text=sub)

        # Activity Log
        self.log_text.delete("1.0", "end")
        self.log_text.insert(
            "end",
            "› Input folder loaded: E:/Temp/Test02\n"
            "› Sample 5H3A2988.JPG analyzed — 2304 × 1536 at quality 60\n"
            "› Estimated output 251.9 KB (95.7% smaller). Ready to batch convert.\n"
        )

        # Action Bar Status
        self.status_dot.configure(text_color=COLOR_SUCCESS)
        self._update_status_summary("Ready to convert")

        # CTA Enabled styling
        self.process_button.configure(
            fg_color=COLOR_BRAND,
            border_width=0,
            hover_color=COLOR_BRAND_HOVER,
            text_color=COLOR_ON_BRAND,
            state="normal",
        )

    def _display_sample_image(self):
        if not path.exists(self.sample_img_path):
            return

        try:
            with Image.open(self.sample_img_path) as img:
                target_w, target_h = 540, 280
                thumb = ImageOps.fit(img, (target_w, target_h), Image.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=thumb, dark_image=thumb, size=(target_w, target_h))

            self.image_preview.configure(image=ctk_img)
            self.image_preview.grid(row=0, column=0, sticky="nsew")
            self.current_preview = ctk_img
        except Exception as e:
            print(f"Error loading preview image: {e}")

    # =======================================================================
    # Theme Switching & Synchronized Controls
    # =======================================================================
    def set_theme(self, mode: str):
        self.current_theme = mode
        ctk.set_appearance_mode(mode)
        self._update_theme_switch_ui()

    def _update_theme_switch_ui(self):
        if self.current_theme == "Light":
            self.btn_light.configure(
                fg_color=COLOR_BRAND, text_color=COLOR_ON_BRAND, hover_color=COLOR_BRAND_HOVER
            )
            self.btn_dark.configure(
                fg_color="transparent", text_color=COLOR_MUTED, hover_color=COLOR_SURFACE
            )
        else:
            self.btn_dark.configure(
                fg_color=COLOR_BRAND, text_color=COLOR_ON_BRAND, hover_color=COLOR_BRAND_HOVER
            )
            self.btn_light.configure(
                fg_color="transparent", text_color=COLOR_MUTED, hover_color=COLOR_SURFACE
            )

    def validate_slider_input(self, P: str) -> bool:
        if P == "":
            return True
        return P.isdigit() and len(P) <= 3

    def commit_slider_input(self, input_var: ctk.StringVar, variable: ctk.IntVar, slider: ctk.CTkSlider, from_: int, to: int, label_text: str):
        raw = input_var.get().strip()
        try:
            val = int(raw)
            clamped = max(from_, min(val, to))
        except ValueError:
            fallback = 60 if "quality" in label_text.lower() else 40
            try:
                clamped = variable.get()
            except Exception:
                clamped = fallback
            clamped = max(from_, min(clamped, to))

        variable.set(clamped)
        slider.set(clamped)
        input_var.set(str(clamped))
        self._update_status_summary()

    def _on_quality_changed(self, value):
        val = int(float(value))
        self.quality.set(val)
        self._update_status_summary()

    def _on_resize_changed(self, value):
        val = int(float(value))
        self.resize_percent.set(val)
        self._update_status_summary()

    def _on_format_changed(self, value):
        self._update_status_summary()

    def _update_status_summary(self, prefix: str | None = None):
        if prefix is None:
            prefix = "Ready to convert" if self.is_loaded_state else "Waiting for folder"
        fmt = self.selected_image_type.get().replace(".", "")
        q = self.quality.get()
        r = self.resize_percent.get()
        dpi = self.image_dpi.get() or "72"
        text = f"{prefix}  ·  {fmt} · quality {q} · resize {r}% · {dpi} DPI"
        self.status_summary_label.configure(text=text)

    # =======================================================================
    # Command Stubs for Engine Parity (Step 2 Implementation)
    # =======================================================================
    def browse_input_folder(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory()
        if folder:
            self.input_folder_path.set(folder)
            self.set_loaded_state()

    def browse_output_folder(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder_path.set(folder)

    def pick_random_image(self):
        self.log_text.insert("end", "› Resampling sample image...\n")
        self.log_text.see("end")

    def process_images(self):
        self.log_text.insert("end", "› Batch Convert Images clicked (visual prototype mode).\n")
        self.log_text.see("end")

    def show_settings(self):
        self.log_text.insert("end", "› Settings dialog invoked.\n")
        self.log_text.see("end")

    def show_help(self):
        self.log_text.insert("end", "› Help documentation invoked.\n")
        self.log_text.see("end")


if __name__ == "__main__":
    app = FXbatchUIPrototype()
    app.mainloop()
