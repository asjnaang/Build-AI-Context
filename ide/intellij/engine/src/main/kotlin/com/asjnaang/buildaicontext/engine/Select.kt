package com.asjnaang.buildaicontext.engine

import java.nio.file.Path

fun normalizeCategories(values: List<String>): List<String> {
    val policy = loadPolicy()
    val normalized = ArrayList<String>()
    for (value in values) {
        val key = value.trim().lowercase()
        if (key.isEmpty()) continue
        val mapped = policy.categoryAliases[key] ?: key
        if (mapped in policy.categoryDescriptions && mapped !in normalized) {
            normalized.add(mapped)
        }
    }
    return normalized
}

fun parseCsvInput(raw: String): List<String> {
    return raw.split(',').map { it.trim() }.filter { it.isNotEmpty() }
}

fun parseIntelligentInput(raw: String, files: List<SourceFile>, root: String): List<String> {
    if (raw.trim().isEmpty()) return emptyList()
    val allPathStrs = files.map { it.relPath }.toSet()
    val allNames = files.map { Path.of(it.relPath).fileName.toString() }.toSet()
    val found = ArrayList<String>()
    val parts = raw.split(Regex("[,;\\s]+")).map { it.trim() }.filter { it.isNotEmpty() }

    for (original in parts) {
        var part = original
        if (Path.of(part).isAbsolute) {
            try {
                part = posixRel(Path.of(root), Path.of(part).toAbsolutePath().normalize())
            } catch (_: Exception) {
                /* keep */
            }
        }
        if (part in allPathStrs) {
            if (part !in found) found.add(part)
            continue
        }
        if (part in allNames) {
            for (p in allPathStrs) {
                if (p.endsWith("/$part") || p == part) {
                    if (p !in found) found.add(p)
                }
            }
            continue
        }
        val exact = allPathStrs.filter { it == part || it.endsWith("/$part") }
        if (exact.isNotEmpty()) {
            for (m in exact) if (m !in found) found.add(m)
            continue
        }
        val folder = allPathStrs.filter { it.startsWith("$part/") || it.contains("/$part/") }
        if (folder.isNotEmpty()) {
            for (m in folder) if (m !in found) found.add(m)
            continue
        }
        val contains = allPathStrs.filter { it.contains(part) }
        if (contains.isNotEmpty()) {
            for (m in contains) if (m !in found) found.add(m)
            continue
        }
        fun stripped(s: String) = s.replace("/", "").replace("\\", "")
        val partial = allPathStrs.filter { stripped(it).startsWith(stripped(part)) }
        if (partial.isNotEmpty()) {
            for (m in partial) if (m !in found) found.add(m)
        }
    }
    return found
}

fun filterFilesByPaths(
    files: List<SourceFile>,
    root: String,
    rawPaths: List<String>,
): Triple<List<SourceFile>, List<String>, List<String>> {
    val normalized = normalizeSelectionPaths(rawPaths, root)
    if (normalized.isEmpty()) return Triple(files.toList(), emptyList(), emptyList())

    val matched = ArrayList<SourceFile>()
    val missing = ArrayList<String>()
    val rootPath = Path.of(root)

    for (i in rawPaths.indices) {
        val rawInput = rawPaths[i]
        val norm = normalized.getOrNull(i) ?: continue
        val looksLikeFileNameOnly = !Path.of(rawInput).isAbsolute && !rawInput.contains("/") && !rawInput.contains("\\")
        val absCandidate = try {
            val raw = Path.of(rawInput)
            if (raw.isAbsolute) raw.toAbsolutePath().normalize() else rootPath.resolve(rawInput).toAbsolutePath().normalize()
        } catch (_: Exception) {
            null
        }
        val exact = files.filter { item ->
            item.relPath == norm ||
                item.relPath.startsWith(norm.trimEnd('/') + "/") ||
                (absCandidate != null && Path.of(item.absPath).toAbsolutePath().normalize() == absCandidate)
        }
        if (exact.isNotEmpty()) {
            for (item in exact) if (item !in matched) matched.add(item)
            continue
        }
        if (looksLikeFileNameOnly) {
            val rawName = Path.of(rawInput).fileName.toString()
            val base = files.filter { Path.of(it.relPath).fileName.toString() == rawName }
            if (base.isNotEmpty()) {
                for (item in base) if (item !in matched) matched.add(item)
                continue
            }
        }
        missing.add(rawInput)
    }
    matched.sortWith { a, b -> a.relPath.compareTo(b.relPath) }
    return Triple(matched, normalized, missing)
}

fun filterFilesByKeywords(
    files: List<SourceFile>,
    keywords: List<String>,
): Pair<List<SourceFile>, List<String>> {
    val matched = ArrayList<SourceFile>()
    val matchedKeywords = ArrayList<String>()
    val lower = keywords.map { it.lowercase() }
    for (item in files) {
        val content = item.lines.joinToString("\n").lowercase()
        val found = lower.filter { kw -> content.contains(kw) }
        if (found.isNotEmpty()) {
            matched.add(item)
            for (kw in found) if (kw !in matchedKeywords) matchedKeywords.add(kw)
        }
    }
    matched.sortWith { a, b -> a.relPath.compareTo(b.relPath) }
    return matched to matchedKeywords.sortedWith { a, b -> a.compareTo(b) }
}

fun select(catalog: Catalog, filters: Filters): Selection {
    val policy = loadPolicy()
    var selected = catalog.files.toList()
    val hasCat = filters.categories.isNotEmpty()
    val hasPath = filters.paths.isNotEmpty()
    val hasName = filters.nameFilters.isNotEmpty()
    val hasKw = filters.keywords.isNotEmpty()

    var selectedCategories = emptyList<String>()
    if (hasCat) {
        selectedCategories = normalizeCategories(filters.categories)
        val invalid = filters.categories.filter { item ->
            val key = item.trim().lowercase()
            val mapped = policy.categoryAliases[key] ?: key
            mapped !in policy.categoryDescriptions
        }
        if (invalid.isNotEmpty()) {
            throw IllegalArgumentException("Unsupported categories requested: ${invalid.joinToString(", ")}")
        }
        selected = selected.filter { it.category in selectedCategories }
    }

    var selectedPaths = emptyList<String>()
    var missingPaths = emptyList<String>()
    if (hasPath) {
        val (matched, normalized, missing) = filterFilesByPaths(selected, catalog.workspace, filters.paths)
        selected = matched
        selectedPaths = normalized
        missingPaths = missing
    }

    if (hasName) {
        selected = selected.filter { f ->
            val fname = Path.of(f.relPath).fileName.toString().lowercase()
            filters.nameFilters.any { nf -> fname.contains(nf.lowercase()) }
        }
    }

    if (hasKw) {
        selected = filterFilesByKeywords(selected, filters.keywords).first
    }

    selected = selected.sortedWith { a, b -> a.relPath.compareTo(b.relPath) }
    val anyFilter = hasCat || hasPath || hasName || hasKw
    return Selection(
        files = selected,
        metadata = SelectionMetadata(
            selectionMode = if (anyFilter) "composed" else "non_interactive",
            selectedCategories = selectedCategories,
            selectedPaths = selectedPaths,
            nameFilters = when {
                hasName -> filters.nameFilters.toList()
                hasKw -> filters.keywords.toList()
                else -> emptyList()
            },
            missingPaths = missingPaths,
        ),
    )
}

fun applyMaxFileLines(selection: Selection, maxFileLines: Int): Pair<List<SourceFile>, List<SourceFile>> {
    if (maxFileLines <= 0) {
        return selection.files.toList() to emptyList()
    }
    val included = ArrayList<SourceFile>()
    val oversized = ArrayList<SourceFile>()
    for (file in selection.files) {
        if (file.lineCount >= maxFileLines) oversized.add(file) else included.add(file)
    }
    return included to oversized
}

private fun normalizeSelectionPaths(rawPaths: List<String>, root: String): List<String> {
    val normalized = ArrayList<String>()
    val rootPath = Path.of(root)
    for (raw in rawPaths) {
        var value = raw.trim()
        if (value.isEmpty()) continue
        val candidate = Path.of(value)
        if (candidate.isAbsolute) {
            value = try {
                posixRel(rootPath, candidate.toAbsolutePath().normalize())
            } catch (_: Exception) {
                candidate.toAbsolutePath().normalize().toString().replace('\\', '/')
            }
        } else {
            value = value.trimEnd('/')
        }
        if (value !in normalized) normalized.add(value)
    }
    return normalized
}
