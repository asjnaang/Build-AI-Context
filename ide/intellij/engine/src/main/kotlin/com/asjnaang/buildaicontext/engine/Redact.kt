package com.asjnaang.buildaicontext.engine

import java.util.regex.Matcher
import java.util.regex.Pattern

private val RE_JWT = Pattern.compile(
    "\\beyJ[A-Za-z0-9_\\-]{10,}\\.[A-Za-z0-9_\\-]{10,}\\.[A-Za-z0-9_\\-]{10,}\\b",
)
private val RE_BEARER = Pattern.compile(
    "(Authorization\\s*:\\s*Bearer\\s+)([A-Za-z0-9\\-_.=]+)",
    Pattern.CASE_INSENSITIVE,
)
private val RE_BEARER_JSON = Pattern.compile(
    "(\"Authorization\"\\s*:\\s*\")Bearer\\s+[^\"]+(\")",
    Pattern.CASE_INSENSITIVE,
)
private val RE_API_KEY_HEADER = Pattern.compile(
    "((?:x-api-key|api-key|apikey|api_key)[\"\\s:=]+)([\"']?[A-Za-z0-9_\\-.]{8,}[\"']?)",
    Pattern.CASE_INSENSITIVE,
)
private val RE_JSON_SECRET = Pattern.compile(
    "(\"(?:api[_-]?key|token|secret|password|client[_-]?secret|access[_-]?token|refresh[_-]?token|bearer|auth_token|private[_-]?key|credentials)\"\\s*:\\s*)\"[^\"]*\"",
    Pattern.CASE_INSENSITIVE,
)
private val RE_YAML_SECRET = Pattern.compile(
    "(api[_-]?key|token|secret|password|client[_-]?secret|access[_-]?token|refresh[_-]?token|bearer|auth_token|private[_-]?key|credentials|secret[_-]?key|signing[_-]?key)\\s*:\\s*(\\S+)",
    Pattern.CASE_INSENSITIVE,
)
private val RE_URL_SECRET = Pattern.compile(
    "\\b((?:token|access_token|refresh_token|api_key|apikey|secret|sig|signature|auth|bearer|password|passwd|pwd)=)([^&\\s\"]+)",
    Pattern.CASE_INSENSITIVE,
)
private val RE_PRIVATE_KEY_BLOCK = Pattern.compile(
    "-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    Pattern.DOTALL,
)
private val RE_ENV_SECRET = Pattern.compile(
    "^\\s*(?:export\\s+)?(?<key>(?:SECRET_KEY|API_KEY|PRIVATE_KEY|SIGNING_KEY|CLIENT_SECRET|API_SECRET|ACCESS_KEY|AUTH_TOKEN|BEARER_TOKEN|CREDENTIALS|TOKEN|PASSWORD|PASS|SIGNING_SECRET|API_PASSWORD|CLIENT_KEY)[A-Z0-9_]*)\\s*=\\s*(?<val>.*)\$",
    Pattern.MULTILINE,
)
private val RE_BASE64_SECRET = Pattern.compile(
    "((?:secret|private|signing)[_-]?key(?:_[a-z]+)?)\\s*=\\s*['\"]([A-Za-z0-9+/]{20,}={0,2})['\"]",
    Pattern.CASE_INSENSITIVE,
)
private val RE_HEX_TOKEN = Pattern.compile(
    "((?:secret|token|password|auth)[_-]?(?:key|value|hash|secret)?)\\s*=\\s*['\"]([0-9a-f]{32,})['\"]",
    Pattern.CASE_INSENSITIVE,
)
private val RE_AWS_KEY = Pattern.compile("(AKIA[0-9A-Z]{16})")
private val RE_GITHUB_TOKEN = Pattern.compile("(gh[pousr]_[A-Za-z0-9_]{36,251})")
private val RE_SLACK_TOKEN = Pattern.compile("(xox[bpors]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*)")
private val RE_GOOGLE_API_KEY = Pattern.compile("(AIza[0-9A-Za-z\\-_]{35})")
private val RE_STRIPE_KEY = Pattern.compile("(sk_live_[0-9a-zA-Z]{24,})")
private val RE_TWILIO_KEY = Pattern.compile("(SK[0-9a-fA-F]{32})")

fun redactText(text: String?): String {
    if (text.isNullOrEmpty()) return text ?: ""
    val mark = loadPolicy().redactionMark
    var out = text
    out = RE_PRIVATE_KEY_BLOCK.matcher(out).replaceAll(
        Matcher.quoteReplacement("-----BEGIN PRIVATE KEY-----\n$mark\n-----END PRIVATE KEY-----"),
    )
    out = RE_BEARER.matcher(out).replaceAll("$1${Matcher.quoteReplacement(mark)}")
    out = RE_BEARER_JSON.matcher(out).replaceAll("$1Bearer ${Matcher.quoteReplacement(mark)}$2")
    out = RE_API_KEY_HEADER.matcher(out).replaceAll("$1${Matcher.quoteReplacement(mark)}")
    out = RE_JWT.matcher(out).replaceAll(Matcher.quoteReplacement(mark))
    out = RE_AWS_KEY.matcher(out).replaceAll(Matcher.quoteReplacement(mark))
    out = RE_GITHUB_TOKEN.matcher(out).replaceAll(Matcher.quoteReplacement(mark))
    out = RE_SLACK_TOKEN.matcher(out).replaceAll(Matcher.quoteReplacement(mark))
    out = RE_GOOGLE_API_KEY.matcher(out).replaceAll(Matcher.quoteReplacement(mark))
    out = RE_STRIPE_KEY.matcher(out).replaceAll(Matcher.quoteReplacement(mark))
    out = RE_TWILIO_KEY.matcher(out).replaceAll(Matcher.quoteReplacement(mark))
    out = RE_JSON_SECRET.matcher(out).replaceAll("$1\"${Matcher.quoteReplacement(mark)}\"")
    out = replaceEach(out, RE_YAML_SECRET) { m ->
        val key = m.group(1)
        val value = m.group(2).trim()
        if (value.isEmpty() || value == "\"\"" || value == "''" || value == "null" || value == "~") m.group(0)
        else "$key: $mark"
    }
    out = RE_URL_SECRET.matcher(out).replaceAll("$1${Matcher.quoteReplacement(mark)}")
    out = RE_BASE64_SECRET.matcher(out).replaceAll("$1=\"${Matcher.quoteReplacement(mark)}\"")
    out = RE_HEX_TOKEN.matcher(out).replaceAll("$1='${Matcher.quoteReplacement(mark)}'")
    out = replaceEach(out, RE_ENV_SECRET) { m ->
        val key = m.group("key")
        val value = (m.group("val") ?: "")
        if (value.trim().isEmpty()) return@replaceEach m.group(0)
        val v = value.trim()
        if ((v.startsWith("\"") && v.endsWith("\"")) || (v.startsWith("'") && v.endsWith("'"))) {
            val q = v[0]
            "$key=$q$mark$q"
        } else {
            "$key=$mark"
        }
    }
    return out
}

fun redactLines(lines: List<String>): List<String> = lines.map { redactText(it) }

private fun replaceEach(text: String, pattern: Pattern, transform: (Matcher) -> String): String {
    val matcher = pattern.matcher(text)
    val sb = StringBuffer()
    while (matcher.find()) {
        matcher.appendReplacement(sb, Matcher.quoteReplacement(transform(matcher)))
    }
    matcher.appendTail(sb)
    return sb.toString()
}
