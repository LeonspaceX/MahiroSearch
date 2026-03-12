import lancedb
from typing import Any

from .schema import make_chunks_schema


class ChunksRepo:
    TABLE_NAME = "content_chunks"

    def __init__(self, db: lancedb.DBConnection, embedding_dim: int = 1536, sparse_enabled: bool = False) -> None:
        self._db = db
        self.embedding_dim = embedding_dim
        self.sparse_enabled = sparse_enabled
        self.init_warnings: list[str] = []
        self._tbl = self._open_or_create()

    def _open_or_create(self) -> lancedb.table.Table:
        schema = make_chunks_schema(self.embedding_dim, self.sparse_enabled)
        try:
            tbl = self._db.open_table(self.TABLE_NAME)
            tbl.count_rows()  # Verify table is healthy
            return tbl
        except Exception as e:
            import logging
            logging.warning(f"Failed to open chunks table (will recreate): {e}")
            warning_msg = (
                f"Table '{self.TABLE_NAME}' schema mismatch or incompatible table detected; "
                f"auto rebuilding table. Error: {e}"
            )
            logging.warning(warning_msg)
            self.init_warnings.append(warning_msg)
            try:
                self._db.drop_table(self.TABLE_NAME)
            except Exception:
                pass
            return self._db.create_table(self.TABLE_NAME, schema=schema)

    def upsert_batch(self, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        batch_size = 500
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            try:
                self._tbl.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(batch)
            except Exception as e:
                import logging
                logging.warning(f"merge_insert failed for chunk batch {i}-{i+len(batch)}: {e}, falling back to add()")
                try:
                    self._tbl.add(batch)
                except Exception as e2:
                    logging.error(f"add() also failed: {e2}")
                    for record in batch:
                        try:
                            self._tbl.add([record])
                        except Exception:
                            continue

    def delete_by_file_id(self, file_id: str) -> None:
        try:
            self._tbl.delete(f"file_id = '{file_id}'")
        except Exception:
            pass

    def vector_search(self, query_vec: list[float], limit: int = 50) -> list[dict]:
        try:
            return (
                self._tbl.search(query_vec, vector_column_name="embedding")
                .select(["id", "file_id", "path", "chunk_index", "text", "_distance"])
                .limit(limit)
                .to_list()
            )
        except Exception as e:
            import logging
            logging.warning(f"Content vector search failed: {e}")
            return []

    def sparse_search(self, query_sparse: dict[str, float], limit: int = 50) -> list[dict]:
        """Search using sparse embedding (BGE-M3 only).

        LanceDB doesn't natively support sparse vector queries yet, so we
        approximate with a dot-product computed in Python over dense candidates
        retrieved via full-scan.  This is acceptable for moderate index sizes.
        When LanceDB adds native sparse support this can be replaced.
        """
        if not self.sparse_enabled or not query_sparse:
            return []
        try:
            # Pull all rows (path + sparse_embedding) – works for local indexes
            rows = (
                self._tbl.search()
                .select(["id", "file_id", "path", "chunk_index", "text", "sparse_embedding"])
                .limit(10000)
                .to_list()
            )
        except Exception as e:
            import logging
            logging.warning(f"Sparse chunk search fetch failed: {e}")
            return []

        scored: list[tuple[dict, float]] = []
        for row in rows:
            sparse = row.get("sparse_embedding") or {}
            # dot product
            score = sum(query_sparse.get(k, 0.0) * v for k, v in sparse.items())
            if score > 0:
                scored.append((row, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        results = []
        for row, score in scored[:limit]:
            row["_sparse_score"] = score
            results.append(row)
        return results

    def count(self) -> int:
        return self._tbl.count_rows()

    def drop(self) -> None:
        """Drop the table completely."""
        try:
            self._db.drop_table(self.TABLE_NAME)
        except Exception:
            pass
        self._tbl = self._open_or_create()

    def clear(self) -> None:
        """Delete all rows but keep the table."""
        try:
            self._tbl.delete("true")
        except Exception:
            pass

