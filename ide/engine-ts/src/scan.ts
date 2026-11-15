import { createHash } from "node:crypto";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { basename, extname, join, relative, resolve, sep } from "node:path";
import ignore from "ignore";
import { minimatch } from "minimatch";
import { loadPolicy } from "./policy.ts";
import { EngineCanceled, type Catalog, type ScanOptions, type SourceFile } from "./types.ts";

export function detectCategory(filePath: string): string | undefined {
  const policy = loadPolicy();
  const name = basename(filePath);
  const suffix = extname(filePath).toLowerCase();
  if (policy.specialFilenames.includes(name)) {
    if (name === "Podfile" || name === ".swiftlint.yml") return "ios_apple";
    if (
      [
        "AndroidManifest.xml",
        "gradle.properties",
        "settings.gradle",
        "settings.gradle.kts",
        "build.gradle",
        "build.gradle.kts",
      ].includes(name)
    ) {
      return "java_kotlin";
    }
    return "config_docs";
  }
  for (const [category, extensions] of Object.entries(policy.categoryExtensions)) {
    if (extensions.includes(suffix)) return category;
  }
  return undefined;
}

function posixRel(rel: string): string {
  return rel.split(sep).join("/");
}

export function pathMatchesAnyPattern(relPath: string, patterns: string[]): boolean {
  const name = basename(relPath);
  return patterns.some((pattern) => minimatch(relPath, pattern) || minimatch(name, pattern));
}

function shouldSkipByDir(relPath: string, dirs: string[]): boolean {
  return posixRel(relPath)
    .split("/")
    .some((part) => dirs.includes(part));
}

function shouldSkipByPrefix(relPath: string, prefixes: string[]): boolean {
  const rel = posixRel(relPath);
  return prefixes.some((prefix) => rel.startsWith(prefix));
}

function isProbablyBinary(absPath: string): boolean {
  try {
    const fd = readFileSync(absPath);
    return fd.subarray(0, 4096).includes(0);
  } catch {
    return true;
  }
}

export function splitLines(text: string): string[] {
  if (text.length === 0) return [];
  const lines = text.split(/\r\n|\n|\r/);
  if ((text.endsWith("\n") || text.endsWith("\r")) && lines[lines.length - 1] === "") {
    lines.pop();
  }
  return lines;
}

function decodeText(buf: Buffer): string {
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(buf);
  } catch {
    /* utf-8-sig: skip BOM then strict utf-8 */
  }
  try {
    const rest =
      buf.length >= 3 && buf[0] === 0xef && buf[1] === 0xbb && buf[2] === 0xbf ? buf.subarray(3) : buf;
    return new TextDecoder("utf-8", { fatal: true }).decode(rest);
  } catch {
    /* latin-1 never fails */
  }
  return buf.toString("latin1");
}

function readTextLines(absPath: string): string[] {
  return splitLines(decodeText(readFileSync(absPath)));
}

export function sha256OfLines(lines: string[]): string {
  return createHash("sha256").update(lines.join("\n"), "utf8").digest("hex");
}

export function sha256OfBytes(data: Buffer): string {
  return createHash("sha256").update(data).digest("hex");
}

function normalizeIncludeFormats(values: string[] | undefined): Set<string> {
  const out = new Set<string>();
  for (const raw of values ?? []) {
    let ext = raw.trim().toLowerCase();
    if (!ext) continue;
    ext = ext.replace(/^\*\./, "").replace(/^\./, "");
    if (!ext.startsWith(".")) ext = `.${ext}`;
    out.add(ext);
  }
  return out;
}

function matchesForcedPath(rel: string, forced: string[]): boolean {
  const posix = posixRel(rel).replace(/\/$/, "");
  return forced.some((requested) => {
    const want = posixRel(requested).replace(/\/$/, "");
    return posix === want || posix.startsWith(want + "/") || want.startsWith(posix + "/");
  });
}

function walkFiles(root: string): string[] {
  const out: string[] = [];
  const stack = [root];
  while (stack.length) {
    const dir = stack.pop()!;
    let entries;
    try {
      entries = readdirSync(dir, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const entry of entries) {
      const full = join(dir, entry.name);
      if (entry.isDirectory()) stack.push(full);
      else if (entry.isFile() || entry.isSymbolicLink()) {
        try {
          if (statSync(full).isFile()) out.push(full);
        } catch {
          /* skip */
        }
      }
    }
  }
  return out;
}

function loadGitignore(root: string) {
  const ig = ignore();
  try {
    const text = readFileSync(join(root, ".gitignore"), "utf8");
    ig.add(text.split(/\r?\n/));
  } catch {
    /* no gitignore */
  }
  return ig;
}

export async function scan(workspace: string, options: ScanOptions): Promise<Catalog> {
  const policy = loadPolicy();
  const root = resolve(workspace);
  const gitignore = loadGitignore(root);
  const files: SourceFile[] = [];
  const skipped: Record<string, number> = {};
  const bump = (reason: string) => {
    skipped[reason] = (skipped[reason] ?? 0) + 1;
  };
  const forcedPaths = (options.forceIgnoredPaths ?? []).map((p) => posixRel(p));
  const forcedFormats = normalizeIncludeFormats(options.forceIncludeFormats);
  const excluded = (options.excludePaths ?? []).map((p) => posixRel(p).replace(/\/$/, "")).filter(Boolean);

  for (const abs of walkFiles(root)) {
    if (options.isCanceled?.()) throw new EngineCanceled();
    const rel = posixRel(relative(root, abs));
    const forceThis = matchesForcedPath(rel, forcedPaths) && !rel.split("/").includes(".git");
    if (excluded.some((ex) => rel === ex || rel.startsWith(ex + "/"))) {
      bump("excluded_path");
      continue;
    }
    if (shouldSkipByDir(rel, policy.defaultExcludedDirs) && !forceThis) {
      bump("default_excluded_dir");
      continue;
    }
    if (shouldSkipByPrefix(rel, policy.defaultExcludedPrefixes) && !forceThis) {
      bump("default_excluded_prefix");
      continue;
    }
    if (gitignore.ignores(rel) && !forceThis) {
      bump(".gitignore");
      continue;
    }
    if (pathMatchesAnyPattern(rel, policy.extraExcludedPatterns) && !forceThis) {
      bump("extra_excluded_pattern");
      continue;
    }
    if (!options.includeSecretFiles && pathMatchesAnyPattern(rel, policy.defaultSecretPatterns)) {
      bump("secret_like_file");
      continue;
    }
    const suffix = extname(abs).toLowerCase();
    const forceFormat = forcedFormats.has(suffix);
    let category = detectCategory(abs);
    if (!category && !forceFormat) {
      bump("unsupported_type");
      continue;
    }
    if (!category) category = "config_docs";
    let snapshotBytes: Buffer;
    let sizeBytes = 0;
    let mode = 0o644;
    try {
      snapshotBytes = readFileSync(abs);
      const st = statSync(abs);
      sizeBytes = st.size;
      mode = st.mode & 0o7777;
    } catch {
      bump("read_error");
      continue;
    }
    const binary = forceFormat ? isProbablyBinary(abs) || suffix === ".sqlite3" : isProbablyBinary(abs);
    if (binary && !forceFormat) {
      bump("binary");
      continue;
    }
    let lines: string[] = [];
    if (!binary) {
      try {
        lines = splitLines(decodeText(snapshotBytes));
      } catch {
        if (!forceFormat) {
          bump("read_error");
          continue;
        }
      }
    }
    files.push({
      absPath: resolve(abs),
      relPath: rel,
      category,
      lineCount: lines.length,
      sizeBytes,
      sha256: sha256OfBytes(snapshotBytes),
      lines,
      snapshotBytes,
      mode: mode || 0o644,
      encoding: binary ? "binary" : "text",
    });
  }

  files.sort((a, b) => (a.relPath < b.relPath ? -1 : a.relPath > b.relPath ? 1 : 0));
  const orderedSkipped: Record<string, number> = {};
  for (const key of Object.keys(skipped).sort()) orderedSkipped[key] = skipped[key];
  return { workspace: root, files, skipped: orderedSkipped };
}
