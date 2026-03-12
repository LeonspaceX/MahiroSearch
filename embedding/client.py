import httpx


class EmbeddingClient:
    """OpenAI-compatible embedding API client.

    When ``sparse_enabled=True`` the client will request BGE-M3's sparse
    embeddings alongside the dense ones.  The API must support the
    ``return_sparse`` extension (e.g. SiliconFlow / local BGE-M3 server).
    Falls back gracefully to dense-only if the response contains no sparse
    field.
    """

    def __init__(
        self,
        api_base_url: str,
        api_key: str,
        model: str,
        timeout: float = 30.0,
        sparse_enabled: bool = False,
    ) -> None:
        self._base = api_base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._model = model
        self._timeout = timeout
        self.sparse_enabled = sparse_enabled

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """POST /embeddings, return list of dense embedding vectors."""
        if not texts:
            return []
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base}/embeddings",
                json={"input": texts, "model": self._model},
                headers=self._headers,
            )
        response.raise_for_status()
        data = response.json()
        items = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in items]

    async def embed_with_sparse(
        self, texts: list[str]
    ) -> tuple[list[list[float]], list[dict[str, float]]]:
        """POST /embeddings with return_sparse=True (BGE-M3 extension).

        Returns:
            (dense_vectors, sparse_vectors)
            sparse_vectors is a list of dicts {token_id_str: weight}.
            Falls back to empty sparse dicts if the API doesn't support it.
        """
        if not texts:
            return [], []
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base}/embeddings",
                json={
                    "input": texts,
                    "model": self._model,
                    "return_sparse": True,
                },
                headers=self._headers,
            )
        response.raise_for_status()
        data = response.json()
        items = sorted(data["data"], key=lambda x: x["index"])
        dense = [item["embedding"] for item in items]
        sparse = [item.get("sparse_embedding") or {} for item in items]
        return dense, sparse

    async def aclose(self) -> None:
        pass  # 不再持有长连接，无需关闭
