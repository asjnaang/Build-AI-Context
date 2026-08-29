# Plan: 4 Tasks Implementation — Status

## Task 1: Interactive file deselection for all non-"all" selection modes
- `_display_files_for_deselection()` in `cli_ui.py` implemented and used by modes 2, 3, 4, and 5 fallback
- Mode 5 uses questionary checkbox when available
- Mode 1 ("all") skips as required
- **🔧 Fixed**: keyword mode metadata (`selection_mode`, `name_filters`) now correctly set even when questionary is used
- **Status: ✅ done**

## Task 2: Add prompt.md and include it in bundles
- `PROMPT_MD_LINES` and `get_prompt_md_content()` in `writing.py` defines the prompt
- `prompt.md` is written as standalone file in output dir
- `prompt.md` is prepended to every bundle
- User is shown tip to replace `<tasks_contract>` after export
- **Status: ✅ done**

## Task 3: Stop bundling file tree in generated files
- Filetree is NOT bundled into any bundle file in `writing.py`
- Filetree is only written as a separate `*_file_tree_*.txt` file
- Users can generate it standalone via `baic --tree`
- **Status: ✅ done**

## Task 4: Add --update-headers CLI command
- `--update-headers` flag defined in argparse (`cli.py`)
- `walk_and_update` imported and called in `run_update_headers()`
- Handled before tree/export in both `main()` and `interactive_main()`
- **🔧 Fixed**: `run_update_headers` now passes `DEFAULT_EXCLUDES` (was empty set)
- **🔧 Extended**: Added `.kt`, `.kts`, `.java`, `.swift` support to header updater
- **Status: ✅ done**
