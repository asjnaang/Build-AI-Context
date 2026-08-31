import { loadPolicy } from "./policy.ts";
import { redactText } from "./redact.ts";
import type { FileChunk, SourceFile } from "./types.ts";

export function bundleHeader(chunk: FileChunk): string {
  return (
    `${"=".repeat(60)}\n` +
    `===== BEGIN FILE: ${chunk.relPath} =====\n` +
    `# category : ${chunk.category}\n` +
    `# chunk : ${chunk.chunkIndex}/${chunk.chunkCount}\n` +
    `# line_range : ${chunk.startLine}-${chunk.endLine}\n` +
    `# total_lines : ${chunk.totalFileLines}\n` +
    `${"=".repeat(60)}\n`
  );
}

export function bundleFooter(chunk: FileChunk): string {
  return (
    `${"=".repeat(60)}\n` +
    `===== END FILE: ${chunk.relPath} (chunk ${chunk.chunkIndex}/${chunk.chunkCount}) =====\n` +
    `${"=".repeat(60)}\n`
  );
}

export function renderChunkBlock(chunk: FileChunk, redact: boolean): string {
  const parts: string[] = [bundleHeader(chunk)];
  for (const line of chunk.lines) {
    parts.push((redact ? redactText(line) : line) + "\n");
  }
  parts.push(bundleFooter(chunk));
  return parts.join("");
}

export function chunkOverheadLines(redact: boolean): number {
  const dummy: FileChunk = {
    relPath: "dummy.py",
    category: "python",
    chunkIndex: 1,
    chunkCount: 1,
    startLine: 1,
    endLine: 1,
    totalFileLines: 1,
    lines: ["x"],
  };
  return renderChunkBlock(dummy, redact).split(/\n/).length - 1;
}

export function splitIntoChunks(
  files: SourceFile[],
  maxLines: number,
  redact: boolean,
  maxFileLines: number | null,
): { chunks: FileChunk[]; skipped: Array<Record<string, unknown>> } {
  const policy = loadPolicy();
  const chunks: FileChunk[] = [];
  const skipped: Array<Record<string, unknown>> = [];
  const overhead = chunkOverheadLines(redact);
  const skipThreshold = maxFileLines === null ? policy.largeFileSkipLines : maxFileLines;

  for (const source of files) {
    const lines = source.lines;
    const totalLines = lines.length;
    if (totalLines === 0) continue;

    if (skipThreshold > 0 && totalLines >= skipThreshold) {
      skipped.push({
        path: source.relPath,
        reason: "large_file_exceeds_skip_threshold",
        line_count: totalLines,
        threshold: skipThreshold,
      });
      continue;
    }

    if (totalLines >= policy.largeFileWarnLines) {
      skipped.push({
        path: source.relPath,
        reason: "large_file_warning",
        line_count: totalLines,
        threshold: policy.largeFileWarnLines,
      });
    }

    let effectiveMax = maxLines - overhead;
    if (effectiveMax <= 0) effectiveMax = maxLines;

    if (totalLines <= effectiveMax) {
      chunks.push({
        relPath: source.relPath,
        category: source.category,
        chunkIndex: 1,
        chunkCount: 1,
        startLine: 1,
        endLine: totalLines,
        totalFileLines: totalLines,
        lines,
      });
    } else {
      const chunkCount = Math.ceil(totalLines / effectiveMax);
      for (let i = 0; i < chunkCount; i++) {
        const start = i * effectiveMax;
        const end = Math.min(start + effectiveMax, totalLines);
        chunks.push({
          relPath: source.relPath,
          category: source.category,
          chunkIndex: i + 1,
          chunkCount,
          startLine: start + 1,
          endLine: end,
          totalFileLines: totalLines,
          lines: lines.slice(start, end),
        });
      }
    }
  }
  return { chunks, skipped };
}

export function packChunks(
  chunks: FileChunk[],
  maxLines: number,
  redact: boolean,
): { bundles: FileChunk[][]; skipped: Array<Record<string, unknown>> } {
  const bundles: FileChunk[][] = [];
  const skipped: Array<Record<string, unknown>> = [];
  let current: FileChunk[] = [];
  let currentLines = 0;
  const overhead = chunkOverheadLines(redact);

  for (const chunk of chunks) {
    const chunkLines = chunk.lines.length;
    const totalNeeded = chunkLines + overhead;
    if (totalNeeded > maxLines) {
      skipped.push({
        path: chunk.relPath,
        reason: "chunk_exceeds_max_lines",
        line_count: chunkLines,
        max_lines: maxLines,
      });
      continue;
    }
    if (currentLines + totalNeeded > maxLines && current.length) {
      bundles.push(current);
      current = [];
      currentLines = 0;
    }
    current.push(chunk);
    currentLines += totalNeeded;
  }
  if (current.length) bundles.push(current);
  return { bundles, skipped };
}
