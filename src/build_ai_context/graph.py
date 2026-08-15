"""Code-graph generation for AI-agent context.

Serpentine-shaped output (catalog + imports) built with stdlib ast for
Python and tree-sitter when installed. Heuristics cover the same
languages if tree-sitter is missing so --graph still works on 3.9.
"""

from __future__ import annotations

import ast
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from build_ai_context.models import SourceFile

GRAPHABLE_EXTENSIONS: Set[str] = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".java",
    ".kt",
    ".kts",
    ".swift",
    ".dart",
}

_SKIP_DUNDER = re.compile(r"^__\w+__$")

_JS_INDEX_NAMES = (
    "index.ts",
    "index.tsx",
    "index.js",
    "index.jsx",
    "index.mjs",
    "index.cjs",
)
_JS_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")


@dataclass
class Symbol:
    kind: str
    name: str
    line: Optional[int] = None


@dataclass
class FileFacts:
    path: str
    symbols: List[Symbol] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    engine: str = "skip"
    error: Optional[str] = None


def generate_graph(
    files: Sequence[SourceFile], root: Path, output_format: str = "txt"
) -> str:
    """Generate a catalog + imports graph that AI agents can parse."""
    fmt = (output_format or "txt").strip().lower()
    if fmt not in {"txt", "json"}:
        raise ValueError("output_format must be 'txt' or 'json'")

    graphable = [f for f in files if f.rel_path.suffix.lower() in GRAPHABLE_EXTENSIONS]
    skipped = len(files) - len(graphable)
    facts: List[FileFacts] = []
    engines: Set[str] = set()
    lang_counts: Dict[str, int] = defaultdict(int)
    parsed = 0

    for source in graphable:
        item = extract_file(source)
        facts.append(item)
        lang_counts[_language_label(source)] += 1
        if item.error:
            continue
        parsed += 1
        engines.add(item.engine)

    all_paths = [f.rel_path.as_posix() for f in files]
    path_set = set(all_paths)
    import_rows = _collect_imports(facts, path_set)
    ranks = _pagerank(
        [item.path for item in facts],
        [(src, dst) for src, dst, resolved in import_rows if resolved],
    )
    catalog_items = [item for item in facts if item.symbols]
    catalog_items.sort(key=lambda item: (-ranks.get(item.path, 0.0), item.path))

    if fmt == "json":
        return _format_json(
            root=root,
            files=files,
            parsed=parsed,
            skipped=skipped,
            engines=engines,
            lang_counts=lang_counts,
            catalog_items=catalog_items,
            ranks=ranks,
            import_rows=import_rows,
        )
    return _format_txt(
        root=root,
        files=files,
        parsed=parsed,
        skipped=skipped,
        engines=engines,
        lang_counts=lang_counts,
        catalog_items=catalog_items,
        ranks=ranks,
        import_rows=import_rows,
    )


def extract_file(source: SourceFile) -> FileFacts:
    """Extract symbols and imports from one source file."""
    suffix = source.rel_path.suffix.lower()
    path = source.rel_path.as_posix()
    text = "\n".join(source.lines)
    try:
        if suffix == ".py":
            return _extract_python(path, text)
        ts_facts = _extract_treesitter(path, suffix, text)
        if ts_facts is not None:
            return ts_facts
        return _extract_heuristic(path, suffix, text)
    except SyntaxError as exc:
        return FileFacts(path=path, engine="error", error=str(exc))
    except Exception as exc:  # pragma: no cover - defensive
        return FileFacts(path=path, engine="error", error=str(exc))


def _extract_python(path: str, text: str) -> FileFacts:
    tree = ast.parse(text)
    symbols: List[Symbol] = []
    imports: List[str] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            symbols.append(Symbol("class", node.name, node.lineno))
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if _keep_func_name(child.name):
                        symbols.append(Symbol("method", f"{node.name}.{child.name}", child.lineno))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _keep_func_name(node.name):
                symbols.append(Symbol("fn", node.name, node.lineno))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name and alias.name != "__future__":
                    imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                continue
            if node.level:
                dots = "." * node.level
                module = node.module or ""
                imports.append(f"{dots}{module}" if module else dots)
            elif node.module:
                imports.append(node.module)

    return FileFacts(path=path, symbols=symbols, imports=_unique(imports), engine="ast")


def _extract_treesitter(path: str, suffix: str, text: str) -> Optional[FileFacts]:
    parser, _lang = _treesitter_parser(suffix)
    if parser is None:
        return None
    tree = parser.parse(text.encode("utf-8", errors="replace"))
    src = text.encode("utf-8", errors="replace")
    symbols: List[Symbol] = []
    imports: List[str] = []
    _walk_treesitter(tree.root_node, src, symbols, imports, parent_class=None)
    if suffix in {".kt", ".kts"}:
        _merge_kotlin_object_interface(text, symbols)
    return FileFacts(
        path=path,
        symbols=_dedupe_symbols(symbols),
        imports=_unique(imports),
        engine="tree-sitter",
    )


def _treesitter_parser(suffix: str):
    try:
        from tree_sitter_language_pack import get_parser
    except ImportError:
        return None, None
    lang_map = {
        ".js": "javascript",
        ".jsx": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".kt": "kotlin",
        ".kts": "kotlin",
        ".swift": "swift",
        ".java": "java",
        ".dart": "dart",
    }
    lang = lang_map.get(suffix)
    if not lang:
        return None, None
    try:
        return get_parser(lang), lang
    except Exception:
        return None, None


def _walk_treesitter(node, src: bytes, symbols: List[Symbol], imports: List[str], parent_class: Optional[str]) -> None:
    ntype = node.type

    if ntype in {"import_statement", "import_from_statement", "import_header", "import_declaration", "import_or_export"}:
        target = _import_target_from_node(node, src)
        if target:
            imports.append(target)
    elif ntype == "export_statement":
        target = _js_export_from_target(node, src)
        if target:
            imports.append(target)
    elif ntype == "call_expression" and _is_require_call(node, src):
        target = _require_target(node, src)
        if target:
            imports.append(target)

    kind = _symbol_kind_for_node(node, src)
    name = None
    if kind:
        name = _first_identifier(node, src)
        if name and _keep_func_name(name):
            line = node.start_point[0] + 1
            if kind == "fn" and parent_class:
                symbols.append(Symbol("method", f"{parent_class}.{name}", line))
            elif kind == "method" and parent_class:
                symbols.append(Symbol("method", f"{parent_class}.{name}", line))
            else:
                symbols.append(Symbol(kind, name, line))

    next_parent = parent_class
    if kind in {"class", "struct", "enum", "interface", "protocol", "object", "actor"} and name:
        next_parent = name

    # Dart splits function_signature / function_body; still walk children.
    for child in node.children:
        _walk_treesitter(child, src, symbols, imports, next_parent)


def _symbol_kind_for_node(node, src: bytes) -> Optional[str]:
    ntype = node.type
    mapping = {
        "function_definition": "fn",
        "function_declaration": "fn",
        "async_function_definition": "fn",
        "function_signature": "fn",
        "method_declaration": "method",
        "method_definition": "method",
        "class_definition": "class",
        "interface_declaration": "interface",
        "type_alias_declaration": "type",
        "protocol_declaration": "protocol",
        "enum_declaration": "enum",
        "object_declaration": "object",
        "actor_declaration": "actor",
        "struct_declaration": "struct",
    }
    if ntype in mapping:
        return mapping[ntype]
    if ntype == "class_declaration":
        keyword = _declaration_keyword(node, src)
        if keyword in {"struct", "enum", "actor", "interface"}:
            return keyword
        return "class"
    if ntype == "lexical_declaration":
        # const foo = () => {}
        if _lexical_is_function(node):
            return "fn"
    return None


def _declaration_keyword(node, src: bytes) -> Optional[str]:
    for child in node.children:
        text = _node_text(child, src)
        if text in {"class", "struct", "enum", "actor", "interface", "data"}:
            return text
    return None


def _lexical_is_function(node) -> bool:
    for child in node.children:
        if child.type == "variable_declarator":
            for inner in child.children:
                if inner.type in {"arrow_function", "function", "function_expression"}:
                    return True
    return False


def _first_identifier(node, src: bytes) -> Optional[str]:
    preferred = {
        "identifier",
        "type_identifier",
        "simple_identifier",
        "name",
        "property_identifier",
    }
    for child in node.children:
        if child.type in preferred:
            text = _node_text(child, src)
            if text and text not in {"export", "default", "async", "public", "private"}:
                return text
    # const foo = () =>  — name is inside variable_declarator
    for child in node.children:
        if child.type in {"variable_declarator", "lexical_declaration"}:
            found = _first_identifier(child, src)
            if found:
                return found
    return None


def _import_target_from_node(node, src: bytes) -> Optional[str]:
    ntype = node.type
    if ntype in {"import_header", "import_declaration"}:
        ident = _named_child_text(node, src, {"identifier", "scoped_identifier", "dotted_name"})
        if ident:
            return ident
        return _strip_import_keyword(_node_text(node, src))
    if ntype == "import_or_export":
        return _first_string_literal(node, src)
    if ntype in {"import_statement", "import_from_statement"}:
        string = _first_string_literal(node, src)
        if string:
            return string
        return None
    return None


def _js_export_from_target(node, src: bytes) -> Optional[str]:
    # export { z } from './z'
    return _first_string_literal(node, src)


def _is_require_call(node, src: bytes) -> bool:
    if not node.children:
        return False
    first = node.children[0]
    return first.type == "identifier" and _node_text(first, src) == "require"


def _require_target(node, src: bytes) -> Optional[str]:
    return _first_string_literal(node, src)


def _first_string_literal(node, src: bytes) -> Optional[str]:
    if node.type in {"string", "string_literal", "uri", "configurable_uri"}:
        text = _node_text(node, src).strip()
        return _unquote(text)
    for child in node.children:
        found = _first_string_literal(child, src)
        if found:
            return found
    return None


def _named_child_text(node, src: bytes, types: Set[str]) -> Optional[str]:
    for child in node.children:
        if child.type in types:
            return _node_text(child, src)
    return None


def _node_text(node, src: bytes) -> str:
    return src[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _strip_import_keyword(text: str) -> Optional[str]:
    cleaned = text.strip()
    cleaned = re.sub(r"^import\s+", "", cleaned)
    cleaned = cleaned.rstrip(";").strip()
    cleaned = cleaned.split(" as ")[0].strip()
    return cleaned or None


def _unquote(text: str) -> str:
    if len(text) >= 2 and text[0] in {"'", '"', "`"} and text[-1] == text[0]:
        return text[1:-1]
    return text


def _merge_kotlin_object_interface(text: str, symbols: List[Symbol]) -> None:
    existing = {s.name for s in symbols}
    for match in re.finditer(r"\b(?:object|interface)\s+([A-Za-z_][\w]*)", text):
        name = match.group(1)
        kind = "object" if match.group(0).startswith("object") else "interface"
        if name not in existing:
            symbols.append(Symbol(kind, name, text.count("\n", 0, match.start()) + 1))
            existing.add(name)


def _extract_heuristic(path: str, suffix: str, text: str) -> FileFacts:
    symbols: List[Symbol] = []
    imports: List[str] = []
    if suffix in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}:
        imports.extend(_heuristic_js_imports(text))
        symbols.extend(_heuristic_js_symbols(text))
    elif suffix in {".kt", ".kts"}:
        imports.extend(_heuristic_import_lines(text, r"^import\s+([^\s;]+)"))
        symbols.extend(_heuristic_kotlin_symbols(text))
    elif suffix == ".swift":
        imports.extend(_heuristic_import_lines(text, r"^import\s+([A-Za-z_][\w.]*)"))
        symbols.extend(_heuristic_swift_symbols(text))
    elif suffix == ".java":
        imports.extend(_heuristic_import_lines(text, r"^import\s+(?:static\s+)?([^\s;]+)"))
        symbols.extend(_heuristic_java_symbols(text))
    elif suffix == ".dart":
        imports.extend(_heuristic_import_lines(text, r"""^import\s+['"]([^'"]+)['"]"""))
        symbols.extend(_heuristic_dart_symbols(text))
    return FileFacts(
        path=path,
        symbols=_dedupe_symbols(symbols),
        imports=_unique(imports),
        engine="heuristic",
    )


def _heuristic_js_imports(text: str) -> List[str]:
    found: List[str] = []
    for match in re.finditer(
        r"""(?:import|export)\s+(?:type\s+)?(?:[^'"\n]+?\s+from\s+)?['"]([^'"]+)['"]""",
        text,
    ):
        found.append(match.group(1))
    for match in re.finditer(r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""", text):
        found.append(match.group(1))
    return found


def _heuristic_js_symbols(text: str) -> List[Symbol]:
    symbols: List[Symbol] = []
    for match in re.finditer(
        r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)",
        text,
        re.MULTILINE,
    ):
        symbols.append(Symbol("fn", match.group(1), _line_at(text, match.start())))
    for match in re.finditer(
        r"^\s*(?:export\s+)?(?:default\s+)?class\s+([A-Za-z_$][\w$]*)",
        text,
        re.MULTILINE,
    ):
        symbols.append(Symbol("class", match.group(1), _line_at(text, match.start())))
    for match in re.finditer(
        r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>",
        text,
        re.MULTILINE,
    ):
        symbols.append(Symbol("fn", match.group(1), _line_at(text, match.start())))
    for match in re.finditer(r"^\s*(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)", text, re.MULTILINE):
        symbols.append(Symbol("interface", match.group(1), _line_at(text, match.start())))
    for match in re.finditer(r"^\s*(?:export\s+)?type\s+([A-Za-z_$][\w$]*)\s*=", text, re.MULTILINE):
        symbols.append(Symbol("type", match.group(1), _line_at(text, match.start())))
    return symbols


def _heuristic_import_lines(text: str, pattern: str) -> List[str]:
    return [m.group(1).rstrip(";") for m in re.finditer(pattern, text, re.MULTILINE)]


def _heuristic_kotlin_symbols(text: str) -> List[Symbol]:
    symbols: List[Symbol] = []
    current_class: Optional[str] = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        class_match = re.match(
            r"(?:(?:public|private|internal|protected|open|data|sealed|abstract)\s+)*"
            r"(class|object|interface|enum\s+class)\s+([A-Za-z_][\w]*)",
            line,
        )
        if class_match:
            kind = "enum" if "enum" in class_match.group(1) else class_match.group(1)
            current_class = class_match.group(2)
            symbols.append(Symbol(kind, current_class, lineno))
            continue
        fn_match = re.match(r"(?:(?:public|private|internal|protected|override|suspend)\s+)*fun\s+([A-Za-z_][\w]*)\s*\(", line)
        if fn_match:
            name = fn_match.group(1)
            if current_class:
                symbols.append(Symbol("method", f"{current_class}.{name}", lineno))
            else:
                symbols.append(Symbol("fn", name, lineno))
    return symbols


def _heuristic_swift_symbols(text: str) -> List[Symbol]:
    symbols: List[Symbol] = []
    current: Optional[Tuple[str, str]] = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        type_match = re.match(
            r"(?:(?:public|private|internal|open|final|fileprivate)\s+)*"
            r"(class|struct|enum|protocol|actor)\s+([A-Za-z_][\w]*)",
            line,
        )
        if type_match:
            current = (type_match.group(1), type_match.group(2))
            symbols.append(Symbol(current[0], current[1], lineno))
            continue
        fn_match = re.match(
            r"(?:(?:public|private|internal|open|override|static|mutating)\s+)*func\s+([A-Za-z_][\w]*)\s*\(",
            line,
        )
        if fn_match:
            name = fn_match.group(1)
            if current and current[0] != "protocol":
                symbols.append(Symbol("method", f"{current[1]}.{name}", lineno))
            else:
                symbols.append(Symbol("fn", name, lineno))
    return symbols


def _heuristic_java_symbols(text: str) -> List[Symbol]:
    symbols: List[Symbol] = []
    current: Optional[str] = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        type_match = re.match(
            r"(?:(?:public|private|protected|abstract|final|static)\s+)*"
            r"(class|interface|enum)\s+([A-Za-z_][\w]*)",
            line,
        )
        if type_match:
            current = type_match.group(2)
            symbols.append(Symbol(type_match.group(1), current, lineno))
            continue
        method_match = re.match(
            r"(?:(?:public|private|protected|static|final|synchronized|abstract)\s+)+"
            r"(?:[\w.<>,\[\]?]+\s+)+([A-Za-z_][\w]*)\s*\(",
            line,
        )
        if method_match and current and method_match.group(1) not in {current, "if", "for", "while", "switch"}:
            symbols.append(Symbol("method", f"{current}.{method_match.group(1)}", lineno))
    return symbols


def _heuristic_dart_symbols(text: str) -> List[Symbol]:
    symbols: List[Symbol] = []
    for match in re.finditer(r"^\s*(?:class|mixin)\s+([A-Za-z_][\w]*)", text, re.MULTILINE):
        symbols.append(Symbol("class", match.group(1), _line_at(text, match.start())))
    for match in re.finditer(
        r"^\s*(?:[A-Za-z_][\w<>,\s?]*\s+)?([A-Za-z_][\w]*)\s*\([^;]*\)\s*(?:async\s*)?\{",
        text,
        re.MULTILINE,
    ):
        name = match.group(1)
        if name not in {"if", "for", "while", "switch", "catch"}:
            # class constructors share the class name; skip those already added
            if any(s.name == name and s.kind == "class" for s in symbols):
                continue
            symbols.append(Symbol("fn", name, _line_at(text, match.start())))
    return symbols


def _line_at(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _collect_imports(
    facts: Sequence[FileFacts], path_set: Set[str]
) -> List[Tuple[str, str, bool]]:
    rows: List[Tuple[str, str, bool]] = []
    for item in sorted(facts, key=lambda f: f.path):
        for raw in item.imports:
            resolved = resolve_import(item.path, raw, path_set)
            rows.append((item.path, resolved or raw, resolved is not None))
    return rows


def _pagerank(
    nodes: Sequence[str], edges: Sequence[Tuple[str, str]], damping: float = 0.85, rounds: int = 20
) -> Dict[str, float]:
    """PageRank on local file-to-file import edges (Aider-style importance)."""
    unique = list(dict.fromkeys(nodes))
    if not unique:
        return {}
    n = len(unique)
    node_set = set(unique)
    incoming: Dict[str, List[str]] = defaultdict(list)
    outdeg: Dict[str, int] = defaultdict(int)
    for src, dst in edges:
        if src in node_set and dst in node_set and src != dst:
            incoming[dst].append(src)
            outdeg[src] += 1
    rank = {node: 1.0 / n for node in unique}
    for _ in range(rounds):
        dangling = sum(rank[node] for node in unique if outdeg[node] == 0)
        nxt: Dict[str, float] = {}
        for node in unique:
            inbound = sum(rank[src] / outdeg[src] for src in incoming[node])
            nxt[node] = (1.0 - damping) / n + damping * (inbound + dangling / n)
        rank = nxt
    return rank


def _format_txt(
    root: Path,
    files: Sequence[SourceFile],
    parsed: int,
    skipped: int,
    engines: Iterable[str],
    lang_counts: Dict[str, int],
    catalog_items: Sequence[FileFacts],
    ranks: Dict[str, float],
    import_rows: Sequence[Tuple[str, str, bool]],
) -> str:
    lines: List[str] = [
        f"root: {root.name}",
        f"file_count: {len(files)}",
        f"parsed: {parsed}",
        f"skipped: {skipped}",
        f"engine: {_format_engines(engines)}",
        f"languages: {_format_languages(lang_counts)}",
        "",
        "catalog:",
    ]
    for item in catalog_items:
        lines.append(f"{item.path}:")
        lines.append(f"  rank: {ranks.get(item.path, 0.0):.4f},")
        for symbol in item.symbols:
            lines.append(f"  {_format_symbol_line(symbol)}")
    lines.extend(["", "imports:"])
    for src, dest, _resolved in import_rows:
        lines.append(f"{src} --> {dest},")
    return "\n".join(lines)


def _format_json(
    root: Path,
    files: Sequence[SourceFile],
    parsed: int,
    skipped: int,
    engines: Iterable[str],
    lang_counts: Dict[str, int],
    catalog_items: Sequence[FileFacts],
    ranks: Dict[str, float],
    import_rows: Sequence[Tuple[str, str, bool]],
) -> str:
    payload = {
        "root": root.name,
        "file_count": len(files),
        "parsed": parsed,
        "skipped": skipped,
        "engine": _format_engines(engines),
        "languages": dict(sorted(lang_counts.items())),
        "catalog": [
            {
                "path": item.path,
                "rank": round(ranks.get(item.path, 0.0), 6),
                "symbols": [
                    {
                        "kind": symbol.kind,
                        "name": symbol.name,
                        **({"line": symbol.line} if symbol.line else {}),
                    }
                    for symbol in item.symbols
                ],
            }
            for item in catalog_items
        ],
        "imports": [{"from": src, "to": dest} for src, dest, _resolved in import_rows],
    }
    return json.dumps(payload, indent=2) + "\n"


def _format_symbol_line(symbol: Symbol) -> str:
    if symbol.line:
        return f"{symbol.kind}: {symbol.name} @{symbol.line},"
    return f"{symbol.kind}: {symbol.name},"


def resolve_import(from_path: str, spec: str, path_set: Set[str]) -> Optional[str]:
    """Best-effort resolve of an import spec onto a scanned project file."""
    if not spec or spec == "__future__":
        return None
    if spec.startswith("."):
        return _resolve_relative(from_path, spec, path_set)
    if "/" in spec or spec.endswith(_JS_SUFFIXES + (".dart", ".kt", ".swift", ".java")):
        return _resolve_pathish(from_path, spec, path_set)
    dotted = _resolve_dotted(from_path, spec, path_set)
    if dotted:
        return dotted
    return _resolve_basename(spec, path_set)


def _resolve_relative(from_path: str, spec: str, path_set: Set[str]) -> Optional[str]:
    # Python: .foo / ..pkg.sub   JS: ./foo / ../bar
    origin = Path(from_path).parent
    if spec.startswith("./") or spec.startswith("../"):
        candidate = (origin / spec).as_posix()
        return _match_existing(candidate, path_set, from_path)
    # Python dotted relative
    dots = len(spec) - len(spec.lstrip("."))
    remainder = spec[dots:]
    dest = origin
    for _ in range(dots - 1):
        dest = dest.parent
    if remainder:
        dest = dest / remainder.replace(".", "/")
    return _match_existing(dest.as_posix(), path_set, from_path)


def _resolve_pathish(from_path: str, spec: str, path_set: Set[str]) -> Optional[str]:
    if spec.startswith("package:"):
        return None
    origin = Path(from_path).parent
    candidate = (origin / spec).as_posix() if not spec.startswith("/") else spec.lstrip("/")
    return _match_existing(candidate, path_set, from_path)


def _resolve_dotted(from_path: str, spec: str, path_set: Set[str]) -> Optional[str]:
    cleaned = spec.rstrip(".*")
    rel = cleaned.replace(".", "/")
    return _match_existing(rel, path_set, from_path)


def _resolve_basename(spec: str, path_set: Set[str]) -> Optional[str]:
    name = spec.rsplit(".", 1)[-1]
    matches = [p for p in path_set if Path(p).stem == name]
    if len(matches) == 1:
        return matches[0]
    return None


def _match_existing(candidate: str, path_set: Set[str], from_path: str = "") -> Optional[str]:
    normalized = _normalize_rel(candidate)
    if normalized in path_set:
        return normalized
    for suffix in _suffixes_for(from_path):
        with_suffix = _normalize_rel(normalized + suffix)
        if with_suffix in path_set:
            return with_suffix
    if Path(from_path).suffix.lower() == ".py" or not from_path:
        init_py = _normalize_rel(normalized + "/__init__.py")
        if init_py in path_set:
            return init_py
    if Path(from_path).suffix.lower() in _JS_SUFFIXES or not from_path:
        for index in _JS_INDEX_NAMES:
            indexed = _normalize_rel(f"{normalized}/{index}")
            if indexed in path_set:
                return indexed
    return None


def _suffixes_for(from_path: str) -> Tuple[str, ...]:
    ext = Path(from_path).suffix.lower()
    families = {
        ".py": (".py",),
        ".js": _JS_SUFFIXES,
        ".jsx": _JS_SUFFIXES,
        ".mjs": _JS_SUFFIXES,
        ".cjs": _JS_SUFFIXES,
        ".ts": _JS_SUFFIXES,
        ".tsx": _JS_SUFFIXES,
        ".kt": (".kt", ".kts", ".java"),
        ".kts": (".kt", ".kts", ".java"),
        ".java": (".java", ".kt", ".kts"),
        ".swift": (".swift",),
        ".dart": (".dart",),
    }
    preferred = families.get(ext, ())
    fallback = (".py",) + _JS_SUFFIXES + (".kt", ".kts", ".swift", ".java", ".dart")
    seen: Set[str] = set()
    ordered: List[str] = []
    for suffix in preferred + fallback:
        if suffix not in seen:
            seen.add(suffix)
            ordered.append(suffix)
    return tuple(ordered)


def _normalize_rel(path: str) -> str:
    parts: List[str] = []
    for part in path.replace("\\", "/").split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def _language_label(source: SourceFile) -> str:
    suffix = source.rel_path.suffix.lower()
    mapping = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".kt": "kotlin",
        ".kts": "kotlin",
        ".java": "java",
        ".swift": "swift",
        ".dart": "dart",
    }
    return mapping.get(suffix, source.category)


def _format_engines(engines: Iterable[str]) -> str:
    ordered = [name for name in ("ast", "tree-sitter", "heuristic") if name in set(engines)]
    return ", ".join(ordered) if ordered else "none"


def _format_languages(counts: Dict[str, int]) -> str:
    if not counts:
        return "-"
    return ", ".join(f"{name}={counts[name]}" for name in sorted(counts))


def _keep_func_name(name: str) -> bool:
    if name == "__init__":
        return True
    return not _SKIP_DUNDER.match(name)


def _unique(values: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _dedupe_symbols(symbols: Sequence[Symbol]) -> List[Symbol]:
    seen: Set[Tuple[str, str]] = set()
    out: List[Symbol] = []
    for symbol in symbols:
        key = (symbol.kind, symbol.name)
        if key in seen:
            continue
        seen.add(key)
        out.append(symbol)
    return out
