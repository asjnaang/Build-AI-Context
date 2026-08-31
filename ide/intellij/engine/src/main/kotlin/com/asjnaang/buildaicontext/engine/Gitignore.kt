package com.asjnaang.buildaicontext.engine

import java.nio.file.Files
import java.nio.file.Path

@Suppress("UNUSED_PARAMETER")
fun updateGitignore(root: String, filetreeName: String = "") {
    val gitignorePath = Path.of(root).resolve(".gitignore")
    val existing = if (Files.isRegularFile(gitignorePath)) {
        splitLines(Files.readString(gitignorePath)).toMutableList()
    } else {
        mutableListOf()
    }

    val additions = ArrayList<String>()
    val hasExported = existing.any { "exported_sources" in it && !it.trimStart().startsWith("#") }
    val hasFiletree = existing.any { "_file_tree_" in it && !it.trimStart().startsWith("#") }
    val hasGraphTxt = existing.any { "*_code_graph_*.txt" in it && !it.trimStart().startsWith("#") }
    val hasGraphJson = existing.any { "*_code_graph_*.json" in it && !it.trimStart().startsWith("#") }

    if (!hasExported) {
        additions.add("# Ignore exported source bundles")
        additions.add("exported_sources*/")
    }
    if (!hasFiletree) {
        additions.add("# Ignore filetree files (all timestamps)")
        additions.add("*_file_tree_*.txt")
    }
    if (!hasGraphTxt) {
        additions.add("# Ignore code graph files (all timestamps)")
        additions.add("*_code_graph_*.txt")
    }
    if (!hasGraphJson) {
        additions.add("# Ignore JSON code graph files (all timestamps)")
        additions.add("*_code_graph_*.json")
    }

    if (additions.isNotEmpty()) {
        val newLines = ArrayList<String>()
        if (existing.isNotEmpty() && existing.last().isNotBlank()) newLines.add("")
        newLines.addAll(additions)
        Files.writeString(gitignorePath, (existing + newLines).joinToString("\n") + "\n")
    }
}
