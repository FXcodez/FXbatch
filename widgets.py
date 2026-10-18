# widgets.py — FXbatch v2.5.0 Widget Construction & Layout Engine
# Exact typography, text sizes, and padding restored from v2.0.
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

HEAD_FONT = "Oswald"
BODY_FONT = "Roboto"
MONO_FONT = "Roboto Mono"

# ---------------------------------------------------------------------------
# DESIGN SYSTEM COLOR TOKENS (Light, Dark)
# ---------------------------------------------------------------------------
COLOR_BG = ("#F6F6F7", "#1A1A1A")          # Main background
COLOR_SURFACE = ("#FFFFFF", "#2D2D2D")     # Cards, sidebar, action bar
COLOR_SURFACE_2 = ("#F1F1F3", "#242424")   # Insets, dropzone, inactive controls
COLOR_BORDER = ("#E3E3E7", "#3D3D3D")      # Subtle outlines & 1px dividers
COLOR_BORDER_2 = ("#CDCDD3", "#4A4A4A")    # Interactive outlines (buttons, entries)
COLOR_TEXT = ("#16161A", "#F2F2F2")        # Primary text & values
COLOR_TEXT_3 = ("#3C3C43", "#C9C9C9")      # Secondary labels, paths, log text
COLOR_MUTED = ("#7C7C83", "#8E8E93")       # Placeholders, units, inactive icons
COLOR_BRAND = ("#AA182C", "#AA182C")       # Brand red accent & CTA
COLOR_BRAND_HOVER = ("#8B1324", "#C41F36") # Interactive hover for brand CTA
COLOR_ON_BRAND = ("#FFFFFF", "#F2F2F2")    # Text/icons over brand
COLOR_THUMB = ("#16161A", "#F2F2F2")       # Slider thumb knob
COLOR_SUCCESS = ("#1E824C", "#35B36E")     # Reduction & status green
COLOR_SUCCESS_BG = ("#E3F5EA", "#12301F")  # Pill badge background
COLOR_WARNING = ("#C27D00", "#FFB020")     # Warning amber
COLOR_WARNING_BG = ("#FFF4E5", "#332200")  # Warning amber background

CORNER_RADIUS = 2
BORDER_WIDTH = 1


# ---------------------------------------------------------------------------
# TRUE 1-PIXEL HARDWARE DIVIDER (Theme-Aware with Memory Leak Fix)
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

    def destroy(self):
        """Unregister listener from static Tracker list to prevent memory leaks."""
        try:
            ctk.AppearanceModeTracker.remove(self._on_theme_change)
        except Exception:
            pass
        super().destroy()


# ---------------------------------------------------------------------------
# CIRCULAR ICON BUTTON (Pixel-perfect centering for icon-only circular buttons)
# ---------------------------------------------------------------------------
class CircularIconButton(ctk.CTkButton):
    """Circular icon-only button with pixel-perfect icon centering and no text offset."""
    def __init__(self, master=None, size: int = 36, **kwargs):
        super().__init__(
            master=master,
            text="",
            width=size,
            height=size,
            corner_radius=size // 2,
            **kwargs,
        )
        self._center_icon()

    def _center_icon(self):
        if hasattr(self, "_image_label") and self._image_label is not None:
            self._image_label.grid(row=2, column=0, columnspan=5, sticky="")
        self.grid_columnconfigure(0, weight=1, minsize=0)
        self.grid_columnconfigure(4, weight=1, minsize=0)

    def _create_grid(self):
        super()._create_grid()
        self._center_icon()

    def configure(self, **kwargs):
        super().configure(**kwargs)
        self._center_icon()


# ---------------------------------------------------------------------------
# HOVER TOOLTIP (Theme-Aware Singleton with Polling & Boundary Clamping)
# ---------------------------------------------------------------------------
class CTkTooltip:
    """A polished, theme-adaptive hover tooltip for CustomTkinter & Tkinter widgets.

    Features:
    - Global singleton enforcement: Only one tooltip can exist on screen at any time.
    - Continuous boundary polling (every 60ms) ensures instant dismissal when the cursor exits.
    - Dismisses automatically if the mouse enters the tooltip window itself or is clicked.
    - Screen edge boundary clamping to prevent clipping off viewport edges.
    - Theme-adaptive color scheme with signature brand-crimson border (#AA182C).
    """

    _active_tooltip: CTkTooltip | None = None

    def __init__(
        self,
        widget: tk.Widget | ctk.CTkBaseClass,
        text: str,
        delay_ms: int = 250,
        fg_color: tuple[str, str] = ("#FFFFFF", "#202124"),
        text_color: tuple[str, str] = ("#16161A", "#F2F2F2"),
        border_color: tuple[str, str] = (COLOR_BRAND[0], COLOR_BRAND[1]),
        font: tuple[str, int] = (BODY_FONT, 10),
    ):
        self.widget = widget
        self.text = text.strip()
        self.delay_ms = delay_ms
        self.fg_color = fg_color
        self.text_color = text_color
        self.border_color = border_color
        self.font = font

        self.tip_window: tk.Toplevel | None = None
        self._timer_id: str | None = None
        self._poll_id: str | None = None

        self._bind_events(self.widget)

    @classmethod
    def hide_active(cls):
        """Dismiss whichever tooltip is currently displayed anywhere in the application."""
        if cls._active_tooltip is not None:
            cls._active_tooltip.hide()

    def _bind_events(self, w):
        try:
            w.bind("<Enter>", self._on_enter, add="+")
            w.bind("<Leave>", self._on_leave, add="+")
            w.bind("<ButtonPress>", self._on_click, add="+")
            w.bind("<Destroy>", self._on_destroy, add="+")
        except Exception:
            pass

        # Inspect internal CTk subwidgets
        for attr in ("_entry", "_canvas", "_text_label", "_label", "_textbox", "_dropdown_menu"):
            sub = getattr(w, attr, None)
            if sub and isinstance(sub, tk.Widget):
                try:
                    sub.bind("<Enter>", self._on_enter, add="+")
                    sub.bind("<Leave>", self._on_leave, add="+")
                    sub.bind("<ButtonPress>", self._on_click, add="+")
                except Exception:
                    pass

        try:
            for child in w.winfo_children():
                try:
                    child.bind("<Enter>", self._on_enter, add="+")
                    child.bind("<Leave>", self._on_leave, add="+")
                    child.bind("<ButtonPress>", self._on_click, add="+")
                except Exception:
                    pass
        except Exception:
            pass

    def _on_enter(self, event=None):
        self._cancel_timer()
        # Ensure any other tooltip closes immediately
        if CTkTooltip._active_tooltip and CTkTooltip._active_tooltip != self:
            CTkTooltip._active_tooltip.hide()
        if self.tip_window is None and self.widget.winfo_exists():
            self._timer_id = self.widget.after(self.delay_ms, self.show)

    def _on_leave(self, event=None):
        self._cancel_timer()
        if self.tip_window and self.widget.winfo_exists():
            self.widget.after(30, self._verify_leave)

    def _verify_leave(self):
        if not self.tip_window or not self.widget.winfo_exists():
            return
        try:
            rx = self.widget.winfo_rootx()
            ry = self.widget.winfo_rooty()
            rw = self.widget.winfo_width()
            rh = self.widget.winfo_height()
            px = self.widget.winfo_pointerx()
            py = self.widget.winfo_pointery()
            if px < rx or px > rx + rw or py < ry or py > ry + rh:
                self.hide()
        except Exception:
            self.hide()

    def _on_click(self, event=None):
        self._cancel_timer()
        self.hide()

    def _on_destroy(self, event=None):
        self._cancel_timer()
        self.hide()

    def _cancel_timer(self):
        if self._timer_id:
            try:
                self.widget.after_cancel(self._timer_id)
            except Exception:
                pass
            self._timer_id = None

    def _cancel_poll(self):
        if self._poll_id:
            try:
                self.widget.after_cancel(self._poll_id)
            except Exception:
                pass
            self._poll_id = None

    def show(self):
        if not self.widget.winfo_exists():
            return

        # Close any active tooltip first
        if CTkTooltip._active_tooltip and CTkTooltip._active_tooltip != self:
            CTkTooltip._active_tooltip.hide()

        # Check if cursor is still actually within the widget boundary
        try:
            rx = self.widget.winfo_rootx()
            ry = self.widget.winfo_rooty()
            rw = self.widget.winfo_width()
            rh = self.widget.winfo_height()
            px = self.widget.winfo_pointerx()
            py = self.widget.winfo_pointery()
            if px < rx or px > rx + rw or py < ry or py > ry + rh:
                return
        except Exception:
            return

        CTkTooltip._active_tooltip = self

        is_dark = ctk.get_appearance_mode().lower() == "dark"
        bg = self.fg_color[1] if is_dark else self.fg_color[0]
        fg = self.text_color[1] if is_dark else self.text_color[0]
        border = self.border_color[1] if is_dark else self.border_color[0]

        # Calculate positioning near cursor with safe offset so cursor is never inside tw
        try:
            x = self.widget.winfo_pointerx() + 14
            y = self.widget.winfo_pointery() + 18
        except Exception:
            x = self.widget.winfo_rootx() + 20
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_attributes("-topmost", True)

        # If cursor enters the tooltip window itself, dismiss it immediately
        tw.bind("<Enter>", lambda e: self.hide())
        tw.bind("<ButtonPress>", lambda e: self.hide())

        frame = tk.Frame(
            tw,
            bg=bg,
            highlightbackground=border,
            highlightcolor=border,
            highlightthickness=1,
            bd=0,
            padx=10,
            pady=8,
        )
        frame.pack()
        frame.bind("<Enter>", lambda e: self.hide())

        lbl = tk.Label(
            frame,
            text=self.text,
            justify="left",
            bg=bg,
            fg=fg,
            font=self.font,
            wraplength=380,
        )
        lbl.pack()
        lbl.bind("<Enter>", lambda e: self.hide())

        tw.update_idletasks()
        w_w = tw.winfo_width()
        w_h = tw.winfo_height()
        screen_w = tw.winfo_screenwidth()
        screen_h = tw.winfo_screenheight()

        if x + w_w > screen_w - 10:
            x = max(10, screen_w - w_w - 10)
        if y + w_h > screen_h - 10:
            y = max(10, self.widget.winfo_pointery() - w_h - 10)

        tw.wm_geometry(f"+{x}+{y}")

        # Start continuous poll loop to dismiss as soon as cursor leaves widget
        self._poll_loop()

    def _poll_loop(self):
        if not self.tip_window or not self.widget.winfo_exists():
            self._cancel_poll()
            return
        try:
            rx = self.widget.winfo_rootx()
            ry = self.widget.winfo_rooty()
            rw = self.widget.winfo_width()
            rh = self.widget.winfo_height()
            px = self.widget.winfo_pointerx()
            py = self.widget.winfo_pointery()
            if px < rx or px > rx + rw or py < ry or py > ry + rh:
                self.hide()
                return
        except Exception:
            self.hide()
            return
        self._poll_id = self.widget.after(60, self._poll_loop)

    def hide(self):
        self._cancel_timer()
        self._cancel_poll()
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None
        if CTkTooltip._active_tooltip == self:
            CTkTooltip._active_tooltip = None

    def destroy(self):
        self.hide()


# ---------------------------------------------------------------------------
# WIDGET CREATOR
# ---------------------------------------------------------------------------
class WidgetCreator:
    def __init__(self, app, ctk_module):
        self.app = app
        self.ctk = ctk_module
        self.update_timer = None

        # Widget references
        self.input_entry = None
        self.output_entry = None
        self.quality_slider = None
        self.quality_input_box = None
        self.resize_slider = None
        self.resize_input_box = None
        self.image_type_dropdown = None
        self.resize_mode_dropdown = None

        # Dynamic Sizing Rows
        self.sizing_percent_frame = None
        self.sizing_bbox_frame = None
        self.sizing_width_frame = None
        self.sizing_height_frame = None
        self.sizing_ico_frame = None

    def create_widgets(self):
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

        # Initial layout sync
        self.on_image_type_changed(self.app.selected_image_type.get(), trigger_update=False)
        self.on_resize_mode_changed(self.app.selected_resize_mode.get(), trigger_update=False)

        return self.app.main_body

    # -----------------------------------------------------------------------
    # 1. Configuration Sidebar (Width: 330px, matching v2.0)
    # -----------------------------------------------------------------------
    def _build_sidebar(self):
        self.app.sidebar_frame = self.ctk.CTkFrame(
            self.app.main_body, width=330, fg_color=COLOR_SURFACE, corner_radius=0
        )
        self.app.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.app.sidebar_frame.grid_propagate(False)
        self.app.sidebar_frame.grid_columnconfigure(0, weight=1)
        self.app.sidebar_frame.grid_rowconfigure(12, weight=1)

        p = {"padx": 20}

        # Row 0: Brand Header (Exact v2.0 top-left logo file, not the icon)
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

        # Row 5: FORMAT Dropdown (.JPG, .PNG, .WEBP, .AVIF, .ICO)
        self.app.image_type_dropdown = self._create_format_row(
            self.app.sidebar_frame, row=5, label_text="FORMAT"
        )
        self.image_type_dropdown = self.app.image_type_dropdown

        # Row 6: RESIZE MODE Dropdown
        self.app.resize_mode_dropdown = self._create_resize_mode_row(
            self.app.sidebar_frame, row=6, label_text="RESIZE MODE"
        )
        self.resize_mode_dropdown = self.app.resize_mode_dropdown

        # Row 7: DYNAMIC SIZING CONTROLS CONTAINER
        self._build_dynamic_sizing_container(self.app.sidebar_frame, row=7)

        # Row 8: QUALITY Slider (10 - 100)
        self.app.quality_slider, self.app.quality_input_box, self.app.quality_row_frame = self._create_slider_row(
            self.app.sidebar_frame,
            row=8,
            label_text="QUALITY",
            variable=self.app.quality,
            from_=10,
            to=100,
            command=self._on_quality_changed,
        )
        self.quality_slider = self.app.quality_slider
        self.quality_input_box = self.app.quality_input_box

        # Row 9: RESIZE DPI
        self.app.dpi_entry = self._create_dpi_row(
            self.app.sidebar_frame, row=9, label_text="RESIZE DPI"
        )

        # Row 10: RESAMPLING FILTER
        self.app.filter_dropdown = self._create_filter_row(
            self.app.sidebar_frame, row=10, label_text="FILTER"
        )

        # Row 11: Reset Settings Button (Below filter section)
        self.app.reset_settings_btn = self.ctk.CTkButton(
            self.app.sidebar_frame,
            text="↺ Reset Settings",
            command=self.app.reset_to_default_settings,
            height=30,
            corner_radius=CORNER_RADIUS,
            font=self.ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            fg_color="transparent",
            hover_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER_2,
            border_width=BORDER_WIDTH,
            text_color=COLOR_TEXT_3,
        )
        self.app.reset_settings_btn.grid(row=11, column=0, padx=20, pady=(10, 4), sticky="ew")

        # Row 12: Empty Expanding Row (weight=1 handles spacing)

        # Row 13: Sidebar Bottom Actions (Settings & Help)
        self.app.sidebar_actions = self.ctk.CTkFrame(self.app.sidebar_frame, fg_color="transparent", height=36)
        self.app.sidebar_actions.grid(row=13, column=0, pady=(0, 20), sticky="ew", **p)
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
        """Exact v2.0 brand lockup using the FXbatch logo files, NOT the app icon."""
        logo_light = path.join(BASE_DIR, "Design", "Logos", "FXbatch.png")
        logo_dark = path.join(BASE_DIR, "Design", "Logos", "FXbatch_rev.png")
        if not path.exists(logo_light):
            logo_light = path.join(BASE_DIR, "icons", "FXbatch.png")
            logo_dark = path.join(BASE_DIR, "icons", "FXbatch_rev.png")

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
            text="BATCH IMAGE RESIZER 2.5.0",
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

    def _create_resize_mode_row(self, parent, row: int, label_text: str):
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
            variable=self.app.selected_resize_mode,
            values=[
                "Percentage (%)",
                "Bounding Box (Max WxH)",
                "Fixed Width",
                "Fixed Height",
                "ICO Resolution",
            ],
            command=self._on_resize_mode_changed,
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

    # -----------------------------------------------------------------------
    # Dynamic Sizing Controls Container
    # -----------------------------------------------------------------------
    def _build_dynamic_sizing_container(self, parent, row: int):
        self.sizing_container = self.ctk.CTkFrame(parent, fg_color="transparent")
        self.sizing_container.grid(row=row, column=0, padx=20, pady=4, sticky="ew")
        self.sizing_container.grid_columnconfigure(0, weight=1)

        # 1. Percentage Frame
        self.sizing_percent_frame = self.ctk.CTkFrame(self.sizing_container, fg_color="transparent", height=28)
        self.sizing_percent_frame.grid_columnconfigure(1, weight=1)

        lbl_pct = self.ctk.CTkLabel(
            self.sizing_percent_frame,
            text="RESIZE %",
            width=70,
            font=self.ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_TEXT_3,
            anchor="w",
        )
        lbl_pct.grid(row=0, column=0, sticky="w")

        self.app.resize_slider = self.ctk.CTkSlider(
            self.sizing_percent_frame,
            from_=5,
            to=200,
            variable=self.app.resize_percent,
            command=self._on_resize_percent_slider,
            width=168,
            height=16,
            corner_radius=CORNER_RADIUS,
            fg_color=COLOR_BORDER,
            progress_color=COLOR_BRAND,
            button_color=COLOR_THUMB,
            button_hover_color=COLOR_BRAND,
            border_width=0,
        )
        self.app.resize_slider.grid(row=0, column=1, padx=8, sticky="ew")
        self.resize_slider = self.app.resize_slider

        self.app.resize_input_var = self.ctk.StringVar(value=str(self.app.resize_percent.get()))
        self.app.resize_input_box = self.ctk.CTkEntry(
            self.sizing_percent_frame,
            textvariable=self.app.resize_input_var,
            width=42,
            height=24,
            corner_radius=CORNER_RADIUS,
            font=self.ctk.CTkFont(family=MONO_FONT, size=11),
            fg_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            text_color=COLOR_TEXT,
            justify="center",
        )
        self.app.resize_input_box.grid(row=0, column=2, sticky="e")
        self.resize_input_box = self.app.resize_input_box
        self._bind_select_all_and_commit(self.app.resize_input_box, self.app.resize_input_var, self.app.resize_percent, 5, 200, self.app.resize_slider)

        # 2. Bounding Box Frame (Max W x Max H)
        self.sizing_bbox_frame = self.ctk.CTkFrame(self.sizing_container, fg_color="transparent", height=28)
        self.sizing_bbox_frame.grid_columnconfigure((1, 3), weight=1)

        lbl_bb = self.ctk.CTkLabel(
            self.sizing_bbox_frame,
            text="BOUNDS",
            width=70,
            font=self.ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_TEXT_3,
            anchor="w",
        )
        lbl_bb.grid(row=0, column=0, sticky="w")

        lbl_w = self.ctk.CTkLabel(self.sizing_bbox_frame, text="W:", font=self.ctk.CTkFont(family=MONO_FONT, size=10), text_color=COLOR_MUTED)
        lbl_w.grid(row=0, column=1, sticky="e", padx=(0, 2))
        self.app.bbox_w_entry = self.ctk.CTkEntry(
            self.sizing_bbox_frame, textvariable=self.app.bbox_max_w, width=56, height=26, font=self.ctk.CTkFont(family=MONO_FONT, size=11), justify="center"
        )
        self.app.bbox_w_entry.grid(row=0, column=2, sticky="w", padx=(0, 4))
        self.app.bbox_w_entry.bind("<FocusOut>", lambda e: self.delayed_update())
        self.app.bbox_w_entry.bind("<Return>", lambda e: self.delayed_update())

        lbl_h = self.ctk.CTkLabel(self.sizing_bbox_frame, text="H:", font=self.ctk.CTkFont(family=MONO_FONT, size=10), text_color=COLOR_MUTED)
        lbl_h.grid(row=0, column=3, sticky="e", padx=(0, 2))
        self.app.bbox_h_entry = self.ctk.CTkEntry(
            self.sizing_bbox_frame, textvariable=self.app.bbox_max_h, width=56, height=26, font=self.ctk.CTkFont(family=MONO_FONT, size=11), justify="center"
        )
        self.app.bbox_h_entry.grid(row=0, column=4, sticky="w")
        self.app.bbox_h_entry.bind("<FocusOut>", lambda e: self.delayed_update())
        self.app.bbox_h_entry.bind("<Return>", lambda e: self.delayed_update())

        # 3. Fixed Width Frame
        self.sizing_width_frame = self.ctk.CTkFrame(self.sizing_container, fg_color="transparent", height=28)
        self.sizing_width_frame.grid_columnconfigure(1, weight=1)
        self.ctk.CTkLabel(
            self.sizing_width_frame, text="WIDTH", width=70, font=self.ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"), text_color=COLOR_TEXT_3, anchor="w"
        ).grid(row=0, column=0, sticky="w")
        self.app.fixed_w_entry = self.ctk.CTkEntry(
            self.sizing_width_frame, textvariable=self.app.fixed_width, width=72, height=26, font=self.ctk.CTkFont(family=MONO_FONT, size=11), justify="center"
        )
        self.app.fixed_w_entry.grid(row=0, column=1, sticky="w")
        self.app.fixed_w_entry.bind("<FocusOut>", lambda e: self.delayed_update())
        self.app.fixed_w_entry.bind("<Return>", lambda e: self.delayed_update())

        # 4. Fixed Height Frame
        self.sizing_height_frame = self.ctk.CTkFrame(self.sizing_container, fg_color="transparent", height=28)
        self.sizing_height_frame.grid_columnconfigure(1, weight=1)
        self.ctk.CTkLabel(
            self.sizing_height_frame, text="HEIGHT", width=70, font=self.ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"), text_color=COLOR_TEXT_3, anchor="w"
        ).grid(row=0, column=0, sticky="w")
        self.app.fixed_h_entry = self.ctk.CTkEntry(
            self.sizing_height_frame, textvariable=self.app.fixed_height, width=72, height=26, font=self.ctk.CTkFont(family=MONO_FONT, size=11), justify="center"
        )
        self.app.fixed_h_entry.grid(row=0, column=1, sticky="w")
        self.app.fixed_h_entry.bind("<FocusOut>", lambda e: self.delayed_update())
        self.app.fixed_h_entry.bind("<Return>", lambda e: self.delayed_update())

        # 5. ICO Size Frame
        self.sizing_ico_frame = self.ctk.CTkFrame(self.sizing_container, fg_color="transparent")
        self.sizing_ico_frame.grid_columnconfigure(1, weight=1)
        self.ctk.CTkLabel(
            self.sizing_ico_frame, text="ICON SIZE", width=70, font=self.ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"), text_color=COLOR_TEXT_3, anchor="w"
        ).grid(row=0, column=0, sticky="w")
        self.app.ico_size_menu = self.ctk.CTkOptionMenu(
            self.sizing_ico_frame,
            variable=self.app.ico_size_choice,
            values=[
                "Bundle (16-256 px)",
                "256 x 256",
                "128 x 128",
                "64 x 64",
                "48 x 48",
                "32 x 32",
                "16 x 16",
            ],
            command=lambda v: self.delayed_update(),
            height=30,
            font=self.ctk.CTkFont(family=MONO_FONT, size=11),
            fg_color=COLOR_SURFACE_2,
            button_color=COLOR_SURFACE_2,
            button_hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT,
        )
        self.app.ico_size_menu.grid(row=0, column=1, sticky="ew")

        # Row 1: Create Favicon Package Checkbox
        self.app.favicon_checkbox = self.ctk.CTkCheckBox(
            self.sizing_ico_frame,
            text="Create Favicon Package (.ico + PNGs)",
            variable=self.app.create_favicon,
            command=lambda: self.delayed_update(),
            font=self.ctk.CTkFont(family=BODY_FONT, size=11),
            text_color=COLOR_TEXT,
            corner_radius=CORNER_RADIUS,
            fg_color=COLOR_BRAND,
            hover_color=COLOR_BRAND_HOVER,
            checkbox_width=18,
            checkbox_height=18,
        )
        self.app.favicon_checkbox.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 2))

        fav_tip = (
            "When checked, generates a complete web favicon bundle:\n"
            "• favicon.ico (multi-resolution 16, 32, 48px)\n"
            "• favicon-16x16.png (standard tab)\n"
            "• favicon-32x32.png (retina tab)\n"
            "• apple-touch-icon.png (180x180 mobile)\n\n"
            "Single image outputs standard root names;\n"
            "batch images prefix filenames with each asset name."
        )
        CTkTooltip(self.app.favicon_checkbox, fav_tip)

        # Initial default display
        self.sizing_percent_frame.grid(row=0, column=0, sticky="ew")

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
        )
        input_box.grid(row=0, column=2, sticky="e")
        input_box.input_var = input_var

        self.app.quality_input_var = input_var
        self._bind_select_all_and_commit(input_box, input_var, variable, from_, to, slider)
        return slider, input_box, frame

    def _bind_select_all_and_commit(self, entry_widget, str_var, int_var, min_val, max_val, slider_widget):
        def _on_select(e=None):
            entry_widget.after(15, lambda: (entry_widget.select_range(0, "end"), entry_widget.icursor("end")))

        entry_widget.bind("<FocusIn>", _on_select)
        entry_widget.bind("<Button-1>", _on_select)
        if hasattr(entry_widget, "_entry"):
            entry_widget._entry.bind("<FocusIn>", _on_select)
            entry_widget._entry.bind("<Button-1>", _on_select)

        def _on_commit(e=None):
            raw = str_var.get().strip()
            try:
                val = int(raw)
                clamped = max(min_val, min(val, max_val))
            except ValueError:
                clamped = int_var.get()
            int_var.set(clamped)
            slider_widget.set(clamped)
            str_var.set(str(clamped))
            self.delayed_update()

        entry_widget.bind("<FocusOut>", _on_commit)
        entry_widget.bind("<Return>", _on_commit)
        if hasattr(entry_widget, "_entry"):
            entry_widget._entry.bind("<FocusOut>", _on_commit)
            entry_widget._entry.bind("<Return>", _on_commit)

        int_var.trace_add("write", lambda *args: str_var.set(str(int_var.get())) if str_var.get() != str(int_var.get()) else None)

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
            justify="center",
        )
        dpi_entry.grid(row=0, column=1, sticky="w")

        dpi_entry.bind("<FocusOut>", self.app.on_dpi_focusout)
        dpi_entry.bind("<Return>", self.app.on_dpi_focusout)
        return dpi_entry

    def _create_filter_row(self, parent, row: int, label_text: str):
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

        filter_menu = self.ctk.CTkOptionMenu(
            frame,
            variable=self.app.selected_filter,
            values=[
                "Lanczos (High Quality)",
                "Bicubic",
                "Bilinear",
                "Nearest (Pixel Art)",
            ],
            command=lambda v: self.delayed_update(),
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
        filter_menu.grid(row=0, column=1, columnspan=2, sticky="ew")
        return filter_menu

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

        # Row 3: Activity Log Card (Height: 165px)
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
            font=self.ctk.CTkFont(family=HEAD_FONT, size=13, weight="bold"),
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

        # Controls Block (Aspect Warning + Resample Button aligned with sample filename)
        controls_block = self.ctk.CTkFrame(self.app.header_frame, fg_color="transparent")
        controls_block.grid(row=0, column=2, sticky="se", pady=(0, 2))

        # Aspect Warning Badge (Shown for non-square ICO)
        self.app.aspect_warning_pill = self.ctk.CTkFrame(
            controls_block,
            height=26,
            corner_radius=CORNER_RADIUS,
            fg_color=COLOR_WARNING_BG,
        )
        self.app.aspect_warning_label = self.ctk.CTkLabel(
            self.app.aspect_warning_pill,
            text="⚠️ NON-SQUARE (AUTO-CROP 1:1)",
            font=self.ctk.CTkFont(family=HEAD_FONT, size=10, weight="bold"),
            text_color=COLOR_WARNING,
            padx=10,
            pady=3,
        )
        self.app.aspect_warning_label.pack()

        # Resample Preview Button (Horizontally aligned with sample filename)
        self.app.resample_button = self.ctk.CTkButton(
            controls_block,
            text="↻ Resample Preview",
            command=self.app.pick_random_image,
            height=30,
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

        # Card Header: Left title, Right: Files ready indicator (Display only, no click handler!)
        header = self.ctk.CTkFrame(self.app.preview_card, height=36, fg_color="transparent")
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

        # Status Pill Badge moved to sample preview header right (Display only, no browse trigger)
        self.app.status_pill = self.ctk.CTkFrame(
            header,
            height=26,
            corner_radius=CORNER_RADIUS,
            fg_color=COLOR_SURFACE_2,
        )
        self.app.status_pill.grid(row=0, column=2, sticky="e", pady=5)

        self.app.status_pill_label = self.ctk.CTkLabel(
            self.app.status_pill,
            text="• AWAITING FOLDER",
            font=self.ctk.CTkFont(family=HEAD_FONT, size=10, weight="bold"),
            text_color=COLOR_MUTED,
            padx=10,
            pady=3,
        )
        self.app.status_pill_label.pack()

        # 1px Divider
        div = ThemeDivider(self.app.preview_card, height=1)
        div.grid(row=1, column=0, sticky="ew")

        # Preview Container Frame
        self.app.image_preview_frame = self.ctk.CTkFrame(
            self.app.preview_card, fg_color=COLOR_SURFACE_2, corner_radius=0
        )
        self.app.image_preview_frame.grid(row=2, column=0, sticky="nsew")
        self.app.image_preview_frame.grid_rowconfigure(0, weight=1)
        self.app.image_preview_frame.grid_columnconfigure(0, weight=1)

        # Dropzone Widget
        self.app.dropzone_frame = self.ctk.CTkFrame(self.app.image_preview_frame, fg_color="transparent", cursor="hand2")
        self.app.dropzone_frame.grid(row=0, column=0, sticky="nsew")
        self.app.dropzone_frame.grid_rowconfigure(0, weight=1)
        self.app.dropzone_frame.grid_columnconfigure(0, weight=1)
        self.app.dropzone_frame.bind("<Button-1>", lambda e: self.app.browse_input_folder())

        inner_drop = self.ctk.CTkFrame(self.app.dropzone_frame, fg_color="transparent", cursor="hand2")
        inner_drop.place(relx=0.5, rely=0.5, anchor="center")
        inner_drop.bind("<Button-1>", lambda e: self.app.browse_input_folder())

        icon_lbl = self.ctk.CTkLabel(
            inner_drop, text="🖼", font=self.ctk.CTkFont(size=32), text_color=COLOR_BORDER_2, cursor="hand2"
        )
        icon_lbl.pack(pady=(0, 8))
        icon_lbl.bind("<Button-1>", lambda e: self.app.browse_input_folder())

        drop_title = self.ctk.CTkLabel(
            inner_drop, text="Drop Folder Here", font=self.ctk.CTkFont(family=BODY_FONT, size=14, weight="bold"), text_color=COLOR_TEXT, cursor="hand2"
        )
        drop_title.pack()
        drop_title.bind("<Button-1>", lambda e: self.app.browse_input_folder())

        drop_sub = self.ctk.CTkLabel(
            inner_drop, text="or Click Browse to select a folder", font=self.ctk.CTkFont(family=BODY_FONT, size=12), text_color=COLOR_MUTED, cursor="hand2"
        )
        drop_sub.pack(pady=(4, 0))
        drop_sub.bind("<Button-1>", lambda e: self.app.browse_input_folder())

        # Image Display Label
        self.app.image_preview = self.ctk.CTkLabel(
            self.app.image_preview_frame, text="", image=None
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
            height=165,
            fg_color=COLOR_SURFACE,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            corner_radius=CORNER_RADIUS,
        )
        self.app.log_card.grid(row=3, column=0, sticky="ew")
        self.app.log_card.grid_propagate(False)
        self.app.log_card.grid_rowconfigure(1, weight=1)
        self.app.log_card.grid_columnconfigure(0, weight=1)

        # Log Header with Action Buttons
        header_row = self.ctk.CTkFrame(self.app.log_card, fg_color="transparent", height=30)
        header_row.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
        header_row.grid_columnconfigure(0, weight=1)

        eyebrow = self.ctk.CTkLabel(
            header_row,
            text="ACTIVITY LOG",
            font=self.ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            text_color=COLOR_MUTED,
            anchor="w",
        )
        eyebrow.grid(row=0, column=0, sticky="w")

        btn_box = self.ctk.CTkFrame(header_row, fg_color="transparent")
        btn_box.grid(row=0, column=1, sticky="e")

        copy_btn = self.ctk.CTkButton(
            btn_box,
            text="📋 Copy",
            command=self.app.copy_log_to_clipboard,
            width=58,
            height=24,
            corner_radius=CORNER_RADIUS,
            font=self.ctk.CTkFont(family=HEAD_FONT, size=10, weight="bold"),
            fg_color="transparent",
            hover_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            text_color=COLOR_TEXT_3,
        )
        copy_btn.pack(side="left", padx=(0, 4))

        clear_btn = self.ctk.CTkButton(
            btn_box,
            text="🗑 Clear",
            command=self.app.clear_log,
            width=58,
            height=24,
            corner_radius=CORNER_RADIUS,
            font=self.ctk.CTkFont(family=HEAD_FONT, size=10, weight="bold"),
            fg_color="transparent",
            hover_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            text_color=COLOR_TEXT_3,
        )
        clear_btn.pack(side="left")

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
        self.app.action_bar.grid_columnconfigure(1, weight=1)

        # Left: Theme Icon Toggle Button (Perfect round container with centered filled icon)
        self.app.theme_toggle_btn = CircularIconButton(
            self.app.action_bar,
            size=36,
            image=self.app.get_current_theme_icon(),
            fg_color=COLOR_SURFACE_2,
            hover_color=COLOR_BORDER,
            border_color=COLOR_BORDER,
            border_width=BORDER_WIDTH,
            command=self.app.toggle_theme,
        )
        self.app.theme_toggle_btn.grid(row=0, column=0, padx=(20, 16), sticky="w")

        # Center Container (Telemetry summary OR Progress bar)
        self.app.center_action_frame = self.ctk.CTkFrame(self.app.action_bar, fg_color="transparent")
        self.app.center_action_frame.grid(row=0, column=1, sticky="ew", padx=(0, 16))
        self.app.center_action_frame.grid_columnconfigure(0, weight=1)

        # Summary Frame (idle state)
        self.app.summary_frame = self.ctk.CTkFrame(self.app.center_action_frame, fg_color="transparent")
        self.app.summary_frame.grid(row=0, column=0, sticky="w")

        self.app.status_dot = self.ctk.CTkLabel(
            self.app.summary_frame, text="●", font=self.ctk.CTkFont(size=9), text_color=COLOR_MUTED
        )
        self.app.status_dot.pack(side="left", padx=(0, 6))

        self.app.status_summary_label = self.ctk.CTkLabel(
            self.app.summary_frame,
            text="Waiting for folder  ·  JPG · quality 60 · resize 40% · 72 DPI",
            font=self.ctk.CTkFont(family=BODY_FONT, size=12),
            text_color=COLOR_TEXT_3,
        )
        self.app.status_summary_label.pack(side="left")

        # Open Output Folder Button (shown on batch finish)
        self.app.open_folder_btn = self.ctk.CTkButton(
            self.app.summary_frame,
            text="📂 Open Output Folder",
            command=self.app.open_output_folder,
            height=30,
            corner_radius=CORNER_RADIUS,
            font=self.ctk.CTkFont(family=HEAD_FONT, size=11, weight="bold"),
            fg_color=COLOR_SURFACE_2,
            border_color=COLOR_BORDER_2,
            border_width=BORDER_WIDTH,
            hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT,
        )

        # Progress bar frame (active state)
        self.app.progress_frame = self.ctk.CTkFrame(self.app.center_action_frame, fg_color="transparent")
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
        self.app.process_button.grid(row=0, column=2, padx=20, sticky="e")

    # -----------------------------------------------------------------------
    # Interactive Format, Mode & Slider Event Callbacks
    # -----------------------------------------------------------------------
    def _on_format_changed(self, value):
        self.on_image_type_changed(value, trigger_update=True)

    def on_image_type_changed(self, selected_type: str, trigger_update: bool = True):
        clean_type = str(selected_type).strip().replace(".", "").upper()
        is_ico = clean_type == "ICO"
        is_png = clean_type == "PNG"

        allows_quality = clean_type in ("JPG", "JPEG", "WEBP", "AVIF")
        q_state = "normal" if allows_quality else "disabled"
        if self.quality_slider:
            self.quality_slider.configure(state=q_state)
        if self.quality_input_box:
            self.quality_input_box.configure(state=q_state)

        if is_ico and self.app.selected_resize_mode.get() != "ICO Resolution":
            self.app.selected_resize_mode.set("ICO Resolution")
            self.on_resize_mode_changed("ICO Resolution", trigger_update=False)
        elif not is_ico and self.app.selected_resize_mode.get() == "ICO Resolution":
            self.app.selected_resize_mode.set("Percentage (%)")
            self.on_resize_mode_changed("Percentage (%)", trigger_update=False)

        if trigger_update:
            self.delayed_update()

    def _on_resize_mode_changed(self, value):
        self.on_resize_mode_changed(value, trigger_update=True)

    def on_resize_mode_changed(self, mode_str: str, trigger_update: bool = True):
        for f in (
            self.sizing_percent_frame,
            self.sizing_bbox_frame,
            self.sizing_width_frame,
            self.sizing_height_frame,
            self.sizing_ico_frame,
        ):
            if f:
                f.grid_forget()

        if "percent" in mode_str.lower():
            if self.sizing_percent_frame:
                self.sizing_percent_frame.grid(row=0, column=0, sticky="ew")
        elif "bound" in mode_str.lower():
            if self.sizing_bbox_frame:
                self.sizing_bbox_frame.grid(row=0, column=0, sticky="ew")
        elif "width" in mode_str.lower():
            if self.sizing_width_frame:
                self.sizing_width_frame.grid(row=0, column=0, sticky="ew")
        elif "height" in mode_str.lower():
            if self.sizing_height_frame:
                self.sizing_height_frame.grid(row=0, column=0, sticky="ew")
        elif "ico" in mode_str.lower():
            if self.sizing_ico_frame:
                self.sizing_ico_frame.grid(row=0, column=0, sticky="ew")

        if trigger_update:
            self.delayed_update()

    def _on_quality_changed(self, value):
        val = int(float(value))
        self.app.quality.set(val)
        self.delayed_update()

    def _on_resize_percent_slider(self, value):
        val = int(float(value))
        self.app.resize_percent.set(val)
        self.delayed_update()

    def delayed_update(self, *args):
        if self.update_timer is not None:
            self.app.after_cancel(self.update_timer)
        self.update_timer = self.app.after(300, self.app.update_sample_image_info)
