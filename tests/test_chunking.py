import pytest

from chunk_dedup_lab.chunking import (
    Chunk,
    ChunkError,
    dedup,
    delta,
    fixed_chunks,
    gear_chunks,
)
from chunk_dedup_lab.dataset import edits, insertions, sample_text

BASE = sample_text(128 * 1024)


def test_fixed_chunks_cover_the_file_exactly():
    chunks = fixed_chunks(BASE, 4096)
    assert sum(chunk.length for chunk in chunks) == len(BASE)
    assert chunks[0].offset == 0
    assert all(previous.end == current.offset for previous, current in zip(chunks, chunks[1:],
                                                                        strict=False))


def test_fixed_chunks_last_chunk_is_short():
    chunks = fixed_chunks(b"x" * 5000, 4096)
    assert [chunk.length for chunk in chunks] == [4096, 904]


def test_fixed_chunks_rejects_zero_size():
    with pytest.raises(ChunkError, match="must be positive"):
        fixed_chunks(BASE, 0)


def test_identical_content_gives_identical_digests():
    first = fixed_chunks(b"abcabc", 3)
    second = fixed_chunks(b"abcabc", 3)
    assert [chunk.digest for chunk in first] == [chunk.digest for chunk in second]


def test_gear_chunks_cover_the_file_exactly():
    chunks = gear_chunks(BASE, bits=10, min_size=256, max_size=8192)
    assert sum(chunk.length for chunk in chunks) == len(BASE)
    assert chunks[0].offset == 0


def test_gear_chunks_respect_min_and_max():
    chunks = gear_chunks(BASE, bits=8, min_size=256, max_size=2048)
    assert all(256 <= chunk.length <= 2048 for chunk in chunks[:-1])


def test_gear_boundaries_are_reproducible():
    first = [(chunk.offset, chunk.length) for chunk in gear_chunks(BASE, bits=10, min_size=256)]
    second = [(chunk.offset, chunk.length) for chunk in gear_chunks(BASE, bits=10, min_size=256)]
    assert first == second


def test_gear_chunks_reject_bad_parameters():
    with pytest.raises(ChunkError, match="bits"):
        gear_chunks(BASE, bits=0)
    with pytest.raises(ChunkError, match="min_size"):
        gear_chunks(BASE, min_size=8)
    with pytest.raises(ChunkError, match="max_size"):
        gear_chunks(BASE, min_size=4096, max_size=4096)


def test_gear_resynchronises_after_a_one_byte_insertion():
    shifted = BASE[:1024] + b"X" + BASE[1024:]
    before = gear_chunks(BASE, bits=12)
    after = gear_chunks(shifted, bits=12)
    result = delta("insert", before, after)
    assert result.reuse > 0.9
    assert result.new_chunks <= 3


def test_fixed_chunks_do_not_resynchronise_after_one_byte():
    shifted = BASE[:1024] + b"X" + BASE[1024:]
    result = delta("insert", fixed_chunks(BASE, 4096), fixed_chunks(shifted, 4096))
    assert result.reuse < 0.05


def test_delta_counts_reused_bytes():
    old = [Chunk(offset=0, length=10, digest="a"), Chunk(offset=10, length=10, digest="b")]
    new = [Chunk(offset=0, length=10, digest="a"), Chunk(offset=10, length=5, digest="c")]
    result = delta("x", old, new)
    assert result.reused_bytes == 10
    assert result.new_bytes == 15
    assert result.new_chunks == 1
    assert result.reuse == pytest.approx(10 / 15)


def test_dedup_ratio_counts_unique_bytes_once():
    versions = [[Chunk(0, 10, "a"), Chunk(10, 10, "b")], [Chunk(0, 10, "a")]]
    result = dedup("x", versions, [20, 10])
    assert result.total_bytes == 30
    assert result.unique_bytes == 20
    assert result.unique_chunks == 2
    assert result.ratio == pytest.approx(20 / 30)


def test_dedup_handles_empty_input():
    result = dedup("empty", [[]], [0])
    assert result.ratio == 0.0
    assert result.chunk_count == 0


def test_sample_text_is_deterministic_and_sized():
    assert sample_text(1000) == sample_text(1000)
    assert len(sample_text(1000)) == 1000
    assert sample_text(1000, seed=5) != sample_text(1000, seed=6)


def test_edits_change_the_file():
    for label, payload in edits(BASE):
        assert isinstance(label, str)
        assert payload != BASE


def test_insertions_have_the_requested_size():
    for label, payload in insertions(BASE):
        size = int(label.split()[1])
        assert len(payload) == len(BASE) + size


def test_chunk_dataclass_end():
    assert Chunk(offset=5, length=3, digest="x").end == 8
