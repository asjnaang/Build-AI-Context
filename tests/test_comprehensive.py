"""Comprehensive tests for build_ai_context package."""

import pytest
from pathlib import Path

import pathspec

from build_ai_context import __version__
from build_ai_context.exporter import CodeExporter
from build_ai_context.models import ExportConfig, FileChunk, SourceFile
from build_ai_context import constants


class TestVersion:
    """Tests for package version."""

    def test_version_exists(self):
        assert __version__ is not None

    def test_version_format(self):
        parts = __version__.split(".")
        assert len(parts) >= 2
        assert all(p.isdigit() for p in parts)


class TestCategoryDetection:
    """Tests for file category detection."""

    def test_detect_python(self, tmp_path):
        f = tmp_path / "test.py"
        f.touch()
        assert CodeExporter.detect_category(f) == "python"

    def test_detect_typescript(self, tmp_path):
        f = tmp_path / "test.ts"
        f.touch()
        assert CodeExporter.detect_category(f) == "typescript"

    def test_detect_tsx(self, tmp_path):
        f = tmp_path / "test.tsx"
        f.touch()
        assert CodeExporter.detect_category(f) == "typescript"

    def test_detect_javascript(self, tmp_path):
        f = tmp_path / "test.js"
        f.touch()
        assert CodeExporter.detect_category(f) == "javascript"

    def test_detect_jsx(self, tmp_path):
        f = tmp_path / "test.jsx"
        f.touch()
        assert CodeExporter.detect_category(f) == "javascript"

    def test_detect_mjs(self, tmp_path):
        f = tmp_path / "test.mjs"
        f.touch()
        assert CodeExporter.detect_category(f) == "javascript"

    def test_detect_cjs(self, tmp_path):
        f = tmp_path / "test.cjs"
        f.touch()
        assert CodeExporter.detect_category(f) == "javascript"

    def test_detect_java(self, tmp_path):
        f = tmp_path / "Test.java"
        f.touch()
        assert CodeExporter.detect_category(f) == "java_kotlin"

    def test_detect_kotlin(self, tmp_path):
        f = tmp_path / "Test.kt"
        f.touch()
        assert CodeExporter.detect_category(f) == "java_kotlin"

    def test_detect_swift(self, tmp_path):
        f = tmp_path / "Test.swift"
        f.touch()
        assert CodeExporter.detect_category(f) == "ios_apple"

    def test_detect_html(self, tmp_path):
        f = tmp_path / "index.html"
        f.touch()
        assert CodeExporter.detect_category(f) == "web_ui"

    def test_detect_css(self, tmp_path):
        f = tmp_path / "style.css"
        f.touch()
        assert CodeExporter.detect_category(f) == "web_ui"

    def test_detect_scss(self, tmp_path):
        f = tmp_path / "style.scss"
        f.touch()
        assert CodeExporter.detect_category(f) == "web_ui"

    def test_detect_shell_sh(self, tmp_path):
        f = tmp_path / "script.sh"
        f.touch()
        assert CodeExporter.detect_category(f) == "shell"

    def test_detect_shell_bash(self, tmp_path):
        f = tmp_path / "script.bash"
        f.touch()
        assert CodeExporter.detect_category(f) == "shell"

    def test_detect_shell_zsh(self, tmp_path):
        f = tmp_path / "script.zsh"
        f.touch()
        assert CodeExporter.detect_category(f) == "shell"

    def test_detect_flutter_dart(self, tmp_path):
        f = tmp_path / "main.dart"
        f.touch()
        assert CodeExporter.detect_category(f) == "flutter"

    def test_detect_json(self, tmp_path):
        f = tmp_path / "data.json"
        f.touch()
        assert CodeExporter.detect_category(f) == "config_docs"

    def test_detect_yaml(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.touch()
        assert CodeExporter.detect_category(f) == "config_docs"

    def test_detect_markdown(self, tmp_path):
        f = tmp_path / "README.md"
        f.touch()
        assert CodeExporter.detect_category(f) == "config_docs"

    def test_detect_unknown(self, tmp_path):
        f = tmp_path / "test.xyz"
        f.touch()
        assert CodeExporter.detect_category(f) is None

    def test_detect_dockerfile(self, tmp_path):
        f = tmp_path / "Dockerfile"
        f.touch()
        assert CodeExporter.detect_category(f) == "config_docs"

    def test_detect_pubspec(self, tmp_path):
        f = tmp_path / "pubspec.yaml"
        f.touch()
        assert CodeExporter.detect_category(f) == "config_docs"


class TestDirectorySkipping:
    """Tests for directory exclusion logic."""

    def test_skip_git(self):
        rel_path = Path(".git") / "objects"
        assert CodeExporter.should_skip_by_dir(rel_path) is True

    def test_skip_node_modules(self):
        rel_path = Path("node_modules") / "package" / "index.js"
        assert CodeExporter.should_skip_by_dir(rel_path) is True

    def test_skip_pycache(self):
        rel_path = Path("__pycache__") / "module.pyc"
        assert CodeExporter.should_skip_by_dir(rel_path) is True

    def test_skip_build(self):
        rel_path = Path("build") / "output.txt"
        assert CodeExporter.should_skip_by_dir(rel_path) is True

    def test_skip_venv(self):
        rel_path = Path(".venv") / "lib" / "site-packages"
        assert CodeExporter.should_skip_by_dir(rel_path) is True

    def test_no_skip_src(self):
        rel_path = Path("src") / "main.py"
        assert CodeExporter.should_skip_by_dir(rel_path) is False

    def test_no_skip_lib(self):
        rel_path = Path("lib") / "utils.py"
        assert CodeExporter.should_skip_by_dir(rel_path) is False

    def test_skip_github(self):
        rel_path = Path(".github") / "workflows" / "ci.yml"
        assert CodeExporter.should_skip_by_dir(rel_path) is True


class TestPrefixSkipping:
    """Tests for prefix-based exclusion."""

    def test_skip_exported_sources_prefix(self):
        rel_path = Path("exported_sources_myproject") / "bundle.txt"
        assert CodeExporter.should_skip_by_prefix(rel_path) is True

    def test_skip_nested_exported_sources(self):
        rel_path = Path("exported_sources_test") / "bundle.txt"
        assert CodeExporter.should_skip_by_prefix(rel_path) is True

    def test_no_skip_exported_sources_in_middle(self):
        rel_path = Path("some") / "exported_sources_test" / "bundle.txt"
        assert CodeExporter.should_skip_by_prefix(rel_path) is False

    def test_no_skip_regular_src(self):
        rel_path = Path("src") / "main.py"
        assert CodeExporter.should_skip_by_prefix(rel_path) is False

    def test_no_skip_similar_name(self):
        rel_path = Path("export_source_old") / "file.txt"
        assert CodeExporter.should_skip_by_prefix(rel_path) is False


class TestKeywordFiltering:
    """Tests for keyword-based file filtering."""

    def test_filter_by_keyword(self, tmp_path):
        file1 = tmp_path / "test1.py"
        file1.write_text("def TODO(): pass")
        file2 = tmp_path / "test2.py"
        file2.write_text("def done(): pass")

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        matched, keywords = exporter.filter_files_by_keywords(files, ["TODO"])
        assert len(matched) == 1
        assert "todo" in keywords

    def test_filter_case_insensitive(self, tmp_path):
        file1 = tmp_path / "test1.py"
        file1.write_text("def todo(): pass")

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        matched, keywords = exporter.filter_files_by_keywords(files, ["TODO"])
        assert len(matched) == 1

    def test_filter_multiple_keywords(self, tmp_path):
        file1 = tmp_path / "test1.py"
        file1.write_text("def TODO(): pass\ndef FIXME(): pass")
        file2 = tmp_path / "test2.py"
        file2.write_text("def HACK(): pass")
        file3 = tmp_path / "test3.py"
        file3.write_text("def done(): pass")

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        matched, keywords = exporter.filter_files_by_keywords(files, ["TODO", "FIXME", "HACK"])
        assert len(matched) == 2
        assert "todo" in keywords
        assert "fixme" in keywords
        assert "hack" in keywords

    def test_filter_no_match(self, tmp_path):
        file1 = tmp_path / "test1.py"
        file1.write_text("def done(): pass")

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        matched, keywords = exporter.filter_files_by_keywords(files, ["NONEXISTENT"])
        assert len(matched) == 0
        assert len(keywords) == 0

    def test_filter_in_content(self, tmp_path):
        file1 = tmp_path / "config.py"
        file1.write_text("API_KEY = 'test'\nDEBUG = True")

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        matched, keywords = exporter.filter_files_by_keywords(files, ["API_KEY"])
        assert len(matched) == 1


class TestIntelligentInputParsing:
    """Tests for intelligent input parsing."""

    def test_parse_comma_separated(self, tmp_path):
        file1 = tmp_path / "test1.py"
        file1.write_text("print('1')")
        file2 = tmp_path / "test2.py"
        file2.write_text("print('2')")

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        result = exporter.parse_intelligent_input("test1.py, test2.py", files, tmp_path)
        assert len(result) == 2

    def test_parse_space_separated(self, tmp_path):
        file1 = tmp_path / "test1.py"
        file1.write_text("print('1')")
        file2 = tmp_path / "test2.py"
        file2.write_text("print('2')")

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        result = exporter.parse_intelligent_input("test1.py test2.py", files, tmp_path)
        assert len(result) == 2

    def test_parse_by_filename(self, tmp_path):
        file1 = tmp_path / "app.properties"
        file1.write_text("key=value")

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        result = exporter.parse_intelligent_input("app.properties", files, tmp_path)
        assert len(result) == 1
        assert result[0] == "app.properties"

    def test_parse_folder_name(self, tmp_path):
        (tmp_path / "src").mkdir()
        file1 = tmp_path / "src" / "main.py"
        file1.write_text("print('hello')")

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        result = exporter.parse_intelligent_input("src", files, tmp_path)
        assert len(result) == 1
        assert "src" in result[0]

    def test_parse_empty_string(self, tmp_path):
        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        result = exporter.parse_intelligent_input("", files, tmp_path)
        assert len(result) == 0

    def test_parse_only_whitespace(self, tmp_path):
        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        result = exporter.parse_intelligent_input("   ", files, tmp_path)
        assert len(result) == 0

    def test_parse_extension_matching(self, tmp_path):
        file1 = tmp_path / "test_script.py"
        file1.write_text("print('test')")

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        result = exporter.parse_intelligent_input("test_script.py", files, tmp_path)
        assert len(result) == 1


class TestCategoryNormalization:
    """Tests for category alias normalization."""

    def test_normalize_python_aliases(self):
        exporter = CodeExporter()
        result = exporter.normalize_categories(["py", "python"])
        assert result == ["python"]

    def test_normalize_typescript_aliases(self):
        exporter = CodeExporter()
        result = exporter.normalize_categories(["ts", "tsx", "typescript"])
        assert "typescript" in result

    def test_normalize_javascript_aliases(self):
        exporter = CodeExporter()
        result = exporter.normalize_categories(["js", "jsx", "javascript"])
        assert "javascript" in result

    def test_normalize_java_kotlin_aliases(self):
        exporter = CodeExporter()
        result = exporter.normalize_categories(["java", "kotlin", "android"])
        assert "java_kotlin" in result

    def test_normalize_ios_aliases(self):
        exporter = CodeExporter()
        result = exporter.normalize_categories(["ios", "swift", "apple"])
        assert "ios_apple" in result

    def test_normalize_web_aliases(self):
        exporter = CodeExporter()
        result = exporter.normalize_categories(["web", "frontend", "ui"])
        assert "web_ui" in result

    def test_normalize_shell_aliases(self):
        exporter = CodeExporter()
        result = exporter.normalize_categories(["shell", "sh", "bash", "zsh"])
        assert "shell" in result

    def test_normalize_flutter_aliases(self):
        exporter = CodeExporter()
        result = exporter.normalize_categories(["flutter", "dart"])
        assert "flutter" in result

    def test_normalize_config_aliases(self):
        exporter = CodeExporter()
        result = exporter.normalize_categories(["config", "docs"])
        assert "config_docs" in result


class TestParseCsvInput:
    """Tests for CSV input parsing."""

    def test_parse_single(self):
        result = CodeExporter.parse_csv_input("python")
        assert result == ["python"]

    def test_parse_multiple(self):
        result = CodeExporter.parse_csv_input("python, typescript, javascript")
        assert result == ["python", "typescript", "javascript"]

    def test_parse_empty(self):
        result = CodeExporter.parse_csv_input("")
        assert result == []

    def test_parse_with_trailing_comma(self):
        result = CodeExporter.parse_csv_input("python, typescript,")
        assert result == ["python", "typescript"]

    def test_parse_with_spaces(self):
        result = CodeExporter.parse_csv_input("  python  ,  typescript  ")
        assert result == ["python", "typescript"]


class TestConstants:
    """Tests for constants module."""

    def test_default_max_lines(self):
        assert constants.DEFAULT_MAX_LINES == 8000

    def test_large_file_warn_threshold(self):
        assert constants.LARGE_FILE_WARN_LINES == 1500

    def test_large_file_skip_threshold(self):
        assert constants.LARGE_FILE_SKIP_LINES == 3000

    def test_category_extensions_python(self):
        assert ".py" in constants.CATEGORY_EXTENSIONS["python"]

    def test_category_extensions_shell(self):
        assert ".sh" in constants.CATEGORY_EXTENSIONS["shell"]
        assert ".bash" in constants.CATEGORY_EXTENSIONS["shell"]
        assert ".zsh" in constants.CATEGORY_EXTENSIONS["shell"]

    def test_category_extensions_flutter(self):
        assert ".dart" in constants.CATEGORY_EXTENSIONS["flutter"]

    def test_category_descriptions_flutter(self):
        assert "flutter" in constants.CATEGORY_DESCRIPTIONS
        assert "Flutter" in constants.CATEGORY_DESCRIPTIONS["flutter"]

    def test_category_aliases_flutter(self):
        assert constants.CATEGORY_ALIASES["dart"] == "flutter"
        assert constants.CATEGORY_ALIASES["flutter"] == "flutter"

    def test_excluded_dirs(self):
        assert ".git" in constants.DEFAULT_EXCLUDED_DIRS
        assert "node_modules" in constants.DEFAULT_EXCLUDED_DIRS
        assert ".github" in constants.DEFAULT_EXCLUDED_DIRS

    def test_excluded_prefixes(self):
        assert "exported_sources" in constants.DEFAULT_EXCLUDED_PREFIXES

    def test_extra_excluded_patterns(self):
        assert "package-lock.json" in constants.EXTRA_EXCLUDED_PATTERNS
        assert "yarn.lock" in constants.EXTRA_EXCLUDED_PATTERNS

    def test_special_filenames_flutter(self):
        assert "pubspec.yaml" in constants.SPECIAL_FILENAMES
        assert "pubspec.lock" in constants.SPECIAL_FILENAMES
        assert "analysis_options.yaml" in constants.SPECIAL_FILENAMES


class TestScanFiles:
    """Tests for file scanning functionality."""

    def test_scan_finds_python_files(self, tmp_path):
        (tmp_path / "test.py").write_text("print('hello')")

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        assert any(f.rel_path.name == "test.py" for f in files)

    def test_scan_finds_shell_files(self, tmp_path):
        (tmp_path / "script.sh").write_text("#!/bin/bash\necho hello")

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        assert any(f.rel_path.name == "script.sh" for f in files)

    def test_scan_finds_dart_files(self, tmp_path):
        (tmp_path / "main.dart").write_text("void main() {}")

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        assert any(f.rel_path.name == "main.dart" for f in files)

    def test_scan_skips_git_dir(self, tmp_path):
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("fake")

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        assert not any(".git" in str(f.rel_path) for f in files)

    def test_scan_skips_exported_sources(self, tmp_path):
        exported_dir = tmp_path / "exported_sources_test"
        exported_dir.mkdir()
        (exported_dir / "bundle.txt").write_text("fake")

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        assert not any("exported_sources" in str(f.rel_path) for f in files)

    def test_scan_skips_secret_files(self, tmp_path):
        (tmp_path / ".env").write_text("SECRET=123")

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        assert not any(f.rel_path.name == ".env" for f in files)

    def test_scan_includes_other_files_when_secret_flag_false(self, tmp_path):
        (tmp_path / "normal_file.txt").write_text("Some normal content")

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=False)

        txt_files = [f for f in files if f.rel_path.name == "normal_file.txt"]
        assert len(txt_files) == 1


class TestBundleFilename:
    """Tests for bundle filename generation."""

    def test_bundle_includes_folder_name(self, tmp_path):
        project_root = tmp_path / "my_project"
        project_root.mkdir()
        (project_root / "test.py").write_text("print('hello')")

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(project_root, skip_secret_files=True)

        chunks, _ = exporter.split_into_chunks(files, 8000)
        bundles, _ = exporter.pack_chunks(chunks, 8000)

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        exporter.write_bundles_and_manifest(
            root=project_root,
            selected_files=files,
            bundles=bundles,
            output_dir=output_dir,
            max_lines=8000,
            skipped_reasons={},
            selection_metadata={"selection_mode": "all"},
            skip_secret_files=True,
            skipped_during_pack=[],
        )

        bundle_files = list(output_dir.glob("*_bundle_*.txt"))
        assert len(bundle_files) > 0
        assert "my_project" in bundle_files[0].name


class TestLargeFileHandling:
    """Tests for large file handling."""

    def test_large_file_warning(self, tmp_path):
        file1 = tmp_path / "large.py"
        file1.write_text("\n".join([f"line_{i}" for i in range(2000)]))

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        chunks, skipped = exporter.split_into_chunks(files, 8000)

        large_warnings = [s for s in skipped if s.get("reason") == "large_file_warning"]
        large_skips = [s for s in skipped if s.get("reason") == "large_file_exceeds_skip_threshold"]

        assert len(large_warnings) == 1 or len(large_skips) == 1

    def test_very_large_file_skipped(self, tmp_path):
        file1 = tmp_path / "huge.py"
        file1.write_text("\n".join([f"line_{i}" for i in range(5000)]))

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        chunks, skipped = exporter.split_into_chunks(files, 8000)

        large_skips = [s for s in skipped if s.get("reason") == "large_file_exceeds_skip_threshold"]
        assert len(large_skips) == 1

    def test_normal_file_not_skipped(self, tmp_path):
        file1 = tmp_path / "small.py"
        file1.write_text("\n".join([f"line_{i}" for i in range(100)]))

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        chunks, skipped = exporter.split_into_chunks(files, 8000)

        large_skips = [s for s in skipped if "large_file" in s.get("reason", "")]
        assert len(large_skips) == 0


class TestIsIgnored:
    """Tests for file ignore logic."""

    def test_ignored_git_dir(self):
        rel_path = Path(".git") / "config"
        gitignore = pathspec.PathSpec.from_lines("gitwildmatch", [])
        is_ignored, reason = CodeExporter.is_ignored(rel_path, gitignore, True)
        assert is_ignored is True

    def test_ignored_exported_sources(self):
        rel_path = Path("exported_sources_test") / "bundle.txt"
        gitignore = pathspec.PathSpec.from_lines("gitwildmatch", [])
        is_ignored, reason = CodeExporter.is_ignored(rel_path, gitignore, True)
        assert is_ignored is True
        assert reason == "default_excluded_prefix"

    def test_ignored_package_lock(self):
        rel_path = Path("package-lock.json")
        gitignore = pathspec.PathSpec.from_lines("gitwildmatch", [])
        is_ignored, reason = CodeExporter.is_ignored(rel_path, gitignore, True)
        assert is_ignored is True
        assert reason == "extra_excluded_pattern"

    def test_ignored_env_file(self):
        rel_path = Path(".env")
        gitignore = pathspec.PathSpec.from_lines("gitwildmatch", [])
        is_ignored, reason = CodeExporter.is_ignored(rel_path, gitignore, True)
        assert is_ignored is True
        assert reason == "secret_like_file"

    def test_not_ignored_normal_file(self):
        rel_path = Path("src") / "main.py"
        gitignore = pathspec.PathSpec.from_lines("gitwildmatch", [])
        is_ignored, reason = CodeExporter.is_ignored(rel_path, gitignore, True)
        assert is_ignored is False

    def test_ignored_by_gitignore(self):
        rel_path = Path("temp") / "output.txt"
        gitignore = pathspec.PathSpec.from_lines("gitwildmatch", ["temp/"])
        is_ignored, reason = CodeExporter.is_ignored(rel_path, gitignore, True)
        assert is_ignored is True
        assert reason == ".gitignore"
