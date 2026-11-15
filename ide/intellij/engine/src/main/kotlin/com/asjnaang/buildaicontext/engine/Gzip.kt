package com.asjnaang.buildaicontext.engine

import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest
import java.util.zip.GZIPInputStream
import java.util.zip.GZIPOutputStream
import java.util.Base64

class RestoreError(message: String) : RuntimeException(message)

data class GzipSource(
    val relPath: String,
    val category: String,
    val sizeBytes: Long,
    val sha256: String,
    val data: ByteArray,
    val mode: Int,
    val encoding: String,
)

data class GzipWriteResult(
    val payloadPaths: List<String>,
    val payloadRecords: List<Map<String, Any?>>,
    val archiveEntries: List<Map<String, Any?>>,
    val logicalPaths: List<String>,
)

private const val BLOCK = 512

private fun sha256(data: ByteArray): String {
    val digest = MessageDigest.getInstance("SHA-256").digest(data)
    return digest.joinToString("") { b -> "%02x".format(b) }
}

private fun octal(value: Int, width: Int): ByteArray {
    val body = value.toString(8).padStart(width - 1, '0')
    return (body + "\u0000").toByteArray(Charsets.US_ASCII)
}

private fun splitName(name: String): Pair<String, String> {
    if (name.length <= 100) return name to ""
    for (i in name.length - 1 downTo 0) {
        if (name[i] != '/') continue
        val prefix = name.substring(0, i)
        val base = name.substring(i + 1)
        if (base.length in 1..100 && prefix.length <= 155) return base to prefix
    }
    throw IllegalArgumentException("path too long for ustar: $name")
}

private fun tarHeader(path: String, size: Int, mode: Int): ByteArray {
    val header = ByteArray(BLOCK)
    val (name, prefix) = splitName(path)
    name.toByteArray(Charsets.UTF_8).copyInto(header, 0, 0, minOf(name.length, 100))
    octal(mode and 511, 8).copyInto(header, 100)
    octal(0, 8).copyInto(header, 108)
    octal(0, 8).copyInto(header, 116)
    octal(size, 12).copyInto(header, 124)
    octal(0, 12).copyInto(header, 136)
    "        ".toByteArray(Charsets.US_ASCII).copyInto(header, 148)
    header[156] = '0'.code.toByte()
    "ustar\u0000".toByteArray(Charsets.US_ASCII).copyInto(header, 257)
    "00".toByteArray(Charsets.US_ASCII).copyInto(header, 263)
    if (prefix.isNotEmpty()) prefix.toByteArray(Charsets.UTF_8).copyInto(header, 345, 0, minOf(prefix.length, 155))
    var sum = 0
    for (b in header) sum += b.toInt() and 0xFF
    (sum.toString(8).padStart(6, '0') + "\u0000 ").toByteArray(Charsets.US_ASCII).copyInto(header, 148)
    return header
}

fun packUstar(entries: List<GzipSource>): ByteArray {
    val out = ByteArrayOutputStream()
    for (entry in entries.sortedBy { it.relPath }) {
        out.write(tarHeader(entry.relPath, entry.data.size, entry.mode))
        out.write(entry.data)
        val pad = (BLOCK - (entry.data.size % BLOCK)) % BLOCK
        if (pad > 0) out.write(ByteArray(pad))
    }
    out.write(ByteArray(BLOCK * 2))
    return out.toByteArray()
}

fun gzipBytes(data: ByteArray): ByteArray {
    val out = ByteArrayOutputStream()
    GZIPOutputStream(out).use { it.write(data) }
    return out.toByteArray()
}

fun gunzipBytes(data: ByteArray): ByteArray {
    return GZIPInputStream(ByteArrayInputStream(data)).use { it.readBytes() }
}

fun encodePayload(archiveName: String, archiveBytes: ByteArray): Pair<ByteArray, ByteArray> {
    val body = Base64.getEncoder().encode(archiveBytes)
    val wrapped = ByteArrayOutputStream()
    var i = 0
    while (i < body.size) {
        if (i > 0) wrapped.write('\n'.code)
        val end = minOf(i + 76, body.size)
        wrapped.write(body, i, end - i)
        i = end
    }
    val header = (
        "BAIC-ENCODED-CONTEXT-V1\n" +
            "archive-name: $archiveName\n" +
            "content-format: tar+gzip\n" +
            "transport-encoding: base64\n" +
            "archive-size-bytes: ${archiveBytes.size}\n" +
            "archive-sha256: ${sha256(archiveBytes)}\n" +
            "base64-body-size-bytes: ${body.size}\n" +
            "base64-body-sha256: ${sha256(body)}\n\n"
        ).toByteArray(Charsets.US_ASCII)
    return header + wrapped.toByteArray() + "\n".toByteArray(Charsets.US_ASCII) to body
}

fun unpackUstar(archive: ByteArray): List<Pair<String, ByteArray>> {
    val out = ArrayList<Pair<String, ByteArray>>()
    var offset = 0
    fun cString(start: Int, width: Int): String {
        val slice = archive.copyOfRange(start, start + width)
        val end = slice.indexOf(0)
        return String(if (end < 0) slice else slice.copyOf(end), Charsets.UTF_8)
    }
    fun octalAt(start: Int, width: Int): Int {
        val raw = cString(start, width).trim()
        if (raw.isEmpty()) return 0
        return raw.toInt(8)
    }
    while (offset + BLOCK <= archive.size) {
        val zero = archive.copyOfRange(offset, offset + BLOCK).all { it == 0.toByte() }
        if (zero) break
        val name = cString(offset, 100)
        val prefix = cString(offset + 345, 155)
        val path = if (prefix.isEmpty()) name else "$prefix/$name"
        val size = octalAt(offset + 124, 12)
        val type = archive[offset + 156]
        offset += BLOCK
        val data = archive.copyOfRange(offset, offset + size)
        val pad = (BLOCK - (size % BLOCK)) % BLOCK
        offset += size + pad
        if (type == 0.toByte() || type == '0'.code.toByte()) out.add(path to data)
    }
    return out
}

fun writeGzipExport(
    outputDir: Path,
    folderName: String,
    timestamp: String,
    sources: List<GzipSource>,
): GzipWriteResult {
    val ordered = sources.sortedBy { it.relPath }
    val archiveBytes = gzipBytes(packUstar(ordered))
    val archiveName = "${folderName}_context_${timestamp}.tar.gz"
    val payloadName = "${folderName}_payload_${timestamp}.txt"
    val (payload, body) = encodePayload(archiveName, archiveBytes)
    val payloadPath = outputDir.resolve(payloadName)
    Files.write(payloadPath, payload)
    val record = linkedMapOf<String, Any?>(
        "part" to 1,
        "part_count" to 1,
        "payload" to payloadName,
        "payload_size_bytes" to payload.size,
        "payload_sha256" to sha256(payload),
        "base64_body_size_bytes" to body.size,
        "base64_body_sha256" to sha256(body),
        "archive_name" to archiveName,
        "archive_size_bytes" to archiveBytes.size,
        "archive_sha256" to sha256(archiveBytes),
        "entries" to ordered.map { it.relPath },
    )
    val entries = ordered.map { source ->
        linkedMapOf<String, Any?>(
            "path" to source.relPath,
            "category" to source.category,
            "content_kind" to if (source.encoding == "text") "text" else "binary",
            "source_format" to if (source.relPath.lowercase().endsWith(".gz")) "gzip" else null,
            "transport_encoding" to "identity",
            "size_bytes" to source.sizeBytes,
            "sha256" to source.sha256,
            "mode" to source.mode,
            "payload_part" to 1,
        )
    }
    return GzipWriteResult(
        payloadPaths = listOf(payloadPath.toString()),
        payloadRecords = listOf(record),
        archiveEntries = entries,
        logicalPaths = ordered.map { it.relPath },
    )
}

fun restoreExport(source: Path, output: Path, force: Boolean = false): Pair<Path, Int> {
    val manifestPath = if (Files.isRegularFile(source)) {
        source
    } else {
        val manifests = Files.newDirectoryStream(source, "*_manifest_*.json").use { it.toList() }.sorted()
        if (manifests.size != 1) throw RestoreError("Expected exactly one manifest in $source; found ${manifests.size}")
        manifests[0]
    }
    @Suppress("UNCHECKED_CAST")
    val manifest = Json.parse(Files.readString(manifestPath)) as Map<String, Any?>
    @Suppress("UNCHECKED_CAST")
    val transport = manifest["transport"] as? Map<String, Any?> ?: emptyMap()
    if (transport["format"] != "tar+gzip+base64") {
        throw RestoreError("Only tar+gzip+base64 exports can be restored byte-for-byte")
    }
    @Suppress("UNCHECKED_CAST")
    val payloads = transport["payloads"] as? List<Map<String, Any?>> ?: throw RestoreError("Manifest payloads missing")
    val payload = payloads.first()
    val payloadFile = manifestPath.parent.resolve(payload["payload"] as String)
    val payloadBytes = Files.readAllBytes(payloadFile)
    var splitAt = -1
    var i = 0
    while (i < payloadBytes.size - 1) {
        if (payloadBytes[i] == 0x0A.toByte() && payloadBytes[i + 1] == 0x0A.toByte()) {
            splitAt = i
            break
        }
        i++
    }
    if (splitAt < 0) throw RestoreError("Invalid payload header")
    val encoded = payloadBytes.copyOfRange(splitAt + 2, payloadBytes.size)
        .toString(Charsets.US_ASCII)
        .filter { !it.isWhitespace() }
    val archiveBytes = Base64.getDecoder().decode(encoded)
    val tarBytes = gunzipBytes(archiveBytes)
    val files = unpackUstar(tarBytes)
    if (Files.exists(output)) {
        val occupied = if (Files.isDirectory(output)) Files.list(output).use { it.findFirst().isPresent } else true
        if (!force && occupied) throw RestoreError("Output is not empty; use --restore-force: $output")
        if (Files.isDirectory(output)) output.toFile().deleteRecursively() else Files.delete(output)
    }
    Files.createDirectories(output)
    for ((name, data) in files) {
        if (name.contains("..") || name.startsWith("/")) throw RestoreError("Unsafe archive path: $name")
        val target = output.resolve(name)
        Files.createDirectories(target.parent)
        Files.write(target, data)
    }
    return output to files.size
}
