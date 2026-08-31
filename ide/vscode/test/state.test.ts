import assert from "node:assert/strict";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { scan } from "../../engine-ts/src/scan.ts";
import { applyScan, createState, selectionFiles, toggleCategory } from "../src/state.ts";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../testdata/workspaces/small-py");

test("after scan, python files are checked", async () => {
  const catalog = await scan(root, { includeSecretFiles: false });
  const state = createState(3000);
  applyScan(state, catalog);
  assert.ok(state.checked.has("main.py"));
  const files = selectionFiles(state);
  assert.ok(files.some((f) => f.relPath === "main.py"));
});

test("toggling python off drops main.py when it is the only remaining category constraint", async () => {
  const catalog = await scan(root, { includeSecretFiles: false });
  const state = createState(3000);
  applyScan(state, catalog);
  toggleCategory(state, "python");
  const files = selectionFiles(state);
  assert.ok(!files.some((f) => f.relPath === "main.py"));
});
