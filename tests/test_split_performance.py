"""Regression tests for efficient compressed payload splitting."""

import hashlib
from pathlib import Path

from build_ai_context.models import SourceFile
import build_ai_context.writing as writing


def test_split_compression_work_is_logarithmic_per_part(tmp_path, monkeypatch):
    """Splitting must not rebuild a growing archive once for every source file."""
    root = tmp_path / "project"
    root.mkdir()
    sources = []
    for index in range(64):
        data = bytes(((index + offset) % 251 for offset in range(2048)))
        path = root / f"item-{index:03d}.bin"
        path.write_bytes(data)
        sources.append(
            SourceFile(
                abs_path=path,
                rel_path=Path(path.name),
                category="config_docs",
                line_count=0,
                size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                lines=[],
                encoding="base64",
                snapshot_bytes=data,
                mode=0o644,
            )
        )

    original = writing.gzip.GzipFile
    compression_count = 0

    class CountingGzipFile(original):
        def __init__(self, *args, **kwargs):
            nonlocal compression_count
            compression_count += 1
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(writing.gzip, "GzipFile", CountingGzipFile)
    writing.write_bundles_and_manifest(
        root=root,
        selected_files=sources,
        transport_files=sources,
        bundles=[],
        output_dir=tmp_path / "output",
        max_lines=8000,
        max_file_lines=3000,
        skipped_reasons={},
        selection_metadata={},
        skip_secret_files=True,
        skipped_during_pack=[],
        timestamp="20261030T120000",
        transport="tar-gz",
        split=True,
        split_payload_max_bytes=12_000,
    )

    assert compression_count < len(sources) // 2


def test_compressed_transport_uses_fast_native_zlib_level(tmp_path, monkeypatch):
    """Compressed transport uses zlib's fast level instead of CPU-heavy level 9."""
    root = tmp_path / "project"
    root.mkdir()
    data = bytes(range(256)) * 1024
    path = root / "payload.bin"
    path.write_bytes(data)
    source = SourceFile(
        abs_path=path, rel_path=Path(path.name), category="config_docs", line_count=0,
        size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), lines=[],
        encoding="base64", snapshot_bytes=data, mode=0o644,
    )
    original = writing.gzip.GzipFile
    levels = []

    class RecordingGzipFile(original):
        def __init__(self, *args, **kwargs):
            levels.append(kwargs.get("compresslevel"))
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(writing.gzip, "GzipFile", RecordingGzipFile)
    writing.write_bundles_and_manifest(
        root=root, selected_files=[source], transport_files=[source], bundles=[],
        output_dir=tmp_path / "output", max_lines=8000, max_file_lines=3000,
        skipped_reasons={}, selection_metadata={}, skip_secret_files=True,
        skipped_during_pack=[], timestamp="20261030T120000", transport="tar-gz",
    )

    assert levels == [writing.GZIP_COMPRESSLEVEL]
    assert writing.GZIP_COMPRESSLEVEL == 1
