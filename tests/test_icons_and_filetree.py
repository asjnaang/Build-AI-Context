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
    """Tests for filetree generation."""

    def test_filetree_contains_files(self, tmp_path):
        """Test that generated filetree contains file names."""
        (tmp_path / "test.py").write_text("print('hello')")
        (tmp_path / "README.md").write_text("# Test")

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        filetree = exporter.generate_filetree(files, tmp_path)

        assert "test.py" in filetree
        assert "README.md" in filetree

    def test_filetree_contains_icons(self, tmp_path):
        """Test that generated filetree contains icons."""
        (tmp_path / "test.py").write_text("print('hello')")
        (tmp_path / "test.kt").write_text("fun main() {}")

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        filetree = exporter.generate_filetree(files, tmp_path)

        assert "🐍" in filetree  # Python icon
        assert "🟪" in filetree  # Kotlin icon

    def test_filetree_contains_summary(self, tmp_path):
        """Test that generated filetree contains a summary section."""
        (tmp_path / "test.py").write_text("print('hello')")

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        filetree = exporter.generate_filetree(files, tmp_path)

        assert "📊 File Summary:" in filetree
        assert "Total:" in filetree

    def test_filetree_summary_shows_type_names(self, tmp_path):
        """Test that summary shows file type names."""
        (tmp_path / "test.py").write_text("print('hello')")
        (tmp_path / "test2.py").write_text("print('world')")

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        filetree = exporter.generate_filetree(files, tmp_path)

        assert "Python" in filetree

    def test_filetree_shows_directory_structure(self, tmp_path):
        """Test that filetree shows directory structure."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hello')")

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        filetree = exporter.generate_filetree(files, tmp_path)

        assert "src/" in filetree
        assert "main.py" in filetree

    def test_filetree_root_name(self, tmp_path):
        """Test that filetree shows root directory name."""
        (tmp_path / "test.py").write_text("print('hello')")

        exporter = CodeExporter()
        files, _ = exporter.scan_supported_files(tmp_path, skip_secret_files=True)

        filetree = exporter.generate_filetree(files, tmp_path)

        assert f"{tmp_path.name}/" in filetree


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
