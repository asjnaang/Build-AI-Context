package com.asjnaang.buildaicontext.engine

import java.nio.ByteBuffer
import java.nio.charset.CharacterCodingException
import java.nio.charset.Charset
import java.nio.charset.CodingErrorAction
import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest

fun detectCategory(filePath: String): String? {
    val policy = loadPolicy()
    val name = Path.of(filePath).fileName.toString()
    val suffix = suffixOf(name)
    if (name in policy.specialFilenames) {
        if (name == "Podfile" || name == ".swiftlint.yml") return "ios_apple"
        if (name in setOf(
                "AndroidManifest.xml",
                "gradle.properties",
                "settings.gradle",
                "settings.gradle.kts",
                "build.gradle",
                "build.gradle.kts",
            )
        ) {
            return "java_kotlin"
        }
        return "config_docs"
    }
    for ((category, extensions) in policy.categoryExtensions) {
        if (suffix in extensions) return category
    }
    return null
}

fun splitLines(text: String): List<String> {
    if (text.isEmpty()) return emptyList()
    val lines = ArrayList<String>()
    val sb = StringBuilder()
    var i = 0
    while (i < text.length) {
        val c = text[i]
        val isCrLf = c == '\r' && i + 1 < text.length && text[i + 1] == '\n'
        val isBreak = isCrLf || c == '\n' || c == '\r' || c == '\u000B' || c == '\u000C' ||
            c == '\u001C' || c == '\u001D' || c == '\u001E' || c == '\u0085' ||
            c == '\u2028' || c == '\u2029'
        if (isBreak) {
            lines.add(sb.toString())
            sb.setLength(0)
            i += if (isCrLf) 2 else 1
        } else {
            sb.append(c)
            i++
        }
    }
    if (sb.isNotEmpty()) lines.add(sb.toString())
    return lines
}

fun sha256OfLines(lines: List<String>): String {
    val digest = MessageDigest.getInstance("SHA-256")
    digest.update(lines.joinToString("\n").toByteArray(StandardCharsets.UTF_8))
    return digest.digest().joinToString("") { b -> "%02x".format(b) }
}

fun scan(workspace: String, options: ScanOptions = ScanOptions()): Catalog {
    val policy = loadPolicy()
    val root = Path.of(workspace).toAbsolutePath().normalize()
    val gitignore = loadGitignore(root)
    val files = ArrayList<SourceFile>()
    val skipped = LinkedHashMap<String, Int>()
    fun bump(reason: String) {
        skipped[reason] = (skipped[reason] ?: 0) + 1
    }

    for (abs in walkFiles(root)) {
        val rel = posixRel(root, abs)
        if (shouldSkipByDir(rel, policy.defaultExcludedDirs)) {
            bump("default_excluded_dir")
            continue
        }
        if (shouldSkipByPrefix(rel, policy.defaultExcludedPrefixes)) {
            bump("default_excluded_prefix")
            continue
        }
        if (gitignore.ignores(rel)) {
            bump(".gitignore")
            continue
        }
        if (pathMatchesAnyPattern(rel, policy.extraExcludedPatterns)) {
            bump("extra_excluded_pattern")
            continue
        }
        if (!options.includeSecretFiles && pathMatchesAnyPattern(rel, policy.defaultSecretPatterns)) {
            bump("secret_like_file")
            continue
        }
        val category = detectCategory(abs.toString())
        if (category == null) {
            bump("unsupported_type")
            continue
        }
        if (isProbablyBinary(abs)) {
            bump("binary")
            continue
        }
        val lines = try {
            readTextLines(abs)
        } catch (_: Exception) {
            bump("read_error")
            continue
        }
        val sizeBytes = try {
            Files.size(abs)
        } catch (_: Exception) {
            bump("read_error")
            continue
        }
        files.add(
            SourceFile(
                absPath = abs.toAbsolutePath().normalize().toString(),
                relPath = rel,
                category = category,
                lineCount = lines.size,
                sizeBytes = sizeBytes,
                sha256 = sha256OfLines(lines),
                lines = lines,
            ),
        )
    }
    files.sortWith { a, b -> a.relPath.compareTo(b.relPath) }
    val orderedSkipped = skipped.toSortedMap()
    return Catalog(workspace = root.toString(), files = files, skipped = orderedSkipped)
}

internal fun posixRel(root: Path, abs: Path): String {
    return root.relativize(abs).toString().replace('\\', '/')
}

internal fun suffixOf(name: String): String {
    val i = name.lastIndexOf('.')
    if (i <= 0) return ""
    return name.substring(i).lowercase()
}

private fun shouldSkipByDir(relPath: String, dirs: List<String>): Boolean {
    return relPath.split('/').any { it in dirs }
}

private fun shouldSkipByPrefix(relPath: String, prefixes: List<String>): Boolean {
    return prefixes.any { relPath.startsWith(it) }
}

private fun isProbablyBinary(abs: Path): Boolean {
    return try {
        Files.newInputStream(abs).use { input ->
            val buf = ByteArray(4096)
            val n = input.read(buf)
            if (n <= 0) false else buf.copyOf(n).any { it == 0.toByte() }
        }
    } catch (_: Exception) {
        true
    }
}

private fun readTextLines(abs: Path): List<String> {
    val bytes = Files.readAllBytes(abs)
    val tries = listOf(StandardCharsets.UTF_8, Charset.forName("ISO-8859-1"))
    for (cs in tries) {
        try {
            val decoder = cs.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
            val text = decoder.decode(ByteBuffer.wrap(bytes)).toString()
            return splitLines(text)
        } catch (_: CharacterCodingException) {
            continue
        }
    }
    return splitLines(String(bytes, StandardCharsets.UTF_8))
}

private fun walkFiles(root: Path): List<Path> {
    val out = ArrayList<Path>()
    Files.walk(root).use { stream ->
        stream.filter { Files.isRegularFile(it) }.forEach { out.add(it) }
    }
    return out
}

private fun loadGitignore(root: Path): GitIgnore {
    val path = root.resolve(".gitignore")
    if (!Files.isRegularFile(path)) return GitIgnore("")
    return try {
        GitIgnore(Files.readString(path))
    } catch (_: Exception) {
        GitIgnore("")
    }
}
