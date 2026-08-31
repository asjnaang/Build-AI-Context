package com.asjnaang.buildaicontext.engine

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class ScanTest {
    @Test
    fun scanFindsSupportedFilesAndSkipsSecretsAndExcludedDirs() {
        val catalog = scan(smallPyWorkspace().toString(), ScanOptions(includeSecretFiles = false))
        val rels = catalog.files.map { it.relPath }
        assertTrue(rels.contains("main.py"))
        assertTrue(rels.contains("src/util.py"))
        assertTrue(rels.contains("README.md"))
        assertFalse(rels.any { it.contains("node_modules") })
        assertFalse(rels.contains(".env"))
        assertEquals("python", catalog.files.find { it.relPath == "main.py" }?.category)
        assertEquals(listOf("README.md", "main.py", "src/util.py"), rels)
    }
}
