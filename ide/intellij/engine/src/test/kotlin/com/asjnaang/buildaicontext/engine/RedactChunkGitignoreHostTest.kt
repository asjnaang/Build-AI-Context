package com.asjnaang.buildaicontext.engine

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.nio.file.Files
import java.nio.file.Path

class RedactTest {
    @Test
    fun redactsJwt() {
        val jwt =
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ.signaturexx"
        assertEquals("<REDACTED>", redactText(jwt))
    }

    @Test
    fun redactsBearerHeader() {
        val out = redactText("Authorization: Bearer abcdefghijklmnop")
        assertTrue(out.contains("Authorization: Bearer <REDACTED>"))
    }

    @Test
    fun redactsAwsKey() {
        assertEquals("<REDACTED>", redactText("AKIAIOSFODNN7EXAMPLE"))
    }

    @Test
    fun redactsGithubToken() {
        val tok = "ghp_" + "a".repeat(36)
        assertEquals("<REDACTED>", redactText(tok))
    }

    @Test
    fun redactsEnvAssignment() {
        assertEquals("API_KEY=<REDACTED>", redactText("API_KEY=supersecretvalue"))
    }
}

class ChunkTest {
    @Test
    fun chunkBlockMatchesPythonHeaderForm() {
        val chunk = FileChunk(
            relPath = "dummy.py",
            category = "python",
            chunkIndex = 1,
            chunkCount = 1,
            startLine = 1,
            endLine = 1,
            totalFileLines = 1,
            lines = listOf("x"),
        )
        val expected = listOf(
            "=".repeat(60),
            "===== BEGIN FILE: dummy.py =====",
            "# category : python",
            "# chunk : 1/1",
            "# line_range : 1-1",
            "# total_lines : 1",
            "=".repeat(60),
            "x",
            "=".repeat(60),
            "===== END FILE: dummy.py (chunk 1/1) =====",
            "=".repeat(60),
            "",
        ).joinToString("\n")
        assertEquals(expected, renderChunkBlock(chunk, false))
    }

    @Test
    fun defaultMaxFileLinesSkips3000LineFiles() {
        val lines = List(3000) { "x" }
        val file = SourceFile(
            relPath = "big.py",
            absPath = "/tmp/big.py",
            category = "python",
            lineCount = 3000,
            sizeBytes = 3000,
            sha256 = "x",
            lines = lines,
        )
        val skipped = splitIntoChunks(listOf(file), 8000, false, 3000)
        assertEquals(0, skipped.first.size)
        assertEquals("large_file_exceeds_skip_threshold", skipped.second[0]["reason"])
        val unlimited = splitIntoChunks(listOf(file), 8000, false, 0)
        assertTrue(unlimited.first.isNotEmpty())
    }
}

class GitignoreTest {
    @Test
    fun updateGitignoreWritesPatterns(@TempDir dir: Path) {
        updateGitignore(dir.toString(), "proj_file_tree_TIMESTAMP.txt")
        val text = Files.readString(dir.resolve(".gitignore"))
        assertTrue(text.contains("exported_sources*/"))
        assertTrue(text.contains("*_file_tree_*.txt"))
        assertTrue(text.contains("*_code_graph_*.txt"))
        assertTrue(text.contains("*_code_graph_*.json"))
        updateGitignore(dir.toString(), "proj_file_tree_TIMESTAMP.txt")
        val again = Files.readString(dir.resolve(".gitignore"))
        assertEquals(text, again)
    }
}

class HostStateTest {
    @Test
    fun scanThenCategoryExportWritesManifest(@TempDir dir: Path) {
        val catalog = scan(smallPyWorkspace().toString(), ScanOptions(includeSecretFiles = false))
        val state = HostState()
        state.applyScan(catalog)
        assertTrue(state.checked.contains("main.py"))
        assertTrue(state.checked.contains("README.md"))
        state.toggleCategory("config_docs")
        assertTrue(state.checked.contains("main.py"))
        assertFalse(state.checked.contains("README.md"))
        val selection = state.exportSelection()
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
        assertTrue(Files.exists(Path.of(result.manifestPath)))
        val manifest = Files.readString(Path.of(result.manifestPath))
        assertTrue(manifest.contains("\"tool\": \"build-ai-context\""))
        assertTrue(selection.files.all { it.category == "python" })
    }

    @Test
    fun oversizedFilesUncheckedByDefault(@TempDir dir: Path) {
        val big = dir.resolve("big.py")
        Files.writeString(big, (1..3000).joinToString("\n") { "x" } + "\n")
        Files.writeString(dir.resolve("small.py"), "print(1)\n")
        val catalog = scan(dir.toString(), ScanOptions(includeSecretFiles = false))
        val state = HostState(maxFileLines = 3000)
        state.applyScan(catalog)
        assertTrue(state.checked.contains("small.py"))
        assertFalse(state.checked.contains("big.py"))
        val (included, oversized) = state.visibleFiles()
        assertTrue(included.any { it.relPath == "small.py" })
        assertTrue(oversized.any { it.relPath == "big.py" })
    }

    @Test
    fun selectAllThenClearVisibleResults() {
        val catalog = scan(smallPyWorkspace().toString(), ScanOptions(includeSecretFiles = false))
        val state = HostState()
        state.applyScan(catalog)
        assertTrue(state.allResultsChecked())
        state.setResultsChecked(false)
        assertFalse(state.allResultsChecked())
        assertEquals(0, state.exportSelection().files.size)
        state.setResultsChecked(true)
        assertTrue(state.allResultsChecked())
        assertTrue(state.exportSelection().files.isNotEmpty())
    }
}
