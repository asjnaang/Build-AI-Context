import assert from "node:assert/strict";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { scan } from "../src/scan.ts";
import { select } from "../src/select.ts";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../testdata/workspaces/small-py");

test("empty filters select all catalog files", async () => {
  const catalog = await scan(root, { includeSecretFiles: false });
  const selection = select(catalog, { categories: [], paths: [], nameFilters: [], keywords: [] });
  assert.equal(selection.files.length, catalog.files.length);
  assert.equal(selection.metadata.selectionMode, "non_interactive");
});

test("py alias selects python only", async () => {
  const catalog = await scan(root, { includeSecretFiles: false });
  const selection = select(catalog, { categories: ["py"], paths: [], nameFilters: [], keywords: [] });
  assert.ok(selection.files.every((f) => f.category === "python"));
  assert.ok(selection.files.some((f) => f.relPath === "main.py"));
});

test("path src keeps util", async () => {
  const catalog = await scan(root, { includeSecretFiles: false });
  const selection = select(catalog, { categories: [], paths: ["src"], nameFilters: [], keywords: [] });
  assert.deepEqual(selection.files.map((f) => f.relPath), ["src/util.py"]);
});

test("keyword TODO matches main.py", async () => {
  const catalog = await scan(root, { includeSecretFiles: false });
  const selection = select(catalog, { categories: [], paths: [], nameFilters: [], keywords: ["TODO"] });
  assert.ok(selection.files.some((f) => f.relPath === "main.py"));
});

test("name filter util", async () => {
  const catalog = await scan(root, { includeSecretFiles: false });
  const selection = select(catalog, { categories: [], paths: [], nameFilters: ["util"], keywords: [] });
  assert.deepEqual(selection.files.map((f) => f.relPath), ["src/util.py"]);
});

test("explicit empty category set selects zero files", async () => {
  const catalog = await scan(root, { includeSecretFiles: false });
  const selection = select(catalog, {
    categories: [],
    categoriesConstrained: true,
    paths: [],
    nameFilters: [],
    keywords: [],
  });
  assert.equal(selection.files.length, 0);
  assert.equal(selection.metadata.selectionMode, "composed");
});
