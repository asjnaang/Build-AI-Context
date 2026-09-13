"""Tests for scanner module functions."""

import pytest
from pathlib import Path
from unittest.mock import patch

from build_ai_context.scanner import (
    parse_intelligent_input,
    filter_files_by_paths,
    _normalize_selection_paths,
    scan_supported_files,
)
from build_ai_context.models import SourceFile
from build_ai_context.exporter import CodeExporter


@pytest.fixture
def sample_files(tmp_path):
    """Create a sample set of source files in a temporary directory."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')")
    (tmp_path / "src" / "utils.py").write_text("def foo(): pass")
    (tmp_path / "README.md").write_text("# Project")
    (tmp_path / "docs" / "guide.md").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "guide.md" / "index.md").write_text("Guide")
    # Create SourceFile objects manually for testing
    files = []
    for rel_path in ["src/main.py", "src/utils.py", "README.md", "docs/guide.md/index.md"]:
        abs_path = tmp_path / rel_path
        text = abs_path.read_text()
        lines = text.splitlines()
        files.append(
            SourceFile(
                abs_path=abs_path,
                rel_path=Path(rel_path),
                category="python" if rel_path.endswith(".py") else "config_docs",
                line_count=len(lines),
                lines=lines,
                size_bytes=abs_path.stat().st_size,
                sha256="dummy",
            )
        )
    return tmp_path, files


class TestParseIntelligentInput:
    """Tests for parse_intelligent_input function."""

    def test_empty_input(self, sample_files):
        root, files = sample_files
        result = parse_intelligent_input("", files, root)
        assert result == []

    def test_single_filename(self, sample_files):
        root, files = sample_files
        result = parse_intelligent_input("main.py", files, root)
        assert "src/main.py" in result

    def test_multiple_comma_separated(self, sample_files):
        root, files = sample_files
        result = parse_intelligent_input("main.py, utils.py", files, root)
        assert len(result) == 2
        assert "src/main.py" in result
        assert "src/utils.py" in result

    def test_multiple_space_separated(self, sample_files):
        root, files = sample_files
        result = parse_intelligent_input("main.py utils.py", files, root)
        assert len(result) == 2

    def test_folder_name(self, sample_files):
        root, files = sample_files
        result = parse_intelligent_input("src", files, root)
        assert "src/main.py" in result
        assert "src/utils.py" in result

    def test_folder_path(self, sample_files):
        root, files = sample_files
        result = parse_intelligent_input("docs/guide.md", files, root)
        assert "docs/guide.md/index.md" in result

    def test_absolute_path(self, sample_files):
        root, files = sample_files
        abs_path = (root / "README.md").resolve()
        result = parse_intelligent_input(str(abs_path), files, root)
        assert "README.md" in result

    def test_partial_match(self, sample_files):
        root, files = sample_files
        result = parse_intelligent_input("main", files, root)
        assert "src/main.py" in result

    def test_extension_match(self, sample_files):
        root, files = sample_files
        result = parse_intelligent_input(".md", files, root)
        assert "README.md" in result
        assert "docs/guide.md/index.md" in result


    def test_paths_with_spaces_do_not_select_unrelated_files(self, tmp_path):
        requested = [
            "services/data/North Region Config_JSON_Consolidate_v1.81.json",
            "services/data/west desk config_consolidated json_v1.8.json",
            "services/data/east desk config_consolidated json_v18.json",
        ]
        unrelated = [
            "frontend/Settings/SettingsPanel.tsx",
            "frontend/InputForms/InputAccordion.tsx",
            "services/compare_search_algorithms.py",
        ]
        files = []
        for relative_path in requested + unrelated:
            path = tmp_path / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("content")
            files.append(
                SourceFile(
                    abs_path=path,
                    rel_path=Path(relative_path),
                    category="config_docs",
                    line_count=1,
                    size_bytes=7,
                    sha256="dummy",
                    lines=["content"],
                )
            )

        raw = "\n".join(requested)
        result = parse_intelligent_input(raw, files, tmp_path)

        assert result == requested
        assert not set(result).intersection(unrelated)

    def test_mixed_line_and_comma_input_preserves_spaces(self, tmp_path):
        requested = [
            "services/data/North Region Config_JSON_Consolidate_v1.81.json",
            "services/data/plain.json",
            "frontend/src/main.tsx",
        ]
        files = []
        for relative_path in requested:
            path = tmp_path / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("content")
            files.append(
                SourceFile(
                    abs_path=path,
                    rel_path=Path(relative_path),
                    category="config_docs",
                    line_count=1,
                    size_bytes=7,
                    sha256="dummy",
                    lines=["content"],
                )
            )

        raw = f"{requested[0]},\n{requested[1]}; {requested[2]}"
        result = parse_intelligent_input(raw, files, tmp_path)

        assert result == requested

    def test_combined_comma_space_and_line_separators_select_all_paths(self, tmp_path):
        requested = [
            "data/Sampled_master_files",
            "docs/master_data_import_runbook.md",
            "scripts/master_data_db.sh",
            "scripts/import_master_data.py",
            "scripts/create_master_data_postgres.sql",
            "data/path with spaces/reference data.json",
        ]
        files = []
        for relative_path in requested:
            path = tmp_path / relative_path
            if path.suffix:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("content")
                file_paths = [path]
            else:
                path.mkdir(parents=True, exist_ok=True)
                child = path / "sample.json"
                child.write_text("content")
                file_paths = [child]
            for file_path in file_paths:
                files.append(SourceFile(
                    abs_path=file_path,
                    rel_path=file_path.relative_to(tmp_path),
                    category="config_docs",
                    line_count=1,
                    size_bytes=7,
                    sha256="dummy",
                    lines=["content"],
                ))

        raw = (
            f"{tmp_path / requested[0]}, {tmp_path / requested[1]}, "
            f"{tmp_path / requested[2]} {tmp_path / requested[3]} "
            f"{tmp_path / requested[4]}\n{tmp_path / requested[5]}"
        )
        result = parse_intelligent_input(raw, files, tmp_path)

        assert result == [
            "data/Sampled_master_files/sample.json",
            "docs/master_data_import_runbook.md",
            "scripts/master_data_db.sh",
            "scripts/import_master_data.py",
            "scripts/create_master_data_postgres.sql",
            "data/path with spaces/reference data.json",
        ]

    def test_unresolved_text_does_not_become_substring_search(self, sample_files):
        root, files = sample_files
        result = parse_intelligent_input("read main documentation", files, root)
        assert result == []

class TestFilterFilesByPaths:
    """Tests for filter_files_by_paths function."""

    def test_empty_paths(self, sample_files):
        root, files = sample_files
        matched, norm, missing = filter_files_by_paths(files, root, [])
        assert matched == files
        assert norm == []
        assert missing == []

    def test_exact_rel_path(self, sample_files):
        root, files = sample_files
        matched, norm, missing = filter_files_by_paths(files, root, ["src/main.py"])
        assert len(matched) == 1
        assert matched[0].rel_path.as_posix() == "src/main.py"
        assert norm == ["src/main.py"]
        assert missing == []

    def test_folder_path(self, sample_files):
        root, files = sample_files
        matched, norm, missing = filter_files_by_paths(files, root, ["src"])
        assert len(matched) == 2
        assert {f.rel_path.as_posix() for f in matched} == {"src/main.py", "src/utils.py"}

    def test_nonexistent_path(self, sample_files):
        root, files = sample_files
        matched, norm, missing = filter_files_by_paths(files, root, ["nonexistent"])
        assert matched == []
        assert missing == ["nonexistent"]

    def test_mixed_existing_nonexisting(self, sample_files):
        root, files = sample_files
        matched, norm, missing = filter_files_by_paths(files, root, ["src", "nonexistent"])
        assert len(matched) == 2
        assert missing == ["nonexistent"]

    def test_absolute_path(self, sample_files):
        root, files = sample_files
        abs_path = str((root / "README.md").resolve())
        matched, norm, missing = filter_files_by_paths(files, root, [abs_path])
        assert len(matched) == 1
        assert matched[0].rel_path.as_posix() == "README.md"

    def test_filename_only(self, sample_files):
        root, files = sample_files
        matched, norm, missing = filter_files_by_paths(files, root, ["main.py"])
        assert len(matched) == 1
        assert matched[0].rel_path.as_posix() == "src/main.py"

    def test_duplicate_paths(self, sample_files):
        root, files = sample_files
        matched, norm, missing = filter_files_by_paths(files, root, ["src", "src"])
        # Should not duplicate files
        assert len(matched) == 2


class TestNormalizeSelectionPaths:
    """Tests for _normalize_selection_paths."""

    def test_absolute_path(self, sample_files):
        root, _ = sample_files
        abs_path = str((root / "README.md").resolve())
        norm = _normalize_selection_paths([abs_path], root)
        assert norm == ["README.md"]

    def test_relative_path(self, sample_files):
        root, _ = sample_files
        norm = _normalize_selection_paths(["src/main.py"], root)
        assert norm == ["src/main.py"]

    def test_trailing_slash(self, sample_files):
        root, _ = sample_files
        norm = _normalize_selection_paths(["src/"], root)
        assert norm == ["src"]

    def test_empty_string(self, sample_files):
        root, _ = sample_files
        norm = _normalize_selection_paths([""], root)
        assert norm == []


class TestInteractiveSelection:
    """Integration tests for interactive selection via monkeypatching."""

    def test_path_selection_interactive(self, sample_files, monkeypatch):
        """Test that interactive path selection works (mock input)."""
        root, files = sample_files
        exporter = CodeExporter()
        exporter._questionary_available = False  # force numbered-list fallback
        # Simulate user choosing mode 3, entering path "src", then confirming deselection
        inputs = iter(["3", "src", "c"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        # Mock filter_files_by_paths to verify correct arguments
        from build_ai_context import cli_ui

        called_with = []
        original_filter = exporter.filter_files_by_paths

        def mock_filter(*args, **kwargs):
            called_with.append((args, kwargs))
            return original_filter(*args, **kwargs)

        monkeypatch.setattr(exporter, "filter_files_by_paths", mock_filter)

        selected, metadata = cli_ui.interactive_select_files(exporter, files, root)
        # Ensure filter_files_by_paths was called with correct order
        assert len(called_with) == 1
        args, kwargs = called_with[0]
        # args should be (all_files, root, path_prefixes)
        assert args[0] == files
        assert args[1] == root
        assert isinstance(args[2], list)
        # Should have selected the two python files
        assert len(selected) == 2
        assert metadata["selection_mode"] == "path"


class TestCategorySelection:
    """Tests for interactive category selection."""

    def test_select_categories_interactive_with_questionary(self, sample_files, monkeypatch):
        """Test category selection when questionary is available."""
        pytest.importorskip("questionary")
        root, files = sample_files
        exporter = CodeExporter()
        # Mock questionary
        mock_questionary = type(
            "MockQuestionary",
            (),
            {
                "Choice": lambda self, title, value: (title, value),
                "checkbox": lambda self, title, choices: type(
                    "MockCheckbox", (), {"ask": lambda self: ["python", "config_docs"]}
                )(),
            },
        )()
        exporter._questionary_available = True
        exporter._questionary = mock_questionary

        from build_ai_context.cli_ui import select_categories_interactive

        result = select_categories_interactive(exporter, files)
        assert result == ["python", "config_docs"]

    def test_select_categories_interactive_without_questionary(self, sample_files, monkeypatch):
        """Test category selection without questionary (fallback)."""
        root, files = sample_files
        exporter = CodeExporter()
        exporter._questionary_available = False

        # Simulate user entering "python, config_docs"
        inputs = iter(["python, config_docs"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        from build_ai_context.cli_ui import select_categories_interactive

        result = select_categories_interactive(exporter, files)
        assert set(result) == {"python", "config_docs"}

    def test_select_categories_interactive_all(self, sample_files, monkeypatch):
        """Test selecting all categories by pressing Enter."""
        root, files = sample_files
        exporter = CodeExporter()
        exporter._questionary_available = False

        inputs = iter([""])  # empty input selects all
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        from build_ai_context.cli_ui import select_categories_interactive

        result = select_categories_interactive(exporter, files)
        # Should return all detected categories
        summary = exporter.summarize_by_category(files)
        expected = sorted(summary.keys())
        assert result == expected

    def test_select_categories_interactive_numbers(self, sample_files, monkeypatch):
        """Test selecting categories by numbers."""
        root, files = sample_files
        exporter = CodeExporter()
        exporter._questionary_available = False

        inputs = iter(["1,2"])  # select first two categories
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        from build_ai_context.cli_ui import select_categories_interactive

        result = select_categories_interactive(exporter, files)
        summary = exporter.summarize_by_category(files)
        expected = sorted(summary.keys())[:2]
        assert result == expected

    def test_select_categories_interactive_numbers(self, sample_files, monkeypatch):
        """Test selecting categories by numbers."""
        root, files = sample_files
        exporter = CodeExporter()
        exporter._questionary_available = False

        inputs = iter(["1,2"])  # select first two categories
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        from build_ai_context.cli_ui import select_categories_interactive

        result = select_categories_interactive(exporter, files)
        summary = exporter.summarize_by_category(files)
        expected = sorted(summary.keys())[:2]
        assert result == expected


class TestGitignoreAwareTraversal:
    """Regression coverage for pruning and nested repository ignore rules."""

    def test_root_gitignore_prunes_ignored_repository_before_descent(self, tmp_path, monkeypatch):
        included = tmp_path / "frontend"
        ignored = tmp_path / "unused-repo"
        included.mkdir()
        ignored.mkdir()
        (included / "app.ts").write_text("export const app = true")
        (ignored / "never-read.py").write_text("raise AssertionError")
        (tmp_path / ".gitignore").write_text("unused-repo/\n")

        original_read = Path.read_text

        def guarded_read(path, *args, **kwargs):
            if path.name == "never-read.py":
                raise AssertionError("ignored repository was traversed")
            return original_read(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", guarded_read)
        files, skipped = scan_supported_files(tmp_path, skip_secret_files=True)

        assert [item.rel_path.as_posix() for item in files] == ["frontend/app.ts"]
        assert skipped[".gitignore"] == 1

    def test_nested_gitignore_is_applied_within_each_repository(self, tmp_path):
        repo = tmp_path / "backend"
        generated = repo / "generated"
        generated.mkdir(parents=True)
        (repo / ".gitignore").write_text("generated/\n")
        (repo / "main.py").write_text("print('included')")
        (generated / "large.py").write_text("print('ignored')")

        files, skipped = scan_supported_files(tmp_path, skip_secret_files=True)

        assert [item.rel_path.as_posix() for item in files] == ["backend/main.py"]
        assert skipped[".gitignore"] == 1

if __name__ == "__main__":
    pytest.main([__file__])
