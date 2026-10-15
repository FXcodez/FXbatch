# widgets.py — FXbatch v05 Widget Construction & Layout Engine
# Exact implementation matching FXbatch_Conversion.pen and v05 UI Specifications.
from __future__ import annotations

import ctypes
import os
from os import path
import sys
import tkinter as tk
import customtkinter as ctk
from PIL import Image

# ---------------------------------------------------------------------------
# LOAD DESIGN FONTS (Oswald, Roboto, Roboto Mono)
# ---------------------------------------------------------------------------
BASE_DIR = getattr(sys, "_MEIPASS", path.dirname(path.abspath(__file__)))
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
# WIDGET CREATOR (Split from functional logic for clean maintainability)
# ---------------------------------------------------------------------------
class WidgetCreator:
    def __init__(self, app, ctk_module, initial_quality: int, initial_resize: int, initial_dpi: str):
        self.app = app
        self.ctk = ctk_module
        self.initial_quality = initial_quality
        self.initial_resize = initial_resize
        self.initial_dpi = initial_dpi
        self.update_timer = None

        # Widget references
        self.input_entry = None
        self.output_entry = None
        self.quality_slider = None
        self.quality_input_box = None
        self.resize_slider = None
        self.resize_input_box = None
        self.image_type_dropdown = None

    def create_widgets(self):
        # Configure root grid: Main Body (Row 0, weight=1), Divider (Row 1), ActionBar (Row 2)
        self.app.grid_rowconfigure(0, weight=1)
        self.app.grid_rowconfigure(1, weight=0)
        self.app.grid_rowconfigure(2, weight=0)
        self.app.grid_columnconfigure(0, weight=1)

        # 1. Main Body Frame (Sidebar + Analysis)
        self.app.main_body = self.ctk.CTkFrame(self.app, fg_color="transparent", corner_radius=0)
        self.app.main_body.grid(row=0, column=0, sticky="nsew")
        self.app.main_body.grid_rowconfigure(0, weight=1)
        self.app.main_body.grid_columnconfigure(0, weight=0)  # Sidebar fixed 330px
        self.app.main_body.grid_columnconfigure(1, weight=0)  # Divider 1px
        self.app.main_body.grid_columnconfigure(2, weight=1)  # Analysis expanding

        self._build_sidebar()

        self.app.vertical_divider = ThemeDivider(self.app.main_body, width=1)
        self.app.vertical_divider.grid(row=0, column=1, sticky="ns")

        self._build_analysis_area()

        # 2. Bottom Divider (1px)
        self.app.bottom_divider = ThemeDivider(self.app, height=1)
        self.app.bottom_divider.grid(row=1, column=0, sticky="ew")

        # 3. Action Bar (Height: 72px)
        self._build_action_bar()

        # Sync initial format & quality states
        self.on_image_type_changed(self.app.selected_image_type.get(), trigger_update=False)

        return self.app.main_body

    # -----------------------------------------------------------------------
    # 1. Configuration Sidebar (Width: 330px)
    # -----------------------------------------------------------------------
    def _build_sidebar(self):
        self.app.sidebar_frame = self.ctk.CTkFrame(
            self.app.main_body, width=330, fg_color=COLOR_SURFACE, corner_radius=0
        )
        self.app.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.app.sidebar_frame.grid_propagate(False)
        self.app.sidebar_frame.grid_columnconfigure(0, weight=1)
        self.app.sidebar_frame.grid_rowconfigure(9, weight=1)  # Row 9 absorbs all vertical space

        p = {"padx": 20}

        # Row 0: Brand Lockup with PNG Logo
        self.app.brand_frame = self.ctk.CTkFrame(self.app.sidebar_frame, fg_color="transparent")
        self.app.brand_frame.grid(row=0, column=0, pady=(20, 16), sticky="w", **p)

        self._build_brand_logo()

        # Row 1: Section Header — SOURCE FOLDERS
        self._create_section_header(self.app.sidebar_frame, 1, "SOURCE FOLDERS")

        # Row 2: INPUT FOLDER
        self.app.input_entry, self.app.input_field_frame = self._create_path_picker_row(
            self.app.sidebar_frame,
            row=2,
            label_text="INPUT FOLDER",
            variable=self.app.input_folder_path,
            browse_command=self.app.browse_input_folder,
        )
        self.input_entry = self.app.input_entry

        # Row 3: OUTPUT FOLDER
        self.app.output_entry, self.app.output_field_frame = self._create_path_picker_row(
            self.app.sidebar_frame,
            row=3,
            label_text="OUTPUT FOLDER",
            variable=self.app.output_folder_path,
            browse_command=self.app.browse_output_folder,
        )
        self.output_entry = self.app.output_entry

        # Row 4: Section Header — OUTPUT SETTINGS
        self._create_section_header(self.app.sidebar_frame, 4, "OUTPUT SETTINGS")

        # Row 5: QUALITY Slider
        self.app.quality_slider, self.app.quality_input_box = self._create_slider_row(
            self.app.sidebar_frame,
            row=5,
            label_text="QUALITY",
            variable=self.app.quality,
            from_=10,
            to=100,
            command=self._on_quality_changed,
        )
        self.quality_slider = self.app.quality_slider
        self.quality_input_box = self.app.quality_input_box

        # Row 6: FORMAT Dropdown
        self.app.image_type_dropdown = self._create_format_row(
            self.app.sidebar_frame, row=6, label_text="FORMAT"
        )
        self.image_type_dropdown = self.app.image_type_dropdown

        # Row 7: RESIZE % Slider
        self.app.resize_slider, self.app.resize_input_box = self._create_slider_row(
            self.app.sidebar_frame,
            row=7,
            label_text="RESIZE %",
            variable=self.app.resize_percent,
            from_=10,
            to=100,
            command=self._on_resize_changed,
        )
        self.resize_slider = self.app.resize_slider
        self.resize_input_box = self.app.resize_input_box

        # Row 8: RESIZE DPI Entry
        self.app.dpi_entry = self._create_dpi_row(
            self.app.sidebar_frame, row=8, label_text="RESIZE DPI"
        )

        # Row 9: Empty Expanding Row (weight=1 handles spacing)

        # Row 10: Sidebar Bottom Actions (Settings & Help)
        self.app.sidebar_actions = self.ctk.CTkFrame(self.app.sidebar_frame, fg_color="transparent", height=36)
        self.app.sidebar_actions.grid(row=10, column=0, pady=(0, 20), sticky="ew", **p)
        self.app.sidebar_actions.grid_columnconfigure(0, weight=1)
        self.app.sidebar_actions.grid_columnconfigure(1, weight=1)

        self.app.settings_button = self.ctk.CTkButton(
            self.app.sidebar_actions,
            text="⚙ Settings",
            command=self.app.show_settings,
            height=36,
            corner_radius=CORNER_RADIUS,
            font=self.ctk.CTkFont(family=HEAD_FONT, size=12, weight="bold"),
            fg_color="transparent",
            hover_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER_2,
            border_width=BORDER_WIDTH,
            text_color=COLOR_TEXT_3,
        )
        self.app.settings_button.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self.app.help_button = self.ctk.CTkButton(
            self.app.sidebar_actions,
            text="ⓘ Help",
            command=self.app.show_help,
            height=36,
            corner_radius=CORNER_RADIUS,
            font=self.ctk.CTkFont(family=HEAD_FONT, size=12, weight="bold"),
            fg_color="transparent",
            hover_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER_2,
            border_width=BORDER_WIDTH,
            text_color=COLOR_TEXT_3,
        )
        self.app.help_button.grid(row=0, column=1, padx=(4, 0), sticky="ew")

    def _build_brand_logo(self):
        """Builds the logo header using PNG logos (light and dark)."""
        logo_light = path.join(BASE_DIR, "Design", "Logos", "FXbatch.png")
        logo_dark = path.join(BASE_DIR, "Design", "Logos", "FXbatch_rev.png")
        if not path.exists(logo_light):
            logo_light = path.join(BASE_DIR, "icons", "fx.png")
            logo_dark = path.join(BASE_DIR, "icons", "fx_rev.png")

        if path.exists(logo_light) and path.exists(logo_dark):
            try:
                img_light = Image.open(logo_light)
                img_dark = Image.open(logo_dark)
                self.app.logo_image = self.ctk.CTkImage(light_image=img_light, dark_image=img_dark, size=(140, 26))
                self.app.logo_label = self.ctk.CTkLabel(self.app.brand_frame, image=self.app.logo_image, text="")
                self.app.logo_label.pack(anchor="w")
            except Exception:
                self._build_fallback_brand_text()
        else:
            self._build_fallback_brand_text()

        self.app.brand_sub = self.ctk.CTkLabel(
            self.app.brand_frame,
            text="BATCH IMAGE RESIZER 2.0.0",
            font=self.ctk.CTkFont(family=HEAD_FONT, size=10, weight="bold"),
            text_color=COLOR_MUTED,
        )
        self.app.brand_sub.pack(anchor="w", pady=(2, 0))

    def _build_fallback_brand_text(self):
        row = self.ctk.CTkFrame(self.app.brand_frame, fg_color="transparent")
        row.pack(anchor="w")
        self.ctk.CTkLabel(
            row, text="FX", font=self.ctk.CTkFont(family=HEAD_FONT, size=24, weight="bold"), text_color=COLOR_BRAND
        ).pack(side="left")
        self.ctk.CTkLabel(
            row, text="batch", font=self.ctk.CTkFont(family=HEAD_FONT, size=24, weight="bold"), text_color=COLOR_TEXT
        ).pack(side="left")

    def _create_section_header(self, parent, row: int, title: str):
        frame = self.ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=0, padx=20, pady=(10, 8), sticky="ew")
        frame.grid_columnconfigure(0, weight=1)

        label = self.ctk.CTkLabel(
            frame,
            text=title,
            font=self.ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_MUTED,
            anchor="w",
        )
        label.grid(row=0, column=0, sticky="w", pady=(0, 6))

        div = ThemeDivider(frame, height=1)
        div.grid(row=1, column=0, sticky="ew")

    def _create_path_picker_row(self, parent, row: int, label_text: str, variable: ctk.StringVar, browse_command):
        frame = self.ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=0, padx=20, pady=(0, 10), sticky="ew")
        frame.grid_columnconfigure(0, weight=1)

        label = self.ctk.CTkLabel(
            frame,
            text=label_text,
            font=self.ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_MUTED,
            anchor="w",
        )
        label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))

        row_frame = self.ctk.CTkFrame(frame, fg_color="transparent", height=36)
        row_frame.grid(row=1, column=0, sticky="ew")
        row_frame.grid_columnconfigure(0, weight=1)
        row_frame.grid_columnconfigure(1, weight=0)

        field_container = self.ctk.CTkFrame(
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

        folder_icon = self.ctk.CTkLabel(
            field_container,
            text="📁",
            font=self.ctk.CTkFont(size=12),
            text_color=COLOR_MUTED,
            width=26,
        )
        folder_icon.grid(row=0, column=0, padx=(8, 2), pady=4)

        entry = self.ctk.CTkEntry(
            field_container,
            textvariable=variable,
            font=self.ctk.CTkFont(family=MONO_FONT, size=11),
            fg_color="transparent",
            border_width=0,
            text_color=COLOR_TEXT_3,
        )
        entry.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=4)

        browse_btn = self.ctk.CTkButton(
            row_frame,
            text="Browse",
            command=browse_command,
            width=72,
            height=36,
            corner_radius=CORNER_RADIUS,
            font=self.ctk.CTkFont(family=HEAD_FONT, size=12, weight="bold"),
            fg_color="transparent",
            hover_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER_2,
            border_width=BORDER_WIDTH,
            text_color=COLOR_TEXT,
        )
        browse_btn.grid(row=0, column=1, sticky="e")

        return entry, field_container

    def _create_slider_row(self, parent, row: int, label_text: str, variable: ctk.IntVar, from_: int, to: int, command):
        frame = self.ctk.CTkFrame(parent, fg_color="transparent", height=28)
        frame.grid(row=row, column=0, padx=20, pady=4, sticky="ew")
        frame.grid_columnconfigure(1, weight=1)

        label = self.ctk.CTkLabel(
            frame,
            text=label_text,
            width=70,
            font=self.ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_TEXT_3,
            anchor="w",
        )
        label.grid(row=0, column=0, sticky="w")

        slider = self.ctk.CTkSlider(
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

        input_var = self.ctk.StringVar(value=str(variable.get()))
        input_box = self.ctk.CTkEntry(
            frame,
            textvariable=input_var,
            width=42,
            height=24,
            corner_radius=CORNER_RADIUS,
            font=self.ctk.CTkFont(family=MONO_FONT, size=11),
            fg_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            text_color=COLOR_TEXT,
            justify="center",
            validate="key",
            validatecommand=(frame.register(self.validate_slider_input), "%P"),
        )
        input_box.grid(row=0, column=2, sticky="e")
        input_box.input_var = input_var
        if "quality" in label_text.lower():
            self.quality_input_var = input_var
            self.app.quality_input_var = input_var
        elif "resize" in label_text.lower():
            self.resize_input_var = input_var
            self.app.resize_input_var = input_var

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
        frame = self.ctk.CTkFrame(parent, fg_color="transparent", height=32)
        frame.grid(row=row, column=0, padx=20, pady=4, sticky="ew")
        frame.grid_columnconfigure(1, weight=1)

        label = self.ctk.CTkLabel(
            frame,
            text=label_text,
            width=70,
            font=self.ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_TEXT_3,
            anchor="w",
        )
        label.grid(row=0, column=0, sticky="w")

        opt_menu = self.ctk.CTkOptionMenu(
            frame,
            variable=self.app.selected_image_type,
            values=[f".{fmt}" for fmt in self.app.image_types],
            command=self._on_format_changed,
            height=30,
            corner_radius=CORNER_RADIUS,
            font=self.ctk.CTkFont(family=MONO_FONT, size=11),
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
        frame = self.ctk.CTkFrame(parent, fg_color="transparent", height=32)
        frame.grid(row=row, column=0, padx=20, pady=4, sticky="ew")
        frame.grid_columnconfigure(1, weight=1)

        label = self.ctk.CTkLabel(
            frame,
            text=label_text,
            width=70,
            font=self.ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_TEXT_3,
            anchor="w",
        )
        label.grid(row=0, column=0, sticky="w")

        dpi_entry = self.ctk.CTkEntry(
            frame,
            textvariable=self.app.image_dpi,
            width=56,
            height=30,
            corner_radius=CORNER_RADIUS,
            font=self.ctk.CTkFont(family=MONO_FONT, size=11),
            fg_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            text_color=COLOR_TEXT,
            validate="key",
            validatecommand=(self.app.register(self.app.validate_dpi), "%P"),
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

        dpi_entry.bind("<FocusOut>", self.app.on_dpi_focusout)
        dpi_entry.bind("<Return>", self.app.on_dpi_focusout)
        return dpi_entry

    # -----------------------------------------------------------------------
    # 2. Analysis Area (Expanding Right Panel)
    # -----------------------------------------------------------------------
    def _build_analysis_area(self):
        self.app.analysis_frame = self.ctk.CTkFrame(
            self.app.main_body, fg_color=COLOR_BG, corner_radius=0
        )
        self.app.analysis_frame.grid(row=0, column=2, sticky="nsew", padx=20, pady=20)
        self.app.analysis_frame.grid_columnconfigure(0, weight=1)
        self.app.analysis_frame.grid_rowconfigure(1, weight=1)

        # Row 0: Analysis Header (Height: 40px)
        self._build_analysis_header()

        # Row 1: Preview Card (Expanding weight=1, height ~329px)
        self._build_preview_card()

        # Row 2: Metrics Strip (Height: 80px, 5 cards)
        self._build_metrics_strip()

        # Row 3: Activity Log Card (Height: 132px)
        self._build_activity_log()

    def _build_analysis_header(self):
        self.app.header_frame = self.ctk.CTkFrame(self.app.analysis_frame, height=40, fg_color="transparent")
        self.app.header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        self.app.header_frame.grid_columnconfigure(1, weight=1)

        # Title Block
        title_block = self.ctk.CTkFrame(self.app.header_frame, fg_color="transparent")
        title_block.grid(row=0, column=0, sticky="w")

        self.app.analysis_eyebrow = self.ctk.CTkLabel(
            title_block,
            text="SAMPLE ANALYSIS",
            font=self.ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_MUTED,
            anchor="w",
        )
        self.app.analysis_eyebrow.pack(anchor="w")

        self.app.sample_filename_label = self.ctk.CTkLabel(
            title_block,
            text="No sample image",
            font=self.ctk.CTkFont(family=BODY_FONT, size=13, weight="bold"),
            text_color=COLOR_MUTED,
            anchor="w",
        )
        self.app.sample_filename_label.pack(anchor="w")

        # Controls Block (Status Pill + Resample Button)
        controls_block = self.ctk.CTkFrame(self.app.header_frame, fg_color="transparent")
        controls_block.grid(row=0, column=2, sticky="e")

        # Status Pill Badge
        self.app.status_pill = self.ctk.CTkFrame(
            controls_block,
            height=26,
            corner_radius=CORNER_RADIUS,
            fg_color=COLOR_SURFACE_2,
            cursor="hand2",
        )
        self.app.status_pill.pack(side="left", padx=(0, 10))
        self.app.status_pill.bind("<Button-1>", lambda e: self.app.browse_input_folder())

        self.app.status_pill_label = self.ctk.CTkLabel(
            self.app.status_pill,
            text="• AWAITING FOLDER",
            font=self.ctk.CTkFont(family=HEAD_FONT, size=10, weight="bold"),
            text_color=COLOR_MUTED,
            padx=10,
            pady=4,
            cursor="hand2",
        )
        self.app.status_pill_label.pack()
        self.app.status_pill_label.bind("<Button-1>", lambda e: self.app.browse_input_folder())

        # Resample Preview Button
        self.app.resample_button = self.ctk.CTkButton(
            controls_block,
            text="↻ Resample Preview",
            command=self.app.pick_random_image,
            height=34,
            corner_radius=CORNER_RADIUS,
            font=self.ctk.CTkFont(family=HEAD_FONT, size=12, weight="bold"),
            fg_color="transparent",
            hover_color=COLOR_SURFACE,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            text_color=COLOR_MUTED,
            state="disabled",
        )
        self.app.resample_button.pack(side="left")

    def _build_preview_card(self):
        self.app.preview_card = self.ctk.CTkFrame(
            self.app.analysis_frame,
            fg_color=COLOR_SURFACE,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            corner_radius=CORNER_RADIUS,
        )
        self.app.preview_card.grid(row=1, column=0, sticky="nsew", pady=(0, 16))
        self.app.preview_card.grid_rowconfigure(2, weight=1)
        self.app.preview_card.grid_columnconfigure(0, weight=1)

        # Card Header (Height: 34px)
        header = self.ctk.CTkFrame(self.app.preview_card, height=34, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14)
        header.grid_propagate(False)
        header.grid_columnconfigure(1, weight=1)

        lbl = self.ctk.CTkLabel(
            header,
            text="SAMPLE PREVIEW",
            font=self.ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_MUTED,
        )
        lbl.grid(row=0, column=0, sticky="w", pady=8)

        self.app.preview_dims_label = self.ctk.CTkLabel(
            header,
            text="no sample loaded",
            font=self.ctk.CTkFont(family=MONO_FONT, size=11),
            text_color=COLOR_MUTED,
        )
        self.app.preview_dims_label.grid(row=0, column=2, sticky="e", pady=8)

        # Header 1px Divider
        div = ThemeDivider(self.app.preview_card, height=1)
        div.grid(row=1, column=0, sticky="ew")

        # Preview Container Frame
        self.app.image_preview_frame = self.ctk.CTkFrame(
            self.app.preview_card, fg_color=COLOR_SURFACE_2, corner_radius=0
        )
        self.app.image_preview_frame.grid(row=2, column=0, sticky="nsew")
        self.app.image_preview_frame.grid_rowconfigure(0, weight=1)
        self.app.image_preview_frame.grid_columnconfigure(0, weight=1)

        # 1) Empty State Dropzone Widget (Click to browse folder)
        self.app.dropzone_frame = self.ctk.CTkFrame(self.app.image_preview_frame, fg_color="transparent", cursor="hand2")
        self.app.dropzone_frame.grid(row=0, column=0, sticky="nsew")
        self.app.dropzone_frame.grid_rowconfigure(0, weight=1)
        self.app.dropzone_frame.grid_columnconfigure(0, weight=1)
        self.app.dropzone_frame.bind("<Button-1>", lambda e: self.app.browse_input_folder())

        inner_drop = self.ctk.CTkFrame(self.app.dropzone_frame, fg_color="transparent", cursor="hand2")
        inner_drop.place(relx=0.5, rely=0.5, anchor="center")
        inner_drop.bind("<Button-1>", lambda e: self.app.browse_input_folder())

        icon_lbl = self.ctk.CTkLabel(
            inner_drop,
            text="🖼",
            font=self.ctk.CTkFont(size=32),
            text_color=COLOR_BORDER_2,
            cursor="hand2",
        )
        icon_lbl.pack(pady=(0, 8))
        icon_lbl.bind("<Button-1>", lambda e: self.app.browse_input_folder())

        drop_title = self.ctk.CTkLabel(
            inner_drop,
            text="Drop Folder Here",
            font=self.ctk.CTkFont(family=BODY_FONT, size=14, weight="bold"),
            text_color=COLOR_TEXT,
            cursor="hand2",
        )
        drop_title.pack()
        drop_title.bind("<Button-1>", lambda e: self.app.browse_input_folder())

        drop_sub = self.ctk.CTkLabel(
            inner_drop,
            text="or Click Browse to select a folder",
            font=self.ctk.CTkFont(family=BODY_FONT, size=12),
            text_color=COLOR_MUTED,
            cursor="hand2",
        )
        drop_sub.pack(pady=(4, 0))
        drop_sub.bind("<Button-1>", lambda e: self.app.browse_input_folder())

        # 2) Filled State Image Display Widget
        self.app.image_preview = self.ctk.CTkLabel(
            self.app.image_preview_frame,
            text="",
            image=None,
        )

    def _build_metrics_strip(self):
        self.app.metrics_container = self.ctk.CTkFrame(
            self.app.analysis_frame, height=80, fg_color="transparent"
        )
        self.app.metrics_container.grid(row=2, column=0, sticky="ew", pady=(0, 16))
        for c in range(5):
            self.app.metrics_container.grid_columnconfigure(c, weight=1)

        cards_spec = [
            ("ORIGINAL", "—", ""),
            ("OUTPUT", "—", ""),
            ("NEW SIZE", "—", ""),
            ("REDUCTION", "—", ""),
            ("SAMPLE DPI", "—", ""),
        ]

        self.app.metric_cards = {}
        for idx, (title, val, sub) in enumerate(cards_spec):
            card = self.ctk.CTkFrame(
                self.app.metrics_container,
                height=80,
                fg_color=COLOR_SURFACE,
                border_color=COLOR_BORDER,
                border_width=BORDER_WIDTH,
                corner_radius=CORNER_RADIUS,
            )
            card.grid(row=0, column=idx, padx=(0 if idx == 0 else 6, 0 if idx == 4 else 6), sticky="ew")
            card.grid_propagate(False)

            lbl = self.ctk.CTkLabel(
                card,
                text=title,
                font=self.ctk.CTkFont(family=HEAD_FONT, size=10, weight="bold"),
                text_color=COLOR_MUTED,
                anchor="w",
            )
            lbl.pack(anchor="w", padx=13, pady=(10, 2))

            v_lbl = self.ctk.CTkLabel(
                card,
                text=val,
                font=self.ctk.CTkFont(family=MONO_FONT, size=13, weight="bold"),
                text_color=COLOR_MUTED,
                anchor="w",
            )
            v_lbl.pack(anchor="w", padx=13)

            s_lbl = self.ctk.CTkLabel(
                card,
                text=sub,
                font=self.ctk.CTkFont(family=MONO_FONT, size=10),
                text_color=COLOR_MUTED,
                anchor="w",
            )
            s_lbl.pack(anchor="w", padx=13, pady=(2, 0))

            self.app.metric_cards[title] = (card, v_lbl, s_lbl)

    def _build_activity_log(self):
        self.app.log_card = self.ctk.CTkFrame(
            self.app.analysis_frame,
            height=172,
            fg_color=COLOR_SURFACE,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            corner_radius=CORNER_RADIUS,
        )
        self.app.log_card.grid(row=3, column=0, sticky="ew")
        self.app.log_card.grid_propagate(False)
        self.app.log_card.grid_rowconfigure(1, weight=1)
        self.app.log_card.grid_columnconfigure(0, weight=1)

        eyebrow = self.ctk.CTkLabel(
            self.app.log_card,
            text="ACTIVITY LOG",
            font=self.ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_MUTED,
            anchor="w",
        )
        eyebrow.grid(row=0, column=0, sticky="w", padx=14, pady=(10, 4))

        self.app.log_text = self.ctk.CTkTextbox(
            self.app.log_card,
            font=self.ctk.CTkFont(family=MONO_FONT, size=11),
            fg_color="transparent",
            text_color=COLOR_TEXT_3,
            wrap="word",
            border_width=0,
            activate_scrollbars=True,
        )
        self.app.log_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

    # -----------------------------------------------------------------------
    # 3. Action Bar (Height: 72px)
    # -----------------------------------------------------------------------
    def _build_action_bar(self):
        self.app.action_bar = self.ctk.CTkFrame(self.app, height=72, fg_color=COLOR_SURFACE, corner_radius=0)
        self.app.action_bar.grid(row=2, column=0, sticky="ew")
        self.app.action_bar.grid_propagate(False)
        self.app.action_bar.grid_rowconfigure(0, weight=1)
        self.app.action_bar.grid_columnconfigure(1, weight=0)
        self.app.action_bar.grid_columnconfigure(2, weight=1)  # Expanding spacer

        # Left: Theme Switcher [ LIGHT | DARK ]
        self.app.theme_switch_frame = self.ctk.CTkFrame(
            self.app.action_bar,
            width=118,
            height=28,
            fg_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            corner_radius=CORNER_RADIUS,
        )
        self.app.theme_switch_frame.grid(row=0, column=0, padx=(20, 16), sticky="w")
        self.app.theme_switch_frame.grid_propagate(False)
        self.app.theme_switch_frame.grid_rowconfigure(0, weight=1)
        self.app.theme_switch_frame.grid_columnconfigure((0, 1), weight=1)

        self.app.btn_light = self.ctk.CTkButton(
            self.app.theme_switch_frame,
            text="LIGHT",
            corner_radius=CORNER_RADIUS,
            font=self.ctk.CTkFont(family=HEAD_FONT, size=10, weight="bold"),
            fg_color="transparent",
            hover_color=COLOR_SURFACE,
            text_color=COLOR_MUTED,
            command=lambda: self.app.set_theme("Light"),
        )
        self.app.btn_light.grid(row=0, column=0, padx=(2, 1), pady=2, sticky="nsew")

        self.app.btn_dark = self.ctk.CTkButton(
            self.app.theme_switch_frame,
            text="DARK",
            corner_radius=CORNER_RADIUS,
            font=self.ctk.CTkFont(family=HEAD_FONT, size=10, weight="bold"),
            fg_color=COLOR_BRAND,
            hover_color=COLOR_BRAND_HOVER,
            text_color=COLOR_ON_BRAND,
            command=lambda: self.app.set_theme("Dark"),
        )
        self.app.btn_dark.grid(row=0, column=1, padx=(1, 2), pady=2, sticky="nsew")

        # Center: Telemetry Status Summary & Dot
        self.app.summary_frame = self.ctk.CTkFrame(self.app.action_bar, fg_color="transparent")
        self.app.summary_frame.grid(row=0, column=1, sticky="w")

        self.app.status_dot = self.ctk.CTkLabel(
            self.app.summary_frame,
            text="●",
            font=self.ctk.CTkFont(size=9),
            text_color=COLOR_MUTED,
        )
        self.app.status_dot.pack(side="left", padx=(0, 6))

        self.app.status_summary_label = self.ctk.CTkLabel(
            self.app.summary_frame,
            text="Waiting for folder  ·  JPG · quality 60 · resize 40% · 72 DPI",
            font=self.ctk.CTkFont(family=BODY_FONT, size=12),
            text_color=COLOR_TEXT_3,
        )
        self.app.status_summary_label.pack(side="left")

        # Hidden Progress bar frame (gridded when processing)
        self.app.progress_frame = self.ctk.CTkFrame(self.app.action_bar, fg_color="transparent")
        self.app.progress_frame.grid_columnconfigure(0, weight=1)
        self.app.progress_frame.grid_columnconfigure(1, weight=0)

        self.app.progress_bar = self.ctk.CTkProgressBar(
            self.app.progress_frame,
            height=14,
            corner_radius=CORNER_RADIUS,
            fg_color=COLOR_BORDER,
            progress_color=COLOR_BRAND,
        )
        self.app.progress_bar.grid(row=0, column=0, padx=(0, 12), sticky="ew")
        self.app.progress_bar.set(0)

        self.app.cancel_button = self.ctk.CTkButton(
            self.app.progress_frame,
            text="Cancel",
            command=self.app.cancel_processing,
            width=70,
            height=28,
            corner_radius=CORNER_RADIUS,
            font=self.ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            fg_color=COLOR_BRAND,
            hover_color=COLOR_BRAND_HOVER,
            text_color=COLOR_ON_BRAND,
        )
        self.app.cancel_button.grid(row=0, column=1, sticky="e")

        # Right: Batch Convert CTA Button
        self.app.process_button = self.ctk.CTkButton(
            self.app.action_bar,
            text="▷ Batch Convert Images",
            command=self.app.process_images,
            width=200,
            height=44,
            corner_radius=CORNER_RADIUS,
            font=self.ctk.CTkFont(family=HEAD_FONT, size=12, weight="bold"),
            fg_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            hover_color=COLOR_BORDER_2,
            text_color=COLOR_MUTED,
            state="disabled",
        )
        self.app.process_button.grid(row=0, column=3, padx=20, sticky="e")

    # -----------------------------------------------------------------------
    # Interactive Slider & Input Event Callbacks
    # -----------------------------------------------------------------------
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
        self.delayed_update()

    def _on_quality_changed(self, value):
        val = int(float(value))
        self.app.quality.set(val)
        self.delayed_update()

    def _on_resize_changed(self, value):
        val = int(float(value))
        self.app.resize_percent.set(val)
        self.delayed_update()

    def _on_format_changed(self, value):
        self.on_image_type_changed(value, trigger_update=True)

    def on_image_type_changed(self, selected_type: str, trigger_update: bool = True):
        clean_type = str(selected_type).strip().replace(".", "").upper()
        is_png = clean_type == "PNG"
        state = "disabled" if is_png else "normal"
        if self.quality_slider:
            self.quality_slider.configure(state=state)
        if self.quality_input_box:
            self.quality_input_box.configure(state=state)
        if trigger_update:
            self.delayed_update()

    def delayed_update(self, *args):
        if self.update_timer is not None:
            self.app.after_cancel(self.update_timer)
        self.update_timer = self.app.after(350, self.app.update_sample_image_info)
