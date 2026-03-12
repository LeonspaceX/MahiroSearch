#!/usr/bin/env python3
"""Build MahiroSearch macOS package with PyInstaller (onefile)."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path


APP_NAME = "MahiroSearch"


def main() -> int:
    if platform.system() != "Darwin":
        print("build_macos.py can only run on macOS")
        return 1

    root = Path(__file__).resolve().parent
    main_py = root / "main.py"
    config_yaml = root / "config.yaml"
    icon_icns = root / "icon.icns"
    icon_png = root / "icon.png"
    icon_ico = root / "icon.ico"

    if not main_py.exists():
        print("main.py not found")
        return 1
    if not config_yaml.exists():
        print("config.yaml not found")
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
        "--exclude-module",
        "PyQt5",
        "--collect-all",
        "qfluentwidgets",
        "--collect-submodules",
        "watchdog.observers",
        "--collect-submodules",
        "tiktoken",
        "--collect-submodules",
        "tiktoken_ext",
        "--hidden-import",
        "tiktoken_ext.openai_public",
        "--add-data",
        f"{config_yaml}:.",
    ]

    if icon_png.exists():
        cmd.extend(["--add-data", f"{icon_png}:."])
    if icon_ico.exists():
        cmd.extend(["--add-data", f"{icon_ico}:."])

    if icon_icns.exists():
        cmd.extend(["--icon", str(icon_icns)])
    elif icon_png.exists():
        cmd.extend(["--icon", str(icon_png)])

    cmd.append(str(main_py))

    print("Running command:")
    print(" ".join(f'"{c}"' if " " in c else c for c in cmd))
    result = subprocess.run(cmd, cwd=root, check=False)
    if result.returncode != 0:
        print(f"Build failed with exit code: {result.returncode}")
        return result.returncode

    app_path = root / "dist" / f"{APP_NAME}.app"
    bin_path = root / "dist" / APP_NAME
    if app_path.exists():
        print(f"Build complete: {app_path}")
    else:
        print(f"Build complete: {bin_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

