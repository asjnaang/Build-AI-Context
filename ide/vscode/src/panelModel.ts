import {
  availableFormats,
  categoryChecked,
  searchResults,
  selectionFiles,
  visibleFileTree,
  type FileTreeEntry,
  type HostState,
} from "./state.ts";

export type PanelSettings = {
  transport: string;
  forceBundle: boolean;
  forceIgnored: boolean;
  split: boolean;
  excludePaths: string;
  forceIncludeFormats: string;
};

export type PanelCategory = {
  id: string;
  label: string;
  count: number;
  checked: boolean;
};

export type PanelSnapshot = {
  catalogReady: boolean;
  searchQuery: string;
  formatFilter: string;
  formats: string[];
  resultCount: number;
  selectedCount: number;
  oversizedCount: number;
  transport: string;
  transportLabel: string;
  selectAllChecked: boolean;
  files: FileTreeEntry[];
  categories: PanelCategory[];
  keywords: string;
  paths: string;
  forceBundle: boolean;
  forceIgnored: boolean;
  split: boolean;
  excludePaths: string;
  extraFormats: string;
  lastExportDir?: string;
  lastPromptPath?: string;
  manifestPath?: string;
  status: string;
};

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function attr(value: string): string {
  return escapeHtml(value);
}

export function panelSnapshot(state: HostState, settings: PanelSettings): PanelSnapshot {
  const results = searchResults(state);
  const selected = selectionFiles(state);
  const oversized = results.filter((file) => file.lineCount >= state.maxFileLines && state.maxFileLines > 0);
  const transport = settings.transport || "tar-gz";
  const counts = new Map<string, number>();
  for (const file of state.catalog?.files ?? []) {
    counts.set(file.category, (counts.get(file.category) ?? 0) + 1);
  }
  const categories = [...counts.entries()]
    .filter(([, count]) => count > 0)
    .sort((a, b) => (a[0] < b[0] ? -1 : 1))
    .map(([id, count]) => ({
      id,
      label: id.replaceAll("_", " "),
      count,
      checked: categoryChecked(state, id),
    }));
  return {
    catalogReady: Boolean(state.catalog),
    searchQuery: state.searchQuery,
    formatFilter: state.formatFilter,
    formats: availableFormats(state),
    resultCount: results.length,
    selectedCount: selected.length,
    oversizedCount: oversized.length,
    transport,
    transportLabel: transport === "tar-gz" ? "gzip" : "text",
    selectAllChecked: results.length > 0 && results.every((file) => state.checked.has(file.relPath)),
    files: visibleFileTree(state),
    categories,
    keywords: state.filters.keywords.join(" "),
    paths: state.filters.paths.join(", "),
    forceBundle: settings.forceBundle,
    forceIgnored: settings.forceIgnored,
    split: settings.split,
    excludePaths: settings.excludePaths,
    extraFormats: settings.forceIncludeFormats,
    lastExportDir: state.lastExportDir,
    lastPromptPath: state.lastPromptPath,
    manifestPath: state.manifestPath,
    status: state.catalog
      ? `${results.length} results · ${selected.length} selected · ${transport === "tar-gz" ? "gzip" : "text"}`
      : "Cataloging this folder… Export waits for the catalog.",
  };
}

function renderTree(entries: FileTreeEntry[], depth = 0): string {
  return entries
    .map((entry) => {
      if (entry.kind === "dir") {
        const open = depth === 0 ? " open" : "";
        return `<details class="dir" data-path="${attr(entry.relPath)}"${open}><summary>${escapeHtml(entry.name)}</summary>${renderTree(entry.children, depth + 1)}</details>`;
      }
      const large = entry.oversized ? ` <span class="warning">large</span>` : "";
      return `<label class="file"><input type="checkbox" data-path="${attr(entry.relPath)}" ${entry.checked ? "checked" : ""}/> ${escapeHtml(entry.name)}${large}</label>`;
    })
    .join("");
}

export function panelMarkup(snapshot: PanelSnapshot): string {
  const formats = [`<option value="">All formats</option>`]
    .concat(
      snapshot.formats.map(
        (format) =>
          `<option value="${attr(format)}"${snapshot.formatFilter === format ? " selected" : ""}>${escapeHtml(format)}</option>`,
      ),
    )
    .join("");
  const categories =
    snapshot.categories.length === 0
      ? `<span class="hint">All supported</span>`
      : snapshot.categories
          .map(
            (category) =>
              `<label class="chip"><input type="checkbox" data-category="${attr(category.id)}" ${category.checked ? "checked" : ""}/> ${escapeHtml(category.label)}</label>`,
          )
          .join("");
  const last = snapshot.lastExportDir
    ? `<button type="button" class="link" data-action="openFolder">Open folder</button> · <button type="button" class="link" data-action="openManifest">Manifest</button> · <button type="button" class="link" data-action="openPrompt">baic_prompt.md</button>`
    : `<span class="hint">No export yet</span>`;
  const oversized =
    snapshot.catalogReady && snapshot.oversizedCount > 0
      ? `<div class="hint">${snapshot.oversizedCount} large files start unchecked</div>`
      : "";
  return `
<section data-section="search"><input id="search" type="search" placeholder="Search files…" value="${attr(snapshot.searchQuery)}" /></section>
<section data-section="format" class="option"><span>File format</span><select id="format">${formats}</select></section>
<section data-section="meta" class="meta">${escapeHtml(snapshot.status)}${oversized}</section>
<section data-section="export"><button type="button" class="primary" id="export" ${snapshot.selectedCount === 0 && snapshot.catalogReady ? "disabled" : ""}>Export ${snapshot.selectedCount} files</button></section>
<section data-section="selectAll" class="actions"><label><input type="checkbox" id="selectAll" ${snapshot.selectAllChecked ? "checked" : ""}/> Select all results</label></section>
<section data-section="actions" class="actions"><button type="button" class="link" id="refresh">Refresh</button><button type="button" class="link" id="restore">Restore gzip</button></section>
<section data-section="files"><div class="label">Files</div><div class="tree">${snapshot.files.length ? renderTree(snapshot.files) : `<div class="hint">${snapshot.catalogReady ? "No files match." : "Open a trusted folder."}</div>`}</div></section>
<section data-section="options" class="section"><div class="label">Options</div>
  <div class="option"><span>Package</span><select id="transport"><option value="tar-gz"${snapshot.transport === "tar-gz" ? " selected" : ""}>gzip</option><option value="text"${snapshot.transport === "text" ? " selected" : ""}>text</option></select></div>
  <div class="option wrap"><span>Categories</span><div class="chips">${categories}</div></div>
  <label class="field-label">Content keywords / paths</label>
  <input id="keywords" placeholder="Keywords" value="${attr(snapshot.keywords)}" />
  <input id="paths" placeholder="Paths" value="${attr(snapshot.paths)}" />
  <details class="advanced"><summary>Advanced: ignored paths, large files, extra formats, safety, output</summary>
    <label class="chip"><input type="checkbox" id="forceBundle" ${snapshot.forceBundle ? "checked" : ""}/> Include large files</label>
    <label class="chip"><input type="checkbox" id="forceIgnored" ${snapshot.forceIgnored ? "checked" : ""}/> Include ignored paths</label>
    <label class="chip"><input type="checkbox" id="split" ${snapshot.split ? "checked" : ""}/> Split gzip</label>
    <input id="excludePaths" placeholder="Exclude paths" value="${attr(snapshot.excludePaths)}" />
    <input id="extraFormats" placeholder="Extra formats (.sqlite3)" value="${attr(snapshot.extraFormats)}" />
  </details>
</section>
<section data-section="lastExport" class="section"><div class="label">Last export</div>${last}</section>
`.trim();
}
