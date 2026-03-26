# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


project_root = Path(SPECPATH).resolve().parents[1]
datas = (
    collect_data_files("label_pdf_sku")
    + collect_data_files("pypdf")
    + collect_data_files("reportlab")
)
hiddenimports = (
    collect_submodules("label_pdf_sku")
    + collect_submodules("pypdf")
    + collect_submodules("reportlab")
)

a = Analysis(
    [str(project_root / "desktop_app.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LabelPdfSku",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="LabelPdfSku",
)
app = BUNDLE(
    coll,
    name="LabelPdfSku.app",
    icon=None,
    bundle_identifier="com.miniento.labelpdfsku",
    info_plist={
        "CFBundleDisplayName": "面单 SKU 标注工具",
        "CFBundleName": "LabelPdfSku",
        "CFBundleShortVersionString": "0.2.0",
        "CFBundleVersion": "0.2.0",
        "NSHighResolutionCapable": True,
    },
)
