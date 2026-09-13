"""
File scanning, detection, and selection for build_ai_context.
"""

from __future__ import annotations

import fnmatch
import hashlib
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pathspec

from build_ai_context.constants import (
    CATEGORY_ALIASES,
    CATEGORY_DESCRIPTIONS,
    CATEGORY_EXTENSIONS,
    DEFAULT_EXCLUDED_DIRS,
    DEFAULT_EXCLUDED_PREFIXES,
    DEFAULT_SECRET_PATTERNS,
    DEFAULT_TEXT_ENCODING,
    EXTRA_EXCLUDED_PATTERNS,
    SPECIAL_FILENAMES,
)
from build_ai_context.models import SourceFile


# ---------------------------------------------------------------------------
# .gitignore and path filtering
# ---------------------------------------------------------------------------


def _read_gitignore_lines(gitignore_path: Path) -> List[str]:
    """Read one .gitignore without letting an encoding issue disable filtering."""
    if not gitignore_path.is_file():
        return []
    try:
        return gitignore_path.read_text(encoding=DEFAULT_TEXT_ENCODING).splitlines()
    except UnicodeDecodeError:
        return gitignore_path.read_text(errors="ignore").splitlines()


def _rebase_gitignore_lines(lines: Sequence[str], base: Path) -> List[str]:
    """Rebase patterns from a nested .gitignore to the scan root."""
    if not base.parts:
        return list(lines)
    prefix = base.as_posix().rstrip("/")
    rebased: List[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            rebased.append(line)
            continue
        negated = line.startswith("!")
        pattern = line[1:] if negated else line
        escaped_prefix = "!" if negated else ""
        if pattern.startswith("/"):
            rebased.append(f"{escaped_prefix}{prefix}/{pattern.lstrip('/')}")
        elif "/" in pattern.rstrip("/"):
            rebased.append(f"{escaped_prefix}{prefix}/{pattern}")
        else:
            rebased.append(f"{escaped_prefix}{prefix}/{pattern}")
            rebased.append(f"{escaped_prefix}{prefix}/**/{pattern}")
    return rebased


def load_gitignore_spec(root: Path) -> pathspec.PathSpec:
    """Load .gitignore patterns from the project root."""
    return pathspec.PathSpec.from_lines(
        "gitwildmatch", _read_gitignore_lines(root / ".gitignore")
    )


def path_matches_any_pattern(rel_path: str, patterns: Iterable[str]) -> bool:
    """Check if a path matches any of the given patterns."""
    return any(
        fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(Path(rel_path).name, pattern)
        for pattern in patterns
    )


def should_skip_by_dir(rel_path: Path) -> bool:
    """Check if a path should be skipped based on directory name."""
    return any(part in DEFAULT_EXCLUDED_DIRS for part in rel_path.parts)


def should_skip_by_prefix(rel_path: Path) -> bool:
    """Check if a path should be skipped based on directory prefix."""
    rel_str = rel_path.as_posix()
    return any(rel_str.startswith(prefix) for prefix in DEFAULT_EXCLUDED_PREFIXES)


def is_ignored(
    rel_path: Path, gitignore_spec: pathspec.PathSpec, skip_secret_files: bool
) -> Tuple[bool, str]:
    """Check if a file should be ignored and return the reason."""
    rel_str = rel_path.as_posix()
    if should_skip_by_dir(rel_path):
        return True, "default_excluded_dir"
    if should_skip_by_prefix(rel_path):
        return True, "default_excluded_prefix"
    if gitignore_spec.match_file(rel_str):
        return True, ".gitignore"
    if path_matches_any_pattern(rel_str, EXTRA_EXCLUDED_PATTERNS):
        return True, "extra_excluded_pattern"
    if skip_secret_files and path_matches_any_pattern(rel_str, DEFAULT_SECRET_PATTERNS):
        return True, "secret_like_file"
    return False, ""


# ---------------------------------------------------------------------------
# File detection and reading
# ---------------------------------------------------------------------------


def detect_category(path: Path) -> Optional[str]:
    """Detect the category of a file based on its name and extension."""
    name = path.name
    suffix = path.suffix.lower()
    if name in SPECIAL_FILENAMES:
        if name in {"Podfile", ".swiftlint.yml"}:
            return "ios_apple"
        if name in {
            "AndroidManifest.xml",
            "gradle.properties",
            "settings.gradle",
            "settings.gradle.kts",
            "build.gradle",
            "build.gradle.kts",
        }:
            return "java_kotlin"
        return "config_docs"
    for category, extensions in CATEGORY_EXTENSIONS.items():
        if suffix in extensions:
            return category
    return None


def is_probably_binary(path: Path) -> bool:
    """Check if a file is likely binary by reading a sample."""
    try:
        with path.open("rb") as fh:
            sample = fh.read(4096)
        return b"\x00" in sample
    except OSError:
        return True


def read_text_lines(path: Path) -> List[str]:
    """Read a text file with multiple encoding attempts."""
    encodings = ["utf-8", "utf-8-sig", "latin-1"]
    last_error: Optional[Exception] = None
    for encoding in encodings:
        try:
            return path.read_text(encoding=encoding).splitlines()
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error is not None:
        return path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return []


def sha256_of_lines(lines: Sequence[str]) -> str:
    """Calculate SHA256 hash of file lines."""
    joined = "\n".join(lines).encode("utf-8", errors="ignore")
    return hashlib.sha256(joined).hexdigest()


def scan_supported_files(
    root: Path, skip_secret_files: bool
) -> Tuple[List[SourceFile], Dict[str, int]]:
    """Scan supported files while pruning ignored directories before descent."""
    discovered: List[SourceFile] = []
    skipped_reasons: Dict[str, int] = defaultdict(int)
    inherited_patterns: Dict[Path, List[str]] = {
        root: _read_gitignore_lines(root / ".gitignore")
    }

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        current_dir = Path(dirpath)
        current_rel = current_dir.relative_to(root)
        gitignore_lines = list(inherited_patterns.pop(current_dir, []))
        if current_rel.parts:
            gitignore_lines.extend(
                _rebase_gitignore_lines(
                    _read_gitignore_lines(current_dir / ".gitignore"), current_rel
                )
            )
        gitignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", gitignore_lines)

        kept_dirs: List[str] = []
        for dirname in dirnames:
            rel_dir = current_rel / dirname
            ignored, reason = is_ignored(rel_dir, gitignore_spec, skip_secret_files)
            if ignored:
                skipped_reasons[reason] += 1
            else:
                kept_dirs.append(dirname)
                inherited_patterns[current_dir / dirname] = gitignore_lines
        dirnames[:] = kept_dirs

        for filename in filenames:
            path = current_dir / filename
            rel_path = current_rel / filename
            ignored, reason = is_ignored(rel_path, gitignore_spec, skip_secret_files)
            if ignored:
                skipped_reasons[reason] += 1
                continue
            category = detect_category(path)
            if not category:
                skipped_reasons["unsupported_type"] += 1
                continue
            if is_probably_binary(path):
                skipped_reasons["binary"] += 1
                continue
            try:
                lines = read_text_lines(path)
                size_bytes = path.stat().st_size
            except OSError:
                skipped_reasons["read_error"] += 1
                continue
            discovered.append(
                SourceFile(
                    abs_path=path.resolve(),
                    rel_path=rel_path,
                    category=category,
                    line_count=len(lines),
                    size_bytes=size_bytes,
                    sha256=sha256_of_lines(lines),
                    lines=lines,
                )
            )
    discovered.sort(key=lambda item: item.rel_path.as_posix())
    return discovered, dict(sorted(skipped_reasons.items()))

# ---------------------------------------------------------------------------
# Selection helpers
# ---------------------------------------------------------------------------


def summarize_by_category(files: Sequence[SourceFile]) -> Dict[str, Dict[str, int]]:
    """Summarize files by category."""
    summary: Dict[str, Dict[str, int]] = defaultdict(lambda: {"files": 0, "lines": 0, "bytes": 0})
    for item in files:
        summary[item.category]["files"] += 1
        summary[item.category]["lines"] += item.line_count
        summary[item.category]["bytes"] += item.size_bytes
    return dict(summary)


def summarize_top_folders(
    files: Sequence[SourceFile], max_depth: int = 2
) -> Dict[str, Dict[str, int]]:
    """Summarize files by top-level folders."""
    summary: Dict[str, Dict[str, int]] = defaultdict(lambda: {"files": 0, "lines": 0})
    for item in files:
        parts = item.rel_path.parts[:max_depth]
        folder = "/".join(parts[:-1]) if len(parts) > 1 else "."
        summary[folder]["files"] += 1
        summary[folder]["lines"] += item.line_count
    return dict(sorted(summary.items(), key=lambda pair: (-pair[1]["files"], pair[0])))


def normalize_categories(values: Sequence[str]) -> List[str]:
    """Normalize category names using aliases."""
    normalized: List[str] = []
    for value in values:
        key = value.strip().lower()
        if not key:
            continue
        mapped = CATEGORY_ALIASES.get(key, key)
        if mapped in CATEGORY_DESCRIPTIONS and mapped not in normalized:
            normalized.append(mapped)
    return normalized


def parse_csv_input(raw: str) -> List[str]:
    """Parse comma-separated input into a list of strings."""
    return [token.strip() for token in raw.split(",") if token.strip()]


def _resolve_selection_token(
    token: str, all_path_strs: set[str], all_names: set[str], root: Path
) -> List[str]:
    """Resolve one selection token without broad substring matching."""
    candidate = token.strip()
    if not candidate:
        return []
    if Path(candidate).is_absolute():
        try:
            candidate = Path(candidate).resolve().relative_to(root).as_posix()
        except ValueError:
            return []
    if candidate in all_path_strs:
        return [candidate]
    if candidate in all_names:
        return sorted(
            path for path in all_path_strs
            if path == candidate or path.endswith("/" + candidate)
        )
    suffix_matches = sorted(
        path for path in all_path_strs if path.endswith("/" + candidate)
    )
    if suffix_matches:
        return suffix_matches
    directory_prefix = candidate.rstrip("/") + "/"
    return sorted(path for path in all_path_strs if path.startswith(directory_prefix))


def parse_intelligent_input(raw: str, files: Sequence[SourceFile], root: Path) -> List[str]:
    """Parse line-, comma-, semicolon-, or legacy space-separated path input."""
    if not raw.strip():
        return []

    all_path_strs = {f.rel_path.as_posix() for f in files}
    all_names = {f.rel_path.name for f in files}
    found_paths: List[str] = []

    def add_matches(token: str) -> bool:
        matches = _resolve_selection_token(token, all_path_strs, all_names, root)
        for match in matches:
            if match not in found_paths:
                found_paths.append(match)
        return bool(matches)

    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if add_matches(line.rstrip(",;").strip()):
            continue

        separator_parts = [
            part.strip() for part in re.split(r"[,;]+", line) if part.strip()
        ]
        if len(separator_parts) > 1:
            for part in separator_parts:
                add_matches(part)
            continue

        # Backward compatibility for inputs such as "main.py utils.py". Only
        # accept whitespace splitting when every token independently resolves.
        whitespace_parts = line.split()
        if len(whitespace_parts) > 1:
            resolved = [
                _resolve_selection_token(part, all_path_strs, all_names, root)
                for part in whitespace_parts
            ]
            if all(resolved):
                for matches in resolved:
                    for match in matches:
                        if match not in found_paths:
                            found_paths.append(match)

    return found_paths


# ---------------------------------------------------------------------------
# Non-interactive selection
# ---------------------------------------------------------------------------


def filter_files_by_paths(
    files: Sequence[SourceFile],
    root: Path,
    raw_paths: Sequence[str],
) -> Tuple[List[SourceFile], List[str], List[str]]:
    """Filter files by path patterns."""
    normalized_paths = _normalize_selection_paths(raw_paths, root)
    if not normalized_paths:
        return list(files), [], []

    matched: List[SourceFile] = []
    missing_inputs: List[str] = []

    for raw_input, normalized in zip(raw_paths, normalized_paths):
        raw_candidate = Path(raw_input).expanduser()
        abs_candidate = (
            raw_candidate.resolve()
            if raw_candidate.is_absolute()
            else (root / raw_candidate).resolve()
        )
        raw_name = raw_candidate.name
        looks_like_file_name_only = (
            not raw_candidate.is_absolute() and "/" not in raw_input and "\\" not in raw_input
        )

        exact_matches = [
            item
            for item in files
            if item.rel_path.as_posix() == normalized
            or item.rel_path.as_posix().startswith(normalized.rstrip("/") + "/")
            or item.abs_path.resolve() == abs_candidate
        ]

        if exact_matches:
            for item in exact_matches:
                if item not in matched:
                    matched.append(item)
            continue

        if looks_like_file_name_only:
            basename_matches = [item for item in files if item.rel_path.name == raw_name]
            if basename_matches:
                for item in basename_matches:
                    if item not in matched:
                        matched.append(item)
                continue

        missing_inputs.append(raw_input)

    matched.sort(key=lambda item: item.rel_path.as_posix())
    return matched, normalized_paths, missing_inputs


def _normalize_selection_paths(raw_paths: Sequence[str], root: Path) -> List[str]:
    """Normalize path selections."""
    normalized: List[str] = []
    for raw in raw_paths:
        value = raw.strip()
        if not value:
            continue
        candidate = Path(value).expanduser()
        if candidate.is_absolute():
            try:
                rel = candidate.resolve().relative_to(root)
                value = rel.as_posix()
            except Exception:
                value = candidate.resolve().as_posix()
        else:
            value = value.rstrip("/")
        if value not in normalized:
            normalized.append(value)
    return normalized


def filter_files_by_keywords(
    files: Sequence[SourceFile], keywords: Sequence[str]
) -> Tuple[List[SourceFile], List[str]]:
    """Filter files by keywords found in their content."""
    matched: List[SourceFile] = []
    matched_keywords: List[str] = []
    keywords_lower = [k.lower() for k in keywords]

    for item in files:
        content_lower = "\n".join(item.lines).lower()
        found_keywords = [kw for kw in keywords_lower if kw in content_lower]
        if found_keywords:
            matched.append(item)
            for kw in found_keywords:
                if kw not in matched_keywords:
                    matched_keywords.append(kw)

    matched.sort(key=lambda item: item.rel_path.as_posix())
    return matched, sorted(matched_keywords)


def non_interactive_select_files(
    all_files: Sequence[SourceFile],
    categories: Sequence[str],
    path_prefixes: Sequence[str],
    root: Path,
) -> Tuple[List[SourceFile], Dict[str, object]]:
    """Select files non-interactively based on categories and paths."""
    selected = list(all_files)
    if categories:
        normalized_categories = normalize_categories(categories)
        invalid = [
            item
            for item in categories
            if CATEGORY_ALIASES.get(item.strip().lower(), item.strip().lower())
            not in CATEGORY_DESCRIPTIONS
        ]
        if invalid:
            raise ValueError(f"Unsupported categories requested: {', '.join(invalid)}")
        selected = [item for item in selected if item.category in normalized_categories]
        categories = normalized_categories
    else:
        categories = []
    missing_paths: List[str] = []
    normalized_paths: List[str] = []
    if path_prefixes:
        selected, normalized_paths, missing_paths = filter_files_by_paths(
            selected, root, path_prefixes
        )
    selected.sort(key=lambda item: item.rel_path.as_posix())
    return selected, {
        "selection_mode": "non_interactive",
        "selected_categories": list(categories),
        "selected_paths": normalized_paths,
        "name_filters": [],
        "missing_paths": missing_paths,
    }
