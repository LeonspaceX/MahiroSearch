import asyncio
import os
import platform
import queue
from pathlib import Path
from typing import AsyncIterator, Iterator

from .backend_base import AbstractFileIndexBackend, FileEntry
from .exclusion import ExclusionRules


class OsWalkWatchdogBackend(AbstractFileIndexBackend):
    """Cross-platform backend using os.walk + watchdog."""

    def get_all_roots(self) -> list[Path]:
        system = platform.system()
        if system == "Windows":
            return self._windows_roots()
        if system == "Linux":
            return self._linux_roots()
        return [Path("/")]

    @staticmethod
    def _windows_roots() -> list[Path]:
        import string

        roots: list[Path] = []
        for letter in string.ascii_uppercase:
            drive = Path(f"{letter}:/")
            if drive.exists():
                roots.append(drive)
        return roots

    @staticmethod
    def _linux_roots() -> list[Path]:
        roots: list[Path] = []
        virtual_fs = {
            "proc",
            "sysfs",
            "devtmpfs",
            "devpts",
            "tmpfs",
            "cgroup",
            "cgroup2",
            "pstore",
            "efivarfs",
            "bpf",
            "debugfs",
            "tracefs",
            "hugetlbfs",
            "mqueue",
            "fusectl",
            "securityfs",
            "configfs",
        }
        try:
            with open("/proc/mounts", "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) < 3:
                        continue
                    fs_type = parts[2]
                    mount_point = Path(parts[1])
                    if fs_type not in virtual_fs and mount_point.exists():
                        roots.append(mount_point)
        except FileNotFoundError:
            roots.append(Path("/"))

        seen: set[str] = set()
        unique: list[Path] = []
        for r in sorted(roots, key=lambda p: len(str(p))):
            key = str(r)
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique or [Path("/")]

    def iter_all_files(
        self,
        exclusion_rules: ExclusionRules,
        include_paths: list[Path] | None = None,
    ) -> Iterator[FileEntry]:
        roots = [Path(p) for p in include_paths] if include_paths else self.get_all_roots()
        for root in roots:
            yield from self._walk(root, exclusion_rules)

    def _walk(self, root: Path, exclusion_rules: ExclusionRules) -> Iterator[FileEntry]:
        try:
            for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
                current = Path(dirpath)
                if exclusion_rules.is_excluded(current):
                    dirnames.clear()
                    continue
                dirnames[:] = [
                    d for d in dirnames if not exclusion_rules.is_excluded(current / d)
                ]
                for fname in filenames:
                    fpath = current / fname
                    if exclusion_rules.is_excluded(fpath):
                        continue
                    try:
                        stat = fpath.stat()
                        yield FileEntry(
                            path=fpath,
                            name=fname,
                            size=stat.st_size,
                            modified_at=stat.st_mtime,
                            extension=fpath.suffix.lower(),
                        )
                    except OSError:
                        continue
        except (PermissionError, OSError):
            return

    async def watch_changes(
        self,
        exclusion_rules: ExclusionRules,
        include_paths: list[Path] | None = None,
    ) -> AsyncIterator[tuple[str, "FileEntry | Path"]]:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        event_queue: queue.Queue = queue.Queue()

        class Handler(FileSystemEventHandler):
            def on_created(self, event):
                if not event.is_directory:
                    event_queue.put(("created", Path(event.src_path)))

            def on_modified(self, event):
                if not event.is_directory:
                    event_queue.put(("modified", Path(event.src_path)))

            def on_deleted(self, event):
                if not event.is_directory:
                    event_queue.put(("deleted", Path(event.src_path)))

        observer = Observer()
        handler = Handler()
        watch_roots = [Path(p) for p in include_paths] if include_paths else self.get_all_roots()
        for root in watch_roots:
            try:
                observer.schedule(handler, str(root), recursive=True)
            except Exception:
                continue
        observer.start()

        try:
            while True:
                try:
                    event_type, path = event_queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.5)
                    continue
                if exclusion_rules.is_excluded(path):
                    continue
                if event_type == "deleted":
                    yield event_type, path
                    continue
                try:
                    stat = path.stat()
                    entry = FileEntry(
                        path=path,
                        name=path.name,
                        size=stat.st_size,
                        modified_at=stat.st_mtime,
                        extension=path.suffix.lower(),
                    )
                    yield event_type, entry
                except OSError:
                    continue
        finally:
            observer.stop()
            observer.join()

