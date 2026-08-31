package com.asjnaang.buildaicontext.engine

import java.nio.file.Files
import java.nio.file.Path
import java.time.Instant

private val DEP_FILENAMES = setOf(
    "package.json", "requirements.txt", "pyproject.toml", "Cargo.toml", "go.mod", "pom.xml",
    "build.gradle", "build.gradle.kts", "Gemfile", "Podfile", "composer.json", "setup.py", "setup.cfg",
)

private val FRAMEWORK_INDICATORS = linkedMapOf(
    "typescript" to listOf("tsconfig.json"),
    "react" to listOf("*.tsx"),
    "vue" to listOf("*.vue"),
    "svelte" to listOf("*.svelte"),
    "django" to listOf("manage.py", "settings.py"),
    "flask" to listOf("app.py", "wsgi.py"),
    "fastapi" to listOf("main.py", "requirements.txt"),
    "spring" to listOf("pom.xml", "build.gradle"),
    "rails" to listOf("Gemfile", "config.ru"),
    "flutter" to listOf("pubspec.yaml"),
)

fun detectDependencyFiles(allFiles: List<SourceFile>): List<String> {
    val interesting = ArrayList<String>()
    for (f in allFiles) {
        if (Path.of(f.relPath).fileName.toString() in DEP_FILENAMES) interesting.add(f.relPath)
    }
    return interesting
}

fun detectFrameworks(allFiles: List<SourceFile>): List<String> {
    val frameworks = ArrayList<String>()
    for ((fw, indicators) in FRAMEWORK_INDICATORS) {
        for (indicator in indicators) {
            if (allFiles.any { f ->
                    f.relPath == indicator ||
                        Path.of(f.relPath).fileName.toString() == indicator ||
                        (indicator.startsWith("*") && Path.of(f.relPath).fileName.toString().endsWith(indicator.substring(1)))
                }
            ) {
                frameworks.add(fw)
                break
            }
        }
    }
    return frameworks
}

fun suggestReadingOrder(allFiles: List<SourceFile>): List<String> {
    val priority = ArrayList<String>()
    val entry = setOf("main.py", "app.py", "index.ts", "index.js", "Main.kt")
    val config = setOf("package.json", "tsconfig.json", "settings.py", "application.yaml")
    val keyDirs = setOf("src", "lib", "app", "core", "models", "services")
    for (f in allFiles) {
        if (Path.of(f.relPath).fileName.toString() in entry) priority.add(f.relPath)
    }
    for (f in allFiles) {
        if (Path.of(f.relPath).fileName.toString() in config && f.relPath !in priority) priority.add(f.relPath)
    }
    for (f in allFiles) {
        val first = f.relPath.split('/').first()
        if (first in keyDirs && f.relPath !in priority) priority.add(f.relPath)
    }
    return priority
}

fun summarizeByCategory(files: List<SourceFile>): Map<String, Map<String, Int>> {
    val summary = LinkedHashMap<String, MutableMap<String, Int>>()
    for (item in files) {
        val slot = summary.getOrPut(item.category) { mutableMapOf("files" to 0, "lines" to 0, "bytes" to 0) }
        slot["files"] = slot.getValue("files") + 1
        slot["lines"] = slot.getValue("lines") + item.lineCount
        slot["bytes"] = slot.getValue("bytes") + item.sizeBytes.toInt()
    }
    return summary
}

fun summarizeTopFolders(files: List<SourceFile>, maxDepth: Int = 2): Map<String, Map<String, Int>> {
    val summary = LinkedHashMap<String, MutableMap<String, Int>>()
    for (item in files) {
        val parts = item.relPath.split('/').take(maxDepth)
        val folder = if (parts.size > 1) parts.dropLast(1).joinToString("/") else "."
        val slot = summary.getOrPut(folder) { mutableMapOf("files" to 0, "lines" to 0) }
        slot["files"] = slot.getValue("files") + 1
        slot["lines"] = slot.getValue("lines") + item.lineCount
    }
    return summary.entries
        .sortedWith(compareByDescending<Map.Entry<String, MutableMap<String, Int>>> { it.value.getValue("files") }.thenBy { it.key })
        .associate { it.key to it.value }
}

fun writeProjectOverview(
    root: String,
    allFiles: List<SourceFile>,
    selectedFiles: List<SourceFile>,
    outputDir: String,
    selectionMetadata: SelectionMetadata,
    manifestName: String,
): String {
    val policy = loadPolicy()
    val depFiles = detectDependencyFiles(allFiles)
    val frameworks = detectFrameworks(allFiles)
    val categorySummary = summarizeByCategory(selectedFiles)
    val folderSummary = summarizeTopFolders(selectedFiles)
    val readingOrder = suggestReadingOrder(allFiles)
    val lines = ArrayList<String>()
    lines.add("=".repeat(60))
    lines.add("PROJECT OVERVIEW: ${Path.of(root).fileName}")
    lines.add("=".repeat(60))
    lines.add("Generated: ${Instant.now()}")
    lines.add("Manifest: $manifestName")
    lines.add("")
    lines.add("📊 PROJECT STATISTICS")
    lines.add("-".repeat(40))
    lines.add("  Total files in project: ${allFiles.size}")
    lines.add("  Files exported: ${selectedFiles.size}")
    lines.add("  Selection mode: ${selectionMetadata.selectionMode}")
    lines.add("")
    if (frameworks.isNotEmpty()) {
        lines.add("🚀 DETECTED FRAMEWORKS")
        lines.add("-".repeat(40))
        for (fw in frameworks) lines.add("  • $fw")
        lines.add("")
    }
    if (depFiles.isNotEmpty()) {
        lines.add("📦 DEPENDENCY FILES")
        lines.add("-".repeat(40))
        for (dep in depFiles.take(10)) lines.add("  • $dep")
        lines.add("")
    }
    lines.add("📁 FILES BY CATEGORY")
    lines.add("-".repeat(40))
    val catEntries = categorySummary.entries.sortedByDescending { it.value.getValue("files") }
    for ((cat, stats) in catEntries) {
        val desc = policy.categoryDescriptions[cat] ?: cat
        lines.add(
            "  ${cat.padEnd(15)} ${stats.getValue("files").toString().padStart(4)} files  ${stats.getValue("lines").toString().padStart(7)} lines  | $desc",
        )
    }
    lines.add("")
    lines.add("📂 TOP FOLDERS")
    lines.add("-".repeat(40))
    for ((folder, stats) in folderSummary.entries.take(10)) {
        lines.add(
            "  ${folder.padEnd(20)} ${stats.getValue("files").toString().padStart(4)} files  ${stats.getValue("lines").toString().padStart(7)} lines",
        )
    }
    lines.add("")
    if (readingOrder.isNotEmpty()) {
        lines.add("📖 SUGGESTED READING ORDER")
        lines.add("-".repeat(40))
        for (i in 0 until minOf(20, readingOrder.size)) {
            lines.add("  ${(i + 1).toString().padStart(3)}. ${readingOrder[i]}")
        }
        if (readingOrder.size > 20) {
            lines.add("  ... and ${readingOrder.size - 20} more")
        }
        lines.add("")
    }
    lines.add("=".repeat(60))
    lines.add("END OF PROJECT OVERVIEW")
    lines.add("=".repeat(60))
    val outputPath = Path.of(outputDir).resolve("PROJECT_OVERVIEW.txt")
    Files.writeString(outputPath, lines.joinToString("\n"))
    return outputPath.toString()
}
