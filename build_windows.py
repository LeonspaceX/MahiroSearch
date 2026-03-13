#!/usr/bin/env python3
"""Build MahiroSearch Windows package with PyInstaller (onefile)."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path


APP_NAME = "MahiroSearch"


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
    ]

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
