package com.asjnaang.buildaicontext.engine

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class SelectTest {
    @Test
    fun emptyFiltersSelectAllCatalogFiles() {
        val catalog = scan(smallPyWorkspace().toString(), ScanOptions(includeSecretFiles = false))
        val selection = select(catalog, Filters())
        assertEquals(catalog.files.size, selection.files.size)
        assertEquals("non_interactive", selection.metadata.selectionMode)
    }

    @Test
    fun pyAliasSelectsPythonOnly() {
        val catalog = scan(smallPyWorkspace().toString(), ScanOptions(includeSecretFiles = false))
        val selection = select(catalog, Filters(categories = mutableListOf("py")))
        assertTrue(selection.files.all { it.category == "python" })
        assertTrue(selection.files.any { it.relPath == "main.py" })
        assertEquals("composed", selection.metadata.selectionMode)
    }

    @Test
    fun pathSrcKeepsUtil() {
        val catalog = scan(smallPyWorkspace().toString(), ScanOptions(includeSecretFiles = false))
        val selection = select(catalog, Filters(paths = mutableListOf("src")))
        assertEquals(listOf("src/util.py"), selection.files.map { it.relPath })
    }

    @Test
    fun keywordTodoMatchesMain() {
        val catalog = scan(smallPyWorkspace().toString(), ScanOptions(includeSecretFiles = false))
        val selection = select(catalog, Filters(keywords = mutableListOf("TODO")))
        assertTrue(selection.files.any { it.relPath == "main.py" })
    }

    @Test
    fun nameFilterUtil() {
        val catalog = scan(smallPyWorkspace().toString(), ScanOptions(includeSecretFiles = false))
        val selection = select(catalog, Filters(nameFilters = mutableListOf("util")))
        assertEquals(listOf("src/util.py"), selection.files.map { it.relPath })
    }
}
