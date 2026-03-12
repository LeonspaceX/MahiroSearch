from pathlib import Path
import platform

WINDOWS_EXCLUDED_PATHS: frozenset[Path] = frozenset([
    Path("C:/Windows"),
    Path("C:/Program Files"),
    Path("C:/Program Files (x86)"),
    Path("C:/ProgramData"),
    Path("C:/Recovery"),
    Path("C:/System Volume Information"),
])

WINDOWS_EXCLUDED_NAMES: frozenset[str] = frozenset([
    "$RECYCLE.BIN",
    "System Volume Information",
])

LINUX_EXCLUDED_PATHS: frozenset[Path] = frozenset([
    Path("/proc"), Path("/sys"), Path("/dev"), Path("/run"),
    Path("/tmp"), Path("/boot"), Path("/lib"), Path("/lib64"),
    Path("/usr/lib"), Path("/snap"),
])

UNIVERSAL_EXCLUDED_NAMES: frozenset[str] = frozenset([
    ".git", ".svn", ".hg", "node_modules", ".pnpm-store",
    "__pycache__", ".venv", "venv", "env", "target",
    "build", "dist", "out", ".cache", ".tmp", ".temp",
])


class ExclusionRules:
    def __init__(self, user_exclusions: list[str] | None = None) -> None:
        self._user_exclusions: list[str] = user_exclusions or []
        self._platform = platform.system()

    def is_excluded(self, path: Path) -> bool:
        return self._excluded_by_path(path) or self._excluded_by_name(path)

    def _excluded_by_path(self, path: Path) -> bool:
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        if self._platform == "Windows":
            for ep in WINDOWS_EXCLUDED_PATHS:
                try:
                    resolved.relative_to(ep)
                    return True
                except ValueError:
                    pass
        else:
            for ep in LINUX_EXCLUDED_PATHS:
                try:
                    resolved.relative_to(ep)
                    return True
                except ValueError:
                    pass
        # User absolute-path exclusions
        for excl in self._user_exclusions:
            excl_path = Path(excl)
            if excl_path.is_absolute():
                try:
                    resolved.relative_to(excl_path)
                    return True
                except ValueError:
                    pass
        return False

    def _excluded_by_name(self, path: Path) -> bool:
        name = path.name
        if name.startswith("."):
            return True
        if name in UNIVERSAL_EXCLUDED_NAMES:
            return True
        if self._platform == "Windows" and name in WINDOWS_EXCLUDED_NAMES:
            return True
        # User name exclusions (non-absolute)
        for excl in self._user_exclusions:
            if not Path(excl).is_absolute() and name == excl:
                return True
        return False

    def add_user_exclusion(self, name_or_path: str) -> None:
        if name_or_path not in self._user_exclusions:
            self._user_exclusions.append(name_or_path)

    def remove_user_exclusion(self, name_or_path: str) -> None:
        self._user_exclusions = [e for e in self._user_exclusions if e != name_or_path]

    def list_user_exclusions(self) -> list[str]:
        return list(self._user_exclusions)
