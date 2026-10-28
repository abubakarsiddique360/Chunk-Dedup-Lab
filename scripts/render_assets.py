"""Regenerate README assets from real runs.

Usage:  python scripts/render_assets.py
Writes: docs/results.json, docs/images/edits.png,
        docs/images/insertion-curve.png, docs/images/chunk-map.png
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chunk_dedup_lab.bench import (  # noqa: E402
    compare_methods,
    edit_reuse,
    insertion_curve,
    size_curve,
)
from chunk_dedup_lab.chunking import fixed_chunks, gear_chunks  # noqa: E402
from chunk_dedup_lab.dataset import sample_text  # noqa: E402
from chunk_dedup_lab.report import (  # noqa: E402
    render_compare,
    render_edit_reuse,
    render_insertion_curve,
    render_size_curve,
)

BG = "#0d1117"
CHROME = "#161b22"
FG = "#e6edf3"
MUTED = "#8b949e"
ACCENT = "#79c0ff"
BASE_KIB = 256


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for name in ("consola.ttf", "courier.ttf", "DejaVuSansMono.ttf"):
        candidate = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def render_terminal(text: str, out_path: Path, title: str) -> None:
    font = load_font(15)
    lines = text.expandtabs(4).splitlines() or [""]
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    char_width = probe.textlength("M", font=font)
    line_height = 21
    pad = 24
    width = int(max(len(line) for line in lines) * char_width) + pad * 2
    height = pad * 2 + len(lines) * line_height + 44
    image = Image.new("RGB", (max(width, 800), height), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, image.width, 34], fill=CHROME)
    for index, color in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
        draw.ellipse([16 + index * 22, 10, 28 + index * 22, 22], fill=color)
    draw.text((92, 9), title, font=load_font(13), fill=MUTED)

    for row, line in enumerate(lines):
        color = FG
        stripped = line.strip()
        if line.startswith("$"):
            color = ACCENT
        elif stripped.startswith("cdc"):
            color = "#1a7f37"
        elif stripped.startswith("fixed"):
            color = "#cf222e"
        elif stripped.startswith(("method", "edit", "insert", "=")) or "Same" in stripped:
            color = MUTED
        draw.text((pad, 50 + row * line_height), line, font=font, fill=color)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path)


def render_insertion_plot(rows: list[dict], out_path: Path) -> None:
    sizes = [row["insert"] for row in rows]
    fixed = [row["fixed_reuse"] * 100 for row in rows]
    cdc = [row["cdc_reuse"] * 100 for row in rows]

    figure, axis = plt.subplots(figsize=(9.2, 3.8))
    figure.patch.set_facecolor("#ffffff")
    axis.plot(sizes, cdc, marker="o", color="#1a7f37", label="content-defined (2^12)")
    axis.plot(sizes, fixed, marker="s", color="#cf222e", label="fixed 4 KiB")
    axis.set_xscale("log", base=2)
    axis.set_xticks(sizes)
    axis.set_xticklabels([str(size) for size in sizes])
    axis.set_ylim(-5, 105)
    axis.set_xlabel("bytes inserted near the start of a 256 KiB file (log scale)")
    axis.set_ylabel("% of the new file already stored")
    heading = "A one-byte insertion re-uploads the whole file after fixed chunking"
    axis.set_title(heading, fontsize=10, loc="left")
    axis.grid(linestyle=":", alpha=0.45)
    axis.legend(fontsize=8, frameon=False, loc="center right")
    for spine in ("top", "right"):
        axis.spines[spine].set_visible(False)
    figure.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(out_path, format="png", dpi=150)
    plt.close(figure)


def render_edit_bars(rows: list[dict], out_path: Path) -> None:
    labels = [row["edit"] for row in rows]
    fixed = [row["fixed_reuse"] * 100 for row in rows]
    cdc = [row["cdc_reuse"] * 100 for row in rows]
    positions = range(len(labels))
    width = 0.38

    figure, axis = plt.subplots(figsize=(10.0, 4.0))
    figure.patch.set_facecolor("#ffffff")
    bars_fixed = axis.bar([p - width / 2 for p in positions], fixed, width, color="#cf222e",
                          label="fixed 4 KiB")
    bars_cdc = axis.bar([p + width / 2 for p in positions], cdc, width, color="#1a7f37",
                        label="content-defined 2^12")
    for bars in (bars_fixed, bars_cdc):
        for bar in bars:
            axis.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                      f"{bar.get_height():.0f}%", ha="center", fontsize=7, color="#24292f")
    axis.set_xticks(list(positions))
    axis.set_xticklabels([label.replace(" at ", "\nat ") for label in labels], fontsize=7)
    axis.set_ylim(0, 118)
    axis.set_ylabel("% of the edited file already stored")
    axis.set_title("Per edit: what the backup would actually upload", fontsize=10, loc="left")
    figure.legend(
        [bars_fixed, bars_cdc],
        ["fixed 4 KiB", "content-defined 2^12"],
        fontsize=8,
        frameon=False,
        ncol=2,
        loc="upper right",
        bbox_to_anchor=(0.995, 0.995),
    )
    axis.grid(axis="y", linestyle=":", alpha=0.45)
    for spine in ("top", "right"):
        axis.spines[spine].set_visible(False)
    figure.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(out_path, format="png", dpi=150)
    plt.close(figure)


def render_chunk_map(out_path: Path, size: int = 48 * 1024) -> None:
    base = sample_text(size)
    shifted = base[:1024] + b"X" + base[1024:]
    rows = [
        ("fixed 4 KiB, original", fixed_chunks(base, 4096), base),
        ("fixed 4 KiB, 1 byte inserted", fixed_chunks(shifted, 4096), shifted),
        ("cdc 2^12, original", gear_chunks(base, bits=12), base),
        ("cdc 2^12, 1 byte inserted", gear_chunks(shifted, bits=12), shifted),
    ]
    known = {
        "fixed": {chunk.digest for chunk in fixed_chunks(base, 4096)},
        "cdc": {chunk.digest for chunk in gear_chunks(base, bits=12)},
    }

    figure, axes = plt.subplots(len(rows), 1, figsize=(10.4, 0.75 * len(rows) + 1.2))
    figure.patch.set_facecolor("#ffffff")
    axes = list(axes)
    for axis, (label, chunks, data) in zip(axes, rows, strict=True):
        family = "fixed" if label.startswith("fixed") else "cdc"
        for chunk in chunks:
            reused = chunk.digest in known[family]
            axis.add_patch(
                Rectangle((chunk.offset, 0), chunk.length, 1,
                          facecolor="#1a7f37" if reused else "#cf222e",
                          alpha=0.75 if reused else 0.45, edgecolor="white", linewidth=0.5)
            )
        axis.set_xlim(0, len(data))
        axis.set_ylim(0, 1)
        axis.set_yticks([])
        axis.set_ylabel(label, rotation=0, ha="right", va="center", fontsize=7.5)
        axis.tick_params(axis="x", labelsize=6)
        for spine in ("top", "right", "left"):
            axis.spines[spine].set_visible(False)
    axes[-1].set_xlabel(
        "byte offset (green = chunk already stored, red = chunk that must be uploaded)"
    )
    figure.suptitle("Where the boundaries move when one byte is inserted at 1 KiB", fontsize=11,
                    x=0.02, ha="left")
    figure.tight_layout(rect=(0.02, 0, 1, 0.95))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(out_path, format="png", dpi=150)
    plt.close(figure)


def main() -> int:
    images = ROOT / "docs" / "images"
    images.mkdir(parents=True, exist_ok=True)
    os.chdir(ROOT)

    base_size = BASE_KIB * 1024
    compare = compare_methods(base_size)
    inserts = insertion_curve(base_size)
    edits_rows = edit_reuse(base_size)
    sizes = size_curve(base_size)

    payload = {
        "base_kib": BASE_KIB,
        "compare": [result.as_dict() for result in compare],
        "insertions": inserts,
        "edits": edits_rows,
        "sizes": sizes,
    }
    (ROOT / "docs" / "results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    terminal = (
        "$ dedup-lab compare --size-kib 256\n\n"
        + render_compare(compare)
        + "\n\n$ dedup-lab edits --size-kib 256\n\n"
        + render_edit_reuse(edits_rows)
        + "\n\n$ dedup-lab insertions --size-kib 256\n\n"
        + render_insertion_curve(inserts)
        + "\n\n$ dedup-lab sizes --size-kib 256\n\n"
        + render_size_curve(sizes[:4])
    )
    title = "dedup-lab  -  fixed vs content-defined chunking"
    render_terminal(terminal, images / "edits.png", title)
    render_insertion_plot(inserts, images / "insertion-curve.png")
    render_edit_bars(edits_rows, images / "edit-bars.png")
    render_chunk_map(images / "chunk-map.png")

    fixed = next(result for result in compare if result.label.startswith("fixed"))
    cdc = next(result for result in compare if result.label == "cdc 2^12")
    print(
        f"compare: fixed {fixed.reuse * 100:.1f}% reuse vs cdc12 {cdc.reuse * 100:.1f}% | "
        f"1-byte insert: fixed {inserts[0]['fixed_reuse'] * 100:.1f}% vs "
        f"cdc {inserts[0]['cdc_reuse'] * 100:.1f}%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
