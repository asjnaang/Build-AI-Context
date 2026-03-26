"""
Core export functionality for build_ai_context package.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import pathspec

from build_ai_context.constants import (
    CATEGORY_ALIASES,
    CATEGORY_DESCRIPTIONS,
    CATEGORY_EXTENSIONS,
    DEFAULT_EXCLUDED_DIRS,
    DEFAULT_EXCLUDED_PREFIXES,
    DEFAULT_MAX_LINES,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SECRET_PATTERNS,
    DEFAULT_TEXT_ENCODING,
    EXTRA_EXCLUDED_PATTERNS,
    INTERESTING_FILES,
    LARGE_FILE_SKIP_LINES,
    LARGE_FILE_WARN_LINES,
    SPECIAL_FILENAMES,
)
from build_ai_context.models import ExportConfig, ExportResult, FileChunk, SourceFile
from build_ai_context.redact import redact_text


class CodeExporter:
    """
    Main exporter class for converting source code files to AI-friendly text bundles.

    This class handles scanning, filtering, chunking, and exporting source files
    into text bundles with a manifest for AI assistant consumption.
    """

    def __init__(self, config: ExportConfig | None = None):
        """Initialize the exporter with optional configuration."""
        self.config = config
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
    # .gitignore and path filtering
    # -------------------------------------------------------------------------
    @staticmethod
    def load_gitignore_spec(root: Path) -> pathspec.PathSpec:
        """Load .gitignore patterns from the project root."""
        gitignore_path = root / ".gitignore"
        patterns: List[str] = []
        if gitignore_path.exists():
            try:
                patterns.extend(
                    gitignore_path.read_text(encoding=DEFAULT_TEXT_ENCODING).splitlines()
                )
            except UnicodeDecodeError:
                patterns.extend(gitignore_path.read_text(errors="ignore").splitlines())
        return pathspec.PathSpec.from_lines("gitwildmatch", patterns)

    @staticmethod
    def path_matches_any_pattern(rel_path: str, patterns: Iterable[str]) -> bool:
        """Check if a path matches any of the given patterns."""
        return any(
            fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(Path(rel_path).name, pattern)
            for pattern in patterns
        )

    @staticmethod
    def should_skip_by_dir(rel_path: Path) -> bool:
        """Check if a path should be skipped based on directory name."""
        return any(part in DEFAULT_EXCLUDED_DIRS for part in rel_path.parts)

    @classmethod
    def should_skip_by_prefix(cls, rel_path: Path) -> bool:
        """Check if a path should be skipped based on directory prefix."""
        rel_str = rel_path.as_posix()
        return any(rel_str.startswith(prefix) for prefix in DEFAULT_EXCLUDED_PREFIXES)

    @classmethod
    def is_ignored(
        cls, rel_path: Path, gitignore_spec: pathspec.PathSpec, skip_secret_files: bool
    ) -> Tuple[bool, str]:
        """Check if a file should be ignored and return the reason."""
        rel_str = rel_path.as_posix()
        if cls.should_skip_by_dir(rel_path):
            return True, "default_excluded_dir"
        if cls.should_skip_by_prefix(rel_path):
            return True, "default_excluded_prefix"
        if gitignore_spec.match_file(rel_str):
            return True, ".gitignore"
        if cls.path_matches_any_pattern(rel_str, EXTRA_EXCLUDED_PATTERNS):
            return True, "extra_excluded_pattern"
        if skip_secret_files and cls.path_matches_any_pattern(rel_str, DEFAULT_SECRET_PATTERNS):
            return True, "secret_like_file"
        return False, ""

    # -------------------------------------------------------------------------
    # File detection and reading
    # -------------------------------------------------------------------------
    @staticmethod
    def detect_category(path: Path) -> str | None:
        """Detect the category of a file based on its name and extension."""
        name = path.name
        suffix = path.suffix.lower()
        if name in SPECIAL_FILENAMES:
            if name in {"Podfile", ".swiftlint.yml"}:
                return "ios_apple"
            if name in {
                "AndroidManifest.xml",
                "gradle.properties",
                "settings.gradle",
                "settings.gradle.kts",
                "build.gradle",
                "build.gradle.kts",
            }:
                return "java_kotlin"
            return "config_docs"
        for category, extensions in CATEGORY_EXTENSIONS.items():
            if suffix in extensions:
                return category
        return None

    @staticmethod
    def is_probably_binary(path: Path) -> bool:
        """Check if a file is likely binary by reading a sample."""
        try:
            with path.open("rb") as fh:
                sample = fh.read(4096)
            return b"\x00" in sample
        except OSError:
            return True

    @staticmethod
    def read_text_lines(path: Path) -> List[str]:
        """Read a text file with multiple encoding attempts."""
        encodings = ["utf-8", "utf-8-sig", "latin-1"]
        last_error: Exception | None = None
        for encoding in encodings:
            try:
                return path.read_text(encoding=encoding).splitlines()
            except UnicodeDecodeError as exc:
                last_error = exc
        if last_error is not None:
            return path.read_text(encoding="utf-8", errors="ignore").splitlines()
        return []

    @staticmethod
    def sha256_of_lines(lines: Sequence[str]) -> str:
        """Calculate SHA256 hash of file lines."""
        joined = "\n".join(lines).encode("utf-8", errors="ignore")
        return hashlib.sha256(joined).hexdigest()

    def scan_supported_files(
        self, root: Path, skip_secret_files: bool
    ) -> Tuple[List[SourceFile], Dict[str, int]]:
        """Scan the project root for supported files."""
        gitignore_spec = self.load_gitignore_spec(root)
        discovered: List[SourceFile] = []
        skipped_reasons: Dict[str, int] = defaultdict(int)

        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel_path = path.relative_to(root)
            ignored, reason = self.is_ignored(rel_path, gitignore_spec, skip_secret_files)
            if ignored:
                skipped_reasons[reason] += 1
                continue
            category = self.detect_category(path)
            if not category:
                skipped_reasons["unsupported_type"] += 1
                continue
            if self.is_probably_binary(path):
                skipped_reasons["binary"] += 1
                continue
            try:
                lines = self.read_text_lines(path)
            except OSError:
                skipped_reasons["read_error"] += 1
                continue
            discovered.append(
                SourceFile(
                    abs_path=path.resolve(),
                    rel_path=rel_path,
                    category=category,
                    line_count=len(lines),
                    size_bytes=path.stat().st_size,
                    sha256=self.sha256_of_lines(lines),
                    lines=lines,
                )
            )
        discovered.sort(key=lambda item: item.rel_path.as_posix())
        return discovered, dict(sorted(skipped_reasons.items()))

    # -------------------------------------------------------------------------
    # Selection helpers
    # -------------------------------------------------------------------------
    @staticmethod
    def summarize_by_category(files: Sequence[SourceFile]) -> Dict[str, Dict[str, int]]:
        """Summarize files by category."""
        summary: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"files": 0, "lines": 0, "bytes": 0}
        )
        for item in files:
            summary[item.category]["files"] += 1
            summary[item.category]["lines"] += item.line_count
            summary[item.category]["bytes"] += item.size_bytes
        return dict(summary)

    @staticmethod
    def summarize_top_folders(
        files: Sequence[SourceFile], max_depth: int = 2
    ) -> Dict[str, Dict[str, int]]:
        """Summarize files by top-level folders."""
        summary: Dict[str, Dict[str, int]] = defaultdict(lambda: {"files": 0, "lines": 0})
        for item in files:
            parts = item.rel_path.parts[:max_depth]
            folder = "/".join(parts[:-1]) if len(parts) > 1 else "."
            summary[folder]["files"] += 1
            summary[folder]["lines"] += item.line_count
        return dict(sorted(summary.items(), key=lambda pair: (-pair[1]["files"], pair[0])))

    @staticmethod
    def normalize_categories(values: Sequence[str]) -> List[str]:
        """Normalize category names using aliases."""
        normalized: List[str] = []
        for value in values:
            key = value.strip().lower()
            if not key:
                continue
            mapped = CATEGORY_ALIASES.get(key, key)
            if mapped in CATEGORY_DESCRIPTIONS and mapped not in normalized:
                normalized.append(mapped)
        return normalized

    @staticmethod
    def parse_csv_input(raw: str) -> List[str]:
        """Parse comma-separated input into a list of strings."""
        return [token.strip() for token in raw.split(",") if token.strip()]

    def parse_intelligent_input(
        self, raw: str, files: Sequence[SourceFile], root: Path
    ) -> List[str]:
        """Intelligently parse input that might have mixed commas, spaces, or no separators."""
        if not raw.strip():
            return []

        all_path_strs = {f.rel_path.as_posix() for f in files}
        all_names = {f.rel_path.name for f in files}
        found_paths = []

        parts = [p.strip() for p in re.split(r"[,;\s]+", raw) if p.strip()]

        for part in parts:
            original_part = part

            if Path(part).is_absolute():
                try:
                    rel = Path(part).resolve().relative_to(root)
                    part = rel.as_posix()
                except ValueError:
                    pass

            if part in all_path_strs:
                if part not in found_paths:
                    found_paths.append(part)
                continue

            if part in all_names:
                for p in all_path_strs:
                    if p.endswith("/" + part) or p == part:
                        if p not in found_paths:
                            found_paths.append(p)
                continue

            exact_matches = [p for p in all_path_strs if p == part or p.endswith("/" + part)]
            if exact_matches:
                for m in exact_matches:
                    if m not in found_paths:
                        found_paths.append(m)
                continue

            folder_matches = [
                p for p in all_path_strs if p.startswith(part + "/") or "/" + part + "/" in p
            ]
            if folder_matches:
                for m in folder_matches:
                    if m not in found_paths:
                        found_paths.append(m)
                continue

            contains_matches = [p for p in all_path_strs if part in p]
            if contains_matches:
                for m in contains_matches:
                    if m not in found_paths:
                        found_paths.append(m)
                continue

            partial = [
                p
                for p in all_path_strs
                if p.replace("/", "")
                .replace("\\", "")
                .startswith(part.replace("/", "").replace("\\", ""))
            ]
            if partial:
                for m in partial:
                    if m not in found_paths:
                        found_paths.append(m)
                continue

            for ext in [
                ".dart",
                ".py",
                ".js",
                ".ts",
                ".kt",
                ".java",
                ".swift",
                ".md",
                ".json",
                ".yaml",
                ".xml",
                ".txt",
                ".properties",
            ]:
                if ext in part:
                    matching_files = [
                        p for p in all_path_strs if p.endswith(part) or p.endswith("/" + part)
                    ]
                    for m in matching_files:
                        if m not in found_paths:
                            found_paths.append(m)
                    if matching_files:
                        break

        return found_paths

    # -------------------------------------------------------------------------
    # Non-interactive selection
    # -------------------------------------------------------------------------
    def filter_files_by_paths(
        self,
        files: Sequence[SourceFile],
        root: Path,
        raw_paths: Sequence[str],
        *,
        interactive: bool,
        fancy: bool,
    ) -> Tuple[List[SourceFile], List[str], List[str]]:
        """Filter files by path patterns."""
        normalized_paths = self._normalize_selection_paths(raw_paths, root)
        if not normalized_paths:
            return list(files), [], []

        matched: List[SourceFile] = []
        missing_inputs: List[str] = []

        for raw_input, normalized in zip(raw_paths, normalized_paths):
            raw_candidate = Path(raw_input).expanduser()
            abs_candidate = (
                raw_candidate.resolve()
                if raw_candidate.is_absolute()
                else (root / raw_candidate).resolve()
            )
            raw_name = raw_candidate.name
            looks_like_file_name_only = (
                not raw_candidate.is_absolute() and "/" not in raw_input and "\\" not in raw_input
            )

            exact_matches = [
                item
                for item in files
                if item.rel_path.as_posix() == normalized
                or item.rel_path.as_posix().startswith(normalized.rstrip("/") + "/")
                or item.abs_path.resolve() == abs_candidate
            ]

            if exact_matches:
                for item in exact_matches:
                    if item not in matched:
                        matched.append(item)
                continue

            if looks_like_file_name_only:
                basename_matches = [item for item in files if item.rel_path.name == raw_name]
                if basename_matches:
                    for item in basename_matches:
                        if item not in matched:
                            matched.append(item)
                    continue

            missing_inputs.append(raw_input)

        matched.sort(key=lambda item: item.rel_path.as_posix())
        return matched, normalized_paths, missing_inputs

    @staticmethod
    def _normalize_selection_paths(raw_paths: Sequence[str], root: Path) -> List[str]:
        """Normalize path selections."""
        normalized: List[str] = []
        for raw in raw_paths:
            value = raw.strip()
            if not value:
                continue
            candidate = Path(value).expanduser()
            if candidate.is_absolute():
                try:
                    rel = candidate.resolve().relative_to(root)
                    value = rel.as_posix()
                except Exception:
                    value = candidate.resolve().as_posix()
            else:
                value = value.rstrip("/")
            if value not in normalized:
                normalized.append(value)
        return normalized

    def filter_files_by_keywords(
        self, files: Sequence[SourceFile], keywords: Sequence[str]
    ) -> Tuple[List[SourceFile], List[str]]:
        """Filter files by keywords found in their content."""
        matched: List[SourceFile] = []
        matched_keywords: List[str] = []
        keywords_lower = [k.lower() for k in keywords]

        for item in files:
            content_lower = "\n".join(item.lines).lower()
            found_keywords = [kw for kw in keywords_lower if kw in content_lower]
            if found_keywords:
                matched.append(item)
                for kw in found_keywords:
                    if kw not in matched_keywords:
                        matched_keywords.append(kw)

        matched.sort(key=lambda item: item.rel_path.as_posix())
        return matched, sorted(matched_keywords)

    def non_interactive_select_files(
        self,
        all_files: Sequence[SourceFile],
        categories: Sequence[str],
        path_prefixes: Sequence[str],
        root: Path,
    ) -> Tuple[List[SourceFile], Dict[str, object]]:
        """Select files non-interactively based on categories and paths."""
        selected = list(all_files)
        if categories:
            normalized_categories = self.normalize_categories(categories)
            invalid = [
                item
                for item in categories
                if CATEGORY_ALIASES.get(item.strip().lower(), item.strip().lower())
                not in CATEGORY_DESCRIPTIONS
            ]
            if invalid:
                raise ValueError(f"Unsupported categories requested: {', '.join(invalid)}")
            selected = [item for item in selected if item.category in normalized_categories]
            categories = normalized_categories
        else:
            categories = []
        missing_paths: List[str] = []
        normalized_paths: List[str] = []
        if path_prefixes:
            selected, normalized_paths, missing_paths = self.filter_files_by_paths(
                selected,
                root,
                path_prefixes,
                interactive=False,
                fancy=False,
            )
        selected.sort(key=lambda item: item.rel_path.as_posix())
        return selected, {
            "selection_mode": "non_interactive",
            "selected_categories": list(categories),
            "selected_paths": normalized_paths,
            "name_filters": [],
            "missing_paths": missing_paths,
        }

    # -------------------------------------------------------------------------
    # Chunking and packing
    # -------------------------------------------------------------------------
    @staticmethod
    def bundle_header(chunk: FileChunk) -> str:
        """Generate the header for a file chunk in a bundle."""
        return (
            f"\n# ===== BEGIN FILE: {chunk.rel_path.as_posix()} =====\n"
            f"# category : {chunk.category}\n"
            f"# chunk : {chunk.chunk_index}/{chunk.chunk_count}\n"
            f"# line_range : {chunk.start_line}-{chunk.end_line}\n"
            f"# total_lines : {chunk.total_file_lines}\n"
            f"# ===== CONTENT =====\n"
        )

    @staticmethod
    def bundle_footer(chunk: FileChunk) -> str:
        """Generate the footer for a file chunk in a bundle."""
        return (
            f"# ===== END FILE: {chunk.rel_path.as_posix()} "
            f"(chunk {chunk.chunk_index}/{chunk.chunk_count}) =====\n"
        )

    def render_chunk_block(self, chunk: FileChunk) -> str:
        """Render a complete chunk block with header and footer.

        All lines are passed through redaction to remove secrets/tokens.
        """
        parts: List[str] = [self.bundle_header(chunk)]
        for line in chunk.lines:
            parts.append(redact_text(line) + "\n")
        parts.append(self.bundle_footer(chunk))
        return "".join(parts)

    def chunk_overhead_lines(self) -> int:
        """Calculate the overhead lines added by chunk headers and footers."""
        dummy = FileChunk(
            rel_path=Path("dummy.py"),
            category="python",
            chunk_index=1,
            chunk_count=1,
            start_line=1,
            end_line=1,
            total_file_lines=1,
            lines=["x"],
        )
        return len(self.render_chunk_block(dummy).splitlines()) - 1

    def split_into_chunks(
        self, files: Sequence[SourceFile], max_lines: int
    ) -> Tuple[List[FileChunk], List[Dict[str, object]]]:
        """Split files into chunks respecting max_lines limit."""
        skipped: List[Dict[str, object]] = []
        chunks: List[FileChunk] = []
        large_file_warnings: List[Dict[str, object]] = []

        overhead = self.chunk_overhead_lines()
        content_limit = max_lines - overhead
        if content_limit <= 0:
            raise ValueError(
                f"--max-lines must be greater than bundle wrapper overhead ({overhead})."
            )

        for item in files:
            if item.line_count >= LARGE_FILE_SKIP_LINES:
                skipped.append(
                    {
                        "path": item.rel_path.as_posix(),
                        "reason": "large_file_exceeds_skip_threshold",
                        "line_count": item.line_count,
                        "threshold": LARGE_FILE_SKIP_LINES,
                    }
                )
                continue

            if item.line_count >= LARGE_FILE_WARN_LINES:
                large_file_warnings.append(
                    {
                        "path": item.rel_path.as_posix(),
                        "reason": "large_file_warning",
                        "line_count": item.line_count,
                        "threshold": LARGE_FILE_WARN_LINES,
                    }
                )

            if item.line_count <= content_limit:
                chunks.append(
                    FileChunk(
                        rel_path=item.rel_path,
                        category=item.category,
                        chunk_index=1,
                        chunk_count=1,
                        start_line=1 if item.line_count > 0 else 0,
                        end_line=item.line_count,
                        total_file_lines=item.line_count,
                        lines=item.lines,
                    )
                )
                continue

            total_chunks = (item.line_count + content_limit - 1) // content_limit
            if total_chunks <= 0:
                skipped.append(
                    {
                        "path": item.rel_path.as_posix(),
                        "reason": "unable_to_chunk",
                        "line_count": item.line_count,
                    }
                )
                continue

            item_chunks: List[FileChunk] = []
            chunk_failed = False
            for index in range(total_chunks):
                start = index * content_limit
                end = min(start + content_limit, item.line_count)
                chunk_lines = item.lines[start:end]
                chunk = FileChunk(
                    rel_path=item.rel_path,
                    category=item.category,
                    chunk_index=index + 1,
                    chunk_count=total_chunks,
                    start_line=start + 1,
                    end_line=end,
                    total_file_lines=item.line_count,
                    lines=chunk_lines,
                )
                rendered_line_count = len(self.render_chunk_block(chunk).splitlines())
                if rendered_line_count > max_lines:
                    skipped.append(
                        {
                            "path": item.rel_path.as_posix(),
                            "reason": "rendered_chunk_exceeds_limit",
                            "line_count": item.line_count,
                            "chunk_index": index + 1,
                            "chunk_count": total_chunks,
                            "rendered_line_count": rendered_line_count,
                        }
                    )
                    chunk_failed = True
                    break
                item_chunks.append(chunk)
            if not chunk_failed:
                chunks.extend(item_chunks)

        for warning in large_file_warnings:
            skipped.append(warning)

        return chunks, skipped

    def pack_chunks(
        self, chunks: Sequence[FileChunk], max_lines: int
    ) -> Tuple[List[List[FileChunk]], List[Dict[str, object]]]:
        """Pack chunks into bundles respecting max_lines limit."""
        bundles: List[List[FileChunk]] = []
        skipped: List[Dict[str, object]] = []
        current_bundle: List[FileChunk] = []
        current_lines = 0

        for chunk in chunks:
            rendered_block = self.render_chunk_block(chunk)
            rendered_line_count = len(rendered_block.splitlines())
            if rendered_line_count > max_lines:
                skipped.append(
                    {
                        "path": chunk.rel_path.as_posix(),
                        "reason": "rendered_chunk_exceeds_limit",
                        "chunk_index": chunk.chunk_index,
                        "chunk_count": chunk.chunk_count,
                        "rendered_line_count": rendered_line_count,
                    }
                )
                continue
            if current_bundle and (current_lines + rendered_line_count > max_lines):
                bundles.append(current_bundle)
                current_bundle = []
                current_lines = 0
            current_bundle.append(chunk)
            current_lines += rendered_line_count
        if current_bundle:
            bundles.append(current_bundle)
        return bundles, skipped

    # -------------------------------------------------------------------------
    # Output writing
    # -------------------------------------------------------------------------
    @staticmethod
    def sanitize_output_dir_name(root: Path) -> str:
        """Generate a sanitized output directory name with timestamp."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        project_name = root.name.replace(" ", "_") or "project"
        return f"{DEFAULT_OUTPUT_DIR}_{project_name}_{timestamp}"

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
    ) -> Path:
        """Write bundles and manifest to the output directory."""
        output_dir.mkdir(parents=True, exist_ok=True)

        source_lookup: Dict[str, SourceFile] = {
            item.rel_path.as_posix(): item for item in selected_files
        }

        manifest: Dict[str, object] = {
            "tool": "build-ai-context",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "project_root": str(root),
            "max_lines_per_bundle": max_lines,
            "bundle_count": len(bundles),
            "skip_secret_like_files": skip_secret_files,
            "selection": selection_metadata,
            "selected_files": [item.rel_path.as_posix() for item in selected_files],
            "summary": {
                "selected_file_count": len(selected_files),
                "selected_total_lines": sum(item.line_count for item in selected_files),
                "selected_total_bytes": sum(item.size_bytes for item in selected_files),
                "skipped_counts": skipped_reasons,
                "skipped_during_pack_count": len(skipped_during_pack),
            },
            "skipped_during_pack": list(skipped_during_pack),
            "bundles": [],
        }

        for index, bundle in enumerate(bundles, start=1):
            folder_name = root.name.replace(" ", "_")
            bundle_name = f"bundle_{index:03d}_{folder_name}.txt"
            bundle_path = output_dir / bundle_name
            text_parts: List[str] = []
            next_bundle_line = 1
            bundle_files: List[Dict[str, object]] = []

            for chunk in bundle:
                rel_path_str = chunk.rel_path.as_posix()
                source = source_lookup[rel_path_str]
                block_text = self.render_chunk_block(chunk)
                block_line_count = len(block_text.splitlines())
                bundle_start_line = next_bundle_line
                bundle_end_line = next_bundle_line + block_line_count - 1
                next_bundle_line = bundle_end_line + 1
                text_parts.append(block_text)
                bundle_files.append(
                    {
                        "path": rel_path_str,
                        "category": chunk.category,
                        "size_bytes": source.size_bytes,
                        "sha256": source.sha256,
                        "total_file_lines": source.line_count,
                        "chunk_index": chunk.chunk_index,
                        "chunk_count": chunk.chunk_count,
                        "file_start_line": chunk.start_line,
                        "file_end_line": chunk.end_line,
                        "file_line_count": chunk.line_count,
                        "bundle_start_line": bundle_start_line,
                        "bundle_end_line": bundle_end_line,
                        "bundle_line_count": block_line_count,
                    }
                )

            bundle_text = "".join(text_parts)
            bundle_path.write_text(bundle_text, encoding=DEFAULT_TEXT_ENCODING)
            manifest["bundles"].append(
                {
                    "bundle": bundle_name,
                    "rendered_total_lines": len(bundle_text.splitlines()),
                    "files": bundle_files,
                }
            )

        summary_path = output_dir / "README_EXPORT.txt"
        summary_text = [
            "build-ai-context Exporter\n",
            "=====================\n\n",
            f"Project root            : {root}\n",
            f"Created at (UTC)        : {manifest['created_at_utc']}\n",
            f"Bundles created         : {len(bundles)}\n",
            f"Selected files          : {len(selected_files)}\n",
            f"Selected total lines    : {manifest['summary']['selected_total_lines']}\n",
            f"Max lines per bundle    : {max_lines}\n",
            f"Secret-like files skipped: {skip_secret_files}\n",
            f"Skipped during pack     : {len(skipped_during_pack)}\n\n",
            "How to use\n",
            "----------\n",
            "1) Attach one or more bundle_XXX.txt files to your AI assistant.\n",
            "2) Attach MANIFEST.json as well so the assistant understands the mapping.\n",
            "3) Use bundles[].files[].bundle_start_line / bundle_end_line for exact positions.\n",
            "4) Use bundles[].files[].file_start_line / file_end_line for original source ranges.\n",
        ]
        summary_path.write_text("".join(summary_text), encoding=DEFAULT_TEXT_ENCODING)

        manifest_path = output_dir / "MANIFEST.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding=DEFAULT_TEXT_ENCODING)
        return manifest_path

    # -------------------------------------------------------------------------
    # Project overview
    # -------------------------------------------------------------------------
    @staticmethod
    def detect_dependency_files(all_files: Sequence[SourceFile]) -> List[str]:
        """Detect dependency/config files in the project."""
        return sorted(
            item.rel_path.as_posix()
            for item in all_files
            if item.rel_path.name in INTERESTING_FILES
        )

    @staticmethod
    def detect_frameworks(all_files: Sequence[SourceFile]) -> List[str]:
        """Detect frameworks used in the project."""
        rel_paths = {item.rel_path.as_posix() for item in all_files}
        names = {item.rel_path.name for item in all_files}
        categories = {item.category for item in all_files}
        frameworks: List[str] = []
        if "python" in categories or "pyproject.toml" in names or "requirements.txt" in names:
            frameworks.append("Python")
        if "typescript" in categories or "tsconfig.json" in names:
            frameworks.append("TypeScript")
        if "javascript" in categories or "package.json" in names:
            frameworks.append("JavaScript / Node.js")
        if "java_kotlin" in categories or any(
            path.endswith((".gradle", ".gradle.kts")) for path in rel_paths
        ):
            frameworks.append("Android / Java / Kotlin / Gradle")
        if "ios_apple" in categories or "Podfile" in names:
            frameworks.append("iOS / Apple")
        if "web_ui" in categories:
            frameworks.append("Web UI / Frontend")
        if "Dockerfile" in names:
            frameworks.append("Docker")
        if "Jenkinsfile" in names:
            frameworks.append("Jenkins / CI")
        return frameworks

    @staticmethod
    def suggest_reading_order(
        root: Path, all_files: Sequence[SourceFile], selected_files: Sequence[SourceFile]
    ) -> List[str]:
        """Suggest a reading order for the AI assistant."""
        existing_paths = {item.rel_path.as_posix() for item in all_files}
        preferred = [
            "README.md",
            "pyproject.toml",
            "requirements.txt",
            "requirements-dev.txt",
            "requirements-ci.txt",
            "package.json",
            "tsconfig.json",
            "Jenkinsfile",
            "AndroidManifest.xml",
            "build.gradle",
            "build.gradle.kts",
            "src",
            "app",
            "scripts",
            "tools",
        ]
        ordered: List[str] = []
        for candidate in preferred:
            if candidate in existing_paths or (root / candidate).exists():
                ordered.append(candidate)
        selected_top_folders: List[str] = []
        for item in selected_files:
            parts = item.rel_path.parts
            if len(parts) > 1:
                folder = "/".join(parts[:2])
            elif len(parts) == 1:
                folder = parts[0]
            else:
                folder = "."
            selected_top_folders.append(folder)
        for folder in sorted(dict.fromkeys(selected_top_folders)):
            if folder not in ordered:
                ordered.append(folder)
        return ordered

    def write_project_overview(
        self,
        root: Path,
        all_files: Sequence[SourceFile],
        selected_files: Sequence[SourceFile],
        output_dir: Path,
        selection_metadata: Dict[str, object],
    ) -> Path:
        """Write a project overview file."""
        output_dir.mkdir(parents=True, exist_ok=True)
        category_summary = self.summarize_by_category(all_files)
        top_folders = self.summarize_top_folders(all_files, max_depth=2)
        dependency_files = self.detect_dependency_files(all_files)
        frameworks = self.detect_frameworks(all_files)
        reading_order = self.suggest_reading_order(root, all_files, selected_files)

        lines: List[str] = []
        lines.append("PROJECT OVERVIEW\n")
        lines.append("================\n\n")
        lines.append("1) Architecture summary\n")
        lines.append("-----------------------\n")
        lines.append(f"- Project root: {root}\n")
        lines.append(f"- Total supported files detected: {len(all_files)}\n")
        lines.append(f"- Files selected for export: {len(selected_files)}\n")
        lines.append(f"- Selection mode: {selection_metadata.get('selection_mode', 'unknown')}\n\n")

        lines.append("2) Major folders\n")
        lines.append("----------------\n")
        for folder, stats in list(top_folders.items())[:20]:
            lines.append(f"- {folder}: files={stats['files']}, lines={stats['lines']}\n")
        lines.append("\n")

        lines.append("3) Detected frameworks / stack hints\n")
        lines.append("------------------------------------\n")
        if frameworks:
            for item in frameworks:
                lines.append(f"- {item}\n")
        else:
            lines.append("- No obvious framework hints detected.\n")
        lines.append("\n")

        lines.append("4) Dependency / configuration files\n")
        lines.append("-----------------------------------\n")
        if dependency_files:
            for item in dependency_files:
                lines.append(f"- {item}\n")
        else:
            lines.append("- No major dependency files detected.\n")
        lines.append("\n")

        lines.append("5) Codebase composition by category\n")
        lines.append("----------------------------------\n")
        for category in CATEGORY_DESCRIPTIONS:
            row = category_summary.get(category, {"files": 0, "lines": 0, "bytes": 0})
            lines.append(
                f"- {category}: files={row['files']}, lines={row['lines']}, "
                f"bytes={row['bytes']} ({CATEGORY_DESCRIPTIONS[category]})\n"
            )
        lines.append("\n")

        lines.append("6) Suggested reading order for Copilot / AI assistant\n")
        lines.append("-----------------------------------------------------\n")
        if reading_order:
            for idx, item in enumerate(reading_order, start=1):
                lines.append(f"{idx}. {item}\n")
        lines.append("\n")

        lines.append("7) Notes\n")
        lines.append("--------\n")
        lines.append("- Use this file together with MANIFEST.json and the bundle_XXX.txt files.\n")
        lines.append(
            "- Start from the suggested reading order, then use MANIFEST.json to locate exact file chunks.\n"
        )
        lines.append(
            "- If asking targeted questions, attach only the most relevant bundles first.\n"
        )

        overview_path = output_dir / "PROJECT_OVERVIEW.txt"
        overview_path.write_text("".join(lines), encoding=DEFAULT_TEXT_ENCODING)
        return overview_path

    # -------------------------------------------------------------------------
    # Main export method
    # -------------------------------------------------------------------------
    def export(
        self,
        project_root: Path | str | None = None,
        max_lines: int = DEFAULT_MAX_LINES,
        output_dir: Path | str | None = None,
        include_secret_files: bool = False,
        categories: List[str] | None = None,
        paths: List[str] | None = None,
        interactive: bool = True,
        project_overview: bool = False,
    ) -> ExportResult:
        """
        Run the full export process.

        Parameters
        ----------
        project_root : Path, str, or None
            Root directory to scan. Defaults to current working directory.
        max_lines : int
            Maximum lines per output bundle.
        output_dir : Path, str, or None
            Output directory for bundles.
        include_secret_files : bool
            Whether to include secret-like files.
        categories : list of str, optional
            Categories to export (non-interactive mode).
        paths : list of str, optional
            Specific paths to export (non-interactive mode).
        interactive : bool
            Whether to run in interactive mode.
        project_overview : bool
            Whether to generate PROJECT_OVERVIEW.txt.

        Returns
        -------
        ExportResult
            Result object containing export metadata.
        """
        root = Path(project_root or ".").expanduser().resolve()
        if not root.exists():
            raise FileNotFoundError(f"Project root does not exist: {root}")
        if not root.is_dir():
            raise NotADirectoryError(f"Project root is not a directory: {root}")

        if max_lines <= 0:
            raise ValueError("--max-lines must be greater than zero")

        skip_secret_files = not include_secret_files
        self.print_info(f"Scanning project: {root}")

        all_files, skipped_reasons = self.scan_supported_files(root, skip_secret_files)
        if not all_files:
            self.print_warning(
                "No supported files were found after applying .gitignore and default exclusions."
            )
            return ExportResult(
                output_dir=Path(output_dir or "."),
                manifest_path=Path("."),
                overview_path=None,
                bundles_created=0,
                files_exported=0,
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
            )

        chunks, skipped_during_split = self.split_into_chunks(selected_files, max_lines)
        bundles, skipped_during_pack = self.pack_chunks(chunks, max_lines)
        skipped_during_processing = skipped_during_split + skipped_during_pack

        out_dir = (
            Path(output_dir).expanduser().resolve()
            if output_dir
            else Path.cwd() / self.sanitize_output_dir_name(root)
        )
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
        )

        overview_path = None
        if project_overview:
            overview_path = self.write_project_overview(
                root=root,
                all_files=all_files,
                selected_files=selected_files,
                output_dir=out_dir,
                selection_metadata=selection_metadata,
            )

        self.print_success("\nExport complete.")
        self.print_success(f"Output directory : {out_dir}")
        self.print_success(f"Manifest         : {manifest_path}")
        if overview_path is not None:
            self.print_success(f"Project overview : {overview_path}")
        self.print_success(f"Bundles created  : {len(bundles)}")
        self.print_success(f"Files exported   : {len(selected_files)}")

        if skipped_during_processing:
            self.print_warning("Files/chunks skipped during processing:")
            for item in skipped_during_processing:
                self.print_warning("  - " + json.dumps(item, ensure_ascii=False))

        missing_paths = selection_metadata.get("missing_paths", [])
        if missing_paths:
            self.print_warning("Paths that did not match supported files:")
            for value in missing_paths:
                self.print_warning(f"  - {value}")

        return ExportResult(
            output_dir=out_dir,
            manifest_path=manifest_path,
            overview_path=overview_path,
            bundles_created=len(bundles),
            files_exported=len(selected_files),
            skipped_items=skipped_during_processing,
            missing_paths=list(missing_paths) if missing_paths else [],
        )
