#!/usr/bin/env python3
"""Generate golden Export artifacts from the current Python CLI."""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT / "ide" / "testdata" / "workspaces" / "small-py"
GOLDEN = ROOT / "ide" / "testdata" / "golden" / "small-py"

TIMESTAMP_RE = re.compile(r"\d{8}T\d{6}Z")
ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:\+00:00|Z)")


def _normalize(text: str, project_root: Path) -> str:
    text = TIMESTAMP_RE.sub("TIMESTAMP", text)
    text = ISO_RE.sub("TIMESTAMP", text)
    text = text.replace(str(project_root), "PROJECT_ROOT")
    text = text.replace(project_root.as_posix(), "PROJECT_ROOT")
    return text


def _run_cli(argv: list[str]) -> int:
    from build_ai_context.cli import interactive_main

    old = sys.argv
    try:
        sys.argv = ["baic", *argv]
        return int(interactive_main())
    finally:
        sys.argv = old


def main() -> int:
    sys.path.insert(0, str(ROOT / "src"))
    GOLDEN.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        dest = tmp_path / "small-py"
        shutil.copytree(WORKSPACE, dest, ignore=shutil.ignore_patterns(".DS_Store"))
        old_cwd = Path.cwd()
        import os

        os.chdir(tmp_path)
        try:
            code = _run_cli([str(dest), "--all"])
        finally:
            os.chdir(old_cwd)
        if code != 0:
            print(f"export failed: {code}", file=sys.stderr)
            return code

        export_dirs = sorted(tmp_path.glob("exported_sources_small-py_*"))
        if not export_dirs:
            export_dirs = sorted(dest.glob("exported_sources_small-py_*"))
        if not export_dirs:
            export_dirs = sorted(Path.cwd().glob("exported_sources_small-py_*"))
        if not export_dirs:
            print("no export directory found", file=sys.stderr)
            return 1
        export_dir = export_dirs[-1]

        for path in sorted(export_dir.iterdir()):
            if path.is_file():
                stable = TIMESTAMP_RE.sub("TIMESTAMP", path.name)
                out = GOLDEN / stable
                out.write_text(_normalize(path.read_text(encoding="utf-8"), dest), encoding="utf-8")
                if stable.endswith("_bundle_001_TIMESTAMP.txt"):
                    (GOLDEN / "bundle.txt").write_text(out.read_text(encoding="utf-8"), encoding="utf-8")
                if "_manifest_" in stable:
                    (GOLDEN / "manifest.json").write_text(out.read_text(encoding="utf-8"), encoding="utf-8")

        code = _run_cli(["--tree", str(dest)])
        if code != 0:
            print(f"tree failed: {code}", file=sys.stderr)
            return code
        code = _run_cli(["--graph", "--format", "txt", str(dest)])
        if code != 0:
            print(f"graph txt failed: {code}", file=sys.stderr)
            return code
        code = _run_cli(["--graph", "--format", "json", str(dest)])
        if code != 0:
            print(f"graph json failed: {code}", file=sys.stderr)
            return code

        for path in dest.glob("*_file_tree_*.txt"):
            (GOLDEN / "filetree.txt").write_text(
                _normalize(path.read_text(encoding="utf-8"), dest), encoding="utf-8"
            )
        for path in dest.glob("*_code_graph_*.txt"):
            (GOLDEN / "graph.txt").write_text(
                _normalize(path.read_text(encoding="utf-8"), dest), encoding="utf-8"
            )
        for path in dest.glob("*_code_graph_*.json"):
            (GOLDEN / "graph.json").write_text(
                _normalize(path.read_text(encoding="utf-8"), dest), encoding="utf-8"
            )

        index = {
            "files": sorted(p.name for p in GOLDEN.iterdir() if p.is_file()),
        }
        (GOLDEN / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")

    print(f"wrote goldens to {GOLDEN}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
