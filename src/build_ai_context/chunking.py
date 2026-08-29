"""
Chunking and bundling logic for build_ai_context.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from build_ai_context.constants import (
    DEFAULT_MAX_LINES,
    LARGE_FILE_SKIP_LINES,
    LARGE_FILE_WARN_LINES,
)
from build_ai_context.models import FileChunk, SourceFile
from build_ai_context.redact import redact_text


def bundle_header(chunk: FileChunk) -> str:
    """Generate a header for a file chunk in a bundle."""
    total = chunk.chunk_count
    idx = chunk.chunk_index
    return (
        f"{'=' * 60}\n"
        f"===== BEGIN FILE: {chunk.rel_path.as_posix()} =====\n"
        f"# category : {chunk.category}\n"
        f"# chunk : {idx}/{total}\n"
        f"# line_range : {chunk.start_line}-{chunk.end_line}\n"
        f"# total_lines : {chunk.total_file_lines}\n"
        f"{'=' * 60}"
    )


def bundle_footer(chunk: FileChunk) -> str:
    """Generate a footer for a file chunk in a bundle."""
    total = chunk.chunk_count
    idx = chunk.chunk_index
    return (
        f"{'=' * 60}\n"
        f"===== END FILE: {chunk.rel_path.as_posix()} (chunk {idx}/{total}) =====\n"
        f"{'=' * 60}"
    )


def render_chunk_block(chunk: FileChunk, redact: bool = False) -> str:
    """Render a complete chunk block with header and footer."""
    parts: List[str] = [bundle_header(chunk)]
    for line in chunk.lines:
        if redact:
            parts.append(redact_text(line) + "\n")
        else:
            parts.append(line + "\n")
    parts.append(bundle_footer(chunk))
    return "".join(parts)


def chunk_overhead_lines(redact: bool = False) -> int:
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
    return len(render_chunk_block(dummy, redact).splitlines()) - 1


def split_into_chunks(
    files: Sequence[SourceFile],
    max_lines: int,
    redact: bool = False,
) -> Tuple[List[FileChunk], List[Dict[str, object]]]:
    """
    Split files into chunks respecting max_lines.

    Returns (chunks, skipped_files).
    """
    chunks: List[FileChunk] = []
    skipped: List[Dict[str, object]] = []
    overhead = chunk_overhead_lines(redact)

    for source in files:
        lines = source.lines
        total_lines = len(lines)
        if total_lines == 0:
            continue

        # Check if file exceeds skip threshold
        if total_lines >= LARGE_FILE_SKIP_LINES:
            skipped.append(
                {
                    "path": source.rel_path.as_posix(),
                    "reason": "large_file_exceeds_skip_threshold",
                    "line_count": total_lines,
                    "threshold": LARGE_FILE_SKIP_LINES,
                }
            )
            continue

        # Warn for large files (1500-2999 lines)
        if total_lines >= LARGE_FILE_WARN_LINES:
            skipped.append(
                {
                    "path": source.rel_path.as_posix(),
                    "reason": "large_file_warning",
                    "line_count": total_lines,
                    "threshold": LARGE_FILE_WARN_LINES,
                }
            )

        # Calculate effective max lines accounting for overhead
        effective_max = max_lines - overhead
        if effective_max <= 0:
            effective_max = max_lines

        # Single chunk if fits
        if total_lines <= effective_max:
            chunks.append(
                FileChunk(
                    rel_path=source.rel_path,
                    category=source.category,
                    chunk_index=1,
                    chunk_count=1,
                    start_line=1,
                    end_line=total_lines,
                    total_file_lines=total_lines,
                    lines=lines,
                )
            )
        else:
            # Split into multiple chunks
            chunk_count = (total_lines + effective_max - 1) // effective_max
            for i in range(chunk_count):
                start = i * effective_max
                end = min(start + effective_max, total_lines)
                chunks.append(
                    FileChunk(
                        rel_path=source.rel_path,
                        category=source.category,
                        chunk_index=i + 1,
                        chunk_count=chunk_count,
                        start_line=start + 1,
                        end_line=end,
                        total_file_lines=total_lines,
                        lines=lines[start:end],
                    )
                )

    return chunks, skipped


def pack_chunks(
    chunks: Sequence[FileChunk],
    max_lines: int,
    redact: bool = False,
) -> Tuple[List[List[FileChunk]], List[Dict[str, object]]]:
    """
    Pack chunks into bundles respecting max_lines.

    Returns (bundles, skipped_chunks).
    """
    bundles: List[List[FileChunk]] = []
    skipped: List[Dict[str, object]] = []
    current_bundle: List[FileChunk] = []
    current_lines = 0
    overhead = chunk_overhead_lines(redact)

    for chunk in chunks:
        chunk_lines = len(chunk.lines)
        block_overhead = overhead
        total_needed = chunk_lines + block_overhead

        # Skip individual chunks that exceed max_lines
        if total_needed > max_lines:
            skipped.append(
                {
                    "path": chunk.rel_path.as_posix(),
                    "reason": "chunk_exceeds_max_lines",
                    "line_count": chunk_lines,
                    "max_lines": max_lines,
                }
            )
            continue

        # Start new bundle if adding would exceed max
        if current_lines + total_needed > max_lines and current_bundle:
            bundles.append(current_bundle)
            current_bundle = []
            current_lines = 0

        current_bundle.append(chunk)
        current_lines += total_needed

    if current_bundle:
        bundles.append(current_bundle)

    return bundles, skipped
