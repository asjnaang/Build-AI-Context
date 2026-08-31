import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
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

test("latin-1 encoded file is readable", async () => {
  const dir = mkdtempSync(path.join(tmpdir(), "baic-enc-"));
  try {
    writeFileSync(path.join(dir, "latin.py"), Buffer.from([0x23, 0x20, 0x63, 0x61, 0x66, 0xe9, 0x0a]));
    const catalog = await scan(dir, { includeSecretFiles: false });
    const file = catalog.files.find((f) => f.relPath === "latin.py");
    assert.ok(file);
    assert.equal(file.lines[0], "# café");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
