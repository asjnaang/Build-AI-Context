"""
Filetree generation for build_ai_context.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Sequence

from build_ai_context.constants import (
    DEFAULT_OUTPUT_DIR,
    GENERATED_FILES_DIR,
    generate_timestamp,
)
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
    root_path = root.name.replace(" ", "_") or "project"
    lines: List[str] = [
        f"root: {root_path}",
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


def generated_files_dir(root: Path) -> Path:
    """Create and return the repository-local generated-files directory."""
    output = root / GENERATED_FILES_DIR
    output.mkdir(parents=True, exist_ok=True)
    return output


def update_gitignore(root: Path, _generated_name: str = "") -> None:
    """Consolidate legacy generated-output ignores into one .gen_files rule."""
    gitignore_path = root / ".gitignore"
    if not gitignore_path.is_file():
        return

    legacy_patterns = {
        "exported_sources**",
        "exported_sources*",
        "exported_sources*/",
        "*_file_tree_*.txt",
        "*_code_graph_*.txt",
        "*_code_graph_*.json",
        ".gapply-logs",
        ".gapply-logs*",
        "git_commit_exports",
        "git_commit_exports/",
    }
    original = gitignore_path.read_text(encoding="utf-8")
    lines = [line for line in original.splitlines() if line.strip() not in legacy_patterns]
    generated_pattern = f"{GENERATED_FILES_DIR}/**"
    if generated_pattern not in {line.strip() for line in lines}:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(
            [
                "# Generated files created by build",
                generated_pattern,
            ]
        )
    updated = "\n".join(lines) + "\n"
    if updated != original:
        gitignore_path.write_text(updated, encoding="utf-8", newline="\n")
