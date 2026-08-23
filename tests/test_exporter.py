"""Tests for build_ai_context package."""

import pytest
from pathlib import Path

import pathspec

from build_ai_context import __version__
from build_ai_context.exporter import CodeExporter
from build_ai_context.models import ExportConfig, ExportResult, FileChunk, SourceFile
from build_ai_context import constants


def test_version():
    """Test that version is defined and follows semver."""
    assert __version__ is not None
    assert len(__version__.split(".")) >= 2  # At least major.minor


class TestCodeExporter:
    """Tests for the CodeExporter class."""

    def test_init(self):
        """Test exporter initialization."""
        exporter = CodeExporter()
        assert exporter is not None

    def test_detect_category_python(self, tmp_path):
        """Test detecting Python files."""
        py_file = tmp_path / "test.py"
        py_file.touch()
        assert CodeExporter.detect_category(py_file) == "python"

    def test_detect_category_typescript(self, tmp_path):
        """Test detecting TypeScript files."""
        ts_file = tmp_path / "test.ts"
        ts_file.touch()
        assert CodeExporter.detect_category(ts_file) == "typescript"

    def test_detect_category_javascript(self, tmp_path):
        """Test detecting JavaScript files."""
        js_file = tmp_path / "test.js"
        js_file.touch()
        assert CodeExporter.detect_category(js_file) == "javascript"

    def test_detect_category_unknown(self, tmp_path):
        """Test unknown file types return None."""
        unknown_file = tmp_path / "test.xyz"
        unknown_file.touch()
        assert CodeExporter.detect_category(unknown_file) is None

    def test_detect_category_special_file(self, tmp_path):
        """Test special filenames like Dockerfile."""
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.touch()
        assert CodeExporter.detect_category(dockerfile) == "config_docs"

    def test_detect_category_shell_sh(self, tmp_path):
        """Test detecting shell .sh files."""
        sh_file = tmp_path / "script.sh"
        sh_file.touch()
        assert CodeExporter.detect_category(sh_file) == "shell"

    def test_detect_category_shell_bash(self, tmp_path):
        """Test detecting shell .bash files."""
        bash_file = tmp_path / "script.bash"
        bash_file.touch()
        assert CodeExporter.detect_category(bash_file) == "shell"

    def test_detect_category_shell_zsh(self, tmp_path):
        """Test detecting shell .zsh files."""
        zsh_file = tmp_path / "script.zsh"
        zsh_file.touch()
        assert CodeExporter.detect_category(zsh_file) == "shell"

    def test_should_skip_by_dir_git(self):
        """Test that .git directory is skipped."""
        rel_path = Path(".git") / "objects"
        assert CodeExporter.should_skip_by_dir(rel_path) is True

    def test_should_skip_by_dir_normal(self):
        """Test that normal directories are not skipped."""
        rel_path = Path("src") / "main.py"
        assert CodeExporter.should_skip_by_dir(rel_path) is False

    def test_should_skip_by_prefix(self):
        """Test that exported_sources prefix is skipped."""
        rel_path = Path("exported_sources_myproject") / "bundle.txt"
        assert CodeExporter.should_skip_by_prefix(rel_path) is True

    def test_should_skip_by_prefix_nested(self):
        """Test that nested exported_sources prefix is skipped."""
        rel_path = Path("some") / Path("exported_sources") / "bundle.txt"
        assert CodeExporter.should_skip_by_prefix(rel_path) is True

    def test_should_not_skip_by_prefix_unrelated(self):
        """Test that unrelated paths are not skipped."""
        rel_path = Path("src") / "main.py"
        assert CodeExporter.should_skip_by_prefix(rel_path) is False

    def test_sha256_of_lines(self):
        """Test SHA256 calculation."""
        lines = ["line1", "line2", "line3"]
        hash1 = CodeExporter.sha256_of_lines(lines)
        hash2 = CodeExporter.sha256_of_lines(lines)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length

    def test_normalize_categories(self):
        """Test category normalization."""
        exporter = CodeExporter()
        result = exporter.normalize_categories(["py", "ts", "js", "invalid"])
        assert "python" in result
        assert "typescript" in result
        assert "javascript" in result
        assert "invalid" not in result

    def test_normalize_categories_shell_alias(self):
        """Test shell category aliases."""
        exporter = CodeExporter()
        result = exporter.normalize_categories(["sh", "bash", "zsh"])
        assert "shell" in result

    def test_parse_csv_input(self):
        """Test CSV input parsing."""
        exporter = CodeExporter()
        result = exporter.parse_csv_input("a, b, c,")
        assert result == ["a", "b", "c"]

    def test_filter_files_by_keywords_basic(self, tmp_path):
        """Test keyword filtering finds files with keyword."""
        file1 = tmp_path / "test1.py"
        file1.write_text("def TODO(): pass")
        file2 = tmp_path / "test2.py"
        file2.write_text("def done(): pass")

        exporter = CodeExporter()
        files, skipped = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        matched, found_keywords = exporter.filter_files_by_keywords(files, ["TODO"])

        assert len(matched) == 1
        assert matched[0].rel_path.name == "test1.py"
        assert "todo" in found_keywords

    def test_filter_files_by_keywords_multiple(self, tmp_path):
        """Test keyword filtering with multiple keywords."""
        file1 = tmp_path / "test1.py"
        file1.write_text("def TODO(): pass\ndef FIXME(): pass")
        file2 = tmp_path / "test2.py"
        file2.write_text("def done(): pass")

        exporter = CodeExporter()
        files, skipped = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        matched, found_keywords = exporter.filter_files_by_keywords(files, ["TODO", "FIXME"])

        assert len(matched) == 1
        assert "todo" in found_keywords
        assert "fixme" in found_keywords

    def test_filter_files_by_keywords_case_insensitive(self, tmp_path):
        """Test keyword filtering is case insensitive."""
        file1 = tmp_path / "test1.py"
        file1.write_text("def todo(): pass")

        exporter = CodeExporter()
        files, skipped = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        matched, found_keywords = exporter.filter_files_by_keywords(files, ["TODO"])

        assert len(matched) == 1

    def test_filter_files_by_keywords_no_match(self, tmp_path):
        """Test keyword filtering with no matches."""
        file1 = tmp_path / "test1.py"
        file1.write_text("def done(): pass")

        exporter = CodeExporter()
        files, skipped = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        matched, found_keywords = exporter.filter_files_by_keywords(files, ["TODO"])

        assert len(matched) == 0

    def test_is_ignored_extra_excluded_patterns(self, tmp_path):
        """Test extra excluded patterns like package-lock.json."""
        rel_path = Path("package-lock.json")
        gitignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", [])

        is_ignored, reason = CodeExporter.is_ignored(
            rel_path, gitignore_spec, skip_secret_files=False
        )

        assert is_ignored is True
        assert reason == "extra_excluded_pattern"

    def test_is_ignored_default_excluded_prefix(self, tmp_path):
        """Test default excluded prefix like exported_sources."""
        rel_path = Path("exported_sources_test") / "bundle.txt"
        gitignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", [])

        is_ignored, reason = CodeExporter.is_ignored(
            rel_path, gitignore_spec, skip_secret_files=False
        )

        assert is_ignored is True
        assert reason == "default_excluded_prefix"

    def test_non_interactive_select_all(self, tmp_path):
        """Test non-interactive selection with all categories."""
        (tmp_path / "test.py").write_text("print('hello')")

        exporter = CodeExporter()
        all_files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        selected, metadata = exporter.non_interactive_select_files(
            all_files, categories=[], path_prefixes=[], root=tmp_path
        )

        assert len(selected) > 0
        assert metadata["selection_mode"] == "non_interactive"

    def test_non_interactive_select_categories(self, tmp_path):
        """Test non-interactive selection by category."""
        (tmp_path / "test.py").write_text("print('hello')")
        (tmp_path / "test.js").write_text("console.log('hello')")

        exporter = CodeExporter()
        all_files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        selected, metadata = exporter.non_interactive_select_files(
            all_files, categories=["python"], path_prefixes=[], root=tmp_path
        )

        assert len(selected) == 1
        assert selected[0].category == "python"
        assert "python" in metadata["selected_categories"]

    def test_non_interactive_select_paths(self, tmp_path):
        """Test non-interactive selection by path."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "test.py").write_text("print('hello')")
        (tmp_path / "test.js").write_text("console.log('hello')")

        exporter = CodeExporter()
        all_files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        selected, metadata = exporter.non_interactive_select_files(
            all_files, categories=[], path_prefixes=["src"], root=tmp_path
        )

        assert len(selected) == 1
        assert "src" in metadata["selected_paths"]

    def test_summarize_by_category(self, tmp_path):
        """Test summarizing files by category."""
        (tmp_path / "test.py").write_text("print('hello')")
        (tmp_path / "test2.py").write_text("print('world')")

        exporter = CodeExporter()
        all_files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        summary = exporter.summarize_by_category(all_files)

        assert "python" in summary
        assert summary["python"]["files"] == 2


class TestFileChunk:
    """Tests for FileChunk model."""

    def test_line_count(self):
        """Test line_count property."""
        chunk = FileChunk(
            rel_path=Path("test.py"),
            category="python",
            chunk_index=1,
            chunk_count=1,
            start_line=1,
            end_line=3,
            total_file_lines=3,
            lines=["line1", "line2", "line3"],
        )
        assert chunk.line_count == 3


class TestSourceFile:
    """Tests for SourceFile model."""

    def test_source_file_creation(self):
        """Test creating a SourceFile."""
        sf = SourceFile(
            abs_path=Path("/tmp/test.py"),
            rel_path=Path("test.py"),
            category="python",
            line_count=10,
            size_bytes=100,
            sha256="abc123",
            lines=["line" + str(i) for i in range(10)],
        )
        assert sf.category == "python"
        assert sf.line_count == 10


class TestConstants:
    """Tests for constants module."""

    def test_default_max_lines(self):
        """Test default max lines constant."""
        assert constants.DEFAULT_MAX_LINES == 8000

    def test_category_extensions_keys(self):
        """Test that category extensions have expected keys."""
        assert "python" in constants.CATEGORY_EXTENSIONS
        assert "typescript" in constants.CATEGORY_EXTENSIONS
        assert "javascript" in constants.CATEGORY_EXTENSIONS

    def test_shell_category_exists(self):
        """Test shell category is defined."""
        assert "shell" in constants.CATEGORY_EXTENSIONS
        assert ".sh" in constants.CATEGORY_EXTENSIONS["shell"]
        assert ".bash" in constants.CATEGORY_EXTENSIONS["shell"]
        assert ".zsh" in constants.CATEGORY_EXTENSIONS["shell"]

    def test_category_descriptions_shell(self):
        """Test shell category description."""
        assert "shell" in constants.CATEGORY_DESCRIPTIONS

    def test_category_aliases_shell(self):
        """Test shell category aliases."""
        assert "shell" in constants.CATEGORY_ALIASES
        assert "sh" in constants.CATEGORY_ALIASES
        assert "bash" in constants.CATEGORY_ALIASES
        assert "zsh" in constants.CATEGORY_ALIASES
        assert constants.CATEGORY_ALIASES["sh"] == "shell"

    def test_excluded_dirs(self):
        """Test that .git is in excluded dirs."""
        assert ".git" in constants.DEFAULT_EXCLUDED_DIRS
        assert "node_modules" in constants.DEFAULT_EXCLUDED_DIRS

    def test_extra_excluded_patterns(self):
        """Test extra excluded patterns."""
        assert "package-lock.json" in constants.EXTRA_EXCLUDED_PATTERNS
        assert "yarn.lock" in constants.EXTRA_EXCLUDED_PATTERNS
        assert "pnpm-lock.yaml" in constants.EXTRA_EXCLUDED_PATTERNS

    def test_default_excluded_prefixes(self):
        """Test default excluded prefixes."""
        assert "exported_sources" in constants.DEFAULT_EXCLUDED_PREFIXES


class TestExportConfig:
    """Tests for ExportConfig model."""

    def test_default_values(self):
        """Test default config values."""
        config = ExportConfig(project_root=Path("."))
        assert config.max_lines == 8000
        assert config.include_secret_files is False
        assert config.interactive is True
