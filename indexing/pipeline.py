import asyncio
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path

from .backend_base import AbstractFileIndexBackend, FileEntry
from .exclusion import ExclusionRules
from .content_reader import ContentReaderDispatcher
from .chunker import TokenChunker
from embedding.client import EmbeddingClient
from db.filenames_repo import FilenamesRepo
from db.chunks_repo import ChunksRepo

logger = logging.getLogger(__name__)


@dataclass
class IndexProgress:
    total_files_discovered: int = 0
    files_indexed: int = 0
    chunks_indexed: int = 0
    errors: list[str] = field(default_factory=list)
    is_running: bool = False
    is_complete: bool = False


class IndexingPipeline:
    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

    def __init__(
        self,
        backend: AbstractFileIndexBackend,
        exclusion_rules: ExclusionRules,
        content_reader: ContentReaderDispatcher,
        chunker: TokenChunker,
        embedder: EmbeddingClient,
        filenames_repo: FilenamesRepo,
        chunks_repo: ChunksRepo,
        include_paths: list[Path] | None = None,
        disable_large_file_protection: bool = False,
    ) -> None:
        self._backend = backend
        self._exclusion_rules = exclusion_rules
        self._content_reader = content_reader
        self._chunker = chunker
        self._embedder = embedder
        self._filenames_repo = filenames_repo
        self._chunks_repo = chunks_repo
        self._include_paths = include_paths or []
        self._disable_large_file_protection = disable_large_file_protection
        self._progress = IndexProgress()
        self._cancel_event = threading.Event()

    async def run_full_index(self) -> None:
        self._cancel_event.clear()
        self._progress = IndexProgress(is_running=True)
        logger.info("Starting full index run")

        try:
            include = [Path(p) for p in self._include_paths] if self._include_paths else None
            entries: list[FileEntry] = []
            for entry in self._backend.iter_all_files(self._exclusion_rules, include_paths=include):
                if self._cancel_event.is_set():
                    break
                entries.append(entry)
                self._progress.total_files_discovered += 1

            await self._index_filenames(entries)

            if self._content_reader._readers:
                await self._index_content(entries)

            self._progress.is_complete = True
        except Exception as e:
            logger.exception("Index run failed")
            self._progress.errors.append(str(e))
        finally:
            self._progress.is_running = False
            logger.info("Index run finished")

    async def _embed_with_fallback(
        self, texts: list[str]
    ) -> tuple[list[list[float]], list[dict]]:
        """Embed texts, returning (dense, sparse).

        When sparse_enabled, tries embed_with_sparse first.
        On failure (or when sparse not enabled), falls back to dense-only
        embed() — never returns zero vectors for the dense path.
        Returns empty sparse dicts when sparse is unavailable.
        """
        sparse_enabled = self._embedder.sparse_enabled
        dim = self._filenames_repo.embedding_dim

        if sparse_enabled:
            try:
                dense, sparse = await self._embedder.embed_with_sparse(texts)
                # Normalise: ensure sparse list length matches
                if not sparse:
                    sparse = [{} for _ in texts]
                return dense, sparse
            except Exception as ex:
                logger.warning(
                    "embed_with_sparse failed, falling back to dense: %s", ex
                )

        # Dense-only path (also the fallback from sparse failure)
        try:
            dense = await self._embedder.embed(texts)
        except Exception as ex:
            logger.error("embed() failed: %s", ex)
            return [], [{} for _ in texts]

        return dense, [{} for _ in texts]

    async def _index_filenames(self, entries: list[FileEntry]) -> None:
        import hashlib
        import time

        if not entries:
            return

        sparse_enabled = self._filenames_repo.sparse_enabled
        BATCH = 64

        for i in range(0, len(entries), BATCH):
            if self._cancel_event.is_set():
                break
            batch_entries = entries[i:i + BATCH]
            batch_paths = [str(e.path) for e in batch_entries]

            embeddings, sparse_vecs = await self._embed_with_fallback(batch_paths)
            if not embeddings:
                batch_desc = f"{batch_paths[0]} -> {batch_paths[-1]}"
                msg = f"Embed error filename batch skipped: {batch_desc}"
                logger.error(msg)
                self._progress.errors.append(msg)
                continue

            records = []
            now = time.time()
            for idx, (entry, emb) in enumerate(zip(batch_entries, embeddings)):
                file_id = hashlib.sha256(str(entry.path).encode()).hexdigest()
                record = {
                    "id": file_id,
                    "path": str(entry.path),
                    "name": entry.name,
                    "extension": entry.extension,
                    "size": entry.size,
                    "modified_at": entry.modified_at,
                    "indexed_at": now,
                    "name_embedding": emb,
                }
                if sparse_enabled:
                    record["name_sparse"] = sparse_vecs[idx] if idx < len(sparse_vecs) else {}
                records.append(record)
                self._progress.files_indexed += 1

            self._filenames_repo.upsert(records)
            await asyncio.sleep(0)

    async def _index_content(self, entries: list[FileEntry]) -> None:
        import hashlib
        import time

        sparse_enabled = self._chunks_repo.sparse_enabled

        for entry in entries:
            if self._cancel_event.is_set():
                break
            if not self._content_reader.can_read(entry.path):
                continue
            if (
                not self._disable_large_file_protection
                and entry.size > self.MAX_FILE_SIZE
            ):
                logger.warning(
                    "Skipping oversized file %s (%.1fMB)",
                    entry.path,
                    entry.size / 1024 / 1024,
                )
                continue
            try:
                text = self._content_reader.read_text(entry.path)
            except Exception as ex:
                self._progress.errors.append(f"Read error {entry.path}: {ex}")
                continue

            chunks = self._chunker.chunk(text)
            if not chunks:
                continue

            chunk_texts = [c.text for c in chunks]
            embeddings, sparse_vecs = await self._embed_with_fallback(chunk_texts)
            if not embeddings:
                msg = f"Embed error content file skipped: {entry.path}"
                logger.error(msg)
                self._progress.errors.append(msg)
                continue

            file_id = hashlib.sha256(str(entry.path).encode()).hexdigest()
            records = []
            now = time.time()
            for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                chunk_id = hashlib.sha256(
                    (str(entry.path) + str(chunk.chunk_index)).encode()
                ).hexdigest()
                record = {
                    "id": chunk_id,
                    "file_id": file_id,
                    "path": str(entry.path),
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                    "token_count": chunk.token_count,
                    "char_start": chunk.char_start,
                    "char_end": chunk.char_end,
                    "indexed_at": now,
                    "embedding": emb,
                }
                if sparse_enabled:
                    record["sparse_embedding"] = sparse_vecs[idx] if idx < len(sparse_vecs) else {}
                records.append(record)
                self._progress.chunks_indexed += 1

            self._chunks_repo.upsert_batch(records)
            await asyncio.sleep(0)

    async def index_single_file(self, path: Path) -> None:
        await self.reindex_file(path)

    async def reindex_file(self, path: Path) -> None:
        import hashlib
        import time

        path = Path(path)

        if self._exclusion_rules.is_excluded(path):
            return
        if self._include_paths and not self._is_included_path(path):
            return
        if not path.exists():
            await self.delete_file(path)
            return

        try:
            stat = path.stat()
        except OSError:
            return

        sparse_enabled = self._filenames_repo.sparse_enabled
        dense_list, sparse_list = await self._embed_with_fallback([str(path)])
        name_emb = dense_list[0] if dense_list else [0.0] * self._filenames_repo.embedding_dim

        file_id = hashlib.sha256(str(path).encode()).hexdigest()
        now = time.time()
        filename_record = {
            "id": file_id,
            "path": str(path),
            "name": path.name,
            "extension": path.suffix.lower(),
            "size": stat.st_size,
            "modified_at": stat.st_mtime,
            "indexed_at": now,
            "name_embedding": name_emb,
        }
        if sparse_enabled:
            filename_record["name_sparse"] = sparse_list[0] if sparse_list else {}
        self._filenames_repo.upsert([filename_record])

        self._chunks_repo.delete_by_file_id(file_id)
        if not self._content_reader.can_read(path):
            return
        if (
            not self._disable_large_file_protection
            and stat.st_size > self.MAX_FILE_SIZE
        ):
            logger.warning(
                "Skipping oversized file %s (%.1fMB)",
                path,
                stat.st_size / 1024 / 1024,
            )
            return

        try:
            text = self._content_reader.read_text(path)
        except Exception as ex:
            self._progress.errors.append(f"Read error {path}: {ex}")
            return

        chunks = self._chunker.chunk(text)
        if not chunks:
            return

        chunk_texts = [c.text for c in chunks]
        embeddings, chunk_sparse_vecs = await self._embed_with_fallback(chunk_texts)
        if not embeddings:
            msg = f"Embed error content file skipped: {path}"
            logger.error(msg)
            self._progress.errors.append(msg)
            return

        records = []
        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            chunk_id = hashlib.sha256(
                (str(path) + str(chunk.chunk_index)).encode()
            ).hexdigest()
            record = {
                "id": chunk_id,
                "file_id": file_id,
                "path": str(path),
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "token_count": chunk.token_count,
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
                "indexed_at": now,
                "embedding": emb,
            }
            if self._chunks_repo.sparse_enabled:
                record["sparse_embedding"] = chunk_sparse_vecs[idx] if idx < len(chunk_sparse_vecs) else {}
            records.append(record)

        self._chunks_repo.upsert_batch(records)

    async def delete_file(self, path: Path) -> None:
        import hashlib
        path = Path(path)
        file_id = hashlib.sha256(str(path).encode()).hexdigest()
        self._filenames_repo.delete_by_path(path)
        self._chunks_repo.delete_by_file_id(file_id)

    def _is_included_path(self, path: Path) -> bool:
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path

        for root in self._include_paths:
            try:
                normalized_root = root.resolve()
            except Exception:
                normalized_root = root
            try:
                resolved.relative_to(normalized_root)
                return True
            except ValueError:
                continue
        return False

    def get_progress(self) -> IndexProgress:
        return self._progress

    def cancel(self) -> None:
        self._cancel_event.set()
