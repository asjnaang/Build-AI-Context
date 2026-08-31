import * as vscode from "vscode";
import { join, relative } from "node:path";
import { scan } from "../../engine-ts/src/scan.ts";
import { select } from "../../engine-ts/src/select.ts";
import { applyMaxFileLines } from "../../engine-ts/src/select.ts";
import { exportCatalog, writeStandaloneFiletree, writeStandaloneGraph } from "../../engine-ts/src/write.ts";
import { setPolicyPath } from "../../engine-ts/src/policy.ts";
import { setPromptPath } from "../../engine-ts/src/write.ts";
import {
  addPath,
  applyScan,
  createState,
  emptyFilters,
  selectionFiles,
  toggleCategory,
  type HostState,
} from "./state.ts";
import type { SourceFile } from "../../engine-ts/src/types.ts";

class FilterItem extends vscode.TreeItem {
  constructor(
    public readonly category: string,
    count: number,
    checked: boolean,
  ) {
    super(`${checked ? "$(check) " : ""}${category} (${count})`, vscode.TreeItemCollapsibleState.None);
    this.contextValue = "baicCategory";
    this.command = { command: "baic.toggleCategory", title: "Toggle", arguments: [category] };
  }
}

class FileItem extends vscode.TreeItem {
  constructor(public readonly file: SourceFile, checked: boolean, oversized: boolean) {
    super(`${checked ? "$(check) " : "$(circle-slash) "}${file.relPath}`, vscode.TreeItemCollapsibleState.None);
    this.description = `${file.lineCount} lines`;
    this.contextValue = "baicFile";
    if (oversized) this.iconPath = new vscode.ThemeIcon("warning");
    this.command = { command: "baic.toggleFile", title: "Toggle", arguments: [file.relPath] };
  }
}

class ArtifactItem extends vscode.TreeItem {
  constructor(label: string, uri: vscode.Uri) {
    super(label, vscode.TreeItemCollapsibleState.None);
    this.resourceUri = uri;
    this.command = { command: "vscode.open", title: "Open", arguments: [uri] };
  }
}

export function activate(context: vscode.ExtensionContext): void {
  setPolicyPath(join(context.extensionPath, "..", "policy", "policy.json"));
  setPromptPath(join(context.extensionPath, "..", "engine-ts", "prompt.md"));

  const state: HostState = createState(
    vscode.workspace.getConfiguration("baic").get<number>("maxFileLines") ?? 3000,
  );

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
      if (!state.catalog) return [];
      const counts = new Map<string, number>();
      for (const f of state.catalog.files) counts.set(f.category, (counts.get(f.category) ?? 0) + 1);
      const selected = new Set(state.filters.categories);
      const allSelected = selected.size === 0;
      return [...counts.entries()]
        .sort((a, b) => (a[0] < b[0] ? -1 : 1))
        .map(([cat, n]) => new FilterItem(cat, n, allSelected || selected.has(cat)));
    }
  })();

  const filesTree = new (class implements vscode.TreeDataProvider<FileItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<void>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;
    refresh() {
      this._onDidChangeTreeData.fire();
    }
    getTreeItem(el: FileItem) {
      return el;
    }
    getChildren(): FileItem[] {
      if (!state.catalog) return [];
      const selected = select(state.catalog, state.filters);
      const { included, oversized } = applyMaxFileLines(selected, state.maxFileLines);
      const oversizedSet = new Set(oversized.map((f) => f.relPath));
      return [...included, ...oversized].map(
        (f) => new FileItem(f, state.checked.has(f.relPath), oversizedSet.has(f.relPath)),
      );
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
      const dir = vscode.Uri.file(state.lastExportDir);
      return [
        new ArtifactItem("Output folder", dir),
        ...(state.lastPromptPath
          ? [new ArtifactItem("Agent Contract", vscode.Uri.file(state.lastPromptPath))]
          : []),
      ];
    }
  })();

  const refreshAll = () => {
    filtersTree.refresh();
    filesTree.refresh();
    exportTree.refresh();
  };

  const workspaceRoot = () => vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;

  const scanCmd = async () => {
    if (!vscode.workspace.isTrusted) {
      vscode.window.showWarningMessage("Trust this workspace to scan.");
      return;
    }
    const root = workspaceRoot();
    if (!root) {
      vscode.window.showWarningMessage("Open a folder first.");
      return;
    }
    const cfg = vscode.workspace.getConfiguration("baic");
    await vscode.window.withProgress(
      { location: vscode.ProgressLocation.Notification, title: "Scanning workspace", cancellable: true },
      async () => {
        const catalog = await scan(root, {
          includeSecretFiles: cfg.get<boolean>("includeSecretFiles") ?? false,
        });
        applyScan(state, catalog);
        refreshAll();
      },
    );
  };

  const exportCmd = async () => {
    if (!vscode.workspace.isTrusted) {
      vscode.window.showWarningMessage("Trust this workspace to export.");
      return;
    }
    const root = workspaceRoot();
    if (!root || !state.catalog) {
      vscode.window.showWarningMessage("Scan the workspace first.");
      return;
    }
    const cfg = vscode.workspace.getConfiguration("baic");
    if (cfg.get<boolean>("includeSecretFiles")) {
      const ok = await vscode.window.showWarningMessage(
        "Include secret-like files in this export?",
        { modal: true },
        "Include",
      );
      if (ok !== "Include") return;
    }
    const files = selectionFiles(state);
    if (!files.length) {
      vscode.window.showWarningMessage("No files selected.");
      return;
    }
    const writeGraph = cfg.get<string>("writeGraph") ?? "off";
    await vscode.window.withProgress(
      { location: vscode.ProgressLocation.Notification, title: "Exporting AI context", cancellable: true },
      async (_p, token) => {
        if (token.isCancellationRequested) return;
        const result = await exportCatalog(
          state.catalog!,
          { files, metadata: select(state.catalog!, state.filters).metadata },
          {
            outputDir: cfg.get<string>("outputDir") || undefined,
            maxFileLines: cfg.get<number>("maxFileLines") ?? 3000,
            redact: cfg.get<boolean>("redact") ?? false,
            projectOverview: cfg.get<boolean>("projectOverview") ?? false,
            writeGraph: writeGraph === "off" ? undefined : (writeGraph as "txt" | "json"),
            updateGitignore: cfg.get<boolean>("updateGitignore") ?? true,
          },
        );
        state.lastExportDir = result.outputDir;
        state.lastPromptPath = result.promptPath;
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
      },
    );
  };

  context.subscriptions.push(
    vscode.window.registerTreeDataProvider("baic.filters", filtersTree),
    vscode.window.registerTreeDataProvider("baic.files", filesTree),
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
      if (!state.catalog) {
        await scanCmd();
      }
      if (!state.catalog) return;
      const path = writeStandaloneFiletree(state.catalog);
      vscode.window.showInformationMessage(`Filetree written: ${path}`);
    }),
    vscode.commands.registerCommand("baic.generateGraph", async () => {
      if (!state.catalog) await scanCmd();
      if (!state.catalog) return;
      const format =
        (vscode.workspace.getConfiguration("baic").get<string>("writeGraph") === "json" ? "json" : "txt") as
          | "txt"
          | "json";
      const path = writeStandaloneGraph(state.catalog, format);
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
    vscode.commands.registerCommand("baic.toggleRedact", async () => {
      const cfg = vscode.workspace.getConfiguration("baic");
      await cfg.update("redact", !cfg.get<boolean>("redact"), vscode.ConfigurationTarget.Workspace);
    }),
  );
}

export function deactivate(): void {}
