from dataclasses import dataclass
import tiktoken


@dataclass
class Chunk:
    text: str
    token_count: int
    char_start: int
    char_end: int
    chunk_index: int


class TokenChunker:
    def __init__(
        self,
        chunk_size: int = 512,
        overlap: int = 64,
        encoding_name: str = "cl100k_base",
    ) -> None:
        self._enc = tiktoken.get_encoding(encoding_name)
        self._chunk_size = chunk_size
        self._overlap = overlap

    def chunk(self, text: str) -> list[Chunk]:
        tokens = self._enc.encode(text)
        if not tokens:
            return []
        _, token_char_offsets = self._enc.decode_with_offsets(tokens)

        chunks: list[Chunk] = []
        step = self._chunk_size - self._overlap
        idx = 0
        chunk_index = 0

        while idx < len(tokens):
            end = min(idx + self._chunk_size, len(tokens))
            chunk_tokens = tokens[idx:end]
            chunk_text = self._enc.decode(chunk_tokens)

            char_start = token_char_offsets[idx]
            last_token_start = token_char_offsets[end - 1]
            last_token_length = len(self._enc.decode([tokens[end - 1]]))
            char_end = last_token_start + last_token_length

            chunks.append(Chunk(
                text=chunk_text,
                token_count=len(chunk_tokens),
                char_start=char_start,
                char_end=char_end,
                chunk_index=chunk_index,
            ))
            chunk_index += 1
            idx += step

        return chunks

    def count_tokens(self, text: str) -> int:
        return len(self._enc.encode(text))
