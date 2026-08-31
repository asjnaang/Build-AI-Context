package com.asjnaang.buildaicontext.engine

import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path

private var cached: EnginePolicy? = null

fun loadPolicy(): EnginePolicy {
    cached?.let { return it }
    val text = readPolicyText()
    val raw = Json.parse(text).asMap()
    val policy = EnginePolicy(
        bundleMaxLines = raw.intVal("bundleMaxLines"),
        largeFileWarnLines = raw.intVal("largeFileWarnLines"),
        largeFileSkipLines = raw.intVal("largeFileSkipLines"),
        textEncoding = raw.strVal("textEncoding"),
        defaultOutputDir = raw.strVal("defaultOutputDir"),
        categoryExtensions = raw.strToStrList("categoryExtensions"),
        categoryAliases = raw.strToStr("categoryAliases"),
        categoryDescriptions = raw.strToStr("categoryDescriptions"),
        specialFilenames = raw.strList("specialFilenames"),
        defaultExcludedDirs = raw.strList("defaultExcludedDirs"),
        defaultExcludedPrefixes = raw.strList("defaultExcludedPrefixes"),
        extraExcludedPatterns = raw.strList("extraExcludedPatterns"),
        defaultSecretPatterns = raw.strList("defaultSecretPatterns"),
        redactionMark = raw.strVal("redactionMark"),
    )
    cached = policy
    return policy
}

fun loadPromptMd(): String {
    val stream = EnginePolicy::class.java.getResourceAsStream("/prompt.md")
    if (stream != null) {
        return stream.bufferedReader(StandardCharsets.UTF_8).use { it.readText() }
    }
    var dir = Path.of(System.getProperty("user.dir")).toAbsolutePath()
    while (true) {
        val candidate = dir.resolve("ide/engine-ts/prompt.md")
        if (Files.isRegularFile(candidate)) return Files.readString(candidate)
        dir = dir.parent ?: break
    }
    return ""
}

private fun readPolicyText(): String {
    val stream = EnginePolicy::class.java.getResourceAsStream("/policy.json")
    if (stream != null) {
        return stream.bufferedReader(StandardCharsets.UTF_8).use { it.readText() }
    }
    System.getProperty("baic.policy")?.let { path ->
        val p = Path.of(path)
        if (Files.isRegularFile(p)) return Files.readString(p)
    }
    var dir = Path.of(System.getProperty("user.dir")).toAbsolutePath()
    while (true) {
        val candidate = dir.resolve("ide/policy/policy.json")
        if (Files.isRegularFile(candidate)) return Files.readString(candidate)
        dir = dir.parent ?: break
    }
    error("policy.json not found on classpath or under ide/policy/")
}

@Suppress("UNCHECKED_CAST")
private fun Any?.asMap(): Map<String, Any?> = this as Map<String, Any?>
