import { basename, join, relative } from "node:path";
import * as vscode from "vscode";
import { scan } from "../../engine-ts/src/scan.ts";
import { select } from "../../engine-ts/src/select.ts";
import { EngineCanceled } from "../../engine-ts/src/types.ts";
import { exportCatalog, writeStandaloneFiletree, writeStandaloneGraph } from "../../engine-ts/src/write.ts";
import { setPolicyPath } from "../../engine-ts/src/policy.ts";
import { setPromptPath } from "../../engine-ts/src/write.ts";
import {
  addPath,
  applyScan,
  categoryChecked,
  createState,
  emptyFilters,
  exportMaxFileLines,
  recordExport,
  selectionFiles,
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
      entry.kind === "dir" ? vscode.TreeItemCollapsibleState.Expanded : vscode.TreeItemCollapsibleState.None,
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
  setPromptPath(join(context.extensionPath, "resources", "prompt.md"));

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

  const filesTree = new (class implements vscode.TreeDataProvider<FileNode> {
    private _onDidChangeTreeData = new vscode.EventEmitter<FileNode | void>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;
    refresh() {
      this._onDidChangeTreeData.fire();
    }
    getTreeItem(el: FileNode) {
      return el;
    }
    getChildren(el?: FileNode): FileNode[] {
      if (!state.catalog) return [];
      const nodes = el ? (el.entry.kind === "dir" ? el.entry.children : []) : visibleFileTree(state);
      return nodes.map((entry) => new FileNode(entry));
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

  const refreshAll = () => {
    filtersTree.refresh();
    filesTree.refresh();
    exportTree.refresh();
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

  const scanCmd = async () => {
    if (!requireTrusted()) return;
    const root = workspaceRoot();
    if (!root) {
      vscode.window.showWarningMessage("Open a folder first.");
      return;
    }
    readMaxFileLines();
    await vscode.window.withProgress(
      { location: vscode.ProgressLocation.Notification, title: "Scanning workspace", cancellable: true },
      async (_p, token) => {
        try {
          const catalog = await scan(root, {
            includeSecretFiles: cfg().get<boolean>("includeSecretFiles") ?? false,
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
    if (!root || !state.catalog) {
      vscode.window.showWarningMessage("Scan the workspace first.");
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
    await vscode.window.withProgress(
      { location: vscode.ProgressLocation.Notification, title: "Exporting AI context", cancellable: true },
      async (_p, token) => {
        try {
          const result = await exportCatalog(
            state.catalog!,
            { files, metadata: select(state.catalog!, state.filters).metadata },
            {
              outputDir: cfg().get<string>("outputDir") || undefined,
              maxFileLines: exportMaxFileLines(state),
              redact: cfg().get<boolean>("redact") ?? false,
              projectOverview: cfg().get<boolean>("projectOverview") ?? false,
              writeGraph: writeGraph === "off" ? undefined : (writeGraph as "txt" | "json"),
              updateGitignore: cfg().get<boolean>("updateGitignore") ?? true,
              includeSecretFiles,
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

  const filesView = vscode.window.createTreeView("baic.files", {
    treeDataProvider: filesTree,
    showCollapseAll: true,
  });
  filesView.onDidChangeCheckboxState((e) => {
    for (const [item, box] of e.items) {
      if (item.entry.kind !== "file") continue;
      if (box === vscode.TreeItemCheckboxState.Checked) state.checked.add(item.entry.relPath);
      else state.checked.delete(item.entry.relPath);
    }
    filesTree.refresh();
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
    vscode.commands.registerCommand("baic.scan", scanCmd),
    vscode.commands.registerCommand("baic.export", exportCmd),
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
}

export function deactivate(): void {}
