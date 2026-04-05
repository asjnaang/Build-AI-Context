"""Tests for redaction module."""

from build_ai_context.redact import redact_text, REDACTION_MARK


class TestRedaction:
    """Test secret redaction patterns."""

    def test_jwt_token(self):
        text = 'token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"'
        result = redact_text(text)
        assert "eyJ" not in result
        assert REDACTION_MARK in result

    def test_bearer_token(self):
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        result = redact_text(text)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "Bearer" in result
        assert REDACTION_MARK in result

    def test_api_key_json(self):
        text = '{"api_key": "sk-1234567890abcdef"}'
        result = redact_text(text)
        assert "sk-1234567890abcdef" not in result
        assert REDACTION_MARK in result

    def test_env_var_uppercase(self):
        text = "SECRET_KEY=supersecretvalue123"
        result = redact_text(text)
        assert REDACTION_MARK in result
        assert "supersecretvalue123" not in result

    def test_env_var_lowercase_preserved(self):
        """Lowercase env vars should NOT be redacted to avoid false positives."""
        text = "token = get_token_from_config()"
        result = redact_text(text)
        assert "get_token_from_config()" in result

    def test_private_key_block(self):
        text = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC
-----END PRIVATE KEY-----"""
        result = redact_text(text)
        assert "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC" not in result
        assert REDACTION_MARK in result

    def test_url_token_param(self):
        text = "https://api.example.com/data?token=abc123secret"
        result = redact_text(text)
        assert "abc123secret" not in result
        assert REDACTION_MARK in result

    def test_github_token(self):
        text = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmn"
        result = redact_text(text)
        assert "ghp_" not in result
        assert REDACTION_MARK in result

    def test_aws_key(self):
        text = "AKIAIOSFODNN7EXAMPLE"
        result = redact_text(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert REDACTION_MARK in result

    def test_google_api_key(self):
        text = "AIzaSyDummyKeyForTestingPurposesOnly123"
        result = redact_text(text)
        assert "AIzaSyDummyKeyForTestingPurposesOnly123" not in result
        assert REDACTION_MARK in result

    def test_normal_code_preserved(self):
        """Normal code without secrets should pass through unchanged."""
        text = "def calculate_sum(a, b):\n    return a + b"
        result = redact_text(text)
        assert result == text

    def test_password_json(self):
        text = '{"password": "mysecretpassword123"}'
        result = redact_text(text)
        assert "mysecretpassword123" not in result
        assert REDACTION_MARK in result

    def test_yaml_secret(self):
        text = "api_secret: my_secret_value_here"
        result = redact_text(text)
        assert "my_secret_value_here" not in result
        assert REDACTION_MARK in result

    def test_empty_string(self):
        assert redact_text("") == ""

    def test_none_handling(self):
        # redact_text expects str, returns empty string for None
        assert redact_text(None) == ""  # type: ignore


class TestRedactionFalsePositives:
    """Test that common code patterns are NOT redacted (false positive prevention)."""

    def test_react_key_prop(self):
        """React key props should NOT be redacted."""
        test_cases = [
            "key={user}",
            "key={kind}",
            "key={key}",
            "key={item.id}",
            "<MenuItem key={user} value={user}>{user}</MenuItem>",
            "<Paper key={key} elevation={0}>",
        ]
        for text in test_cases:
            result = redact_text(text)
            assert result == text, f"False positive: '{text}' was redacted to '{result}'"

    def test_sql_key_clauses(self):
        """SQL KEY clauses should NOT be redacted."""
        test_cases = [
            "PRIMARY KEY (id)",
            "FOREIGN KEY (user_id) REFERENCES users(id)",
            "KEY `idx_name` (name)",
            "UNIQUE KEY `uk_email` (email)",
            "CONSTRAINT pk PRIMARY KEY (id)",
        ]
        for text in test_cases:
            result = redact_text(text)
            assert result == text, f"False positive: '{text}' was redacted to '{result}'"

    def test_yaml_key_field(self):
        """YAML 'key:' field should NOT be redacted (not api_key/secret_key)."""
        test_cases = [
            "key: value",
            'key: "some value"',
            "key: 'some value'",
            "key: 123",
        ]
        for text in test_cases:
            result = redact_text(text)
            assert result == text, f"False positive: '{text}' was redacted to '{result}'"

    def test_url_key_param_preserved(self):
        """URL key= param (not api_key=) should NOT be redacted."""
        test_cases = [
            "https://example.com/?key=value",
            "https://example.com/?key=12345",
        ]
        for text in test_cases:
            result = redact_text(text)
            assert result == text, f"False positive: '{text}' was redacted to '{result}'"

    def test_env_uppercase_key_suffix(self):
        """Uppercase ENV vars ending with just KEY should NOT be redacted."""
        test_cases = [
            "DATABASE_KEY=abc123",
            "CACHE_KEY=value123",
            "ENCRYPTION_KEY=abc",
            "STORAGE_KEY=xyz",
        ]
        for text in test_cases:
            result = redact_text(text)
            assert result == text, f"False positive: '{text}' was redacted to '{result}'"

    def test_secret_key_env_redacted(self):
        """Uppercase ENV vars with SECRET_KEY SHOULD be redacted."""
        test_cases = [
            "SECRET_KEY=supersecret123",
            "API_KEY=sk_live_abc123",
            "SIGNING_KEY=signvalue",
            "PRIVATE_KEY=keydata",
        ]
        for text in test_cases:
            result = redact_text(text)
            assert REDACTION_MARK in result, f"Missed: '{text}' was not redacted"

    def test_javascript_key_property(self):
        """JavaScript object key property should NOT be redacted."""
        test_cases = [
            'const key = "mykey";',
            "const { key } = obj;",
            "return { key: value };",
            "map.set(key, value);",
        ]
        for text in test_cases:
            result = redact_text(text)
            assert result == text, f"False positive: '{text}' was redacted to '{result}'"

    def test_hex_assignment_without_secret_prefix(self):
        """Hex assignment without secret-related prefix should NOT be redacted."""
        test_cases = [
            'hash = "abcdef1234567890abcdef1234567890"',
            'value = "1234567890abcdef1234567890abcdef"',
            'color = "ff0000ff0000ff0000ff0000ff0000ff"',
        ]
        for text in test_cases:
            result = redact_text(text)
            assert result == text, f"False positive: '{text}' was redacted to '{result}'"

    def test_hex_assignment_with_secret_prefix(self):
        """Hex assignment with secret-related prefix SHOULD be redacted."""
        test_cases = [
            'secret_hash = "abcdef1234567890abcdef1234567890"',
            'token_value = "abcdef1234567890abcdef1234567890"',
            'auth_key = "abcdef1234567890abcdef1234567890"',
        ]
        for text in test_cases:
            result = redact_text(text)
            assert REDACTION_MARK in result, f"Missed: '{text}' was not redacted"
