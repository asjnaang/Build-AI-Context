package com.asjnaang.buildaicontext.engine

class EngineCanceled : RuntimeException("canceled")

data class ScanOptions(
    val includeSecretFiles: Boolean = false,
    val forceIgnoredPaths: List<String> = emptyList(),
    val forceIncludeFormats: List<String> = emptyList(),
    val excludePaths: List<String> = emptyList(),
    val isCanceled: () -> Boolean = { false },
)

data class SourceFile(
    val relPath: String,
    val absPath: String,
    val category: String,
    val lineCount: Int,
    val sizeBytes: Long,
    val sha256: String,
    val lines: List<String>,
    val snapshotBytes: ByteArray = byteArrayOf(),
    val mode: Int = 420,
    val encoding: String = "text",
)

data class Catalog(
    val workspace: String,
    val files: List<SourceFile>,
    val skipped: Map<String, Int>,
)

data class Filters(
    val categories: MutableList<String> = mutableListOf(),
    val paths: MutableList<String> = mutableListOf(),
    val nameFilters: MutableList<String> = mutableListOf(),
    val keywords: MutableList<String> = mutableListOf(),
    var categoriesConstrained: Boolean = false,
)

data class SelectionMetadata(
    val selectionMode: String,
    val selectedCategories: List<String>,
    val selectedPaths: List<String>,
    val nameFilters: List<String>,
    val missingPaths: List<String>,
)

data class Selection(
    val files: List<SourceFile>,
    val metadata: SelectionMetadata,
)

data class ExportOptions(
    val outputDir: String? = null,
    val maxFileLines: Int = 3000,
    val redact: Boolean = false,
    val projectOverview: Boolean = false,
    val writeGraph: String? = null,
    val updateGitignore: Boolean = true,
    val includeSecretFiles: Boolean = false,
    val transport: String = "tar-gz",
    val forceBundle: Boolean = false,
    val split: Boolean = false,
    val task: String? = null,
    val isCanceled: () -> Boolean = { false },
)

data class ExportResult(
    val outputDir: String,
    val manifestPath: String,
    val bundlePaths: List<String>,
    val filetreeEmbedded: Boolean = true,
    val graphPath: String? = null,
    val overviewPath: String? = null,
    val promptPath: String,
    val filesExported: Int,
    val bundlesCreated: Int,
    val warnings: List<Map<String, Any?>>,
    val skippedDuringPack: List<Map<String, Any?>>,
)

data class FileChunk(
    val relPath: String,
    val category: String,
    val chunkIndex: Int,
    val chunkCount: Int,
    val startLine: Int,
    val endLine: Int,
    val totalFileLines: Int,
    val lines: List<String>,
)

data class EnginePolicy(
    val bundleMaxLines: Int,
    val largeFileWarnLines: Int,
    val largeFileSkipLines: Int,
    val textEncoding: String,
    val defaultOutputDir: String,
    val categoryExtensions: Map<String, List<String>>,
    val categoryAliases: Map<String, String>,
    val categoryDescriptions: Map<String, String>,
    val specialFilenames: List<String>,
    val defaultExcludedDirs: List<String>,
    val defaultExcludedPrefixes: List<String>,
    val extraExcludedPatterns: List<String>,
    val defaultSecretPatterns: List<String>,
    val redactionMark: String,
)
