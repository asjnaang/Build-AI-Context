import { join, relative } from "node:path";
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
  createState,
  emptyFilters,
  exportMaxFileLines,
  recordExport,
  selectionFiles,
  selectSearchResults,
  setNameFilters,
  setPathFilters,
  setSearchResultsChecked,
  toggleCategory,
  type HostState,
} from "./state.ts";
import { denyUntrustedWrite } from "./trust.ts";
import { BaicPanelView, type PanelMessage } from "./panel.ts";
import { panelSnapshot } from "./panelModel.ts";

function cfg() {
  return vscode.workspace.getConfiguration("baic");
}

export function activate(context: vscode.ExtensionContext): void {
  setPolicyPath(join(context.extensionPath, "resources", "policy.json"));
  setPromptDir(join(context.extensionPath, "resources"));

  const state: HostState = createState();
  const panelSettings = () => ({
    transport: cfg().get<string>("transport") ?? "tar-gz",
    forceBundle: cfg().get<boolean>("forceBundle") ?? false,
    forceIgnored: cfg().get<boolean>("forceIgnored") ?? false,
    split: cfg().get<boolean>("split") ?? false,
    excludePaths: cfg().get<string>("excludePaths") ?? "",
    forceIncludeFormats: cfg().get<string>("forceIncludeFormats") ?? "",
  });
  const snapshot = () => panelSnapshot(state, panelSettings());
  let panelView: BaicPanelView;
  const refreshAll = () => panelView?.refresh();

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

  const toggleSetting = async (key: string) => {
    const current = cfg().get<boolean>(key) ?? false;
    await cfg().update(key, !current, vscode.ConfigurationTarget.Workspace);
    refreshAll();
  };

  const handlePanelMessage = (message: PanelMessage) => {
    switch (message.type) {
      case "search":
        state.searchQuery = message.value;
        refreshAll();
        return;
      case "format":
        state.formatFilter = message.value;
        refreshAll();
        return;
      case "selectAll":
        setSearchResultsChecked(state, message.checked);
        refreshAll();
        return;
      case "toggleFile":
        if (message.checked) state.checked.add(message.path);
        else state.checked.delete(message.path);
        refreshAll();
        return;
      case "toggleCategory":
        toggleCategory(state, message.category);
        refreshAll();
        return;
      case "export":
        void exportCmd();
        return;
      case "restore":
        void vscode.commands.executeCommand("baic.restore");
        return;
      case "refresh":
        void scanCmd(false);
        return;
      case "transport":
        void cfg().update("transport", message.value, vscode.ConfigurationTarget.Workspace).then(refreshAll);
        return;
      case "keywords":
        state.filters.keywords = message.value.trim() ? [message.value.trim()] : [];
        if (state.catalog) applyScan(state, state.catalog);
        refreshAll();
        return;
      case "paths":
        setPathFilters(state, message.value);
        refreshAll();
        return;
      case "setting":
        void cfg().update(message.key, message.checked, vscode.ConfigurationTarget.Workspace).then(async () => {
          if (message.key === "forceIgnored") await scanCmd(true);
          else refreshAll();
        });
        return;
      case "excludePaths":
        void cfg().update("excludePaths", message.value, vscode.ConfigurationTarget.Workspace).then(() => scanCmd(true));
        return;
      case "extraFormats":
        void cfg().update("forceIncludeFormats", message.value, vscode.ConfigurationTarget.Workspace).then(() => scanCmd(true));
        return;
      case "openFolder":
        void vscode.commands.executeCommand("baic.openLastExport");
        return;
      case "openManifest":
        if (state.manifestPath) void vscode.commands.executeCommand("vscode.open", vscode.Uri.file(state.manifestPath));
        return;
      case "openPrompt":
        void vscode.commands.executeCommand("baic.openAgentContract");
        return;
    }
  };

  panelView = new BaicPanelView(snapshot, handlePanelMessage);

  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(BaicPanelView.viewId, panelView),
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
