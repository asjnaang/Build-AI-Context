import assert from "node:assert/strict";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { scan } from "../../engine-ts/src/scan.ts";
import { applyScan, createState } from "../src/state.ts";
import { panelMarkup, panelSnapshot, type PanelSettings } from "../src/panelModel.ts";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../testdata/workspaces/small-py");

const settings: PanelSettings = {
  transport: "tar-gz",
  forceBundle: false,
  forceIgnored: false,
  split: false,
  excludePaths: "",
  forceIncludeFormats: "",
};

function headingOrder(html: string): string[] {
  const labels = [...html.matchAll(/data-section="([^"]+)"/g)].map((m) => m[1]);
  return labels;
}

test("export-first panel lists search, format, export, files, options, last export in that order", async () => {
  const catalog = await scan(root, { includeSecretFiles: false });
  const state = createState();
  applyScan(state, catalog);
  const snap = panelSnapshot(state, settings);
  const html = panelMarkup(snap);
  assert.deepEqual(headingOrder(html), [
    "search",
    "format",
    "meta",
    "export",
    "selectAll",
    "actions",
    "files",
    "options",
    "lastExport",
  ]);
  assert.match(html, /Search files/);
  assert.match(html, /File format/);
  assert.match(html, /Export \d+ files/);
  assert.match(html, /Select all results/);
  assert.match(html, /Restore gzip/);
  assert.match(html, />Files</);
  assert.match(html, />Options</);
  assert.match(html, /Last export/);
  assert.equal(snap.transportLabel, "gzip");
  assert.ok(snap.selectedCount > 0);
  assert.ok(html.includes("README.md"));
});

test("select-all checkbox reflects whether every visible result is checked", async () => {
  const catalog = await scan(root, { includeSecretFiles: false });
  const state = createState();
  applyScan(state, catalog);
  const all = panelSnapshot(state, settings);
  assert.equal(all.selectAllChecked, true);
  state.checked.clear();
  const none = panelSnapshot(state, settings);
  assert.equal(none.selectAllChecked, false);
  assert.match(panelMarkup(none), /Export 0 files/);
});
