"""Tests for oversized-file UX and non-interactive all-file exports."""
import json
from pathlib import Path

from build_ai_context.cli import build_parser, run_exporter
from build_ai_context.cli_ui import select_oversized_files_for_inclusion
from build_ai_context.exporter import CodeExporter
from build_ai_context.models import SourceFile


def _source(tmp_path: Path, name: str, line_count: int) -> SourceFile:
    path = tmp_path / name
    lines = [f"line_{index}" for index in range(line_count)]
    path.write_text("\n".join(lines))
    return SourceFile(
        abs_path=path,
        rel_path=Path(name),
        category="python",
        line_count=line_count,
        size_bytes=path.stat().st_size,
        sha256="test",
        lines=lines,
    )


def test_all_flag_enables_non_interactive_export():
    args = build_parser().parse_args(["--all"])
    assert args.non_interactive is True
    assert args.categories == []
    assert args.paths == []
    assert args.keywords == []


def test_oversized_prompt_enter_keeps_files_excluded(tmp_path, monkeypatch):
    source = _source(tmp_path, "large.py", 3001)
    exporter = CodeExporter()
    exporter._questionary_available = False
    monkeypatch.setattr("builtins.input", lambda _: "")

    selected = select_oversized_files_for_inclusion(
        [source],
        [{"path": "large.py", "reason": "large_file_exceeds_skip_threshold"}],
        exporter,
    )

    assert selected == []


def test_oversized_prompt_can_include_selected_file(tmp_path, monkeypatch):
    first = _source(tmp_path, "first.py", 3001)
    second = _source(tmp_path, "second.py", 3002)
    exporter = CodeExporter()
    exporter._questionary_available = False
    monkeypatch.setattr("builtins.input", lambda _: "2")

    selected = select_oversized_files_for_inclusion(
        [first, second],
        [
            {"path": "first.py", "reason": "large_file_exceeds_skip_threshold"},
            {"path": "second.py", "reason": "large_file_exceeds_skip_threshold"},
        ],
        exporter,
    )

    assert selected == [second]


def test_manifest_separates_included_warnings_from_actual_skips(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    warning_file = project / "warning.py"
    warning_file.write_text("\n".join(f"line_{index}" for index in range(1501)))
    skipped_file = project / "skipped.py"
    skipped_file.write_text("\n".join(f"line_{index}" for index in range(3001)))
    output = tmp_path / "output"
    args = build_parser().parse_args(
        [str(project), "--all", "--output-dir", str(output)]
    )

    result, _, _ = run_exporter(args, None)

    assert result == 0
    manifest = json.loads(next(output.glob("*_manifest_*.json")).read_text())
    assert manifest["summary"]["warning_count"] == 1
    assert manifest["summary"]["skipped_during_pack_count"] == 1
    assert manifest["warnings"][0]["path"] == "warning.py"
    assert manifest["warnings"][0]["reason"] == "large_file_warning"
    assert manifest["skipped_during_pack"][0]["path"] == "skipped.py"
    assert manifest["skipped_during_pack"][0]["reason"] == "large_file_exceeds_skip_threshold"
    bundle_text = "".join(path.read_text() for path in output.glob("*_bundle_*.txt"))
    assert "===== BEGIN FILE: warning.py =====" in bundle_text
    assert "===== BEGIN FILE: skipped.py =====" not in bundle_text


def test_interactive_export_can_force_include_oversized_file(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    oversized = project / "oversized.py"
    oversized.write_text("\n".join(f"line_{index}" for index in range(3001)))
    output = tmp_path / "output"
    args = build_parser().parse_args(
        [str(project), "--output-dir", str(output)]
    )

    def select_all(_exporter, files, _root):
        return list(files), {
            "selection_mode": "all",
            "selected_categories": [],
            "selected_paths": [],
            "name_filters": [],
            "missing_paths": [],
        }

    monkeypatch.setattr("build_ai_context.cli.render_category_table", lambda *_: None)
    monkeypatch.setattr("build_ai_context.cli.render_folder_table", lambda *_: None)
    monkeypatch.setattr("build_ai_context.cli.interactive_select_files", select_all)
    monkeypatch.setattr(
        "build_ai_context.cli.select_oversized_files_for_inclusion",
        lambda files, _items, _exporter: list(files),
    )

    result, _, _ = run_exporter(args, None)

    assert result == 0
    manifest = json.loads(next(output.glob("*_manifest_*.json")).read_text())
    assert manifest["summary"]["skipped_during_pack_count"] == 0
    assert manifest["skipped_during_pack"] == []
    assert manifest["warnings"][0]["path"] == "oversized.py"
    bundle_text = "".join(path.read_text() for path in output.glob("*_bundle_*.txt"))
    assert "===== BEGIN FILE: oversized.py =====" in bundle_text
