"""Background search worker using QThread."""

import time

from PySide6.QtCore import QThread, Signal


class SearchWorker(QThread):
    results_ready = Signal(list, float)
    error_occurred = Signal(str)

    def __init__(self, query: str, limit: int = 50, include_content: bool = True):
        super().__init__()
        self.query = query
        self.limit = limit
        self.include_content = include_content

    def run(self):
        from services import Services
        import asyncio

        start_time = time.time()

        try:
            engine = Services.get_search_engine()

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(
                    engine.search(
                        query=self.query,
                        limit=self.limit,
                        include_content=self.include_content,
                    )
                )
            finally:
                loop.close()

            query_time = (time.time() - start_time) * 1000
            self.results_ready.emit(results, query_time)
        except Exception as e:
            self.error_occurred.emit(str(e))
