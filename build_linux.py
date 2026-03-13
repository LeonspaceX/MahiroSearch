#!/usr/bin/env python3
"""Build MahiroSearch Linux package with PyInstaller (onefile)."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path


APP_NAME = "MahiroSearch"


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

    bin_path = root / "dist" / APP_NAME
    print(f"Build complete: {bin_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
