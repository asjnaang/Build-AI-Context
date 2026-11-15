import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { exportCatalog } from "../src/write.ts";
import { generateGraph } from "../src/graph.ts";
import { generateFiletree } from "../src/filetree.ts";
import { scan } from "../src/scan.ts";
import { select } from "../src/select.ts";

const here = path.dirname(fileURLToPath(import.meta.url));
const workspace = path.resolve(here, "../../testdata/workspaces/small-py");
const golden = path.resolve(here, "../../testdata/golden/small-py");

function normalize(text: string, projectRoot: string): string {
  return text
    .replace(/\d{8}T\d{6}Z/g, "TIMESTAMP")
    .replace(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)/g, "TIMESTAMP")
    .replaceAll(projectRoot, "PROJECT_ROOT");
}

test("filetree matches golden", async () => {
  const catalog = await scan(workspace, { includeSecretFiles: false });
  const actual = generateFiletree(catalog.files, catalog.workspace);
  const expected = readFileSync(path.join(golden, "filetree.txt"), "utf8");
  assert.equal(actual, expected);
});

test("graph txt matches golden", async () => {
  const catalog = await scan(workspace, { includeSecretFiles: false });
  const actual = generateGraph(catalog.files, catalog.workspace, "txt");
  const expected = readFileSync(path.join(golden, "graph.txt"), "utf8");
  assert.equal(actual, expected);
});

test("export bundle body matches golden", async () => {
  const catalog = await scan(workspace, { includeSecretFiles: false });
  const selection = select(catalog, { categories: [], paths: [], nameFilters: [], keywords: [] });
  const dir = mkdtempSync(path.join(tmpdir(), "baic-"));
  try {
    const result = await exportCatalog(catalog, selection, {
      outputDir: dir,
      maxFileLines: 3000,
      redact: false,
      projectOverview: false,
      updateGitignore: false,
      transport: "text",
    });
    const bundle = readFileSync(result.bundlePaths[0], "utf8");
    const expected = readFileSync(path.join(golden, "bundle.txt"), "utf8");
    assert.equal(normalize(bundle, catalog.workspace), expected);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
