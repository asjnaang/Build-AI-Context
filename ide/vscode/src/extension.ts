import { basename, join, relative } from "node:path";
import * as vscode from "vscode";
import { scan } from "../../engine-ts/src/scan.ts";
import { select } from "../../engine-ts/src/select.ts";
import { EngineCanceled } from "../../engine-ts/src/types.ts";
import { exportCatalog, writeStandaloneFiletree, writeStandaloneGraph } from "../../engine-ts/src/write.ts";
import { restoreExport, RestoreError } from "../../engine-ts/src/gzip.ts";
import { setPolicyPath } from "../../engine-ts/src/policy.ts";
import { setPromptDir } from "../../engine-ts/src/prompt.ts";
import {
  addPath,
  availableFormats,
  applyScan,
  categoryChecked,
  createState,
  emptyFilters,
  exportMaxFileLines,
  recordExport,
  selectionFiles,
  searchResults,
  selectSearchResults,
  setNameFilters,
  setPathFilters,
  toggleCategory,
  visibleFileTree,
  type FileTreeEntry,
  type HostState,
} from "./state.ts";
import { denyUntrustedWrite } from "./trust.ts";

class FilterItem extends vscode.TreeItem {
  constructor(
    label: string,
    public readonly rowId: string,
    commandId?: string,
    args?: unknown[],
  ) {
    super(label, vscode.TreeItemCollapsibleState.None);
    this.contextValue = rowId.startsWith("cat:") ? "baicCategory" : "baicFilter";
    if (commandId) this.command = { command: commandId, title: "Toggle", arguments: args ?? [] };
  }
}

class FileNode extends vscode.TreeItem {
  constructor(public readonly entry: FileTreeEntry) {
    super(
      entry.name,
      entry.kind === "dir" ? vscode.TreeItemCollapsibleState.Collapsed : vscode.TreeItemCollapsibleState.None,
    );
    if (entry.kind === "file") {
      this.checkboxState = entry.checked
        ? vscode.TreeItemCheckboxState.Checked
        : vscode.TreeItemCheckboxState.Unchecked;
      this.description = `${entry.lineCount} lines`;
      this.contextValue = "baicFile";
      this.tooltip = entry.relPath;
      if (entry.oversized) this.iconPath = new vscode.ThemeIcon("warning");
    } else {
      this.contextValue = "baicDir";
    }
  }
}

class ExportActionItem extends vscode.TreeItem {
  constructor(count: number, transport: string) {
    super(`Export ${count} files`, vscode.TreeItemCollapsibleState.None);
    this.description = transport === "tar-gz" ? "gzip package" : "readable text";
    this.iconPath = new vscode.ThemeIcon("export");
    this.tooltip = "Write selected files, manifest, and baic_prompt.md";
    this.command = { command: "baic.export", title: "Export selected files" };
  }
}

class FileActionItem extends vscode.TreeItem {
  constructor(label: string, description: string, icon: string, command: string) {
    super(label, vscode.TreeItemCollapsibleState.None);
    this.description = description;
    this.iconPath = new vscode.ThemeIcon(icon);
    this.command = { command, title: label };
  }
}

class ArtifactItem extends vscode.TreeItem {
  constructor(label: string, uri: vscode.Uri) {
    super(label, vscode.TreeItemCollapsibleState.None);
    this.resourceUri = uri;
    this.command = { command: "vscode.open", title: "Open", arguments: [uri] };
  }
}

function cfg() {
  return vscode.workspace.getConfiguration("baic");
}

export function activate(context: vscode.ExtensionContext): void {
  setPolicyPath(join(context.extensionPath, "resources", "policy.json"));
  setPromptDir(join(context.extensionPath, "resources"));

  const state: HostState = createState();

  const filtersTree = new (class implements vscode.TreeDataProvider<FilterItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<void>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;
    refresh() {
      this._onDidChangeTreeData.fire();
    }
    getTreeItem(el: FilterItem) {
      return el;
    }
    getChildren(): FilterItem[] {
      const rows: FilterItem[] = [];
      if (state.catalog) {
        const counts = new Map<string, number>();
        for (const f of state.catalog.files) counts.set(f.category, (counts.get(f.category) ?? 0) + 1);
        for (const [cat, n] of [...counts.entries()].sort((a, b) => (a[0] < b[0] ? -1 : 1))) {
          const checked = categoryChecked(state, cat);
          rows.push(
            new FilterItem(`${checked ? "$(check) " : ""}${cat} (${n})`, `cat:${cat}`, "baic.toggleCategory", [cat]),
          );
        }
      }
      const keyword = state.filters.keywords[0] ?? "(none)";
      const name = state.filters.nameFilters[0] ?? "(none)";
      const paths = state.filters.paths.length ? state.filters.paths.join(", ") : "(none)";
      const redact = cfg().get<boolean>("redact") ? "on" : "off";
      const secrets = cfg().get<boolean>("includeSecretFiles") ? "on" : "off";
      const overview = cfg().get<boolean>("projectOverview") ? "on" : "off";
      const graph = cfg().get<string>("writeGraph") ?? "off";
      const transport = cfg().get<string>("transport") ?? "tar-gz";
      const forceBundle = cfg().get<boolean>("forceBundle") ? "on" : "off";
      const forceIgnored = cfg().get<boolean>("forceIgnored") ? "on" : "off";
      const split = cfg().get<boolean>("split") ? "on" : "off";
      const exclude = cfg().get<string>("excludePaths")?.trim() || "(none)";
      const formats = cfg().get<string>("forceIncludeFormats")?.trim() || "(none)";
      rows.push(new FilterItem(`Transport: ${transport}`, "transport", "baic.cycleTransport"));
      rows.push(new FilterItem(`Force bundle: ${forceBundle}`, "forceBundle", "baic.toggleForceBundle"));
      rows.push(new FilterItem(`Force ignored: ${forceIgnored}`, "forceIgnored", "baic.toggleForceIgnored"));
      rows.push(new FilterItem(`Split gzip: ${split}`, "split", "baic.toggleSplit"));
      rows.push(new FilterItem(`Exclude paths: ${exclude}`, "excludePaths", "baic.setExcludePaths"));
      rows.push(new FilterItem(`Force include formats: ${formats}`, "forceInclude", "baic.setForceIncludeFormats"));
      rows.push(new FilterItem(`Keyword: ${keyword}`, "keyword", "baic.setKeyword"));
      rows.push(new FilterItem(`Filename: ${name}`, "name", "baic.setNameFilter"));
      rows.push(new FilterItem(`Paths: ${paths}`, "paths", "baic.setPathFilter"));
      rows.push(new FilterItem(`Redact: ${redact}`, "redact", "baic.toggleRedact"));
      rows.push(new FilterItem(`Secrets: ${secrets}`, "secrets", "baic.toggleSecrets"));
      rows.push(new FilterItem(`Overview: ${overview}`, "overview", "baic.toggleOverview"));
      rows.push(new FilterItem(`Graph: ${graph}`, "graph", "baic.cycleGraph"));
      return rows;
    }
  })();

  const filesTree = new (class implements vscode.TreeDataProvider<vscode.TreeItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<vscode.TreeItem | void>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;
    refresh() {
      this._onDidChangeTreeData.fire();
    }
    getTreeItem(el: vscode.TreeItem) {
      return el;
    }
    getChildren(el?: vscode.TreeItem): vscode.TreeItem[] {
      if (!state.catalog) return [];
      if (el && !(el instanceof FileNode)) return [];
      const nodes = el ? (el.entry.kind === "dir" ? el.entry.children : []) : visibleFileTree(state);
      const files = nodes.map((entry) => new FileNode(entry));
      if (el) return files;
      return [
        new FileActionItem("Search files…", state.searchQuery || "all files", "search", "baic.searchFiles"),
        new FileActionItem("File format", state.formatFilter || "All formats", "filter", "baic.chooseFormat"),
        new FileActionItem("Select all results", `${searchResults(state).length} matching`, "check-all", "baic.selectSearchResults"),
        new ExportActionItem(selectionFiles(state).length, cfg().get<string>("transport") ?? "tar-gz"),
        ...files,
      ];
    }
  })();

  const exportTree = new (class implements vscode.TreeDataProvider<ArtifactItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<void>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;
    refresh() {
      this._onDidChangeTreeData.fire();
    }
    getTreeItem(el: ArtifactItem) {
      return el;
    }
    getChildren(): ArtifactItem[] {
      if (!state.lastExportDir) return [];
      const items = [new ArtifactItem("Output folder", vscode.Uri.file(state.lastExportDir))];
      if (state.lastPromptPath) items.push(new ArtifactItem("Agent Contract", vscode.Uri.file(state.lastPromptPath)));
      if (state.manifestPath) items.push(new ArtifactItem("Manifest", vscode.Uri.file(state.manifestPath)));
      for (const bundle of state.bundlePaths ?? []) {
        items.push(new ArtifactItem(basename(bundle), vscode.Uri.file(bundle)));
      }
      if (state.graphPath) items.push(new ArtifactItem("Code graph", vscode.Uri.file(state.graphPath)));
      return items;
    }
  })();

  let filesView: vscode.TreeView<vscode.TreeItem>;
  const updateFilesMessage = () => {
    if (!filesView) return;
    filesView.message = state.catalog
      ? `${searchResults(state).length} results · ${selectionFiles(state).length} selected · ${cfg().get<string>("transport") ?? "tar-gz"}. Export uses these results.`
      : "Open a trusted folder; the catalog loads automatically.";
  };
  const refreshAll = () => {
    filtersTree.refresh();
    filesTree.refresh();
    exportTree.refresh();
    updateFilesMessage();
  };

  const workspaceRoot = () => vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;

  const requireTrusted = (): boolean => {
    const message = denyUntrustedWrite(vscode.workspace.isTrusted);
    if (message) {
      vscode.window.showWarningMessage(message);
      return false;
    }
    return true;
  };

  const readMaxFileLines = () => {
    state.maxFileLines = cfg().get<number>("maxFileLines") ?? 3000;
  };

  const csv = (raw: string | undefined) =>
    (raw ?? "")
      .split(/[,;\s]+/)
      .map((t) => t.trim())
      .filter(Boolean);

  const scanOptions = () => ({
    includeSecretFiles: cfg().get<boolean>("includeSecretFiles") ?? false,
    forceIgnoredPaths: cfg().get<boolean>("forceIgnored") ? state.filters.paths : [],
    forceIncludeFormats: csv(cfg().get<string>("forceIncludeFormats")),
    excludePaths: csv(cfg().get<string>("excludePaths")),
  });

  const scanCmd = async (quiet = false) => {
    if (!requireTrusted()) return;
    const root = workspaceRoot();
    if (!root) {
      if (!quiet) vscode.window.showWarningMessage("Open a folder first.");
      return;
    }
    readMaxFileLines();
    await vscode.window.withProgress(
      {
        location: quiet ? vscode.ProgressLocation.Window : vscode.ProgressLocation.Notification,
        title: "Cataloging workspace",
        cancellable: true,
      },
      async (_p, token) => {
        try {
          const catalog = await scan(root, {
            ...scanOptions(),
            isCanceled: () => token.isCancellationRequested,
          });
          if (token.isCancellationRequested) return;
          applyScan(state, catalog);
          refreshAll();
        } catch (err) {
          if (err instanceof EngineCanceled) return;
          throw err;
        }
      },
    );
  };

  const exportCmd = async () => {
    if (!requireTrusted()) return;
    const root = workspaceRoot();
    if (!root) {
      vscode.window.showWarningMessage("Open a folder first.");
      return;
    }
    if (!state.catalog) await scanCmd(true);
    if (!state.catalog) {
      vscode.window.showWarningMessage("No catalog for this folder.");
      return;
    }
    readMaxFileLines();
    let includeSecretFiles = cfg().get<boolean>("includeSecretFiles") ?? false;
    if (includeSecretFiles) {
      const ok = await vscode.window.showWarningMessage(
        "Include secret-like files in this export?",
        { modal: true },
        "Include",
      );
      if (ok !== "Include") includeSecretFiles = false;
    }
    const files = selectionFiles(state);
    if (!files.length) {
      vscode.window.showWarningMessage("No files selected.");
      return;
    }
    const writeGraph = cfg().get<string>("writeGraph") ?? "off";
    const transport = (cfg().get<string>("transport") ?? "tar-gz") as "tar-gz" | "text";
    const forceBundle = cfg().get<boolean>("forceBundle") ?? false;
    const split = cfg().get<boolean>("split") ?? false;
    const task = cfg().get<string>("task")?.trim() || undefined;
    if (transport !== "tar-gz" && csv(cfg().get<string>("forceIncludeFormats")).length) {
      vscode.window.showWarningMessage("Force include formats requires gzip transport.");
      return;
    }
    if (transport === "tar-gz" && (cfg().get<boolean>("redact") ?? false)) {
      vscode.window.showWarningMessage("Redact requires text transport.");
      return;
    }
    await vscode.window.withProgress(
      { location: vscode.ProgressLocation.Notification, title: "Exporting AI context", cancellable: true },
      async (_p, token) => {
        try {
          const result = await exportCatalog(
            state.catalog!,
            { files, metadata: select(state.catalog!, { ...state.filters, excludePaths: csv(cfg().get<string>("excludePaths")) }).metadata },
            {
              outputDir: cfg().get<string>("outputDir") || undefined,
              maxFileLines: forceBundle ? 0 : exportMaxFileLines(state),
              redact: cfg().get<boolean>("redact") ?? false,
              projectOverview: cfg().get<boolean>("projectOverview") ?? false,
              writeGraph: writeGraph === "off" ? undefined : (writeGraph as "txt" | "json"),
              updateGitignore: cfg().get<boolean>("updateGitignore") ?? true,
              includeSecretFiles,
              transport,
              forceBundle,
              split,
              task,
              isCanceled: () => token.isCancellationRequested,
            },
          );
          recordExport(state, result);
          refreshAll();
          const pick = await vscode.window.showInformationMessage(
            `Exported ${result.filesExported} files to ${result.outputDir}`,
            "Open folder",
            "Open Agent Contract",
            "Copy path",
          );
          if (pick === "Open folder") {
            await vscode.commands.executeCommand("revealFileInOS", vscode.Uri.file(result.outputDir));
          } else if (pick === "Open Agent Contract") {
            const doc = await vscode.workspace.openTextDocument(result.promptPath);
            await vscode.window.showTextDocument(doc);
          } else if (pick === "Copy path") {
            await vscode.env.clipboard.writeText(result.outputDir);
          }
        } catch (err) {
          if (err instanceof EngineCanceled) return;
          throw err;
        }
      },
    );
  };

  filesView = vscode.window.createTreeView("baic.files", {
    treeDataProvider: filesTree,
    showCollapseAll: true,
  });
  updateFilesMessage();
  filesView.onDidChangeCheckboxState((e) => {
    for (const [item, box] of e.items) {
      if (!(item instanceof FileNode) || item.entry.kind !== "file") continue;
      if (box === vscode.TreeItemCheckboxState.Checked) state.checked.add(item.entry.relPath);
      else state.checked.delete(item.entry.relPath);
    }
    filesTree.refresh();
    updateFilesMessage();
  });

  const toggleSetting = async (key: string) => {
    const current = cfg().get<boolean>(key) ?? false;
    await cfg().update(key, !current, vscode.ConfigurationTarget.Workspace);
    refreshAll();
  };

  context.subscriptions.push(
    filesView,
    vscode.window.registerTreeDataProvider("baic.filters", filtersTree),
    vscode.window.registerTreeDataProvider("baic.export", exportTree),
    vscode.commands.registerCommand("baic.scan", () => scanCmd(false)),
    vscode.commands.registerCommand("baic.export", exportCmd),
    vscode.commands.registerCommand("baic.searchFiles", async () => {
      const value = await vscode.window.showInputBox({
        prompt: "Search file names, paths, and categories",
        placeHolder: "Try .kt, README, or java_kotlin",
        value: state.searchQuery,
      });
      if (value === undefined) return;
      state.searchQuery = value.trim();
      refreshAll();
    }),
    vscode.commands.registerCommand("baic.chooseFormat", async () => {
      const picked = await vscode.window.showQuickPick(["All formats", ...availableFormats(state)], {
        placeHolder: "Filter the search results by file format",
      });
      if (!picked) return;
      state.formatFilter = picked === "All formats" ? "" : picked;
      refreshAll();
    }),
    vscode.commands.registerCommand("baic.selectSearchResults", () => {
      selectSearchResults(state);
      refreshAll();
    }),
    vscode.commands.registerCommand("baic.restore", async () => {
      if (!requireTrusted()) return;
      const picked = await vscode.window.showOpenDialog({
        canSelectFiles: false,
        canSelectFolders: true,
        canSelectMany: false,
        title: "Select a gzip export folder (manifest + payload)",
      });
      if (!picked?.[0]) return;
      const dest = await vscode.window.showOpenDialog({
        canSelectFiles: false,
        canSelectFolders: true,
        canSelectMany: false,
        title: "Select an empty folder to restore into",
      });
      if (!dest?.[0]) return;
      try {
        const result = restoreExport(picked[0].fsPath, dest[0].fsPath, false);
        vscode.window.showInformationMessage(`Restored ${result.restoredCount} file(s) to ${result.destination}`);
      } catch (err) {
        const message = err instanceof RestoreError || err instanceof Error ? err.message : String(err);
        vscode.window.showErrorMessage(message);
      }
    }),
    vscode.commands.registerCommand("baic.cycleTransport", async () => {
      const current = cfg().get<string>("transport") ?? "tar-gz";
      await cfg().update("transport", current === "tar-gz" ? "text" : "tar-gz", vscode.ConfigurationTarget.Workspace);
      refreshAll();
    }),
    vscode.commands.registerCommand("baic.toggleForceBundle", () => toggleSetting("forceBundle")),
    vscode.commands.registerCommand("baic.toggleForceIgnored", async () => {
      await toggleSetting("forceIgnored");
      await scanCmd(true);
    }),
    vscode.commands.registerCommand("baic.toggleSplit", () => toggleSetting("split")),
    vscode.commands.registerCommand("baic.setExcludePaths", async () => {
      const value = await vscode.window.showInputBox({
        prompt: "Exclude paths (comma-separated, like history/,docs/,tests/)",
        value: cfg().get<string>("excludePaths") ?? "",
      });
      if (value === undefined) return;
      await cfg().update("excludePaths", value, vscode.ConfigurationTarget.Workspace);
      await scanCmd(true);
    }),
    vscode.commands.registerCommand("baic.setForceIncludeFormats", async () => {
      const value = await vscode.window.showInputBox({
        prompt: "Force-include formats for gzip (comma-separated, like .sqlite3)",
        value: cfg().get<string>("forceIncludeFormats") ?? "",
      });
      if (value === undefined) return;
      await cfg().update("forceIncludeFormats", value, vscode.ConfigurationTarget.Workspace);
      await scanCmd(true);
    }),
    vscode.commands.registerCommand("baic.refresh", scanCmd),
    vscode.commands.registerCommand("baic.toggleCategory", (category: string) => {
      toggleCategory(state, category);
      refreshAll();
    }),
    vscode.commands.registerCommand("baic.toggleFile", (relPath: string) => {
      if (state.checked.has(relPath)) state.checked.delete(relPath);
      else state.checked.add(relPath);
      refreshAll();
    }),
    vscode.commands.registerCommand("baic.setKeyword", async () => {
      const value = await vscode.window.showInputBox({ prompt: "Keyword to search in file content" });
      if (value === undefined) return;
      state.filters.keywords = value.trim() ? [value.trim()] : [];
      if (state.catalog) applyScan(state, state.catalog);
      refreshAll();
    }),
    vscode.commands.registerCommand("baic.setNameFilter", async () => {
      const value = await vscode.window.showInputBox({ prompt: "Filename substring filter" });
      if (value === undefined) return;
      setNameFilters(state, value);
      refreshAll();
    }),
    vscode.commands.registerCommand("baic.setPathFilter", async () => {
      const value = await vscode.window.showInputBox({
        prompt: "Path chips (comma-separated relative paths or names)",
        value: state.filters.paths.join(", "),
      });
      if (value === undefined) return;
      setPathFilters(state, value);
      refreshAll();
    }),
    vscode.commands.registerCommand("baic.clearFilters", () => {
      state.filters = emptyFilters();
      if (state.catalog) applyScan(state, state.catalog);
      refreshAll();
    }),
    vscode.commands.registerCommand("baic.selectAllSupported", () => {
      state.filters = emptyFilters();
      if (state.catalog) applyScan(state, state.catalog);
      refreshAll();
    }),
    vscode.commands.registerCommand("baic.addCurrentFile", () => {
      const root = workspaceRoot();
      const uri = vscode.window.activeTextEditor?.document.uri;
      if (!root || !uri || uri.scheme !== "file") return;
      addPath(state, relative(root, uri.fsPath).split("\\").join("/"));
      refreshAll();
    }),
    vscode.commands.registerCommand("baic.addExplorerPath", (uri?: vscode.Uri) => {
      const root = workspaceRoot();
      if (!root || !uri) return;
      addPath(state, relative(root, uri.fsPath).split("\\").join("/"));
      refreshAll();
    }),
    vscode.commands.registerCommand("baic.generateFiletree", async () => {
      if (!requireTrusted()) return;
      if (!state.catalog) await scanCmd();
      if (!state.catalog) return;
      const path = writeStandaloneFiletree(state.catalog, cfg().get<boolean>("updateGitignore") ?? true);
      vscode.window.showInformationMessage(`Filetree written: ${path}`);
    }),
    vscode.commands.registerCommand("baic.generateGraph", async () => {
      if (!requireTrusted()) return;
      if (!state.catalog) await scanCmd();
      if (!state.catalog) return;
      const format = (cfg().get<string>("writeGraph") === "json" ? "json" : "txt") as "txt" | "json";
      const path = writeStandaloneGraph(state.catalog, format, cfg().get<boolean>("updateGitignore") ?? true);
      vscode.window.showInformationMessage(`Code graph written: ${path}`);
    }),
    vscode.commands.registerCommand("baic.openLastExport", async () => {
      if (!state.lastExportDir) return;
      await vscode.commands.executeCommand("revealFileInOS", vscode.Uri.file(state.lastExportDir));
    }),
    vscode.commands.registerCommand("baic.openAgentContract", async () => {
      if (!state.lastPromptPath) return;
      const doc = await vscode.workspace.openTextDocument(state.lastPromptPath);
      await vscode.window.showTextDocument(doc);
    }),
    vscode.commands.registerCommand("baic.toggleRedact", () => toggleSetting("redact")),
    vscode.commands.registerCommand("baic.toggleSecrets", () => toggleSetting("includeSecretFiles")),
    vscode.commands.registerCommand("baic.toggleOverview", () => toggleSetting("projectOverview")),
    vscode.commands.registerCommand("baic.cycleGraph", async () => {
      const current = cfg().get<string>("writeGraph") ?? "off";
      const next = current === "off" ? "txt" : current === "txt" ? "json" : "off";
      await cfg().update("writeGraph", next, vscode.ConfigurationTarget.Workspace);
      refreshAll();
    }),
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration("baic")) refreshAll();
    }),
  );

  void scanCmd(true);
}

export function deactivate(): void {}
