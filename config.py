from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class EmbeddingConfig(BaseModel):
    api_base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    # Prepend BGE-M3 query prefix to improve retrieval quality.
    query_prefix_enabled: bool = False
    # BGE-M3 sparse embedding switch — only enable when the API supports
    # the return_sparse extension (e.g. SiliconFlow + BAAI/bge-m3).
    enable_sparse: bool = False


class IndexingConfig(BaseModel):
    enable_content_docs: bool = False
    enable_content_code: bool = False
    chunk_size_tokens: int = 512
    chunk_overlap_tokens: int = 64
    disable_large_file_protection: bool = False
    user_exclusions: list[str] = Field(default_factory=list)
    include_paths: list[str] = Field(default_factory=list)


class AppConfig(BaseModel):
    auto_start: bool = False
    auto_index_new_files: bool = False
    data_dir: Path = Path("data")
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    indexing: IndexingConfig = Field(default_factory=IndexingConfig)

    @classmethod
    def load(cls) -> "AppConfig":
        """Load configuration from config.yaml."""
        yaml_path = Path("config.yaml")
        yaml_data: dict = {}

        # Auto-generate config.yaml on first run.
        if not yaml_path.exists():
            try:
                default_cfg = cls()
                yaml_data = {
                    "app": {
                        "auto_start": default_cfg.auto_start,
                        "auto_index_new_files": default_cfg.auto_index_new_files,
                        "data_dir": str(default_cfg.data_dir),
                    },
                    "embedding": {
                        "api_base_url": default_cfg.embedding.api_base_url,
                        "api_key": default_cfg.embedding.api_key,
                        "model": default_cfg.embedding.model,
                        "embedding_dim": default_cfg.embedding.embedding_dim,
                        "query_prefix_enabled": default_cfg.embedding.query_prefix_enabled,
                        "enable_sparse": default_cfg.embedding.enable_sparse,
                    },
                    "indexing": {
                        "enable_content_docs": default_cfg.indexing.enable_content_docs,
                        "enable_content_code": default_cfg.indexing.enable_content_code,
                        "chunk_size_tokens": default_cfg.indexing.chunk_size_tokens,
                        "chunk_overlap_tokens": default_cfg.indexing.chunk_overlap_tokens,
                        "disable_large_file_protection": default_cfg.indexing.disable_large_file_protection,
                        "user_exclusions": default_cfg.indexing.user_exclusions,
                        "include_paths": default_cfg.indexing.include_paths,
                    },
                }
                with yaml_path.open("w", encoding="utf-8") as f:
                    yaml.safe_dump(yaml_data, f, allow_unicode=True, sort_keys=False)
            except Exception:
                yaml_data = {}
        else:
            try:
                with yaml_path.open("r", encoding="utf-8") as f:
                    yaml_data = yaml.safe_load(f) or {}
            except Exception:
                pass

        # Extract top-level fields
        top_level = {
            "auto_start": yaml_data.get("app", {}).get("auto_start", False),
            "auto_index_new_files": yaml_data.get("app", {}).get("auto_index_new_files", False),
            "data_dir": Path(yaml_data.get("app", {}).get("data_dir", "data")),
        }

        # Extract embedding config
        emb_data = yaml_data.get("embedding", {})
        embedding = EmbeddingConfig(
            api_base_url=emb_data.get("api_base_url", "https://api.openai.com/v1"),
            api_key=emb_data.get("api_key", ""),
            model=emb_data.get("model", "text-embedding-3-small"),
            embedding_dim=emb_data.get("embedding_dim", 1536),
            query_prefix_enabled=emb_data.get("query_prefix_enabled", False),
            enable_sparse=emb_data.get("enable_sparse", False),
        )

        # Extract indexing config
        idx_data = yaml_data.get("indexing", {})
        indexing = IndexingConfig(
            enable_content_docs=idx_data.get("enable_content_docs", False),
            enable_content_code=idx_data.get("enable_content_code", False),
            chunk_size_tokens=idx_data.get("chunk_size_tokens", 512),
            chunk_overlap_tokens=idx_data.get("chunk_overlap_tokens", 64),
            disable_large_file_protection=idx_data.get("disable_large_file_protection", False),
            user_exclusions=idx_data.get("user_exclusions", []),
            include_paths=idx_data.get("include_paths", []),
        )

        return cls(
            **top_level,
            embedding=embedding,
            indexing=indexing,
        )
