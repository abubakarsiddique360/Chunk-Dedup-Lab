"""Text reports for chunking benchmarks."""

from __future__ import annotations

import json

from .chunking import Chunk, DedupResult


def render_dedup(result: DedupResult) -> str:
    lines = [f"Deduplication: {result.label}", "=" * 58]
    lines.append(f"logical bytes     {result.total_bytes:,}")
    lines.append(f"stored bytes      {result.unique_bytes:,}")
    lines.append(f"chunks            {result.chunk_count:,} ({result.unique_chunks:,} unique)")
    lines.append(f"average chunk     {result.avg_chunk:,.0f} bytes")
    lines.append(f"ratio             {result.ratio:.3f}  (reuse {result.reuse * 100:.1f}%)")
    return "\n".join(lines)


def render_compare(results: list[DedupResult]) -> str:
    header = (
        f"{'method':<14}{'chunks':>9}{'unique':>9}{'avg':>8}{'ratio':>8}{'reuse':>8}"
    )
    lines = ["Same 6 versions, two families of chunker", "=" * len(header), header]
    for result in results:
        lines.append(
            f"{result.label[:13]:<14}{result.chunk_count:>9,}{result.unique_chunks:>9,}"
            f"{result.avg_chunk:>8,.0f}{result.ratio:>8.3f}{result.reuse * 100:>7.1f}%"
        )
    return "\n".join(lines)


def render_scenario(payload: dict) -> str:
    fixed = payload["fixed"]
    cdc = payload["cdc"]
    lines = [f"Scenario: {payload['scenario']}", "=" * 58]
    lines.append(f"{'':<10}{'fixed':>12}{'cdc':>12}")
    lines.append(f"{'chunks':<10}{fixed['chunk_count']:>12,}{cdc['chunk_count']:>12,}")
    lines.append(f"{'unique':<10}{fixed['unique_chunks']:>12,}{cdc['unique_chunks']:>12,}")
    lines.append(f"{'ratio':<10}{fixed['ratio']:>12.3f}{cdc['ratio']:>12.3f}")
    lines.append(f"{'reuse':<10}{fixed['reuse'] * 100:>11.1f}%{cdc['reuse'] * 100:>11.1f}%")
    return "\n".join(lines)


def render_insertion_curve(rows: list[dict]) -> str:
    header = (
        f"{'insert':>8}{'fixed reuse':>13}{'cdc reuse':>12}{'fixed chunks':>14}{'cdc chunks':>12}"
    )
    lines = ["One insertion, two chunkers", "=" * len(header), header]
    for row in rows:
        lines.append(
            f"{row['insert']:>8,}{row['fixed_reuse'] * 100:>12.1f}%{row['cdc_reuse'] * 100:>11.1f}%"
            f"{row['fixed_chunks']:>14,}{row['cdc_chunks']:>12,}"
        )
    lines.append("")
    lines.append("reuse = share of the new version the existing chunks already cover")
    return "\n".join(lines)


def render_edit_reuse(rows: list[dict]) -> str:
    header = f"{'edit':<24}{'fixed reuse':>13}{'cdc reuse':>12}{'fixed new':>11}{'cdc new':>9}"
    lines = ["Reuse per edit (what the backup would upload)", "=" * len(header), header]
    for row in rows:
        lines.append(
            f"{row['edit'][:23]:<24}{row['fixed_reuse'] * 100:>12.1f}%"
            f"{row['cdc_reuse'] * 100:>11.1f}%{row['fixed_new_chunks']:>11,}"
            f"{row['cdc_new_chunks']:>9,}"
        )
    lines.append("")
    lines.append("'new' = chunks the target already has something else for, i.e. must upload")
    return "\n".join(lines)


def render_size_curve(rows: list[dict]) -> str:
    header = f"{'target':>8}{'fixed':>9}{'cdc':>8}{'cdc avg':>10}{'cdc min':>9}{'cdc max':>9}"
    lines = ["Chunk counts against target size (256 KiB sample)", "=" * len(header), header]
    for row in rows:
        lines.append(
            f"{row['target']:>8,}{row['fixed_count']:>9,}{row['cdc_count']:>8,}"
            f"{row['cdc_avg']:>10,.0f}{row['cdc_min']:>9,}{row['cdc_max']:>9,}"
        )
    return "\n".join(lines)


def render_chunks(chunks: list[Chunk], limit: int = 12) -> str:
    lines = [f"{'#':>3}{'offset':>10}{'length':>9}  digest", "-" * 44]
    for index, chunk in enumerate(chunks[:limit], start=1):
        lines.append(f"{index:>3}{chunk.offset:>10,}{chunk.length:>9,}  {chunk.digest[:16]}")
    if len(chunks) > limit:
        lines.append(f"... {len(chunks) - limit} more chunks")
    return "\n".join(lines)


def render_json(payload) -> str:
    return json.dumps(payload, indent=2)
