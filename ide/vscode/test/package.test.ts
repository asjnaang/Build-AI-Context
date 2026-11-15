import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { denyUntrustedWrite } from "../src/trust.ts";

const pkg = JSON.parse(
  readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "package.json"), "utf8"),
) as {
  capabilities?: { untrustedWorkspaces?: { supported?: unknown }; virtualWorkspaces?: { supported?: unknown } };
  contributes?: {
    commands?: Array<{ command: string; enablement?: string }>;
    menus?: Record<string, Array<{ command: string; when?: string }>>;
    views?: Record<string, Array<{ id: string; visibility?: string }>>;
    viewsWelcome?: Array<{ view: string; contents: string }>;
    walkthroughs?: unknown;
  };
};

test("restricted mode and virtual workspaces cannot write", () => {
  assert.equal(pkg.capabilities?.virtualWorkspaces?.supported, false);
  assert.equal(pkg.capabilities?.untrustedWorkspaces?.supported, false);
  assert.equal(denyUntrustedWrite(false), "Trust this workspace to write files.");
  assert.equal(denyUntrustedWrite(true), undefined);
});

test("write commands require a trusted workspace", () => {
  const writeCommands = ["baic.scan", "baic.export", "baic.generateFiletree", "baic.generateGraph"];
  const commands = pkg.contributes?.commands ?? [];
  for (const id of writeCommands) {
    const cmd = commands.find((c) => c.command === id);
    assert.ok(cmd, id);
    assert.ok(cmd?.enablement?.includes("isWorkspaceTrusted"), `${id} enablement`);
  }
  const menus = Object.values(pkg.contributes?.menus ?? {}).flat();
  for (const item of menus.filter((m) => writeCommands.includes(m.command))) {
    assert.ok(item.when?.includes("isWorkspaceTrusted"), `${item.command} menu when`);
  }
});

test("filter commands include filename, paths, and setting toggles", () => {
  const ids = new Set((pkg.contributes?.commands ?? []).map((c) => c.command));
  for (const id of [
    "baic.searchFiles",
    "baic.chooseFormat",
    "baic.selectSearchResults",
    "baic.setNameFilter",
    "baic.setPathFilter",
    "baic.toggleSecrets",
    "baic.toggleOverview",
    "baic.cycleGraph",
  ]) {
    assert.ok(ids.has(id), id);
  }
});

test("Files opens first with Export as the primary action", () => {
  const views = pkg.contributes?.views?.baic ?? [];
  assert.equal(views[0]?.id, "baic.files");
  assert.equal(views[1]?.id, "baic.filters");
  const welcome = pkg.contributes?.viewsWelcome?.find((item) => item.view === "baic.files");
  assert.match(welcome?.contents ?? "", /\[Export\]\(command:baic\.export\)/);
  const menu = pkg.contributes?.menus?.["view/title"] ?? [];
  assert.ok(menu.some((item) => item.command === "baic.export" && item.when?.includes("baic.files")));
  const ids = new Set((pkg.contributes?.commands ?? []).map((c) => c.command));
  assert.ok(ids.has("baic.restore"));
  const walkthrough = JSON.stringify(pkg.contributes?.walkthroughs ?? []);
  assert.equal(/Scan And Select/i.test(walkthrough), false);
  assert.match(welcome?.contents ?? "", /\[Restore gzip\]\(command:baic\.restore\)/);
});
