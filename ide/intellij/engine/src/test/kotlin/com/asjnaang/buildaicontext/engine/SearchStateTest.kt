package com.asjnaang.buildaicontext.engine

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.nio.file.Files

class SearchStateTest {
    @Test
    fun searchAndFormatNarrowSelectAllAndExport() {
        val root = Files.createTempDirectory("baic-search-")
        Files.createDirectories(root.resolve("src"))
        Files.writeString(root.resolve("README.md"), "hello\n")
        Files.writeString(root.resolve("main.py"), "print(1)\n")
        Files.writeString(root.resolve("src/util.py"), "print(2)\n")
        val state = HostState()
        state.applyScan(scan(root.toString(), ScanOptions()))
        assertTrue(".py" in state.availableFormats())
        state.searchQuery = "src"
        state.formatFilter = ".py"
        assertEquals(listOf("src/util.py"), state.searchResults().map { it.relPath })
        state.checked.clear()
        assertEquals(1, state.selectAllResults())
        assertEquals(listOf("src/util.py"), state.exportSelection().files.map { it.relPath })
        state.searchQuery = "python"
        assertEquals(listOf("main.py", "src/util.py"), state.searchResults().map { it.relPath }.sorted())
    }
}
