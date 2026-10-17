"""Tests for transport-neutral export planning and format policies."""

from pathlib import Path

import pytest

from build_ai_context.formats import policy_for_path
from build_ai_context.models import SourceFile
from build_ai_context.planning import build_export_plan


def source(path: str) -> SourceFile:
    return SourceFile(
        abs_path=Path(path),
        rel_path=Path(path),
        category="config_docs",
        line_count=1,
        size_bytes=1,
        sha256="0" * 64,
        lines=["x"],
        encoding=policy_for_path(Path(path)).scanner_encoding,
    )


@pytest.mark.parametrize(
    ("transport", "policy", "expected", "omitted_reason"),
    [
        ("text", "include", ["main.py", "report.pdf"], None),
        ("text", "skip", ["main.py"], "binary_policy_skip"),
        (
            "text",
            "compressed-only",
            ["main.py"],
            "binary_policy_requires_compressed_transport",
        ),
        ("tar-gz", "compressed-only", ["main.py", "report.pdf"], None),
    ],
)
def test_binary_policy_is_explicit(transport, policy, expected, omitted_reason):
    plan = build_export_plan([source("main.py"), source("report.pdf")], transport, policy)
    assert plan.selected_paths == ["main.py", "report.pdf"]
    assert plan.transported_paths == expected
    if omitted_reason:
        assert plan.omitted_files[0]["reason"] == omitted_reason
    else:
        assert not plan.omitted_files


def test_pdf_policy_is_binary_and_not_line_limited():
    policy = policy_for_path(Path("report.pdf"))
    assert policy.content_kind == "binary"
    assert policy.scanner_encoding == "base64"
    assert not policy.line_limits_apply
    assert not policy.redactable
    assert policy.size_warning_bytes == 15 * 1024 * 1024
