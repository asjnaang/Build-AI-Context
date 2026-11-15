package com.asjnaang.buildaicontext.engine

class HostState(
    var catalog: Catalog? = null,
    var filters: Filters = Filters(),
    val checked: MutableSet<String> = linkedSetOf(),
    var maxFileLines: Int = 3000,
) {
    var searchQuery: String = ""
    var formatFilter: String = ""

    fun availableFormats(): List<String> = catalog?.files
        ?.map { fileFormat(it.relPath) }?.distinct()?.sorted() ?: emptyList()

    fun searchResults(): List<SourceFile> {
        val catalog = this.catalog ?: return emptyList()
        val query = searchQuery.trim().lowercase()
        return select(catalog, filters).files.filter {
            (query.isEmpty() || it.relPath.lowercase().contains(query) || it.category.lowercase().contains(query)) &&
                (formatFilter.isEmpty() || fileFormat(it.relPath) == formatFilter)
        }
    }

    fun selectAllResults(): Int {
        var added = 0
        for (file in searchResults()) if (checked.add(file.relPath)) added++
        return added
    }

    private fun fileFormat(path: String): String {
        val name = path.substringAfterLast('/')
        val dot = name.lastIndexOf('.')
        return if (dot <= 0) "(no extension)" else name.substring(dot).lowercase()
    }

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
        return applyMaxFileLines(selected.copy(files = searchResults()), maxFileLines)
    }

    fun exportSelection(): Selection {
        val catalog = this.catalog ?: return Selection(
            emptyList(),
            SelectionMetadata("non_interactive", emptyList(), emptyList(), emptyList(), emptyList()),
        )
        val selected = select(catalog, filters)
        return selected.copy(files = searchResults().filter { it.relPath in checked })
    }

    fun toggleCategory(category: String) {
        val catalog = this.catalog ?: return
        val all = catalog.files.map { it.category }.distinct()
        if (!filters.categoriesConstrained) {
            filters.categoriesConstrained = true
            filters.categories.clear()
            filters.categories.addAll(all.filter { it != category })
        } else {
            val i = filters.categories.indexOf(category)
            if (i >= 0) filters.categories.removeAt(i) else filters.categories.add(category)
        }
        applyScan(catalog)
    }

    fun categoryChecked(category: String): Boolean {
        if (!filters.categoriesConstrained) return true
        return category in filters.categories
    }

    fun exportMaxFileLines(): Int {
        if (maxFileLines <= 0) return 0
        val files = exportSelection().files
        if (files.any { it.lineCount >= maxFileLines }) return 0
        return maxFileLines
    }

    fun setPaths(raw: String) {
        filters.paths.clear()
        filters.paths.addAll(raw.split(Regex("[,;\\s]+")).map { it.trim() }.filter { it.isNotEmpty() })
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
        searchQuery = ""
        formatFilter = ""
        catalog?.let { applyScan(it) }
    }

    fun selectAllCategories() {
        filters.categories.clear()
        filters.categoriesConstrained = false
        catalog?.let { applyScan(it) }
    }
}
