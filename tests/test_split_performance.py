"""Regression tests for efficient compressed payload splitting."""

import hashlib
from pathlib import Path

from build_ai_context.models import SourceFile
import build_ai_context.writing as writing


def test_split_compresses_each_final_payload_once(tmp_path, monkeypatch):
    """Splitting compresses each final payload once without candidate recompression."""
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
    manifest_path = writing.write_bundles_and_manifest(
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

    import json

    manifest = json.loads(manifest_path.read_text())
    assert compression_count <= len(sources) + 1


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


def test_split_transport_reassembles_single_file_larger_than_payload_limit(tmp_path):
    """One large incompressible source is split into safe members and restored byte-for-byte."""
    import base64
    import io
    import json
    import tarfile

    root = tmp_path / "project"
    root.mkdir()
    data = bytes(range(256)) * 256
    path = root / "large.sqlite3"
    path.write_bytes(data)
    source = SourceFile(
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
    output = tmp_path / "output"
    manifest_path = writing.write_bundles_and_manifest(
        root=root,
        selected_files=[source],
        transport_files=[source],
        bundles=[],
        output_dir=output,
        max_lines=8000,
        max_file_lines=3000,
        skipped_reasons={},
        selection_metadata={},
        skip_secret_files=True,
        skipped_during_pack=[],
        timestamp="20261112T120000",
        transport="tar-gz",
        split=True,
        split_payload_max_bytes=16_384,
    )

    manifest = json.loads(manifest_path.read_text())
    assert manifest["schema_version"] == 5
    assert manifest["transported_files"] == ["large.sqlite3"]
    record = manifest["transport"]["reassembly"][0]
    members = {}
    for payload in manifest["transport"]["payloads"]:
        raw = (output / payload["payload"]).read_bytes()
        _, body = raw.split(b"\n\n", 1)
        archive_bytes = base64.b64decode(b"".join(body.split()), validate=True)
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
            for member in archive.getmembers():
                members[member.name] = archive.extractfile(member).read()
    restored = b"".join(members[name] for name in record["members"])
    assert restored == data
    assert all(
        (output / payload["payload"]).stat().st_size <= 16_384
        for payload in manifest["transport"]["payloads"]
    )


def test_compressibility_estimates_keep_split_payloads_well_filled(tmp_path):
    """Highly compressible files are packed by estimated output size, not raw bytes."""
    import json

    root = tmp_path / "project"
    root.mkdir()
    sources = []
    for index in range(40):
        data = ((f"record-{index:03d},value\n" * 4000).encode("utf-8"))
        path = root / f"item-{index:03d}.json"
        path.write_bytes(data)
        sources.append(
            SourceFile(
                abs_path=path,
                rel_path=Path(path.name),
                category="config_docs",
                line_count=4000,
                size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                lines=[],
                encoding="text",
                snapshot_bytes=data,
                mode=0o644,
            )
        )

    manifest_path = writing.write_bundles_and_manifest(
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
        timestamp="20261112T120000",
        transport="tar-gz",
        split=True,
        split_payload_max_bytes=1_000_000,
    )

    manifest = json.loads(manifest_path.read_text())
    assert manifest["payload_count"] <= 2
    assert all(
        payload["payload_size_bytes"] <= 1_000_000
        for payload in manifest["transport"]["payloads"]
    )


def test_best_fit_packing_avoids_tiny_sequential_tail_payload(tmp_path):
    """Mixed compressibility is balanced across payloads instead of leaving a tiny tail."""
    import json

    root = tmp_path / "project"
    root.mkdir()
    sources = []
    sizes = [780_000, 760_000, 740_000, 520_000, 500_000, 480_000, 260_000]
    for index, size in enumerate(sizes):
        pattern = bytes(((index * 31 + offset) % 251 for offset in range(4096)))
        data = (pattern * ((size + len(pattern) - 1) // len(pattern)))[:size]
        path = root / f"item-{index:02d}.bin"
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

    manifest_path = writing.write_bundles_and_manifest(
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
        timestamp="20261112T120000",
        transport="tar-gz",
        split=True,
        split_payload_max_bytes=18_000,
    )

    manifest = json.loads(manifest_path.read_text())
    payload_sizes = [
        payload["payload_size_bytes"] for payload in manifest["transport"]["payloads"]
    ]
    assert max(payload_sizes) <= 18_000
    assert min(payload_sizes) >= max(payload_sizes) * 0.35


def test_actual_size_consolidation_merges_underfilled_payloads(tmp_path):
    """Actual compressed sizes merge groups that conservative estimates left underfilled."""
    import json

    root = tmp_path / "project"
    root.mkdir()
    sources = []
    for index in range(12):
        data = ((f"highly-compressible-{index:02d}\n" * 20_000).encode("utf-8"))
        path = root / f"item-{index:02d}.json"
        path.write_bytes(data)
        sources.append(
            SourceFile(
                abs_path=path,
                rel_path=Path(path.name),
                category="config_docs",
                line_count=20_000,
                size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                lines=[],
                encoding="text",
                snapshot_bytes=data,
                mode=0o644,
            )
        )

    manifest_path = writing.write_bundles_and_manifest(
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
        timestamp="20261112T120000",
        transport="tar-gz",
        split=True,
        split_payload_max_bytes=45_000,
    )

    manifest = json.loads(manifest_path.read_text())
    payload_sizes = [
        payload["payload_size_bytes"] for payload in manifest["transport"]["payloads"]
    ]
    assert len(payload_sizes) <= 5
    assert max(payload_sizes) <= 45_000


def test_calibrated_repacking_redistributes_underfilled_payloads(tmp_path):
    """Aggregate compression calibration reduces fragmented initial packing."""
    import json

    root = tmp_path / "project"
    root.mkdir()
    sources = []
    for index in range(48):
        repeat = 3000 + ((index % 7) * 400)
        data = ((f"screen-{index:02d},action,value\n" * repeat).encode("utf-8"))
        path = root / f"screen-{index:02d}.json"
        path.write_bytes(data)
        sources.append(
            SourceFile(
                abs_path=path,
                rel_path=Path(path.name),
                category="config_docs",
                line_count=repeat,
                size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                lines=[],
                encoding="text",
                snapshot_bytes=data,
                mode=0o644,
            )
        )

    manifest_path = writing.write_bundles_and_manifest(
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
        timestamp="20261112T120000",
        transport="tar-gz",
        split=True,
        split_payload_max_bytes=45_000,
    )

    manifest = json.loads(manifest_path.read_text())
    payload_sizes = [
        payload["payload_size_bytes"] for payload in manifest["transport"]["payloads"]
    ]
    assert len(payload_sizes) <= 3
    assert max(payload_sizes) <= 45_000


def test_exact_member_stream_packing_fills_payloads_without_recompression(tmp_path):
    """Independent gzip members provide additive weights and tightly packed payloads."""
    import base64
    import json
    import gzip

    root = tmp_path / "project"
    root.mkdir()
    sources = []
    for index in range(24):
        data = bytes(((index * 17 + offset) % 251 for offset in range(12_000)))
        path = root / f"item-{index:02d}.bin"
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

    output = tmp_path / "output"
    manifest_path = writing.write_bundles_and_manifest(
        root=root,
        selected_files=sources,
        transport_files=sources,
        bundles=[],
        output_dir=output,
        max_lines=8000,
        max_file_lines=3000,
        skipped_reasons={},
        selection_metadata={},
        skip_secret_files=True,
        skipped_during_pack=[],
        timestamp="20261112T120000",
        transport="tar-gz",
        split=True,
        split_payload_max_bytes=8_000,
    )

    manifest = json.loads(manifest_path.read_text())
    for payload in manifest["transport"]["payloads"]:
        raw = (output / payload["payload"]).read_bytes()
        _, body = raw.split(b"\n\n", 1)
        archive_bytes = base64.b64decode(b"".join(body.split()), validate=True)
        assert gzip.decompress(archive_bytes)
        assert len(raw) <= 8_000
    payload_sizes = [
        payload["payload_size_bytes"] for payload in manifest["transport"]["payloads"]
    ]
    assert all(size <= 8_000 for size in payload_sizes)
