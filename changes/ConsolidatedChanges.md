# FXbatch v06 : Consolidated Architecture & Implementation Plan

## Overview
FXbatch v06 represents the evolution of FXbatch from an integrated prototype into an enterprise-grade, high-performance batch image conversion and optimization suite.

This document consolidates:
1. **Critical bug fixes and edge-case resolutions** identified during the v05 code audit.
2. **Architecture enhancements** across the processing engine, UI layout, and settings persistence.
3. **New feature specifications** including advanced bounding-box sizing, next-gen AVIF encoding, ICC profile preservation, safe atomic file replacement, and one-click workflow presets.

For the exhaustive analysis, line-by-line code audit, and bug catalog, refer to [FXbatch_v06_Analysis_and_Improvements.md](file:///g:/Code/Python/Projects/00_FutureProjects/03_FXbatch/v06/FXbatch_v06_Analysis_and_Improvements.md).

---

## 1. Summary of Issues Identified in v05 & Solutions for v06

| Severity | Issue | File & Location | v06 Solution |
| :--- | :--- | :--- | :--- |
| **Critical** | Windows `WinError 32` file lock crash when source and destination are identical | `image_compressor.py` (`compress_and_resize_image`) | Implement atomic write via temporary file (`.tmp`) and `os.replace` after closing Pillow handles. |
| **Critical** | Activity Log overwrites itself on every image, erasing error history | `fxbatch_main_gui.py` (`_on_worker_progress`) | Route rate/ETA to the Action Bar telemetry; convert Activity Log into an appending event stream. |
| **Critical** | Version number is invisible (white-on-white) in Light Theme Settings | `fxbatch_main_gui.py` (`SettingsWindow`) | Bind version label to dynamic `COLOR_TEXT` or `COLOR_BRAND`. |
| **Critical** | WebP mode drops alpha channel on grayscale `LA` images | `image_compressor.py` (`_prepare_image_for_format`) | Convert `LA` mode to `RGBA` for WebP instead of forcing `RGB`. |
| **Critical** | `ThemeDivider` listener leak in `AppearanceModeTracker` | `widgets.py` (`ThemeDivider`) | Unregister callback on widget `<Destroy>`. |
| **Critical** | PyInstaller spec omits `tkinterdnd2` dynamic DLL binaries | `FXbatch.spec` | Add `collect_dynamic_libs('tkinterdnd2')` to binaries collection. |
| **Moderate** | Washed-out colors due to missing embedded ICC color profiles | `image_compressor.py` | Preserve `icc_profile` on export and auto-normalize to sRGB for web outputs. |
| **Moderate** | Settings window enforces minimum 72 DPI, conflicting with 1-3000 DPI main UI | `fxbatch_main_gui.py` (`SettingsWindow`) | Harmonize minimum DPI to `1` across all input fields. |
| **Moderate** | Multiprocessing pool raises `ResourceWarning` on normal teardown | `image_compressor.py` | Call explicit `pool.close()` and `pool.join()` on clean batch completion. |
| **Moderate** | Dummy Tkinter root initialized during module import | `widgets.py` (`_resolve_fonts`) | Defer font query until main `ctk.CTk()` root is created. |

---

## 2. Key Features Scheduled for v06

### A. Advanced Sizing & Dimension Modes
- **Proportional Bounding Box**: Fit within `Max Width × Max Height` (e.g. 1920 × 1080) maintaining exact aspect ratio.
- **Target Width / Target Height**: Set single dimension with automatic proportional calculation.
- **Extended Scale Range**: 5% to 200% scaling.
- **Resampling Filter Selection**: `LANCZOS`, `BICUBIC`, `BILINEAR`, and `NEAREST` (for pixel art).

### B. Next-Gen Formats & Compression Intelligence
- **AVIF Support**: Up to 50% smaller than JPEG at identical perceptual quality.
- **Lossless WebP Toggle**: Bit-exact compression for logos, UI, and graphics.
- **PNG8 Palette Quantization**: Up to 70% reduction in PNG file size while preserving alpha transparency.
- **Progressive JPEG**: Faster perceived loading for web delivery.

### C. Color Management & EXIF Control
- **ICC Profile Preservation**: Keeps Apple Display P3 and Adobe RGB profiles intact.
- **Configurable EXIF Retention**: Option to strip metadata for web privacy or preserve camera EXIF for archiving.

### D. Safety, File Management & Workflow
- **Collision Strategies**: Choose between *Auto-rename* (`_1`), *Overwrite* (atomic replace), or *Skip* (resume interrupted jobs).
- **Custom Naming Tokens**: Suffixes such as `{name}_{w}x{h}`, `{name}_thumb`, or `{name}_q{quality}`.
- **Open Output Folder**: One-click button in Action Bar to view results in Windows Explorer.
- **Subdirectory Processing**: Option to recurse through nested directories and mirror structure.

### E. Interactive UI & Presets
- **Interactive Before / After Comparison**: Toggle or split preview between source and compressed RAM sample.
- **Alpha Checkerboard Preview**: Two-tone grid under transparent PNG/WebP images.
- **Workflow Presets Dropdown**: Quick selection of *Web Optimized*, *Social Media*, *Lossless Archive*, and *Print*.

---

## 3. Directory Structure for v06

```
v06/
├── FXbatch_v06_Analysis_and_Improvements.md   # Complete code audit, bug fixes & feature roadmap
├── ConsolidatedChanges.md                     # Consolidated architecture & feature summary
```
