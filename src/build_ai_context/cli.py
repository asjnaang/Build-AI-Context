"""
Command-line interface for build_ai_context package.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Sequence

from build_ai_context import __version__
from build_ai_context.cli_ui import (
    interactive_select_files,
    prompt_yes_no,
    render_category_table,
    render_folder_table,
)
from build_ai_context.constants import (
    CATEGORY_DESCRIPTIONS,
    DEFAULT_MAX_LINES,
    extract_timestamp_from_dir_name,
    generate_timestamp,
)
from build_ai_context.exporter import CodeExporter
from build_ai_context.models import SourceFile


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
        "--tree",
        action="store_true",
        help="Generate only a filetree in the current directory and exit.",
    )
    parser.add_argument(
        "--redact",
        action="store_true",
        default=False,
        help="Redact secrets and tokens from the output (default: disabled).",
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

    # Handle --tree: just generate a filetree in the current directory
    if args.tree:
        return run_tree_only(args)

    result, _, _ = run_exporter(args, None)
    return result


def run_tree_only(args) -> int:
    """Generate only a filetree in the current directory."""
    exporter = CodeExporter()

    try:
        root = Path(args.project_root).expanduser().resolve()
        if not root.exists():
            print(f"Error: Project root does not exist: {root}", file=sys.stderr)
            return 1
        if not root.is_dir():
            print(f"Error: Project root is not a directory: {root}", file=sys.stderr)
            return 1

        exporter.print_info(f"Scanning project: {root}")

        # Scan files
        all_files, skipped_reasons = exporter.scan_supported_files(root, skip_secret_files=True)
        if not all_files:
            exporter.print_warning("No supported files found.")
            return 1

        exporter.print_info(f"Detected {len(all_files)} supported file(s).")

        # Generate filetree
        filetree_content = exporter.generate_filetree(all_files, root)
        timestamp = generate_timestamp()
        folder_name = root.name.replace(" ", "_")
        filetree_name = f"{folder_name}_file_tree_{timestamp}.txt"
        filetree_path = root / filetree_name
        filetree_path.write_text(filetree_content, encoding="utf-8")
        exporter.update_gitignore(root, filetree_name)

        exporter.print_success(f"\nFiletree created: {filetree_path}")
        return 0

    except Exception as exc:
        exporter.print_error(f"Unexpected error: {exc}")
        return 1


def run_exporter(args, exporter, pre_scanned=None) -> int:
    """Run the exporter with given arguments."""
    if exporter is None:
        exporter = CodeExporter(redact=getattr(args, "redact", False))

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

        if pre_scanned:
            all_files, skipped_reasons = pre_scanned
        else:
            exporter.print_info(f"Scanning project: {root}")
            all_files, skipped_reasons = exporter.scan_supported_files(
                root, skip_secret_files=skip_secret_files
            )

        if not all_files:
            exporter.print_warning(
                "No supported files were found after applying .gitignore and default exclusions."
            )
            return 0, None, None

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
                    return 0, all_files, skipped_reasons
            else:
                path_inputs = args.paths
                if args.paths and len(args.paths) == 1:
                    path_inputs = exporter.parse_intelligent_input(args.paths[0], all_files, root)
                    if not path_inputs:
                        path_inputs = args.paths
                selected_files, selection_metadata = exporter.non_interactive_select_files(
                    all_files,
                    categories=args.categories,
                    path_prefixes=path_inputs,
                    root=root,
                )
        else:
            render_category_table(exporter, all_files)
            render_folder_table(exporter, all_files)
            selected_files, selection_metadata = interactive_select_files(exporter, all_files, root)

        if not selected_files:
            exporter.print_warning("No files selected. Nothing was exported.")
            return 0, None, None

        exporter.print_info(
            f"Selected {len(selected_files)} file(s) out of {len(all_files)} supported file(s)."
        )

        chunks, skipped_during_split = exporter.split_into_chunks(selected_files, args.max_lines)
        bundles, skipped_during_pack = exporter.pack_chunks(chunks, args.max_lines)
        skipped_during_processing = skipped_during_split + skipped_during_pack

        output_dir = (
            Path(args.output_dir).expanduser().resolve()
            if args.output_dir
            else Path.cwd() / exporter.sanitize_output_dir_name(root)
        )

        # Extract timestamp from output_dir name for consistency
        dir_name = output_dir.name
        timestamp = extract_timestamp_from_dir_name(dir_name)

        # Always generate filetree from ALL files - AI needs full project view
        output_dir.mkdir(parents=True, exist_ok=True)
        filetree_content = exporter.generate_filetree(all_files, root)
        folder_name = root.name.replace(" ", "_")
        filetree_name = f"{folder_name}_file_tree_{timestamp}.txt"
        filetree_path = output_dir / filetree_name
        filetree_path.write_text(filetree_content, encoding="utf-8")
        exporter.update_gitignore(root, filetree_name)
        exporter.print_success(f"Filetree created  : {filetree_path}")

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
            filetree_name=filetree_name,
            timestamp=timestamp,
        )

        overview_path = None
        if args.project_overview:
            overview_path = exporter.write_project_overview(
                root=root,
                all_files=all_files,
                selected_files=selected_files,
                output_dir=output_dir,
                selection_metadata=selection_metadata,
                manifest_name=manifest_path.name,
            )

        exporter.print_success("\nExport complete.")
        exporter.print_success(f"Output directory : {output_dir}")
        exporter.print_success(f"Manifest         : {manifest_path}")
        if overview_path is not None:
            exporter.print_success(f"Project overview : {overview_path}")
        exporter.print_success(f"Filetree         : {filetree_path}")
        exporter.print_success(f"Bundles created  : {len(bundles)}")
        exporter.print_success(f"Files exported   : {len(selected_files)}")

        if skipped_during_processing:
            exporter.print_warning("\nFiles/chunks skipped during processing:")
            for entry in skipped_during_processing:
                exporter.print_warning(f"  - {entry}")

        if not args.non_interactive and not args.non_interactive:
            print(
                f"\nTip: Upload the bundle(s) and {manifest_path.name} to your AI "
                "assistant for best results."
            )

        return 0, all_files, skipped_reasons

    except Exception as exc:
        exporter.print_error(f"Unexpected error: {exc}")
        import traceback

        traceback.print_exc()
        return 1, None, None


def interactive_main() -> int:
    """Main entry point for interactive mode with loop."""
    parser = build_parser()
    args = parser.parse_args()

    # Handle --tree: just generate a filetree in the current directory
    if args.tree:
        return run_tree_only(args)

    exporter = CodeExporter(redact=getattr(args, "redact", False))

    pre_scanned = None

    while True:
        result, all_files, skipped_reasons = run_exporter(args, exporter, pre_scanned)

        if result != 0:
            return result

        if args.non_interactive:
            return 0

        if all_files:
            pre_scanned = (all_files, skipped_reasons)

        user_input = input("Do you want to export more files? [Y/n]: ")

        if user_input.strip().lower() in ("", "y", "yes"):
            print("\n" + "=" * 50)
            print("Starting new export (using cached scan)...")
            print("=" * 50 + "\n")
        else:
            print("\nGoodbye!")
            return 0


if __name__ == "__main__":
    raise SystemExit(interactive_main())
