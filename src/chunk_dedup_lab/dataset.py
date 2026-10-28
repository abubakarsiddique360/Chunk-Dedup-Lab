"""Deterministic datasets and edits, so the benchmark is reproducible everywhere."""

from __future__ import annotations

import random
from dataclasses import dataclass

WORDS = (
    "frame sensor payload checksum window offset buffer stream record invoice ledger account "
    "customer address detail summary region shard replica index chunk digest archive snapshot"
).split()


def sample_text(size: int, *, seed: int = 11) -> bytes:
    """Build roughly ``size`` bytes of wordy text with a fixed seed."""
    rng = random.Random(seed)
    parts: list[str] = []
    produced = 0
    while produced < size:
        word = rng.choice(WORDS)
        parts.append(word)
        produced += len(word) + 1
        if rng.random() < 0.08:
            parts.append("\n")
    return (" ".join(parts))[:size].encode("utf-8")


@dataclass(frozen=True)
class Edit:
    name: str
    offset: int
    payload: bytes
    delete: int = 0

    def apply(self, data: bytes) -> bytes:
        return data[: self.offset] + self.payload + data[self.offset + self.delete :]


def insertions(
    base: bytes, sizes: tuple[int, ...] = (1, 16, 64, 256, 4096)
) -> list[tuple[str, bytes]]:
    """One insertion of ``size`` bytes near the front of the file, for each size."""
    versions = []
    for size in sizes:
        payload = b"X" * size
        versions.append((f"insert {size} B at 1 KiB", base[:1024] + payload + base[1024:]))
    return versions


def edits(base: bytes) -> list[tuple[str, bytes]]:
    """A realistic edit session: insert, delete, append, and a move."""
    head = base[: 64 * 1024]
    tail = base[64 * 1024 :]
    return [
        ("insert 1 B at 1 KiB", base[:1024] + b"X" + base[1024:]),
        ("insert 512 B at 40 KiB", base[: 40 * 1024] + b"Y" * 512 + base[40 * 1024 :]),
        ("delete 200 B at 90 KiB", base[: 90 * 1024] + base[90 * 1024 + 200 :]),
        ("append 4 KiB", base + sample_text(4 * 1024, seed=99)),
        (
            "move 4 KiB block",
            head[: 32 * 1024] + tail[: 4 * 1024] + head[32 * 1024 :] + tail[4 * 1024 :],
        ),
    ]
