"""Background indexing worker using QThread."""

import threading
import time
from pathlib import Path

from PySide6.QtCore import QThread, Signal


class IndexWorker(QThread):
    progress_updated = Signal(dict)
    indexing_complete = Signal()
    error_occurred = Signal(str)

    def __init__(self, action: str = "start", file_path: str = None):
        super().__init__()
        self.action = action
        self.file_path = file_path
        self._poll_thread = None

    def run(self):
        from config import AppConfig
        from services import Services
        import asyncio

        try:
            if self.action == "start":
                cfg = AppConfig.load()
                Services.reload_pipeline(cfg)

            pipeline = Services.get_pipeline()
            if self.action == "start":
                init_warnings = [
                    *getattr(pipeline._filenames_repo, "init_warnings", []),
                    *getattr(pipeline._chunks_repo, "init_warnings", []),
                ]
                if init_warnings:
                    self.progress_updated.emit(
                        {
                            "total_files_discovered": 0,
                            "files_indexed": 0,
                            "chunks_indexed": 0,
                            "errors": init_warnings,
                            "is_running": False,
                            "is_complete": False,
                        }
                    )

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                if self.action == "start":
                    self._start_progress_polling(pipeline)
                    loop.run_until_complete(pipeline.run_full_index())
                elif self.action == "stop":
                    pipeline.cancel()
                elif self.action == "reindex_file" and self.file_path:
                    loop.run_until_complete(pipeline.reindex_file(Path(self.file_path)))
                elif self.action == "delete_file" and self.file_path:
                    loop.run_until_complete(pipeline.delete_file(Path(self.file_path)))
            finally:
                loop.close()

            if self.action == "start":
                progress = pipeline.get_progress()
                self.progress_updated.emit(
                    {
                        "total_files_discovered": progress.total_files_discovered,
                        "files_indexed": progress.files_indexed,
                        "chunks_indexed": progress.chunks_indexed,
                        "errors": progress.errors,
                        "is_running": False,
                        "is_complete": progress.is_complete,
                    }
                )

            self.indexing_complete.emit()
        except Exception as e:
            self.error_occurred.emit(str(e))

    def _start_progress_polling(self, pipeline):
        def poll():
            for _ in range(100):
                if pipeline.get_progress().is_running:
                    break
                time.sleep(0.1)

            while True:
                progress = pipeline.get_progress()
                try:
                    self.progress_updated.emit(
                        {
                            "total_files_discovered": progress.total_files_discovered,
                            "files_indexed": progress.files_indexed,
                            "chunks_indexed": progress.chunks_indexed,
                            "errors": progress.errors,
                            "is_running": progress.is_running,
                            "is_complete": progress.is_complete,
                        }
                    )
                except RuntimeError:
                    break
                if not progress.is_running:
                    break
                time.sleep(0.5)

        self._poll_thread = threading.Thread(target=poll, daemon=True)
        self._poll_thread.start()

    def cancel(self):
        from services import Services

        pipeline = Services.get_pipeline()
        pipeline.cancel()
