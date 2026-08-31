# IDE Hosts for Build AI Context

**Date:** 2026-08-31
**Status:** proposed — waiting on approval of `plan.md`
**Branch:** `feat/ide-plugins`

## Problem

`build-ai-context` / `baic` (v1.0.12) already scans a Workspace, selects files, and writes Bundles + Manifest + Filetree + optional Code Graph + overview + Agent Contract. It is a Python CLI. Developers who cannot install or run Python — typical in locked-down IntelliJ and VS Code shops — cannot use it. A Flet GUI on `main_gui` does not help: it is still Python.

## What we are building

Two Hosts that drive the same Engine the CLI drives, with **no Python at runtime**:

1. A **VS Code extension** (also installable in Cursor / VSCodium / compatible editors via Marketplace + Open VSX).
2. An **IntelliJ Platform plugin** that declares `com.intellij.modules.platform`, so it loads in IntelliJ IDEA, Android Studio, WebStorm, PyCharm, GoLand, Rider, CLion, PhpStorm, and other IntelliJ-based IDEs.

Visual Studio (the Windows IDE) is **not** v1. See ADR 0002.

The Python CLI stays. Hosts are additional, not a replacement.

## Architecture

```
                    ┌──────────────────────────┐
                    │  packages/engine-policy  │
                    │  policy.json (constants, │
                    │  regexes, limits)        │
                    └────────────┬─────────────┘
           ┌─────────────────────┼─────────────────────┐
           ▼                     ▼                     ▼
   ┌───────────────┐     ┌───────────────┐     ┌───────────────┐
   │ engine-ts     │     │ engine-kt     │     │ Python CLI    │
   │ (VS Code      │     │ (IntelliJ     │     │ (parity       │
   │  in-process)  │     │  in-process)  │     │  oracle)      │
   └───────┬───────┘     └───────┬───────┘     └───────┬───────┘
           ▼                     ▼                     ▼
   VS Code Host            IntelliJ Host           baic / TTY
   TreeView + commands     Tool Window + Actions   existing UX
```

**Seam:** the Engine interface (scan → select → export / filetree / graph). Hosts never reimplement ignore rules, chunk math, or Bundle headers.

**Depth:** a Host calls a handful of Engine functions and maps Catalog/Selection/ExportResult onto native widgets. All format and policy complexity stays behind that interface.

**Two ports, one contract:** TypeScript in-process for VS Code; Kotlin in-process for IntelliJ. Neither Host requires the other's runtime. Drift is caught by golden artifacts generated from today's Python CLI (ADR 0003, 0006). `policy.json` is extracted from `constants.py` / `redact.py`; a Python test fails if they diverge.

**Rejected:** shelling out to `baic`; PyInstaller sidecar; cloning the five-step terminal wizard into a Webview.

## Engine interface

Language-neutral. Names below are TypeScript; Kotlin mirrors them.

```ts
interface ScanOptions {
  includeSecretFiles: boolean;
}

interface SourceFile {
  relPath: string;
  absPath: string;
  category: string;
  lineCount: number;
  sizeBytes: number;
  sha256: string; // sha256 of lines joined by \n, matching current CLI
  lines: string[];
}

interface Catalog {
  workspace: string;
  files: SourceFile[]; // sorted by posix relPath
  skipped: Record<string, number>;
}

interface Filters {
  categories: string[];  // empty = no category constraint
  paths: string[];       // empty = no path constraint
  nameFilters: string[]; // substring of filename
  keywords: string[];    // substring of file text, case-insensitive
}

interface SelectionMetadata {
  selectionMode: "composed";
  selectedCategories: string[];
  selectedPaths: string[];
  nameFilters: string[];
  missingPaths: string[];
}

interface Selection {
  files: SourceFile[];
  metadata: SelectionMetadata;
}

interface ExportOptions {
  outputDir?: string;          // default: exported_sources_{name}_{timestamp}
  maxFileLines: number;        // default 3000; 0 = unlimited
  redact: boolean;             // default false
  projectOverview: boolean;    // default false
  writeGraph?: "txt" | "json"; // default undefined (off)
  updateGitignore: boolean;    // default true
}

interface ExportResult {
  outputDir: string;
  manifestPath: string;
  bundlePaths: string[];
  filetreeEmbedded: true;      // always embedded in bundle 001, matching CLI
  graphPath?: string;
  overviewPath?: string;
  promptPath: string;
  filesExported: number;
  bundlesCreated: number;
  warnings: Array<Record<string, unknown>>;
  skippedDuringPack: Array<Record<string, unknown>>;
}

interface Engine {
  scan(workspace: string, options: ScanOptions): Promise<Catalog>;
  select(catalog: Catalog, filters: Filters): Selection;
  applyMaxFileLines(selection: Selection, maxFileLines: number): {
    included: SourceFile[];
    oversized: SourceFile[];
  };
  export(catalog: Catalog, selection: Selection, options: ExportOptions): Promise<ExportResult>;
  filetree(catalog: Catalog): string;
  graph(catalog: Catalog, format: "txt" | "json"): string;
}
```

Scan, ignore, category detection, intelligent path parsing, keyword filter, chunk/pack (8000-line Bundles, 1500 warn, 3000 skip), redaction, Manifest schema, Filetree text, Code Graph txt/json, overview heuristics, Agent Contract copy, and `.gitignore` updates must match current code in `src/build_ai_context/`, not the README where they disagree.

Known CLI mismatches Hosts must **not** "fix" in v1 except where called out:

| Topic | Follow |
|---|---|
| Bundle header form | `chunking.bundle_header` (`===== BEGIN FILE`, not README's `# ===== BEGIN FILE`) |
| `{project}_readme_*.txt` | Do not write it (README lists it; code does not) |
| Nested `.gitignore` | Root `.gitignore` only |
| `--keywords` excluding categories/paths | Hosts **compose** filters (ADR 0005) — deliberate Host improvement |
| `--tree`/`--graph` writing into Workspace | Hosts write those artifacts into the Export directory when requested from the panel; dedicated commands may still write beside the Workspace to match CLI. Default for panel Export: graph goes in the Export dir; Filetree stays embedded in bundle 001 as today. A "Generate Filetree / Graph only" command matches CLI placement (Workspace root + gitignore). |
| `--update-headers` | Out of Hosts |
| `--fancy-ui` | Dead in CLI; ignore |

## Host UX

One persistent panel, not a wizard.

### VS Code

- Activity Bar View Container **AI Context**.
- Views (TreeView, not Webview):
  - **Filters** — checkable Categories with counts; items for keyword, redact, secrets, overview, graph format; title actions Scan / Refresh.
  - **Files** — checkable tree of the current Selection, grouped by folder, description = line count; oversized files warned and unchecked by default.
  - **Export** — last Export artifacts, or a Welcome view with the primary "Export" button when none exist.
- Command Palette commands for every action (Scan, Export, Add Current File, Add Explorer Path, Set Keyword, Clear Filters, Select All Supported, Generate Filetree, Generate Graph, Open Last Export, Open Agent Contract, Toggle Redact).
- Explorer and editor context menus: **Add to AI Context**.
- Settings under `baic.*`.
- `withProgress` + cancellation for scan/export.
- Notification on success: Open folder / Open Agent Contract / Copy output path.
- First-run Walkthrough: open panel → scan → filter → export → upload Bundles + Agent Contract.
- `untrustedWorkspaces.supported: "limited"` — no scan/export until trusted.
- `extensionKind: ["workspace"]` so Remote SSH runs next to the files.
- Desktop only in v1 (no VS Code Web / `vscode.dev`).

Webviews are not used in v1 ([do not use webviews for wizards](https://code.visualstudio.com/api/ux-guidelines/webviews)).

### IntelliJ Platform

- Declarative Tool Window **AI Context** (anchor right, `com.intellij.toolWindow`), `SimpleToolWindowPanel` + Kotlin UI DSL.
- Toolbar Actions: Scan, Export, Refresh, Clear.
- CheckboxTree of files; filter row (category checkboxes, keyword field, path chip list).
- Actions in Tools menu, Project View popup, Editor popup (`Add to AI Context`).
- Settings → Tools → Build AI Context (same keys as `baic.*`).
- `ProgressIndicator` for scan/export; cancellable.
- Notification group with Reveal / Open Agent Contract.
- `com.intellij.modules.platform` only — no Java-only APIs — so all IntelliJ-based IDEs load it.
- v1 is local projects. Split/remote (Gateway) is a later backend-module split; do not block v1 on it.

### Copy

Host strings are clean English. Do not carry CLI typos (`unecessary`, `promt.md`). Product name in UI: **Build AI Context**. Command prefix: `baic`.

## Data flow

1. User opens a Workspace. Host shows an empty panel + Walkthrough / Welcome.
2. Scan → Engine.scan → Catalog cached in Host memory. Category counts render.
3. User adjusts Filters (or Add to AI Context from explorer). Engine.select → Files view.
4. Oversized files appear with a warning; unchecked unless the user checks them (`maxFileLines: 0` for those).
5. Export → Engine.export with current Selection (checked files, not merely the filter result).
6. Host reveals the output directory, lists artifacts in the Export view, offers Open Agent Contract.
7. Catalog stays cached (CLI "export more") until Refresh.

## Error handling

| Case | Host behavior |
|---|---|
| No Workspace folder | Welcome view: "Open a folder first." |
| No supported files | Warning in the panel; Export disabled. |
| Empty Selection | Export disabled; "No files selected." |
| Untrusted workspace | Commands hidden; no file writes. |
| Include secret files | Extra confirmation dialog. |
| `.gitignore` update fails | Export still succeeds; warn. |
| Disk write failure | Error notification; no partial "success." If some Bundles were written, say so. |
| Cancellation | Partial output directory left; user can delete. Do not mutate gitignore on cancel. |

## Testing

- **Policy lock:** Python test that `constants.py` + redaction pattern names match `policy.json`.
- **Golden fixtures:** small Workspaces under `ide/testdata/workspaces/`; Python CLI generates expected Bundles/Manifest/Filetree/Graph with timestamps stripped; both Engine ports must match.
- **Engine unit tests:** port the behaviors in `tests/test_scanner.py`, `test_redact.py`, `test_graph.py`, `test_large_file_cli.py`, `test_icons_and_filetree.py` that encode domain rules.
- **VS Code:** `@vscode/test-electron` — scan a fixture workspace, toggle a category, export, assert files exist.
- **IntelliJ:** Gradle unit tests for engine-kt; one plugin test that the tool window factory creates content.

## Out of scope (v1)

- Visual Studio (full) VSIX
- VS Code Web / `vscode.dev`
- Copilot Chat participant / auto-upload to any model
- Code Graph visualization Webview
- MCP server
- `--update-headers`
- Flet GUI revival
- `gdwf_export.py` / `universal_code_to_text_exporter.py`
- Tree-sitter native extra (use the same heuristic-or-stdlib path the CLI uses without `[graph]`)
- Nested gitignore (CLI does not)
- Changing Python CLI behavior except the policy-lock test

## Distribution (after implementation, still needs a human)

- VS Code Marketplace via `vsce` + a publisher id (human creates publisher; PAT/Entra) ([publishing](https://code.visualstudio.com/api/working-with-extensions/publishing-extension))
- Open VSX for VSCodium
- JetBrains Marketplace (human JetBrains account)
- MIT, same as the CLI
- Plugin versions start at `0.1.0`, independent of PyPI `1.0.12`, and record `enginePolicyVersion` matching the policy file
