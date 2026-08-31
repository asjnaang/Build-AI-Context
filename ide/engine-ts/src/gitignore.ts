import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

export function updateGitignore(root: string, _filetreeName: string): void {
  const gitignorePath = join(root, ".gitignore");
  const existing: string[] = existsSync(gitignorePath)
    ? readFileSync(gitignorePath, "utf8").split(/\n/)
    : [];
  if (existing.length && existing[existing.length - 1] === "") existing.pop();

  const newLines: string[] = [];
  const hasExported = existing.some((line) => line.includes("exported_sources") && !line.trim().startsWith("#"));
  const hasFiletree = existing.some((line) => line.includes("_file_tree_") && !line.trim().startsWith("#"));
  const hasGraphTxt = existing.some((line) => line.includes("*_code_graph_*.txt") && !line.trim().startsWith("#"));
  const hasGraphJson = existing.some((line) => line.includes("*_code_graph_*.json") && !line.trim().startsWith("#"));

  if (existing.length && existing[existing.length - 1].trim()) newLines.push("");

  if (!hasExported) {
    newLines.push("# Ignore exported source bundles");
    newLines.push("exported_sources*/");
  }
  if (!hasFiletree) {
    newLines.push("# Ignore filetree files (all timestamps)");
    newLines.push("*_file_tree_*.txt");
  }
  if (!hasGraphTxt) {
    newLines.push("# Ignore code graph files (all timestamps)");
    newLines.push("*_code_graph_*.txt");
  }
  if (!hasGraphJson) {
    newLines.push("# Ignore JSON code graph files (all timestamps)");
    newLines.push("*_code_graph_*.json");
  }

  if (newLines.length) {
    writeFileSync(gitignorePath, [...existing, ...newLines].join("\n") + "\n", "utf8");
  }
}
