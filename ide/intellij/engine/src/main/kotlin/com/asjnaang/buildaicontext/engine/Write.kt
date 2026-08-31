package com.asjnaang.buildaicontext.engine

import java.nio.file.Files
import java.nio.file.Path
import java.time.Instant

private fun throwIfCanceled(isCanceled: () -> Boolean) {
    if (isCanceled()) throw EngineCanceled()
}

fun exportCatalog(catalog: Catalog, selection: Selection, options: ExportOptions): ExportResult {
    throwIfCanceled(options.isCanceled)
    val policy = loadPolicy()
    val root = catalog.workspace
    val files = if (options.includeSecretFiles) {
        selection.files
    } else {
        selection.files.filterNot { pathMatchesAnyPattern(it.relPath, policy.defaultSecretPatterns) }
    }
    val effective = selection.copy(files = files)
    val maxLines = policy.bundleMaxLines
    val (chunks, splitSkipped) = splitIntoChunks(
        effective.files,
        maxLines,
        options.redact,
        options.maxFileLines,
    )
    throwIfCanceled(options.isCanceled)
    val warnings = splitSkipped.filter { it["reason"] == "large_file_warning" }
    val skippedDuringSplit = splitSkipped.filter { it["reason"] != "large_file_warning" }
    val (packedBundles, packedSkipped) = packChunks(chunks, maxLines, options.redact)
    val skippedDuringPack = skippedDuringSplit + packedSkipped

    val outDir = if (!options.outputDir.isNullOrBlank()) {
        val requested = Path.of(options.outputDir)
        if (requested.isAbsolute) requested else Path.of(root).resolve(requested)
    } else {
        Path.of(root).resolve(sanitizeOutputDirName(root))
    }
    Files.createDirectories(outDir)
    val timestamp = extractTimestampFromDirName(outDir.fileName.toString())
    val filetreeContent = generateFiletree(catalog.files, root)
    val folderName = Path.of(root).fileName.toString().replace(" ", "_")
    val filetreeName = "${folderName}_file_tree_$timestamp.txt"

    val sourceLookup = effective.files.associateBy { it.relPath }
    val manifest = linkedMapOf<String, Any?>(
        "tool" to "build-ai-context",
        "created_at_utc" to Instant.now().toString(),
        "project_root" to root,
        "max_lines_per_bundle" to maxLines,
        "max_file_lines" to options.maxFileLines,
        "bundle_count" to packedBundles.size,
        "skip_secret_like_files" to !options.includeSecretFiles,
        "selection" to linkedMapOf(
            "selection_mode" to selection.metadata.selectionMode,
            "selected_categories" to selection.metadata.selectedCategories,
            "selected_paths" to selection.metadata.selectedPaths,
            "name_filters" to selection.metadata.nameFilters,
            "missing_paths" to selection.metadata.missingPaths,
        ),
        "selected_files" to effective.files.map { it.relPath },
        "filetree" to filetreeName,
        "summary" to linkedMapOf(
            "selected_file_count" to effective.files.size,
            "selected_total_lines" to effective.files.sumOf { it.lineCount },
            "selected_total_bytes" to effective.files.sumOf { it.sizeBytes },
            "skipped_counts" to catalog.skipped,
            "skipped_during_pack_count" to skippedDuringPack.size,
            "warning_count" to warnings.size,
        ),
        "skipped_during_pack" to skippedDuringPack,
        "warnings" to warnings,
        "bundles" to ArrayList<Any?>(),
    )

    val promptPath = outDir.resolve("prompt.md")
    Files.writeString(promptPath, loadPromptMd())

    val bundlePaths = ArrayList<String>()
    val exportedRels = LinkedHashSet<String>()
    packedBundles.forEachIndexed { index0, bundle ->
        throwIfCanceled(options.isCanceled)
        val index = index0 + 1
        val bundleName = "${folderName}_bundle_${index.toString().padStart(3, '0')}_$timestamp.txt"
        val bundlePath = outDir.resolve(bundleName)
        val textParts = ArrayList<String>()
        var nextBundleLine = 1
        val bundleFiles = ArrayList<Map<String, Any?>>()

        if (index == 1 && filetreeContent.isNotEmpty()) {
            val header = "${"=".repeat(60)}\n===== FILETREE: Project Structure =====\n${"=".repeat(60)}\n"
            val footer = "\n${"=".repeat(60)}\n===== END FILETREE =====\n${"=".repeat(60)}\n"
            val block = header + filetreeContent + footer
            textParts.add(block)
            val filetreeLineCount = splitLines(block).size
            bundleFiles.add(
                linkedMapOf(
                    "path" to filetreeName,
                    "category" to "filetree",
                    "size_bytes" to filetreeContent.length.toLong(),
                    "sha256" to "",
                    "total_file_lines" to filetreeLineCount,
                    "chunk_index" to 1,
                    "chunk_count" to 1,
                    "file_start_line" to 1,
                    "file_end_line" to filetreeLineCount,
                    "file_line_count" to filetreeLineCount,
                    "bundle_start_line" to 1,
                    "bundle_end_line" to filetreeLineCount,
                    "bundle_line_count" to filetreeLineCount,
                ),
            )
            nextBundleLine = filetreeLineCount + 1
        }

        for (chunk in bundle) {
            throwIfCanceled(options.isCanceled)
            val source = sourceLookup[chunk.relPath] ?: continue
            exportedRels.add(chunk.relPath)
            val blockText = renderChunkBlock(chunk, options.redact)
            val blockLineCount = splitLines(blockText).size
            val bundleStartLine = nextBundleLine
            val bundleEndLine = nextBundleLine + blockLineCount - 1
            nextBundleLine = bundleEndLine + 1
            textParts.add(blockText)
            bundleFiles.add(
                linkedMapOf(
                    "path" to chunk.relPath,
                    "category" to chunk.category,
                    "size_bytes" to source.sizeBytes,
                    "sha256" to source.sha256,
                    "total_file_lines" to source.lineCount,
                    "chunk_index" to chunk.chunkIndex,
                    "chunk_count" to chunk.chunkCount,
                    "file_start_line" to chunk.startLine,
                    "file_end_line" to chunk.endLine,
                    "file_line_count" to chunk.lines.size,
                    "bundle_start_line" to bundleStartLine,
                    "bundle_end_line" to bundleEndLine,
                    "bundle_line_count" to blockLineCount,
                ),
            )
        }

        Files.writeString(bundlePath, textParts.joinToString(""))
        bundlePaths.add(bundlePath.toString())
        @Suppress("UNCHECKED_CAST")
        (manifest["bundles"] as MutableList<Any?>).add(linkedMapOf("bundle" to bundleName, "files" to bundleFiles))
    }

    val manifestName = "${folderName}_manifest_$timestamp.json"
    val manifestPath = outDir.resolve(manifestName)
    Files.writeString(manifestPath, Json.stringify(manifest))

    var overviewPath: String? = null
    if (options.projectOverview) {
        overviewPath = writeProjectOverview(
            root,
            catalog.files,
            effective.files,
            outDir.toString(),
            selection.metadata,
            manifestName,
        )
    }

    var graphPath: String? = null
    if (!options.writeGraph.isNullOrBlank()) {
        throwIfCanceled(options.isCanceled)
        val content = generateGraph(catalog.files, root, options.writeGraph)
        graphPath = outDir.resolve("${folderName}_code_graph_$timestamp.${options.writeGraph}").toString()
        Files.writeString(Path.of(graphPath), content)
    }

    throwIfCanceled(options.isCanceled)
    if (options.updateGitignore) updateGitignore(root, filetreeName)

    return ExportResult(
        outputDir = outDir.toString(),
        manifestPath = manifestPath.toString(),
        bundlePaths = bundlePaths,
        filetreeEmbedded = true,
        graphPath = graphPath,
        overviewPath = overviewPath,
        promptPath = promptPath.toString(),
        filesExported = exportedRels.size,
        bundlesCreated = packedBundles.size,
        warnings = warnings,
        skippedDuringPack = skippedDuringPack,
    )
}

fun writeStandaloneFiletree(catalog: Catalog, shouldUpdateGitignore: Boolean = true): String {
    val timestamp = generateTimestamp()
    val folderName = Path.of(catalog.workspace).fileName.toString().replace(" ", "_")
    val name = "${folderName}_file_tree_$timestamp.txt"
    val path = Path.of(catalog.workspace).resolve(name)
    Files.writeString(path, generateFiletree(catalog.files, catalog.workspace))
    if (shouldUpdateGitignore) updateGitignore(catalog.workspace, name)
    return path.toString()
}

fun writeStandaloneGraph(catalog: Catalog, format: String, shouldUpdateGitignore: Boolean = true): String {
    val timestamp = generateTimestamp()
    val folderName = Path.of(catalog.workspace).fileName.toString().replace(" ", "_")
    val name = "${folderName}_code_graph_$timestamp.$format"
    val path = Path.of(catalog.workspace).resolve(name)
    Files.writeString(path, generateGraph(catalog.files, catalog.workspace, format))
    if (shouldUpdateGitignore) updateGitignore(catalog.workspace, name)
    return path.toString()
}
