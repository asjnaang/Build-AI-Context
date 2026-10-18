"""Restore exact files from a BAIC tar+gzip+base64 export."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import shutil
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Dict, List, Mapping, Tuple


class RestoreError(ValueError):
    """Raised when a BAIC export cannot be validated or safely restored."""


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or path.is_absolute()
        or any(part in ("", ".", "..") for part in path.parts)
    ):
        raise RestoreError(f"Unsafe archive path: {name!r}")
    return path


def _manifest_for(source: Path) -> Path:
    source = source.expanduser().resolve()
    if source.is_file():
        if source.suffix.lower() != ".json":
            raise RestoreError(f"Restore source must be a manifest JSON file or export directory: {source}")
        return source
    if not source.is_dir():
        raise RestoreError(f"Restore source does not exist: {source}")
    manifests = sorted(source.glob("*_manifest_*.json"))
    if not manifests:
        manifests = sorted(source.glob("*manifest*.json"))
    if len(manifests) != 1:
        raise RestoreError(
            f"Expected exactly one manifest in {source}; found {len(manifests)}. "
            "Pass the exact manifest path when a directory contains multiple manifests."
        )
    return manifests[0]


def _payload_records(transport: Mapping[str, object]) -> List[Mapping[str, object]]:
    raw = transport.get("payloads") or [transport]
    records = sorted(raw, key=lambda item: int(item.get("part", 1)))
    parts = [int(item.get("part", 1)) for item in records]
    if parts != list(range(1, len(records) + 1)):
        raise RestoreError("Manifest has missing, duplicate, or reordered payload parts")
    if any(int(item.get("part_count", len(records))) != len(records) for item in records):
        raise RestoreError("Manifest payload part-count mismatch")
    return records


def _decode_payload(
    manifest_path: Path,
    record: Mapping[str, object],
    expected: Mapping[str, Mapping[str, object]],
) -> Dict[str, bytes]:
    payload_name = str(record["payload"])
    payload_path = manifest_path.parent / payload_name
    try:
        payload_bytes = payload_path.read_bytes()
    except FileNotFoundError as error:
        raise RestoreError(f"Missing payload: {payload_path}") from error
    if (
        len(payload_bytes) != int(record["payload_size_bytes"])
        or _digest(payload_bytes) != record["payload_sha256"]
    ):
        raise RestoreError(f"Payload size or SHA-256 mismatch: {payload_name}")
    header, separator, body = payload_bytes.partition(b"\n\n")
    if not separator or not header.startswith(b"BAIC-ENCODED-CONTEXT-V1\n"):
        raise RestoreError(f"Invalid payload header: {payload_name}")
    encoded = b"".join(body.split())
    if (
        len(encoded) != int(record["base64_body_size_bytes"])
        or _digest(encoded) != record["base64_body_sha256"]
    ):
        raise RestoreError(f"Base64 body size or SHA-256 mismatch: {payload_name}")
    try:
        archive_bytes = base64.b64decode(encoded, validate=True)
    except ValueError as error:
        raise RestoreError(f"Invalid Base64 body: {payload_name}") from error
    if (
        len(archive_bytes) != int(record["archive_size_bytes"])
        or _digest(archive_bytes) != record["archive_sha256"]
    ):
        raise RestoreError(f"Decoded archive size or SHA-256 mismatch: {payload_name}")
    files: Dict[str, bytes] = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
            for member in archive.getmembers():
                name = str(_safe_path(member.name))
                if name in files or name not in expected or not member.isfile():
                    raise RestoreError(f"Unexpected or unsafe archive member: {name}")
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise RestoreError(f"Archive member has no data: {name}")
                data = extracted.read()
                entry = expected[name]
                if len(data) != int(entry["size_bytes"]) or _digest(data) != entry["sha256"]:
                    raise RestoreError(f"Archive entry size or SHA-256 mismatch: {name}")
                files[name] = data
    except tarfile.TarError as error:
        raise RestoreError(f"Invalid tar+gzip archive: {payload_name}") from error
    record_entries = {str(name) for name in record["entries"]}
    if set(files) != record_entries:
        raise RestoreError(f"Payload path-set mismatch: {payload_name}")
    return files


def restore_export(source: Path, output: Path | None = None, force: bool = False) -> Tuple[Path, int]:
    """Validate a BAIC compressed export and atomically restore its logical files."""
    manifest_path = _manifest_for(source)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RestoreError(f"Invalid manifest JSON: {manifest_path}") from error
    transport = manifest.get("transport") or {}
    if transport.get("format") != "tar+gzip+base64":
        raise RestoreError("Only tar+gzip+base64 exports can be restored byte-for-byte")
    archive_entries = manifest.get("archive_entries") or []
    expected = {str(entry["path"]): entry for entry in archive_entries}
    if not expected or len(expected) != len(archive_entries):
        raise RestoreError("Manifest has no archive entries or contains duplicate paths")
    for name in expected:
        _safe_path(name)

    physical: Dict[str, bytes] = {}
    for record in _payload_records(transport):
        part_files = _decode_payload(manifest_path, record, expected)
        overlap = set(physical).intersection(part_files)
        if overlap:
            raise RestoreError(f"Archive members appear in multiple payloads: {sorted(overlap)}")
        physical.update(part_files)
    if set(physical) != set(expected):
        missing = sorted(set(expected) - set(physical))
        raise RestoreError(f"Archive path-set mismatch; missing: {missing}")

    consumed = set()
    restored: Dict[str, bytes] = {}
    modes = {name: int(entry.get("mode", 0o644)) for name, entry in expected.items()}
    for record in transport.get("reassembly") or []:
        name = str(_safe_path(str(record["path"])))
        members = [str(_safe_path(str(member))) for member in record["members"]]
        if (
            not members
            or name in restored
            or any(member in consumed or member not in physical for member in members)
        ):
            raise RestoreError(f"Invalid reassembly record: {name}")
        data = b"".join(physical[member] for member in members)
        if len(data) != int(record["size_bytes"]) or _digest(data) != record["sha256"]:
            raise RestoreError(f"Reassembled file size or SHA-256 mismatch: {name}")
        restored[name] = data
        modes[name] = int(record.get("mode", 0o644))
        consumed.update(members)
    for name, data in physical.items():
        if name not in consumed:
            restored[name] = data

    if output is None:
        project_name = Path(str(manifest.get("project_root") or "")).name
        if not project_name or project_name in (".", ".."):
            raise RestoreError(
                "Manifest project_root has no usable project name; pass --restore-output"
            )
        destination = (Path.cwd() / project_name).resolve()
    else:
        destination = output.expanduser().resolve()
    source_directory = manifest_path.parent.resolve()
    if destination == source_directory:
        raise RestoreError(
            "Restore output cannot be the export source directory; omit --restore-output "
            "to use the PROJECT_NAME default or choose another directory"
        )
    if destination.exists():
        if not force:
            if any(destination.iterdir()) if destination.is_dir() else True:
                raise RestoreError(f"Output is not empty; use --restore-force: {destination}")
        elif destination.is_dir():
            shutil.rmtree(destination)
        else:
            destination.unlink()
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}.restore-", dir=destination.parent))
    try:
        for name, data in restored.items():
            target = stage.joinpath(*_safe_path(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(modes.get(name, 0o644) & 0o777)
        for name, data in restored.items():
            target = stage.joinpath(*_safe_path(name).parts)
            if target.read_bytes() != data:
                raise RestoreError(f"Restored file verification failed: {name}")
        if destination.exists():
            destination.rmdir()
        stage.replace(destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return destination, len(restored)
