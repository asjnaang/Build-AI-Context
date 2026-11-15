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

fun loadPromptMd(transport: String = "text", task: String? = null): String {
    val name = if (transport == "tar-gz") "baic_prompt_gzip.md" else "baic_prompt_text.md"
    val stream = EnginePolicy::class.java.getResourceAsStream("/$name")
    if (stream != null) {
        return applyTask(stream.bufferedReader(StandardCharsets.UTF_8).use { it.readText() }, task)
    }
    var dir = Path.of(System.getProperty("user.dir")).toAbsolutePath()
    while (true) {
        val candidate = dir.resolve("ide/engine-ts/$name")
        if (Files.isRegularFile(candidate)) return applyTask(Files.readString(candidate), task)
        dir = dir.parent ?: break
    }
    error("Bundled prompt is missing: $name")
}

private fun applyTask(prompt: String, task: String?): String =
    if (task == null) prompt else prompt.replace("[PASTE THE SPECIFIC FEATURE / BUGFIX / REFACTOR REQUEST HERE]", task)

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
