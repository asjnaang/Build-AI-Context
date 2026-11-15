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
import zlib
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


def _repack_group_window(
    groups: Sequence[Sequence[SourceFile]],
    group_sizes: Sequence[int],
    member_weights: Dict[str, int],
    capacity: int,
    max_nodes: int = 250_000,
) -> Optional[List[List[SourceFile]]]:
    """Repack a small group window into one fewer bin using bounded exact search."""
    target_count = len(groups) - 1
    if target_count < 1 or sum(group_sizes) > target_count * capacity:
        return None
    sources = sorted(
        (source for group in groups for source in group),
        key=lambda source: (-member_weights[source.rel_path.as_posix()], source.rel_path.as_posix()),
    )
    if sources and member_weights[sources[0].rel_path.as_posix()] > capacity:
        return None
    target_groups: List[List[SourceFile]] = [[] for _ in range(target_count)]
    remaining = [capacity] * target_count
    nodes = 0

    def place(source_index: int) -> bool:
        nonlocal nodes
        nodes += 1
        if nodes > max_nodes:
            return False
        if source_index == len(sources):
            return True
        source = sources[source_index]
        weight = member_weights[source.rel_path.as_posix()]
        tried_remaining: Set[int] = set()
        for group_index in sorted(range(target_count), key=lambda index: remaining[index]):
            available = remaining[group_index]
            if available < weight or available in tried_remaining:
                continue
            tried_remaining.add(available)
            target_groups[group_index].append(source)
            remaining[group_index] -= weight
            if place(source_index + 1):
                return True
            remaining[group_index] += weight
            target_groups[group_index].pop()
            if available == capacity:
                break
        return False

    if place(0):
        return [group for group in target_groups if group]

    # The common compaction case is three underfilled payloads that should fit in two.
    # Exact backtracking can hit its node bound when those payloads contain hundreds of
    # small files. A quantized bitset subset-sum finds that two-bin partition in bounded
    # time and memory. Rounding every member up makes a found partition conservative;
    # the caller still verifies the resulting payload bytes against the exact limit.
    if target_count != 2:
        return None
    for quantum in (1024, 256):
        capacity_units = capacity // quantum
        scaled = [
            (member_weights[source.rel_path.as_posix()] + quantum - 1) // quantum
            for source in sources
        ]
        total_units = sum(scaled)
        if total_units > 2 * capacity_units:
            continue
        reachable = 1
        mask = (1 << (capacity_units + 1)) - 1
        history = [reachable]
        for weight in scaled:
            reachable = (reachable | (reachable << weight)) & mask
            history.append(reachable)
        lower_bound = max(0, total_units - capacity_units)
        midpoint = total_units // 2
        target = next(
            (
                candidate
                for distance in range(capacity_units + 1)
                for candidate in (midpoint - distance, midpoint + distance)
                if lower_bound <= candidate <= capacity_units
                and (reachable >> candidate) & 1
            ),
            None,
        )
        if target is None:
            continue
        first: List[SourceFile] = []
        second: List[SourceFile] = []
        for index in range(len(sources) - 1, -1, -1):
            previous = history[index]
            if (previous >> target) & 1:
                second.append(sources[index])
            else:
                first.append(sources[index])
                target -= scaled[index]
        if first and second:
            return [first, second]
    return None


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
    split_payload_max_bytes: int = 19_900_000,
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

        # A split payload has Base64 and TAR framing overhead. Split large source files into
        # deterministic transport members before payload packing so one incompressible PDF,
        # SQLite database, or existing .gz file cannot make the export impossible.
        logical_sources = sorted_sources
        reassembly_records: List[Dict[str, object]] = []
        part_owner: Dict[str, str] = {}
        if split:
            framing_reserve = min(128 * 1024, split_payload_max_bytes // 8)
            # Keep physical members below half of one archive's usable capacity. This
            # prevents three individually valid, half-full members from becoming an
            # unsplittable three-bin pattern even when their combined bytes fit two
            # payloads. Splitting changes only TAR member boundaries; total compression
            # work remains linear in the same source bytes.
            max_member_bytes = max(1, (split_payload_max_bytes * 3 // 8) - framing_reserve)
            physical_sources: List[SourceFile] = []
            for source in logical_sources:
                data = source_bytes(source)
                if len(data) <= max_member_bytes:
                    physical_sources.append(source)
                    continue
                part_count_for_file = (len(data) + max_member_bytes - 1) // max_member_bytes
                member_paths: List[str] = []
                file_key = hashlib.sha256(source.rel_path.as_posix().encode("utf-8")).hexdigest()[:16]
                for part_index in range(part_count_for_file):
                    start_offset = part_index * max_member_bytes
                    part_data = data[start_offset : start_offset + max_member_bytes]
                    member_path = Path(
                        ".baic-file-parts"
                    ) / file_key / f"{part_index + 1:06d}-of-{part_count_for_file:06d}.part"
                    member_paths.append(member_path.as_posix())
                    part_owner[member_path.as_posix()] = source.rel_path.as_posix()
                    physical_sources.append(
                        SourceFile(
                            abs_path=source.abs_path,
                            rel_path=member_path,
                            category=source.category,
                            line_count=0,
                            size_bytes=len(part_data),
                            sha256=hashlib.sha256(part_data).hexdigest(),
                            lines=[],
                            encoding="base64",
                            snapshot_bytes=part_data,
                            mode=source.mode,
                        )
                    )
                reassembly_records.append(
                    {
                        "path": source.rel_path.as_posix(),
                        "size_bytes": source.size_bytes,
                        "sha256": source.sha256,
                        "mode": source.mode if source.mode is not None else 0o644,
                        "members": member_paths,
                    }
                )
            sorted_sources = physical_sources

        source_groups: List[List[SourceFile]] = [sorted_sources]
        group_archives: List[bytes] = []
        if split:
            # Estimate each member from bounded samples, pack near the real compressed limit,
            # then split only a rare group whose final payload exceeds that limit.
            framing_reserve = min(128 * 1024, split_payload_max_bytes // 16)
            encoded_budget = max(1, split_payload_max_bytes - framing_reserve)
            archive_budget = max(1, encoded_budget * 3 // 4)
            sample_size = 64 * 1024

            def estimated_archive_size(source: SourceFile) -> int:
                data = source_bytes(source)
                if len(data) <= sample_size:
                    sample = data
                else:
                    half = sample_size // 2
                    sample = data[:half] + data[-half:]
                compressed_size = len(zlib.compress(sample, level=GZIP_COMPRESSLEVEL))
                ratio = compressed_size / max(1, len(sample))
                estimated_data = max(compressed_size, int(source.size_bytes * ratio))
                return 512 + ((estimated_data + 511) // 512 * 512)

            estimates = {
                source.rel_path.as_posix(): estimated_archive_size(source)
                for source in sorted_sources
            }

            def best_fit_groups(sources: Sequence[SourceFile]) -> List[List[SourceFile]]:
                groups: List[List[SourceFile]] = []
                group_sizes: List[int] = []
                ordered_sources = sorted(
                    sources,
                    key=lambda source: (
                        -estimates[source.rel_path.as_posix()],
                        source.rel_path.as_posix(),
                    ),
                )
                for source in ordered_sources:
                    member_size = estimates[source.rel_path.as_posix()]
                    best_index: Optional[int] = None
                    best_remaining: Optional[int] = None
                    for index, group_size in enumerate(group_sizes):
                        remaining = archive_budget - group_size - member_size
                        if remaining >= 0 and (best_remaining is None or remaining < best_remaining):
                            best_index = index
                            best_remaining = remaining
                    if best_index is None:
                        groups.append([source])
                        group_sizes.append(1024 + member_size)
                    else:
                        groups[best_index].append(source)
                        group_sizes[best_index] += member_size
                return groups

            probe_name = f"{folder_name}_context_part_001_of_999_{timestamp}.tar.gz"
            # Compress each TAR member independently, then concatenate the gzip members.
            # RFC 1952 readers decode concatenated members as one byte stream, yielding one
            # ordinary TAR archive. Compressed member sizes are exact additive packing weights.
            def compressed_tar_member(source: SourceFile) -> bytes:
                data = source_bytes(source)
                info = tarfile.TarInfo(source.rel_path.as_posix())
                info.size = len(data)
                info.mode = source.mode if source.mode is not None else 0o644
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                padding = (-len(data)) % 512
                member_bytes = (
                    info.tobuf(format=tarfile.PAX_FORMAT) + data + (b"\0" * padding)
                )
                compressed_output = io.BytesIO()
                with gzip.GzipFile(
                    filename="", mode="wb", fileobj=compressed_output, mtime=0,
                    compresslevel=GZIP_COMPRESSLEVEL,
                ) as gz_output:
                    gz_output.write(member_bytes)
                return compressed_output.getvalue()

            compressed_members = {
                source.rel_path.as_posix(): compressed_tar_member(source)
                for source in sorted_sources
            }
            end_blocks_output = io.BytesIO()
            with gzip.GzipFile(
                filename="", mode="wb", fileobj=end_blocks_output, mtime=0,
                compresslevel=GZIP_COMPRESSLEVEL,
            ) as gz_output:
                gz_output.write(b"\0" * 1024)
            end_blocks = end_blocks_output.getvalue()
            member_weights = {
                path: len(member_bytes) for path, member_bytes in compressed_members.items()
            }
            def payload_size_for_archive_size(archive_size: int) -> int:
                body_size = ((archive_size + 2) // 3) * 4
                wrapped_body_size = body_size + ((body_size - 1) // 76) + 1
                header_size = len(
                    (
                        "BAIC-ENCODED-CONTEXT-V1\n"
                        f"archive-name: {probe_name}\n"
                        "content-format: tar+gzip\n"
                        "transport-encoding: base64\n"
                        f"archive-size-bytes: {archive_size}\n"
                        f"archive-sha256: {'0' * 64}\n"
                        f"base64-body-size-bytes: {body_size}\n"
                        f"base64-body-sha256: {'0' * 64}\n\n"
                    ).encode("ascii")
                )
                return header_size + wrapped_body_size

            low, high = 0, split_payload_max_bytes
            while low < high:
                middle = (low + high + 1) // 2
                if payload_size_for_archive_size(middle) <= split_payload_max_bytes:
                    low = middle
                else:
                    high = middle - 1
            exact_archive_budget = max(1, low - len(end_blocks))

            exact_groups: List[List[SourceFile]] = []
            exact_group_sizes: List[int] = []
            for source in sorted(
                sorted_sources,
                key=lambda item: (
                    -member_weights[item.rel_path.as_posix()], item.rel_path.as_posix()
                ),
            ):
                member_size = member_weights[source.rel_path.as_posix()]
                best_index: Optional[int] = None
                best_remaining: Optional[int] = None
                for index, group_size in enumerate(exact_group_sizes):
                    remaining = exact_archive_budget - group_size - member_size
                    if remaining >= 0 and (best_remaining is None or remaining < best_remaining):
                        best_index = index
                        best_remaining = remaining
                if best_index is None:
                    exact_groups.append([source])
                    exact_group_sizes.append(member_size)
                else:
                    exact_groups[best_index].append(source)
                    exact_group_sizes[best_index] += member_size

            # Best-fit decreasing is fast but can leave a local three-bin pattern that fits
            # into two bins after redistribution. Search only the least-filled windows, with a
            # strict node bound, to remove that extra payload without unbounded latency.
            improved = True
            while improved and len(exact_groups) > 2:
                improved = False
                for window_size in range(3, min(5, len(exact_groups)) + 1):
                    selected = sorted(
                        range(len(exact_groups)), key=lambda index: exact_group_sizes[index]
                    )[:window_size]
                    window_groups = [exact_groups[index] for index in selected]
                    window_sizes = [exact_group_sizes[index] for index in selected]
                    repacked = _repack_group_window(
                        window_groups, window_sizes, member_weights, exact_archive_budget
                    )
                    if repacked is None:
                        continue
                    retained = [
                        index for index in range(len(exact_groups)) if index not in set(selected)
                    ]
                    exact_groups = [exact_groups[index] for index in retained] + repacked
                    exact_group_sizes = [exact_group_sizes[index] for index in retained] + [
                        sum(member_weights[source.rel_path.as_posix()] for source in group)
                        for group in repacked
                    ]
                    improved = True
                    break

            exact_archives: List[bytes] = []
            for group in exact_groups:
                group.sort(key=lambda source: source.rel_path.as_posix())
                archive_bytes = b"".join(
                    compressed_members[source.rel_path.as_posix()] for source in group
                ) + end_blocks
                payload_bytes, _ = payload_bytes_for(probe_name, archive_bytes)
                if len(payload_bytes) > split_payload_max_bytes:
                    source = group[0]
                    raise ValueError(
                        f"File cannot fit in one {split_payload_max_bytes}-byte payload: "
                        f"{part_owner.get(source.rel_path.as_posix(), source.rel_path.as_posix())}"
                    )
                exact_archives.append(archive_bytes)
            source_groups = exact_groups
            group_archives = exact_archives

            ordered_parts = sorted(
                zip(source_groups, group_archives),
                key=lambda item: item[0][0].rel_path.as_posix(),
            )
            source_groups = [item[0] for item in ordered_parts]
            group_archives = [item[1] for item in ordered_parts]
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
            "reassembly": reassembly_records,
        }
        if not split:
            transport_details.update({key: value for key, value in payload_records[0].items() if key not in {"part", "part_count", "entries"}})
        manifest.update(
            {
                "schema_version": 5 if reassembly_records else (4 if split else 3),
                "transported_files": [source.rel_path.as_posix() for source in logical_sources],
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
