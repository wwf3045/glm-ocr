# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_dir = Path(SPECPATH).resolve()
pyside_dir = Path(r"D:\anaconda3\Lib\site-packages\PySide6")
shiboken_dir = Path(r"D:\anaconda3\Lib\site-packages\shiboken6")
conda_bin_dir = Path(r"D:\anaconda3\Library\bin")
icon_path = project_dir / "assets" / "ocr_duplicate_reviewer.ico"
dist_name = "OCRDuplicateReviewer_compact"

block_cipher = None


def collect_pairs(root: Path, names: list[str], dest_prefix: str = "") -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for name in names:
        src = root / name
        if not src.exists():
            continue
        dest = dest_prefix or "."
        pairs.append((str(src), dest))
    return pairs


binaries: list[tuple[str, str]] = []
binaries += collect_pairs(
    pyside_dir,
    [
        "pyside6.abi3.dll",
        "QtCore.pyd",
        "QtGui.pyd",
        "QtWidgets.pyd",
        "Qt6Core.dll",
        "Qt6Gui.dll",
        "Qt6Widgets.dll",
        "MSVCP140.dll",
        "MSVCP140_1.dll",
        "MSVCP140_2.dll",
        "VCRUNTIME140.dll",
        "VCRUNTIME140_1.dll",
    ],
    "PySide6",
)
binaries += collect_pairs(
    shiboken_dir,
    [
        "shiboken6.abi3.dll",
    ],
    "shiboken6",
)
binaries += collect_pairs(
    conda_bin_dir,
    [
        "icuuc.dll",
        "icudt75.dll",
    ],
)
binaries += [(str(path), ".") for path in sorted(Path(r"D:\anaconda3").glob("api-ms-win-crt-*.dll"))]
binaries += collect_pairs(
    Path(r"D:\anaconda3"),
    [
        "ucrtbase.dll",
    ],
)

datas: list[tuple[str, str]] = []
datas += collect_pairs(
    pyside_dir / "plugins" / "platforms",
    [
        "qwindows.dll",
        "qminimal.dll",
    ],
    "PySide6/plugins/platforms",
)
datas += collect_pairs(
    pyside_dir / "plugins" / "imageformats",
    [
        "qjpeg.dll",
        "qico.dll",
        "qgif.dll",
    ],
    "PySide6/plugins/imageformats",
)
datas += collect_pairs(
    pyside_dir / "plugins" / "styles",
    [
        "qmodernwindowsstyle.dll",
    ],
    "PySide6/plugins/styles",
)


a = Analysis(
    [str(project_dir / "duplicate_image_reviewer_app.py")],
    pathex=[str(project_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "numpy",
        "pyreadline3",
        "matplotlib",
        "PySide6.Qt3DAnimation",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DExtras",
        "PySide6.Qt3DInput",
        "PySide6.Qt3DLogic",
        "PySide6.Qt3DRender",
        "PySide6.QtBluetooth",
        "PySide6.QtCharts",
        "PySide6.QtConcurrent",
        "PySide6.QtDBus",
        "PySide6.QtDesigner",
        "PySide6.QtGraphs",
        "PySide6.QtHelp",
        "PySide6.QtHttpServer",
        "PySide6.QtLocation",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtNetwork",
        "PySide6.QtNetworkAuth",
        "PySide6.QtNfc",
        "PySide6.QtOpenGL",
        "PySide6.QtOpenGLWidgets",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtPositioning",
        "PySide6.QtPrintSupport",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuick3D",
        "PySide6.QtQuickControls2",
        "PySide6.QtQuickWidgets",
        "PySide6.QtRemoteObjects",
        "PySide6.QtScxml",
        "PySide6.QtSensors",
        "PySide6.QtSerialBus",
        "PySide6.QtSerialPort",
        "PySide6.QtSpatialAudio",
        "PySide6.QtSql",
        "PySide6.QtStateMachine",
        "PySide6.QtSvg",
        "PySide6.QtTest",
        "PySide6.QtTextToSpeech",
        "PySide6.QtUiTools",
        "PySide6.QtWebChannel",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineQuick",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebSockets",
        "PySide6.QtWebView",
        "PySide6.QtXml",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OCRDuplicateReviewer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon=str(icon_path) if icon_path.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=dist_name,
)
