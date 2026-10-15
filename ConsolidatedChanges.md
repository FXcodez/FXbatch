# FXbatch v05 : Consolidated Architecture & Implementation Summary

## Overview
FXbatch v05 is a complete redesign and engine integration combining:
1. The visual design specifications extracted from `FXbatch_Conversion.pen` and reference mockups (`v05/Design/`).
2. The high-performance multi-core batch image resizing engine from `v04/FXbatch/`.
3. Modern Python 3.12+ execution architecture powered by `uv`.

---

## 1. Key Enhancements & New Features in v05

### A. New UI Architecture & Layout
- **Fixed-width Configuration Sidebar (330px)**:
  - Genuine PNG/SVG brand logo lockup with responsive fallback.
  - Section headers with custom 1px hardware theme dividers.
  - Path picker rows for Input and Output folders with inset text fields, folder icons, and Browse buttons.
  - Refined slider rows for **Quality** (10-100) and **Resize %** (10-100) with interactive numeric value badges.
  - Format dropdown menu supporting `.JPG`, `.PNG`, and `.WEBP`. Lossless PNG automatically disables the Quality slider.
  - Resampling DPI input field with real-time numeric validation (1-3000).
  - Sidebar utility buttons for **⚙ Settings** and **ⓘ Help**.
- **Expanding Analysis Area**:
  - **Sample Analysis Header**: Filename display, status pill badge (e.g. `• READY (12 FILES)`), and `↻ Resample Preview` button.
  - **Sample Preview Card**: High-resolution thumbnail display with LANCZOS scaling, switching cleanly from the interactive dropzone in the empty state to the live cover image in the filled state.
  - **5 Metric Cards**:
    1. `ORIGINAL`: Original image resolution & file size.
    2. `OUTPUT`: Target resolution & format/quality.
    3. `NEW SIZE`: Exact compressed output size estimated in RAM via `BytesIO`.
    4. `REDUCTION`: Percentage size savings highlighted in green.
    5. `SAMPLE DPI`: DPI comparison and verification.
  - **Activity Log Card**: Scrollable terminal-styled log with onboarding instructions and batch execution metrics.
- **Action Bar (72px)**:
  - **Theme Switcher**: Segmented toggle `[ LIGHT | DARK ]` with responsive brand red active indicator.
  - **Status Telemetry**: Live status dot and summary of active conversion parameters.
  - **Batch Convert CTA Button**: `▷ Batch Convert Images` with brand crimson styling.
  - **In-place Progress Bar & Cancel Button**: Replaces the summary text during active conversions with real-time ETA and cancellation.

### B. Settings Dialog Updates (User Tweaks)
1. **Matching Version Number & Card Frame Spacing**:
   - Displays `2.0.0` in crisp white (`#FFFFFF`) text, matching window title, subtitle, and `APP_VERSION = "2.0.0"`.
   - Balanced window geometry (`450x405`), with outer dark frame margins reduced by 15px (`padx=5, pady=5`), +15px spacing between the subfolder name element and action buttons (`pady=(31, 22)` on `btn_frame`), and preserved breathing room below the action buttons (~24-30px clearance).
2. **Startup Theme Mode Selection**:
   - New dropdown setting: `Startup Theme: [Dark | Light | System]`.
   - Persists in `config.ini` under `[Settings] theme_mode`.
   - Immediately updates the active window theme upon saving.
3. **Uppercase Setting Labels**:
   - Standardized all row labels to uppercase (`FXBATCH VERSION:`, `STARTUP THEME:`, `DEFAULT QUALITY:`, `DEFAULT RESIZE %:`, `DEFAULT DPI:`, `SUBFOLDER NAME:`), matching the design language across the rest of the application.

### C. Engine & Concurrency Enhancements
- **Thread-Safe UI Dispatcher**:
  - Implemented `dispatch_ui(func, *args, **kwargs)` backed by `Queue` and a 20ms Tkinter polling loop.
  - Eliminates Python 3.12/3.13 `RuntimeError: main thread is not in main loop` cross-thread exceptions.
- **Multiprocessing Pool with Auto CPU Core Detection**:
  - Utilizes `os.cpu_count()` to distribute batch jobs across all logical cores.
  - Chunked workload dispatching for minimal IPC overhead.
- **Native Alpha Flattening for JPEG**:
  - Automatically composites `RGBA`, `LA`, and palette-transparency onto white backgrounds when saving as `.JPG`, avoiding Pillow conversion crashes.

### D. Activity Log & Input Refinements
1. **Editable Quality & Resize % Fields**:
   - Replaced static labels with interactive `CTkEntry` inputs (`width=42, height=24, justify="center"`).
   - Auto-selects full text on click or `<FocusIn>` (bound to both outer frame and native internal `_entry`).
   - Validates keystrokes (digits up to 3 chars).
   - Clamps on `<FocusOut>` and `<Return>` to `[10, 100]`, instantly syncing sliders, string variables, and background sample estimators.
2. **Compact DPI Field (25% Width)**:
   - Resized DPI input to `width=56` (25% of former ~220px width), positioned cleanly in column 1 (`sticky="w"`).
   - Auto-selects all text on click or focus for rapid inline adjustment.
3. **Removal of Modal Messageboxes & Auto-Scroll to Top**:
   - Removed `CTkMessagebox` popups upon conversion completion or cancellation.
   - Replaced with clear, highlighted ASCII banner summary reports directly in the Activity Log (`[SUCCESS]`, `[CANCELLED]`, `[COMPLETED WITH ERRORS]`).
   - Automatically scrolls the Activity Log to the very top (`see("1.0")` and `yview_moveto(0.0)`) on completion and cancellation so the report banner and key statistics are immediately visible.
4. **Expanded Activity Log Area (+40px)**:
   - Increased log card height from `132px` to `172px` for improved visibility of terminal logs and conversion statistics.
   - Expanded window geometry from `920x780` to `920x820` (minimum size: `920x760`).
5. **Simulated Warmup Progress (10% in 2.5s)**:
   - Smooth quadratic ease-out progress curve (`1 - (1 - t/2.5)^2`) advancing exactly 10% (`_warmup_target = 0.10`) over 2.5 seconds before yielding to actual multi-core conversion progress.
6. **Universal Version Text Standardized to '2.0.0'**:
   - Standardized across window title (`FXbatch Resizer 2.0.0`), brand subtitle (`BATCH IMAGE RESIZER 2.0.0`), Settings dialog, `config.ini`, and `pyproject.toml`.
7. **Redesigned User Documentation (`help.html`)**:
   - Upgraded to match the v05 dark design system (`#17181C` background, `#242424` surfaces, `#AA182C` crimson accent, Oswald and Roboto typography).
   - Fully vetted copy against `/humanizer` rules (zero em/en dashes, zero AI buzzwords, plain technical tone).
   - Detailed coverage of sample preview metrics, multi-core processing, format handling, settings, and keyboard shortcuts.
8. **Performance Benchmark Added**:
   - Documented reference conversion benchmark: 1,000 images at 5760x3840 px resized to 2304x1536 px (40% scale, Quality 60, JPEG) in ~20.7 seconds (~48 images/sec) on an SSD.


## 2. File Structure

```
v05/
├── .venv/                         # Managed Python 3.13.9 virtual environment via uv
├── fonts/                         # Registered TTF fonts (Oswald, Roboto, Roboto Mono)
├── icons/                         # Desktop icons (.ico, .png, .icns)
├── Design/                        # Reference design mockups, pen tokens, and logos
├── config.ini                     # User configuration (quality, resize, dpi, theme, version)
├── help.html                      # Offline HTML user documentation
├── image_compressor.py            # Multi-core resizing engine & BytesIO estimator
├── widgets.py                     # ThemeDivider, Design Tokens, & WidgetCreator
├── fxbatch_main_gui.py            # Main application entry point & SettingsWindow
├── ui_preview.py                  # Standalone preview mockup
├── pyproject.toml                 # uv project configuration and dependencies
└── uv.lock                        # Deterministic dependency lockfile
```

---

## 3. Running & Testing

To launch the integrated application:
```powershell
uv run python fxbatch_main_gui.py
```
