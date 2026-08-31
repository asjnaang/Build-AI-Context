package com.asjnaang.buildaicontext.engine

import java.nio.file.Path
import java.util.Locale

private val GRAPHABLE = setOf(
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".java", ".kt", ".kts", ".swift", ".dart",
)
private val SKIP_DUNDER = Regex("^__\\w+__$")
private val JS_INDEX = listOf("index.ts", "index.tsx", "index.js", "index.jsx", "index.mjs", "index.cjs")
private val JS_SUFFIXES = listOf(".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")

private data class Symbol(val kind: String, val name: String, val line: Int? = null)

private data class FileFacts(
    val path: String,
    val symbols: List<Symbol>,
    val imports: List<String>,
    val engine: String,
    val error: String? = null,
)

private fun unique(values: List<String>): List<String> {
    val seen = HashSet<String>()
    val out = ArrayList<String>()
    for (value in values) {
        if (value.isNotEmpty() && seen.add(value)) out.add(value)
    }
    return out
}

private fun dedupeSymbols(symbols: List<Symbol>): List<Symbol> {
    val seen = HashSet<String>()
    val out = ArrayList<Symbol>()
    for (s in symbols) {
        val key = "${s.kind}:${s.name}"
        if (seen.add(key)) out.add(s)
    }
    return out
}

private fun keepFuncName(name: String): Boolean {
    if (name == "__init__") return true
    return !SKIP_DUNDER.matches(name)
}

private fun lineAt(text: String, index: Int): Int {
    return text.substring(0, index).count { it == '\n' } + 1
}

private fun extractPython(path: String, text: String): FileFacts {
    val symbols = ArrayList<Symbol>()
    val imports = ArrayList<String>()
    val lines = text.split('\n')
    var i = 0
    while (i < lines.size) {
        val raw = lines[i]
        val indent = raw.length - raw.trimStart().length
        if (indent != 0 || raw.trim().isEmpty() || raw.trimStart().startsWith("#")) {
            i += 1
            continue
        }
        val classMatch = Regex("^class\\s+(\\w+)").find(raw)
        val asyncFn = Regex("^async\\s+def\\s+(\\w+)").find(raw)
        val fnMatch = Regex("^def\\s+(\\w+)").find(raw)
        val importMatch = Regex("^import\\s+(.+)$").find(raw)
        val fromMatch = Regex("^from\\s+(\\S+)\\s+import\\b").find(raw)
        if (classMatch != null) {
            val className = classMatch.groupValues[1]
            symbols.add(Symbol("class", className, i + 1))
            i += 1
            while (i < lines.size) {
                val child = lines[i]
                if (child.trim().isEmpty()) {
                    i += 1
                    continue
                }
                val childIndent = child.length - child.trimStart().length
                if (childIndent <= indent) break
                val method = Regex("^(?:async\\s+)?def\\s+(\\w+)").find(child.trim())
                if (method != null && childIndent > indent && keepFuncName(method.groupValues[1])) {
                    symbols.add(Symbol("method", "$className.${method.groupValues[1]}", i + 1))
                }
                i += 1
            }
            continue
        }
        if (asyncFn != null || fnMatch != null) {
            val name = (asyncFn ?: fnMatch)!!.groupValues[1]
            if (keepFuncName(name)) symbols.add(Symbol("fn", name, i + 1))
            i += 1
            continue
        }
        if (importMatch != null) {
            for (part in importMatch.groupValues[1].split(',')) {
                val name = part.trim().split(Regex("\\s+as\\s+"))[0].trim()
                if (name.isNotEmpty() && name != "__future__") imports.add(name)
            }
            i += 1
            continue
        }
        if (fromMatch != null) {
            val spec = fromMatch.groupValues[1]
            if (spec != "__future__") imports.add(spec)
            i += 1
            continue
        }
        i += 1
    }
    return FileFacts(path, symbols, unique(imports), "ast")
}

private fun heuristicJsImports(text: String): List<String> {
    val found = ArrayList<String>()
    val fromRe = Regex("(?:import|export)\\s+(?:type\\s+)?(?:[^'\"\\n]+?\\s+from\\s+)?['\"]([^'\"]+)['\"]")
    val reqRe = Regex("require\\s*\\(\\s*['\"]([^'\"]+)['\"]\\s*\\)")
    found.addAll(fromRe.findAll(text).map { it.groupValues[1] })
    found.addAll(reqRe.findAll(text).map { it.groupValues[1] })
    return found
}

private fun heuristicJsSymbols(text: String): List<Symbol> {
    val symbols = ArrayList<Symbol>()
    fun add(re: Regex, kind: String) {
        for (m in re.findAll(text)) {
            symbols.add(Symbol(kind, m.groupValues[1], lineAt(text, m.range.first)))
        }
    }
    add(Regex("^\\s*(?:export\\s+)?(?:default\\s+)?(?:async\\s+)?function\\s+([A-Za-z_$][\\w$]*)", RegexOption.MULTILINE), "fn")
    add(Regex("^\\s*(?:export\\s+)?(?:default\\s+)?class\\s+([A-Za-z_$][\\w$]*)", RegexOption.MULTILINE), "class")
    add(
        Regex(
            "^\\s*(?:export\\s+)?(?:const|let|var)\\s+([A-Za-z_$][\\w$]*)\\s*=\\s*(?:async\\s*)?(?:\\([^)]*\\)|[A-Za-z_$][\\w$]*)\\s*=>",
            RegexOption.MULTILINE,
        ),
        "fn",
    )
    add(Regex("^\\s*(?:export\\s+)?interface\\s+([A-Za-z_$][\\w$]*)", RegexOption.MULTILINE), "interface")
    add(Regex("^\\s*(?:export\\s+)?type\\s+([A-Za-z_$][\\w$]*)\\s*=", RegexOption.MULTILINE), "type")
    return symbols
}

private fun heuristicImportLines(text: String, pattern: Regex): List<String> {
    return pattern.findAll(text).map { it.groupValues[1].trimEnd(';') }.toList()
}

private fun heuristicKotlin(text: String): List<Symbol> {
    val symbols = ArrayList<Symbol>()
    var currentClass: String? = null
    text.split('\n').forEachIndexed { idx, raw ->
        val line = raw.trim()
        val classMatch = Regex(
            "(?:(?:public|private|internal|protected|open|data|sealed|abstract)\\s+)*(class|object|interface|enum\\s+class)\\s+([A-Za-z_][\\w]*)",
        ).find(line)
        if (classMatch != null) {
            val kind = if (classMatch.groupValues[1].contains("enum")) "enum" else classMatch.groupValues[1]
            currentClass = classMatch.groupValues[2]
            symbols.add(Symbol(kind, currentClass!!, idx + 1))
            return@forEachIndexed
        }
        val fnMatch = Regex(
            "(?:(?:public|private|internal|protected|override|suspend)\\s+)*fun\\s+([A-Za-z_][\\w]*)\\s*\\(",
        ).find(line)
        if (fnMatch != null) {
            val name = fnMatch.groupValues[1]
            val cls = currentClass
            symbols.add(
                if (cls != null) Symbol("method", "$cls.$name", idx + 1) else Symbol("fn", name, idx + 1),
            )
        }
    }
    return symbols
}

private fun heuristicSwift(text: String): List<Symbol> {
    val symbols = ArrayList<Symbol>()
    var current: Pair<String, String>? = null
    text.split('\n').forEachIndexed { idx, raw ->
        val line = raw.trim()
        val typeMatch = Regex(
            "(?:(?:public|private|internal|open|final|fileprivate)\\s+)*(class|struct|enum|protocol|actor)\\s+([A-Za-z_][\\w]*)",
        ).find(line)
        if (typeMatch != null) {
            current = typeMatch.groupValues[1] to typeMatch.groupValues[2]
            symbols.add(Symbol(current!!.first, current!!.second, idx + 1))
            return@forEachIndexed
        }
        val fnMatch = Regex(
            "(?:(?:public|private|internal|open|override|static|mutating)\\s+)*func\\s+([A-Za-z_][\\w]*)\\s*\\(",
        ).find(line)
        if (fnMatch != null) {
            val name = fnMatch.groupValues[1]
            val cur = current
            if (cur != null && cur.first != "protocol") {
                symbols.add(Symbol("method", "${cur.second}.$name", idx + 1))
            } else {
                symbols.add(Symbol("fn", name, idx + 1))
            }
        }
    }
    return symbols
}

private fun heuristicJava(text: String): List<Symbol> {
    val symbols = ArrayList<Symbol>()
    var current: String? = null
    text.split('\n').forEachIndexed { idx, raw ->
        val line = raw.trim()
        val typeMatch = Regex(
            "(?:(?:public|private|protected|abstract|final|static)\\s+)*(class|interface|enum)\\s+([A-Za-z_][\\w]*)",
        ).find(line)
        if (typeMatch != null) {
            current = typeMatch.groupValues[2]
            symbols.add(Symbol(typeMatch.groupValues[1], current!!, idx + 1))
            return@forEachIndexed
        }
        val methodMatch = Regex(
            "(?:(?:public|private|protected|static|final|synchronized|abstract)\\s+)+(?:[\\w.<>,\\[\\]?]+\\s+)+([A-Za-z_][\\w]*)\\s*\\(",
        ).find(line)
        if (methodMatch != null && current != null && methodMatch.groupValues[1] !in setOf("if", "for", "while", "switch", current)) {
            symbols.add(Symbol("method", "$current.${methodMatch.groupValues[1]}", idx + 1))
        }
    }
    return symbols
}

private fun heuristicDart(text: String): List<Symbol> {
    val symbols = ArrayList<Symbol>()
    val classRe = Regex("^\\s*(?:class|mixin)\\s+([A-Za-z_][\\w]*)", RegexOption.MULTILINE)
    for (m in classRe.findAll(text)) {
        symbols.add(Symbol("class", m.groupValues[1], lineAt(text, m.range.first)))
    }
    val fnRe = Regex("^\\s*(?:[A-Za-z_][\\w<>,\\s?]*\\s+)?([A-Za-z_][\\w]*)\\s*\\([^;]*\\)\\s*(?:async\\s*)?\\{", RegexOption.MULTILINE)
    for (m in fnRe.findAll(text)) {
        val name = m.groupValues[1]
        if (name in setOf("if", "for", "while", "switch", "catch")) continue
        if (symbols.any { it.name == name && it.kind == "class" }) continue
        symbols.add(Symbol("fn", name, lineAt(text, m.range.first)))
    }
    return symbols
}

private fun extractHeuristic(path: String, suffix: String, text: String): FileFacts {
    var symbols: List<Symbol> = emptyList()
    var imports: List<String> = emptyList()
    if (suffix in listOf(".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx")) {
        imports = heuristicJsImports(text)
        symbols = heuristicJsSymbols(text)
    } else if (suffix in listOf(".kt", ".kts")) {
        imports = heuristicImportLines(text, Regex("^import\\s+([^\\s;]+)", RegexOption.MULTILINE))
        symbols = heuristicKotlin(text)
    } else if (suffix == ".swift") {
        imports = heuristicImportLines(text, Regex("^import\\s+([A-Za-z_][\\w.]*)", RegexOption.MULTILINE))
        symbols = heuristicSwift(text)
    } else if (suffix == ".java") {
        imports = heuristicImportLines(text, Regex("^import\\s+(?:static\\s+)?([^\\s;]+)", RegexOption.MULTILINE))
        symbols = heuristicJava(text)
    } else if (suffix == ".dart") {
        imports = heuristicImportLines(text, Regex("^import\\s+['\"]([^'\"]+)['\"]", RegexOption.MULTILINE))
        symbols = heuristicDart(text)
    }
    return FileFacts(path, dedupeSymbols(symbols), unique(imports), "heuristic")
}

private fun extractFile(source: SourceFile): FileFacts {
    val suffix = suffixOf(Path.of(source.relPath).fileName.toString())
    val path = source.relPath
    val text = source.lines.joinToString("\n")
    return try {
        if (suffix == ".py") extractPython(path, text) else extractHeuristic(path, suffix, text)
    } catch (err: Exception) {
        FileFacts(path, emptyList(), emptyList(), "error", err.toString())
    }
}

private fun normalizeRel(path: String): String {
    val parts = ArrayList<String>()
    for (part in path.replace('\\', '/').split('/')) {
        if (part.isEmpty() || part == ".") continue
        if (part == "..") {
            if (parts.isNotEmpty()) parts.removeAt(parts.lastIndex)
            continue
        }
        parts.add(part)
    }
    return parts.joinToString("/")
}

private fun suffixesFor(fromPath: String): List<String> {
    val ext = suffixOf(Path.of(fromPath).fileName.toString())
    val families = mapOf(
        ".py" to listOf(".py"),
        ".js" to JS_SUFFIXES,
        ".jsx" to JS_SUFFIXES,
        ".mjs" to JS_SUFFIXES,
        ".cjs" to JS_SUFFIXES,
        ".ts" to JS_SUFFIXES,
        ".tsx" to JS_SUFFIXES,
        ".kt" to listOf(".kt", ".kts", ".java"),
        ".kts" to listOf(".kt", ".kts", ".java"),
        ".java" to listOf(".java", ".kt", ".kts"),
        ".swift" to listOf(".swift"),
        ".dart" to listOf(".dart"),
    )
    val preferred = families[ext] ?: emptyList()
    val fallback = listOf(".py") + JS_SUFFIXES + listOf(".kt", ".kts", ".swift", ".java", ".dart")
    val seen = HashSet<String>()
    val ordered = ArrayList<String>()
    for (suffix in preferred + fallback) {
        if (seen.add(suffix)) ordered.add(suffix)
    }
    return ordered
}

private fun matchExisting(candidate: String, pathSet: Set<String>, fromPath: String = ""): String? {
    val normalized = normalizeRel(candidate)
    if (normalized in pathSet) return normalized
    for (suffix in suffixesFor(fromPath)) {
        val withSuffix = normalizeRel(normalized + suffix)
        if (withSuffix in pathSet) return withSuffix
    }
    if (suffixOf(Path.of(fromPath).fileName.toString()) == ".py" || fromPath.isEmpty()) {
        val initPy = normalizeRel("$normalized/__init__.py")
        if (initPy in pathSet) return initPy
    }
    if (suffixOf(Path.of(fromPath).fileName.toString()) in JS_SUFFIXES || fromPath.isEmpty()) {
        for (index in JS_INDEX) {
            val indexed = normalizeRel("$normalized/$index")
            if (indexed in pathSet) return indexed
        }
    }
    return null
}

private fun dirnamePosix(fromPath: String): String {
    val i = fromPath.lastIndexOf('/')
    return if (i == -1) "" else fromPath.substring(0, i)
}

private fun resolveRelative(fromPath: String, spec: String, pathSet: Set<String>): String? {
    val origin = dirnamePosix(fromPath)
    if (spec.startsWith("./") || spec.startsWith("../")) {
        return matchExisting("$origin/$spec", pathSet, fromPath)
    }
    val stripped = spec.replace(Regex("^\\.+"), "")
    val dots = spec.length - stripped.length
    var dest = origin
    repeat(dots - 1) { dest = dirnamePosix(dest) }
    if (stripped.isNotEmpty()) {
        dest = if (dest.isNotEmpty()) "$dest/${stripped.replace('.', '/')}" else stripped.replace('.', '/')
    }
    return matchExisting(dest, pathSet, fromPath)
}

private fun resolvePathish(fromPath: String, spec: String, pathSet: Set<String>): String? {
    if (spec.startsWith("package:")) return null
    val origin = dirnamePosix(fromPath)
    val candidate = if (spec.startsWith("/")) spec.replace(Regex("^/+"), "") else "$origin/$spec"
    return matchExisting(candidate, pathSet, fromPath)
}

private fun resolveDotted(fromPath: String, spec: String, pathSet: Set<String>): String? {
    val cleaned = spec.replace(Regex("\\.\\*\$"), "").replace(Regex("\\.\$"), "")
    return matchExisting(cleaned.replace('.', '/'), pathSet, fromPath)
}

private fun resolveBasename(spec: String, pathSet: Set<String>): String? {
    val name = spec.substringAfterLast('.')
    val matches = pathSet.filter { p ->
        val base = Path.of(p).fileName.toString()
        val ext = suffixOf(base)
        val stem = if (ext.isEmpty()) base else base.removeSuffix(ext)
        stem == name
    }
    return if (matches.size == 1) matches[0] else null
}

fun resolveImport(fromPath: String, spec: String, pathSet: Set<String>): String? {
    if (spec.isEmpty() || spec == "__future__") return null
    if (spec.startsWith(".")) return resolveRelative(fromPath, spec, pathSet)
    if (spec.contains("/") || JS_SUFFIXES.any { spec.endsWith(it) } || Regex("\\.(dart|kt|swift|java)\$").containsMatchIn(spec)) {
        return resolvePathish(fromPath, spec, pathSet)
    }
    return resolveDotted(fromPath, spec, pathSet) ?: resolveBasename(spec, pathSet)
}

private fun pagerank(
    nodes: List<String>,
    edges: List<Pair<String, String>>,
    damping: Double = 0.85,
    rounds: Int = 20,
): Map<String, Double> {
    val uniqueNodes = nodes.distinct()
    if (uniqueNodes.isEmpty()) return emptyMap()
    val n = uniqueNodes.size
    val nodeSet = uniqueNodes.toSet()
    val incoming = LinkedHashMap<String, ArrayList<String>>()
    val outdeg = LinkedHashMap<String, Int>()
    for (node in uniqueNodes) {
        incoming[node] = ArrayList()
        outdeg[node] = 0
    }
    for ((src, dst) in edges) {
        if (src in nodeSet && dst in nodeSet && src != dst) {
            incoming[dst]!!.add(src)
            outdeg[src] = (outdeg[src] ?: 0) + 1
        }
    }
    var rank = uniqueNodes.associateWith { 1.0 / n }.toMutableMap()
    repeat(rounds) {
        val dangling = uniqueNodes.sumOf { node -> if (outdeg[node] == 0) rank[node]!! else 0.0 }
        val nxt = LinkedHashMap<String, Double>()
        for (node in uniqueNodes) {
            val inbound = incoming[node]!!.sumOf { src -> rank[src]!! / outdeg[src]!! }
            nxt[node] = (1.0 - damping) / n + damping * (inbound + dangling / n)
        }
        rank = nxt
    }
    return rank
}

private fun languageLabel(source: SourceFile): String {
    val suffix = suffixOf(Path.of(source.relPath).fileName.toString())
    val mapping = mapOf(
        ".py" to "python",
        ".ts" to "typescript",
        ".tsx" to "typescript",
        ".js" to "javascript",
        ".jsx" to "javascript",
        ".mjs" to "javascript",
        ".cjs" to "javascript",
        ".kt" to "kotlin",
        ".kts" to "kotlin",
        ".java" to "java",
        ".swift" to "swift",
        ".dart" to "dart",
    )
    return mapping[suffix] ?: suffix.removePrefix(".")
}

private fun formatEngines(engines: Set<String>): String {
    val ordered = listOf("ast", "tree-sitter", "heuristic").filter { it in engines }
    return if (ordered.isNotEmpty()) ordered.joinToString(", ") else "none"
}

private fun formatLanguages(counts: Map<String, Int>): String {
    val keys = counts.keys.sortedWith { a, b -> a.compareTo(b) }
    if (keys.isEmpty()) return "-"
    return keys.joinToString(", ") { name -> "$name=${counts[name]}" }
}

private fun formatSymbolLine(symbol: Symbol): String {
    return if (symbol.line != null) "${symbol.kind}: ${symbol.name} @${symbol.line},"
    else "${symbol.kind}: ${symbol.name},"
}

fun generateGraph(files: List<SourceFile>, root: String, outputFormat: String = "txt"): String {
    val fmt = (outputFormat.ifBlank { "txt" }).trim().lowercase()
    if (fmt != "txt" && fmt != "json") throw IllegalArgumentException("output_format must be 'txt' or 'json'")
    val graphable = files.filter { suffixOf(Path.of(it.relPath).fileName.toString()) in GRAPHABLE }
    val skipped = files.size - graphable.size
    val facts = ArrayList<FileFacts>()
    val engines = HashSet<String>()
    val langCounts = LinkedHashMap<String, Int>()
    var parsed = 0
    for (source in graphable) {
        val item = extractFile(source)
        facts.add(item)
        val label = languageLabel(source)
        langCounts[label] = (langCounts[label] ?: 0) + 1
        if (item.error != null) continue
        parsed += 1
        engines.add(item.engine)
    }
    val pathSet = files.map { it.relPath }.toSet()
    val importRows = ArrayList<Triple<String, String, Boolean>>()
    for (item in facts.sortedWith { a, b -> a.path.compareTo(b.path) }) {
        for (raw in item.imports) {
            val resolved = resolveImport(item.path, raw, pathSet)
            importRows.add(Triple(item.path, resolved ?: raw, resolved != null))
        }
    }
    val ranks = pagerank(
        facts.map { it.path },
        importRows.filter { it.third }.map { it.first to it.second },
    )
    val catalogItems = facts.filter { it.symbols.isNotEmpty() }.sortedWith { a, b ->
        val rankCmp = (ranks[b.path] ?: 0.0).compareTo(ranks[a.path] ?: 0.0)
        if (rankCmp != 0) rankCmp else a.path.compareTo(b.path)
    }

    val rootName = Path.of(root).fileName.toString()
    if (fmt == "json") {
        val payload = linkedMapOf<String, Any?>(
            "root" to rootName,
            "file_count" to files.size,
            "parsed" to parsed,
            "skipped" to skipped,
            "engine" to formatEngines(engines),
            "languages" to langCounts.keys.sortedWith { a, b -> a.compareTo(b) }.associateWith { langCounts[it] },
            "catalog" to catalogItems.map { item ->
                linkedMapOf(
                    "path" to item.path,
                    "rank" to Math.round((ranks[item.path] ?: 0.0) * 1e6) / 1e6,
                    "symbols" to item.symbols.map { symbol ->
                        val row = linkedMapOf<String, Any?>("kind" to symbol.kind, "name" to symbol.name)
                        if (symbol.line != null) row["line"] = symbol.line
                        row
                    },
                )
            },
            "imports" to importRows.map { (src, dest) -> linkedMapOf("from" to src, "to" to dest) },
        )
        return Json.stringify(payload) + "\n"
    }

    val lines = ArrayList<String>()
    lines.add("root: $rootName")
    lines.add("file_count: ${files.size}")
    lines.add("parsed: $parsed")
    lines.add("skipped: $skipped")
    lines.add("engine: ${formatEngines(engines)}")
    lines.add("languages: ${formatLanguages(langCounts)}")
    lines.add("")
    lines.add("catalog:")
    for (item in catalogItems) {
        lines.add("${item.path}:")
        lines.add("  rank: ${String.format(Locale.US, "%.4f", ranks[item.path] ?: 0.0)},")
        for (symbol in item.symbols) lines.add("  ${formatSymbolLine(symbol)}")
    }
    lines.add("")
    lines.add("imports:")
    for ((src, dest) in importRows.map { it.first to it.second }) lines.add("$src --> $dest,")
    return lines.joinToString("\n")
}
