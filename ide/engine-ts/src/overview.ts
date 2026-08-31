import { basename } from "node:path";
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { loadPolicy } from "./policy.ts";
import type { SelectionMetadata, SourceFile } from "./types.ts";

const DEP_FILENAMES = new Set([
  "package.json",
  "requirements.txt",
  "pyproject.toml",
  "Cargo.toml",
  "go.mod",
  "pom.xml",
  "build.gradle",
  "build.gradle.kts",
  "Gemfile",
  "Podfile",
  "composer.json",
  "setup.py",
  "setup.cfg",
]);

const FRAMEWORK_INDICATORS: Record<string, string[]> = {
  typescript: ["tsconfig.json"],
  react: ["*.tsx"],
  vue: ["*.vue"],
  svelte: ["*.svelte"],
  django: ["manage.py", "settings.py"],
  flask: ["app.py", "wsgi.py"],
  fastapi: ["main.py", "requirements.txt"],
  spring: ["pom.xml", "build.gradle"],
  rails: ["Gemfile", "config.ru"],
  flutter: ["pubspec.yaml"],
};

export function detectDependencyFiles(allFiles: SourceFile[]): string[] {
  const interesting: string[] = [];
  for (const f of allFiles) {
    if (DEP_FILENAMES.has(basename(f.relPath))) interesting.push(f.relPath);
  }
  return interesting;
}

export function detectFrameworks(allFiles: SourceFile[]): string[] {
  const frameworks: string[] = [];
  for (const [fw, indicators] of Object.entries(FRAMEWORK_INDICATORS)) {
    for (const indicator of indicators) {
      if (
        allFiles.some(
          (f) =>
            f.relPath === indicator ||
            basename(f.relPath) === indicator ||
            (indicator.startsWith("*") && basename(f.relPath).endsWith(indicator.slice(1))),
        )
      ) {
        frameworks.push(fw);
        break;
      }
    }
  }
  return frameworks;
}

export function suggestReadingOrder(allFiles: SourceFile[]): string[] {
  const priority: string[] = [];
  const entry = new Set(["main.py", "app.py", "index.ts", "index.js", "Main.kt"]);
  const config = new Set(["package.json", "tsconfig.json", "settings.py", "application.yaml"]);
  const keyDirs = new Set(["src", "lib", "app", "core", "models", "services"]);
  for (const f of allFiles) {
    if (entry.has(basename(f.relPath))) priority.push(f.relPath);
  }
  for (const f of allFiles) {
    if (config.has(basename(f.relPath)) && !priority.includes(f.relPath)) priority.push(f.relPath);
  }
  for (const f of allFiles) {
    const first = f.relPath.split("/")[0];
    if (keyDirs.has(first) && !priority.includes(f.relPath)) priority.push(f.relPath);
  }
  return priority;
}

export function summarizeByCategory(files: SourceFile[]): Record<string, { files: number; lines: number; bytes: number }> {
  const summary: Record<string, { files: number; lines: number; bytes: number }> = {};
  for (const item of files) {
    const slot = (summary[item.category] ??= { files: 0, lines: 0, bytes: 0 });
    slot.files += 1;
    slot.lines += item.lineCount;
    slot.bytes += item.sizeBytes;
  }
  return summary;
}

export function summarizeTopFolders(
  files: SourceFile[],
  maxDepth = 2,
): Record<string, { files: number; lines: number }> {
  const summary: Record<string, { files: number; lines: number }> = {};
  for (const item of files) {
    const parts = item.relPath.split("/").slice(0, maxDepth);
    const folder = parts.length > 1 ? parts.slice(0, -1).join("/") : ".";
    const slot = (summary[folder] ??= { files: 0, lines: 0 });
    slot.files += 1;
    slot.lines += item.lineCount;
  }
  return Object.fromEntries(
    Object.entries(summary).sort((a, b) => b[1].files - a[1].files || a[0].localeCompare(b[0])),
  );
}

export function writeProjectOverview(
  root: string,
  allFiles: SourceFile[],
  selectedFiles: SourceFile[],
  outputDir: string,
  selectionMetadata: SelectionMetadata,
  manifestName: string,
): string {
  const policy = loadPolicy();
  const depFiles = detectDependencyFiles(allFiles);
  const frameworks = detectFrameworks(allFiles);
  const categorySummary = summarizeByCategory(selectedFiles);
  const folderSummary = summarizeTopFolders(selectedFiles);
  const readingOrder = suggestReadingOrder(allFiles);
  const lines: string[] = [];
  lines.push("=".repeat(60));
  lines.push(`PROJECT OVERVIEW: ${basename(root)}`);
  lines.push("=".repeat(60));
  lines.push(`Generated: ${new Date().toISOString()}`);
  lines.push(`Manifest: ${manifestName}`);
  lines.push("");
  lines.push("📊 PROJECT STATISTICS");
  lines.push("-".repeat(40));
  lines.push(`  Total files in project: ${allFiles.length}`);
  lines.push(`  Files exported: ${selectedFiles.length}`);
  lines.push(`  Selection mode: ${selectionMetadata.selectionMode}`);
  lines.push("");
  if (frameworks.length) {
    lines.push("🚀 DETECTED FRAMEWORKS");
    lines.push("-".repeat(40));
    for (const fw of frameworks) lines.push(`  • ${fw}`);
    lines.push("");
  }
  if (depFiles.length) {
    lines.push("📦 DEPENDENCY FILES");
    lines.push("-".repeat(40));
    for (const dep of depFiles.slice(0, 10)) lines.push(`  • ${dep}`);
    lines.push("");
  }
  lines.push("📁 FILES BY CATEGORY");
  lines.push("-".repeat(40));
  for (const [cat, stats] of Object.entries(categorySummary).sort((a, b) => b[1].files - a[1].files)) {
    const desc = policy.categoryDescriptions[cat] ?? cat;
    lines.push(
      `  ${cat.padEnd(15)} ${String(stats.files).padStart(4)} files  ${String(stats.lines).padStart(7)} lines  | ${desc}`,
    );
  }
  lines.push("");
  lines.push("📂 TOP FOLDERS");
  lines.push("-".repeat(40));
  for (const [folder, stats] of Object.entries(folderSummary).slice(0, 10)) {
    lines.push(
      `  ${folder.padEnd(20)} ${String(stats.files).padStart(4)} files  ${String(stats.lines).padStart(7)} lines`,
    );
  }
  lines.push("");
  if (readingOrder.length) {
    lines.push("📖 SUGGESTED READING ORDER");
    lines.push("-".repeat(40));
    for (let i = 0; i < Math.min(20, readingOrder.length); i++) {
      lines.push(`  ${String(i + 1).padStart(3)}. ${readingOrder[i]}`);
    }
    if (readingOrder.length > 20) {
      lines.push(`  ... and ${readingOrder.length - 20} more`);
    }
    lines.push("");
  }
  lines.push("=".repeat(60));
  lines.push("END OF PROJECT OVERVIEW");
  lines.push("=".repeat(60));
  const outputPath = join(outputDir, "PROJECT_OVERVIEW.txt");
  writeFileSync(outputPath, lines.join("\n"), "utf8");
  return outputPath;
}
