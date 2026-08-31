package com.asjnaang.buildaicontext.engine

internal fun pathMatchesAnyPattern(relPath: String, patterns: List<String>): Boolean {
    val name = relPath.substringAfterLast('/')
    return patterns.any { pattern -> fnmatch(relPath, pattern) || fnmatch(name, pattern) }
}

internal fun fnmatch(name: String, pattern: String): Boolean {
    return globToRegex(pattern, starMatchesSlash = true).matches(name)
}

internal fun globToRegex(pattern: String, starMatchesSlash: Boolean): Regex {
    val sb = StringBuilder("^")
    var i = 0
    while (i < pattern.length) {
        when (val c = pattern[i]) {
            '*' -> sb.append(if (starMatchesSlash) ".*" else "[^/]*")
            '?' -> sb.append(if (starMatchesSlash) "." else "[^/]")
            '[' -> {
                val end = pattern.indexOf(']', i + 1)
                if (end < 0) {
                    sb.append("\\[")
                } else {
                    sb.append(pattern.substring(i, end + 1))
                    i = end
                }
            }
            else -> {
                if (c in ".$^|{}()+\\") sb.append('\\')
                sb.append(c)
            }
        }
        i++
    }
    sb.append('$')
    return sb.toString().toRegex()
}

internal class GitIgnore(text: String) {
    private data class Rule(val negated: Boolean, val regex: Regex)

    private val rules: List<Rule> = text.splitToSequence('\n', '\r')
        .map { it.trimEnd() }
        .mapNotNull { parseRule(it) }
        .toList()

    fun ignores(relPath: String): Boolean {
        val path = relPath.replace('\\', '/').removePrefix("./")
        var ignored = false
        for (rule in rules) {
            if (rule.regex.matches(path)) ignored = !rule.negated
        }
        return ignored
    }

    private fun parseRule(raw: String): Rule? {
        var line = raw.trim()
        if (line.isEmpty() || line.startsWith("#")) return null
        var negated = false
        if (line.startsWith("!")) {
            negated = true
            line = line.substring(1)
        }
        if (line.startsWith("\\#") || line.startsWith("\\!")) {
            line = line.substring(1)
        }
        val dirOnly = line.endsWith("/")
        if (dirOnly) line = line.dropLast(1)
        val anchored = line.startsWith("/")
        if (anchored) line = line.drop(1)
        val hasSlash = line.contains("/")
        val body = gitGlobBody(line)
        val prefix = if (anchored || hasSlash) "^" else "^(?:.*/)?"
        val suffix = if (dirOnly) "(?:/.*)?$" else "$"
        return Rule(negated, (prefix + body + suffix).toRegex())
    }

    private fun gitGlobBody(pattern: String): String {
        val sb = StringBuilder()
        var i = 0
        while (i < pattern.length) {
            when (val c = pattern[i]) {
                '*' -> {
                    if (i + 1 < pattern.length && pattern[i + 1] == '*') {
                        sb.append(".*")
                        i += 2
                        if (i < pattern.length && pattern[i] == '/') {
                            sb.append("(?:/)?")
                            i++
                        }
                        continue
                    }
                    sb.append("[^/]*")
                }
                '?' -> sb.append("[^/]")
                else -> {
                    if (c in ".$^|{}()+\\[]") sb.append('\\')
                    sb.append(c)
                }
            }
            i++
        }
        return sb.toString()
    }
}
