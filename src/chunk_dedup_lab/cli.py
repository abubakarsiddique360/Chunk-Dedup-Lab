"""Command line entry point for dedup-lab."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .bench import (
    Scenario,
    compare_methods,
    edit_reuse,
    insertion_curve,
    run_scenario,
    size_curve,
)
from .chunking import ChunkError, fixed_chunks, gear_chunks
from .dataset import sample_text
from .report import (
    render_chunks,
    render_compare,
    render_dedup,
    render_edit_reuse,
    render_insertion_curve,
    render_json,
    render_scenario,
    render_size_curve,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dedup-lab",
        description="Compare fixed-size and content-defined chunking on real edit sessions.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    bench = sub.add_parser("bench", help="one scenario: fixed against cdc")
    bench.add_argument("--size-kib", type=int, default=256)
    bench.add_argument("--fixed", type=int, default=4096)
    bench.add_argument("--bits", type=int, default=12)
    bench.add_argument("--format", choices=("text", "json"), default="text")

    cmp_cmd = sub.add_parser("compare", help="several chunkers over the same edit session")
    cmp_cmd.add_argument("--size-kib", type=int, default=256)
    cmp_cmd.add_argument("--format", choices=("text", "json"), default="text")

    ins = sub.add_parser("insertions", help="reuse against the size of one insertion")
    ins.add_argument("--size-kib", type=int, default=256)
    ins.add_argument("--bits", type=int, default=12)
    ins.add_argument("--format", choices=("text", "json"), default="text")

    edits_cmd = sub.add_parser("edits", help="reuse for each edit of a realistic session")
    edits_cmd.add_argument("--size-kib", type=int, default=256)
    edits_cmd.add_argument("--bits", type=int, default=12)
    edits_cmd.add_argument("--format", choices=("text", "json"), default="text")

    sizes = sub.add_parser("sizes", help="chunk counts against target chunk size")
    sizes.add_argument("--size-kib", type=int, default=256)
    sizes.add_argument("--format", choices=("text", "json"), default="text")

    chunks = sub.add_parser("chunks", help="show the first chunks of a sample file")
    chunks.add_argument("--size-kib", type=int, default=64)
    chunks.add_argument("--mode", choices=("fixed", "cdc"), default="cdc")
    chunks.add_argument("--fixed", type=int, default=4096)
    chunks.add_argument("--bits", type=int, default=10)
    chunks.add_argument("--limit", type=int, default=12)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "bench":
            payload = run_scenario(
                Scenario(
                    name=f"{args.size_kib} KiB with five edits",
                    base_size=args.size_kib * 1024,
                    fixed_size=args.fixed,
                    bits=args.bits,
                )
            )
            if args.format == "json":
                print(render_json(payload))
            else:
                print(render_scenario(payload))
            return 0

        if args.command == "compare":
            results = compare_methods(args.size_kib * 1024)
            if args.format == "json":
                print(render_json([result.as_dict() for result in results]))
            else:
                print(render_compare(results))
                print()
                print(render_dedup(results[0]))
            return 0

        if args.command == "insertions":
            rows = insertion_curve(args.size_kib * 1024, bits=args.bits)
            if args.format == "json":
                print(render_json(rows))
            else:
                print(render_insertion_curve(rows))
            return 0

        if args.command == "edits":
            rows = edit_reuse(args.size_kib * 1024, bits=args.bits)
            if args.format == "json":
                print(render_json(rows))
            else:
                print(render_edit_reuse(rows))
            return 0

        if args.command == "sizes":
            rows = size_curve(args.size_kib * 1024)
            if args.format == "json":
                print(render_json(rows))
            else:
                print(render_size_curve(rows))
            return 0

        if args.command == "chunks":
            data = sample_text(args.size_kib * 1024)
            chunks = (
                fixed_chunks(data, args.fixed)
                if args.mode == "fixed"
                else gear_chunks(data, bits=args.bits, min_size=256, max_size=16384)
            )
            print(
                f"{len(chunks)} chunks from {len(data):,} bytes "
                f"({len(data) / len(chunks):,.0f} bytes average)"
            )
            print()
            print(render_chunks(chunks, args.limit))
            return 0
    except ChunkError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
