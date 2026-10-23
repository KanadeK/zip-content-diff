from __future__ import annotations

import hashlib
import math
import stat
import time
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path

CHUNK = 64 * 1024


class ArchiveError(ValueError):
    """An expected archive/policy error, without file contents in the message."""


@dataclass(frozen=True)
class Limits:
    max_archive_bytes: int = 64 * 1024 * 1024
    max_entries: int = 10000
    max_member_bytes: int = 64 * 1024 * 1024
    max_total_bytes: int = 256 * 1024 * 1024
    max_ratio: float = 1000.0
    timeout_seconds: float = 30.0

    def __post_init__(self):
        for value in (
            self.max_archive_bytes,
            self.max_entries,
            self.max_member_bytes,
            self.max_total_bytes,
        ):
            if type(value) is not int or value <= 0:
                raise ArchiveError("invalid_limits")
        for value in (self.max_ratio, self.timeout_seconds):
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ArchiveError("invalid_limits")


DEFAULT_LIMITS = Limits()


def _check_time(deadline: float) -> None:
    if time.monotonic() > deadline:
        raise ArchiveError("time_budget_exceeded")


def inspect_archive(path: Path, limits: Limits = DEFAULT_LIMITS) -> dict:
    """Hash all member bytes in bounded chunks. No member is extracted or executed."""
    path = Path(path)
    deadline = time.monotonic() + limits.timeout_seconds
    if not path.is_file():
        raise ArchiveError("input_not_file")
    if path.stat().st_size > limits.max_archive_bytes:
        raise ArchiveError("archive_size_limit")
    raw_hash = hashlib.sha256()
    raw_size = 0
    with path.open("rb") as source:
        while data := source.read(CHUNK):
            _check_time(deadline)
            raw_size += len(data)
            if raw_size > limits.max_archive_bytes:
                raise ArchiveError("archive_size_limit")
            raw_hash.update(data)
        source.seek(0)
        try:
            with zipfile.ZipFile(source) as archive:
                entries = archive.infolist()
                if len(entries) > limits.max_entries:
                    raise ArchiveError("entry_count_limit")
                members = {}
                order = []
                declared_total = actual_total = 0
                for entry in entries:
                    _check_time(deadline)
                    name = entry.filename
                    if name in members:
                        raise ArchiveError("duplicate_member_name")
                    if not name or entry.orig_filename != name:
                        raise ArchiveError("ambiguous_member_name")
                    if entry.flag_bits & 1:
                        raise ArchiveError("encrypted_member")
                    if entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                        raise ArchiveError("unsupported_compression")
                    if entry.file_size > limits.max_member_bytes:
                        raise ArchiveError("member_size_limit")
                    declared_total += entry.file_size
                    if declared_total > limits.max_total_bytes:
                        raise ArchiveError("total_size_limit")
                    if entry.file_size / max(1, entry.compress_size) > limits.max_ratio:
                        raise ArchiveError("compression_ratio_limit")
                    mode = entry.external_attr >> 16
                    kind = (
                        "symlink"
                        if stat.S_ISLNK(mode)
                        else "directory"
                        if entry.is_dir()
                        else "file"
                    )
                    if stat.S_ISDIR(mode) and not entry.is_dir():
                        raise ArchiveError("ambiguous_member_type")
                    if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR, stat.S_IFLNK):
                        raise ArchiveError("unsupported_member_type")
                    member_hash = hashlib.sha256()
                    member_size = 0
                    with archive.open(entry) as member:
                        while chunk := member.read(CHUNK):
                            _check_time(deadline)
                            member_size += len(chunk)
                            actual_total += len(chunk)
                            if (
                                member_size > limits.max_member_bytes
                                or member_size > entry.file_size
                            ):
                                raise ArchiveError("member_size_limit")
                            if actual_total > limits.max_total_bytes:
                                raise ArchiveError("total_size_limit")
                            member_hash.update(chunk)
                    if member_size != entry.file_size:
                        raise ArchiveError("member_size_mismatch")
                    members[name] = {
                        "sha256": member_hash.hexdigest(),
                        "bytes": member_size,
                        "kind": kind,
                        "metadata": {
                            "timestamp": list(entry.date_time),
                            "compression": entry.compress_type,
                            "compressed_bytes": entry.compress_size,
                            "external_attributes": entry.external_attr,
                            "internal_attributes": entry.internal_attr,
                            "creator_system": entry.create_system,
                            "creator_version": entry.create_version,
                            "extract_version": entry.extract_version,
                            "flags": entry.flag_bits,
                            "extra_sha256": hashlib.sha256(entry.extra).hexdigest(),
                            "comment_sha256": hashlib.sha256(entry.comment).hexdigest(),
                        },
                    }
                    order.append(name)
                return {
                    "sha256": raw_hash.hexdigest(),
                    "bytes": raw_size,
                    "members": members,
                    "order": order,
                    "comment_sha256": hashlib.sha256(archive.comment).hexdigest(),
                    "uncompressed_bytes": actual_total,
                }
        except (
            zipfile.BadZipFile,
            zipfile.LargeZipFile,
            RuntimeError,
            NotImplementedError,
            zlib.error,
            EOFError,
            UnicodeError,
        ) as exc:
            raise ArchiveError("invalid_or_unsupported_zip") from exc


def compare(left: Path, right: Path, limits: Limits = DEFAULT_LIMITS) -> dict:
    first, second = inspect_archive(left, limits), inspect_archive(right, limits)
    a, b = first["members"], second["members"]
    added = sorted(b.keys() - a.keys())
    removed = sorted(a.keys() - b.keys())
    changed = []
    metadata = []
    for name in sorted(a.keys() & b.keys()):
        if any(a[name][key] != b[name][key] for key in ("sha256", "bytes", "kind")):
            changed.append(
                {
                    "name": name,
                    "left_sha256": a[name]["sha256"],
                    "right_sha256": b[name]["sha256"],
                    "left_kind": a[name]["kind"],
                    "right_kind": b[name]["kind"],
                }
            )
        fields = sorted(
            key
            for key in a[name]["metadata"]
            if a[name]["metadata"][key] != b[name]["metadata"][key]
        )
        if fields:
            metadata.append({"name": name, "fields": fields})
    byte_equal = first["sha256"] == second["sha256"] and first["bytes"] == second["bytes"]
    payload_equal = not (added or removed or changed)
    # Compare common-member order separately; added/removed members already change payload identity.
    common = a.keys() & b.keys()
    order_changed = [name for name in first["order"] if name in common] != [
        name for name in second["order"] if name in common
    ]
    comment_changed = first["comment_sha256"] != second["comment_sha256"]
    metadata_equal = not (metadata or order_changed or comment_changed)
    return {
        "schema": "zip-content-diff/v1",
        "byte_equal": byte_equal,
        "payload_equal": payload_equal,
        "tracked_metadata_equal": metadata_equal,
        "unclassified_container_change": not byte_equal and payload_equal and metadata_equal,
        "left": {key: first[key] for key in ("sha256", "bytes", "uncompressed_bytes")},
        "right": {key: second[key] for key in ("sha256", "bytes", "uncompressed_bytes")},
        "added": added,
        "removed": removed,
        "changed": changed,
        "metadata_changes": metadata,
        "member_order_changed": order_changed,
        "archive_comment_changed": comment_changed,
        "unchanged_payload_members": len(common) - len(changed),
    }
