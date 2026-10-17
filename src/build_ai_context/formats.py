"""Declarative policies for source formats and transport representations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass(frozen=True)
class FormatPolicy:
    """Describe how one source format is represented and constrained."""

    extension: str
    content_kind: str = "text"
    scanner_encoding: str = "text"
    line_limits_apply: bool = True
    redactable: bool = True
    text_transport_supported: bool = True
    compressed_transport_supported: bool = True
    size_warning_bytes: Optional[int] = None


BINARY_SIZE_WARNING_BYTES = 15 * 1024 * 1024

FORMAT_POLICIES: Dict[str, FormatPolicy] = {
    ".gz": FormatPolicy(
        extension=".gz",
        content_kind="binary",
        scanner_encoding="base64",
        line_limits_apply=False,
        redactable=False,
    ),
    ".pdf": FormatPolicy(
        extension=".pdf",
        content_kind="binary",
        scanner_encoding="base64",
        line_limits_apply=False,
        redactable=False,
        size_warning_bytes=BINARY_SIZE_WARNING_BYTES,
    ),
}

DEFAULT_FORMAT_POLICY = FormatPolicy(extension="")


def policy_for_path(path: Path) -> FormatPolicy:
    """Return the registered policy for a path, or the default text policy."""
    return FORMAT_POLICIES.get(path.suffix.lower(), DEFAULT_FORMAT_POLICY)


def is_binary_format(path: Path) -> bool:
    """Return whether a path has a registered binary policy."""
    return policy_for_path(path).content_kind == "binary"
