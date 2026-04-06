# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for WellSign.
# Build:  python -m PyInstaller wellsign.spec
# Output: dist/WellSign.exe (single-file, windowed)

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

datas = [
    ("src/wellsign/db/schema.sql", "wellsign/db"),
    ("src/wellsign/resources/style.qss", "wellsign/resources"),
    ("src/wellsign/resources/license_public_key.pem", "wellsign/resources"),
]

# keyring discovers backends via entry points; PyInstaller can miss them.
hiddenimports = [
    "keyring.backends.Windows",
    "keyring.backends.SecretService",
    "keyring.backends.macOS",
    "keyring.backends.fail",
    "keyring.backends.null",
    *collect_submodules("wellsign"),
]

a = Analysis(
    ["src/wellsign/main.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Trim things we definitely don't ship
        "tkinter",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineQuick",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.Qt3DInput",
        "PySide6.Qt3DLogic",
        "PySide6.Qt3DAnimation",
        "PySide6.Qt3DExtras",
        "PySide6.QtBluetooth",
        "PySide6.QtNfc",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtPositioning",
        "PySide6.QtLocation",
    ],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="WellSign",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
