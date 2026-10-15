# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Static assets to bundle into the executable directory
datas = [
    ('help.html', '.'),
    ('config.ini', '.'),
    ('icons', 'icons'),
    ('fonts', 'fonts'),
    ('Design/Logos', 'Design/Logos'),
]

# Collect package data files for GUI frameworks
datas += collect_data_files('tkinterdnd2')
datas += collect_data_files('customtkinter')
datas += collect_data_files('CTkMessagebox')

# Hidden imports for dynamically loaded modules
hiddenimports = [
    'tkinterdnd2',
    'customtkinter',
    'CTkMessagebox',
    'image_compressor',
    'widgets',
    'PIL',
    'PIL.Image',
    'PIL.ImageOps',
    'PIL.JpegImagePlugin',
    'PIL.PngImagePlugin',
    'PIL.WebPImagePlugin',
    'ctypes',
    'ctypes.wintypes',
    'multiprocessing',
] + collect_submodules('multiprocessing') + collect_submodules('tkinterdnd2') + collect_submodules('PIL')

# Exclude unnecessary heavy packages to keep the build lean
excludes = [
    'matplotlib',
    'scipy',
    'pandas',
    'unittest',
    'test',
]

a = Analysis(
    ['fxbatch_main_gui.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FXbatch',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['Design/Logos/favicon.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FXbatch',
)
