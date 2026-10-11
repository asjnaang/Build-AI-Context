# === FILE HEADER START (auto) ===
# path: src/build_ai_context/writing.py
# repo: build-ai-context
# updated: 2026-05-14T13:12:59Z
# === FILE HEADER END (auto) ===

"""
Project overview and manifest writing for build_ai_context.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set

from build_ai_context.chunking import render_chunk_block
from build_ai_context.constants import (
    CATEGORY_DESCRIPTIONS,
    DEFAULT_TEXT_ENCODING,
    generate_timestamp,
    local_now,
)
from build_ai_context.models import FileChunk, SourceFile

_TEXT_PROMPT_PATH = Path(__file__).parent / "baic_prompt.md"
_ENCODED_PROMPT_PATH = Path(__file__).parent / "baic_prompt_6_v2.md"
_BAIC_PROMPT_MD_PATH = _TEXT_PROMPT_PATH
_TASK_PLACEHOLDER = "[PASTE THE SPECIFIC FEATURE / BUGFIX / REFACTOR REQUEST HERE]"


def get_baic_prompt_md_content(task: Optional[str] = None) -> str:
    """Return the bundled prompt, optionally replacing its task placeholder."""
    if not _BAIC_PROMPT_MD_PATH.exists():
        return ""
    content = _BAIC_PROMPT_MD_PATH.read_text(encoding="utf-8")
    if task is None:
        return content
    return content.replace(_TASK_PLACEHOLDER, task, 1)


def detect_dependency_files(all_files: Sequence[SourceFile]) -> List[str]:
    """Detect common dependency/config files in the project."""
    interesting: List[str] = []
    dep_filenames = {
        "package.json",
        "requirements.txt",
        "pyproject.toml",
        "Cargo.toml",
        "go.mod",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "Gemfile",
        "Podfile",
        "composer.json",
        "setup.py",
        "setup.cfg",
    }
    for f in all_files:
        if f.rel_path.name in dep_filenames:
            interesting.append(f.rel_path.as_posix())
    return interesting


def detect_frameworks(all_files: Sequence[SourceFile]) -> List[str]:
    """Detect frameworks/libraries based on file patterns."""
    frameworks: List[str] = []
    framework_indicators = {
        "typescript": ["tsconfig.json"],
        "react": ["*.tsx"],
        "vue": ["*.vue"],
        "svelte": ["*.svelte"],
        "django": ["manage.py", "settings.py"],
        "flask": ["app.py", "wsgi.py"],
        "fastapi": ["main.py", "requirements.txt"],
        "spring": ["pom.xml", "build.gradle"],
        "rails": ["Gemfile", "config.ru"],
        "flutter": ["pubspec.yaml"],
    }
    for fw, indicators in framework_indicators.items():
        for indicator in indicators:
            if any(
                f.rel_path.name == indicator or f.rel_path.name.endswith(indicator.replace("*", ""))
                for f in all_files
            ):
                frameworks.append(fw)
                break
    return frameworks


def suggest_reading_order(all_files: Sequence[SourceFile]) -> List[str]:
    """Suggest a reading order for files based on importance."""
    priority_files: List[str] = []

    # Priority 1: Main entry points
    entry_patterns = {"main.py", "app.py", "index.ts", "index.js", "Main.kt"}
    for f in all_files:
        if f.rel_path.name in entry_patterns:
            priority_files.append(f.rel_path.as_posix())

    # Priority 2: Config files
    config_patterns = {"package.json", "tsconfig.json", "settings.py", "application.yaml"}
    for f in all_files:
        if f.rel_path.name in config_patterns:
            if f.rel_path.as_posix() not in priority_files:
                priority_files.append(f.rel_path.as_posix())

    # Priority 3: Key directories
    key_dirs = {"src", "lib", "app", "core", "models", "services"}
    for f in all_files:
        if f.rel_path.parts[0] in key_dirs:
            if f.rel_path.as_posix() not in priority_files:
                priority_files.append(f.rel_path.as_posix())

    return priority_files


def write_project_overview(
    root: Path,
    all_files: Sequence[SourceFile],
    selected_files: Sequence[SourceFile],
    output_dir: Path,
    selection_metadata: Dict[str, object],
    manifest_name: str,
    summarize_by_category_fn,
    summarize_top_folders_fn,
) -> Path:
    """Generate a PROJECT_OVERVIEW.txt file."""
    dep_files = detect_dependency_files(all_files)
    frameworks = detect_frameworks(all_files)
    category_summary = summarize_by_category_fn(selected_files)
    folder_summary = summarize_top_folders_fn(selected_files)
    reading_order = suggest_reading_order(all_files)

    lines: List[str] = []
    lines.append("=" * 60)
    lines.append(f"PROJECT OVERVIEW: {root.name}")
    lines.append("=" * 60)
    lines.append(f"Generated: {local_now().isoformat()}")
    lines.append(f"Manifest: {manifest_name}")
    lines.append("")

    # Project stats
    lines.append("📊 PROJECT STATISTICS")
    lines.append("-" * 40)
    lines.append(f"  Total files in project: {len(all_files)}")
    lines.append(f"  Files exported: {len(selected_files)}")
    lines.append(f"  Selection mode: {selection_metadata.get('selection_mode', 'unknown')}")
    lines.append("")

    # Detected frameworks
    if frameworks:
        lines.append("🚀 DETECTED FRAMEWORKS")
        lines.append("-" * 40)
        for fw in frameworks:
            lines.append(f"  • {fw}")
        lines.append("")

    # Dependency files
    if dep_files:
        lines.append("📦 DEPENDENCY FILES")
        lines.append("-" * 40)
        for dep in dep_files[:10]:
            lines.append(f"  • {dep}")
        lines.append("")

    # Category breakdown
    lines.append("📁 FILES BY CATEGORY")
    lines.append("-" * 40)
    for cat, stats in sorted(category_summary.items(), key=lambda x: x[1]["files"], reverse=True):
        desc = CATEGORY_DESCRIPTIONS.get(cat, cat)
        lines.append(f"  {cat:<15} {stats['files']:>4} files  {stats['lines']:>7} lines  | {desc}")
    lines.append("")

    # Top folders
    lines.append("📂 TOP FOLDERS")
    lines.append("-" * 40)
    for folder, stats in list(folder_summary.items())[:10]:
        lines.append(f"  {folder:<20} {stats['files']:>4} files  {stats['lines']:>7} lines")
    lines.append("")

    # Suggested reading order
    if reading_order:
        lines.append("📖 SUGGESTED READING ORDER")
        lines.append("-" * 40)
        for i, path in enumerate(reading_order[:20], 1):
            lines.append(f"  {i:>3}. {path}")
        if len(reading_order) > 20:
            lines.append(f"  ... and {len(reading_order) - 20} more")
        lines.append("")

    lines.append("=" * 60)
    lines.append("END OF PROJECT OVERVIEW")
    lines.append("=" * 60)

    output_path = output_dir / "PROJECT_OVERVIEW.txt"
    output_path.write_text("\n".join(lines), encoding=DEFAULT_TEXT_ENCODING)
    return output_path


def write_bundles_and_manifest(
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
    filetree_content: Optional[str] = None,
    timestamp: Optional[str] = None,
    redact: bool = False,
    max_file_lines: Optional[int] = None,
    warnings: Sequence[Dict[str, object]] = (),
    task: Optional[str] = None,
    transport: str = "text",
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
        "max_file_lines": max_file_lines,
        "bundle_count": len(bundles),
        "skip_secret_like_files": skip_secret_files,
        "selection": selection_metadata,
        "selected_files": [item.rel_path.as_posix() for item in selected_files],
        "filetree": filetree_name,
        "summary": {
            "selected_file_count": len(selected_files),
            "selected_total_lines": sum(item.line_count for item in selected_files),
            "selected_total_bytes": sum(item.size_bytes for item in selected_files),
            "skipped_counts": skipped_reasons,
            "skipped_during_pack_count": len(skipped_during_pack),
            "warning_count": len(warnings),
        },
        "skipped_during_pack": list(skipped_during_pack),
        "warnings": list(warnings),
        "bundles": [],
    }

    # Use provided timestamp or extract from output_dir name for consistency
    folder_name = root.name.replace(" ", "_")
    if timestamp is None:
        dir_name = output_dir.name
        parts = dir_name.split("_")
        if len(parts) >= 3:
            timestamp = parts[-1]
        else:
            timestamp = generate_timestamp()

    # Select the transport-specific prompt, both based on the v2 contract.
    prompt_path = _ENCODED_PROMPT_PATH if transport == "tar-gz" else _TEXT_PROMPT_PATH
    if not prompt_path.is_file():
        raise FileNotFoundError(f"Bundled prompt is missing: {prompt_path}")
    prompt_content = prompt_path.read_text(encoding="utf-8")
    if task is not None:
        prompt_content = prompt_content.replace(_TASK_PLACEHOLDER, task, 1)

    # Filetree content for the first bundle
    if filetree_content is None and filetree_name:
        filetree_path = output_dir / filetree_name
        if filetree_path.exists():
            filetree_content = filetree_path.read_text(encoding="utf-8")

    # Expose one prompt whose extractor matches the selected transport.
    (output_dir / "baic_prompt.md").write_text(prompt_content, encoding="utf-8")
    if transport == "tar-gz":
        included_paths: Set[str] = {
            chunk.rel_path.as_posix() for bundle in bundles for chunk in bundle
        }
        archive_name = f"{folder_name}_context_{timestamp}.tar.gz"
        archive_path = output_dir / archive_name
        with archive_path.open("wb") as raw_output:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw_output, mtime=0) as gz_output:
                with tarfile.open(fileobj=gz_output, mode="w", format=tarfile.PAX_FORMAT) as archive:
                    for source in sorted(selected_files, key=lambda item: item.rel_path.as_posix()):
                        rel_path = source.rel_path.as_posix()
                        if rel_path not in included_paths:
                            continue
                        data = source.abs_path.read_bytes()
                        if len(data) != source.size_bytes or hashlib.sha256(data).hexdigest() != source.sha256:
                            raise ValueError(f"Source changed during export: {rel_path}")
                        info = tarfile.TarInfo(rel_path)
                        info.size = len(data)
                        info.mode = source.abs_path.stat().st_mode & 0o777
                        info.mtime = 0
                        info.uid = info.gid = 0
                        info.uname = info.gname = ""
                        archive.addfile(info, io.BytesIO(data))
        archive_bytes = archive_path.read_bytes()
        payload_body = __import__("base64").b64encode(archive_bytes).decode("ascii")
        wrapped_body = "\n".join(
            payload_body[index:index + 76]
            for index in range(0, len(payload_body), 76)
        )
        payload_name = f"{folder_name}_payload_{timestamp}.txt"
        payload_header = (
            "BAIC-ENCODED-CONTEXT-V1\n"
            f"archive-name: {archive_name}\n"
            "content-format: tar+gzip\n"
            "transport-encoding: base64\n"
            f"archive-size-bytes: {len(archive_bytes)}\n"
            f"archive-sha256: {hashlib.sha256(archive_bytes).hexdigest()}\n"
            f"base64-body-size-bytes: {len(payload_body.encode('ascii'))}\n"
            f"base64-body-sha256: {hashlib.sha256(payload_body.encode('ascii')).hexdigest()}\n"
            "\n"
        )
        payload_path = output_dir / payload_name
        payload_path.write_text(payload_header + wrapped_body + "\n", encoding="ascii")
        payload_bytes = payload_path.read_bytes()
        archive_path.unlink()
        entries = [
            {
                "path": source.rel_path.as_posix(),
                "category": source.category,
                "content_kind": "binary" if source.encoding != "text" else "text",
                "source_format": "gzip" if source.rel_path.suffix.lower() == ".gz" else None,
                "transport_encoding": "identity",
                "size_bytes": source.size_bytes,
                "sha256": source.sha256,
                "mode": source.abs_path.stat().st_mode & 0o777,
            }
            for source in sorted(selected_files, key=lambda item: item.rel_path.as_posix())
            if source.rel_path.as_posix() in included_paths
        ]
        manifest.update({
            "schema_version": 3,
            "selected_files": [entry["path"] for entry in entries],
            "summary": {
                **manifest["summary"],
                "selected_file_count": len(entries),
                "selected_total_lines": sum(
                    source.line_count for source in selected_files
                    if source.rel_path.as_posix() in included_paths
                ),
                "selected_total_bytes": sum(entry["size_bytes"] for entry in entries),
            },
            "transport": {
                "format": "tar+gzip+base64",
                "payload": payload_name,
                "payload_size_bytes": len(payload_bytes),
                "payload_sha256": hashlib.sha256(payload_bytes).hexdigest(),
                "base64_body_size_bytes": len(payload_body.encode("ascii")),
                "base64_body_sha256": hashlib.sha256(payload_body.encode("ascii")).hexdigest(),
                "archive_name": archive_name,
                "archive_size_bytes": len(archive_bytes),
                "archive_sha256": hashlib.sha256(archive_bytes).hexdigest(),
                "deterministic": True,
            },
            "archive_entries": entries,
            "bundle_count": 0,
            "bundles": [],
        })
        manifest_name = f"{folder_name}_manifest_{timestamp}.json"
        manifest_path = output_dir / manifest_name
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, default=str) + "\n",
            encoding=DEFAULT_TEXT_ENCODING,
        )
        return manifest_path
    if transport != "text":
        raise ValueError("transport must be 'tar-gz' or 'text'")
    for index, bundle in enumerate(bundles, start=1):
        bundle_name = f"{folder_name}_bundle_{index:03d}_{timestamp}.txt"
        bundle_path = output_dir / bundle_name
        text_parts: List[str] = []
        next_bundle_line = 1
        bundle_files: List[Dict[str, object]] = []

        # Prepend filetree to the first bundle
        if index == 1 and filetree_content:
            filetree_header = f"{'=' * 60}\n===== FILETREE: Project Structure =====\n{'=' * 60}\n"
            filetree_footer = f"\n{'=' * 60}\n===== END FILETREE =====\n{'=' * 60}\n"
            filetree_block = filetree_header + filetree_content + filetree_footer
            text_parts.append(filetree_block)
            filetree_line_count = len(filetree_block.splitlines())
            bundle_files.append(
                {
                    "path": filetree_name,
                    "category": "filetree",
                    "size_bytes": len(filetree_content),
                    "sha256": "",
                    "total_file_lines": filetree_line_count,
                    "chunk_index": 1,
                    "chunk_count": 1,
                    "file_start_line": 1,
                    "file_end_line": filetree_line_count,
                    "file_line_count": filetree_line_count,
                    "bundle_start_line": 1,
                    "bundle_end_line": filetree_line_count,
                    "bundle_line_count": filetree_line_count,
                }
            )
            next_bundle_line = filetree_line_count + 1

        for chunk in bundle:
            rel_path_str = chunk.rel_path.as_posix()
            source = source_lookup.get(rel_path_str)
            if not source:
                continue
            block_text = render_chunk_block(chunk, redact)
            block_line_count = len(block_text.splitlines())
            bundle_start_line = next_bundle_line
            bundle_end_line = next_bundle_line + block_line_count - 1
            next_bundle_line = bundle_end_line + 1
            text_parts.append(block_text)
            bundle_files.append(
                {
                    "path": rel_path_str,
                    "category": chunk.category,
                    "encoding": chunk.encoding,
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

        bundle_path.write_text("".join(text_parts), encoding="utf-8")

        manifest["bundles"].append(
            {
                "bundle": bundle_name,
                "files": bundle_files,
            }
        )

    manifest_name = f"{folder_name}_manifest_{timestamp}.json"
    manifest_path = output_dir / manifest_name
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding=DEFAULT_TEXT_ENCODING,
    )

    return manifest_path
