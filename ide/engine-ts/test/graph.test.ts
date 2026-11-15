import assert from "node:assert/strict";
import test from "node:test";
import { generateGraph } from "../src/graph.ts";
import type { SourceFile } from "../src/types.ts";

function src(rel: string, category: string, text: string): SourceFile {
  const lines = text.split("\n");
  if (lines[lines.length - 1] === "") lines.pop();
  return {
    relPath: rel,
    absPath: `/tmp/${rel}`,
    category,
    lineCount: lines.length,
    sizeBytes: text.length,
    sha256: "x",
    lines,
    snapshotBytes: Buffer.from(text, "utf8"),
    mode: 0o644,
    encoding: "text",
  };
}

test("js heuristic catalogs function and import", () => {
  const files = [
    src("a.js", "javascript", "import { b } from './b.js';\nexport function hello() {}\n"),
    src("b.js", "javascript", "export function world() {}\n"),
  ];
  const txt = generateGraph(files, "/tmp", "txt");
  assert.match(txt, /fn: hello @/);
  assert.match(txt, /a\.js --> b\.js,/);
});
