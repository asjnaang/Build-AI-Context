# IDE Hosts (VS Code + IntelliJ) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Do not implement until the user approves this file.** This branch currently contains planning artifacts only.

**Goal:** Ship a VS Code extension and an IntelliJ Platform plugin that give developers who cannot run Python the same Export capabilities as `baic`, using native IDE UX.

**Architecture:** One Engine contract (policy JSON + artifact formats + golden fixtures) with two in-process ports (TypeScript for VS Code, Kotlin for IntelliJ). Hosts are thin adapters: TreeView / Tool Window + commands. The Python CLI stays the CLI Host and the v1 parity oracle.

**Tech Stack:** TypeScript + VS Code Extension API; Kotlin + IntelliJ Platform Gradle Plugin 2.x; shared `policy.json`; Python 3.9+ CLI unchanged except a policy-lock test; golden fixtures from current `baic` 1.0.12.

## Global Constraints

- No Python, Node, or JRE required of the *user* of either Host (VS Code already has Node; IntelliJ already has a JRE — we do not add a third runtime).
- Engine behavior matches current code in `src/build_ai_context/`, not README where they disagree.
- Bundle cap is 8000 lines; `--max-file-lines` default 3000; redaction off; secret files skipped.
- MIT license; public repo; no telemetry.
- Product UI name: **Build AI Context**. Command prefix: `baic`.
- Do not revive the Flet GUI on `main_gui`.
- Do not implement Visual Studio (full) in this plan.
- Do not publish to marketplaces until a human creates publisher accounts.

**Supporting docs:** `CONTEXT.md`, `docs/adr/0001`–`0006`, `docs/superpowers/specs/2026-08-31-ide-plugins-design.md`.

---

## How this plan was produced

The user asked for `/ask-matt` → grill → UI/UX plan → `plan.md`, and said they were stepping away: do not block on interview rounds. I ran `/grilling` and `/grill-with-docs` against the repo and primary IDE docs, then **applied the recommended answer on every frontier question**. Glossary and ADRs were written as terms and trade-offs locked.

**Override anything below before build.** If a recommended action is wrong, change it here first.

Primary sources used for Host UX and platforms:

- VS Code UX guidelines: https://code.visualstudio.com/api/ux-guidelines/overview
- VS Code webviews (do not use for wizards): https://code.visualstudio.com/api/ux-guidelines/webviews
- VS Code views: https://code.visualstudio.com/api/ux-guidelines/views
- VS Code publishing: https://code.visualstudio.com/api/working-with-extensions/publishing-extension
- IntelliJ plugin compatibility: https://plugins.jetbrains.com/docs/intellij/plugin-compatibility.html
- IntelliJ tool windows: https://plugins.jetbrains.com/docs/intellij/tool-windows.html
- Visual Studio extensibility models (why it is a third platform): https://learn.microsoft.com/en-us/visualstudio/extensibility/visualstudio.extensibility/extensibility-models?view=visualstudio

---

## Decision log (recommended action per decision)

Each item is a grilling question, the options, the recommended answer, and the **action** to take on approval.

### D1 — What does “VSStudio” mean?

**Options:** Visual Studio Code; Visual Studio (Windows IDE); both in v1.

**Recommended:** Visual Studio Code (Marketplace + Open VSX). Visual Studio 2022/2026 is a different stack (C# VSIX / VisualStudio.Extensibility) and a third Host.

**Action:** Build `ide/vscode/`. Track Visual Studio (full) as a later Host on the same Engine contract, not in this plan.

### D2 — What does “IntelliJ” mean?

**Options:** IntelliJ IDEA only; Android Studio only; all IntelliJ Platform IDEs.

**Recommended:** One plugin depending on `com.intellij.modules.platform` so every IntelliJ-based IDE can load it.

**Action:** `plugin.xml` declares `<depends>com.intellij.modules.platform</depends>` and no Java-only APIs. Marketplace compatibility will then include IDEA, Android Studio, WebStorm, PyCharm, GoLand, Rider, CLion, PhpStorm, etc.

### D3 — Keep the Python CLI?

**Options:** Replace it; freeze it as the plugin engine; keep it as a first-class Host.

**Recommended:** Keep it. Plugins are additional Hosts. Python remains the parity oracle for v1.

**Action:** Do not delete or wrap `src/build_ai_context/` as the plugin runtime. Add only a policy-lock test.

### D4 — How does the Engine run without Python?

**Options:** (A) Shell out to `baic` if installed; (B) PyInstaller sidecar; (C) one Rust/Go binary; (D) TypeScript engine + compiled binary for IntelliJ; (E) TypeScript + Kotlin in-process ports + golden tests.

**Recommended:** **E**. Native on both platforms, no extra runtime, no notarized native binary in v1. The industry pattern for language tools (ruff, rust-analyzer, clangd) is a bundled native JSON-RPC binary; that is the revisit if golden tests start failing from dual-port drift. Cited notes: `docs/ide-plugins/research-ide-platforms.md`.

**Action:** Implement `ide/engine-ts` and `ide/intellij` `:engine` (Kotlin) against `ide/policy/policy.json` and `ide/testdata/golden/`. CI fails a port that mismatches golden artifacts. Do not freeze CPython into either Host.

### D5 — Where do constants live so two ports do not drift?

**Options:** Copy tables by hand; generate from Python at build; shared `policy.json` that Python also must match.

**Recommended:** Shared `policy.json`. Python test asserts `constants.py` / redaction pattern inventory match it.

**Action:** Task 1 extracts policy from current Python. Ports load the JSON. Do not “improve” skip lists in the Hosts.

### D6 — UI: wizard, webview, or native panel?

**Options:** Clone the 5-mode CLI wizard; custom HTML Webview; Source-Control-like native panel.

**Recommended:** Native panel. VS Code forbids webview wizards; IntelliJ wants a Tool Window.

**Action:** VS Code Activity Bar container + TreeViews + Quick Picks + Settings. IntelliJ Tool Window + Actions + Settings. No Webview in v1.

### D7 — How do the five CLI selection modes map?

**Options:** Five exclusive modes; composed filters.

**Recommended:** Composed filters (empty = all supported). This is capability parity plus a UX upgrade. CLI `--keywords` ignoring other flags is not reproduced.

**Action:** Host Filters = categories ∩ paths ∩ name-filters ∩ keywords (a constraint is skipped when empty). File tree checkboxes are the final Selection (user can uncheck). Oversized files shown, warned, unchecked by default.

### D8 — What CLI features are in v1 Hosts?

**In:** scan; select (all/category/path/mixed/keyword as composed filters); confirm file list; oversized override; Bundles + Manifest + Agent Contract; Filetree (embedded in bundle 001; dedicated command writes Workspace-root file like CLI `--tree`); Code Graph (txt/json); project overview; redact; include-secret-files with confirm; max-file-lines; output dir; repeat Export from cached Catalog; gitignore update (setting, default on); reveal output.

**Out:** `--update-headers`; Flet GUI; `gdwf_export.py`; `universal_code_to_text_exporter.py`; Copilot/chat upload; graph visualization; MCP; VS Code Web; Visual Studio (full); tree-sitter extra (heuristics + Python `ast` equivalent in TS via regex/heuristics matching CLI without `[graph]`).

**Action:** Implement the In list. Do not implement the Out list. Parity matrix is below.

### D9 — Byte-identical artifacts?

**Recommended:** Yes, after normalizing timestamps / `created_at_utc`. Follow **code** where README is wrong (bundle header form; no `*_readme_*.txt`).

**Action:** Golden tests. Hosts write the same BEGIN/END form as `chunking.bundle_header`.

### D10 — Default output location

**Recommended:** Same as CLI: `exported_sources_{project}_{YYYYMMDDTHHMMSSZ}/` under the Workspace (cwd equivalent = Workspace folder). Setting overrides.

**Action:** Setting `baic.outputDir` empty means CLI default. Dedicated Filetree/Graph commands write beside the Workspace like `--tree`/`--graph`.

### D11 — Mutate `.gitignore`?

**Recommended:** Yes, same patterns as `filetree.update_gitignore`, behind `baic.updateGitignore` default true. Skip the mutation if the user cancelled.

**Action:** Engine function `updateGitignore(workspace)` used by both Hosts and covered by golden/unit tests already present in Python.

### D12 — Chat / Copilot integration in v1?

**Recommended:** No. Write files; offer Open Agent Contract / Copy path. Auto-upload is a different product.

**Action:** Success notification actions only. No Language Model / Chat participant in v1.

### D13 — Monorepo or separate plugin repos?

**Recommended:** Monorepo under `ide/` so golden tests and policy stay in one CI.

**Action:** Layout in the file map below. Python package layout unchanged for PyPI.

### D14 — Versioning

**Recommended:** Hosts start at `0.1.0`. Independent of PyPI `1.0.12`. Record `enginePolicyVersion` in Manifest `tool` metadata as `build-ai-context-ide/<policy version>`.

**Action:** Do not bump Python to 2.0 for this. Do not claim plugin == PyPI version.

### D15 — Telemetry, trust, secrets

**Recommended:** No telemetry. VS Code Restricted Mode: no scan/export. Include-secret-files requires a confirmation dialog. Redact off by default.

**Action:** `untrustedWorkspaces.supported: "limited"`. IntelliJ: disable actions when no project. Confirm dialog before `includeSecretFiles: true`.

### D16 — What about `main_gui`?

**Recommended:** Leave the branch. Do not merge Flet. It requires Python and is a different package name (`anything-to-text`).

**Action:** No code taken from `src/anything_to_text/gui.py`.

### D17 — Tracer-bullet order

**Recommended:** Policy + golden fixtures → TypeScript Engine (test-first) → VS Code Host (first installable) → Kotlin Engine → IntelliJ Host. Both Hosts ship in the same effort; VS Code is the first thing a reviewer can install from a VSIX.

**Action:** Follow the task order in this file. Do not start IntelliJ UI before engine-kt matches goldens.

### D18 — Marketplace publish in this work?

**Recommended:** Package VSIX and IntelliJ zip in CI; do **not** publish until the user creates publisher accounts (Azure DevOps Visual Studio Marketplace, Eclipse Open VSX for Cursor/VSCodium, JetBrains Marketplace). That is a human-only step.

**Action:** After implementation approval, packaging tasks only. Publishing waits. Dual-publish the same `publisher.name` to Marketplace and Open VSX.

---

## CLI → Host parity matrix

| CLI | Host |
|---|---|
| `baic` interactive menu | Persistent **AI Context** panel |
| mode 1 all | Empty filters + Select all (checked) |
| mode 2 category | Category checkboxes with counts |
| mode 3 path | Explorer/editor **Add to AI Context**; path chips; Quick Pick |
| mode 4 mixed | Categories + paths + filename filter field |
| mode 5 keyword | Keyword field / `baic.setKeyword` |
| confirm checkbox list | Files TreeView / CheckboxTree |
| oversized prompt | Unchecked warned nodes; user can check |
| “export more?” cached scan | Panel stays open; Refresh rescan |
| `--non-interactive` / `--all` | Export current checks |
| `--categories` / `--paths` / `--keywords` | Composed Filters (keywords **do** combine) |
| `--max-file-lines` | Setting + Filters item |
| `--output-dir` | Setting |
| `--redact` | Toggle + setting, default off |
| `--include-secret-files` | Toggle + confirm |
| `--project-overview` | Toggle |
| `--tree` | Command **Generate Filetree** (Workspace root) |
| `--graph` `--format` | Command **Generate Code Graph**; panel option includes graph in Export dir |
| `--version` | Extension/plugin version in marketplace + About |
| `--update-headers` | **Not in Hosts** |
| `--fancy-ui` | **Ignore** (dead flag) |
| `prompt.md` copy | Always written; **Open Agent Contract** action |
| `.gitignore` update | Setting, default on |
| Rich tables | Category counts on filter items |

---

## File map (created on implementation)

```
ide/
  policy/
    policy.json              # categories, aliases, excludes, secrets, limits
    policy.schema.json
  testdata/
    workspaces/small-py/     # fixture Workspace
    workspaces/mixed-langs/
    golden/small-py/         # normalized CLI output
    generate_goldens.py      # runs baic, strips timestamps
  engine-ts/
    package.json
    src/index.ts             # Engine interface + facade
    src/scan.ts
    src/select.ts
    src/chunk.ts
    src/redact.ts
    src/write.ts
    src/filetree.ts
    src/graph.ts
    src/gitignore.ts
    src/policy.ts
    test/*.test.ts
  vscode/
    package.json             # contribution points
    src/extension.ts
    src/engineAdapter.ts     # imports engine-ts
    src/tree/filtersTree.ts
    src/tree/filesTree.ts
    src/tree/exportTree.ts
    src/commands.ts
    src/progress.ts
    README.md
  intellij/
    settings.gradle.kts
    engine/                  # Kotlin Engine, unit-testable without IDE
      src/main/kotlin/.../Engine.kt
      src/test/kotlin/...
    plugin/
      src/main/kotlin/.../toolwindow/
      src/main/resources/META-INF/plugin.xml
      src/test/kotlin/...
```

Python remains `src/build_ai_context/` + `tests/`. Add `tests/test_policy_lock.py` only.

---

## Approaches considered (and the pick)

1. **Python sidecar** — fastest parity, fails “cannot install Python.” Rejected.
2. **Native Hosts + dual Engine ports + golden tests (this plan)** — no extra runtime, native UX, drift gated by CI.
3. **Rust/Go Engine binary in both Hosts (ruff / rust-analyzer pattern)** — one implementation, JSON-RPC over stdio, per-OS binaries. VS Code can ship platform-specific VSIX; JetBrains cannot (one ZIP, pick binary at runtime). Higher rewrite and signing cost. Revisit if dual-port drift becomes real.

---

## Task 1: Policy file extracted from Python

**Files:**
- Create: `ide/policy/policy.json`
- Create: `ide/policy/policy.schema.json`
- Create: `tests/test_policy_lock.py`
- Modify: none of the Engine modules yet

**Interfaces:**
- Produces: JSON with keys `bundleMaxLines` (8000), `largeFileWarnLines` (1500), `largeFileSkipLines` (3000), `categoryExtensions`, `categoryAliases`, `categoryDescriptions`, `specialFilenames`, `defaultExcludedDirs`, `defaultExcludedPrefixes`, `extraExcludedPatterns`, `defaultSecretPatterns`, `textEncoding` (`utf-8`)
- Redaction: list of named pattern ids matching `redact.py` (do not fork regexes in this task — Task 6 copies the regex source into both ports and this file may hold the pattern strings)

- [ ] **Step 1: Write the failing Python lock test**

```python
# tests/test_policy_lock.py
import json
from pathlib import Path
from build_ai_context import constants

POLICY = Path(__file__).resolve().parents[1] / "ide" / "policy" / "policy.json"


def test_policy_file_exists():
    assert POLICY.is_file()


def test_limits_match_constants():
    data = json.loads(POLICY.read_text(encoding="utf-8"))
    assert data["bundleMaxLines"] == constants.DEFAULT_MAX_LINES
    assert data["largeFileWarnLines"] == constants.LARGE_FILE_WARN_LINES
    assert data["largeFileSkipLines"] == constants.LARGE_FILE_SKIP_LINES


def test_categories_match_constants():
    data = json.loads(POLICY.read_text(encoding="utf-8"))
    assert {k: sorted(v) for k, v in data["categoryExtensions"].items()} == {
        k: sorted(v) for k, v in constants.CATEGORY_EXTENSIONS.items()
    }
    assert data["categoryAliases"] == constants.CATEGORY_ALIASES
    assert data["defaultExcludedDirs"] == sorted(constants.DEFAULT_EXCLUDED_DIRS)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_policy_lock.py -v`

Expected: FAIL with `policy.json` missing

- [ ] **Step 3: Write `ide/policy/policy.json` by copying current constants** (exact sets from `src/build_ai_context/constants.py`; include `specialFilenames`, `defaultSecretPatterns`, `extraExcludedPatterns`, `defaultExcludedPrefixes`)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_policy_lock.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ide/policy tests/test_policy_lock.py
git commit -m "lock engine policy json to python constants"
```

---

## Task 2: Golden fixture generator

**Files:**
- Create: `ide/testdata/workspaces/small-py/` (README.md, `main.py`, `src/util.py`, `.env` secret, `node_modules/skip.js`, `.gitignore`)
- Create: `ide/testdata/generate_goldens.py`
- Create: `ide/testdata/golden/README.md` explaining timestamp stripping

**Interfaces:**
- Produces: `ide/testdata/golden/small-py/{bundles,manifest,filetree,graph.txt}` with `TIMESTAMP` placeholders and `PROJECT_ROOT` placeholder
- Consumes: installed `baic` from this repo (`python -m build_ai_context.cli` via the same entry as tests)

- [ ] **Step 1: Write `generate_goldens.py` that**
  1. Runs the CLI non-interactive on `small-py` with `--all`, `--redact` off, default max-file-lines
  2. Runs `--tree` and `--graph --format txt` and `--graph --format json`
  3. Copies artifacts into `golden/small-py/`
  4. Replaces ISO timestamps and `YYYYMMDDTHHMMSSZ` with `TIMESTAMP`, absolute paths with `PROJECT_ROOT`

- [ ] **Step 2: Run generator once and commit the goldens + fixture workspace**

```bash
python ide/testdata/generate_goldens.py
git add ide/testdata
git commit -m "add golden export fixtures from current baic"
```

Do not hand-edit golden bodies. If CLI output changes later, regenerate.

---

## Task 3: TypeScript Engine — scan

**Files:**
- Create: `ide/engine-ts/package.json` (name `@build-ai-context/engine`, type module, test runner `node:test` + `tsx`)
- Create: `ide/engine-ts/src/policy.ts` (load `ide/policy/policy.json` from the package root: `path.join(packageRoot, "..", "policy", "policy.json")`)
- Create: `ide/engine-ts/src/scan.ts`
- Create: `ide/engine-ts/test/scan.test.ts`

**Interfaces:**
- Produces: `scan(workspace: string, options: { includeSecretFiles: boolean }): Promise<Catalog>`
- `Catalog.files` sorted by posix `relPath`
- Skip reasons match Python: `default_excluded_dir`, `default_excluded_prefix`, `.gitignore`, `extra_excluded_pattern`, `secret_like_file`, `unsupported_type`, binary NUL
- Gitignore: root `.gitignore` only, gitwildmatch (`ignore` package)
- Encoding fallback: utf-8, utf-8-sig, latin-1, then utf-8 ignore
- sha256 of lines joined by `\n`

- [ ] **Step 1: Write failing tests using `ide/testdata/workspaces/small-py`**

```ts
import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { scan } from "../src/scan.ts";

const root = path.resolve("../../testdata/workspaces/small-py");

test("scan finds supported files and skips secrets and excluded dirs", async () => {
  const catalog = await scan(root, { includeSecretFiles: false });
  const rels = catalog.files.map((f) => f.relPath);
  assert.ok(rels.includes("main.py"));
  assert.ok(!rels.some((r) => r.includes("node_modules")));
  assert.ok(!rels.includes(".env"));
  assert.equal(catalog.files.find((f) => f.relPath === "main.py")?.category, "python");
});
```

- [ ] **Step 2: Run `npx tsx --test test/scan.test.ts`** — Expected: FAIL (module missing)

- [ ] **Step 3: Implement `scan.ts` + `policy.ts`**

- [ ] **Step 4: Re-run tests — Expected: PASS**

- [ ] **Step 5: Commit** `git commit -m "add typescript engine scan"`

---

## Task 4: TypeScript Engine — select

**Files:**
- Create: `ide/engine-ts/src/select.ts`
- Create: `ide/engine-ts/test/select.test.ts`
- Port behaviors from `tests/test_scanner.py`: category aliases, path folder/basename, intelligent comma/space paths, keywords case-insensitive, name filters on filename, composed AND of non-empty constraints

**Interfaces:**
- Produces: `select(catalog, filters): Selection` with `metadata.selectionMode === "composed"`

- [ ] **Step 1: Write failing tests** for: empty filters → all files; `categories: ["py"]` → python only; paths `src` → folder prefix; keywords `TODO`; nameFilters `util`; missing paths listed

- [ ] **Step 2: Run tests — Expected: FAIL**

- [ ] **Step 3: Implement `select.ts` (port `normalize_categories`, `filter_files_by_paths`, `filter_files_by_keywords`, mixed name filter)**

- [ ] **Step 4: Run tests — Expected: PASS**

- [ ] **Step 5: Commit** `git commit -m "add typescript engine selection filters"`

---

## Task 5: TypeScript Engine — chunk and pack

**Files:**
- Create: `ide/engine-ts/src/chunk.ts`
- Create: `ide/engine-ts/test/chunk.test.ts`

**Interfaces:**
- Produces: `splitIntoChunks(files, maxLines, redact, maxFileLines)` and `packChunks(chunks, maxLines, redact)` matching `chunking.py`
- Header/footer **byte-for-byte** the Python format (60 equals signs, `===== BEGIN FILE:`, `# category :`, etc.)
- Empty files dropped with no skip record
- `>= maxFileLines` (if > 0) → skip `large_file_exceeds_skip_threshold`
- `>= 1500` included → `large_file_warning`
- Bundle cap 8000 including overhead from `chunkOverheadLines(redact)`

- [ ] **Step 1: Write a failing test that renders one 1-line file and compares the block to Python `chunking.render_chunk_block` output captured in the test as a literal**

```ts
const expected = [
  "=".repeat(60),
  "===== BEGIN FILE: dummy.py =====",
  "# category : python",
  "# chunk : 1/1",
  "# line_range : 1-1",
  "# total_lines : 1",
  "=".repeat(60),
  "x",
  "=".repeat(60),
  "===== END FILE: dummy.py (chunk 1/1) =====",
  "=".repeat(60),
  "",
].join("\n");
```

- [ ] **Step 2: Run — Expected: FAIL**

- [ ] **Step 3: Implement `chunk.ts`**

- [ ] **Step 4: Run — Expected: PASS** including a test that a 3000-line file is skipped at default maxFileLines and included at 0

- [ ] **Step 5: Commit** `git commit -m "add typescript engine chunk and pack"`

---

## Task 6: TypeScript Engine — redact

**Files:**
- Create: `ide/engine-ts/src/redact.ts`
- Create: `ide/engine-ts/test/redact.test.ts`
- Copy regexes from `src/build_ai_context/redact.py` (same replacement `<REDACTED>`, same per-line application)

- [ ] **Step 1: Port cases from `tests/test_redact.py` (JWT, bearer, AWS, GitHub, `.env` assignment, false positives) as TS tests**

- [ ] **Step 2: Run — Expected: FAIL**

- [ ] **Step 3: Implement `redact.ts`**

- [ ] **Step 4: Run — Expected: PASS**

- [ ] **Step 5: Commit** `git commit -m "add typescript engine redaction"`

---

## Task 7: TypeScript Engine — write Bundles, Manifest, Agent Contract, gitignore

**Files:**
- Create: `ide/engine-ts/src/write.ts`
- Create: `ide/engine-ts/src/filetree.ts`
- Create: `ide/engine-ts/src/gitignore.ts`
- Create: `ide/engine-ts/src/overview.ts`
- Create: `ide/engine-ts/src/index.ts` (`export` facade)
- Create: `ide/engine-ts/test/golden.test.ts`
- Copy: Agent Contract from `src/build_ai_context/prompt.md` into `ide/engine-ts/prompt.md` (same bytes)

**Interfaces:**
- Produces: `export(catalog, selection, options): Promise<ExportResult>`
- Filetree of **Catalog** (all scanned), prepended to bundle 001 only
- Manifest fields match `writing.write_bundles_and_manifest` (`tool`, `created_at_utc`, `selection`, `bundles`, `warnings`, `skipped_during_pack`, …)
- Output dir naming: `exported_sources_{sanitizedName}_{timestamp}`
- `updateGitignore` appends `exported_sources*/`, `*_file_tree_*.txt`, `*_code_graph_*.txt`, `*_code_graph_*.json` without dupes

- [ ] **Step 1: Write `golden.test.ts` that exports `small-py` and compares normalized files to `ide/testdata/golden/small-py`**

- [ ] **Step 2: Run — Expected: FAIL**

- [ ] **Step 3: Implement write/filetree/gitignore/overview/index**

- [ ] **Step 4: Run golden + unit tests — Expected: PASS**

- [ ] **Step 5: Commit** `git commit -m "add typescript engine export writer"`

---

## Task 8: TypeScript Engine — Code Graph

**Files:**
- Create: `ide/engine-ts/src/graph.ts`
- Create: `ide/engine-ts/test/graph.test.ts`

**Interfaces:**
- Produces: `graph(catalog, format: "txt" | "json"): string` matching `graph.py` heuristics (no tree-sitter in v1)
- Python: port `_extract_python` using a TS parser **or** the same heuristic path used for other languages if a full `ast` port is too large — **must match golden graph for `small-py`**
- PageRank 0.85 / 20 rounds; txt/json serializers

- [ ] **Step 1: Failing test: `graph(small-py catalog, "txt")` normalizes to golden graph**

- [ ] **Step 2: Run — Expected: FAIL**

- [ ] **Step 3: Implement `graph.ts`**

- [ ] **Step 4: Run — Expected: PASS** (include a JS/Kotlin heuristic smoke test from `tests/test_graph.py` cases)

- [ ] **Step 5: Commit** `git commit -m "add typescript engine code graph"`

---

## Task 9: VS Code extension scaffold

**Files:**
- Create: `ide/vscode/package.json`
- Create: `ide/vscode/tsconfig.json`
- Create: `ide/vscode/src/extension.ts`
- Create: `ide/vscode/README.md`
- Create: `ide/vscode/.vscodeignore`

**Interfaces:**
- `engines.vscode`: `^1.90.0` (or the current stable at implementation time — look up and pin)
- `publisher`: `asjnaang` (placeholder until marketplace id exists)
- `name`: `build-ai-context`
- `displayName`: `Build AI Context`
- `activationEvents`: `onView:baic.filters`, `onCommand:baic.scan`, `onCommand:baic.export`
- `contributes.viewsContainers.activitybar` id `baic`
- `contributes.views`: `baic.filters`, `baic.files`, `baic.export`
- `contributes.commands` listed in the spec
- `contributes.configuration` properties `baic.maxFileLines` (3000), `baic.outputDir` (""), `baic.redact` (false), `baic.includeSecretFiles` (false), `baic.projectOverview` (false), `baic.writeGraph` (enum off/txt/json), `baic.updateGitignore` (true)
- `capabilities.untrustedWorkspaces.supported`: `"limited"`
- `extensionKind`: `["workspace"]`

- [ ] **Step 1: Scaffold so `npm run compile` in `ide/vscode` succeeds and `activate` registers empty tree providers**

- [ ] **Step 2: Commit** `git commit -m "scaffold vscode extension contributions"`

---

## Task 10: VS Code — scan + Filters/Files trees

**Files:**
- Create: `ide/vscode/src/engineAdapter.ts`
- Create: `ide/vscode/src/state.ts` (cached Catalog, Filters, checked paths, last ExportResult)
- Create: `ide/vscode/src/tree/filtersTree.ts`
- Create: `ide/vscode/src/tree/filesTree.ts`
- Create: `ide/vscode/src/progress.ts`

**Interfaces:**
- Consumes: `engine-ts` `scan` / `select` / `applyMaxFileLines`
- `baic.scan` uses `vscode.ProgressLocation.Notification` or `SourceControl` style window progress, cancellable
- Filters tree: one checkable item per Category present in the Catalog, label `python (12)`
- Files tree: folder grouping, checkbox, description `{n} lines`; oversized: warning icon, unchecked

- [ ] **Step 1: Integration test (or unit-test the view model without Electron if cheaper): after scan of `small-py`, Filters contains python; Files contains `main.py` checked**

- [ ] **Step 2: Implement adapter + trees + command `baic.scan`**

- [ ] **Step 3: Manual check in Extension Development Host: open fixture folder, Scan, see counts**

- [ ] **Step 4: Commit** `git commit -m "show scanned catalog in vscode trees"`

---

## Task 11: VS Code — filter commands and Add to AI Context

**Files:**
- Modify: `ide/vscode/src/commands.ts`, `package.json` menus
- `contributes.menus`: `explorer/context`, `editor/title/context`, `commandPalette`

**Interfaces:**
- `baic.setKeyword` → `showInputBox`
- `baic.clearFilters`
- `baic.addExplorerPath` / `baic.addCurrentFile` push posix relative paths into `Filters.paths`
- Category click toggles `Filters.categories` (empty list = no constraint; all-unchecked-with-intent: treat as empty and warn, or keep at least the semantics “no categories selected ⇒ no files” — **lock: if the user unchecks every category, Selection is empty**, matching “I opted out of all types.” A **Select all categories** title action restores them.)
- Files node checkbox updates checked set; Export uses **checked files**, not only filter output

- [ ] **Step 1: Tests on the view model: toggling python off drops `main.py`; add path `src` keeps `src/util.py`**

- [ ] **Step 2: Implement commands + menus**

- [ ] **Step 3: Commit** `git commit -m "add vscode selection filters and context menus"`

---

## Task 12: VS Code — Export

**Files:**
- Create: `ide/vscode/src/tree/exportTree.ts`
- Modify: `commands.ts`, `progress.ts`

**Interfaces:**
- `baic.export` → Engine.export with settings + checked files as Selection
- Confirm if `includeSecretFiles`
- On success: `showInformationMessage` with Open Folder / Open Agent Contract / Copy Path
- Export tree lists artifacts; clicking opens the file
- Cancellation does not patch gitignore
- Workspace Trust: command no-ops with a warning if untrusted

- [ ] **Step 1: Integration test against `small-py`: export creates `*_manifest_*.json`, at least one bundle, `prompt.md`**

- [ ] **Step 2: Implement**

- [ ] **Step 3: Commit** `git commit -m "export bundles from vscode host"`

---

## Task 13: VS Code — Filetree, Graph, Walkthrough, settings wiring

**Files:**
- Modify: `package.json` (`contributes.walkthroughs`), commands
- Settings already declared in Task 9; read them in adapter

**Interfaces:**
- `baic.generateFiletree` / `baic.generateGraph` write beside Workspace root and update gitignore (CLI `--tree`/`--graph`)
- Panel Export honors `baic.writeGraph` by also writing graph into the Export directory
- Walkthrough 4 steps: Open AI Context → Scan → Filter → Export and open Agent Contract

- [ ] **Step 1: Tests: generateFiletree writes `*_file_tree_TIMESTAMP.txt` pattern; graph json parses**

- [ ] **Step 2: Implement remaining commands + walkthrough**

- [ ] **Step 3: Commit** `git commit -m "add vscode filetree graph and walkthrough"`

---

## Task 14: Kotlin Engine port

**Files:**
- Create: `ide/intellij/engine/` Gradle submodule
- Mirror TS modules: `Policy.kt`, `Scan.kt`, `Select.kt`, `Chunk.kt`, `Redact.kt`, `Write.kt`, `Filetree.kt`, `Graph.kt`, `Gitignore.kt`
- Tests: JUnit 5, same goldens (normalize timestamps the same way)

**Interfaces:**
- Same function names as Task 3–8. Load `ide/policy/policy.json` from resources (copy into `engine/src/main/resources` at build).

- [ ] **Step 1: Write failing golden test in Kotlin**

- [ ] **Step 2: Port scan → select → chunk → redact → write → graph until goldens pass**

- [ ] **Step 3: Commit in slices matching TS commits** (`kt engine scan`, `kt engine export`, …)

Do not share mutable files with the TS port. Policy JSON is the only shared mutable contract.

---

## Task 15: IntelliJ plugin scaffold + Tool Window

**Files:**
- Create: `ide/intellij/plugin/src/main/resources/META-INF/plugin.xml`
- Create: `BaicToolWindowFactory.kt` implementing `ToolWindowFactory`
- `plugin.xml`: `id` `com.asjnaang.buildaicontext`, `name` `Build AI Context`, `<depends>com.intellij.modules.platform</depends>`, `com.intellij.toolWindow` id `AI Context` anchor `right`, `factoryClass` pointing at the factory
- Target IntelliJ Platform version: current stable at implementation (Plugin wizard default JDK 21) — pin in `gradle.properties`

- [ ] **Step 1: `./gradlew runIde` shows the tool window button**

- [ ] **Step 2: Commit** `git commit -m "scaffold intellij tool window"`

---

## Task 16: IntelliJ Tool Window UI + Actions

**Files:**
- `BaicPanel.kt` — Kotlin UI DSL: category checkboxes, keyword field, CheckboxTree, Export button
- Actions: `BaicScanAction`, `BaicExportAction`, `BaicAddToContextAction` (Project View + Editor)
- `BaicSettingsConfigurable` under Settings → Tools → Build AI Context (same keys as VS Code)
- `ProgressManager` cancellable tasks for scan/export
- Notification group `Build AI Context`

**Interfaces:**
- Consumes Kotlin Engine
- Same Selection semantics as VS Code (composed filters + checks)
- Confirm before include-secret-files
- Reveal in Finder/Explorer via `RevealFileAction`

- [ ] **Step 1: Unit-test the panel state object (not UI pixels): scan fixture → categories → export temp dir has manifest**

- [ ] **Step 2: Implement panel + actions + settings**

- [ ] **Step 3: Run `./gradlew test` and a manual `runIde` pass with `small-py` opened as a project**

- [ ] **Step 4: Commit** `git commit -m "export bundles from intellij host"`

---

## Task 17: Host READMEs, root README pointer, CI

**Files:**
- `ide/vscode/README.md` — install from VSIX, how it maps to `baic`
- `ide/intellij/plugin/README.md`
- Modify: root `README.md` — short “IDE Hosts (preview)” linking to both, without claiming Marketplace listings until published
- Create: `.github/workflows/ide-hosts.yml` — pytest policy lock; engine-ts tests; intellij `./gradlew :engine:test`; vscode compile

- [ ] **Step 1: CI green on the branch**

- [ ] **Step 2: Commit** `git commit -m "document and ci ide hosts"`

---

## Task 18: Package (not publish)

**Files:**
- `ide/vscode` script `"package": "vsce package"`
- IntelliJ `./gradlew :plugin:buildPlugin`
- Artifacts are local `.vsix` and `build/distributions/*.zip`

- [ ] **Step 1: Produce both packages on a clean tree**

- [ ] **Step 2: Commit packaging scripts only, not the binaries**

**Human later (not this plan):** Azure DevOps publisher + `vsce publish`; JetBrains Marketplace upload; Open VSX. Use `/wizard` when that day comes — accounts and tokens are not agent work.

---

## Self-review

**Spec coverage**

| Spec section | Task |
|---|---|
| Policy JSON + Python lock | Task 1 |
| Golden artifacts | Task 2, 7, 8, 14 |
| Engine scan/select/chunk/redact/write/graph | Tasks 3–8, 14 |
| VS Code native UI | Tasks 9–13 |
| IntelliJ native UI | Tasks 15–16 |
| Untrusted workspace / confirm secrets | Tasks 12, 16 |
| Out of scope list | Honored (no Visual Studio, no Flet, no headers command) |
| Distribution | Task 18 package only |

**Placeholder scan:** none of TBD / later / handle edge cases without a named behavior.

**Type consistency:** `Catalog`, `Filters`, `Selection`, `ExportOptions`, `ExportResult`, `scan/select/export/filetree/graph` used the same way from Task 3 through Task 16. `selectionMode` is `"composed"` in Hosts. Manifest `tool` field stays `build-ai-context` for golden match with Python; do not change it in v1 goldens. If Hosts need an extra field, add `host: "vscode" | "intellij"` without dropping existing keys — and update goldens only if Python is also updated (it will not be in v1). **Lock: Host-written Manifest matches Python keys exactly; Host may write an additional `host` key only if goldens are regenerated from a Python change. v1 goldens have no `host` key, so Hosts omit it.**

---

## What I need from you

Approve, or change any **D1–D18** action. The highest-leverage overrides:

1. If “VSStudio” meant **Visual Studio 2022** (not Code), say so — that replaces D1 and adds a third Host.
2. If you want a **single Engine language** (Rust binary) instead of TS+Kotlin, that replaces D4.
3. If Hosts must reproduce CLI **keyword exclusivity**, that replaces D7.

After approval, implementation follows Tasks 1–18 on `feat/ide-plugins`.
