package com.asjnaang.buildaicontext.engine

fun bundleHeader(chunk: FileChunk): String {
    return (
        "=".repeat(60) + "\n" +
            "===== BEGIN FILE: ${chunk.relPath} =====\n" +
            "# category : ${chunk.category}\n" +
            "# chunk : ${chunk.chunkIndex}/${chunk.chunkCount}\n" +
            "# line_range : ${chunk.startLine}-${chunk.endLine}\n" +
            "# total_lines : ${chunk.totalFileLines}\n" +
            "=".repeat(60) + "\n"
        )
}

fun bundleFooter(chunk: FileChunk): String {
    return (
        "=".repeat(60) + "\n" +
            "===== END FILE: ${chunk.relPath} (chunk ${chunk.chunkIndex}/${chunk.chunkCount}) =====\n" +
            "=".repeat(60) + "\n"
        )
}

fun renderChunkBlock(chunk: FileChunk, redact: Boolean): String {
    val parts = ArrayList<String>()
    parts.add(bundleHeader(chunk))
    for (line in chunk.lines) {
        parts.add((if (redact) redactText(line) else line) + "\n")
    }
    parts.add(bundleFooter(chunk))
    return parts.joinToString("")
}

fun chunkOverheadLines(redact: Boolean): Int {
    val dummy = FileChunk(
        relPath = "dummy.py",
        category = "python",
        chunkIndex = 1,
        chunkCount = 1,
        startLine = 1,
        endLine = 1,
        totalFileLines = 1,
        lines = listOf("x"),
    )
    return splitLines(renderChunkBlock(dummy, redact)).size - 1
}

fun splitIntoChunks(
    files: List<SourceFile>,
    maxLines: Int,
    redact: Boolean,
    maxFileLines: Int?,
): Pair<List<FileChunk>, List<Map<String, Any?>>> {
    val policy = loadPolicy()
    val chunks = ArrayList<FileChunk>()
    val skipped = ArrayList<Map<String, Any?>>()
    val overhead = chunkOverheadLines(redact)
    val skipThreshold = maxFileLines ?: policy.largeFileSkipLines

    for (source in files) {
        val lines = source.lines
        val totalLines = lines.size
        if (totalLines == 0) continue

        if (skipThreshold > 0 && totalLines >= skipThreshold) {
            skipped.add(
                linkedMapOf(
                    "path" to source.relPath,
                    "reason" to "large_file_exceeds_skip_threshold",
                    "line_count" to totalLines,
                    "threshold" to skipThreshold,
                ),
            )
            continue
        }

        if (totalLines >= policy.largeFileWarnLines) {
            skipped.add(
                linkedMapOf(
                    "path" to source.relPath,
                    "reason" to "large_file_warning",
                    "line_count" to totalLines,
                    "threshold" to policy.largeFileWarnLines,
                ),
            )
        }

        var effectiveMax = maxLines - overhead
        if (effectiveMax <= 0) effectiveMax = maxLines

        if (totalLines <= effectiveMax) {
            chunks.add(
                FileChunk(
                    relPath = source.relPath,
                    category = source.category,
                    chunkIndex = 1,
                    chunkCount = 1,
                    startLine = 1,
                    endLine = totalLines,
                    totalFileLines = totalLines,
                    lines = lines,
                ),
            )
        } else {
            val chunkCount = (totalLines + effectiveMax - 1) / effectiveMax
            for (i in 0 until chunkCount) {
                val start = i * effectiveMax
                val end = minOf(start + effectiveMax, totalLines)
                chunks.add(
                    FileChunk(
                        relPath = source.relPath,
                        category = source.category,
                        chunkIndex = i + 1,
                        chunkCount = chunkCount,
                        startLine = start + 1,
                        endLine = end,
                        totalFileLines = totalLines,
                        lines = lines.subList(start, end),
                    ),
                )
            }
        }
    }
    return chunks to skipped
}

fun packChunks(
    chunks: List<FileChunk>,
    maxLines: Int,
    redact: Boolean,
): Pair<List<List<FileChunk>>, List<Map<String, Any?>>> {
    val bundles = ArrayList<List<FileChunk>>()
    val skipped = ArrayList<Map<String, Any?>>()
    var current = ArrayList<FileChunk>()
    var currentLines = 0
    val overhead = chunkOverheadLines(redact)

    for (chunk in chunks) {
        val chunkLines = chunk.lines.size
        val totalNeeded = chunkLines + overhead
        if (totalNeeded > maxLines) {
            skipped.add(
                linkedMapOf(
                    "path" to chunk.relPath,
                    "reason" to "chunk_exceeds_max_lines",
                    "line_count" to chunkLines,
                    "max_lines" to maxLines,
                ),
            )
            continue
        }
        if (currentLines + totalNeeded > maxLines && current.isNotEmpty()) {
            bundles.add(current)
            current = ArrayList()
            currentLines = 0
        }
        current.add(chunk)
        currentLines += totalNeeded
    }
    if (current.isNotEmpty()) bundles.add(current)
    return bundles to skipped
}
