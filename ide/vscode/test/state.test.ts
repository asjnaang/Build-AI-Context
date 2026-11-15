import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { scan } from "../../engine-ts/src/scan.ts";
import { select } from "../../engine-ts/src/select.ts";
import { exportCatalog } from "../../engine-ts/src/write.ts";
import {
  applyScan,
  createState,
  exportMaxFileLines,
  recordExport,
  availableFormats,
  searchResults,
  selectSearchResults,
  selectionFiles,
  setNameFilters,
  toggleCategory,
  visibleFileTree,
} from "../src/state.ts";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../testdata/workspaces/small-py");

test("after scan, python files are checked", async () => {
  const catalog = await scan(root, { includeSecretFiles: false });
  const state = createState(3000);
  applyScan(state, catalog);
  assert.ok(state.checked.has("main.py"));
  const files = selectionFiles(state);
  assert.ok(files.some((f) => f.relPath === "main.py"));
});

test("search and file format compose before select all and export", async () => {
  const catalog = await scan(root, { includeSecretFiles: false });
  const state = createState();
  applyScan(state, catalog);
  assert.ok(availableFormats(state).includes(".py"));
  state.searchQuery = "src";
  state.formatFilter = ".py";
  assert.deepEqual(searchResults(state).map((f) => f.relPath), ["src/util.py"]);
  state.checked.clear();
  assert.equal(selectSearchResults(state), 1);
  assert.deepEqual(selectionFiles(state).map((f) => f.relPath), ["src/util.py"]);
  state.searchQuery = "python";
  assert.deepEqual(searchResults(state).map((f) => f.relPath).sort(), ["main.py", "src/util.py"]);
});

test("toggling python off drops main.py when it is the only remaining category constraint", async () => {
  const catalog = await scan(root, { includeSecretFiles: false });
  const state = createState(3000);
  applyScan(state, catalog);
  toggleCategory(state, "python");
  const files = selectionFiles(state);
  assert.ok(!files.some((f) => f.relPath === "main.py"));
});

test("unchecking the last category selects zero files", async () => {
  const catalog = await scan(root, { includeSecretFiles: false });
  const state = createState(3000);
  applyScan(state, catalog);
  const cats = [...new Set(catalog.files.map((f) => f.category))];
  for (const cat of cats) toggleCategory(state, cat);
  assert.equal(selectionFiles(state).length, 0);
});

test("checking an oversized file exports it in the bundle", async () => {
  const dir = mkdtempSync(path.join(tmpdir(), "baic-over-"));
  try {
    writeFileSync(path.join(dir, "small.py"), "print(1)\n");
    writeFileSync(path.join(dir, "big.py"), Array.from({ length: 3000 }, () => "x").join("\n") + "\n");
    const catalog = await scan(dir, { includeSecretFiles: false });
    const state = createState(3000);
    applyScan(state, catalog);
    assert.ok(!state.checked.has("big.py"));
    state.checked.add("big.py");
    assert.ok(selectionFiles(state).some((f) => f.relPath === "big.py"));
    assert.equal(exportMaxFileLines(state), 0);
    const out = mkdtempSync(path.join(tmpdir(), "baic-over-out-"));
    const result = await exportCatalog(
      catalog,
      { files: selectionFiles(state), metadata: select(catalog, state.filters).metadata },
      {
        outputDir: out,
        maxFileLines: exportMaxFileLines(state),
        redact: false,
        projectOverview: false,
        updateGitignore: false,
        transport: "text",
      },
    );
    const bundle = readFileSync(result.bundlePaths[0], "utf8");
    assert.ok(bundle.includes("===== BEGIN FILE: big.py ====="));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("files tree groups by dirname", async () => {
  const catalog = await scan(root, { includeSecretFiles: false });
  const state = createState(3000);
  applyScan(state, catalog);
  const tree = visibleFileTree(state);
  assert.ok(tree.some((n) => n.kind === "file" && n.name === "main.py"));
  const src = tree.find((n) => n.kind === "dir" && n.name === "src");
  assert.ok(src && src.kind === "dir");
  assert.ok(src.children.some((n) => n.kind === "file" && n.name === "util.py"));
});

test("filename filter is applied through host state", async () => {
  const catalog = await scan(root, { includeSecretFiles: false });
  const state = createState(3000);
  applyScan(state, catalog);
  setNameFilters(state, "util");
  assert.deepEqual(selectionFiles(state).map((f) => f.relPath), ["src/util.py"]);
});

test("recordExport keeps artifact paths", () => {
  const state = createState(3000);
  recordExport(state, {
    outputDir: "/tmp/out",
    manifestPath: "/tmp/out/manifest.json",
    bundlePaths: ["/tmp/out/bundle.txt"],
    filetreeEmbedded: true,
    promptPath: "/tmp/out/prompt.md",
    graphPath: "/tmp/out/graph.txt",
    filesExported: 1,
    bundlesCreated: 1,
    warnings: [],
    skippedDuringPack: [],
  });
  assert.equal(state.lastExportDir, "/tmp/out");
  assert.equal(state.manifestPath, "/tmp/out/manifest.json");
  assert.deepEqual(state.bundlePaths, ["/tmp/out/bundle.txt"]);
  assert.equal(state.graphPath, "/tmp/out/graph.txt");
  assert.equal(state.lastPromptPath, "/tmp/out/prompt.md");
});
