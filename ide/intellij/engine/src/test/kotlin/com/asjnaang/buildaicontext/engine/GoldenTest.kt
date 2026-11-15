package com.asjnaang.buildaicontext.engine

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.nio.file.Files
import java.nio.file.Path

class GoldenTest {
    @Test
    fun filetreeMatchesGolden() {
        val catalog = scan(smallPyWorkspace().toString(), ScanOptions(includeSecretFiles = false))
        val actual = generateFiletree(catalog.files, catalog.workspace)
        val expected = Files.readString(smallPyGolden().resolve("filetree.txt"))
        assertEquals(expected, actual)
    }

    @Test
    fun graphTxtMatchesGolden() {
        val catalog = scan(smallPyWorkspace().toString(), ScanOptions(includeSecretFiles = false))
        val actual = generateGraph(catalog.files, catalog.workspace, "txt")
        val expected = Files.readString(smallPyGolden().resolve("graph.txt"))
        assertEquals(expected, actual)
    }

    @Test
    fun exportBundleBodyMatchesGolden(@TempDir dir: Path) {
        val catalog = scan(smallPyWorkspace().toString(), ScanOptions(includeSecretFiles = false))
        val selection = select(catalog, Filters())
        val result = exportCatalog(
            catalog,
            selection,
            ExportOptions(
                outputDir = dir.toString(),
                maxFileLines = 3000,
                redact = false,
                projectOverview = false,
                updateGitignore = false,
                transport = "text",
            ),
        )
        val bundle = Files.readString(Path.of(result.bundlePaths[0]))
        val expected = Files.readString(smallPyGolden().resolve("bundle.txt"))
        assertEquals(expected, normalizeExport(bundle, catalog.workspace))
    }
}
