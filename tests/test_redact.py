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
        text = 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'
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
        text = 'SECRET_KEY=supersecretvalue123'
        result = redact_text(text)
        assert "supersecretvalue123" not in result
        assert REDACTION_MARK in result

    def test_env_var_lowercase_preserved(self):
        """Lowercase env vars should NOT be redacted to avoid false positives."""
        text = 'token = get_token_from_config()'
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
        text = 'https://api.example.com/data?token=abc123secret'
        result = redact_text(text)
        assert "abc123secret" not in result
        assert REDACTION_MARK in result

    def test_github_token(self):
        text = 'ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmn'
        result = redact_text(text)
        assert "ghp_" not in result
        assert REDACTION_MARK in result

    def test_aws_key(self):
        text = 'AKIAIOSFODNN7EXAMPLE'
        result = redact_text(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert REDACTION_MARK in result

    def test_google_api_key(self):
        text = 'AIzaSyDummyKeyForTestingPurposesOnly123'
        result = redact_text(text)
        assert "AIzaSyDummyKeyForTestingPurposesOnly123" not in result
        assert REDACTION_MARK in result

    def test_normal_code_preserved(self):
        """Normal code without secrets should pass through unchanged."""
        text = 'def calculate_sum(a, b):\n    return a + b'
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
