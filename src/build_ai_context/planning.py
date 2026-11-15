"""Build a transport-neutral export plan before rendering output artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from build_ai_context.formats import is_binary_format, policy_for_path
from build_ai_context.models import SourceFile

BINARY_POLICIES = ("include", "skip", "compressed-only")


@dataclass(frozen=True)
class ExportPlan:
    """Files selected by the user and files eligible for the chosen transport."""

    selected_files: Tuple[SourceFile, ...]
    transport_files: Tuple[SourceFile, ...]
    omitted_files: Tuple[Dict[str, object], ...]
    transport: str
    binary_policy: str

    @property
    def selected_paths(self) -> List[str]:
        return [item.rel_path.as_posix() for item in self.selected_files]

    @property
    def transported_paths(self) -> List[str]:
        return [item.rel_path.as_posix() for item in self.transport_files]


def build_export_plan(
    selected_files: Sequence[SourceFile], transport: str, binary_policy: str
) -> ExportPlan:
    """Apply format and user policies without coupling selection to bundle packing."""
    if binary_policy not in BINARY_POLICIES:
        raise ValueError(f"binary_policy must be one of: {', '.join(BINARY_POLICIES)}")

    transport_files: List[SourceFile] = []
    omitted: List[Dict[str, object]] = []
    for source in selected_files:
        policy = policy_for_path(source.rel_path)
        reason = None
        if is_binary_format(source.rel_path):
            if binary_policy == "skip":
                reason = "binary_policy_skip"
            elif binary_policy == "compressed-only" and transport == "text":
                reason = "binary_policy_requires_compressed_transport"
        if transport == "text" and not policy.text_transport_supported:
            reason = "format_not_supported_by_text_transport"
        if transport == "tar-gz" and not policy.compressed_transport_supported:
            reason = "format_not_supported_by_compressed_transport"
        if reason:
            omitted.append(
                {
                    "path": source.rel_path.as_posix(),
                    "reason": reason,
                    "content_kind": policy.content_kind,
                    "binary_policy": binary_policy,
                    "transport": transport,
                }
            )
        else:
            transport_files.append(source)

    return ExportPlan(
        selected_files=tuple(selected_files),
        transport_files=tuple(transport_files),
        omitted_files=tuple(omitted),
        transport=transport,
        binary_policy=binary_policy,
    )
