"""Two ways to cut a file into chunks: at fixed offsets, or where the content says to.

Fixed chunking is a counter. Content-defined chunking is a rolling hash: a window slides over the
bytes and a boundary is declared when the hash matches a mask. The difference only shows up when
the file *changes*, which is what this module measures.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

# A deterministic gear table: the same 256 constants on every machine, so two runs of the same
# benchmark produce byte-identical boundaries.
GEAR = tuple(((index * 2654435761) & 0xFFFFFFFF) for index in range(256))


class ChunkError(ValueError):
    """Raised for impossible chunking parameters."""


@dataclass(frozen=True)
class Chunk:
    offset: int
    length: int
    digest: str

    @property
    def end(self) -> int:
        return self.offset + self.length


def _digest(data: bytes) -> str:
    return hashlib.blake2b(data, digest_size=12).hexdigest()


def fixed_chunks(data: bytes, size: int) -> list[Chunk]:
    if size <= 0:
        raise ChunkError("chunk size must be positive")
    return [
        Chunk(offset=start, length=min(size, len(data) - start),
              digest=_digest(data[start : start + size]))
        for start in range(0, len(data), size)
    ]


def gear_chunks(
    data: bytes, bits: int = 12, min_size: int = 2048, max_size: int = 65536
) -> list[Chunk]:
    """Content-defined chunking with a gear rolling hash (FastCDC's idea, simplified).

    A boundary is cut when ``hash & mask`` is zero, so the expected chunk length is
    ``2**bits`` bytes. The hash is seeded at each chunk start and rolled forward one byte at a
    time, which makes the whole pass linear in the file size - and, more importantly, makes a
    boundary depend only on the bytes since the previous boundary, so an edit perturbs one chunk
    or two rather than everything after it.
    """
    if not 1 <= bits <= 24:
        raise ChunkError("bits must be between 1 and 24")
    if min_size < 64:
        raise ChunkError("min_size must be at least 64 bytes")
    if max_size <= min_size:
        raise ChunkError("max_size must be greater than min_size")
    mask = (1 << bits) - 1
    chunks: list[Chunk] = []
    start = 0
    total = len(data)
    while start < total:
        limit = min(start + max_size, total)
        cursor = min(start + min_size, limit)
        value = 0
        end = limit
        while cursor < limit:
            value = ((value << 1) + GEAR[data[cursor]]) & 0xFFFFFFFF
            if value & mask == 0:
                end = cursor + 1
                break
            cursor += 1
        end = min(end, total)
        chunks.append(Chunk(offset=start, length=end - start, digest=_digest(data[start:end])))
        start = end
    return chunks


@dataclass(frozen=True)
class Delta:
    """How much of one new version an existing chunk set already covers."""

    label: str
    new_bytes: int
    reused_bytes: int
    new_chunks: int
    total_chunks: int

    @property
    def reuse(self) -> float:
        return self.reused_bytes / self.new_bytes if self.new_bytes else 0.0

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "new_bytes": self.new_bytes,
            "reused_bytes": self.reused_bytes,
            "new_chunks": self.new_chunks,
            "total_chunks": self.total_chunks,
            "reuse": round(self.reuse, 4),
        }


def delta(label: str, old: list[Chunk], new: list[Chunk]) -> Delta:
    """Bytes of ``new`` that the chunk set of ``old`` already stores.

    This is the number a backup tool cares about: how much of *this* version has to be uploaded.
    """
    known = {chunk.digest for chunk in old}
    reused = sum(chunk.length for chunk in new if chunk.digest in known)
    return Delta(
        label=label,
        new_bytes=sum(chunk.length for chunk in new),
        reused_bytes=reused,
        new_chunks=sum(1 for chunk in new if chunk.digest not in known),
        total_chunks=len(new),
    )


@dataclass(frozen=True)
class DedupResult:
    label: str
    total_bytes: int
    chunk_count: int
    unique_chunks: int
    unique_bytes: int
    avg_chunk: float

    @property
    def ratio(self) -> float:
        """Stored bytes over logical bytes - lower is better, 1.0 means no deduplication."""
        return self.unique_bytes / self.total_bytes if self.total_bytes else 0.0

    @property
    def reuse(self) -> float:
        return 1.0 - self.ratio

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "total_bytes": self.total_bytes,
            "chunk_count": self.chunk_count,
            "unique_chunks": self.unique_chunks,
            "unique_bytes": self.unique_bytes,
            "avg_chunk": round(self.avg_chunk, 2),
            "ratio": round(self.ratio, 4),
            "reuse": round(self.reuse, 4),
        }


def dedup(label: str, versions: list[list[Chunk]], sizes: list[int]) -> DedupResult:
    seen: dict[str, int] = {}
    total = 0
    count = 0
    for chunks, size in zip(versions, sizes, strict=True):
        total += size
        count += len(chunks)
        for chunk in chunks:
            if chunk.digest not in seen:
                seen[chunk.digest] = chunk.length
    unique_bytes = sum(seen.values())
    return DedupResult(
        label=label,
        total_bytes=total,
        chunk_count=count,
        unique_chunks=len(seen),
        unique_bytes=unique_bytes,
        avg_chunk=total / count if count else 0.0,
    )
