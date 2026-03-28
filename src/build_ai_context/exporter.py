"""
Core export functionality for build_ai_context package.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from build_ai_context import chunking, filetree, scanner, writing
from build_ai_context.models import ExportConfig, ExportResult, FileChunk, SourceFile


class CodeExporter:
    """
    Main exporter class for converting source code files to AI-friendly text bundles.

    This class handles scanning, filtering, chunking, and exporting source files
    into text bundles with a manifest for AI assistant consumption.
    """

    def __init__(self, config: ExportConfig | None = None, redact: bool = False):
        """Initialize the exporter with optional configuration."""
        self.config = config
        self.redact = redact
        self._rich_available = False
        self._console = None
        self._questionary_available = False
        self._setup_optional_dependencies()

    def _setup_optional_dependencies(self) -> None:
        """Set up optional dependencies for enhanced output."""
        try:
            from rich.console import Console
            from rich.table import Table

            self._rich_available = True
            self._console = Console()
            self._table_class = Table
        except ImportError:
            self._rich_available = False
            self._console = None
            self._table_class = None

        try:
            import questionary

            self._questionary_available = True
            self._questionary = questionary
        except ImportError:
            self._questionary_available = False
            self._questionary = None

    def print_info(self, message: str) -> None:
        """Print an informational message."""
        if self._console:
            self._console.print(f"[cyan]{message}[/cyan]")
        else:
            print(message)

    def print_success(self, message: str) -> None:
        """Print a success message."""
        if self._console:
            self._console.print(f"[green]{message}[/green]")
        else:
            print(message)

    def print_warning(self, message: str) -> None:
        """Print a warning message."""
        if self._console:
            self._console.print(f"[yellow]{message}[/yellow]")
        else:
            print(message)

    def print_error(self, message: str) -> None:
        """Print an error message."""
        if self._console:
            self._console.print(f"[bold red]{message}[/bold red]")
        else:
            print(message)

    # -------------------------------------------------------------------------
    # Delegated methods from scanner module
    # -------------------------------------------------------------------------
    load_gitignore_spec = staticmethod(scanner.load_gitignore_spec)
    path_matches_any_pattern = staticmethod(scanner.path_matches_any_pattern)
    should_skip_by_dir = staticmethod(scanner.should_skip_by_dir)
    should_skip_by_prefix = staticmethod(scanner.should_skip_by_prefix)
    is_ignored = staticmethod(scanner.is_ignored)
    detect_category = staticmethod(scanner.detect_category)
    is_probably_binary = staticmethod(scanner.is_probably_binary)
    read_text_lines = staticmethod(scanner.read_text_lines)
    sha256_of_lines = staticmethod(scanner.sha256_of_lines)
    scan_supported_files = staticmethod(scanner.scan_supported_files)
    summarize_by_category = staticmethod(scanner.summarize_by_category)
    summarize_top_folders = staticmethod(scanner.summarize_top_folders)
    normalize_categories = staticmethod(scanner.normalize_categories)
    parse_csv_input = staticmethod(scanner.parse_csv_input)
    filter_files_by_paths = staticmethod(scanner.filter_files_by_paths)
    _normalize_selection_paths = staticmethod(scanner._normalize_selection_paths)
    filter_files_by_keywords = staticmethod(scanner.filter_files_by_keywords)

    def parse_intelligent_input(
        self, raw: str, files: Sequence[SourceFile], root: Path
    ) -> List[str]:
        """Intelligently parse input that might have mixed commas, spaces, or no separators."""
        return scanner.parse_intelligent_input(raw, files, root)

    def non_interactive_select_files(
        self,
        all_files: Sequence[SourceFile],
        categories: Sequence[str],
        path_prefixes: Sequence[str],
        root: Path,
    ) -> Tuple[List[SourceFile], Dict[str, object]]:
        """Select files non-interactively based on categories and paths."""
        return scanner.non_interactive_select_files(all_files, categories, path_prefixes, root)

    # -------------------------------------------------------------------------
    # Delegated methods from chunking module
    # -------------------------------------------------------------------------
    bundle_header = staticmethod(chunking.bundle_header)
    bundle_footer = staticmethod(chunking.bundle_footer)

    def render_chunk_block(self, chunk: FileChunk) -> str:
        """Render a complete chunk block with header and footer."""
        return chunking.render_chunk_block(chunk, self.redact)

    def chunk_overhead_lines(self) -> int:
        """Calculate the overhead lines added by chunk headers and footers."""
        return chunking.chunk_overhead_lines(self.redact)

    def split_into_chunks(
        self, files: Sequence[SourceFile], max_lines: int
    ) -> Tuple[List[FileChunk], List[Dict[str, object]]]:
        """Split files into chunks respecting max lines."""
        return chunking.split_into_chunks(files, max_lines, self.redact)

    def pack_chunks(
        self, chunks: Sequence[FileChunk], max_lines: int
    ) -> Tuple[List[List[FileChunk]], List[Dict[str, object]]]:
        """Pack chunks into bundles respecting max lines."""
        return chunking.pack_chunks(chunks, max_lines, self.redact)

    # -------------------------------------------------------------------------
    # Delegated methods from filetree module
    # -------------------------------------------------------------------------
    sanitize_output_dir_name = staticmethod(filetree.sanitize_output_dir_name)

    def generate_filetree(self, files: Sequence[SourceFile], root: Path) -> str:
        """Generate a filetree with full paths for AI assistants."""
        return filetree.generate_filetree(files, root)

    update_gitignore = staticmethod(filetree.update_gitignore)

    # -------------------------------------------------------------------------
    # Delegated methods from writing module
    # -------------------------------------------------------------------------
    detect_dependency_files = staticmethod(writing.detect_dependency_files)
    detect_frameworks = staticmethod(writing.detect_frameworks)
    suggest_reading_order = staticmethod(writing.suggest_reading_order)

    def write_project_overview(
        self,
        root: Path,
        all_files: Sequence[SourceFile],
        selected_files: Sequence[SourceFile],
        output_dir: Path,
        selection_metadata: Dict[str, object],
        manifest_name: str,
    ) -> Path:
        """Generate a PROJECT_OVERVIEW.txt file."""
        return writing.write_project_overview(
            root,
            all_files,
            selected_files,
            output_dir,
            selection_metadata,
            manifest_name,
            self.summarize_by_category,
            self.summarize_top_folders,
        )

    def write_bundles_and_manifest(
        self,
        root: Path,
        selected_files: Sequence[SourceFile],
        bundles: Sequence[Sequence[FileChunk]],
        output_dir: Path,
        max_lines: int,
        skipped_reasons: Dict[str, int],
        selection_metadata: Dict[str, object],
        skip_secret_files: bool,
        skipped_during_pack: Sequence[Dict[str, object]],
        filetree_name: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> Path:
        """Write bundles and manifest to the output directory."""
        return writing.write_bundles_and_manifest(
            root,
            selected_files,
            bundles,
            output_dir,
            max_lines,
            skipped_reasons,
            selection_metadata,
            skip_secret_files,
            skipped_during_pack,
            filetree_name,
            timestamp,
            self.redact,
        )

    # -------------------------------------------------------------------------
    # Main export method
    # -------------------------------------------------------------------------
    def export(
        self,
        project_root: Path | str | None = None,
        max_lines: int = 8000,
        output_dir: Path | str | None = None,
        include_secret_files: bool = False,
        categories: List[str] | None = None,
        paths: List[str] | None = None,
        interactive: bool = True,
        project_overview: bool = False,
        include_filetree: bool = True,
    ) -> ExportResult:
        """Run the full export process."""
        root = Path(project_root or Path.cwd()).expanduser().resolve()
        if not root.exists():
            raise ValueError(f"Project root does not exist: {root}")
        if not root.is_dir():
            raise ValueError(f"Project root is not a directory: {root}")

        self.print_info(f"Scanning project: {root}")

        skip_secret_files = not include_secret_files
        all_files, skipped_reasons = self.scan_supported_files(root, skip_secret_files)

        if not all_files:
            self.print_warning("No supported files found.")
            return ExportResult(
                output_dir=Path(output_dir or "."),
                manifest_path=Path("."),
                overview_path=None,
                bundles_created=0,
                files_exported=0,
                filetree_path=None,
            )

        self.print_info(f"Detected {len(all_files)} supported text file(s).")

        if interactive:
            self.print_warning("Interactive mode not yet implemented in package API.")
            self.print_info("Falling back to non-interactive mode with all files.")
            selected_files = list(all_files)
            selection_metadata = {
                "selection_mode": "all",
                "selected_categories": [],
                "selected_paths": [],
                "name_filters": [],
                "missing_paths": [],
            }
        else:
            selected_files, selection_metadata = self.non_interactive_select_files(
                all_files,
                categories=categories or [],
                path_prefixes=paths or [],
                root=root,
            )

        if not selected_files:
            self.print_warning("No files selected. Nothing was exported.")
            return ExportResult(
                output_dir=Path(output_dir or "."),
                manifest_path=Path("."),
                overview_path=None,
                bundles_created=0,
                files_exported=0,
                filetree_path=None,
            )

        chunks, skipped_during_split = self.split_into_chunks(selected_files, max_lines)
        bundles, skipped_during_pack = self.pack_chunks(chunks, max_lines)
        skipped_during_processing = skipped_during_split + skipped_during_pack

        out_dir = (
            Path(output_dir).expanduser().resolve()
            if output_dir
            else Path.cwd() / self.sanitize_output_dir_name(root)
        )

        # Extract timestamp from output_dir name for consistency
        dir_name = out_dir.name
        dir_parts = dir_name.split("_")
        timestamp = dir_parts[-1] if len(dir_parts) >= 3 else "20260328T000000Z"

        # Always generate filetree from ALL files - AI needs full project view
        out_dir.mkdir(parents=True, exist_ok=True)
        filetree_content = self.generate_filetree(all_files, root)
        folder_name = root.name.replace(" ", "_")
        filetree_name = f"{folder_name}_file_tree_{timestamp}.txt"
        filetree_path: Optional[Path] = out_dir / filetree_name
        filetree_path.write_text(filetree_content, encoding="utf-8")
        self.print_success(f"Filetree created  : {filetree_path}")

        manifest_path = self.write_bundles_and_manifest(
            root=root,
            selected_files=selected_files,
            bundles=bundles,
            output_dir=out_dir,
            max_lines=max_lines,
            skipped_reasons=skipped_reasons,
            selection_metadata=selection_metadata,
            skip_secret_files=skip_secret_files,
            skipped_during_pack=skipped_during_processing,
            filetree_name=filetree_name,
            timestamp=timestamp,
        )

        overview_path = None
        if project_overview:
            overview_path = self.write_project_overview(
                root=root,
                all_files=all_files,
                selected_files=selected_files,
                output_dir=out_dir,
                selection_metadata=selection_metadata,
                manifest_name=manifest_path.name,
            )

        self.print_success("\nExport complete.")
        self.print_success(f"Output directory : {out_dir}")
        self.print_success(f"Manifest         : {manifest_path}")
        if overview_path is not None:
            self.print_success(f"Project overview : {overview_path}")
        if filetree_path is not None:
            self.print_success(f"Filetree         : {filetree_path}")
        self.print_success(f"Bundles created  : {len(bundles)}")
        self.print_success(f"Files exported   : {len(selected_files)}")

        return ExportResult(
            output_dir=out_dir,
            manifest_path=manifest_path,
            overview_path=overview_path,
            bundles_created=len(bundles),
            files_exported=len(selected_files),
            skipped_items=skipped_during_processing,
            missing_paths=list(selection_metadata.get("missing_paths", [])),
            filetree_path=filetree_path,
        )
