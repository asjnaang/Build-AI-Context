import { basename, isAbsolute, relative, resolve, sep } from "node:path";
import { loadPolicy } from "./policy.ts";
import type { Catalog, Filters, Selection, SourceFile } from "./types.ts";

export function normalizeCategories(values: string[]): string[] {
  const policy = loadPolicy();
  const normalized: string[] = [];
  for (const value of values) {
    const key = value.trim().toLowerCase();
    if (!key) continue;
    const mapped = policy.categoryAliases[key] ?? key;
    if (mapped in policy.categoryDescriptions && !normalized.includes(mapped)) {
      normalized.push(mapped);
    }
  }
  return normalized;
}

function posix(p: string): string {
  return p.split(sep).join("/");
}

export function parseCsvInput(raw: string): string[] {
  return raw
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
}

export function parseIntelligentInput(raw: string, files: SourceFile[], root: string): string[] {
  if (!raw.trim()) return [];
  const allPathStrs = new Set(files.map((f) => f.relPath));
  const allNames = new Set(files.map((f) => basename(f.relPath)));
  const found: string[] = [];
  const parts = raw.split(/[,;\s]+/).map((p) => p.trim()).filter(Boolean);

  for (let part of parts) {
    if (isAbsolute(part)) {
      try {
        part = posix(relative(root, resolve(part)));
      } catch {
        /* keep */
      }
    }
    if (allPathStrs.has(part)) {
      if (!found.includes(part)) found.push(part);
      continue;
    }
    if (allNames.has(part)) {
      for (const p of allPathStrs) {
        if (p.endsWith("/" + part) || p === part) {
          if (!found.includes(p)) found.push(p);
        }
      }
      continue;
    }
    const exact = [...allPathStrs].filter((p) => p === part || p.endsWith("/" + part));
    if (exact.length) {
      for (const m of exact) if (!found.includes(m)) found.push(m);
      continue;
    }
    const folder = [...allPathStrs].filter((p) => p.startsWith(part + "/") || p.includes("/" + part + "/"));
    if (folder.length) {
      for (const m of folder) if (!found.includes(m)) found.push(m);
      continue;
    }
    const contains = [...allPathStrs].filter((p) => p.includes(part));
    if (contains.length) {
      for (const m of contains) if (!found.includes(m)) found.push(m);
      continue;
    }
    const stripped = (s: string) => s.replaceAll("/", "").replaceAll("\\", "");
    const partial = [...allPathStrs].filter((p) => stripped(p).startsWith(stripped(part)));
    if (partial.length) {
      for (const m of partial) if (!found.includes(m)) found.push(m);
    }
  }
  return found;
}

export function filterFilesByPaths(
  files: SourceFile[],
  root: string,
  rawPaths: string[],
): { matched: SourceFile[]; normalized: string[]; missing: string[] } {
  const normalized = normalizeSelectionPaths(rawPaths, root);
  if (!normalized.length) return { matched: [...files], normalized: [], missing: [] };

  const matched: SourceFile[] = [];
  const missing: string[] = [];

  for (let i = 0; i < rawPaths.length; i++) {
    const rawInput = rawPaths[i];
    const norm = normalized[i];
    const looksLikeFileNameOnly = !isAbsolute(rawInput) && !rawInput.includes("/") && !rawInput.includes("\\");
    const exact = files.filter(
      (item) =>
        item.relPath === norm ||
        item.relPath.startsWith(norm.replace(/\/$/, "") + "/") ||
        resolve(item.absPath) === resolve(isAbsolute(rawInput) ? rawInput : joinRoot(root, rawInput)),
    );
    if (exact.length) {
      for (const item of exact) if (!matched.includes(item)) matched.push(item);
      continue;
    }
    if (looksLikeFileNameOnly) {
      const base = files.filter((item) => basename(item.relPath) === basename(rawInput));
      if (base.length) {
        for (const item of base) if (!matched.includes(item)) matched.push(item);
        continue;
      }
    }
    missing.push(rawInput);
  }
  matched.sort((a, b) => (a.relPath < b.relPath ? -1 : a.relPath > b.relPath ? 1 : 0));
  return { matched, normalized, missing };
}

function joinRoot(root: string, rel: string): string {
  return resolve(root, rel);
}

function normalizeSelectionPaths(rawPaths: string[], root: string): string[] {
  const normalized: string[] = [];
  for (const raw of rawPaths) {
    let value = raw.trim();
    if (!value) continue;
    if (isAbsolute(value)) {
      try {
        value = posix(relative(root, resolve(value)));
      } catch {
        value = posix(resolve(value));
      }
    } else {
      value = value.replace(/\/$/, "");
    }
    if (!normalized.includes(value)) normalized.push(value);
  }
  return normalized;
}

export function filterFilesByKeywords(
  files: SourceFile[],
  keywords: string[],
): { matched: SourceFile[]; keywords: string[] } {
  const matched: SourceFile[] = [];
  const matchedKeywords: string[] = [];
  const lower = keywords.map((k) => k.toLowerCase());
  for (const item of files) {
    const content = item.lines.join("\n").toLowerCase();
    const found = lower.filter((kw) => content.includes(kw));
    if (found.length) {
      matched.push(item);
      for (const kw of found) if (!matchedKeywords.includes(kw)) matchedKeywords.push(kw);
    }
  }
  matched.sort((a, b) => (a.relPath < b.relPath ? -1 : a.relPath > b.relPath ? 1 : 0));
  return { matched, keywords: [...matchedKeywords].sort() };
}

export function select(catalog: Catalog, filters: Filters): Selection {
  const policy = loadPolicy();
  let selected = [...catalog.files];
  const constrainedEmpty = filters.categoriesConstrained === true && filters.categories.length === 0;
  const hasCat = filters.categories.length > 0;
  const hasPath = filters.paths.length > 0;
  const hasName = filters.nameFilters.length > 0;
  const hasKw = filters.keywords.length > 0;

  let selectedCategories: string[] = [];
  if (constrainedEmpty) {
    selected = [];
  } else if (hasCat) {
    selectedCategories = normalizeCategories(filters.categories);
    const invalid = filters.categories.filter((item) => {
      const key = item.trim().toLowerCase();
      const mapped = policy.categoryAliases[key] ?? key;
      return !(mapped in policy.categoryDescriptions);
    });
    if (invalid.length) {
      throw new Error(`Unsupported categories requested: ${invalid.join(", ")}`);
    }
    selected = selected.filter((f) => selectedCategories.includes(f.category));
  }

  let selectedPaths: string[] = [];
  let missingPaths: string[] = [];
  if (hasPath) {
    const filtered = filterFilesByPaths(selected, catalog.workspace, filters.paths);
    selected = filtered.matched;
    selectedPaths = filtered.normalized;
    missingPaths = filtered.missing;
  }

  if (hasName) {
    selected = selected.filter((f) => {
      const fname = basename(f.relPath).toLowerCase();
      return filters.nameFilters.some((nf) => fname.includes(nf.toLowerCase()));
    });
  }

  if (hasKw) {
    selected = filterFilesByKeywords(selected, filters.keywords).matched;
  }

  selected.sort((a, b) => (a.relPath < b.relPath ? -1 : a.relPath > b.relPath ? 1 : 0));
  const anyFilter = hasCat || constrainedEmpty || hasPath || hasName || hasKw;
  return {
    files: selected,
    metadata: {
      selectionMode: anyFilter ? "composed" : "non_interactive",
      selectedCategories,
      selectedPaths,
      nameFilters: hasName ? filters.nameFilters : hasKw ? filters.keywords : [],
      missingPaths,
    },
  };
}

export function applyMaxFileLines(
  selection: Selection,
  maxFileLines: number,
): { included: SourceFile[]; oversized: SourceFile[] } {
  if (maxFileLines <= 0) {
    return { included: [...selection.files], oversized: [] };
  }
  const included: SourceFile[] = [];
  const oversized: SourceFile[] = [];
  for (const file of selection.files) {
    if (file.lineCount >= maxFileLines) oversized.push(file);
    else included.push(file);
  }
  return { included, oversized };
}
