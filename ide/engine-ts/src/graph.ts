import { basename, extname } from "node:path";
import type { SourceFile } from "./types.ts";

const GRAPHABLE = new Set([
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
]);
const SKIP_DUNDER = /^__\w+__$/;
const JS_INDEX = ["index.ts", "index.tsx", "index.js", "index.jsx", "index.mjs", "index.cjs"];
const JS_SUFFIXES = [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"];

interface Symbol {
  kind: string;
  name: string;
  line?: number;
}

interface FileFacts {
  path: string;
  symbols: Symbol[];
  imports: string[];
  engine: string;
  error?: string;
}

function unique(values: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const value of values) {
    if (value && !seen.has(value)) {
      seen.add(value);
      out.push(value);
    }
  }
  return out;
}

function dedupeSymbols(symbols: Symbol[]): Symbol[] {
  const seen = new Set<string>();
  const out: Symbol[] = [];
  for (const s of symbols) {
    const key = `${s.kind}:${s.name}`;
    if (!seen.has(key)) {
      seen.add(key);
      out.push(s);
    }
  }
  return out;
}

function keepFuncName(name: string): boolean {
  if (name === "__init__") return true;
  return !SKIP_DUNDER.test(name);
}

function lineAt(text: string, index: number): number {
  return (text.slice(0, index).match(/\n/g) ?? []).length + 1;
}

function extractPython(path: string, text: string): FileFacts {
  const symbols: Symbol[] = [];
  const imports: string[] = [];
  const lines = text.split(/\n/);
  let i = 0;
  while (i < lines.length) {
    const raw = lines[i];
    const indent = raw.length - raw.trimStart().length;
    if (indent !== 0 || !raw.trim() || raw.trimStart().startsWith("#")) {
      i += 1;
      continue;
    }
    const classMatch = raw.match(/^class\s+(\w+)/);
    const asyncFn = raw.match(/^async\s+def\s+(\w+)/);
    const fnMatch = raw.match(/^def\s+(\w+)/);
    const importMatch = raw.match(/^import\s+(.+)$/);
    const fromMatch = raw.match(/^from\s+(\S+)\s+import\b/);
    if (classMatch) {
      const className = classMatch[1];
      symbols.push({ kind: "class", name: className, line: i + 1 });
      i += 1;
      while (i < lines.length) {
        const child = lines[i];
        if (!child.trim()) {
          i += 1;
          continue;
        }
        const childIndent = child.length - child.trimStart().length;
        if (childIndent <= indent) break;
        const method = child.trim().match(/^(?:async\s+)?def\s+(\w+)/);
        if (method && childIndent > indent && keepFuncName(method[1])) {
          symbols.push({ kind: "method", name: `${className}.${method[1]}`, line: i + 1 });
        }
        i += 1;
      }
      continue;
    }
    if (asyncFn || fnMatch) {
      const name = (asyncFn ?? fnMatch)![1];
      if (keepFuncName(name)) symbols.push({ kind: "fn", name, line: i + 1 });
      i += 1;
      continue;
    }
    if (importMatch) {
      for (const part of importMatch[1].split(",")) {
        const name = part.trim().split(/\s+as\s+/)[0].trim();
        if (name && name !== "__future__") imports.push(name);
      }
      i += 1;
      continue;
    }
    if (fromMatch) {
      const spec = fromMatch[1];
      if (spec !== "__future__") imports.push(spec);
      i += 1;
      continue;
    }
    i += 1;
  }
  return { path, symbols, imports: unique(imports), engine: "ast" };
}

function heuristicJsImports(text: string): string[] {
  const found: string[] = [];
  const fromRe =
    /(?:import|export)\s+(?:type\s+)?(?:[^'"\n]+?\s+from\s+)?['"]([^'"]+)['"]/g;
  const reqRe = /require\s*\(\s*['"]([^'"]+)['"]\s*\)/g;
  let m: RegExpExecArray | null;
  while ((m = fromRe.exec(text))) found.push(m[1]);
  while ((m = reqRe.exec(text))) found.push(m[1]);
  return found;
}

function heuristicJsSymbols(text: string): Symbol[] {
  const symbols: Symbol[] = [];
  const add = (re: RegExp, kind: string) => {
    re.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(text))) symbols.push({ kind, name: m[1], line: lineAt(text, m.index) });
  };
  add(/^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)/gm, "fn");
  add(/^\s*(?:export\s+)?(?:default\s+)?class\s+([A-Za-z_$][\w$]*)/gm, "class");
  add(
    /^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>/gm,
    "fn",
  );
  add(/^\s*(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)/gm, "interface");
  add(/^\s*(?:export\s+)?type\s+([A-Za-z_$][\w$]*)\s*=/gm, "type");
  return symbols;
}

function heuristicImportLines(text: string, pattern: RegExp): string[] {
  const found: string[] = [];
  let m: RegExpExecArray | null;
  const re = new RegExp(pattern.source, pattern.flags.includes("m") ? pattern.flags : pattern.flags + "m");
  while ((m = re.exec(text))) found.push(m[1].replace(/;$/, ""));
  return found;
}

function heuristicKotlin(text: string): Symbol[] {
  const symbols: Symbol[] = [];
  let currentClass: string | undefined;
  text.split(/\n/).forEach((raw, idx) => {
    const line = raw.trim();
    const classMatch = line.match(
      /(?:(?:public|private|internal|protected|open|data|sealed|abstract)\s+)*(class|object|interface|enum\s+class)\s+([A-Za-z_][\w]*)/,
    );
    if (classMatch) {
      const kind = classMatch[1].includes("enum") ? "enum" : classMatch[1];
      currentClass = classMatch[2];
      symbols.push({ kind, name: currentClass, line: idx + 1 });
      return;
    }
    const fnMatch = line.match(
      /(?:(?:public|private|internal|protected|override|suspend)\s+)*fun\s+([A-Za-z_][\w]*)\s*\(/,
    );
    if (fnMatch) {
      const name = fnMatch[1];
      symbols.push(
        currentClass
          ? { kind: "method", name: `${currentClass}.${name}`, line: idx + 1 }
          : { kind: "fn", name, line: idx + 1 },
      );
    }
  });
  return symbols;
}

function heuristicSwift(text: string): Symbol[] {
  const symbols: Symbol[] = [];
  let current: [string, string] | undefined;
  text.split(/\n/).forEach((raw, idx) => {
    const line = raw.trim();
    const typeMatch = line.match(
      /(?:(?:public|private|internal|open|final|fileprivate)\s+)*(class|struct|enum|protocol|actor)\s+([A-Za-z_][\w]*)/,
    );
    if (typeMatch) {
      current = [typeMatch[1], typeMatch[2]];
      symbols.push({ kind: current[0], name: current[1], line: idx + 1 });
      return;
    }
    const fnMatch = line.match(
      /(?:(?:public|private|internal|open|override|static|mutating)\s+)*func\s+([A-Za-z_][\w]*)\s*\(/,
    );
    if (fnMatch) {
      const name = fnMatch[1];
      if (current && current[0] !== "protocol") {
        symbols.push({ kind: "method", name: `${current[1]}.${name}`, line: idx + 1 });
      } else {
        symbols.push({ kind: "fn", name, line: idx + 1 });
      }
    }
  });
  return symbols;
}

function heuristicJava(text: string): Symbol[] {
  const symbols: Symbol[] = [];
  let current: string | undefined;
  text.split(/\n/).forEach((raw, idx) => {
    const line = raw.trim();
    const typeMatch = line.match(
      /(?:(?:public|private|protected|abstract|final|static)\s+)*(class|interface|enum)\s+([A-Za-z_][\w]*)/,
    );
    if (typeMatch) {
      current = typeMatch[2];
      symbols.push({ kind: typeMatch[1], name: current, line: idx + 1 });
      return;
    }
    const methodMatch = line.match(
      /(?:(?:public|private|protected|static|final|synchronized|abstract)\s+)+(?:[\w.<>,\[\]?]+\s+)+([A-Za-z_][\w]*)\s*\(/,
    );
    if (methodMatch && current && !["if", "for", "while", "switch", current].includes(methodMatch[1])) {
      symbols.push({ kind: "method", name: `${current}.${methodMatch[1]}`, line: idx + 1 });
    }
  });
  return symbols;
}

function heuristicDart(text: string): Symbol[] {
  const symbols: Symbol[] = [];
  let m: RegExpExecArray | null;
  const classRe = /^\s*(?:class|mixin)\s+([A-Za-z_][\w]*)/gm;
  while ((m = classRe.exec(text))) {
    symbols.push({ kind: "class", name: m[1], line: lineAt(text, m.index) });
  }
  const fnRe = /^\s*(?:[A-Za-z_][\w<>,\s?]*\s+)?([A-Za-z_][\w]*)\s*\([^;]*\)\s*(?:async\s*)?\{/gm;
  while ((m = fnRe.exec(text))) {
    const name = m[1];
    if (["if", "for", "while", "switch", "catch"].includes(name)) continue;
    if (symbols.some((s) => s.name === name && s.kind === "class")) continue;
    symbols.push({ kind: "fn", name, line: lineAt(text, m.index) });
  }
  return symbols;
}

function extractHeuristic(path: string, suffix: string, text: string): FileFacts {
  let symbols: Symbol[] = [];
  let imports: string[] = [];
  if ([".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"].includes(suffix)) {
    imports = heuristicJsImports(text);
    symbols = heuristicJsSymbols(text);
  } else if ([".kt", ".kts"].includes(suffix)) {
    imports = heuristicImportLines(text, /^import\s+([^\s;]+)/gm);
    symbols = heuristicKotlin(text);
  } else if (suffix === ".swift") {
    imports = heuristicImportLines(text, /^import\s+([A-Za-z_][\w.]*)/gm);
    symbols = heuristicSwift(text);
  } else if (suffix === ".java") {
    imports = heuristicImportLines(text, /^import\s+(?:static\s+)?([^\s;]+)/gm);
    symbols = heuristicJava(text);
  } else if (suffix === ".dart") {
    imports = heuristicImportLines(text, /^import\s+['"]([^'"]+)['"]/gm);
    symbols = heuristicDart(text);
  }
  return { path, symbols: dedupeSymbols(symbols), imports: unique(imports), engine: "heuristic" };
}

function extractFile(source: SourceFile): FileFacts {
  const suffix = extname(source.relPath).toLowerCase();
  const path = source.relPath;
  const text = source.lines.join("\n");
  try {
    if (suffix === ".py") return extractPython(path, text);
    return extractHeuristic(path, suffix, text);
  } catch (err) {
    return { path, symbols: [], imports: [], engine: "error", error: String(err) };
  }
}

function normalizeRel(path: string): string {
  const parts: string[] = [];
  for (const part of path.replaceAll("\\", "/").split("/")) {
    if (part === "" || part === ".") continue;
    if (part === "..") {
      parts.pop();
      continue;
    }
    parts.push(part);
  }
  return parts.join("/");
}

function suffixesFor(fromPath: string): string[] {
  const ext = extname(fromPath).toLowerCase();
  const families: Record<string, string[]> = {
    ".py": [".py"],
    ".js": JS_SUFFIXES,
    ".jsx": JS_SUFFIXES,
    ".mjs": JS_SUFFIXES,
    ".cjs": JS_SUFFIXES,
    ".ts": JS_SUFFIXES,
    ".tsx": JS_SUFFIXES,
    ".kt": [".kt", ".kts", ".java"],
    ".kts": [".kt", ".kts", ".java"],
    ".java": [".java", ".kt", ".kts"],
    ".swift": [".swift"],
    ".dart": [".dart"],
  };
  const preferred = families[ext] ?? [];
  const fallback = [".py", ...JS_SUFFIXES, ".kt", ".kts", ".swift", ".java", ".dart"];
  const seen = new Set<string>();
  const ordered: string[] = [];
  for (const suffix of [...preferred, ...fallback]) {
    if (!seen.has(suffix)) {
      seen.add(suffix);
      ordered.push(suffix);
    }
  }
  return ordered;
}

function matchExisting(candidate: string, pathSet: Set<string>, fromPath = ""): string | undefined {
  const normalized = normalizeRel(candidate);
  if (pathSet.has(normalized)) return normalized;
  for (const suffix of suffixesFor(fromPath)) {
    const withSuffix = normalizeRel(normalized + suffix);
    if (pathSet.has(withSuffix)) return withSuffix;
  }
  if (extname(fromPath).toLowerCase() === ".py" || !fromPath) {
    const initPy = normalizeRel(normalized + "/__init__.py");
    if (pathSet.has(initPy)) return initPy;
  }
  if (JS_SUFFIXES.includes(extname(fromPath).toLowerCase()) || !fromPath) {
    for (const index of JS_INDEX) {
      const indexed = normalizeRel(`${normalized}/${index}`);
      if (pathSet.has(indexed)) return indexed;
    }
  }
  return undefined;
}

function dirnamePosix(fromPath: string): string {
  const i = fromPath.lastIndexOf("/");
  return i === -1 ? "" : fromPath.slice(0, i);
}

function resolveRelative(fromPath: string, spec: string, pathSet: Set<string>): string | undefined {
  const origin = dirnamePosix(fromPath);
  if (spec.startsWith("./") || spec.startsWith("../")) {
    return matchExisting(`${origin}/${spec}`, pathSet, fromPath);
  }
  const stripped = spec.replace(/^\.+/, "");
  const dots = spec.length - stripped.length;
  let dest = origin;
  for (let i = 0; i < dots - 1; i++) dest = dirnamePosix(dest);
  if (stripped) dest = dest ? `${dest}/${stripped.replaceAll(".", "/")}` : stripped.replaceAll(".", "/");
  return matchExisting(dest, pathSet, fromPath);
}

function resolvePathish(fromPath: string, spec: string, pathSet: Set<string>): string | undefined {
  if (spec.startsWith("package:")) return undefined;
  const origin = dirnamePosix(fromPath);
  const candidate = spec.startsWith("/") ? spec.replace(/^\/+/, "") : `${origin}/${spec}`;
  return matchExisting(candidate, pathSet, fromPath);
}

function resolveDotted(fromPath: string, spec: string, pathSet: Set<string>): string | undefined {
  const cleaned = spec.replace(/\.\*$/, "").replace(/\.$/, "");
  return matchExisting(cleaned.replaceAll(".", "/"), pathSet, fromPath);
}

function resolveBasename(spec: string, pathSet: Set<string>): string | undefined {
  const name = spec.split(".").pop()!;
  const matches = [...pathSet].filter((p) => basename(p).replace(extname(p), "") === name);
  return matches.length === 1 ? matches[0] : undefined;
}

export function resolveImport(fromPath: string, spec: string, pathSet: Set<string>): string | undefined {
  if (!spec || spec === "__future__") return undefined;
  if (spec.startsWith(".")) return resolveRelative(fromPath, spec, pathSet);
  if (spec.includes("/") || JS_SUFFIXES.some((s) => spec.endsWith(s)) || /\.(dart|kt|swift|java)$/.test(spec)) {
    return resolvePathish(fromPath, spec, pathSet);
  }
  return resolveDotted(fromPath, spec, pathSet) ?? resolveBasename(spec, pathSet);
}

function pagerank(nodes: string[], edges: Array<[string, string]>, damping = 0.85, rounds = 20): Record<string, number> {
  const uniqueNodes = [...new Set(nodes)];
  if (!uniqueNodes.length) return {};
  const n = uniqueNodes.length;
  const nodeSet = new Set(uniqueNodes);
  const incoming: Record<string, string[]> = {};
  const outdeg: Record<string, number> = {};
  for (const node of uniqueNodes) {
    incoming[node] = [];
    outdeg[node] = 0;
  }
  for (const [src, dst] of edges) {
    if (nodeSet.has(src) && nodeSet.has(dst) && src !== dst) {
      incoming[dst].push(src);
      outdeg[src] += 1;
    }
  }
  let rank: Record<string, number> = {};
  for (const node of uniqueNodes) rank[node] = 1.0 / n;
  for (let r = 0; r < rounds; r++) {
    const dangling = uniqueNodes.reduce((s, node) => s + (outdeg[node] === 0 ? rank[node] : 0), 0);
    const nxt: Record<string, number> = {};
    for (const node of uniqueNodes) {
      const inbound = incoming[node].reduce((s, src) => s + rank[src] / outdeg[src], 0);
      nxt[node] = (1.0 - damping) / n + damping * (inbound + dangling / n);
    }
    rank = nxt;
  }
  return rank;
}

function languageLabel(source: SourceFile): string {
  const suffix = extname(source.relPath).toLowerCase();
  const mapping: Record<string, string> = {
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
  };
  return mapping[suffix] ?? suffix.replace(".", "");
}

function formatEngines(engines: Set<string>): string {
  const ordered = ["ast", "tree-sitter", "heuristic"].filter((name) => engines.has(name));
  return ordered.length ? ordered.join(", ") : "none";
}

function formatLanguages(counts: Record<string, number>): string {
  const keys = Object.keys(counts).sort();
  if (!keys.length) return "-";
  return keys.map((name) => `${name}=${counts[name]}`).join(", ");
}

function formatSymbolLine(symbol: Symbol): string {
  if (symbol.line) return `${symbol.kind}: ${symbol.name} @${symbol.line},`;
  return `${symbol.kind}: ${symbol.name},`;
}

export function generateGraph(files: SourceFile[], root: string, outputFormat = "txt"): string {
  const fmt = (outputFormat || "txt").trim().toLowerCase();
  if (fmt !== "txt" && fmt !== "json") throw new Error("output_format must be 'txt' or 'json'");
  const graphable = files.filter((f) => GRAPHABLE.has(extname(f.relPath).toLowerCase()));
  const skipped = files.length - graphable.length;
  const facts: FileFacts[] = [];
  const engines = new Set<string>();
  const langCounts: Record<string, number> = {};
  let parsed = 0;
  for (const source of graphable) {
    const item = extractFile(source);
    facts.push(item);
    const label = languageLabel(source);
    langCounts[label] = (langCounts[label] ?? 0) + 1;
    if (item.error) continue;
    parsed += 1;
    engines.add(item.engine);
  }
  const pathSet = new Set(files.map((f) => f.relPath));
  const importRows: Array<[string, string, boolean]> = [];
  for (const item of [...facts].sort((a, b) => a.path.localeCompare(b.path))) {
    for (const raw of item.imports) {
      const resolved = resolveImport(item.path, raw, pathSet);
      importRows.push([item.path, resolved ?? raw, resolved !== undefined]);
    }
  }
  const ranks = pagerank(
    facts.map((f) => f.path),
    importRows.filter((r) => r[2]).map((r) => [r[0], r[1]] as [string, string]),
  );
  const catalogItems = facts.filter((item) => item.symbols.length);
  catalogItems.sort((a, b) => (ranks[b.path] ?? 0) - (ranks[a.path] ?? 0) || a.path.localeCompare(b.path));

  const rootName = basename(root);
  if (fmt === "json") {
    const payload = {
      root: rootName,
      file_count: files.length,
      parsed,
      skipped,
      engine: formatEngines(engines),
      languages: Object.fromEntries(Object.keys(langCounts).sort().map((k) => [k, langCounts[k]])),
      catalog: catalogItems.map((item) => ({
        path: item.path,
        rank: Math.round((ranks[item.path] ?? 0) * 1e6) / 1e6,
        symbols: item.symbols.map((symbol) => ({
          kind: symbol.kind,
          name: symbol.name,
          ...(symbol.line ? { line: symbol.line } : {}),
        })),
      })),
      imports: importRows.map(([src, dest]) => ({ from: src, to: dest })),
    };
    return JSON.stringify(payload, null, 2) + "\n";
  }

  const lines: string[] = [
    `root: ${rootName}`,
    `file_count: ${files.length}`,
    `parsed: ${parsed}`,
    `skipped: ${skipped}`,
    `engine: ${formatEngines(engines)}`,
    `languages: ${formatLanguages(langCounts)}`,
    "",
    "catalog:",
  ];
  for (const item of catalogItems) {
    lines.push(`${item.path}:`);
    lines.push(`  rank: ${(ranks[item.path] ?? 0).toFixed(4)},`);
    for (const symbol of item.symbols) lines.push(`  ${formatSymbolLine(symbol)}`);
  }
  lines.push("", "imports:");
  for (const [src, dest] of importRows) lines.push(`${src} --> ${dest},`);
  return lines.join("\n");
}
