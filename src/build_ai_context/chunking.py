"""
Chunking and bundling logic for build_ai_context.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from build_ai_context.constants import (
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
        f"{'=' * 60}\n"
    )


def bundle_footer(chunk: FileChunk) -> str:
    """Generate a footer for a file chunk in a bundle."""
    total = chunk.chunk_count
    idx = chunk.chunk_index
    return (
        f"{'=' * 60}\n"
        f"===== END FILE: {chunk.rel_path.as_posix()} (chunk {idx}/{total}) =====\n"
        f"{'=' * 60}\n"
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



def _json_shape(value: Any) -> object:
    """Return a stable structural signature while ignoring concrete values."""
    if isinstance(value, dict):
        return ("object", tuple(sorted((key, _json_shape(item)) for key, item in value.items())))
    if isinstance(value, list):
        shapes = {_json_shape(item) for item in value}
        return ("array", tuple(sorted(shapes, key=repr)))
    if value is None:
        return "null"
    return type(value).__name__


def _sample_json(value: Any, per_shape: int) -> tuple[Any, int, int]:
    """Recursively retain representative members from repeated JSON structures."""
    if isinstance(value, list):
        sampled: List[Any] = []
        counts: Dict[object, int] = {}
        removed = 0
        groups = set()
        child_group_count = 0
        for item in value:
            shape = _json_shape(item)
            groups.add(shape)
            if counts.get(shape, 0) >= per_shape:
                removed += 1
                continue
            counts[shape] = counts.get(shape, 0) + 1
            child, child_removed, child_groups = _sample_json(item, per_shape)
            sampled.append(child)
            removed += child_removed
            child_group_count += child_groups
        return sampled, removed, len(groups) + child_group_count
    if isinstance(value, dict):
        preserved: Dict[str, Any] = {}
        grouped: Dict[object, List[tuple[str, Any]]] = {}
        removed = 0
        group_count = 0
        for key, item in value.items():
            if key == "_meta":
                child, child_removed, child_groups = _sample_json(item, per_shape)
                preserved[key] = child
                removed += child_removed
                group_count += child_groups
                continue
            grouped.setdefault(_json_shape(item), []).append((key, item))
        for members in grouped.values():
            group_count += 1
            for key, item in members[:per_shape]:
                child, child_removed, child_groups = _sample_json(item, per_shape)
                preserved[key] = child
                removed += child_removed
                group_count += child_groups
            removed += max(0, len(members) - per_shape)
        return preserved, removed, group_count
    return value, 0, 0


def force_bundle_json_files(
    files: Sequence[SourceFile], max_file_lines: Optional[int]
) -> Tuple[List[SourceFile], List[Dict[str, object]]]:
    """Create in-memory representative JSON samples for oversized data files."""
    threshold = LARGE_FILE_SKIP_LINES if max_file_lines is None else max_file_lines
    if threshold <= 0:
        return list(files), []
    transformed: List[SourceFile] = []
    events: List[Dict[str, object]] = []
    for source in files:
        if source.line_count < threshold or source.rel_path.suffix.lower() != ".json":
            transformed.append(source)
            continue
        try:
            payload = json.loads("\n".join(source.lines))
        except (TypeError, json.JSONDecodeError) as exc:
            transformed.append(source)
            events.append({
                "path": source.rel_path.as_posix(),
                "reason": "force_bundle_invalid_json",
                "line_count": source.line_count,
                "threshold": threshold,
                "error": str(exc),
            })
            continue
        replacement = None
        details = None
        for per_shape in (5, 4, 3):
            sampled, removed, groups = _sample_json(payload, per_shape)
            text = json.dumps(sampled, indent=2, ensure_ascii=False)
            lines = text.splitlines()
            if len(lines) < threshold:
                replacement = SourceFile(
                    abs_path=source.abs_path,
                    rel_path=source.rel_path,
                    category=source.category,
                    line_count=len(lines),
                    size_bytes=len(text.encode("utf-8")),
                    sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    lines=lines,
                )
                details = {
                    "path": source.rel_path.as_posix(),
                    "reason": "force_bundled_json_sample",
                    "original_line_count": source.line_count,
                    "bundled_line_count": len(lines),
                    "threshold": threshold,
                    "representatives_per_shape": per_shape,
                    "structure_group_count": groups,
                    "removed_member_count": removed,
                }
                break
        if replacement is None:
            transformed.append(source)
            events.append({
                "path": source.rel_path.as_posix(),
                "reason": "force_bundle_minimum_sample_exceeds_threshold",
                "line_count": source.line_count,
                "threshold": threshold,
            })
        else:
            transformed.append(replacement)
            events.append(details)
    return transformed, events

def split_into_chunks(
    files: Sequence[SourceFile],
    max_lines: int,
    redact: bool = False,
    max_file_lines: Optional[int] = None,
) -> Tuple[List[FileChunk], List[Dict[str, object]]]:
    """
    Split repo source files into chunks for packing.

    max_lines:
      Max lines for a chunk/block within a bundle (typically DEFAULT_MAX_LINES=8000).
      This is the output-bundle capacity used for splitting large included files.
    max_file_lines:
      Max lines allowed for a *source* file before it is skipped entirely:
        - None  → use LARGE_FILE_SKIP_LINES (default 3000)
        - 0     → never skip a file for size (still split across 8000-line bundles)
        - N > 0 → skip files with >= N lines

    Returns (chunks, skipped_files).
    """
    chunks: List[FileChunk] = []
    skipped: List[Dict[str, object]] = []
    overhead = chunk_overhead_lines(redact)
    skip_threshold = (
        LARGE_FILE_SKIP_LINES if max_file_lines is None else max_file_lines
    )

    for source in files:
        lines = source.lines
        total_lines = len(lines)
        if total_lines == 0:
            continue

        # Check if file exceeds skip threshold (0 = disabled / unlimited)
        if skip_threshold > 0 and total_lines >= skip_threshold:
            skipped.append(
                {
                    "path": source.rel_path.as_posix(),
                    "reason": "large_file_exceeds_skip_threshold",
                    "line_count": total_lines,
                    "threshold": skip_threshold,
                }
            )
            continue

        # Warn for large files that are still included
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
