import logging
from dataclasses import dataclass

from db.filenames_repo import FilenamesRepo
from db.chunks_repo import ChunksRepo
from embedding.client import EmbeddingClient

logger = logging.getLogger(__name__)


def reciprocal_rank_fusion(
    ranked_lists: list[list[tuple[str, float]]],
    k: int = 60,
    weights: list[float] | None = None,
) -> list[tuple[str, float]]:
    """
    Standard RRF: score(d) = sum_i( w_i / (k + rank_i(d)) )
    Returns sorted (path, fused_score) list, descending.
    """
    if weights is None:
        weights = [1.0] * len(ranked_lists)

    scores: dict[str, float] = {}
    for ranked, weight in zip(ranked_lists, weights):
        for rank, (path, _) in enumerate(ranked):
            scores[path] = scores.get(path, 0.0) + weight / (k + rank + 1)

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def filename_keyword_search(
    results: list[dict],
    query: str,
    limit: int = 50,
) -> list[tuple[str, float]]:
    """
    Simple substring match on filename, returns (path, score) list.
    Score is 1.0 for exact name match, 0.5 for substring match.
    """
    query_lower = query.lower()
    scored: list[tuple[str, float]] = []
    for row in results:
        name = row.get("name", "").lower()
        path = row.get("path", "")
        if not path:
            continue
        if name == query_lower:
            scored.append((path, 1.0))
        elif query_lower in name:
            scored.append((path, 0.5))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:limit]


@dataclass
class SearchResult:
    path: str
    name: str
    extension: str
    score: float
    snippet: str | None
    match_type: str  # "filename" | "content" | "hybrid"


class SearchEngine:
    def __init__(
        self,
        filenames_repo: FilenamesRepo,
        chunks_repo: ChunksRepo,
        embedder: EmbeddingClient,
        query_prefix_enabled: bool = False,
    ) -> None:
        self._filenames_repo = filenames_repo
        self._chunks_repo = chunks_repo
        self._embedder = embedder
        self._query_prefix_enabled = query_prefix_enabled

    def _apply_prefix(self, query: str) -> str:
        if self._query_prefix_enabled:
            return f"Represent this sentence for searching relevant passages: {query}"
        return query

    async def search(
        self,
        query: str,
        limit: int = 50,
        include_content: bool = True,
    ) -> list[SearchResult]:
        # Enforce max limit of 50
        limit = min(limit, 50)

        # 1. Embed query — dense always, sparse only when enabled
        query_vec: list[float] | None = None
        query_sparse: dict[str, float] = {}
        query_text = self._apply_prefix(query)

        try:
            if self._embedder.sparse_enabled:
                dense_list, sparse_list = await self._embedder.embed_with_sparse([query_text])
                query_vec = dense_list[0] if dense_list else None
                query_sparse = sparse_list[0] if sparse_list else {}
            else:
                embeddings = await self._embedder.embed([query_text])
                query_vec = embeddings[0] if embeddings else None
        except Exception as ex:
            logger.error("Embedding query failed: %s", ex)
            raise RuntimeError(f"Embedding query failed: {ex}") from ex

        ranked_lists: list[list[tuple[str, float]]] = []
        weights: list[float] = []

        # 2. Filename dense vector search
        if query_vec:
            try:
                vec_results = self._filenames_repo.vector_search(query_vec, limit=limit * 2)
                ranked_lists.append([(r["path"], r.get("_distance", 0.0)) for r in vec_results])
                weights.append(1.0)
            except Exception as ex:
                logger.warning("Filename vector search failed: %s", ex)

        # 3. Filename sparse search (BGE-M3 only, when enabled)
        if query_sparse:
            try:
                sparse_results = self._filenames_repo.sparse_search(query_sparse, limit=limit * 2)
                if sparse_results:
                    ranked_lists.append([(r["path"], r.get("_sparse_score", 0.0)) for r in sparse_results])
                    weights.append(0.9)
            except Exception as ex:
                logger.warning("Filename sparse search failed: %s", ex)

        # 4. Filename FTS / keyword search
        try:
            fts_raw = self._filenames_repo.search_by_name(query, limit=limit * 2)
            kw_ranked = filename_keyword_search(fts_raw, query, limit=limit * 2)
            if kw_ranked:
                ranked_lists.append(kw_ranked)
                weights.append(0.8)
        except Exception as ex:
            logger.warning("FTS search failed: %s", ex)

        # 5. Content dense vector search (optional)
        snippets: dict[str, str] = {}
        if include_content and query_vec:
            try:
                chunk_results = self._chunks_repo.vector_search(query_vec, limit=limit * 2)
                content_ranked = [(r["path"], r.get("_distance", 0.0)) for r in chunk_results]
                if content_ranked:
                    ranked_lists.append(content_ranked)
                    weights.append(0.9)
                for r in chunk_results:
                    path = r.get("path", "")
                    if path and path not in snippets:
                        text = r.get("text", "")
                        snippets[path] = text[:200].replace("\n", " ") if text else ""
            except Exception as ex:
                logger.warning("Content dense search failed: %s", ex)

        # 6. Content sparse search (BGE-M3 only, when enabled)
        if include_content and query_sparse:
            try:
                sparse_chunk_results = self._chunks_repo.sparse_search(query_sparse, limit=limit * 2)
                if sparse_chunk_results:
                    ranked_lists.append([(r["path"], r.get("_sparse_score", 0.0)) for r in sparse_chunk_results])
                    weights.append(0.85)
                for r in sparse_chunk_results:
                    path = r.get("path", "")
                    if path and path not in snippets:
                        text = r.get("text", "")
                        snippets[path] = text[:200].replace("\n", " ") if text else ""
            except Exception as ex:
                logger.warning("Content sparse search failed: %s", ex)

        if not ranked_lists:
            return []

        # 7. RRF fusion
        fused = reciprocal_rank_fusion(ranked_lists, weights=weights)

        # 8. Score threshold: filter out results with score < max_score * 0.5
        if fused:
            max_score = fused[0][1]
            threshold = max_score * 0.5
            fused = [(path, score) for path, score in fused if score >= threshold]

        # 9. Fetch metadata only for the paths we actually need (efficient!)
        fused_paths = [path for path, _ in fused[:limit]]
        path_meta = self._filenames_repo.get_by_paths(fused_paths)

        # 10. Build results
        results: list[SearchResult] = []
        for path, score in fused[:limit]:
            from pathlib import Path as PyPath
            p = PyPath(path)
            row = path_meta.get(path, {})
            snippet = snippets.get(path)
            match_type = "hybrid" if snippet else "filename"

            results.append(SearchResult(
                path=path,
                name=row.get("name", p.name),
                extension=row.get("extension", p.suffix.lower()),
                score=round(score, 4),
                snippet=snippet,
                match_type=match_type,
            ))

        return results
