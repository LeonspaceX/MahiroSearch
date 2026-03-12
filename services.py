"""
Service factory for creating application services.
Replaces FastAPI dependency injection with direct instantiation.
"""

import asyncio
import logging
import threading
from contextlib import suppress
from pathlib import Path
from config import AppConfig
from indexing.backend_oswalk import OsWalkWatchdogBackend
from indexing.exclusion import ExclusionRules
from indexing.content_reader import ContentReaderDispatcher
from indexing.chunker import TokenChunker
from embedding.client import EmbeddingClient
from db.lancedb_client import get_db_connection
from db.filenames_repo import FilenamesRepo
from db.chunks_repo import ChunksRepo
from search.searcher import SearchEngine
from indexing.pipeline import IndexingPipeline

logger = logging.getLogger(__name__)


class Services:
    """Singleton service container."""

    _cfg: AppConfig = None
    _pipeline: IndexingPipeline = None
    _search_engine: SearchEngine = None
    _watch_thread: threading.Thread | None = None
    _watch_stop: threading.Event | None = None

    @classmethod
    def initialize(cls, cfg: AppConfig):
        """Initialize all services with config."""
        cls._cfg = cfg

    @classmethod
    def get_search_engine(cls) -> SearchEngine:
        """Get or create SearchEngine instance."""
        if cls._search_engine is None:
            sparse = cls._cfg.embedding.enable_sparse
            db = get_db_connection(cls._cfg.data_dir / "lancedb")
            filenames_repo = FilenamesRepo(db, cls._cfg.embedding.embedding_dim, sparse_enabled=sparse)
            chunks_repo = ChunksRepo(db, cls._cfg.embedding.embedding_dim, sparse_enabled=sparse)
            embedder = EmbeddingClient(
                api_base_url=cls._cfg.embedding.api_base_url,
                api_key=cls._cfg.embedding.api_key,
                model=cls._cfg.embedding.model,
                sparse_enabled=sparse,
            )
            cls._search_engine = SearchEngine(
                filenames_repo=filenames_repo,
                chunks_repo=chunks_repo,
                embedder=embedder,
                query_prefix_enabled=cls._cfg.embedding.query_prefix_enabled,
            )
        return cls._search_engine

    @classmethod
    def set_query_prefix_enabled(cls, enabled: bool):
        if cls._cfg is not None:
            cls._cfg.embedding.query_prefix_enabled = enabled
        # Update existing instance if available, otherwise it'll pick up on next creation
        if cls._search_engine is not None:
            cls._search_engine._query_prefix_enabled = enabled

    @classmethod
    def get_pipeline(cls) -> IndexingPipeline:
        """Get or create IndexingPipeline instance."""
        if cls._pipeline is None:
            cfg = cls._cfg
            sparse = cfg.embedding.enable_sparse
            backend = OsWalkWatchdogBackend()
            exclusion_rules = ExclusionRules(user_exclusions=cfg.indexing.user_exclusions)
            content_reader = ContentReaderDispatcher(
                enable_docs=cfg.indexing.enable_content_docs,
                enable_code=cfg.indexing.enable_content_code,
            )
            chunker = TokenChunker(
                chunk_size=cfg.indexing.chunk_size_tokens,
                overlap=cfg.indexing.chunk_overlap_tokens,
            )
            embedding_client = EmbeddingClient(
                api_base_url=cfg.embedding.api_base_url,
                api_key=cfg.embedding.api_key,
                model=cfg.embedding.model,
                sparse_enabled=sparse,
            )
            db = get_db_connection(cfg.data_dir / "lancedb")
            filenames_repo = FilenamesRepo(db, cfg.embedding.embedding_dim, sparse_enabled=sparse)
            chunks_repo = ChunksRepo(db, cfg.embedding.embedding_dim, sparse_enabled=sparse)

            include_paths = [Path(p) for p in cfg.indexing.include_paths] if cfg.indexing.include_paths else None

            cls._pipeline = IndexingPipeline(
                backend=backend,
                exclusion_rules=exclusion_rules,
                content_reader=content_reader,
                chunker=chunker,
                embedder=embedding_client,
                filenames_repo=filenames_repo,
                chunks_repo=chunks_repo,
                include_paths=include_paths,
                disable_large_file_protection=cfg.indexing.disable_large_file_protection,
            )
        return cls._pipeline

    @classmethod
    def reload_pipeline(cls, cfg: AppConfig = None):
        """Force pipeline recreation after config change."""
        if cfg is not None:
            cls._cfg = cfg
        cls._pipeline = None

    @classmethod
    def start_file_watcher(cls):
        """Start background thread that watches file changes and updates index."""
        if cls._watch_thread and cls._watch_thread.is_alive():
            return

        cls._watch_stop = threading.Event()
        cls._watch_thread = threading.Thread(
            target=cls._watch_thread_main,
            name="mahiro-file-watcher",
            daemon=True,
        )
        cls._watch_thread.start()
        logger.info("File watcher thread started")

    @classmethod
    def stop_file_watcher(cls):
        """Stop background watcher thread."""
        if cls._watch_stop:
            cls._watch_stop.set()
        if cls._watch_thread and cls._watch_thread.is_alive():
            cls._watch_thread.join(timeout=3)
        cls._watch_thread = None
        cls._watch_stop = None
        logger.info("File watcher thread stopped")

    @classmethod
    def _watch_thread_main(cls):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(cls._watch_async())
        except Exception:
            logger.exception("Watcher thread crashed")
        finally:
            loop.close()

    @classmethod
    async def _watch_async(cls):
        pipeline = cls.get_pipeline()
        stop_event = cls._watch_stop
        if stop_event is None:
            return

        include_roots = [Path(p).resolve() for p in cls._cfg.indexing.include_paths] if cls._cfg.indexing.include_paths else None

        async def consume_events():
            async for event_type, payload in pipeline._backend.watch_changes(
                pipeline._exclusion_rules,
                include_paths=include_roots,
            ):
                raw_path = payload.path if hasattr(payload, "path") else payload
                path = Path(raw_path)

                if include_roots and not cls._path_included(path, include_roots):
                    continue

                try:
                    if event_type in ("created", "modified"):
                        await pipeline.reindex_file(path)
                    elif event_type == "deleted":
                        await pipeline.delete_file(path)
                except Exception:
                    logger.exception("Failed to process file change: %s %s", event_type, path)

        task = asyncio.create_task(consume_events())
        try:
            while not stop_event.is_set():
                await asyncio.sleep(0.5)
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    @staticmethod
    def _path_included(path: Path, include_roots: list[Path]) -> bool:
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path

        for root in include_roots:
            try:
                resolved.relative_to(root)
                return True
            except ValueError:
                continue
        return False
