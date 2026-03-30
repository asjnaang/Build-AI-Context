"""
Filetree generation for build_ai_context.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from build_ai_context.constants import DEFAULT_OUTPUT_DIR, generate_timestamp
from build_ai_context.icons import get_file_icon, get_icon_display_name
from build_ai_context.models import SourceFile


def sanitize_output_dir_name(root: Path) -> str:
    """Generate a sanitized output directory name with timestamp."""
    timestamp = generate_timestamp()
    project_name = root.name.replace(" ", "_") or "project"
    return f"{DEFAULT_OUTPUT_DIR}_{project_name}_{timestamp}"


def generate_filetree(files: Sequence[SourceFile], root: Path) -> str:
    """Generate a filetree with full paths for AI assistants."""
    # Group files by their immediate parent directory with icons
    by_parent: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    for f in sorted(files, key=lambda x: x.rel_path.as_posix()):
        parts = f.rel_path.as_posix().split("/")
        icon = get_file_icon(parts[-1], f.category)
        if len(parts) == 1:
            by_parent["."].append((parts[0], icon))
        else:
            parent = "/".join(parts[:-1])
            by_parent[parent].append((parts[-1], icon))

    lines: List[str] = [f"{root.name}/"]

    # Get all unique parent directories sorted
    all_parents = sorted(set(k for k in by_parent.keys() if k != "."))

    # Render root-level files
    root_files = sorted(by_parent.get(".", []), key=lambda x: x[0])
    for i, (fname, icon) in enumerate(root_files):
        is_last = i == len(root_files) - 1 and not all_parents
        connector = "└── " if is_last else "├── "
        lines.append(f"{connector}{icon} {fname}")

    # Group parents by top-level directory
    top_level_groups: Dict[str, List[str]] = defaultdict(list)
    for parent in all_parents:
        top = parent.split("/")[0]
        top_level_groups[top].append(parent)

    # Render each top-level directory
    top_dirs = sorted(top_level_groups.keys())
    for i, top_dir in enumerate(top_dirs):
        parents_in_group = sorted(top_level_groups[top_dir])
        remaining = len(top_dirs) - i - 1
        is_last_top = remaining == 0 and len(root_files) == 0
        connector = "└── " if is_last_top else "├── "

        # Check if this is a simple single-file directory
        if len(parents_in_group) == 1 and parents_in_group[0] == top_dir:
            # Direct files in this directory only
            files_here = sorted(by_parent.get(top_dir, []), key=lambda x: x[0])
            if len(files_here) <= 3:
                # Show compact: dir/ -> icon file1, icon file2, icon file3
                file_list = ", ".join(f"{icon} {fname}" for fname, icon in files_here)
                lines.append(f"{connector}{top_dir}/ [{file_list}]")
            else:
                lines.append(f"{connector}{top_dir}/")
                sub_prefix = "    " if is_last_top else "│   "
                for j, (fname, icon) in enumerate(files_here):
                    is_last_file = j == len(files_here) - 1
                    fc = "└── " if is_last_file else "├── "
                    lines.append(f"{sub_prefix}{fc}{icon} {fname}")
        else:
            # Complex directory with nested structure
            lines.append(f"{connector}{top_dir}/")
            sub_prefix = "    " if is_last_top else "│   "
            _render_parent_group(parents_in_group, by_parent, top_dir, sub_prefix, lines)

    # Add file type summary at the end
    lines.append("")
    lines.append("─" * 40)
    lines.append("📊 File Summary:")
    type_counts: Dict[str, int] = defaultdict(int)
    for f in files:
        icon = get_file_icon(f.rel_path.name, f.category)
        type_counts[icon] += 1

    for icon, count in sorted(type_counts.items(), key=lambda x: (-x[1], x[0])):
        type_name = get_icon_display_name(icon)
        lines.append(f"  {icon} {type_name:<12} × {count}")

    lines.append(f"  ───")
    lines.append(f"  📁  Total: {len(files)} files")

    return "\n".join(lines)


def _render_parent_group(
    parents: List[str],
    by_parent: Dict[str, List[Tuple[str, str]]],
    top_dir: str,
    prefix: str,
    lines: List[str],
) -> None:
    """Render a group of parent directories under a top-level directory."""
    for i, parent in enumerate(parents):
        is_last = i == len(parents) - 1
        connector = "└── " if is_last else "├── "

        files_here = sorted(by_parent.get(parent, []), key=lambda x: x[0])

        if parent == top_dir:
            # Direct files in top directory
            for j, (fname, icon) in enumerate(files_here):
                is_last_file = j == len(files_here) - 1 and i == len(parents) - 1
                fc = "└── " if is_last_file else "├── "
                lines.append(f"{prefix}{fc}{icon} {fname}")
        else:
            # Nested subdirectory
            rel_path = parent[len(top_dir) + 1 :]
            lines.append(f"{prefix}{connector}{rel_path}/")
            sub_prefix = prefix + ("    " if is_last else "│   ")
            for j, (fname, icon) in enumerate(files_here):
                is_last_file = j == len(files_here) - 1
                fc = "└── " if is_last_file else "├── "
                lines.append(f"{sub_prefix}{fc}{icon} {fname}")


def update_gitignore(root: Path, filetree_name: str) -> None:
    """Update .gitignore to ignore exported_sources and filetree files."""
    gitignore_path = root / ".gitignore"

    existing_lines: List[str] = []
    if gitignore_path.exists():
        existing_lines = gitignore_path.read_text(encoding="utf-8").splitlines()

    new_lines: List[str] = []

    has_exported_sources = any(
        "exported_sources" in line and not line.strip().startswith("#") for line in existing_lines
    )
    has_filetree = any(
        "_file_tree_" in line and not line.strip().startswith("#") for line in existing_lines
    )

    if existing_lines and existing_lines[-1].strip():
        new_lines.append("")

    if not has_exported_sources:
        new_lines.append("# Ignore exported source bundles")
        new_lines.append("exported_sources*/")

    if not has_filetree:
        new_lines.append("# Ignore filetree files (all timestamps)")
        new_lines.append("*_file_tree_*.txt")

    if new_lines:
        updated = existing_lines + new_lines
        gitignore_path.write_text("\n".join(updated) + "\n", encoding="utf-8")
