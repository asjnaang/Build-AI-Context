import assert from "node:assert/strict";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { scan } from "../src/scan.ts";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../testdata/workspaces/small-py");

test("scan finds supported files and skips secrets and excluded dirs", async () => {
  const catalog = await scan(root, { includeSecretFiles: false });
  const rels = catalog.files.map((f) => f.relPath);
  assert.ok(rels.includes("main.py"));
  assert.ok(rels.includes("src/util.py"));
  assert.ok(rels.includes("README.md"));
  assert.ok(!rels.some((r) => r.includes("node_modules")));
  assert.ok(!rels.includes(".env"));
  assert.equal(catalog.files.find((f) => f.relPath === "main.py")?.category, "python");
});
