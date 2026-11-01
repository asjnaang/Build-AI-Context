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

GZIP_COMPRESSLEVEL = 1

_PROMPT_PATHS = {
    "text": Path(__file__).parent / "baic_prompt_text.md",
    "tar-gz": Path(__file__).parent / "baic_prompt_gzip.md",
}
_PROMPT_OUTPUT_NAME = "baic_prompt.md"
_TASK_PLACEHOLDER = "[PASTE THE SPECIFIC FEATURE / BUGFIX / REFACTOR REQUEST HERE]"


def prompt_path_for_transport(transport: str) -> Path:
    """Return the single packaged prompt used by the three-attachment workflow."""
    try:
        return _PROMPT_PATHS[transport]
    except KeyError as exc:
        raise ValueError("transport must be 'tar-gz' or 'text'") from exc


def prompt_output_name_for_transport(transport: str) -> str:
    """Return the stable generated prompt filename for every transport."""
    if transport not in {"tar-gz", "text"}:
        raise ValueError("transport must be 'tar-gz' or 'text'")
    return _PROMPT_OUTPUT_NAME


def get_baic_prompt_md_content(task: Optional[str] = None, transport: str = "tar-gz") -> str:
    """Return the single agent prompt with an optional task replacement."""
    prompt_path = prompt_path_for_transport(transport)
    if not prompt_path.is_file():
        return ""
    content = prompt_path.read_text(encoding="utf-8")
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
    transport_files: Optional[Sequence[SourceFile]] = None,
    binary_policy: str = "include",
    policy_omissions: Sequence[Dict[str, object]] = (),
    split: bool = False,
    split_payload_max_bytes: int = 18 * 1024 * 1024,
) -> Path:
    """Write bundles and manifest to the output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    if transport_files is None:
        transport_files = selected_files

    source_lookup: Dict[str, SourceFile] = {
        item.rel_path.as_posix(): item for item in transport_files
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
        "transported_files": [item.rel_path.as_posix() for item in transport_files],
        "transport_policy": {
            "transport": transport,
            "binary_policy": binary_policy,
            "omitted_files": list(policy_omissions),
        },
        "filetree": filetree_name,
        "summary": {
            "selected_file_count": len(selected_files),
            "selected_total_lines": sum(item.line_count for item in selected_files),
            "selected_total_bytes": sum(item.size_bytes for item in selected_files),
            "transported_file_count": len(transport_files),
            "transported_total_bytes": sum(item.size_bytes for item in transport_files),
            "policy_omitted_count": len(policy_omissions),
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
    prompt_path = prompt_path_for_transport(transport)
    if not prompt_path.is_file():
        raise FileNotFoundError(f"Bundled prompt is missing: {prompt_path}")
    prompt_content = get_baic_prompt_md_content(task=task, transport=transport)
    prompt_output_name = prompt_output_name_for_transport(transport)

    # Filetree content for the first bundle
    if filetree_content is None and filetree_name:
        filetree_path = output_dir / filetree_name
        if filetree_path.exists():
            filetree_content = filetree_path.read_text(encoding="utf-8")

    # Expose one prompt whose extractor matches the selected transport.
    (output_dir / prompt_output_name).write_text(prompt_content, encoding="utf-8")
    if transport == "tar-gz":
        sorted_sources = sorted(transport_files, key=lambda item: item.rel_path.as_posix())

        def source_bytes(source: SourceFile) -> bytes:
            data = source.snapshot_bytes
            if data is None:
                data = source.abs_path.read_bytes()
                if len(data) != source.size_bytes or hashlib.sha256(data).hexdigest() != source.sha256:
                    raise ValueError(f"Source changed during export: {source.rel_path.as_posix()}")
            return data

        def archive_bytes_for(sources: Sequence[SourceFile]) -> bytes:
            output = io.BytesIO()
            with gzip.GzipFile(
                filename="", mode="wb", fileobj=output, mtime=0,
                compresslevel=GZIP_COMPRESSLEVEL,
            ) as gz_output:
                with tarfile.open(fileobj=gz_output, mode="w", format=tarfile.PAX_FORMAT) as archive:
                    for source in sources:
                        data = source_bytes(source)
                        info = tarfile.TarInfo(source.rel_path.as_posix())
                        info.size = len(data)
                        info.mode = source.mode if source.mode is not None else 0o644
                        info.mtime = 0
                        info.uid = info.gid = 0
                        info.uname = info.gname = ""
                        archive.addfile(info, io.BytesIO(data))
            return output.getvalue()

        def payload_bytes_for(archive_name: str, archive_bytes: bytes) -> tuple[bytes, bytes]:
            body = __import__("base64").b64encode(archive_bytes)
            wrapped = b"\n".join(body[index : index + 76] for index in range(0, len(body), 76))
            header = (
                "BAIC-ENCODED-CONTEXT-V1\n"
                f"archive-name: {archive_name}\n"
                "content-format: tar+gzip\n"
                "transport-encoding: base64\n"
                f"archive-size-bytes: {len(archive_bytes)}\n"
                f"archive-sha256: {hashlib.sha256(archive_bytes).hexdigest()}\n"
                f"base64-body-size-bytes: {len(body)}\n"
                f"base64-body-sha256: {hashlib.sha256(body).hexdigest()}\n\n"
            ).encode("ascii")
            return header + wrapped + b"\n", body

        source_groups: List[List[SourceFile]] = [sorted_sources]
        group_archives: List[bytes] = []
        if split:
            source_groups = []
            start = 0
            probe_name = f"{folder_name}_context_part_001_of_999_{timestamp}.tar.gz"
            while start < len(sorted_sources):
                low = start + 1
                high = len(sorted_sources)
                best_end = start
                best_archive: Optional[bytes] = None
                while low <= high:
                    middle = (low + high) // 2
                    candidate_archive = archive_bytes_for(sorted_sources[start:middle])
                    candidate_payload, _ = payload_bytes_for(probe_name, candidate_archive)
                    if len(candidate_payload) <= split_payload_max_bytes:
                        best_end = middle
                        best_archive = candidate_archive
                        low = middle + 1
                    else:
                        high = middle - 1
                if best_archive is None:
                    source = sorted_sources[start]
                    raise ValueError(
                        f"File cannot fit in one {split_payload_max_bytes}-byte payload: "
                        f"{source.rel_path.as_posix()}"
                    )
                source_groups.append(sorted_sources[start:best_end])
                group_archives.append(best_archive)
                start = best_end
        else:
            group_archives = [archive_bytes_for(sorted_sources)]

        payload_records: List[Dict[str, object]] = []
        entry_part_lookup: Dict[str, int] = {}
        part_count = len(source_groups)
        for part_index, (sources, archive_bytes) in enumerate(
            zip(source_groups, group_archives), start=1
        ):
            suffix = f"_part_{part_index:03d}_of_{part_count:03d}" if split else ""
            archive_name = f"{folder_name}_context{suffix}_{timestamp}.tar.gz"
            payload_name = f"{folder_name}_payload{suffix}_{timestamp}.txt"
            payload_bytes, body = payload_bytes_for(archive_name, archive_bytes)
            if split and len(payload_bytes) > split_payload_max_bytes:
                raise ValueError(f"Generated payload exceeds split limit: {payload_name}")
            (output_dir / payload_name).write_bytes(payload_bytes)
            paths = [source.rel_path.as_posix() for source in sources]
            for path in paths:
                entry_part_lookup[path] = part_index
            payload_records.append(
                {
                    "part": part_index,
                    "part_count": part_count,
                    "payload": payload_name,
                    "payload_size_bytes": len(payload_bytes),
                    "payload_sha256": hashlib.sha256(payload_bytes).hexdigest(),
                    "base64_body_size_bytes": len(body),
                    "base64_body_sha256": hashlib.sha256(body).hexdigest(),
                    "archive_name": archive_name,
                    "archive_size_bytes": len(archive_bytes),
                    "archive_sha256": hashlib.sha256(archive_bytes).hexdigest(),
                    "entries": paths,
                }
            )

        entries = [
            {
                "path": source.rel_path.as_posix(),
                "category": source.category,
                "content_kind": "binary" if source.encoding != "text" else "text",
                "source_format": "gzip" if source.rel_path.suffix.lower() == ".gz" else None,
                "transport_encoding": "identity",
                "size_bytes": source.size_bytes,
                "sha256": source.sha256,
                "mode": source.mode if source.mode is not None else 0o644,
                "payload_part": entry_part_lookup[source.rel_path.as_posix()],
            }
            for source in sorted_sources
        ]
        transport_details: Dict[str, object] = {
            "format": "tar+gzip+base64",
            "split": split,
            "payload_count": part_count,
            "payloads": payload_records,
            "deterministic": True,
        }
        if not split:
            transport_details.update({key: value for key, value in payload_records[0].items() if key not in {"part", "part_count", "entries"}})
        manifest.update(
            {
                "schema_version": 4 if split else 3,
                "transported_files": [entry["path"] for entry in entries],
                "summary": {
                    **manifest["summary"],
                    "transported_file_count": len(entries),
                    "transported_total_bytes": sum(entry["size_bytes"] for entry in entries),
                },
                "transport": transport_details,
                "archive_entries": entries,
                "payload_count": part_count,
                "bundle_count": 0,
                "bundles": [],
            }
        )
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
