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

  for (const abs of walkFiles(root)) {
    if (options.isCanceled?.()) throw new EngineCanceled();
    const rel = posixRel(relative(root, abs));
    if (shouldSkipByDir(rel, policy.defaultExcludedDirs)) {
      bump("default_excluded_dir");
      continue;
    }
    if (shouldSkipByPrefix(rel, policy.defaultExcludedPrefixes)) {
      bump("default_excluded_prefix");
      continue;
    }
    if (gitignore.ignores(rel)) {
      bump(".gitignore");
      continue;
    }
    if (pathMatchesAnyPattern(rel, policy.extraExcludedPatterns)) {
      bump("extra_excluded_pattern");
      continue;
    }
    if (!options.includeSecretFiles && pathMatchesAnyPattern(rel, policy.defaultSecretPatterns)) {
      bump("secret_like_file");
      continue;
    }
    const category = detectCategory(abs);
    if (!category) {
      bump("unsupported_type");
      continue;
    }
    if (isProbablyBinary(abs)) {
      bump("binary");
      continue;
    }
    let lines: string[];
    try {
      lines = readTextLines(abs);
    } catch {
      bump("read_error");
      continue;
    }
    let sizeBytes = 0;
    try {
      sizeBytes = statSync(abs).size;
    } catch {
      bump("read_error");
      continue;
    }
    files.push({
      absPath: resolve(abs),
      relPath: rel,
      category,
      lineCount: lines.length,
      sizeBytes,
      sha256: sha256OfLines(lines),
      lines,
    });
  }

  files.sort((a, b) => (a.relPath < b.relPath ? -1 : a.relPath > b.relPath ? 1 : 0));
  const orderedSkipped: Record<string, number> = {};
  for (const key of Object.keys(skipped).sort()) orderedSkipped[key] = skipped[key];
  return { workspace: root, files, skipped: orderedSkipped };
}
