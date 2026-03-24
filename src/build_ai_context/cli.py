"""
Command-line interface for build_ai_context package.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Sequence

from build_ai_context import __version__
from build_ai_context.constants import (
    CATEGORY_DESCRIPTIONS,
    DEFAULT_MAX_LINES,
)
from build_ai_context.exporter import CodeExporter
from build_ai_context.models import SourceFile


def prompt_yes_no(message: str, default: bool = True) -> bool:
    """Prompt the user for a yes/no answer."""
    suffix = " [Y/n]: " if default else " [y/N]: "
    raw = input(message + suffix).strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes"}
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
        table.add_column("Category")
        table.add_column("Description")
        table.add_column("Files", justify="right")
        table.add_column("Lines", justify="right")
        table.add_column("Bytes", justify="right")
        for category in CATEGORY_DESCRIPTIONS:
            row = summary.get(category, {"files": 0, "lines": 0, "bytes": 0})
            table.add_row(
                category,
                CATEGORY_DESCRIPTIONS[category],
                str(row["files"]),
                str(row["lines"]),
                str(row["bytes"]),
            )
        exporter._console.print(table)
    else:
        print("\nDetected source files by category")
        for category in CATEGORY_DESCRIPTIONS:
            row = summary.get(category, {"files": 0, "lines": 0, "bytes": 0})
            print(
                f"- {category:12} | files={row['files']:4} lines={row['lines']:6} "
                f"bytes={row['bytes']:8} | {CATEGORY_DESCRIPTIONS[category]}"
            )


def render_folder_table(
    exporter: CodeExporter, files: Sequence[SourceFile], limit: int = 20
) -> None:
    """Render a table showing top folders."""
    folder_summary = exporter.summarize_top_folders(files)
    items = list(folder_summary.items())[:limit]
    if not items:
        return
    if exporter._table_class and exporter._console:
        table = exporter._table_class(title=f"Top folders (showing first {len(items)})")
        table.add_column("Folder")
        table.add_column("Files", justify="right")
        table.add_column("Lines", justify="right")
        for folder, data in items:
            table.add_row(folder, str(data["files"]), str(data["lines"]))
        exporter._console.print(table)
    else:
        print("\nTop folders")
        for folder, data in items:
            print(f"- {folder:30} files={data['files']:4} lines={data['lines']:6}")


def render_selection_modes(exporter: CodeExporter) -> None:
    """Render selection mode options with nice formatting using Rich."""
    if exporter._console:
        from rich.panel import Panel

        console = exporter._console

        options = [
            ("1", "all", "Export everything supported"),
            ("2", "category", "Pick categories (python, typescript, etc.)"),
            ("3", "path", "Pick files/folders by path"),
            ("4", "mixed", "Categories + paths + name filters"),
            ("5", "keyword", "Search by keywords in file content"),
        ]

        content = ""
        for num, name, desc in options:
            content += f"{num}) {name:<12} -> {desc}\n"

        panel = Panel(
            content.strip(),
            title="Selection modes",
            border_style="white",
            padding=(0, 1),
        )
        console.print(panel)
    else:
        print("\nSelection modes:")
        print("  1) all       -> export everything supported")
        print("  2) category  -> pick categories like python, typescript, ios_apple")
        print(
            "  3) path      -> pick files/folders by relative path, absolute path, or just filename"
        )
        print("  4) mixed     -> categories + paths + file name contains filter")
        print("  5) keyword   -> search by keywords in file content and build context")


def interactive_select_files(
    exporter: CodeExporter,
    all_files: Sequence[SourceFile],
    root: Path,
) -> tuple:
    """Run interactive file selection."""
    if not all_files:
        return [], {
            "selection_mode": "interactive",
            "selected_categories": [],
            "selected_paths": [],
            "name_filters": [],
        }

    render_category_table(exporter, all_files)
    render_folder_table(exporter, all_files)

    render_selection_modes(exporter)

    mode = ask_choice("Choose selection mode", ["1", "2", "3", "4", "5"], default="1")
    selected = list(all_files)
    metadata = {
        "selection_mode": {"1": "all", "2": "category", "3": "path", "4": "mixed", "5": "keyword"}[
            mode
        ],
        "selected_categories": [],
        "selected_paths": [],
        "name_filters": [],
        "missing_paths": [],
    }

    if mode in {"2", "4"}:
        print("Available categories: " + ", ".join(CATEGORY_DESCRIPTIONS.keys()))
        raw = input(
            "Enter comma-separated categories (example: python,typescript,web_ui): "
        ).strip()
        categories = exporter.parse_csv_input(raw)
        categories = exporter.normalize_categories(categories)
        metadata["selected_categories"] = categories
        if categories:
            selected = [item for item in selected if item.category in categories]
        elif mode == "2":
            selected = []

    if mode in {"3", "4"}:
        raw = input(
            "Enter comma-separated file/folder paths or filenames (relative, absolute, or filename only): "
        ).strip()
        path_inputs = exporter.parse_csv_input(raw)
        selected, normalized_paths, missing_paths = exporter.filter_files_by_paths(
            selected,
            root,
            path_inputs,
            interactive=True,
            fancy=False,
        )
        metadata["selected_paths"] = normalized_paths
        metadata["missing_paths"] = missing_paths
        if missing_paths:
            print("These paths did not match supported files: " + ", ".join(missing_paths))

    if mode == "4":
        raw = input(
            "Optional file-name contains filters (comma-separated, example: auth,login,api) "
            "or press Enter to skip: "
        ).strip()
        filters = exporter.parse_csv_input(raw)
        metadata["name_filters"] = filters
        if filters:
            selected = [
                item
                for item in selected
                if any(token.lower() in item.rel_path.as_posix().lower() for token in filters)
            ]

    if mode == "5":
        raw = input(
            "Enter comma-separated keywords to search in file content (example: TODO,FIXME,debug): "
        ).strip()
        keywords = exporter.parse_csv_input(raw)
        if keywords:
            matched_files, matched_keywords = exporter.filter_files_by_keywords(
                list(all_files), keywords
            )
            exporter.print_info(
                f"Found {len(matched_files)} file(s) containing keywords: {', '.join(matched_keywords)}"
            )
            if matched_files:
                exporter.print_info("Matching files:")
                for f in matched_files:
                    exporter.print_info(f"  - {f.rel_path.as_posix()}")
                if prompt_yes_no("Build context for these files?"):
                    selected = matched_files
                    metadata["name_filters"] = matched_keywords
                    metadata["selected_paths"] = [f.rel_path.as_posix() for f in matched_files]
                else:
                    selected = []
                    exporter.print_warning("No files selected.")
            else:
                exporter.print_warning("No files found matching the keywords.")
        else:
            exporter.print_warning("No keywords entered.")

    selected.sort(key=lambda item: item.rel_path.as_posix())
    print(f"Selected {len(selected)} file(s) out of {len(all_files)} supported file(s).")
    return selected, metadata


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="build-ai-context",
        description="Export supported source files into AI-friendly text bundles with a manifest. "
        "Use 'baic' as a short alias for 'build-ai-context'.",
    )
    parser.add_argument(
        "project_root",
        nargs="?",
        default=".",
        help="Project root to scan. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=DEFAULT_MAX_LINES,
        help=f"Maximum rendered lines per output bundle (default: {DEFAULT_MAX_LINES}).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory. Defaults to a timestamped folder under the current directory.",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run without prompts. Optionally combine with --categories and/or --paths.",
    )
    parser.add_argument(
        "--categories",
        nargs="*",
        default=[],
        help="Categories to include in non-interactive mode. Example: --categories python typescript web_ui",
    )
    parser.add_argument(
        "--paths",
        nargs="*",
        default=[],
        help="Relative paths, absolute paths, or filenames to include in non-interactive mode.",
    )
    parser.add_argument(
        "--keywords",
        nargs="*",
        default=[],
        help="Keywords to search in file content (non-interactive mode).",
    )
    parser.add_argument(
        "--include-secret-files",
        action="store_true",
        help="Include files that look like secrets (.env, *.pem, *.key, keystores, etc.).",
    )
    parser.add_argument(
        "--fancy-ui",
        action="store_true",
        help="Use checkbox-style interactive selection with questionary.",
    )
    parser.add_argument(
        "--project-overview",
        action="store_true",
        help="Generate PROJECT_OVERVIEW.txt alongside the manifest and bundles.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main() -> int:
    """Main entry point for the CLI."""
    parser = build_parser()
    args = parser.parse_args()
    return run_exporter(args, None)


def run_exporter(args, exporter) -> int:
    """Run the exporter with given arguments."""
    if exporter is None:
        exporter = CodeExporter()

    try:
        root = Path(args.project_root).expanduser().resolve()
        if not root.exists():
            print(f"Error: Project root does not exist: {root}", file=sys.stderr)
            return 1
        if not root.is_dir():
            print(f"Error: Project root is not a directory: {root}", file=sys.stderr)
            return 1

        if args.max_lines <= 0:
            print("Error: --max-lines must be greater than zero", file=sys.stderr)
            return 1

        skip_secret_files = not args.include_secret_files
        exporter.print_info(f"Scanning project: {root}")

        all_files, skipped_reasons = exporter.scan_supported_files(root, skip_secret_files)
        if not all_files:
            exporter.print_warning(
                "No supported files were found after applying .gitignore and default exclusions."
            )
            return 0

        exporter.print_info(f"Detected {len(all_files)} supported text file(s).")

        if args.non_interactive:
            if args.keywords:
                matched_files, matched_keywords = exporter.filter_files_by_keywords(
                    all_files, args.keywords
                )
                if matched_files:
                    exporter.print_info(
                        f"Found {len(matched_files)} file(s) containing keywords: {', '.join(matched_keywords)}"
                    )
                    selected_files = matched_files
                    selection_metadata = {
                        "selection_mode": "keyword",
                        "selected_categories": [],
                        "selected_paths": [f.rel_path.as_posix() for f in matched_files],
                        "name_filters": matched_keywords,
                        "missing_paths": [],
                    }
                else:
                    exporter.print_warning("No files found matching the keywords.")
                    return 0
            else:
                selected_files, selection_metadata = exporter.non_interactive_select_files(
                    all_files,
                    categories=args.categories,
                    path_prefixes=args.paths,
                    root=root,
                )
        else:
            selected_files, selection_metadata = interactive_select_files(exporter, all_files, root)

        if not selected_files:
            exporter.print_warning("No files selected. Nothing was exported.")
            return 0

        chunks, skipped_during_split = exporter.split_into_chunks(selected_files, args.max_lines)
        bundles, skipped_during_pack = exporter.pack_chunks(chunks, args.max_lines)
        skipped_during_processing = skipped_during_split + skipped_during_pack

        output_dir = (
            Path(args.output_dir).expanduser().resolve()
            if args.output_dir
            else Path.cwd() / exporter.sanitize_output_dir_name(root)
        )

        manifest_path = exporter.write_bundles_and_manifest(
            root=root,
            selected_files=selected_files,
            bundles=bundles,
            output_dir=output_dir,
            max_lines=args.max_lines,
            skipped_reasons=skipped_reasons,
            selection_metadata=selection_metadata,
            skip_secret_files=skip_secret_files,
            skipped_during_pack=skipped_during_processing,
        )

        overview_path = None
        if args.project_overview:
            overview_path = exporter.write_project_overview(
                root=root,
                all_files=all_files,
                selected_files=selected_files,
                output_dir=output_dir,
                selection_metadata=selection_metadata,
            )

        exporter.print_success("\nExport complete.")
        exporter.print_success(f"Output directory : {output_dir}")
        exporter.print_success(f"Manifest         : {manifest_path}")
        if overview_path is not None:
            exporter.print_success(f"Project overview : {overview_path}")
        exporter.print_success(f"Bundles created  : {len(bundles)}")
        exporter.print_success(f"Files exported   : {len(selected_files)}")

        if skipped_during_processing:
            import json

            exporter.print_warning("Files/chunks skipped during processing:")
            for item in skipped_during_processing:
                exporter.print_warning("  - " + json.dumps(item, ensure_ascii=False))

        missing_paths = selection_metadata.get("missing_paths", [])
        if missing_paths:
            exporter.print_warning("Paths that did not match supported files:")
            for value in missing_paths:
                exporter.print_warning(f"  - {value}")

        return 0

    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def interactive_main() -> int:
    """Main entry point for interactive mode with loop."""
    exporter = CodeExporter()
    parser = build_parser()
    args = parser.parse_args()

    while True:
        result = run_exporter(args, exporter)

        if result != 0:
            return result

        if args.non_interactive:
            return 0

        user_input = input("Do you want to export more files? [Y/n]: ")

        if user_input.strip().lower() in ("", "y", "yes"):
            print("\n" + "=" * 50)
            print("Starting new export...")
            print("=" * 50 + "\n")
        else:
            print("\nGoodbye!")
            return 0


if __name__ == "__main__":
    raise SystemExit(interactive_main())
