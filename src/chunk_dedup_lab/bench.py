"""Benchmarks that compare fixed and content-defined chunking on the same edit sessions."""

from __future__ import annotations

from dataclasses import dataclass

from .chunking import Chunk, DedupResult, dedup, delta, fixed_chunks, gear_chunks
from .dataset import edits, insertions, sample_text


@dataclass(frozen=True)
class Scenario:
    name: str
    base_size: int
    fixed_size: int = 4096
    bits: int = 12

    def run(self) -> dict:
        base = sample_text(self.base_size)
        versions = [("original", base), *edits(base)]
        sizes = [len(payload) for _label, payload in versions]

        fixed = dedup(
            f"fixed {self.fixed_size // 1024} KiB",
            [fixed_chunks(payload, self.fixed_size) for _label, payload in versions],
            sizes,
        )
        cdc = dedup(
            f"cdc 2^{self.bits}",
            [gear_chunks(payload, bits=self.bits) for _label, payload in versions],
            sizes,
        )
        return {"scenario": self.name, "fixed": fixed.as_dict(), "cdc": cdc.as_dict()}


def run_scenario(scenario: Scenario) -> dict:
    return scenario.run()


def insertion_curve(base_size: int = 256 * 1024, bits: int = 12) -> list[dict]:
    """Bytes that must be re-uploaded after a single insertion near the start of the file."""
    base = sample_text(base_size)
    base_fixed = fixed_chunks(base, 4096)
    base_cdc = gear_chunks(base, bits=bits)
    rows = []
    for label, payload in insertions(base):
        fixed = delta("fixed", base_fixed, fixed_chunks(payload, 4096))
        cdc = delta("cdc", base_cdc, gear_chunks(payload, bits=bits))
        rows.append(
            {
                "insert": int(label.split()[1]),
                "fixed_reuse": round(fixed.reuse, 4),
                "cdc_reuse": round(cdc.reuse, 4),
                "fixed_chunks": len(fixed_chunks(payload, 4096)),
                "cdc_chunks": len(gear_chunks(payload, bits=bits)),
            }
        )
    return rows


def edit_reuse(base_size: int = 256 * 1024, bits: int = 12) -> list[dict]:
    """Per-edit delta reuse for the five-edit session."""
    base = sample_text(base_size)
    base_fixed = fixed_chunks(base, 4096)
    base_cdc = gear_chunks(base, bits=bits)
    rows = []
    for label, payload in edits(base):
        fixed = delta("fixed", base_fixed, fixed_chunks(payload, 4096))
        cdc = delta("cdc", base_cdc, gear_chunks(payload, bits=bits))
        rows.append(
            {
                "edit": label,
                "fixed_reuse": round(fixed.reuse, 4),
                "cdc_reuse": round(cdc.reuse, 4),
                "fixed_new_chunks": fixed.new_chunks,
                "cdc_new_chunks": cdc.new_chunks,
            }
        )
    return rows


def size_curve(base_size: int = 256 * 1024) -> list[dict]:
    """Chunk count and average size for a range of target chunk sizes, both methods."""
    base = sample_text(base_size)
    rows = []
    for power in range(9, 17):
        target = 1 << power
        fixed: list[Chunk] = fixed_chunks(base, target)
        cdc: list[Chunk] = gear_chunks(base, bits=power, min_size=max(64, target // 4),
                                       max_size=target * 4)
        rows.append(
            {
                "target": target,
                "fixed_count": len(fixed),
                "cdc_count": len(cdc),
                "cdc_avg": round(len(base) / len(cdc), 1),
                "cdc_min": min(chunk.length for chunk in cdc),
                "cdc_max": max(chunk.length for chunk in cdc),
            }
        )
    return rows


def compare_methods(base_size: int = 256 * 1024) -> list[DedupResult]:
    base = sample_text(base_size)
    versions = [base, *[payload for _label, payload in edits(base)]]
    sizes = [len(payload) for payload in versions]
    return [
        dedup("fixed 4 KiB", [fixed_chunks(payload, 4096) for payload in versions], sizes),
        dedup("cdc 2^10", [gear_chunks(payload, bits=10, min_size=256, max_size=16384)
                           for payload in versions], sizes),
        dedup("cdc 2^12", [gear_chunks(payload, bits=12) for payload in versions], sizes),
        dedup("cdc 2^14", [gear_chunks(payload, bits=14, min_size=8192, max_size=131072)
                           for payload in versions], sizes),
    ]
