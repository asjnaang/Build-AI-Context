"""Scale checks for graph import resolution and lighter scans."""

import hashlib
import time
from pathlib import Path

import pytest

from build_ai_context.graph import generate_graph
from build_ai_context.models import SourceFile
from build_ai_context.scanner import scan_supported_files


def _source(tmp_path: Path, rel: str, content: str, category: str) -> SourceFile:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    lines = content.splitlines()
    return SourceFile(
        abs_path=path,
        rel_path=Path(rel),
        category=category,
        line_count=len(lines),
        size_bytes=path.stat().st_size,
        sha256="test",
        lines=lines,
    )


def test_import_resolution_stays_correct_when_many_imports_miss(tmp_path):
    """Basename lookup must stay correct without scanning every path per import."""
    files = []
    for index in range(250):
        imports = "\n".join(f"import com.example.missing.Type{item}" for item in range(40))
        files.append(
            _source(
                tmp_path,
                f"feature/Mod{index}.kt",
                f"{imports}\nclass Mod{index} {{}}\n",
                "java_kotlin",
            )
        )
    files.append(_source(tmp_path, "core/UniqueHub.kt", "class UniqueHub {}\n", "java_kotlin"))
    files.append(
        _source(
            tmp_path,
            "app/Main.kt",
            "import com.example.UniqueHub\nclass Main {}\n",
            "java_kotlin",
        )
    )

    started = time.perf_counter()
    text = generate_graph(files, tmp_path)
    elapsed = time.perf_counter() - started

    assert "app/Main.kt --> core/UniqueHub.kt," in text
    assert elapsed < 0.75


def test_graph_read_mode_keeps_source_text_and_drops_binary_payload(tmp_path):
    """Graph scans need source text, not a full copy of unrelated binaries."""
    pdf = tmp_path / "docs" / "design.pdf"
    pdf.parent.mkdir()
    pdf.write_bytes(b"%PDF-1.4\n" + b"A" * 2_000_000)
    (tmp_path / "app.kt").write_text("class App {}\n")

    files, _skipped = scan_supported_files(tmp_path, skip_secret_files=True, read_mode="graph")
    by_name = {item.rel_path.name: item for item in files}

    assert "class App {}" in "\n".join(by_name["app.kt"].lines)
    assert by_name["design.pdf"].snapshot_bytes is None
    assert by_name["design.pdf"].lines == []


def test_paths_read_mode_matches_discovered_files_without_payloads(tmp_path):
    """A file tree needs the same paths and must not retain file bodies."""
    (tmp_path / "app.kt").write_text("class App {}\n")
    (tmp_path / "notes.md").write_text("hello\n")
    pdf = tmp_path / "design.pdf"
    pdf.write_bytes(b"%PDF" + b"B" * 500_000)

    full, full_skipped = scan_supported_files(tmp_path, skip_secret_files=True)
    light, light_skipped = scan_supported_files(
        tmp_path, skip_secret_files=True, read_mode="paths"
    )

    assert [item.rel_path.as_posix() for item in light] == [
        item.rel_path.as_posix() for item in full
    ]
    assert [item.category for item in light] == [item.category for item in full]
    assert light_skipped == full_skipped
    assert all(item.snapshot_bytes is None and item.lines == [] for item in light)
    assert any(item.snapshot_bytes for item in full)


def test_keyword_search_reads_snapshot_when_lines_are_not_stored(tmp_path):
    """Default tar-gz scans keep bytes, not line lists. Keywords still have to match."""
    from build_ai_context.scanner import filter_files_by_keywords

    (tmp_path / "app.kt").write_text("class Repository {}\n")
    files, _skipped = scan_supported_files(tmp_path, skip_secret_files=True, metadata_only=True)

    matched, words = filter_files_by_keywords(files, ["Repository"])

    assert [item.rel_path.name for item in matched] == ["app.kt"]
    assert words == ["repository"]


def test_rust_reader_matches_python_bytes_and_digest(tmp_path):
    """The optional Rust reader must return the same bytes, mode, and digest."""
    baic_native = pytest.importorskip("build_ai_context.baic_native")
    target = tmp_path / "sample.txt"
    payload = b"alpha\nbeta\n"
    target.write_bytes(payload)
    mode = target.stat().st_mode & 0o777

    loaded = baic_native.read_snapshots([str(target), str(tmp_path / "missing.txt")])

    assert loaded[1] is None
    got_mode, got_bytes, digest = loaded[0]
    assert got_mode == mode
    assert bytes(got_bytes) == payload
    assert digest == hashlib.sha256(payload).hexdigest()
