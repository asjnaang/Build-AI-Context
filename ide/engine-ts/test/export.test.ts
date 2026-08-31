import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { scan } from "../src/scan.ts";
import { select } from "../src/select.ts";
import { exportCatalog } from "../src/write.ts";
import type { SourceFile } from "../src/types.ts";

function tempWorkspace(): string {
  const dir = mkdtempSync(path.join(tmpdir(), "baic-ws-"));
  writeFileSync(path.join(dir, "small.py"), "print(1)\n");
  return dir;
}

function bigPy(dir: string, lines = 3000): void {
  writeFileSync(path.join(dir, "big.py"), Array.from({ length: lines }, () => "x").join("\n") + "\n");
}

test("checked oversized file is written when skip is disabled", async () => {
  const dir = tempWorkspace();
  try {
    bigPy(dir);
    const catalog = await scan(dir, { includeSecretFiles: false });
    const big = catalog.files.find((f) => f.relPath === "big.py");
    assert.ok(big);
    const out = mkdtempSync(path.join(tmpdir(), "baic-out-"));
    const result = await exportCatalog(
      catalog,
      { files: [big as SourceFile], metadata: select(catalog, { categories: [], paths: [], nameFilters: [], keywords: [] }).metadata },
      {
        outputDir: out,
        maxFileLines: 0,
        redact: false,
        projectOverview: false,
        updateGitignore: false,
      },
    );
    const bundle = readFileSync(result.bundlePaths[0], "utf8");
    assert.ok(bundle.includes("===== BEGIN FILE: big.py ====="));
    assert.ok(!result.skippedDuringPack.some((s) => s.reason === "large_file_exceeds_skip_threshold"));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("canceled export does not patch gitignore", async () => {
  const dir = tempWorkspace();
  try {
    const catalog = await scan(dir, { includeSecretFiles: false });
    const selection = select(catalog, { categories: [], paths: [], nameFilters: [], keywords: [] });
    await exportCatalog(catalog, selection, {
      maxFileLines: 3000,
      redact: false,
      projectOverview: false,
      updateGitignore: true,
      isCanceled: () => true,
    }).then(
      () => {
        throw new Error("expected cancel");
      },
      () => {
        /* canceled */
      },
    );
    assert.equal(existsSync(path.join(dir, ".gitignore")), false);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("successful export patches gitignore only after bundles exist", async () => {
  const dir = tempWorkspace();
  try {
    const catalog = await scan(dir, { includeSecretFiles: false });
    const selection = select(catalog, { categories: [], paths: [], nameFilters: [], keywords: [] });
    const result = await exportCatalog(catalog, selection, {
      maxFileLines: 3000,
      redact: false,
      projectOverview: false,
      updateGitignore: true,
    });
    assert.ok(existsSync(result.bundlePaths[0]));
    const gi = readFileSync(path.join(dir, ".gitignore"), "utf8");
    assert.ok(gi.includes("exported_sources*/"));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("relative outputDir resolves under workspace", async () => {
  const dir = tempWorkspace();
  try {
    const catalog = await scan(dir, { includeSecretFiles: false });
    const selection = select(catalog, { categories: [], paths: [], nameFilters: [], keywords: [] });
    const result = await exportCatalog(catalog, selection, {
      outputDir: "nested-out",
      maxFileLines: 3000,
      redact: false,
      projectOverview: false,
      updateGitignore: false,
    });
    assert.equal(result.outputDir, path.join(dir, "nested-out"));
    assert.ok(existsSync(path.join(dir, "nested-out")));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("manifest skip_secret_like_files is false when includeSecretFiles is true", async () => {
  const dir = tempWorkspace();
  try {
    writeFileSync(path.join(dir, ".env"), "SECRET=1\n");
    const catalog = await scan(dir, { includeSecretFiles: true });
    const selection = select(catalog, { categories: [], paths: [], nameFilters: [], keywords: [] });
    const out = mkdtempSync(path.join(tmpdir(), "baic-out-"));
    const result = await exportCatalog(catalog, selection, {
      outputDir: out,
      maxFileLines: 3000,
      redact: false,
      projectOverview: false,
      updateGitignore: false,
      includeSecretFiles: true,
    });
    const manifest = JSON.parse(readFileSync(result.manifestPath, "utf8")) as { skip_secret_like_files: boolean };
    assert.equal(manifest.skip_secret_like_files, false);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
