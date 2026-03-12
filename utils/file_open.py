import platform
import subprocess
from pathlib import Path


def reveal_in_file_manager(path: Path) -> None:
    """
    Open the file manager with the given file selected.
    Windows: explorer /select,<path>
    Linux:   xdg-open <parent_dir>
    macOS:   open -R <path> (or open <dir>)
    """
    system = platform.system()
    path = Path(path)
    if system == "Windows":
        subprocess.Popen(["explorer", f"/select,{str(path)}"])
    elif system == "Linux":
        subprocess.Popen(["xdg-open", str(path.parent)])
    elif system == "Darwin":
        if path.exists() and path.is_dir():
            subprocess.Popen(["open", str(path)])
        elif path.exists():
            subprocess.Popen(["open", "-R", str(path)])
        else:
            subprocess.Popen(["open", str(path.parent)])
    else:
        raise NotImplementedError(f"Unsupported platform: {system}")
