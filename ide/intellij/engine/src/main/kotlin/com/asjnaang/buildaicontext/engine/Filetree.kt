package com.asjnaang.buildaicontext.engine

import java.nio.file.Path
import java.time.Clock
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

private val TIMESTAMP_FMT: DateTimeFormatter =
    DateTimeFormatter.ofPattern("yyyyMMdd'T'HHmmss'Z'").withZone(ZoneOffset.UTC)

fun generateTimestamp(clock: Clock = Clock.systemUTC()): String {
    return TIMESTAMP_FMT.format(clock.instant())
}

fun isTimestamp(s: String): Boolean = Regex("^\\d{8}T\\d{6}Z$").matches(s)

fun extractTimestampFromDirName(dirName: String): String {
    val last = dirName.substringAfterLast('_')
    return if (isTimestamp(last)) last else generateTimestamp()
}

fun sanitizeOutputDirName(root: String): String {
    val timestamp = generateTimestamp()
    val projectName = Path.of(root).fileName.toString().replace(" ", "_").ifEmpty { "project" }
    return "${loadPolicy().defaultOutputDir}_${projectName}_$timestamp"
}

fun generateFiletree(files: List<SourceFile>, root: String): String {
    val paths = files.map { it.relPath }.sortedWith { a, b -> a.compareTo(b) }
    val typeCounts = LinkedHashMap<String, Int>()
    for (source in files) {
        typeCounts[source.category] = (typeCounts[source.category] ?: 0) + 1
    }
    val rootPath = Path.of(root).fileName.toString().replace(" ", "_").ifEmpty { "project" }
    val lines = ArrayList<String>()
    lines.add("root: $rootPath")
    lines.add("file_count: ${paths.size}")
    lines.add("")
    lines.add("paths:")
    for (p in paths) lines.add("$p,")
    lines.add("")
    lines.add("types:")
    for (category in typeCounts.keys.sortedWith { a, b -> a.compareTo(b) }) {
        lines.add("$category: ${typeCounts[category]}")
    }
    return lines.joinToString("\n")
}
