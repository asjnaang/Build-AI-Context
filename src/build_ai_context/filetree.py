"""
Filetree generation for build_ai_context.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Sequence

from build_ai_context.constants import DEFAULT_OUTPUT_DIR, generate_timestamp
from build_ai_context.models import SourceFile


def sanitize_output_dir_name(root: Path) -> str:
    """Generate a sanitized output directory name with timestamp."""
    timestamp = generate_timestamp()
    project_name = root.name.replace(" ", "_") or "project"
    return f"{DEFAULT_OUTPUT_DIR}_{project_name}_{timestamp}"


def generate_filetree(files: Sequence[SourceFile], root: Path) -> str:
    """Generate a path-list filetree that AI agents can parse."""
    paths = sorted(f.rel_path.as_posix() for f in files)
    type_counts: Dict[str, int] = defaultdict(int)
    for source in files:
        type_counts[source.category] += 1

    lines: List[str] = [
        f"root: {root.name}",
        f"file_count: {len(paths)}",
        "",
        "paths:",
        *[f"{path}," for path in paths],
        "",
        "types:",
    ]
    for category, count in sorted(type_counts.items()):
        lines.append(f"{category}: {count}")
    return "\n".join(lines)


def update_gitignore(root: Path, filetree_name: str) -> None:
    """Update .gitignore to ignore exported_sources, filetree, and graph files."""
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
    has_graph_txt = any(
        "*_code_graph_*.txt" in line and not line.strip().startswith("#")
        for line in existing_lines
    )
    has_graph_json = any(
        "*_code_graph_*.json" in line and not line.strip().startswith("#")
        for line in existing_lines
    )

    if existing_lines and existing_lines[-1].strip():
        new_lines.append("")

    if not has_exported_sources:
        new_lines.append("# Ignore exported source bundles")
        new_lines.append("exported_sources*/")

    if not has_filetree:
        new_lines.append("# Ignore filetree files (all timestamps)")
        new_lines.append("*_file_tree_*.txt")

    if not has_graph_txt:
        new_lines.append("# Ignore code graph files (all timestamps)")
        new_lines.append("*_code_graph_*.txt")
    if not has_graph_json:
        new_lines.append("# Ignore JSON code graph files (all timestamps)")
        new_lines.append("*_code_graph_*.json")

    if new_lines:
        updated = existing_lines + new_lines
        gitignore_path.write_text("\n".join(updated) + "\n", encoding="utf-8")
