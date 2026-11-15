import type { Catalog, ExportResult, Filters, SourceFile } from "../../engine-ts/src/types.ts";
import { applyMaxFileLines, select } from "../../engine-ts/src/select.ts";
import { extname } from "node:path";

export interface HostState {
  catalog?: Catalog;
  filters: Filters;
  checked: Set<string>;
  lastExportDir?: string;
  lastPromptPath?: string;
  bundlePaths?: string[];
  manifestPath?: string;
  graphPath?: string;
  maxFileLines: number;
  searchQuery: string;
  formatFilter: string;
}

export type FileTreeEntry =
  | { kind: "dir"; name: string; relPath: string; children: FileTreeEntry[] }
  | { kind: "file"; name: string; relPath: string; checked: boolean; oversized: boolean; lineCount: number };

export function emptyFilters(): Filters {
  return { categories: [], categoriesConstrained: false, paths: [], nameFilters: [], keywords: [] };
}

export function createState(maxFileLines = 3000): HostState {
  return { filters: emptyFilters(), checked: new Set(), maxFileLines, searchQuery: "", formatFilter: "" };
}

export function fileFormat(relPath: string): string {
  return extname(relPath).toLowerCase() || "(no extension)";
}

export function availableFormats(state: HostState): string[] {
  if (!state.catalog) return [];
  return [...new Set(state.catalog.files.map((f) => fileFormat(f.relPath)))].sort();
}

export function searchResults(state: HostState): SourceFile[] {
  if (!state.catalog) return [];
  const query = state.searchQuery.trim().toLowerCase();
  return select(state.catalog, state.filters).files.filter((file) =>
    (!query || file.relPath.toLowerCase().includes(query) || file.category.toLowerCase().includes(query)) &&
    (!state.formatFilter || fileFormat(file.relPath) === state.formatFilter),
  );
}

export function selectSearchResults(state: HostState): number {
  let added = 0;
  for (const file of searchResults(state)) {
    if (!state.checked.has(file.relPath)) {
      state.checked.add(file.relPath);
      added++;
    }
  }
  return added;
}

export function selectionFiles(state: HostState): SourceFile[] {
  if (!state.catalog) return [];
  const { included, oversized } = applyMaxFileLines({ files: searchResults(state), metadata: select(state.catalog, state.filters).metadata }, state.maxFileLines);
  return [
    ...included.filter((f) => state.checked.has(f.relPath)),
    ...oversized.filter((f) => state.checked.has(f.relPath)),
  ];
}

export function exportMaxFileLines(state: HostState): number {
  if (state.maxFileLines <= 0) return 0;
  const files = selectionFiles(state);
  if (files.some((f) => f.lineCount >= state.maxFileLines)) return 0;
  return state.maxFileLines;
}

export function applyScan(state: HostState, catalog: Catalog): void {
  state.catalog = catalog;
  const selected = select(catalog, state.filters);
  const { included } = applyMaxFileLines(selected, state.maxFileLines);
  state.checked = new Set(included.map((f) => f.relPath));
}

export function toggleCategory(state: HostState, category: string): void {
  if (!state.catalog) return;
  const all = [...new Set(state.catalog.files.map((f) => f.category))];
  if (!state.filters.categoriesConstrained) {
    state.filters.categoriesConstrained = true;
    state.filters.categories = all.filter((c) => c !== category);
  } else {
    const i = state.filters.categories.indexOf(category);
    if (i >= 0) state.filters.categories.splice(i, 1);
    else state.filters.categories.push(category);
  }
  applyScan(state, state.catalog);
}

export function categoryChecked(state: HostState, category: string): boolean {
  if (!state.filters.categoriesConstrained) return true;
  return state.filters.categories.includes(category);
}

export function addPath(state: HostState, relPath: string): void {
  if (!state.filters.paths.includes(relPath)) state.filters.paths.push(relPath);
  if (state.catalog) applyScan(state, state.catalog);
}

export function setNameFilters(state: HostState, raw: string): void {
  state.filters.nameFilters = raw
    .split(/[,;\s]+/)
    .map((t) => t.trim())
    .filter(Boolean);
  if (state.catalog) applyScan(state, state.catalog);
}

export function setPathFilters(state: HostState, raw: string): void {
  state.filters.paths = raw
    .split(/[,;\s]+/)
    .map((t) => t.trim())
    .filter(Boolean);
  if (state.catalog) applyScan(state, state.catalog);
}

export function selectAllCategories(state: HostState): void {
  state.filters.categories = [];
  state.filters.categoriesConstrained = false;
  if (state.catalog) applyScan(state, state.catalog);
}

export function recordExport(state: HostState, result: ExportResult): void {
  state.lastExportDir = result.outputDir;
  state.lastPromptPath = result.promptPath;
  state.bundlePaths = result.bundlePaths;
  state.manifestPath = result.manifestPath;
  state.graphPath = result.graphPath;
}

export function visibleFileTree(state: HostState): FileTreeEntry[] {
  if (!state.catalog) return [];
  const { included, oversized } = applyMaxFileLines(
    { files: searchResults(state), metadata: select(state.catalog, state.filters).metadata },
    state.maxFileLines,
  );
  const oversizedSet = new Set(oversized.map((f) => f.relPath));
  const files = [...included, ...oversized].sort((a, b) => (a.relPath < b.relPath ? -1 : 1));

  type DirNode = { kind: "dir"; name: string; relPath: string; children: FileTreeEntry[] };
  const root: FileTreeEntry[] = [];
  const dirs = new Map<string, DirNode>();

  const ensureDir = (rel: string): DirNode | undefined => {
    if (!rel) return undefined;
    const existing = dirs.get(rel);
    if (existing) return existing;
    const parentPath = rel.includes("/") ? rel.slice(0, rel.lastIndexOf("/")) : "";
    const name = rel.includes("/") ? rel.slice(rel.lastIndexOf("/") + 1) : rel;
    const dir: DirNode = { kind: "dir", name, relPath: rel, children: [] };
    dirs.set(rel, dir);
    const parent = ensureDir(parentPath);
    if (parent) parent.children.push(dir);
    else root.push(dir);
    return dir;
  };

  for (const file of files) {
    const dir = file.relPath.includes("/") ? file.relPath.slice(0, file.relPath.lastIndexOf("/")) : "";
    const name = file.relPath.includes("/") ? file.relPath.slice(file.relPath.lastIndexOf("/") + 1) : file.relPath;
    const node: FileTreeEntry = {
      kind: "file",
      name,
      relPath: file.relPath,
      checked: state.checked.has(file.relPath),
      oversized: oversizedSet.has(file.relPath),
      lineCount: file.lineCount,
    };
    const parent = ensureDir(dir);
    if (parent) parent.children.push(node);
    else root.push(node);
  }
  return root;
}
