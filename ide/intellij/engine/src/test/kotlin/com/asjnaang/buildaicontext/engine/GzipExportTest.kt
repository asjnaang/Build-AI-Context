package com.asjnaang.buildaicontext.engine

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.nio.file.Files

class GzipExportTest {
    @Test
    fun gzipExportWritesPromptAndRestoresBytes() {
        val dir = Files.createTempDirectory("baic-kt-gz-")
        Files.writeString(dir.resolve("hello.py"), "print(1)\n")
        val catalog = scan(dir.toString(), ScanOptions(includeSecretFiles = false))
        val selection = select(catalog, Filters())
        val out = Files.createTempDirectory("baic-kt-gz-out-")
        val restored = Files.createTempDirectory("baic-kt-gz-rest-")
        restored.toFile().deleteRecursively()
        val result = exportCatalog(
            catalog,
            selection,
            ExportOptions(
                outputDir = out.toString(),
                maxFileLines = 3000,
                redact = false,
                projectOverview = false,
                updateGitignore = false,
                transport = "tar-gz",
                task = "Explain the changed parser",
            ),
        )
        assertTrue(result.promptPath.endsWith("baic_prompt.md"))
        assertTrue(Files.readString(java.nio.file.Path.of(result.promptPath)).contains("tar+gzip+base64"))
        assertTrue(Files.readString(java.nio.file.Path.of(result.promptPath)).contains("Explain the changed parser"))
        val (dest, count) = restoreExport(java.nio.file.Path.of(result.outputDir), restored, true)
        assertEquals(1, count)
        assertEquals("print(1)\n", Files.readString(dest.resolve("hello.py")))
    }

    @Test
    fun forceIgnoredPathsIncludesGitignoredFile() {
        val dir = Files.createTempDirectory("baic-kt-force-")
        Files.writeString(dir.resolve("keep.py"), "print(0)\n")
        Files.writeString(dir.resolve("secret.py"), "print(1)\n")
        Files.writeString(dir.resolve(".gitignore"), "secret.py\n")
        val skipped = scan(dir.toString(), ScanOptions())
        assertTrue(skipped.files.none { it.relPath == "secret.py" })
        val forced = scan(dir.toString(), ScanOptions(forceIgnoredPaths = listOf("secret.py")))
        assertTrue(forced.files.any { it.relPath == "secret.py" })
    }
}
