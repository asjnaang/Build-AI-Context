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
    assert.ok(cmd?.enablement?.includes("workspaceIsTrusted"), `${id} enablement`);
  }
  const menus = Object.values(pkg.contributes?.menus ?? {}).flat();
  for (const item of menus.filter((m) => writeCommands.includes(m.command))) {
    assert.ok(item.when?.includes("workspaceIsTrusted"), `${item.command} menu when`);
  }
});

test("filter commands include filename, paths, and setting toggles", () => {
  const ids = new Set((pkg.contributes?.commands ?? []).map((c) => c.command));
  for (const id of [
    "baic.setNameFilter",
    "baic.setPathFilter",
    "baic.toggleSecrets",
    "baic.toggleOverview",
    "baic.cycleGraph",
  ]) {
    assert.ok(ids.has(id), id);
  }
});
