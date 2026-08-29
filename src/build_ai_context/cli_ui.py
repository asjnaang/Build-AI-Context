"""
CLI UI helpers for build_ai_context - prompts, rendering, and interactive selection.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from build_ai_context.constants import CATEGORY_DESCRIPTIONS
from build_ai_context.exporter import CodeExporter
from build_ai_context.models import SourceFile


def prompt_yes_no(message: str, default: bool = True) -> bool:
    """Prompt the user for a yes/no answer."""
    suffix = " [Y/n]: " if default else " [y/N]: "
    raw = input(message + suffix).strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes"}


def ask_choice(prompt: str, valid_choices: Sequence[str], default: str | None = None) -> str:
    """Prompt the user to choose from valid options."""
    valid_normalized = {choice.lower(): choice for choice in valid_choices}
    while True:
        suffix = f" [{'/'.join(valid_choices)}]"
        if default:
            suffix += f" (default: {default})"
        raw = input(f"{prompt}{suffix}: ").strip().lower()
        if not raw and default:
            return default
        if raw in valid_normalized:
            return valid_normalized[raw]
        print(f"Please choose one of: {', '.join(valid_choices)}")


def render_category_table(exporter: CodeExporter, files: Sequence[SourceFile]) -> None:
    """Render a table showing files by category."""
    summary = exporter.summarize_by_category(files)
    if exporter._table_class and exporter._console:
        table = exporter._table_class(title="Detected source files by category")
        table.add_column("Category", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Files", justify="right", style="green")
        table.add_column("Lines", justify="right", style="yellow")
        table.add_column("Bytes", justify="right", style="magenta")

        for cat in sorted(summary.keys()):
            stats = summary[cat]
            desc = CATEGORY_DESCRIPTIONS.get(cat, cat)
            table.add_row(cat, desc, str(stats["files"]), str(stats["lines"]), str(stats["bytes"]))
        exporter._console.print(table)
    else:
        print("Detected source files by category:")
        print(f"{'Category':<15} {'Files':>6} {'Lines':>8} {'Bytes':>10}")
        print("-" * 45)
        for cat in sorted(summary.keys()):
            stats = summary[cat]
            print(f"{cat:<15} {stats['files']:>6} {stats['lines']:>8} {stats['bytes']:>10}")


def render_folder_table(
    exporter: CodeExporter, files: Sequence[SourceFile], limit: int = 15
) -> None:
    """Render a table showing top folders by file count."""
    summary = exporter.summarize_top_folders(files, limit)
    if exporter._table_class and exporter._console:
        table = exporter._table_class(title=f"Top folders (showing first {limit})")
        table.add_column("Folder", style="cyan")
        table.add_column("Files", justify="right", style="green")
        table.add_column("Lines", justify="right", style="yellow")

        for folder_name, stats in list(summary.items())[:limit]:
            table.add_row(folder_name, str(stats["files"]), str(stats["lines"]))
        exporter._console.print(table)
    else:
        print(f"\nTop folders (showing first {limit}):")
        print(f"{'Folder':<20} {'Files':>6} {'Lines':>8}")
        print("-" * 40)
        for folder_name, stats in list(summary.items())[:limit]:
            print(f"{folder_name:<20} {stats['files']:>6} {stats['lines']:>8}")


def render_selection_modes(exporter: CodeExporter) -> None:
    """Render the selection mode menu."""
    modes = [
        ("1", "all", "Export everything supported"),
        ("2", "category", "Pick categories (python, typescript, etc.)"),
        ("3", "path", "Pick files/folders by path"),
        ("4", "mixed", "Categories + paths + name filters"),
        ("5", "keyword", "Search by keywords in file content"),
    ]
    print("\n" + "=" * 75)
    print("Selection modes".center(75))
    print("=" * 75)
    for num, name, desc in modes:
        print(f"│ {num}) {name:<12} -> {desc:<57} │")
    print("─" * 75)


def interactive_select_files(
    exporter: CodeExporter,
    all_files: Sequence[SourceFile],
    root: Path,
) -> Tuple[List[SourceFile], Dict[str, object]]:
    """Run the interactive file selection workflow."""
    render_selection_modes(exporter)
    mode = ask_choice("Choose selection mode", ["1", "2", "3", "4", "5"], default="1")

    selected: List[SourceFile] = []
    metadata: Dict[str, object] = {
        "selection_mode": "",
        "selected_categories": [],
        "selected_paths": [],
        "name_filters": [],
        "missing_paths": [],
    }

    if mode == "1":
        selected = list(all_files)
        metadata["selection_mode"] = "all"

    elif mode == "2":
        categories = exporter.parse_csv_input(
            input("Enter categories (comma-separated, e.g. python,shell): ")
        )
        categories = exporter.normalize_categories(categories)
        selected = [f for f in all_files if f.category in categories]
        metadata.update(
            selection_mode="category",
            selected_categories=categories,
        )

    elif mode == "3":
        raw_paths = input("Enter paths (comma/space-separated): ")
        path_prefixes = exporter.parse_intelligent_input(raw_paths, all_files, root)
        selected = exporter.filter_files_by_paths(all_files, path_prefixes, root)
        missing = set(path_prefixes) - {f.rel_path.as_posix().split("/")[0] for f in selected}
        metadata.update(
            selection_mode="path",
            selected_paths=path_prefixes,
            missing_paths=list(missing),
        )

    elif mode == "4":
        categories_input = input("Enter categories (comma-separated, or press Enter for all): ")
        categories = exporter.parse_csv_input(categories_input)
        categories = exporter.normalize_categories(categories) if categories else []

        paths_input = input("Enter paths (comma-separated, or press Enter for all): ")
        path_prefixes = (
            exporter.parse_intelligent_input(paths_input, all_files, root) if paths_input else []
        )

        filters_input = input("Enter name filters (comma-separated, or press Enter): ")
        name_filters = exporter.parse_csv_input(filters_input)

        by_category = (
            [f for f in all_files if f.category in categories] if categories else list(all_files)
        )
        by_paths = (
            exporter.filter_files_by_paths(by_category, path_prefixes, root)
            if path_prefixes
            else by_category
        )
        if name_filters:
            filtered = []
            for f in by_paths:
                fname = f.rel_path.name.lower()
                if any(nf.lower() in fname for nf in name_filters):
                    filtered.append(f)
            by_paths = filtered
        selected = by_paths
        metadata.update(
            selection_mode="mixed",
            selected_categories=categories,
            selected_paths=path_prefixes,
            name_filters=name_filters,
        )

    elif mode == "5":
        keywords_input = input("Enter keywords to search in file content: ")
        keywords = exporter.parse_csv_input(keywords_input)
        if keywords:
            matched, found = exporter.filter_files_by_keywords(all_files, keywords)
            if matched:
                if exporter._questionary_available:
                    choices = [
                        exporter._questionary.Choice(title=str(f.rel_path), value=f, checked=True)
                        for f in matched
                    ]
                    selected = exporter._questionary.checkbox(
                        "Select files to include:", choices=choices
                    ).ask()
                    if selected is None:
                        selected = []
                else:
                    print(f"\nFound {len(matched)} files containing {found}")
                    for f in matched:
                        print(f"  {f.rel_path.as_posix()}")
                    confirm = prompt_yes_no("Include all matched files?", default=True)
                    if confirm:
                        selected = list(matched)
                metadata.update(
                    selection_mode="keyword",
                    name_filters=keywords,
                )
            else:
                print("No files matched the keywords.")

    return selected, metadata
