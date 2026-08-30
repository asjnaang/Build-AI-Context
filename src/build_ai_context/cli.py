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
    select_oversized_files_for_inclusion,
)
from build_ai_context.constants import (
    CATEGORY_DESCRIPTIONS,
    DEFAULT_MAX_LINES,
    LARGE_FILE_SKIP_LINES,
    extract_timestamp_from_dir_name,
    generate_timestamp,
)
from build_ai_context.exporter import CodeExporter
from build_ai_context.models import SourceFile
from build_ai_context.update_source_file_headers import DEFAULT_EXCLUDES, walk_and_update


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
    # Bundle packing size is fixed at DEFAULT_MAX_LINES (8000). Only the per-source
    # file inclusion threshold is CLI-overridable.
    parser.add_argument(
        "--max-file-lines",
        type=int,
        default=LARGE_FILE_SKIP_LINES,
        metavar="N",
        help=(
            f"Skip individual repo source files with >= N lines when bundling "
            f"(default: {LARGE_FILE_SKIP_LINES}). Use 0 to include any size "
            f"(large files are still split across fixed {DEFAULT_MAX_LINES}-line bundles)."
        ),
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
        "--all",
        dest="non_interactive",
        action="store_true",
        help="Export all supported files without prompts.",
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
        "--graph",
        action="store_true",
        help="Generate only a code graph (catalog + imports) and exit. "
        "Combine with --tree to write both artifacts.",
    )
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=["txt", "json"],
        default="txt",
        help="Graph output format (default: txt). Used with --graph.",
    )
    parser.add_argument(
        "--redact",
        action="store_true",
        default=False,
        help="Redact secrets and tokens from the output (default: disabled).",
    )
    parser.add_argument(
        "--update-headers",
        action="store_true",
        help="Run the update-source-file-headers script to tag all project files with metadata headers.",
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

    # Handle --update-headers
    if args.update_headers:
        return run_update_headers(args)

    if args.tree or args.graph:
        return run_quick_artifacts(args)

    result, _, _ = run_exporter(args, None)
    return result


def run_update_headers(args) -> int:
    """Run the update-source-file-headers script."""
    root = Path(args.project_root).expanduser().resolve()
    if not root.exists():
        print(f"Error: Project root does not exist: {root}", file=sys.stderr)
        return 1
    if not root.is_dir():
        print(f"Error: Project root is not a directory: {root}", file=sys.stderr)
        return 1
    return walk_and_update(root, set(DEFAULT_EXCLUDES), False)


def run_tree_only(args) -> int:
    """Generate only a filetree. Kept as an alias of run_quick_artifacts."""
    return run_quick_artifacts(args)


def run_quick_artifacts(args) -> int:
    """Write --tree and/or --graph artifacts after a single scan, then exit."""
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

        all_files, _skipped_reasons = exporter.scan_supported_files(root, skip_secret_files=True)
        if not all_files:
            exporter.print_warning("No supported files found.")
            return 1

        exporter.print_info(f"Detected {len(all_files)} supported file(s).")

        timestamp = generate_timestamp()
        folder_name = root.name.replace(" ", "_")
        wrote_any = False

        if getattr(args, "tree", False):
            filetree_content = exporter.generate_filetree(all_files, root)
            filetree_name = f"{folder_name}_file_tree_{timestamp}.txt"
            filetree_path = root / filetree_name
            filetree_path.write_text(filetree_content, encoding="utf-8")
            exporter.update_gitignore(root, filetree_name)
            exporter.print_success(f"\nFiletree created: {filetree_path}")
            wrote_any = True

        if getattr(args, "graph", False):
            output_format = getattr(args, "output_format", "txt") or "txt"
            graph_content = exporter.generate_graph(
                all_files, root, output_format=output_format
            )
            ext = "json" if output_format == "json" else "txt"
            graph_name = f"{folder_name}_code_graph_{timestamp}.{ext}"
            graph_path = root / graph_name
            graph_path.write_text(graph_content, encoding="utf-8")
            exporter.update_gitignore(root, graph_name)
            exporter.print_success(f"Code graph created: {graph_path}")
            wrote_any = True

        return 0 if wrote_any else 1

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
            return 1, None, None
        if not root.is_dir():
            print(f"Error: Project root is not a directory: {root}", file=sys.stderr)
            return 1, None, None

        if args.max_file_lines < 0:
            print("Error: --max-file-lines must be >= 0 (0 = unlimited)", file=sys.stderr)
            return 1, None, None

        # Output bundle size is intentionally fixed; only source-file limit is overridable.
        bundle_max_lines = DEFAULT_MAX_LINES

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

        chunks, split_items = exporter.split_into_chunks(
            selected_files,
            bundle_max_lines,
            max_file_lines=args.max_file_lines,
        )
        warnings = [item for item in split_items if item.get("reason") == "large_file_warning"]
        skipped_during_split = [
            item for item in split_items if item.get("reason") != "large_file_warning"
        ]
        if not args.non_interactive:
            forced_files = select_oversized_files_for_inclusion(
                selected_files, skipped_during_split, exporter
            )
            if forced_files:
                forced_paths = {source.rel_path.as_posix() for source in forced_files}
                forced_chunks, forced_items = exporter.split_into_chunks(
                    forced_files, bundle_max_lines, max_file_lines=0
                )
                chunks.extend(forced_chunks)
                warnings.extend(
                    item for item in forced_items if item.get("reason") == "large_file_warning"
                )
                skipped_during_split = [
                    item for item in skipped_during_split if item.get("path") not in forced_paths
                ]
        bundles, skipped_during_pack = exporter.pack_chunks(chunks, bundle_max_lines)
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
        exporter.update_gitignore(root, filetree_name)

        manifest_path = exporter.write_bundles_and_manifest(
            root=root,
            selected_files=selected_files,
            bundles=bundles,
            output_dir=output_dir,
            max_lines=bundle_max_lines,
            max_file_lines=args.max_file_lines,
            skipped_reasons=skipped_reasons,
            selection_metadata=selection_metadata,
            skip_secret_files=skip_secret_files,
            skipped_during_pack=skipped_during_processing,
            warnings=warnings,
            filetree_name=filetree_name,
            filetree_content=filetree_content,
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
        exporter.print_success(f"Bundles created  : {len(bundles)}")
        exporter.print_success(f"Files exported   : {len(selected_files)}")

        if warnings:
            exporter.print_warning("\nFiles included with warnings:")
            for entry in warnings:
                exporter.print_warning(f"  - {entry}")
        if skipped_during_processing:
            exporter.print_warning("\nFiles/chunks excluded during processing:")
            for entry in skipped_during_processing:
                exporter.print_warning(f"  - {entry}")

        if not args.non_interactive and not args.non_interactive:
            print(
                f"\n📝 Open 'prompt.md' in the output directory and replace the task description "
                f"(under ## Task Contract) with your specific feature request or question or changes needed.\n"
                f"Then upload all bundle files along with prompt.md and ask your AI assistant address the promt.md "
                f"for best results.\n\n"
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

    # Handle --update-headers
    if args.update_headers:
        return run_update_headers(args)

    if args.tree or args.graph:
        return run_quick_artifacts(args)

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
