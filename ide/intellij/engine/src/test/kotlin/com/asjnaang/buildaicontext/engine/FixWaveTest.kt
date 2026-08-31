package com.asjnaang.buildaicontext.engine

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows
import org.junit.jupiter.api.io.TempDir
import java.nio.file.Files
import java.nio.file.Path

class FixWaveTest {
    @Test
    fun checkedOversizedFileIsWrittenWhenSkipDisabled(@TempDir dir: Path) {
        Files.writeString(dir.resolve("small.py"), "print(1)\n")
        Files.writeString(dir.resolve("big.py"), (1..3000).joinToString("\n") { "x" } + "\n")
        val catalog = scan(dir.toString(), ScanOptions(includeSecretFiles = false))
        val big = catalog.files.first { it.relPath == "big.py" }
        val out = Files.createTempDirectory("baic-out-")
        val result = exportCatalog(
            catalog,
            Selection(listOf(big), select(catalog, Filters()).metadata),
            ExportOptions(
                outputDir = out.toString(),
                maxFileLines = 0,
                redact = false,
                projectOverview = false,
                updateGitignore = false,
            ),
        )
        val bundle = Files.readString(Path.of(result.bundlePaths[0]))
        assertTrue(bundle.contains("===== BEGIN FILE: big.py ====="))
        assertFalse(result.skippedDuringPack.any { it["reason"] == "large_file_exceeds_skip_threshold" })
    }

    @Test
    fun canceledExportDoesNotPatchGitignore(@TempDir dir: Path) {
        Files.writeString(dir.resolve("small.py"), "print(1)\n")
        val catalog = scan(dir.toString(), ScanOptions(includeSecretFiles = false))
        val selection = select(catalog, Filters())
        assertThrows<EngineCanceled> {
            exportCatalog(
                catalog,
                selection,
                ExportOptions(
                    maxFileLines = 3000,
                    redact = false,
                    projectOverview = false,
                    updateGitignore = true,
                    isCanceled = { true },
                ),
            )
        }
        assertFalse(Files.exists(dir.resolve(".gitignore")))
    }

    @Test
    fun successfulExportPatchesGitignoreAfterBundles(@TempDir dir: Path) {
        Files.writeString(dir.resolve("small.py"), "print(1)\n")
        val catalog = scan(dir.toString(), ScanOptions(includeSecretFiles = false))
        val result = exportCatalog(
            catalog,
            select(catalog, Filters()),
            ExportOptions(
                maxFileLines = 3000,
                redact = false,
                projectOverview = false,
                updateGitignore = true,
            ),
        )
        assertTrue(Files.exists(Path.of(result.bundlePaths[0])))
        val gi = Files.readString(dir.resolve(".gitignore"))
        assertTrue(gi.contains("exported_sources*/"))
    }

    @Test
    fun relativeOutputDirResolvesUnderWorkspace(@TempDir dir: Path) {
        Files.writeString(dir.resolve("small.py"), "print(1)\n")
        val catalog = scan(dir.toString(), ScanOptions(includeSecretFiles = false))
        val result = exportCatalog(
            catalog,
            select(catalog, Filters()),
            ExportOptions(
                outputDir = "nested-out",
                maxFileLines = 3000,
                redact = false,
                projectOverview = false,
                updateGitignore = false,
            ),
        )
        assertEquals(dir.resolve("nested-out").toString(), result.outputDir)
        assertTrue(Files.isDirectory(dir.resolve("nested-out")))
    }

    @Test
    fun manifestSkipSecretLikeFilesFalseWhenIncludeSecretFiles(@TempDir dir: Path) {
        Files.writeString(dir.resolve("small.py"), "print(1)\n")
        Files.writeString(dir.resolve(".env"), "SECRET=1\n")
        val catalog = scan(dir.toString(), ScanOptions(includeSecretFiles = true))
        val result = exportCatalog(
            catalog,
            select(catalog, Filters()),
            ExportOptions(
                outputDir = Files.createTempDirectory("baic-out-").toString(),
                maxFileLines = 3000,
                redact = false,
                projectOverview = false,
                updateGitignore = false,
                includeSecretFiles = true,
            ),
        )
        val manifest = Files.readString(Path.of(result.manifestPath))
        assertTrue(manifest.contains("\"skip_secret_like_files\": false"))
    }

    @Test
    fun latin1EncodedFileIsReadable(@TempDir dir: Path) {
        Files.write(dir.resolve("latin.py"), byteArrayOf(0x23, 0x20, 0x63, 0x61, 0x66, 0xe9.toByte(), 0x0a))
        val catalog = scan(dir.toString(), ScanOptions(includeSecretFiles = false))
        val file = catalog.files.first { it.relPath == "latin.py" }
        assertEquals("# café", file.lines[0])
    }

    @Test
    fun explicitEmptyCategorySetSelectsZeroFiles() {
        val catalog = scan(smallPyWorkspace().toString(), ScanOptions(includeSecretFiles = false))
        val selection = select(catalog, Filters(categoriesConstrained = true))
        assertEquals(0, selection.files.size)
        assertEquals("composed", selection.metadata.selectionMode)
    }

    @Test
    fun uncheckingLastCategorySelectsZeroFiles() {
        val catalog = scan(smallPyWorkspace().toString(), ScanOptions(includeSecretFiles = false))
        val state = HostState()
        state.applyScan(catalog)
        val cats = catalog.files.map { it.category }.distinct()
        for (cat in cats) state.toggleCategory(cat)
        assertTrue(state.exportSelection().files.isEmpty())
    }
}
