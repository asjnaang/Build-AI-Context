"""Tests for code-graph generation (catalog + imports)."""

from pathlib import Path

from build_ai_context.graph import generate_graph
from build_ai_context.models import SourceFile


def _source(tmp_path: Path, rel: str, content: str, category: str) -> SourceFile:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    lines = content.splitlines()
    return SourceFile(
        abs_path=path,
        rel_path=Path(rel),
        category=category,
        line_count=len(lines),
        size_bytes=path.stat().st_size,
        sha256="test",
        lines=lines,
    )


class TestGraphCatalog:
    def test_graph_catalog_lists_python_functions_and_classes(self, tmp_path):
        """Agents need top-level defs and methods, not a raw syntax tree."""
        src = _source(
            tmp_path,
            "app.py",
            (
                "class Greeter:\n"
                "    def hello(self):\n"
                "        return 1\n"
                "\n"
                "def main():\n"
                "    pass\n"
            ),
            "python",
        )

        text = generate_graph([src], tmp_path)

        assert "catalog:" in text
        assert "app.py:" in text
        assert "class: Greeter @" in text
        assert "fn: main @" in text
        assert "method: Greeter.hello @" in text


class TestGraphImports:
    def test_python_local_import_resolves_to_file(self, tmp_path):
        """Resolved file edges are what agents actually follow."""
        pkg = tmp_path / "pkg"
        exporter = _source(tmp_path, "pkg/exporter.py", "def write():\n    pass\n", "python")
        cli = _source(
            tmp_path,
            "pkg/cli.py",
            "from pkg.exporter import write\nfrom pathlib import Path\n",
            "python",
        )

        text = generate_graph([cli, exporter], tmp_path)

        assert "pkg/cli.py --> pkg/exporter.py," in text
        assert "pkg/cli.py --> pathlib," in text

    def test_python_relative_import_resolves(self, tmp_path):
        _source(tmp_path, "pkg/__init__.py", "", "python")
        foo = _source(tmp_path, "pkg/foo.py", "X = 1\n", "python")
        bar = _source(tmp_path, "pkg/bar.py", "from .foo import X\n", "python")

        text = generate_graph([foo, bar], tmp_path)

        assert "pkg/bar.py --> pkg/foo.py," in text

    def test_skips_future_import(self, tmp_path):
        src = _source(
            tmp_path,
            "mod.py",
            "from __future__ import annotations\nimport os\n",
            "python",
        )
        text = generate_graph([src], tmp_path)
        assert "__future__" not in text
        assert "mod.py --> os," in text


class TestGraphOtherLanguages:
    def test_typescript_imports_and_functions(self, tmp_path):
        util = _source(tmp_path, "src/util.ts", "export const n = 1;\n", "typescript")
        app = _source(
            tmp_path,
            "src/app.ts",
            (
                "import { n } from './util';\n"
                "export function run(): void {}\n"
                "export class Svc {}\n"
            ),
            "typescript",
        )

        text = generate_graph([app, util], tmp_path)

        assert "fn: run @" in text
        assert "class: Svc @" in text
        assert "src/app.ts --> src/util.ts," in text

    def test_js_relative_import_prefers_same_language(self, tmp_path):
        """./util from TS must not land on a sibling util.py."""
        py_util = _source(tmp_path, "src/util.py", "def n():\n    return 1\n", "python")
        ts_util = _source(tmp_path, "src/util.ts", "export const n = 1;\n", "typescript")
        app = _source(tmp_path, "src/app.ts", "import { n } from './util';\n", "typescript")

        text = generate_graph([py_util, ts_util, app], tmp_path)

        assert "src/app.ts --> src/util.ts," in text
        assert "src/app.ts --> src/util.py," not in text

    def test_kotlin_catalog_and_imports(self, tmp_path):
        helper = _source(
            tmp_path,
            "app/src/main/java/com/example/Helper.kt",
            "package com.example\nclass Helper\n",
            "java_kotlin",
        )
        main = _source(
            tmp_path,
            "app/src/main/java/com/example/MainActivity.kt",
            (
                "package com.example\n"
                "import com.example.Helper\n"
                "import android.os.Bundle\n"
                "class MainActivity {\n"
                "    fun onCreate() {}\n"
                "}\n"
                "fun helper() {}\n"
            ),
            "java_kotlin",
        )

        text = generate_graph([main, helper], tmp_path)

        assert "class: MainActivity @" in text
        assert "method: MainActivity.onCreate @" in text
        assert "fn: helper @" in text
        assert "MainActivity.kt --> " in text
        assert "com.example.Helper" in text or "Helper.kt" in text
        assert "android.os.Bundle" in text

    def test_swift_catalog_and_imports(self, tmp_path):
        src = _source(
            tmp_path,
            "App/ContentView.swift",
            (
                "import SwiftUI\n"
                "struct ContentView {\n"
                "    func body() {}\n"
                "}\n"
                "func start() {}\n"
            ),
            "ios_apple",
        )

        text = generate_graph([src], tmp_path)

        assert "struct: ContentView @" in text
        assert "fn: start @" in text
        assert "App/ContentView.swift --> SwiftUI," in text


class TestGraphFormat:
    def test_headers_and_trailing_commas(self, tmp_path):
        src = _source(tmp_path, "app.py", "def main():\n    pass\n", "python")
        readme = _source(tmp_path, "README.md", "# hi\n", "config_docs")

        text = generate_graph([src, readme], tmp_path)

        assert f"root: {tmp_path.name}" in text
        assert "file_count: 2" in text
        assert "parsed: 1" in text
        assert "skipped: 1" in text
        assert "languages: python=1" in text
        assert "engine: ast" in text
        assert "fn: main @" in text
        assert "README.md" not in text.split("catalog:")[1]

    def test_no_icons_or_box_drawing(self, tmp_path):
        src = _source(tmp_path, "app.py", "def main():\n    pass\n", "python")
        text = generate_graph([src], tmp_path)
        for token in ("🐍", "├──", "└──", "│"):
            assert token not in text


class TestGraphCli:
    def test_graph_flag_writes_file_and_exits(self, tmp_path):
        (tmp_path / "app.py").write_text("def hello():\n    return 1\n")
        from build_ai_context.cli import build_parser, run_quick_artifacts

        args = build_parser().parse_args(["--graph", str(tmp_path)])
        rc = run_quick_artifacts(args)

        assert rc == 0
        graphs = list(tmp_path.glob("*_code_graph_*.txt"))
        assert len(graphs) == 1
        content = graphs[0].read_text()
        assert "fn: hello @" in content
        assert list(tmp_path.glob("*_file_tree_*.txt")) == []

    def test_tree_and_graph_write_both(self, tmp_path):
        (tmp_path / "app.py").write_text("def hello():\n    return 1\n")
        from build_ai_context.cli import build_parser, run_quick_artifacts

        args = build_parser().parse_args(["--tree", "--graph", str(tmp_path)])
        rc = run_quick_artifacts(args)

        assert rc == 0
        assert list(tmp_path.glob("*_code_graph_*.txt"))
        assert list(tmp_path.glob("*_file_tree_*.txt"))

    def test_gitignore_gets_graph_pattern(self, tmp_path):
        (tmp_path / "app.py").write_text("def hello():\n    return 1\n")
        from build_ai_context.cli import build_parser, run_quick_artifacts

        args = build_parser().parse_args(["--graph", str(tmp_path)])
        assert run_quick_artifacts(args) == 0

        gitignore = (tmp_path / ".gitignore").read_text()
        assert "*_code_graph_*.txt" in gitignore


class TestGraphJson:
    def test_json_format_is_parseable_and_has_same_facts(self, tmp_path):
        """JSON is for tools; same catalog + imports, not a second invented graph."""
        import json

        src = _source(
            tmp_path,
            "app.py",
            "class Greeter:\n    def hello(self):\n        return 1\n\ndef main():\n    pass\n",
            "python",
        )

        raw = generate_graph([src], tmp_path, output_format="json")
        data = json.loads(raw)

        assert data["root"] == tmp_path.name
        assert data["file_count"] == 1
        assert data["parsed"] == 1
        names = {(s["kind"], s["name"]) for f in data["catalog"] for s in f["symbols"]}
        assert ("class", "Greeter") in names
        assert ("fn", "main") in names
        assert ("method", "Greeter.hello") in names

    def test_default_format_is_txt_not_json(self, tmp_path):
        src = _source(tmp_path, "app.py", "def main():\n    pass\n", "python")
        text = generate_graph([src], tmp_path)
        assert text.lstrip().startswith("root:")
        assert not text.lstrip().startswith("{")

    def test_invalid_format_raises(self, tmp_path):
        src = _source(tmp_path, "app.py", "def main():\n    pass\n", "python")
        try:
            generate_graph([src], tmp_path, output_format="yaml")
        except ValueError as exc:
            assert "json" in str(exc) and "txt" in str(exc)
        else:
            raise AssertionError("expected ValueError for unknown format")


class TestGraphRankAndLines:
    def test_catalog_puts_imported_hubs_first(self, tmp_path):
        """Aider-style PageRank: files many others import should lead the catalog."""
        hub = _source(tmp_path, "hub.py", "def core():\n    return 1\n", "python")
        leaf_a = _source(tmp_path, "aaa.py", "from hub import core\ndef a():\n    pass\n", "python")
        leaf_b = _source(tmp_path, "bbb.py", "from hub import core\ndef b():\n    pass\n", "python")

        text = generate_graph([leaf_a, leaf_b, hub], tmp_path)
        catalog = text.split("catalog:")[1].split("imports:")[0]
        assert catalog.find("hub.py:") < catalog.find("aaa.py:")
        assert "rank:" in catalog

    def test_symbols_include_definition_line(self, tmp_path):
        src = _source(
            tmp_path,
            "app.py",
            "class Greeter:\n    def hello(self):\n        return 1\n\ndef main():\n    pass\n",
            "python",
        )
        text = generate_graph([src], tmp_path)
        assert "class: Greeter @1," in text
        assert "fn: main @5," in text
        assert "method: Greeter.hello @2," in text


class TestGraphCliFormat:
    def test_format_json_writes_json_file(self, tmp_path):
        import json

        (tmp_path / "app.py").write_text("def hello():\n    return 1\n")
        from build_ai_context.cli import build_parser, run_quick_artifacts

        args = build_parser().parse_args(["--graph", "--format", "json", str(tmp_path)])
        assert run_quick_artifacts(args) == 0

        graphs = list(tmp_path.glob("*_code_graph_*.json"))
        assert len(graphs) == 1
        data = json.loads(graphs[0].read_text())
        assert data["catalog"]
        assert list(tmp_path.glob("*_code_graph_*.txt")) == []

    def test_format_default_stays_txt(self, tmp_path):
        (tmp_path / "app.py").write_text("def hello():\n    return 1\n")
        from build_ai_context.cli import build_parser, run_quick_artifacts

        args = build_parser().parse_args(["--graph", str(tmp_path)])
        assert run_quick_artifacts(args) == 0
        assert list(tmp_path.glob("*_code_graph_*.txt"))
        assert list(tmp_path.glob("*_code_graph_*.json")) == []

    def test_gitignore_covers_json_graphs(self, tmp_path):
        (tmp_path / "app.py").write_text("def hello():\n    return 1\n")
        from build_ai_context.cli import build_parser, run_quick_artifacts

        args = build_parser().parse_args(["--graph", "--format", "json", str(tmp_path)])
        assert run_quick_artifacts(args) == 0
        gitignore = (tmp_path / ".gitignore").read_text()
        assert "*_code_graph_*.json" in gitignore
