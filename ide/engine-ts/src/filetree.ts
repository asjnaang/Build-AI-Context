import { basename } from "node:path";
import { loadPolicy } from "./policy.ts";
import type { SourceFile } from "./types.ts";

export function generateTimestamp(): string {
  const now = new Date();
  const y = now.getUTCFullYear();
  const m = String(now.getUTCMonth() + 1).padStart(2, "0");
  const d = String(now.getUTCDate()).padStart(2, "0");
  const hh = String(now.getUTCHours()).padStart(2, "0");
  const mm = String(now.getUTCMinutes()).padStart(2, "0");
  const ss = String(now.getUTCSeconds()).padStart(2, "0");
  return `${y}${m}${d}T${hh}${mm}${ss}Z`;
}

export function isTimestamp(s: string): boolean {
  return /^\d{8}T\d{6}Z$/.test(s);
}

export function extractTimestampFromDirName(dirName: string): string {
  const parts = dirName.split("_");
  const last = parts[parts.length - 1];
  if (last && isTimestamp(last)) return last;
  return generateTimestamp();
}

export function sanitizeOutputDirName(root: string): string {
  const timestamp = generateTimestamp();
  const projectName = basename(root).replaceAll(" ", "_") || "project";
  return `${loadPolicy().defaultOutputDir}_${projectName}_${timestamp}`;
}

export function generateFiletree(files: SourceFile[], root: string): string {
  const paths = [...files.map((f) => f.relPath)].sort();
  const typeCounts = new Map<string, number>();
  for (const source of files) {
    typeCounts.set(source.category, (typeCounts.get(source.category) ?? 0) + 1);
  }
  const rootPath = basename(root).replaceAll(" ", "_") || "project";
  const lines: string[] = [
    `root: ${rootPath}`,
    `file_count: ${paths.length}`,
    "",
    "paths:",
    ...paths.map((p) => `${p},`),
    "",
    "types:",
  ];
  for (const category of [...typeCounts.keys()].sort()) {
    lines.push(`${category}: ${typeCounts.get(category)}`);
  }
  return lines.join("\n");
}
