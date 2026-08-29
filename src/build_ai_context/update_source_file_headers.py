#!/usr/bin/env python3
"""
Insert or repair repo-aware file headers for Python and common front-end source files.

Supported file types:
- Python: .py
- Front-end source: .ts, .tsx, .js, .jsx, .html, .htm

Important safety rule for JSON:
- Strict .json files are intentionally skipped because adding comments would make them
  invalid JSON and can break builds, tooling, or runtime parsing.
- If you need commented JSON-like files, use .jsonc instead (not enabled here by default).

Behavior:
- Never updates a header just to refresh the timestamp.
- If an auto-generated header already exists and its path/repo are correct, it is left unchanged.
- If an auto-generated header exists but the path/repo are wrong, the header is rebuilt and the
  timestamp is refreshed.
- Duplicate auto-generated headers are removed for every supported file type.
- Respects the repo root .gitignore so ignored files/folders are skipped.
- Safe placement:
  * Python: preserves shebang and PEP 263 encoding cookie.
  * JS/TS: preserves shebang if present.
  * HTML: preserves optional XML declaration and <!DOCTYPE ...>.
- Computes repo-relative POSIX path and repo name.
- Atomic writes and permission preservation.
- Skips common noise directories (.git, __pycache__, build, dist, venv, node_modules, etc.).

Examples:
  python update_source_file_headers.py --root . --dry-run
  python update_source_file_headers.py --root .
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

PY_HEADER_START = "# === FILE HEADER START (auto) ==="
PY_HEADER_END = "# === FILE HEADER END (auto) ==="
C_HEADER_START = "/* === FILE HEADER START (auto) ==="
C_HEADER_END = " * === FILE HEADER END (auto) ==="
HTML_HEADER_START = "<!-- === FILE HEADER START (auto) ==="
HTML_HEADER_END = "=== FILE HEADER END (auto) === -->"

HEADER_START_TOKEN = "=== FILE HEADER START (auto) ==="
HEADER_END_TOKEN = "=== FILE HEADER END (auto) ==="

CODING_RE = re.compile(r"coding[:=]\s*([-\w.]+)")
XML_DECL_RE = re.compile(r"^\s*<\?xml\b.*\?>\s*$", re.IGNORECASE)
DOCTYPE_RE = re.compile(r"^\s*<!DOCTYPE\b.*>\s*$", re.IGNORECASE)
HEADER_FIELD_RE = re.compile(
    r"^\s*(?:#|/\*|\*|<!--)?\s*(path|repo|updated)\s*:\s*(.*?)\s*(?:\*/|-->)?\s*$",
    re.IGNORECASE,
)

DEFAULT_EXCLUDES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "env",
    "build",
    "dist",
    "*.egg-info",
    "node_modules",
    ".next",
    ".nuxt",
    ".turbo",
    ".parcel-cache",
    ".cache",
    "coverage",
    ".nyc_output",
    ".idea",
    ".vscode",
}

SUPPORTED_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".kt", ".kts", ".java", ".swift", ".html", ".htm"}
SKIPPED_EXTENSIONS = {".json"}
SCAN_LIMIT_LINES = 120
MAX_HEADER_BLOCK_LINES = 20


@dataclass(frozen=True)
class HeaderBlock:
    start: int
    end: int
    fields: dict[str, str]


def find_repo_root(start: Path) -> Path:
    """Try git; else look for a .git dir; else fallback to start."""
    start = start.resolve()
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(start),
            stderr=subprocess.DEVNULL,
        )
        return Path(out.decode().strip())
    except Exception:
        cur = start
        while True:
            if (cur / ".git").is_dir():
                return cur
            if cur.parent == cur:
                return start
            cur = cur.parent


def is_excluded_dir(dirname: str, excludes: Iterable[str]) -> bool:
    if dirname in excludes:
        return True
    if dirname.endswith(".egg-info") and "*.egg-info" in excludes:
        return True
    return False


def repo_relative_path(path: Path, repo_root: Path) -> str:
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        rel = Path(path.name)
    return rel.as_posix()


def has_root_gitignore(repo_root: Path) -> bool:
    return (repo_root / ".gitignore").is_file()


def is_git_ignored(
    path: Path,
    repo_root: Path,
    gitignore_enabled: bool,
    cache: dict[str, bool],
) -> bool:
    """Respect root .gitignore by delegating matching to Git.

    Using git check-ignore keeps pattern handling correct for globs, anchored rules,
    directory rules, and negation entries. If the check cannot be performed, the path is
    treated as not ignored.
    """
    if not gitignore_enabled:
        return False

    rel = repo_relative_path(path, repo_root)
    key = rel + ("/" if path.is_dir() and not rel.endswith("/") else "")
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", "--no-index", key],
            cwd=str(repo_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        ignored = result.returncode == 0
    except Exception:
        ignored = False

    cache[key] = ignored
    return ignored


def detect_newline(text: str) -> str:
    if "\r\n" in text:
        return "\r\n"
    return "\n"


def detect_insert_at(path: Path, lines: list[str]) -> int:
    ext = path.suffix.lower()

    if ext == ".py":
        has_shebang = bool(lines and lines[0].startswith("#!"))
        enc_idx: Optional[int] = None
        for i in range(min(2, len(lines))):
            if CODING_RE.search(lines[i]):
                enc_idx = i
                break
        insert_at = 1 if has_shebang else 0
        if enc_idx is not None and enc_idx <= 1:
            insert_at = max(insert_at, enc_idx + 1)
        return insert_at

    if ext in {".js", ".jsx", ".ts", ".tsx", ".kt", ".kts", ".java", ".swift"}:
        return 1 if lines and lines[0].startswith("#!") else 0

    if ext in {".html", ".htm"}:
        idx = 0
        if idx < len(lines) and XML_DECL_RE.match(lines[idx].strip()):
            idx += 1
        if idx < len(lines) and DOCTYPE_RE.match(lines[idx].strip()):
            idx += 1
        return idx

    return 0


def build_header(path: Path, relative_posix: str, repo_name: str, newline: str) -> list[str]:
    ext = path.suffix.lower()
    timestamp = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    if ext == ".py":
        return [
            f"{PY_HEADER_START}{newline}",
            f"# path: {relative_posix}{newline}",
            f"# repo: {repo_name}{newline}",
            f"# updated: {timestamp}{newline}",
            f"{PY_HEADER_END}{newline}",
            newline,
        ]

    if ext in {".js", ".jsx", ".ts", ".tsx", ".kt", ".kts", ".java", ".swift"}:
        return [
            f"{C_HEADER_START}{newline}",
            f" * path: {relative_posix}{newline}",
            f" * repo: {repo_name}{newline}",
            f" * updated: {timestamp}{newline}",
            f"{C_HEADER_END}{newline}",
            f" */{newline}",
            newline,
        ]

    if ext in {".html", ".htm"}:
        return [
            f"{HTML_HEADER_START}{newline}",
            f"path: {relative_posix}{newline}",
            f"repo: {repo_name}{newline}",
            f"updated: {timestamp}{newline}",
            f"{HTML_HEADER_END}{newline}",
            newline,
        ]

    raise ValueError(f"Unsupported extension: {ext}")


def parse_header_fields(block_lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in block_lines:
        match = HEADER_FIELD_RE.match(line.rstrip("\r\n"))
        if match:
            key = match.group(1).lower()
            value = match.group(2).strip()
            fields[key] = value
    return fields


def find_header_blocks(lines: list[str]) -> list[HeaderBlock]:
    """Find auto-generated file header blocks near the top of the file.

    Uses token-based scanning so detection works across Python, C-style, and HTML comment forms.
    """
    blocks: list[HeaderBlock] = []
    limit = min(len(lines), SCAN_LIMIT_LINES)
    i = 0

    while i < limit:
        if HEADER_START_TOKEN not in lines[i]:
            i += 1
            continue

        end_idx: Optional[int] = None
        search_end = min(len(lines), i + MAX_HEADER_BLOCK_LINES)
        for j in range(i + 1, search_end):
            if HEADER_END_TOKEN in lines[j]:
                end_idx = j + 1
                break

        if end_idx is None:
            i += 1
            continue

        if end_idx < len(lines) and lines[end_idx].strip() == "*/":
            end_idx += 1

        if end_idx < len(lines) and lines[end_idx].strip() == "":
            end_idx += 1

        block_lines = lines[i:end_idx]
        fields = parse_header_fields(block_lines)
        blocks.append(HeaderBlock(start=i, end=end_idx, fields=fields))
        i = end_idx

    return blocks


def choose_primary_block(blocks: list[HeaderBlock], expected_start: int) -> HeaderBlock:
    for block in blocks:
        if block.start == expected_start:
            return block
    return blocks[0]


def rewrite_with_blocks(lines: list[str], blocks: list[HeaderBlock], primary: HeaderBlock, replacement: list[str]) -> list[str]:
    """Keep the primary block (replaced or preserved) and drop all duplicate blocks."""
    out: list[str] = []
    cursor = 0

    for block in sorted(blocks, key=lambda b: b.start):
        out.extend(lines[cursor:block.start])
        if block.start == primary.start and block.end == primary.end:
            out.extend(replacement)
        cursor = block.end

    out.extend(lines[cursor:])
    return out


def write_atomic(path: Path, content: str) -> None:
    st_mode = path.stat().st_mode
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=str(path.parent), delete=False) as tf:
        tf.write(content)
        temp_name = tf.name
    os.chmod(temp_name, st_mode)
    os.replace(temp_name, path)


def process_file(file_path: Path, repo_root: Path, repo_name: str, dry_run: bool) -> tuple[str, str]:
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return "skipped", f"{file_path}: non-utf8 encoding (skip)"
    except Exception as exc:
        return "error", f"{file_path}: read error: {exc}"

    ext = file_path.suffix.lower()
    if ext in SKIPPED_EXTENSIONS:
        return "skipped", f"{file_path}: strict JSON skipped to avoid breaking parse/compilation"
    if ext not in SUPPORTED_EXTENSIONS:
        return "skipped", f"{file_path}: unsupported extension"

    newline = detect_newline(text)
    lines = text.splitlines(keepends=True)
    insert_at = detect_insert_at(file_path, lines)
    rel = repo_relative_path(file_path, repo_root)

    blocks = find_header_blocks(lines)
    if blocks:
        primary = choose_primary_block(blocks, insert_at)
        path_ok = primary.fields.get("path") == rel
        repo_ok = primary.fields.get("repo") == repo_name
        duplicates = len(blocks) > 1

        if path_ok and repo_ok and not duplicates:
            return "skipped", f"{file_path}: existing header retained (path/repo already correct)"

        replacement = lines[primary.start:primary.end]
        action = "deduplicated headers"

        if not (path_ok and repo_ok):
            replacement = build_header(file_path, rel, repo_name, newline)
            action = "header repaired"
        elif duplicates:
            action = "duplicate headers removed"

        new_lines = rewrite_with_blocks(lines, blocks, primary, replacement)
        new_text = "".join(new_lines)

        if new_text == text:
            return "skipped", f"{file_path}: no effective change"

        if dry_run:
            return "updated", f"{file_path}: would be {action}"

        try:
            write_atomic(file_path, new_text)
            return "updated", f"{file_path}: {action}"
        except Exception as exc:
            return "error", f"{file_path}: write error: {exc}"

    header_lines = build_header(file_path, rel, repo_name, newline)
    new_lines = lines[:insert_at] + header_lines + lines[insert_at:]

    if dry_run:
        return "inserted", f"{file_path}: would insert header"

    try:
        write_atomic(file_path, "".join(new_lines))
        return "inserted", f"{file_path}: header inserted"
    except Exception as exc:
        return "error", f"{file_path}: write error: {exc}"


def walk_and_update(root: Path, excludes: Iterable[str], dry_run: bool) -> int:
    repo_root = find_repo_root(root)
    repo_name = repo_root.name
    gitignore_enabled = has_root_gitignore(repo_root)
    gitignore_cache: dict[str, bool] = {}
    stats = {"inserted": 0, "updated": 0, "skipped": 0, "error": 0}

    for dirpath, dirnames, filenames in os.walk(repo_root, topdown=True):
        current_dir = Path(dirpath)

        filtered_dirnames: list[str] = []
        for dirname in dirnames:
            if is_excluded_dir(dirname, excludes):
                continue

            candidate_dir = current_dir / dirname
            if is_git_ignored(candidate_dir, repo_root, gitignore_enabled, gitignore_cache):
                continue

            filtered_dirnames.append(dirname)

        dirnames[:] = filtered_dirnames

        for fn in filenames:
            path = current_dir / fn
            if is_git_ignored(path, repo_root, gitignore_enabled, gitignore_cache):
                stats["skipped"] += 1
                print(f"{path}: ignored by .gitignore")
                continue

            ext = path.suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS and ext not in SKIPPED_EXTENSIONS:
                continue

            status, message = process_file(path, repo_root, repo_name, dry_run)
            stats[status] = stats.get(status, 0) + 1
            print(message)

    print(
        f"\nSummary: inserted={stats['inserted']} updated={stats['updated']} "
        f"skipped={stats['skipped']} errors={stats['error']}"
    )
    return 1 if stats["error"] else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Insert or repair repo-aware headers in Python and FE source files."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Path inside the repo (default: current directory).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing files.",
    )
    parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Additional directory name to exclude (repeatable).",
    )
    args = parser.parse_args()

    excludes = set(DEFAULT_EXCLUDES) | set(args.exclude_dir)
    exit_code = walk_and_update(args.root, excludes, args.dry_run)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
