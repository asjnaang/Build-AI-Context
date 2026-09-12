"""Tests for oversized-file UX and non-interactive all-file exports."""
import json
import pytest
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


def test_task_flag_replaces_generated_prompt_placeholder(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text("print('hello')\n")
    output = tmp_path / "output"
    task = "Go through these files and fix the issues we discussed before."
    args = build_parser().parse_args(
        [str(project), "--all", "--output-dir", str(output), "--task", task]
    )

    result, _, _ = run_exporter(args, None)

    assert result == 0
    prompt = (output / "baic_prompt.md").read_text()
    assert task in prompt
    assert "[PASTE THE SPECIFIC FEATURE / BUGFIX / REFACTOR REQUEST HERE]" not in prompt
    assert f"## Task Contract\n\n```\n{task}\n```" in prompt


def test_generated_prompt_keeps_placeholder_without_task(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text("print('hello')\n")
    output = tmp_path / "output"
    args = build_parser().parse_args(
        [str(project), "--all", "--output-dir", str(output)]
    )

    result, _, _ = run_exporter(args, None)

    assert result == 0
    prompt = (output / "baic_prompt.md").read_text()
    assert "[PASTE THE SPECIFIC FEATURE / BUGFIX / REFACTOR REQUEST HERE]" in prompt



def test_task_clipboard_alias_reads_pbpaste_and_updates_prompt(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text("print('hello')\n")
    output = tmp_path / "output"
    task = """Review this JSON:
{"_meta": {"updated_by_display_name": "Example User (TS)"}}
Do not reinterpret $HOME, *.json, or `commands`.
"""
    args = build_parser().parse_args(
        [str(project), "--all", "--output-dir", str(output), "--tc"]
    )
    completed = __import__("subprocess").CompletedProcess(["pbpaste"], 0, task, "")
    monkeypatch.setattr("build_ai_context.cli.subprocess.run", lambda *args, **kwargs: completed)
    result, _, _ = run_exporter(args, None)
    assert result == 0
    assert task in (output / "baic_prompt.md").read_text()


def test_task_clipboard_long_option_is_supported():
    args = build_parser().parse_args(["--task-clipboard"])
    assert args.task_clipboard is True


def test_task_and_clipboard_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--task", "one", "--tc"])


def test_task_clipboard_rejects_empty_clipboard(monkeypatch):
    from build_ai_context.cli import resolve_task_content
    args = build_parser().parse_args(["--tc"])
    completed = __import__("subprocess").CompletedProcess(["pbpaste"], 0, "", "")
    monkeypatch.setattr("build_ai_context.cli.subprocess.run", lambda *args, **kwargs: completed)
    with pytest.raises(ValueError, match="does not contain task text"):
        resolve_task_content(args)


def test_task_clipboard_reports_missing_pbpaste(monkeypatch):
    from build_ai_context.cli import resolve_task_content
    args = build_parser().parse_args(["--tc"])

    def missing_pbpaste(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr("build_ai_context.cli.subprocess.run", missing_pbpaste)
    with pytest.raises(ValueError, match="requires the macOS pbpaste command"):
        resolve_task_content(args)



def test_multiple_comma_terminated_path_arguments_are_normalized(tmp_path):
    project = tmp_path / "project"
    first = project / "src" / "service.py"
    second = project / "src" / "materialization.py"
    third = project / "tests" / "test_service.py"
    for path in (first, second, third):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {path.name}\n")
    output = tmp_path / "output"
    args = build_parser().parse_args(
        [
            str(project),
            "--non-interactive",
            "--output-dir",
            str(output),
            "--paths",
            "src/service.py,",
            "src/materialization.py,",
            "tests/test_service.py",
            "--task",
            "Review all selected files.",
        ]
    )

    result, _, _ = run_exporter(args, None)

    assert result == 0
    manifest = json.loads(next(output.glob("*_manifest_*.json")).read_text())
    assert manifest["selected_files"] == [
        "src/materialization.py",
        "src/service.py",
        "tests/test_service.py",
    ]
    assert manifest["selection"]["missing_paths"] == []


def test_line_comma_and_mixed_path_input_select_the_same_files(tmp_path):
    project = tmp_path / "project"
    requested = ["src/one.py", "src/two.py", "tests/test_one.py"]
    for relative_path in requested:
        path = project / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {path.name}\n")

    variants = [
        "\n".join(requested),
        ",".join(requested),
        ",\n".join(requested),
    ]
    for index, path_input in enumerate(variants):
        output = tmp_path / f"output-{index}"
        args = build_parser().parse_args(
            [
                str(project),
                "--non-interactive",
                "--output-dir",
                str(output),
                "--paths",
                path_input,
            ]
        )

        result, _, _ = run_exporter(args, None)

        assert result == 0
        manifest = json.loads(next(output.glob("*_manifest_*.json")).read_text())
        assert manifest["selected_files"] == sorted(requested)
        assert manifest["selection"]["missing_paths"] == []



def test_force_bundle_defaults_to_false():
    assert build_parser().parse_args([]).force_bundle is False


def test_force_bundle_samples_json_without_modifying_source(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    source = project / "catalog.json"
    original = json.dumps({
        "_meta": {"version": 7},
        **{f"page-{i}": {"state": str(i), "aa_data": {"kind": "page"}} for i in range(30)},
        **{f"click-{i}": {"aa_data": {"kind": "click", "name": str(i)}} for i in range(30)},
        **{f"error-{i}": {"aa_data": {"error": str(i)}} for i in range(30)},
    }, indent=2)
    source.write_text(original)
    output = tmp_path / "output"
    args = build_parser().parse_args([
        str(project), "--all", "--output-dir", str(output),
        "--max-file-lines", "100", "--force-bundle",
    ])
    result, _, _ = run_exporter(args, None)
    assert result == 0
    assert source.read_text() == original
    manifest = json.loads(next(output.glob("*_manifest_*.json")).read_text())
    sample = next(item for item in manifest["warnings"]
                  if item["reason"] == "force_bundled_json_sample")
    assert sample["bundled_line_count"] < 100
    assert sample["representatives_per_shape"] >= 3
    bundle = next(output.glob("*_bundle_*.txt")).read_text()
    assert "===== BEGIN FILE: catalog.json =====" in bundle
    assert '"_meta"' in bundle


def test_force_bundle_preserves_array_shapes(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    source = project / "values.json"
    source.write_text(json.dumps({"items": [
        *({"kind": "object", "value": i} for i in range(25)),
        *(f"scalar-{i}" for i in range(25)),
    ]}, indent=2))
    output = tmp_path / "output"
    args = build_parser().parse_args([
        str(project), "--all", "--output-dir", str(output),
        "--max-file-lines", "50", "--force-bundle",
    ])
    result, _, _ = run_exporter(args, None)
    assert result == 0
    bundle = next(output.glob("*_bundle_*.txt")).read_text()
    assert '"kind": "object"' in bundle
    assert '"scalar-0"' in bundle


def test_force_bundle_leaves_invalid_json_skipped(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "invalid.json").write_text("{\n" + "not-json\n" * 20 + "}")
    output = tmp_path / "output"
    args = build_parser().parse_args([
        str(project), "--all", "--output-dir", str(output),
        "--max-file-lines", "10", "--force-bundle",
    ])
    result, _, _ = run_exporter(args, None)
    assert result == 0
    manifest = json.loads(next(output.glob("*_manifest_*.json")).read_text())
    assert any(item["reason"] == "large_file_exceeds_skip_threshold"
               for item in manifest["skipped_during_pack"])
    assert any(item["reason"] == "force_bundle_invalid_json"
               for item in manifest["warnings"])
