#!/usr/bin/env python3
"""Build MahiroSearch Linux package with PyInstaller (onedir + tar.gz)."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path


APP_NAME = "MahiroSearch"
QT_PLUGIN_DIRS = [
    "platforms",
    "platforminputcontexts",
    "xcbglintegrations",
]
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


def _get_qt_plugins_dir() -> Path:
    from PySide6.QtCore import QLibraryInfo

    return Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))


def _add_qt_plugin_binaries(cmd: list[str]) -> None:
    plugins_root = _get_qt_plugins_dir()

    for plugin_dir_name in QT_PLUGIN_DIRS:
        plugin_dir = plugins_root / plugin_dir_name
        if not plugin_dir.exists():
            print(f"Skipping missing Qt plugin dir: {plugin_dir}")
            continue

        for plugin_file in sorted(plugin_dir.rglob("*")):
            if not plugin_file.is_file():
                continue
            relative_parent = plugin_file.relative_to(plugin_dir).parent
            cmd.extend(
                [
                    "--add-binary",
                    f"{plugin_file}:{Path('PySide6') / 'plugins' / plugin_dir_name / relative_parent}",
                ]
            )


def _make_linux_archive(dist_dir: Path) -> Path:
    archive_name = f"{APP_NAME}-linux-{platform.machine()}.tar.gz"
    archive_path = dist_dir / archive_name
    app_dir = dist_dir / APP_NAME

    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(app_dir, arcname=APP_NAME)

    return archive_path


def main() -> int:
    if platform.system() != "Linux":
        print("build_linux.py can only run on Linux")
        return 1

    root = Path(__file__).resolve().parent
    main_py = root / "main.py"
    icon_png = root / "icon.png"
    icon_ico = root / "icon.ico"

    if not main_py.exists():
        print("main.py not found")
        return 1

    icon = icon_png if icon_png.exists() else (icon_ico if icon_ico.exists() else None)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
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

    _add_qt_plugin_binaries(cmd)

    upx_dir = os.environ.get("UPX_DIR")
    if not upx_dir:
        upx_bin = shutil.which("upx")
        if upx_bin:
            upx_dir = str(Path(upx_bin).resolve().parent)
    if upx_dir:
        cmd.extend(["--upx-dir", upx_dir])

    if icon_png.exists():
        cmd.extend(["--add-data", f"{icon_png}:."])

    if icon_ico.exists():
        cmd.extend(["--add-data", f"{icon_ico}:."])
    if icon is not None:
        cmd.extend(["--icon", str(icon)])

    cmd.append(str(main_py))

    print("Running command:")
    print(" ".join(f'"{c}"' if " " in c else c for c in cmd))
    result = subprocess.run(cmd, cwd=root, check=False)
    if result.returncode != 0:
        print(f"Build failed with exit code: {result.returncode}")
        return result.returncode

    dist_dir = root / "dist"
    app_dir = dist_dir / APP_NAME
    archive_path = _make_linux_archive(dist_dir)
    print(f"Build complete: {app_dir}")
    print(f"Archive created: {archive_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
