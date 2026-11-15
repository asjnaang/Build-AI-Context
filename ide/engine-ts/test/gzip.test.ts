import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { restoreExport } from "../src/gzip.ts";
import { scan } from "../src/scan.ts";
import { select } from "../src/select.ts";
import { exportCatalog } from "../src/write.ts";

function workspace(): string {
  const dir = mkdtempSync(path.join(tmpdir(), "baic-gz-ws-"));
  writeFileSync(path.join(dir, "main.py"), "print('ok')\n");
  writeFileSync(path.join(dir, "README.md"), "# hi\n");
  return dir;
}

test("gzip export writes baic_prompt.md from the gzip template and restores bytes", async () => {
  const dir = workspace();
  const out = mkdtempSync(path.join(tmpdir(), "baic-gz-out-"));
  const restored = mkdtempSync(path.join(tmpdir(), "baic-gz-rest-"));
  rmSync(restored, { recursive: true, force: true });
  try {
    const catalog = await scan(dir, { includeSecretFiles: false });
    const selection = select(catalog, { categories: [], paths: [], nameFilters: [], keywords: [] });
    const result = await exportCatalog(catalog, selection, {
      outputDir: out,
      maxFileLines: 3000,
      redact: false,
      projectOverview: false,
      updateGitignore: false,
      transport: "tar-gz",
    });
    const prompt = readFileSync(result.promptPath, "utf8");
    assert.equal(path.basename(result.promptPath), "baic_prompt.md");
    assert.match(prompt, /tar\+gzip\+base64/);
    const manifest = JSON.parse(readFileSync(result.manifestPath, "utf8")) as {
      transport: { format: string };
    };
    assert.equal(manifest.transport.format, "tar+gzip+base64");
    const round = restoreExport(out, restored, true);
    assert.equal(round.restoredCount, 2);
    assert.equal(readFileSync(path.join(restored, "main.py"), "utf8"), "print('ok')\n");
    assert.equal(readFileSync(path.join(restored, "README.md"), "utf8"), "# hi\n");
  } finally {
    rmSync(dir, { recursive: true, force: true });
    rmSync(out, { recursive: true, force: true });
    rmSync(restored, { recursive: true, force: true });
  }
});

test("text export writes baic_prompt.md from the text template", async () => {
  const dir = workspace();
  const out = mkdtempSync(path.join(tmpdir(), "baic-txt-out-"));
  try {
    const catalog = await scan(dir, { includeSecretFiles: false });
    const selection = select(catalog, { categories: [], paths: [], nameFilters: [], keywords: [] });
    const result = await exportCatalog(catalog, selection, {
      outputDir: out,
      maxFileLines: 3000,
      redact: false,
      projectOverview: false,
      updateGitignore: false,
      transport: "text",
    });
    const prompt = readFileSync(result.promptPath, "utf8");
    assert.match(prompt, /_bundle_001_/);
    const bundle = readFileSync(result.bundlePaths[0], "utf8");
    assert.match(bundle, /BEGIN FILE: main.py/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
    rmSync(out, { recursive: true, force: true });
  }
});

test("force-include-formats sqlite3 is packed and restored", async () => {
  const dir = workspace();
  writeFileSync(path.join(dir, "source-catalog.sqlite3"), Buffer.from("SQLite format 3\0demo"));
  const out = mkdtempSync(path.join(tmpdir(), "baic-sql-out-"));
  const restored = path.join(tmpdir(), `baic-sql-rest-${Date.now()}`);
  try {
    const catalog = await scan(dir, {
      includeSecretFiles: false,
      forceIncludeFormats: [".sqlite3"],
    });
    assert.ok(catalog.files.some((f) => f.relPath === "source-catalog.sqlite3"));
    const selection = select(catalog, { categories: [], paths: [], nameFilters: [], keywords: [] });
    const result = await exportCatalog(catalog, selection, {
      outputDir: out,
      maxFileLines: 3000,
      redact: false,
      projectOverview: false,
      updateGitignore: false,
      transport: "tar-gz",
    });
    restoreExport(result.outputDir, restored, true);
    assert.deepEqual(
      readFileSync(path.join(restored, "source-catalog.sqlite3")),
      Buffer.from("SQLite format 3\0demo"),
    );
  } finally {
    rmSync(dir, { recursive: true, force: true });
    rmSync(out, { recursive: true, force: true });
    rmSync(restored, { recursive: true, force: true });
  }
});
