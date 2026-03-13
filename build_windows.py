#!/usr/bin/env python3
"""Build MahiroSearch Windows package with PyInstaller (onefile)."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


APP_NAME = "MahiroSearch"
EXCLUDED_MODULES = [
    "PyQt5",
    "PyQt6",
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNetworkAuth",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtPositioning",
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
    "PySide6.QtStateMachine",
    "PySide6.QtTextToSpeech",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
]


def main() -> int:
    if platform.system() != "Windows":
        print("build_windows.py can only run on Windows")
        return 1

    root = Path(__file__).resolve().parent
    main_py = root / "main.py"
    icon_ico = root / "icon.ico"
    icon_png = root / "icon.png"

    if not main_py.exists():
        print("main.py not found")
        return 1

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onefile",
        "--name",
        APP_NAME,
        "--collect-data",
        "qfluentwidgets",
        "--collect-submodules",
        "qfluentwidgets",
        "--collect-submodules",
        "watchdog.observers",
        "--collect-submodules",
        "tiktoken",
        "--collect-submodules",
        "tiktoken_ext",
        "--hidden-import",
        "tiktoken_ext.openai_public",
    ]

    for module in EXCLUDED_MODULES:
        cmd.extend(["--exclude-module", module])

    upx_dir = os.environ.get("UPX_DIR")
    if not upx_dir:
        upx_bin = shutil.which("upx")
        if upx_bin:
            upx_dir = str(Path(upx_bin).resolve().parent)
    if upx_dir:
        cmd.extend(["--upx-dir", upx_dir])

    if icon_png.exists():
        cmd.extend(["--add-data", f"{icon_png};."])

    if icon_ico.exists():
        cmd.extend(["--add-data", f"{icon_ico};."])
        cmd.extend(["--icon", str(icon_ico)])
    elif icon_png.exists():
        cmd.extend(["--icon", str(icon_png)])

    cmd.append(str(main_py))

    print("Running command:")
    print(" ".join(f'"{c}"' if " " in c else c for c in cmd))
    result = subprocess.run(cmd, cwd=root, check=False)
    if result.returncode != 0:
        print(f"Build failed with exit code: {result.returncode}")
        return result.returncode

    exe_path = root / "dist" / f"{APP_NAME}.exe"
    print(f"Build complete: {exe_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
