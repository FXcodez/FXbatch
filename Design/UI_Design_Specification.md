# FXbatch v05 — UI Design Specification & Architecture

This document defines the complete UI and design specification extracted from `FXbatch_Conversion.pen` and reference mockups in `v05/Design/`.

---

## 1. Top-Level Canvas Frames & Dimensions

All frames are designed for a native window geometry of **`920 × 780` px**:

| State | Theme | Frame ID | Label on Canvas | Dimensions | Canvas Position (x, y) | Reference File |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Empty** | **Dark** | `S3o2l` | `FXbatch Dark` | `920 × 780` | `(2346, 1151)` | `FXbatch Dark.jpg` |
| **Empty** | **Light** | `lYEi0` | `FXbatch Light` | `920 × 780` | `(2346, 2071)` | `FXbatch Light.jpg` |
| **Filled** | **Dark** | `AmnKP` | `FXbatch Dark - Image` | `920 × 780` | `(3530, 1151)` | `FXbatch Dark - Image.jpg` |
| **Filled** | **Light** | `Q4uTP` | `FXbatch Light - Image`| `920 × 780` | `(3530, 2071)` | `FXbatch Light - Image.jpg` |

---

## 2. Design Tokens Paired for CustomTkinter `(light_hex, dark_hex)`

Every color token is extracted directly from the `.pen` theme definition:

```python
THEME_TOKENS = {
    # Surfaces & Backgrounds
    "bg_main": ("#F6F6F7", "#1A1A1A"),        # $th-bg: Root window & analysis background
    "surface": ("#FFFFFF", "#2D2D2D"),        # $th-surface: Sidebar, Title Bar, Action Bar, Cards
    "surface_2": ("#F1F1F3", "#242424"),      # $th-surface-2: Inset fields, Dropzone, Inactive buttons
    
    # Borders & Dividers
    "border": ("#E3E3E7", "#3D3D3D"),         # $th-border: Outlines, Subtle dividers (1px)
    "border_2": ("#CDCDD3", "#4A4A4A"),       # $th-border-2: Interactive controls (Browse, Help, Settings)
    
    # Typography
    "text_primary": ("#16161A", "#F2F2F2"),   # $th-text: Headings, Active labels, Values
    "text_secondary": ("#3C3C43", "#C9C9C9"), # $th-text-3: Field values, Log line 1, Form labels
    "text_muted": ("#7C7C83", "#8E8E93"),     # $th-muted: Placeholders, Subtitles, Unit text
    
    # Brand & Accent
    "brand": ("#AA182C", "#AA182C"),          # $th-brand: Primary Red button, active toggle, slider track
    "on_brand": ("#FFFFFF", "#F2F2F2"),       # $th-on-brand: Text/icon over brand color
    "thumb": ("#16161A", "#F2F2F2"),          # $th-thumb: Slider thumb knob
    "logo": ("#16161A", "#FFFFFF"),           # $th-logo: Logo lettering fill
    
    # Status & Feedback
    "success": ("#1E824C", "#35B36E"),        # $th-success: Reduction value, ready status dot/badge text
    "success_bg": ("#E3F5EA", "#12301F"),     # $th-success-bg: Ready badge pill background
    "warning": ("#B4690E", "#E67E22"),        # $th-warning
    "error": ("#C42B3F", "#D9455B"),          # $th-error
}
```

### Core Geometric Constants
- **`corner_radius = 2`**: Strict design standard applied across cards, text entries, buttons, sliders, badge pills, and theme switch buttons.
- **`border_width = 1`**: Applied to all stroked containers, cards, and input fields.
- **Divider thickness = 1px**: Window and section dividers are explicit 1px height/width lines with `fg_color=border`.
- **Typography**:
  - Headings / Uppercase tags / Buttons: `("Oswald", weight="bold")`
  - Body / Form labels / Dropzone copy: `("Roboto", weight="normal" / "medium")`
  - Metrics / Sliders / Numbers / Logs: `("Roboto Mono", weight="normal")`

---

## 3. Window & Grid Layout Hierarchy

```
Root CTk Window (920 x 780, fg_color=bg_main)
│
├── Row 0: Main Body Frame (height=707, sticky="nsew", weight=1)
│   ├── Col 0: Configuration Sidebar (width=330, sticky="ns", weight=0)
│   ├── Col 1: Vertical Divider (width=1, sticky="ns", weight=0)
│   └── Col 2: Analysis Area (width=589+, sticky="nsew", weight=1)
│       ├── Row 0: Analysis Header (height=40, sticky="ew", weight=0)
│       ├── Row 1: Preview Card (weight=1, sticky="nsew")
│       │   ├── Preview Header (height=34, sticky="ew")
│       │   ├── 1px Divider
│       │   └── Content: Drop Zone (Empty) OR Cover Image (Filled)
│       ├── Row 2: Metrics Strip (height=80, sticky="ew", weight=0)
│       │   └── 5 Equal Cards (cols 0..4, weight=1 each)
│       │       [ ORIGINAL | OUTPUT | NEW SIZE | REDUCTION | SAMPLE DPI ]
│       └── Row 3: Activity Log Card (height=132, sticky="ew", weight=0)
│           ├── Eyebrow: "ACTIVITY LOG"
│           └── Log Lines (Roboto Mono 11)
├── Row 1: Bottom Divider (height=1, sticky="ew", weight=0)
└── Row 2: Action Bar Frame (height=72, sticky="ew", weight=0)
    ├── Col 0: Theme Switch [ LIGHT | DARK ]
    ├── Col 1: Status Indicator & Settings Summary
    ├── Col 2: Spacer (weight=1)
    └── Col 3: Batch Convert CTA Button (height=44, width=200)
```

---

## 4. Component Details & Engine Contract Mapping

To maintain 100% interoperability with `v04/FXbatch/fxbatch_main_gui.py` and `image_compressor.py`, all variable and widget identifiers are matched:

| UI Component | Backend Variable / Attribute | Old UI Widget | Revised v05 UI Widget Specification |
| :--- | :--- | :--- | :--- |
| **Input Folder Path** | `app.input_folder_path` (`StringVar`) | `CTkEntry` | Inset Field (`surface_2`, `border=1`, `h=36`) + Browse `CTkButton` |
| **Output Folder Path**| `app.output_folder_path` (`StringVar`)| `CTkEntry` | Inset Field (`surface_2`, `border=1`, `h=36`) + Browse `CTkButton` |
| **Quality Slider** | `app.quality` (`IntVar`, 10..100) | `CTkSlider` | `CTkSlider` (track `border`, progress `brand`, thumb `thumb`) + Value box (`w=40, h=24`) |
| **Resize % Slider** | `app.resize_percent` (`IntVar`, 10..100)| `CTkSlider`| `CTkSlider` (track `border`, progress `brand`, thumb `thumb`) + Value box (`w=40, h=24`) |
| **Image Format** | `app.selected_image_type` (`StringVar`) | `CTkOptionMenu` | `CTkOptionMenu` (`values=["JPG", "PNG", "WEBP"]`, `h=30`) |
| **Resize DPI** | `app.image_dpi` (`StringVar`) | `CTkEntry` | `CTkEntry` (`h=30`, validated 1..3000) |
| **Sample Info / Dims**| `app.sample_image_info` (`StringVar`) | `CTkLabel` (multiline) | Split into Analysis Header (`sample_image` name), Preview Header Dims, & Metric Cards |
| **Sample Preview** | `app.image_preview` (`CTkLabel`) | `CTkLabel` in 230x230 | Scaled `CTkLabel` fill inside `Preview Card` (mode="cover") |
| **Resample Button** | `app.resample_button` (`CTkButton`) | `CTkButton` (in sample) | `CTkButton` in Analysis Header (`h=34`, icon `refresh-cw`, `corner_radius=2`) |
| **Activity Log** | `app.log_text` (`CTkTextbox`) | `CTkTextbox` | `CTkTextbox` inside `Activity Log Card` (`h=132`, `corner_radius=2`, `border=1`) |
| **Progress Bar** | `app.progress_bar` (`CTkProgressBar`) | `CTkProgressBar` | Pinned or overlay in Action Bar / Status area |
| **Cancel Button** | `app.cancel_button` (`CTkButton`) | `CTkButton` | Cancel button in Action Bar when processing |
| **Batch Convert** | `app.process_button` (`CTkButton`) | `CTkButton` | CTA `CTkButton` (`h=44, w=200`, `corner_radius=2`, `brand` active / `surface_2` disabled) |
| **Settings** | `app.settings_button` (`CTkButton`) | `CTkButton` | In Sidebar bottom bar (`h=36, border=1`) |
| **Help** | `app.help_button` (`CTkButton`) | `CTkButton` | In Sidebar bottom bar (`h=36, border=1`) |

---

## 5. Visual State Transitions

### A. Empty State (Initial Startup)
- **Input & Output**: Display `"No folder selected"` in `text_muted`.
- **Analysis Header**:
  - Filename: `"No sample image"` (`text_muted`)
  - Status pill: `surface_2` fill, dot `text_muted`, text `"AWAITING FOLDER"` (`text_muted`)
  - Resample Button: Inactive (`border`, icon/text `text_muted`)
- **Preview Area**:
  - Center dropzone visible with upload icon, `"Drop Folder Here"`, and `"or Click Browse to select a folder"`.
  - Preview header: `"no sample loaded"`.
- **Metric Cards (x5)**:
  - All values display `"—"` in `text_muted`.
- **Activity Log**:
  - Displays onboarding guide bullet points.
- **Action Bar**:
  - Status: Muted dot + `"Waiting for folder  ·  JPG · quality 60 · resize 40% · 72 DPI"`.
  - CTA Button: Inactive styling (`surface_2` with `border` outline, `text_muted` text).

### B. Filled State (Folder / Images Loaded)
- **Input & Output**: Display loaded folder paths in `text_secondary`.
- **Analysis Header**:
  - Filename: Shows active sample name (e.g. `"5H3A2988.JPG"`) in `text_primary`.
  - Status pill: `success_bg` fill, dot `success`, text `"FOLDER READY"` (`success`).
  - Resample Button: Active (`border_2`, icon/text `text_primary`).
- **Preview Area**:
  - Dropzone replaced by full-bleed resized image preview.
  - Preview header: Displays original vs resized resolution (e.g. `"5760 × 3840  →  2304 × 1536"`).
- **Metric Cards (x5)**:
  - `ORIGINAL`: `"5760 × 3840"` (`text_primary`) + `"5.7 MB"` (`text_muted`).
  - `OUTPUT`: `"2304 × 1536"` (`text_primary`) + `"JPG · Q60"` (`text_muted`).
  - `NEW SIZE`: `"251.9 KB"` (`text_primary`) + `"est. output"` (`text_muted`).
  - `REDUCTION`: `"95.7%"` (**highlighted in `success` green**) + `"vs original"` (`text_muted`).
  - `SAMPLE DPI`: `"72"` (`text_primary`) + `"unchanged"` (`text_muted`).
- **Activity Log**:
  - Populated with operational messages (loaded folder, analyzed sample, compression estimations).
- **Action Bar**:
  - Status: Green dot (`success`) + `"Ready to convert  ·  JPG · quality 60 · resize 40% · 72 DPI"`.
  - CTA Button: Solid brand fill (`brand` `#AA182C`), white bold text (`on_brand`), `corner_radius=2`.

---

## 6. Execution & Workflow via `uv`

All environment provisioning, dependency management, and script execution in `v05/` uses `uv`:

```bash
# Sync dependencies and virtual environment
uv sync

# Launch standalone visual prototype
uv run ui_preview.py
```

