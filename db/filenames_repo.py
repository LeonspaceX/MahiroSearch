import lancedb
from pathlib import Path
from typing import Any

from .schema import make_filenames_schema


class FilenamesRepo:
    TABLE_NAME = "filenames"

    def __init__(self, db: lancedb.DBConnection, embedding_dim: int = 1536, sparse_enabled: bool = False) -> None:
        self._db = db
        self.embedding_dim = embedding_dim
        self.sparse_enabled = sparse_enabled
        self.init_warnings: list[str] = []
        self._tbl = self._open_or_create()

    def _open_or_create(self) -> lancedb.table.Table:
        schema = make_filenames_schema(self.embedding_dim, self.sparse_enabled)
        try:
            tbl = self._db.open_table(self.TABLE_NAME)
            # Verify table is healthy by doing a quick count
            tbl.count_rows()
            return tbl
        except Exception as e:
            import logging
            logging.warning(f"Failed to open table (will recreate): {e}")
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
            tbl = self._db.create_table(self.TABLE_NAME, schema=schema)
            # Create FTS index on name and path columns
            for field in ["name", "path"]:
                try:
                    tbl.create_fts_index(field)
                except Exception as fts_err:
                    logging.warning(f"Failed to create FTS index on {field}: {fts_err}")
            return tbl


    def upsert(self, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        batch_size = 1000
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            try:
                self._tbl.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(batch)
            except Exception as e:
                import logging
                logging.warning(f"merge_insert failed for batch {i}-{i+len(batch)}: {e}, falling back to add()")
                try:
                    self._tbl.add(batch)
                except Exception as e2:
                    logging.error(f"add() also failed: {e2}")
                    for record in batch:
                        try:
                            self._tbl.add([record])
                        except Exception:
                            continue

        # 重建 FTS 索引（数据变化后必须重建，否则 FTS 查不到新数据）
        # use_tantivy=False 时 field_names 只能传单个字符串
        for field in ["name", "path"]:
            try:
                self._tbl.create_fts_index(field, replace=True)
            except Exception as e:
                import logging
                logging.warning(f"Failed to rebuild FTS index on {field}: {e}")


    def delete_by_path(self, path: Path) -> None:
        self._tbl.delete(f"path = '{str(path)}'")

    def search_by_name(self, query: str, limit: int = 50) -> list[dict]:
        # 空 query 直接全表扫描，不走 FTS
        if not query.strip():
            try:
                return (
                    self._tbl.search()
                    .select(["id", "path", "name", "extension", "size"])
                    .limit(limit)
                    .to_list()
                )
            except Exception:
                return []
        try:
            results = (
                self._tbl.search(query, query_type="fts")
                .select(["id", "path", "name", "extension", "size", "_score"])
                .limit(limit)
                .to_list()
            )
            return results
        except Exception as e:
            import logging
            logging.warning(f"FTS search failed: {e}")
            try:
                safe_query = query.replace("'", "''")
                results = (
                    self._tbl.search()
                    .where(f"name LIKE '%{safe_query}%' OR path LIKE '%{safe_query}%'")
                    .select(["id", "path", "name", "extension", "size"])
                    .limit(limit)
                    .to_list()
                )
                return results
            except Exception as e2:
                import logging
                logging.error(f"Fallback search also failed: {e2}")
                return []

    def vector_search(self, query_vec: list[float], limit: int = 50) -> list[dict]:
        try:
            return (
                self._tbl.search(query_vec, vector_column_name="name_embedding")
                .select(["id", "path", "name", "extension", "size", "_distance"])
                .limit(limit)
                .to_list()
            )
        except Exception as e:
            import logging
            logging.warning(f"Vector search failed: {e}")
            return []

    def sparse_search(self, query_sparse: dict[str, float], limit: int = 50) -> list[dict]:
        """Filename sparse search (BGE-M3 only).

        Approximated via Python dot-product over all stored sparse embeddings.
        """
        if not self.sparse_enabled or not query_sparse:
            return []
        try:
            rows = (
                self._tbl.search()
                .select(["id", "path", "name", "extension", "size", "name_sparse"])
                .limit(10000)
                .to_list()
            )
        except Exception as e:
            import logging
            logging.warning(f"Sparse filename search fetch failed: {e}")
            return []

        scored: list[tuple[dict, float]] = []
        for row in rows:
            sparse = row.get("name_sparse") or {}
            score = sum(query_sparse.get(k, 0.0) * v for k, v in sparse.items())
            if score > 0:
                scored.append((row, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        results = []
        for row, score in scored[:limit]:
            row["_sparse_score"] = score
            results.append(row)
        return results

    def get_by_paths(self, paths: list[str]) -> dict[str, dict]:
        """Fetch metadata rows for a specific set of paths (efficient lookup).

        Uses a WHERE filter so we only scan matching rows, not the whole table.
        """
        if not paths:
            return {}
        try:
            # Build SQL IN list with safe quoting
            escaped = [p.replace("'", "''") for p in paths]
            in_clause = ", ".join(f"'{p}'" for p in escaped)
            rows = (
                self._tbl.search()
                .where(f"path IN ({in_clause})")
                .select(["id", "path", "name", "extension", "size"])
                .limit(len(paths))
                .to_list()
            )
            return {r["path"]: r for r in rows}
        except Exception:
            return {}


    def exists(self, file_id: str) -> bool:
        results = self._tbl.search().where(f"id = '{file_id}'").limit(1).to_list()
        return len(results) > 0

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
            self._tbl.delete("true")  # Delete all rows
        except Exception:
            pass
