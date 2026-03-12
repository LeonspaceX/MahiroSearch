import pyarrow as pa


def make_filenames_schema(embedding_dim: int = 1536, sparse_enabled: bool = False) -> pa.Schema:
    fields = [
        pa.field("id",            pa.utf8()),
        pa.field("path",          pa.utf8()),
        pa.field("name",          pa.utf8()),
        pa.field("extension",     pa.utf8()),
        pa.field("size",          pa.int64()),
        pa.field("modified_at",   pa.float64()),
        pa.field("indexed_at",    pa.float64()),
        pa.field("name_embedding", pa.list_(pa.float32(), embedding_dim)),
    ]
    if sparse_enabled:
        # Sparse embedding stored as map<string, float32>
        # Keys are token ids (as strings), values are weights.
        fields.append(pa.field("name_sparse", pa.map_(pa.utf8(), pa.float32())))
    return pa.schema(fields)


def make_chunks_schema(embedding_dim: int = 1536, sparse_enabled: bool = False) -> pa.Schema:
    fields = [
        pa.field("id",          pa.utf8()),
        pa.field("file_id",     pa.utf8()),
        pa.field("path",        pa.utf8()),
        pa.field("chunk_index", pa.int32()),
        pa.field("text",        pa.utf8()),
        pa.field("token_count", pa.int32()),
        pa.field("char_start",  pa.int64()),
        pa.field("char_end",    pa.int64()),
        pa.field("indexed_at",  pa.float64()),
        pa.field("embedding",   pa.list_(pa.float32(), embedding_dim)),
    ]
    if sparse_enabled:
        fields.append(pa.field("sparse_embedding", pa.map_(pa.utf8(), pa.float32())))
    return pa.schema(fields)
