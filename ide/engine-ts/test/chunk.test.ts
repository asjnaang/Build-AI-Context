import assert from "node:assert/strict";
import test from "node:test";
import { renderChunkBlock, splitIntoChunks } from "../src/chunk.ts";
import type { FileChunk, SourceFile } from "../src/types.ts";

test("chunk block matches python header form", () => {
  const chunk: FileChunk = {
    relPath: "dummy.py",
    category: "python",
    chunkIndex: 1,
    chunkCount: 1,
    startLine: 1,
    endLine: 1,
    totalFileLines: 1,
    lines: ["x"],
  };
  const expected = [
    "=".repeat(60),
    "===== BEGIN FILE: dummy.py =====",
    "# category : python",
    "# chunk : 1/1",
    "# line_range : 1-1",
    "# total_lines : 1",
    "=".repeat(60),
    "x",
    "=".repeat(60),
    "===== END FILE: dummy.py (chunk 1/1) =====",
    "=".repeat(60),
    "",
  ].join("\n");
  assert.equal(renderChunkBlock(chunk, false), expected);
});

test("default maxFileLines skips 3000-line files", () => {
  const lines = Array.from({ length: 3000 }, () => "x");
  const file: SourceFile = {
    relPath: "big.py",
    absPath: "/tmp/big.py",
    category: "python",
    lineCount: 3000,
    sizeBytes: 3000,
    sha256: "x",
    lines,
    snapshotBytes: Buffer.from(lines.join("\n"), "utf8"),
    mode: 0o644,
    encoding: "text",
  };
  const skipped = splitIntoChunks([file], 8000, false, 3000);
  assert.equal(skipped.chunks.length, 0);
  assert.equal(skipped.skipped[0]?.reason, "large_file_exceeds_skip_threshold");
  const unlimited = splitIntoChunks([file], 8000, false, 0);
  assert.ok(unlimited.chunks.length >= 1);
});
