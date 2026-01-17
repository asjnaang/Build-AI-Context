"""
Data models for anything_to_text package.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class SourceFile:
    """Represents a discovered source file with its metadata."""

    abs_path: Path
    rel_path: Path
    category: str
    line_count: int
    size_bytes: int
    sha256: str
    lines: List[str] = field(repr=False)


@dataclass(frozen=True)
class FileChunk:
    """Represents a chunk of a file, used when splitting large files."""

    rel_path: Path
    category: str
    chunk_index: int
    chunk_count: int
    start_line: int
    end_line: int
    total_file_lines: int
    lines: List[str] = field(repr=False)

    @property
    def line_count(self) -> int:
        """Return the number of lines in this chunk."""
        return len(self.lines)


@dataclass
class ExportConfig:
    """Configuration for the export process."""

    project_root: Path
    max_lines: int = 8000
    output_dir: Path | None = None
    include_secret_files: bool = False
    categories: List[str] = field(default_factory=list)
    paths: List[str] = field(default_factory=list)
    name_filters: List[str] = field(default_factory=list)
    interactive: bool = True
    fancy_ui: bool = False
    project_overview: bool = False


@dataclass
class ExportResult:
    """Result of an export operation."""

    output_dir: Path
    manifest_path: Path
    overview_path: Path | None
    bundles_created: int
    files_exported: int
    skipped_items: List[dict] = field(default_factory=list)
    missing_paths: List[str] = field(default_factory=list)
