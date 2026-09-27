"""Tests for icons module and filetree generation."""

import pytest
from pathlib import Path

from build_ai_context.icons import get_file_icon, get_icon_display_name, ICON_MAPPING, ICON_NAMES
from build_ai_context.exporter import CodeExporter
from build_ai_context.models import SourceFile


class TestIcons:
    """Tests for the icons module."""

    def test_python_icon(self):
        """Test Python file icon."""
        icon = get_file_icon("test.py")
        assert icon == "🐍"

    def test_typescript_icon(self):
        """Test TypeScript file icon."""
        icon = get_file_icon("test.ts")
        assert icon == "🔷"

    def test_tsx_icon(self):
        """Test TSX file icon."""
        icon = get_file_icon("test.tsx")
        assert icon == "🔷"

    def test_javascript_icon(self):
        """Test JavaScript file icon."""
        icon = get_file_icon("test.js")
        assert icon == "🟨"

    def test_jsx_icon(self):
        """Test JSX file icon."""
        icon = get_file_icon("test.jsx")
        assert icon == "🟨"

    def test_java_icon(self):
        """Test Java file icon."""
        icon = get_file_icon("Test.java")
        assert icon == "☕"

    def test_kotlin_icon(self):
        """Test Kotlin file icon."""
        icon = get_file_icon("MainActivity.kt")
        assert icon == "🟪"

    def test_gradle_icon(self):
        """Test Gradle file icon."""
        icon = get_file_icon("build.gradle.kts")
        assert icon == "🐘"

    def test_swift_icon(self):
        """Test Swift file icon."""
        icon = get_file_icon("AppDelegate.swift")
        assert icon == "🍎"

    def test_html_icon(self):
        """Test HTML file icon."""
        icon = get_file_icon("index.html")
        assert icon == "🌐"

    def test_css_icon(self):
        """Test CSS file icon."""
        icon = get_file_icon("styles.css")
        assert icon == "🎨"

    def test_markdown_icon(self):
        """Test Markdown file icon."""
        icon = get_file_icon("README.md")
        assert icon == "📕"

    def test_json_icon(self):
        """Test JSON file icon."""
        icon = get_file_icon("config.json")
        assert icon == "📋"

    def test_package_json_icon(self):
        """Test package.json has special icon."""
        icon = get_file_icon("package.json")
        assert icon == "📦"  # Node.js icon

    def test_yaml_icon(self):
        """Test YAML file icon."""
        icon = get_file_icon("config.yaml")
        assert icon == "📝"

    def test_xml_icon(self):
        """Test XML file icon."""
        icon = get_file_icon("config.xml")
        assert icon == "📄"

    def test_android_manifest_icon(self):
        """Test AndroidManifest.xml has special icon."""
        icon = get_file_icon("AndroidManifest.xml")
        assert icon == "🤖"  # Android icon

    def test_shell_icon(self):
        """Test shell file icon."""
        icon = get_file_icon("script.sh")
        assert icon == "🖥️"

    def test_docker_icon(self):
        """Test Dockerfile icon."""
        icon = get_file_icon("Dockerfile")
        assert icon == "🐳"

    def test_dart_icon(self):
        """Test Dart file icon."""
        icon = get_file_icon("main.dart")
        assert icon == "🎯"

    def test_unknown_extension_icon(self):
        """Test unknown extension falls back to default."""
        icon = get_file_icon("file.xyz")
        assert icon == "📄"

    def test_category_fallback(self):
        """Test category-based fallback."""
        icon = get_file_icon("file.xyz", category="python")
        assert icon == "🐍"

    def test_icon_display_name(self):
        """Test getting display name for icons."""
        assert get_icon_display_name("🐍") == "Python"
        assert get_icon_display_name("🟪") == "Kotlin"
        assert get_icon_display_name("📕") == "Markdown"
        assert get_icon_display_name("📄") == "XML"
        assert get_icon_display_name("❓") == "Other"


class TestFiletreeGeneration:
    """Tests for filetree generation (AI-agent-readable path lists)."""

    def _scan_tree(self, tmp_path):
        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)
        return exporter.generate_filetree(files, tmp_path)

    def test_filetree_lists_full_relative_paths_one_per_line(self, tmp_path):
        """Nested files must appear as full posix paths, one per line, trailing comma."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hello')")
        (tmp_path / "README.md").write_text("# Test")

        filetree = self._scan_tree(tmp_path)
        path_lines = self._section_lines(filetree, "paths:")

        assert path_lines == ["README.md,", "src/main.py,"]

    def test_filetree_omits_paths_csv_section(self, tmp_path):
        """A second full copy of every path is wasted tokens; paths: is enough."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hello')")
        (tmp_path / "README.md").write_text("# Test")
        (tmp_path / "app.kt").write_text("fun main() {}")

        filetree = self._scan_tree(tmp_path)

        assert "paths_csv:" not in filetree
        path_lines = self._section_lines(filetree, "paths:")
        assert path_lines == ["README.md,", "app.kt,", "src/main.py,"]

    def test_filetree_omits_icons_and_box_drawing(self, tmp_path):
        """Pretty-print chrome is noise for agents; emit plain text only."""
        (tmp_path / "test.py").write_text("print('hello')")
        (tmp_path / "test.kt").write_text("fun main() {}")

        filetree = self._scan_tree(tmp_path)

        for token in ("🐍", "🟪", "📊", "📁", "├──", "└──", "│"):
            assert token not in filetree

    def test_filetree_contains_file_count_and_type_counts(self, tmp_path):
        """Keep the summary, but as parseable key/count lines."""
        (tmp_path / "test.py").write_text("print('hello')")
        (tmp_path / "test2.py").write_text("print('world')")
        (tmp_path / "README.md").write_text("# Test")

        filetree = self._scan_tree(tmp_path)

        assert "file_count: 3" in filetree
        type_lines = self._section_lines(filetree, "types:")
        assert "python: 2" in type_lines
        assert "config_docs: 1" in type_lines

    def test_filetree_root_name(self, tmp_path):
        """Root is a labeled field, not a decorated tree header."""
        (tmp_path / "test.py").write_text("print('hello')")

        filetree = self._scan_tree(tmp_path)

        assert f"root: {tmp_path.name}" in filetree

    @staticmethod
    def _section_lines(filetree: str, header: str) -> list[str]:
        lines = filetree.splitlines()
        start = lines.index(header) + 1
        collected = []
        for line in lines[start:]:
            if not line.strip():
                break
            if line.endswith(":") and ":" in line and " " not in line.rstrip(":"):
                break
            collected.append(line)
        return collected


class TestRedactFlag:
    """Tests for redact flag functionality."""

    def test_redact_disabled_by_default(self, tmp_path):
        """Test that redaction is disabled by default."""
        exporter = CodeExporter(redact=False)
        assert exporter.redact is False

    def test_redact_enabled(self):
        """Test that redaction can be enabled."""
        exporter = CodeExporter(redact=True)
        assert exporter.redact is True

    def test_render_chunk_no_redaction(self):
        """Test that chunks are not redacted when redact=False."""
        from build_ai_context.models import FileChunk

        exporter = CodeExporter(redact=False)
        chunk = FileChunk(
            rel_path=Path("test.py"),
            category="python",
            chunk_index=1,
            chunk_count=1,
            start_line=1,
            end_line=1,
            total_file_lines=1,
            lines=['SECRET_KEY="mysecret123"'],
        )

        result = exporter.render_chunk_block(chunk)
        assert 'SECRET_KEY="mysecret123"' in result
        assert "<REDACTED>" not in result

    def test_render_chunk_with_redaction(self):
        """Test that chunks are redacted when redact=True."""
        from build_ai_context.models import FileChunk

        exporter = CodeExporter(redact=True)
        chunk = FileChunk(
            rel_path=Path("test.py"),
            category="python",
            chunk_index=1,
            chunk_count=1,
            start_line=1,
            end_line=1,
            total_file_lines=1,
            lines=['SECRET_KEY="mysecret123"'],
        )

        result = exporter.render_chunk_block(chunk)
        assert 'SECRET_KEY="mysecret123"' not in result
        assert "<REDACTED>" in result


class TestTimestampConsistency:
    """Tests for timestamp consistency in generated files."""

    def test_bundle_filename_format(self, tmp_path):
        """Test bundle filename contains timestamp."""
        (tmp_path / "test.py").write_text("print('hello')")

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        selected, _ = exporter.non_interactive_select_files(
            files, categories=[], path_prefixes=[], root=tmp_path
        )

        chunks = exporter.split_into_chunks(selected, max_lines=8000)

        # Create output directory
        out_dir = tmp_path / "output"
        out_dir.mkdir()

        # Write bundles with timestamp
        timestamp = "20260328T120000Z"
        for idx, bundle in enumerate(chunks, 1):
            bundle_name = f"test_bundle_{idx:03d}_{timestamp}.txt"
            bundle_path = out_dir / bundle_name
            bundle_path.write_text("test content")

        # Check bundle files exist with consistent timestamp
        bundle_files = list(out_dir.glob("test_bundle_*_20260328T120000Z.txt"))
        assert len(bundle_files) > 0


class TestGitignoreUpdates:
    """Tests for consolidated .gitignore updates."""

    def test_update_gitignore_migrates_legacy_entries(self, tmp_path):
        from build_ai_context.filetree import update_gitignore
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\nexported_sources*/\n*_file_tree_*.txt\n*_code_graph_*.txt\n*_code_graph_*.json\n")
        update_gitignore(tmp_path, "unused")
        lines = gitignore.read_text().splitlines()
        assert "*.pyc" in lines
        assert ".gen_files/**" in lines
        assert "exported_sources*/" not in lines
        assert "*_file_tree_*.txt" not in lines
        assert "*_code_graph_*.txt" not in lines
        assert "*_code_graph_*.json" not in lines

    def test_update_gitignore_is_idempotent(self, tmp_path):
        from build_ai_context.filetree import update_gitignore
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n")
        update_gitignore(tmp_path)
        first = gitignore.read_bytes()
        update_gitignore(tmp_path)
        assert gitignore.read_bytes() == first
        assert first.decode().splitlines().count(".gen_files/**") == 1

    def test_update_gitignore_does_not_create_file(self, tmp_path):
        from build_ai_context.filetree import update_gitignore
        update_gitignore(tmp_path)
        assert not (tmp_path / ".gitignore").exists()
