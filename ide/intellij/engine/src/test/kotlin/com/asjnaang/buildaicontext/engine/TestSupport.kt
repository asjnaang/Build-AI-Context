package com.asjnaang.buildaicontext.engine

import java.nio.file.Files
import java.nio.file.Path

internal fun testdataRoot(): Path {
    System.getProperty("baic.testdata")?.let { return Path.of(it) }
    var dir = Path.of("").toAbsolutePath()
    while (true) {
        val candidate = dir.resolve("ide/testdata")
        if (Files.isDirectory(candidate)) return candidate
        dir = dir.parent ?: break
    }
    error("ide/testdata not found")
}

internal fun smallPyWorkspace(): Path = testdataRoot().resolve("workspaces/small-py")

internal fun smallPyGolden(): Path = testdataRoot().resolve("golden/small-py")

internal fun normalizeExport(text: String, projectRoot: String): String {
    return text
        .replace(Regex("\\d{8}T\\d{6}Z"), "TIMESTAMP")
        .replace(Regex("\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z|\\+00:00)"), "TIMESTAMP")
        .replace(projectRoot, "PROJECT_ROOT")
}
