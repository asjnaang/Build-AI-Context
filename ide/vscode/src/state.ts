import type { Catalog, Filters, SourceFile } from "../../engine-ts/src/types.ts";
import { applyMaxFileLines, select } from "../../engine-ts/src/select.ts";

export interface HostState {
  catalog?: Catalog;
  filters: Filters;
  checked: Set<string>;
  lastExportDir?: string;
  lastPromptPath?: string;
  maxFileLines: number;
}

export function emptyFilters(): Filters {
  return { categories: [], paths: [], nameFilters: [], keywords: [] };
}

export function createState(maxFileLines = 3000): HostState {
  return { filters: emptyFilters(), checked: new Set(), maxFileLines };
}

export function selectionFiles(state: HostState): SourceFile[] {
  if (!state.catalog) return [];
  const selected = select(state.catalog, state.filters);
  const { included, oversized } = applyMaxFileLines(selected, state.maxFileLines);
  return [
    ...included.filter((f) => state.checked.has(f.relPath)),
    ...oversized.filter((f) => state.checked.has(f.relPath)),
  ];
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
  if (state.filters.categories.length === 0) {
    state.filters.categories = all.filter((c) => c !== category);
  } else {
    const i = state.filters.categories.indexOf(category);
    if (i >= 0) state.filters.categories.splice(i, 1);
    else state.filters.categories.push(category);
  }
  applyScan(state, state.catalog);
}

export function addPath(state: HostState, relPath: string): void {
  if (!state.filters.paths.includes(relPath)) state.filters.paths.push(relPath);
  if (state.catalog) applyScan(state, state.catalog);
}
