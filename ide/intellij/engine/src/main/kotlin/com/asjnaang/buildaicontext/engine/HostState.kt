package com.asjnaang.buildaicontext.engine

class HostState(
    var catalog: Catalog? = null,
    var filters: Filters = Filters(),
    val checked: MutableSet<String> = linkedSetOf(),
    var maxFileLines: Int = 3000,
) {
    fun applyScan(catalog: Catalog) {
        this.catalog = catalog
        val selected = select(catalog, filters)
        val (included, _) = applyMaxFileLines(selected, maxFileLines)
        checked.clear()
        checked.addAll(included.map { it.relPath })
    }

    fun visibleFiles(): Pair<List<SourceFile>, List<SourceFile>> {
        val catalog = this.catalog ?: return emptyList<SourceFile>() to emptyList()
        val selected = select(catalog, filters)
        return applyMaxFileLines(selected, maxFileLines)
    }

    fun exportSelection(): Selection {
        val catalog = this.catalog ?: return Selection(
            emptyList(),
            SelectionMetadata("non_interactive", emptyList(), emptyList(), emptyList(), emptyList()),
        )
        val selected = select(catalog, filters)
        return selected.copy(files = selected.files.filter { it.relPath in checked })
    }

    fun toggleCategory(category: String) {
        val i = filters.categories.indexOf(category)
        if (i >= 0) filters.categories.removeAt(i) else filters.categories.add(category)
        catalog?.let { applyScan(it) }
    }

    fun addPath(relPath: String) {
        if (relPath !in filters.paths) filters.paths.add(relPath)
        catalog?.let { applyScan(it) }
    }

    fun setKeywords(raw: String) {
        filters.keywords.clear()
        filters.keywords.addAll(raw.split(Regex("[,;\\s]+")).map { it.trim() }.filter { it.isNotEmpty() })
        catalog?.let { applyScan(it) }
    }

    fun setNameFilters(raw: String) {
        filters.nameFilters.clear()
        filters.nameFilters.addAll(raw.split(Regex("[,;\\s]+")).map { it.trim() }.filter { it.isNotEmpty() })
        catalog?.let { applyScan(it) }
    }

    fun clearFilters() {
        filters = Filters()
        catalog?.let { applyScan(it) }
    }
}
