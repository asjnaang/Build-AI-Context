package com.asjnaang.buildaicontext.engine

import java.util.Locale

internal object Json {
    fun parse(text: String): Any? = Parser(text).parse()

    fun stringify(value: Any?, indent: Int = 2): String {
        val sb = StringBuilder()
        write(value, sb, indent, 0)
        return sb.toString()
    }

    private fun write(value: Any?, sb: StringBuilder, indent: Int, level: Int) {
        when (value) {
            null -> sb.append("null")
            is Boolean -> sb.append(value)
            is Number -> sb.append(formatNumber(value))
            is String -> sb.append(escape(value))
            is Map<*, *> -> writeObject(value, sb, indent, level)
            is Iterable<*> -> writeArray(value.toList(), sb, indent, level)
            is Array<*> -> writeArray(value.toList(), sb, indent, level)
            else -> sb.append(escape(value.toString()))
        }
    }

    private fun writeObject(value: Map<*, *>, sb: StringBuilder, indent: Int, level: Int) {
        val entries = value.entries.toList()
        if (entries.isEmpty()) {
            sb.append("{}")
            return
        }
        sb.append("{\n")
        entries.forEachIndexed { index, (key, v) ->
            sb.append(" ".repeat(indent * (level + 1)))
            sb.append(escape(key.toString()))
            sb.append(": ")
            write(v, sb, indent, level + 1)
            if (index < entries.lastIndex) sb.append(',')
            sb.append('\n')
        }
        sb.append(" ".repeat(indent * level)).append('}')
    }

    private fun writeArray(values: List<*>, sb: StringBuilder, indent: Int, level: Int) {
        if (values.isEmpty()) {
            sb.append("[]")
            return
        }
        sb.append("[\n")
        values.forEachIndexed { index, v ->
            sb.append(" ".repeat(indent * (level + 1)))
            write(v, sb, indent, level + 1)
            if (index < values.lastIndex) sb.append(',')
            sb.append('\n')
        }
        sb.append(" ".repeat(indent * level)).append(']')
    }

    private fun formatNumber(n: Number): String {
        return when (n) {
            is Int, is Long, is Short, is Byte -> n.toString()
            is Double, is Float -> {
                val d = n.toDouble()
                if (!d.isFinite()) d.toString()
                else if (d == d.toLong().toDouble() && Math.abs(d) < 1e15) d.toLong().toString()
                else String.format(Locale.US, "%.10f", d).trimEnd('0').trimEnd('.')
            }
            else -> n.toString()
        }
    }

    private fun escape(s: String): String {
        val sb = StringBuilder("\"")
        for (c in s) {
            when (c) {
                '"' -> sb.append("\\\"")
                '\\' -> sb.append("\\\\")
                '\b' -> sb.append("\\b")
                '\u000C' -> sb.append("\\f")
                '\n' -> sb.append("\\n")
                '\r' -> sb.append("\\r")
                '\t' -> sb.append("\\t")
                else -> if (c.code < 0x20) sb.append("\\u%04x".format(c.code)) else sb.append(c)
            }
        }
        return sb.append('"').toString()
    }

    private class Parser(private val s: String) {
        private var i = 0

        fun parse(): Any? {
            skip()
            val value = value()
            skip()
            return value
        }

        private fun value(): Any? {
            skip()
            if (i >= s.length) error("unexpected end of json")
            return when (s[i]) {
                '{' -> obj()
                '[' -> arr()
                '"' -> str()
                't' -> keyword("true", true)
                'f' -> keyword("false", false)
                'n' -> keyword("null", null)
                '-', in '0'..'9' -> num()
                else -> error("unexpected '${s[i]}' at $i")
            }
        }

        private fun obj(): LinkedHashMap<String, Any?> {
            expect('{')
            val out = LinkedHashMap<String, Any?>()
            skip()
            if (peek('}')) {
                i++
                return out
            }
            while (true) {
                skip()
                val key = str()
                skip()
                expect(':')
                out[key] = value()
                skip()
                if (peek('}')) {
                    i++
                    break
                }
                expect(',')
            }
            return out
        }

        private fun arr(): ArrayList<Any?> {
            expect('[')
            val out = ArrayList<Any?>()
            skip()
            if (peek(']')) {
                i++
                return out
            }
            while (true) {
                out.add(value())
                skip()
                if (peek(']')) {
                    i++
                    break
                }
                expect(',')
            }
            return out
        }

        private fun str(): String {
            expect('"')
            val sb = StringBuilder()
            while (i < s.length) {
                val c = s[i++]
                when (c) {
                    '"' -> return sb.toString()
                    '\\' -> {
                        if (i >= s.length) error("unterminated escape")
                        when (val e = s[i++]) {
                            '"', '\\', '/' -> sb.append(e)
                            'b' -> sb.append('\b')
                            'f' -> sb.append('\u000C')
                            'n' -> sb.append('\n')
                            'r' -> sb.append('\r')
                            't' -> sb.append('\t')
                            'u' -> {
                                val hex = s.substring(i, i + 4)
                                i += 4
                                sb.append(hex.toInt(16).toChar())
                            }
                            else -> error("bad escape \\$e")
                        }
                    }
                    else -> sb.append(c)
                }
            }
            error("unterminated string")
        }

        private fun num(): Number {
            val start = i
            if (peek('-')) i++
            while (i < s.length && s[i] in '0'..'9') i++
            var isFloat = false
            if (i < s.length && s[i] == '.') {
                isFloat = true
                i++
                while (i < s.length && s[i] in '0'..'9') i++
            }
            if (i < s.length && (s[i] == 'e' || s[i] == 'E')) {
                isFloat = true
                i++
                if (i < s.length && (s[i] == '+' || s[i] == '-')) i++
                while (i < s.length && s[i] in '0'..'9') i++
            }
            val raw = s.substring(start, i)
            return if (isFloat) raw.toDouble() else raw.toLong().let { if (it in Int.MIN_VALUE..Int.MAX_VALUE) it.toInt() else it }
        }

        private fun keyword(word: String, value: Any?): Any? {
            if (!s.startsWith(word, i)) error("expected $word")
            i += word.length
            return value
        }

        private fun expect(c: Char) {
            skip()
            if (i >= s.length || s[i] != c) error("expected $c at $i")
            i++
        }

        private fun peek(c: Char) = i < s.length && s[i] == c

        private fun skip() {
            while (i < s.length && s[i].isWhitespace()) i++
        }
    }
}

@Suppress("UNCHECKED_CAST")
internal fun Map<*, *>.asStrMap(): Map<String, Any?> = this as Map<String, Any?>

internal fun Map<String, Any?>.intVal(key: String): Int = (this[key] as Number).toInt()

internal fun Map<String, Any?>.strVal(key: String): String = this[key] as String

@Suppress("UNCHECKED_CAST")
internal fun Map<String, Any?>.strList(key: String): List<String> =
    (this[key] as List<*>).map { it as String }

@Suppress("UNCHECKED_CAST")
internal fun Map<String, Any?>.strToStr(key: String): Map<String, String> =
    (this[key] as Map<*, *>).entries.associate { it.key as String to it.value as String }

@Suppress("UNCHECKED_CAST")
internal fun Map<String, Any?>.strToStrList(key: String): Map<String, List<String>> =
    (this[key] as Map<*, *>).entries.associate { (k, v) ->
        k as String to (v as List<*>).map { it as String }
    }
