from pathlib import Path
import re
from typing import Protocol, runtime_checkable


DOC_EXTENSIONS: frozenset[str] = frozenset([".pdf", ".docx", ".txt", ".md"])
CODE_EXTENSIONS: frozenset[str] = frozenset([
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cpp",
    ".c", ".h", ".hpp", ".go", ".rs", ".rb", ".php",
    ".swift", ".kt", ".cs", ".scala", ".r", ".lua",
    ".sh", ".bash", ".zsh", ".fish", ".ps1",
    ".yaml", ".yml", ".toml", ".json", ".xml",
    ".html", ".css", ".scss", ".sass", ".less",
    ".sql", ".graphql",
])


@runtime_checkable
class ContentReader(Protocol):
    def can_read(self, path: Path) -> bool: ...
    def read_text(self, path: Path) -> str: ...


class PdfReader:
    def can_read(self, path: Path) -> bool:
        return path.suffix.lower() == ".pdf"

    def read_text(self, path: Path) -> str:
        import pdfplumber
        pages: list[str] = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
        return "\n".join(pages)


class DocxReader:
    def can_read(self, path: Path) -> bool:
        return path.suffix.lower() == ".docx"

    def read_text(self, path: Path) -> str:
        from docx import Document
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text)


class PlainTextReader:
    EXTS: frozenset[str] = frozenset([".txt", ".md"])

    def can_read(self, path: Path) -> bool:
        return path.suffix.lower() in self.EXTS

    def read_text(self, path: Path) -> str:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="latin-1")

        if path.suffix.lower() == ".md":
            text = re.sub(r"#{1,6}\s*", "", text)
            text = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)
            text = re.sub(r"`{1,3}[^`]*`{1,3}", "", text)
            text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
            text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

        return text


class CodeReader:
    def can_read(self, path: Path) -> bool:
        return path.suffix.lower() in CODE_EXTENSIONS

    def read_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return path.read_text(encoding="latin-1")


class ContentReaderDispatcher:
    def __init__(self, enable_docs: bool, enable_code: bool) -> None:
        self._readers: list[ContentReader] = []
        if enable_docs:
            self._readers += [PdfReader(), DocxReader(), PlainTextReader()]
        if enable_code:
            self._readers.append(CodeReader())

    def can_read(self, path: Path) -> bool:
        return any(r.can_read(path) for r in self._readers)

    def read_text(self, path: Path) -> str:
        for r in self._readers:
            if r.can_read(path):
                return r.read_text(path)
        raise ValueError(f"No reader available for {path}")
