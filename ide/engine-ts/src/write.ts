import { mkdirSync, writeFileSync } from "node:fs";
import { basename, dirname, isAbsolute, join } from "node:path";
import { packChunks, renderChunkBlock, splitIntoChunks } from "./chunk.ts";
import {
  extractTimestampFromDirName,
  generateFiletree,
  generateTimestamp,
  sanitizeOutputDirName,
} from "./filetree.ts";
import { generateGraph } from "./graph.ts";
import { updateGitignore } from "./gitignore.ts";
import { writeGzipExport, type GzipSource } from "./gzip.ts";
import { writeProjectOverview } from "./overview.ts";
import { loadPolicy } from "./policy.ts";
import { assertTransport, promptContentForTransport, promptOutputName, setPromptDir } from "./prompt.ts";
import { pathMatchesAnyPattern } from "./scan.ts";
import { EngineCanceled, type Catalog, type ExportOptions, type ExportResult, type Selection } from "./types.ts";

export { setPromptDir };
export function setPromptPath(path: string): void {
  setPromptDir(path.endsWith(".md") ? dirname(path) : path);
}

function throwIfCanceled(isCanceled?: () => boolean): void {
  if (isCanceled?.()) throw new EngineCanceled();
}

function resolveOutputDir(root: string, outputDir?: string): string {
  if (!outputDir) return join(root, sanitizeOutputDirName(root));
  return isAbsolute(outputDir) ? outputDir : join(root, outputDir);
}

export async function exportCatalog(
  catalog: Catalog,
  selection: Selection,
  options: ExportOptions,
): Promise<ExportResult> {
  throwIfCanceled(options.isCanceled);
  const policy = loadPolicy();
  const root = catalog.workspace;
  const transport = assertTransport(options.transport ?? "tar-gz");
  if (transport === "tar-gz" && options.redact) {
    throw new Error("--redact requires --transport text");
  }
  const includeSecretFiles = options.includeSecretFiles === true;
  const files = includeSecretFiles
    ? selection.files
    : selection.files.filter((f) => !pathMatchesAnyPattern(f.relPath, policy.defaultSecretPatterns));
  const effective = { ...selection, files };
  const maxLines = policy.bundleMaxLines;
  const maxFileLines = options.forceBundle ? 0 : options.maxFileLines;
  const outDir = resolveOutputDir(root, options.outputDir);
  mkdirSync(outDir, { recursive: true });
  const timestamp = extractTimestampFromDirName(basename(outDir));
  const filetreeContent = generateFiletree(catalog.files, root);
  const folderName = basename(root).replaceAll(" ", "_");
  const filetreeName = `${folderName}_file_tree_${timestamp}.txt`;
  const promptName = promptOutputName();
  const promptPath = join(outDir, promptName);
  writeFileSync(promptPath, promptContentForTransport(transport, options.task), "utf8");

  if (transport === "tar-gz") {
    throwIfCanceled(options.isCanceled);
    const gzipSources: GzipSource[] = effective.files.map((file) => ({
      relPath: file.relPath,
      category: file.category,
      sizeBytes: file.sizeBytes,
      sha256: file.sha256,
      data: file.snapshotBytes,
      mode: file.mode || 0o644,
      encoding: file.encoding,
    }));
    const gzip = writeGzipExport({
      outputDir: outDir,
      folderName,
      timestamp,
      sources: gzipSources,
      split: options.split === true,
    });
    const warnings = effective.files
      .filter((file) => options.maxFileLines > 0 && file.lineCount >= options.maxFileLines)
      .map((file) => ({
        path: file.relPath,
        reason: "large_file_warning",
        line_count: file.lineCount,
        threshold: options.maxFileLines,
      }));
    const manifest: Record<string, unknown> = {
      tool: "build-ai-context",
      created_at_utc: new Date().toISOString(),
      project_root: root,
      max_lines_per_bundle: maxLines,
      max_file_lines: maxFileLines,
      bundle_count: 0,
      skip_secret_like_files: !includeSecretFiles,
      schema_version: gzip.reassembly.length ? 5 : options.split ? 4 : 3,
      selection: {
        selection_mode: selection.metadata.selectionMode,
        selected_categories: selection.metadata.selectedCategories,
        selected_paths: selection.metadata.selectedPaths,
        name_filters: selection.metadata.nameFilters,
        missing_paths: selection.metadata.missingPaths,
      },
      selected_files: effective.files.map((f) => f.relPath),
      transported_files: gzip.logicalPaths,
      filetree: filetreeName,
      summary: {
        selected_file_count: effective.files.length,
        selected_total_lines: effective.files.reduce((n, f) => n + f.lineCount, 0),
        selected_total_bytes: effective.files.reduce((n, f) => n + f.sizeBytes, 0),
        transported_file_count: gzip.archiveEntries.length,
        transported_total_bytes: gzip.archiveEntries.reduce((n, e) => n + Number(e.size_bytes), 0),
        skipped_counts: catalog.skipped,
        skipped_during_pack_count: 0,
        warning_count: warnings.length,
      },
      skipped_during_pack: [],
      warnings,
      bundles: [],
      payload_count: gzip.payloadRecords.length,
      archive_entries: gzip.archiveEntries,
      transport: {
        format: "tar+gzip+base64",
        split: options.split === true,
        payload_count: gzip.payloadRecords.length,
        payloads: gzip.payloadRecords,
        deterministic: true,
        reassembly: gzip.reassembly,
        ...(options.split ? {} : Object.fromEntries(Object.entries(gzip.payloadRecords[0] ?? {}).filter(([key]) => !["part", "part_count", "entries"].includes(key)))),
      },
    };
    const manifestName = `${folderName}_manifest_${timestamp}.json`;
    const manifestPath = join(outDir, manifestName);
    writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n", "utf8");
    throwIfCanceled(options.isCanceled);
    if (options.updateGitignore) updateGitignore(root, filetreeName);
    return {
      outputDir: outDir,
      manifestPath,
      bundlePaths: gzip.payloadPaths,
      filetreeEmbedded: true,
      promptPath,
      filesExported: gzip.logicalPaths.length,
      bundlesCreated: gzip.payloadRecords.length,
      warnings,
      skippedDuringPack: [],
    };
  }

  const { chunks, skipped: splitSkipped } = splitIntoChunks(
    effective.files,
    maxLines,
    options.redact,
    maxFileLines,
  );
  throwIfCanceled(options.isCanceled);
  const warnings = splitSkipped.filter((item) => item.reason === "large_file_warning");
  const skippedDuringSplit = splitSkipped.filter((item) => item.reason !== "large_file_warning");
  const packed = packChunks(chunks, maxLines, options.redact);
  const skippedDuringPack = [...skippedDuringSplit, ...packed.skipped];

  const sourceLookup = new Map(effective.files.map((s) => [s.relPath, s]));
  const manifest: Record<string, unknown> = {
    tool: "build-ai-context",
    created_at_utc: new Date().toISOString(),
    project_root: root,
    max_lines_per_bundle: maxLines,
    max_file_lines: options.maxFileLines,
    bundle_count: packed.bundles.length,
    skip_secret_like_files: !includeSecretFiles,
    selection: {
      selection_mode: selection.metadata.selectionMode,
      selected_categories: selection.metadata.selectedCategories,
      selected_paths: selection.metadata.selectedPaths,
      name_filters: selection.metadata.nameFilters,
      missing_paths: selection.metadata.missingPaths,
    },
    selected_files: effective.files.map((f) => f.relPath),
    filetree: filetreeName,
    summary: {
      selected_file_count: effective.files.length,
      selected_total_lines: effective.files.reduce((n, f) => n + f.lineCount, 0),
      selected_total_bytes: effective.files.reduce((n, f) => n + f.sizeBytes, 0),
      skipped_counts: catalog.skipped,
      skipped_during_pack_count: skippedDuringPack.length,
      warning_count: warnings.length,
    },
    skipped_during_pack: skippedDuringPack,
    warnings,
    bundles: [] as unknown[],
  };

  const bundlePaths: string[] = [];
  const exportedRels = new Set<string>();
  packed.bundles.forEach((bundle, index0) => {
    throwIfCanceled(options.isCanceled);
    const index = index0 + 1;
    const bundleName = `${folderName}_bundle_${String(index).padStart(3, "0")}_${timestamp}.txt`;
    const bundlePath = join(outDir, bundleName);
    const textParts: string[] = [];
    let nextBundleLine = 1;
    const bundleFiles: Record<string, unknown>[] = [];

    if (index === 1 && filetreeContent) {
      const header = `${"=".repeat(60)}\n===== FILETREE: Project Structure =====\n${"=".repeat(60)}\n`;
      const footer = `\n${"=".repeat(60)}\n===== END FILETREE =====\n${"=".repeat(60)}\n`;
      const block = header + filetreeContent + footer;
      textParts.push(block);
      const filetreeLineCount = block.split(/\n/).length - (block.endsWith("\n") ? 1 : 0);
      bundleFiles.push({
        path: filetreeName,
        category: "filetree",
        size_bytes: filetreeContent.length,
        sha256: "",
        total_file_lines: filetreeLineCount,
        chunk_index: 1,
        chunk_count: 1,
        file_start_line: 1,
        file_end_line: filetreeLineCount,
        file_line_count: filetreeLineCount,
        bundle_start_line: 1,
        bundle_end_line: filetreeLineCount,
        bundle_line_count: filetreeLineCount,
      });
      nextBundleLine = filetreeLineCount + 1;
    }

    for (const chunk of bundle) {
      throwIfCanceled(options.isCanceled);
      const source = sourceLookup.get(chunk.relPath);
      if (!source) continue;
      exportedRels.add(chunk.relPath);
      const blockText = renderChunkBlock(chunk, options.redact);
      const blockLineCount = blockText.split(/\n/).length - (blockText.endsWith("\n") ? 1 : 0);
      const bundleStartLine = nextBundleLine;
      const bundleEndLine = nextBundleLine + blockLineCount - 1;
      nextBundleLine = bundleEndLine + 1;
      textParts.push(blockText);
      bundleFiles.push({
        path: chunk.relPath,
        category: chunk.category,
        size_bytes: source.sizeBytes,
        sha256: source.sha256,
        total_file_lines: source.lineCount,
        chunk_index: chunk.chunkIndex,
        chunk_count: chunk.chunkCount,
        file_start_line: chunk.startLine,
        file_end_line: chunk.endLine,
        file_line_count: chunk.lines.length,
        bundle_start_line: bundleStartLine,
        bundle_end_line: bundleEndLine,
        bundle_line_count: blockLineCount,
      });
    }

    writeFileSync(bundlePath, textParts.join(""), "utf8");
    bundlePaths.push(bundlePath);
    (manifest.bundles as unknown[]).push({ bundle: bundleName, files: bundleFiles });
  });

  const manifestName = `${folderName}_manifest_${timestamp}.json`;
  const manifestPath = join(outDir, manifestName);
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), "utf8");

  let overviewPath: string | undefined;
  if (options.projectOverview) {
    overviewPath = writeProjectOverview(
      root,
      catalog.files,
      effective.files,
      outDir,
      selection.metadata,
      manifestName,
    );
  }

  let graphPath: string | undefined;
  if (options.writeGraph) {
    throwIfCanceled(options.isCanceled);
    const content = generateGraph(catalog.files, root, options.writeGraph);
    graphPath = join(outDir, `${folderName}_code_graph_${timestamp}.${options.writeGraph}`);
    writeFileSync(graphPath, content, "utf8");
  }

  throwIfCanceled(options.isCanceled);
  if (options.updateGitignore) updateGitignore(root, filetreeName);

  return {
    outputDir: outDir,
    manifestPath,
    bundlePaths,
    filetreeEmbedded: true,
    graphPath,
    overviewPath,
    promptPath,
    filesExported: exportedRels.size,
    bundlesCreated: packed.bundles.length,
    warnings,
    skippedDuringPack,
  };
}

export function writeStandaloneFiletree(catalog: Catalog, shouldUpdateGitignore = true): string {
  const timestamp = generateTimestamp();
  const folderName = basename(catalog.workspace).replaceAll(" ", "_");
  const name = `${folderName}_file_tree_${timestamp}.txt`;
  const path = join(catalog.workspace, name);
  writeFileSync(path, generateFiletree(catalog.files, catalog.workspace), "utf8");
  if (shouldUpdateGitignore) updateGitignore(catalog.workspace, name);
  return path;
}

export function writeStandaloneGraph(
  catalog: Catalog,
  format: "txt" | "json",
  shouldUpdateGitignore = true,
): string {
  const timestamp = generateTimestamp();
  const folderName = basename(catalog.workspace).replaceAll(" ", "_");
  const name = `${folderName}_code_graph_${timestamp}.${format}`;
  const path = join(catalog.workspace, name);
  writeFileSync(path, generateGraph(catalog.files, catalog.workspace, format), "utf8");
  if (shouldUpdateGitignore) updateGitignore(catalog.workspace, name);
  return path;
}
