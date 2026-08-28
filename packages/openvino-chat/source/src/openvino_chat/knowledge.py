from __future__ import annotations

import hashlib
import json
import math
import os
import re
import zlib
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from openvino_chat.settings import (
    KNOWLEDGE_INDEX_PATH,
    RAG_EMBED_REPO,
    RAG_RERANK_REPO,
)


INDEX_VERSION = 1
MAX_FILE_BYTES = 2 * 1024 * 1024
DEFAULT_CHUNK_CHARS = 1200
DEFAULT_OVERLAP_CHARS = 160
SUPPORTED_EXTENSIONS = {
    ".c", ".cpp", ".cs", ".csv", ".go", ".h", ".hpp", ".htm", ".html",
    ".java", ".js", ".json", ".jsx", ".kt", ".md", ".ps1", ".py", ".rs",
    ".rst", ".sh", ".toml", ".ts", ".tsx", ".txt", ".yaml", ".yml",
}
IGNORED_DIRS = {
    ".git", ".idea", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv",
    "__pycache__", "build", "dist", "node_modules", "venv",
}


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    source: str
    text: str
    embedding: list[float] | None = None


@dataclass(frozen=True)
class KnowledgeMatch:
    source: str
    text: str
    score: float


@dataclass(frozen=True)
class IndexResult:
    files: int
    chunks: int
    semantic: bool


@dataclass(frozen=True)
class SetupStatus:
    embedding_ready: bool
    reranker_ready: bool


def chunk_text(
    text: str,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[str]:
    clean = str(text).replace("\r\n", "\n").replace("\r", "\n").strip()
    chunk_chars = max(80, int(chunk_chars))
    overlap_chars = max(0, min(int(overlap_chars), chunk_chars // 2))
    if not clean:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(clean):
        hard_end = min(len(clean), start + chunk_chars)
        end = hard_end
        if hard_end < len(clean):
            floor = start + chunk_chars // 2
            newline = clean.rfind("\n", floor, hard_end)
            space = clean.rfind(" ", floor, hard_end)
            boundary = max(newline, space)
            if boundary > start:
                end = boundary
        chunk = clean[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(clean):
            break
        next_start = max(start + 1, end - overlap_chars)
        while next_start < end and clean[next_start].isspace():
            next_start += 1
        start = next_start
    return chunks


class KnowledgeStore:
    def __init__(
        self,
        index_path: Path | None = None,
        models_dir: Path | None = None,
        device: str = "CPU",
    ) -> None:
        runtime_home = Path(os.environ.get("OPENVINO_HOME", KNOWLEDGE_INDEX_PATH.parent.parent))
        self.index_path = Path(
            index_path
            or os.environ.get("OPENVINO_CHAT_KNOWLEDGE_INDEX", runtime_home / "knowledge" / "index.json")
        )
        self.models_dir = Path(
            models_dir
            or os.environ.get("OPENVINO_CHAT_KNOWLEDGE_MODELS", runtime_home / "knowledge" / "models")
        )
        self.device = str(device).upper()
        self.embedding_model_dir = self.models_dir / "bge-base-en-v1.5-int8-ov"
        self.reranker_model_dir = self.models_dir / "bge-reranker-base-int8-ov"
        self._chunks: list[KnowledgeChunk] | None = None
        self._checkpoints: dict[str, bytes | None] = {}
        self._checkpoint_signature: tuple[int, int] | None = None
        self._checkpoint_key: str | None = None

    @property
    def chunk_count(self) -> int:
        return len(self._load())

    @property
    def embedding_ready(self) -> bool:
        return _openvino_model_ready(self.embedding_model_dir)

    @property
    def reranker_ready(self) -> bool:
        return _openvino_model_ready(self.reranker_model_dir)

    def setup(
        self,
        snapshot_download: Callable[..., str] | None = None,
    ) -> SetupStatus:
        downloader = snapshot_download or _snapshot_download
        self.models_dir.mkdir(parents=True, exist_ok=True)
        if not self.embedding_ready:
            downloader(
                repo_id=RAG_EMBED_REPO,
                local_dir=self.embedding_model_dir,
            )
        if not self.reranker_ready:
            downloader(
                repo_id=RAG_RERANK_REPO,
                local_dir=self.reranker_model_dir,
            )
        return SetupStatus(self.embedding_ready, self.reranker_ready)

    def add(self, path: Path | str) -> IndexResult:
        root = Path(path).expanduser().resolve()
        if not root.exists():
            raise FileNotFoundError(f"knowledge path missing: {root}")
        files = list(_document_files(root))
        old = self._load()
        replaced = {str(file.resolve()) for file in files}
        if root.is_dir():
            retained = [
                chunk for chunk in old
                if chunk.source not in replaced
                and not _is_below(chunk.source, root)
            ]
        else:
            retained = [chunk for chunk in old if chunk.source not in replaced]
        pending = self._chunks_from_files(files)
        pending, semantic = self._with_embeddings(pending)
        self._chunks = retained + pending
        self._save()
        indexed_files = len({chunk.source for chunk in pending})
        return IndexResult(indexed_files, len(pending), semantic)

    def reindex(self) -> IndexResult:
        files = [Path(source) for source in self.list_sources() if _supported_file(Path(source))]
        if not files:
            self.clear()
            return IndexResult(0, 0, False)
        pending = self._chunks_from_files(files)
        pending, semantic = self._with_embeddings(pending)
        self._chunks = pending
        self._save()
        return IndexResult(len({chunk.source for chunk in pending}), len(pending), semantic)

    @staticmethod
    def _chunks_from_files(files: Iterable[Path]) -> list[KnowledgeChunk]:
        pending: list[KnowledgeChunk] = []
        for file in files:
            text = _read_document(file)
            if text is None:
                continue
            source = str(file.resolve())
            for index, part in enumerate(chunk_text(text)):
                digest = hashlib.sha256(
                    f"{source}\0{index}\0{part}".encode("utf-8")
                ).hexdigest()[:20]
                pending.append(KnowledgeChunk(digest, source, part))
        return pending

    def _with_embeddings(
        self,
        chunks: list[KnowledgeChunk],
    ) -> tuple[list[KnowledgeChunk], bool]:
        if not chunks or not self.embedding_ready:
            return chunks, False
        vectors = self._embed_documents([chunk.text for chunk in chunks])
        if len(vectors) != len(chunks):
            return chunks, False
        return (
            [
                KnowledgeChunk(chunk.chunk_id, chunk.source, chunk.text, vector)
                for chunk, vector in zip(chunks, vectors)
            ],
            True,
        )

    def clear(self) -> None:
        self._chunks = []
        self.index_path.unlink(missing_ok=True)
        self._checkpoint_signature = (-1, -1)
        self._checkpoint_key = "missing"
        self._checkpoints.setdefault("missing", None)

    def checkpoint(self) -> str:
        try:
            stat = self.index_path.stat()
            signature = (stat.st_mtime_ns, stat.st_size)
            if signature == self._checkpoint_signature and self._checkpoint_key is not None:
                return self._checkpoint_key
            data = self.index_path.read_bytes()
        except OSError:
            key = "missing"
            self._checkpoints.setdefault(key, None)
            self._checkpoint_signature = (-1, -1)
            self._checkpoint_key = key
            return key
        key = hashlib.sha256(data).hexdigest()
        if key not in self._checkpoints:
            self._checkpoints[key] = zlib.compress(data, level=3)
        self._checkpoint_signature = signature
        self._checkpoint_key = key
        return key

    def restore_checkpoint(self, checkpoint: str) -> None:
        compressed = self._checkpoints.get(checkpoint)
        if compressed is None:
            self.index_path.unlink(missing_ok=True)
        else:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.index_path.with_suffix(self.index_path.suffix + ".restore")
            temporary.write_bytes(zlib.decompress(compressed))
            temporary.replace(self.index_path)
        self._chunks = None
        self._checkpoint_signature = None
        self._checkpoint_key = None

    def list_sources(self) -> list[str]:
        return sorted({chunk.source for chunk in self._load()}, key=str.lower)

    def search(self, query: str, limit: int = 4) -> list[KnowledgeMatch]:
        chunks = self._load()
        limit = max(1, int(limit))
        if not chunks or not str(query).strip():
            return []
        lexical = _lexical_scores(str(query), chunks)
        semantic: list[float] | None = None
        if self.embedding_ready and all(chunk.embedding for chunk in chunks):
            vectors = self._embed_query(str(query))
            if vectors:
                semantic = [_cosine(vectors, chunk.embedding or []) for chunk in chunks]
        ranked: list[tuple[int, float]] = []
        for index in range(len(chunks)):
            score = lexical[index]
            if semantic is not None:
                score = 0.35 * lexical[index] + 0.65 * max(0.0, semantic[index])
            if score > 0:
                ranked.append((index, score))
        ranked.sort(key=lambda item: item[1], reverse=True)
        candidates = ranked[: max(limit * 3, 10)]
        if self.reranker_ready and len(candidates) > 1:
            reranked = self._rerank(str(query), [chunks[index].text for index, _ in candidates])
            if reranked:
                candidates = [
                    (candidates[position][0], float(score))
                    for position, score in reranked
                    if 0 <= position < len(candidates)
                ]
        return [
            KnowledgeMatch(chunks[index].source, chunks[index].text, float(score))
            for index, score in candidates[:limit]
        ]

    def context_for(self, query: str, limit: int = 4) -> str:
        matches = self.search(query, limit=limit)
        return "\n\n".join(
            f"Source: {match.source}\n{match.text}" for match in matches
        )

    def _load(self) -> list[KnowledgeChunk]:
        if self._chunks is not None:
            return self._chunks
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
            if int(payload.get("version", 0)) != INDEX_VERSION:
                raise ValueError("unsupported knowledge index")
            self._chunks = [KnowledgeChunk(**item) for item in payload.get("chunks", [])]
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            self._chunks = []
        return self._chunks

    def _save(self) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": INDEX_VERSION,
            "chunks": [asdict(chunk) for chunk in (self._chunks or [])],
        }
        temporary = self.index_path.with_suffix(self.index_path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.index_path)
        self._checkpoint_signature = None
        self._checkpoint_key = None

    def _embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            import openvino_genai

            pipeline = openvino_genai.TextEmbeddingPipeline(
                str(self.embedding_model_dir), self.device
            )
            vectors: list[list[float]] = []
            for start in range(0, len(texts), 32):
                batch = pipeline.embed_documents(texts[start : start + 32])
                vectors.extend(_to_vector(item) for item in batch)
            return vectors
        except Exception:
            return []

    def _embed_query(self, text: str) -> list[float]:
        try:
            import openvino_genai

            pipeline = openvino_genai.TextEmbeddingPipeline(
                str(self.embedding_model_dir), self.device
            )
            return _to_vector(pipeline.embed_query(text))
        except Exception:
            return []

    def _rerank(self, query: str, texts: list[str]) -> list[tuple[int, float]]:
        try:
            import openvino_genai

            pipeline = openvino_genai.TextRerankPipeline(
                str(self.reranker_model_dir), self.device
            )
            return [(int(index), float(score)) for index, score in pipeline.rerank(query, texts)]
        except Exception:
            return []


def _document_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        if _supported_file(root):
            yield root
        return
    for path in root.rglob("*"):
        if any(part.lower() in IGNORED_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        if path.is_file() and _supported_file(path):
            yield path


def _supported_file(path: Path) -> bool:
    try:
        return path.suffix.lower() in SUPPORTED_EXTENSIONS and path.stat().st_size <= MAX_FILE_BYTES
    except OSError:
        return False


def _read_document(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:4096]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return data.decode("utf-8-sig")
        except UnicodeDecodeError:
            return None


def _is_below(source: str, root: Path) -> bool:
    try:
        Path(source).resolve().relative_to(root)
        return True
    except (OSError, ValueError):
        return False


def _tokens(text: str) -> list[str]:
    return re.findall(r"[\w.-]{2,}", text.lower(), flags=re.UNICODE)


def _lexical_scores(query: str, chunks: list[KnowledgeChunk]) -> list[float]:
    query_tokens = set(_tokens(query))
    if not query_tokens:
        return [0.0] * len(chunks)
    documents = [Counter(_tokens(chunk.text)) for chunk in chunks]
    frequencies = {
        token: sum(1 for document in documents if token in document)
        for token in query_tokens
    }
    maximum = 0.0
    scores: list[float] = []
    phrase = query.strip().lower()
    for chunk, document in zip(chunks, documents):
        score = 0.0
        for token in query_tokens:
            count = document.get(token, 0)
            if count:
                inverse = math.log((len(chunks) + 1) / (frequencies[token] + 0.5)) + 1.0
                score += inverse * (1.0 + math.log(count))
        if phrase and phrase in chunk.text.lower():
            score += 2.0
        scores.append(score)
        maximum = max(maximum, score)
    return [score / maximum if maximum else 0.0 for score in scores]


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def _to_vector(value: Any) -> list[float]:
    data = getattr(value, "data", value)
    if hasattr(data, "tolist"):
        data = data.tolist()
    while isinstance(data, (list, tuple)) and len(data) == 1 and isinstance(data[0], (list, tuple)):
        data = data[0]
    if not isinstance(data, (list, tuple)):
        return []
    try:
        return [float(item) for item in data]
    except (TypeError, ValueError):
        return []


def _openvino_model_ready(path: Path) -> bool:
    return path.is_dir() and any(path.glob("*.xml"))


def _snapshot_download(**kwargs: Any) -> str:
    from huggingface_hub import snapshot_download

    return str(snapshot_download(**kwargs))
