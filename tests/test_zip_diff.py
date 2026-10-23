from __future__ import annotations

import contextlib
import io
import json
import stat
import struct
import tempfile
import unittest
import warnings
import zipfile
from dataclasses import replace
from pathlib import Path

from zip_content_diff.cli import main
from zip_content_diff.core import ArchiveError, Limits, compare, inspect_archive


class ZipDiffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.left, self.right = self.root / "left.zip", self.root / "right.zip"

    def write(
        self,
        path,
        entries=None,
        *,
        year=2020,
        compression=zipfile.ZIP_STORED,
        mode=stat.S_IFREG | 0o644,
        comment=b"",
        extra=b"",
    ):
        with zipfile.ZipFile(path, "w") as archive:
            for name, data in entries if entries is not None else [("a.txt", b"abc")]:
                info = zipfile.ZipInfo(name, (year, 1, 1, 0, 0, 0))
                info.compress_type = compression
                info.create_system = 3
                info.external_attr = mode << 16
                info.extra = extra
                archive.writestr(info, data)
            archive.comment = comment

    def test_equal_archives_are_fully_verified(self):
        self.write(self.left)
        self.write(self.right)
        result = compare(self.left, self.right)
        self.assertTrue(result["byte_equal"])
        self.assertTrue(result["payload_equal"])
        self.assertEqual(result["unchanged_payload_members"], 1)

    def test_timestamp_drift_is_metadata(self):
        self.write(self.left)
        self.write(self.right, year=2021)
        result = compare(self.left, self.right)
        self.assertTrue(result["payload_equal"])
        self.assertFalse(result["byte_equal"])
        self.assertEqual(result["metadata_changes"], [{"name": "a.txt", "fields": ["timestamp"]}])

    def test_compression_changes_are_metadata(self):
        self.write(self.left)
        self.write(self.right, compression=zipfile.ZIP_DEFLATED)
        result = compare(self.left, self.right)
        self.assertTrue(result["payload_equal"])
        self.assertIn("compression", result["metadata_changes"][0]["fields"])

    def test_member_order_is_tracked(self):
        entries = [("a", b"one"), ("b", b"two")]
        self.write(self.left, entries)
        self.write(self.right, list(reversed(entries)))
        result = compare(self.left, self.right)
        self.assertTrue(result["payload_equal"])
        self.assertTrue(result["member_order_changed"])

    def test_add_remove_and_change(self):
        self.write(self.left, [("old", b"x"), ("change", b"one"), ("same", b"y")])
        self.write(self.right, [("new", b"x"), ("change", b"two"), ("same", b"y")])
        result = compare(self.left, self.right)
        self.assertFalse(result["payload_equal"])
        self.assertEqual(result["added"], ["new"])
        self.assertEqual(result["removed"], ["old"])
        self.assertEqual([entry["name"] for entry in result["changed"]], ["change"])
        self.assertNotEqual(
            result["changed"][0]["left_sha256"], result["changed"][0]["right_sha256"]
        )
        self.assertEqual(result["unchanged_payload_members"], 1)

    def test_empty_archives(self):
        self.write(self.left, [])
        self.write(self.right, [])
        self.assertTrue(compare(self.left, self.right)["byte_equal"])

    def test_directory_entry_is_not_ignored(self):
        self.write(self.left, [])
        self.write(self.right, [("empty/", b"")], mode=stat.S_IFDIR | 0o755)
        result = compare(self.left, self.right)
        self.assertEqual(result["added"], ["empty/"])
        self.assertFalse(result["payload_equal"])

    def test_symlink_kind_differs_from_file(self):
        self.write(self.left, mode=stat.S_IFLNK | 0o777)
        self.write(self.right)
        result = compare(self.left, self.right)
        self.assertFalse(result["payload_equal"])
        self.assertEqual(result["changed"][0]["left_kind"], "symlink")

    def test_permissions_are_metadata(self):
        self.write(self.left, mode=stat.S_IFREG | 0o644)
        self.write(self.right, mode=stat.S_IFREG | 0o755)
        result = compare(self.left, self.right)
        self.assertTrue(result["payload_equal"])
        self.assertIn("external_attributes", result["metadata_changes"][0]["fields"])

    def test_extra_fields_are_compared_without_dumping_values(self):
        self.write(self.left)
        self.write(self.right, extra=struct.pack("<HH", 0xCAFE, 4) + b"priv")
        result = compare(self.left, self.right)
        self.assertIn("extra_sha256", result["metadata_changes"][0]["fields"])
        self.assertNotIn("priv", json.dumps(result))

    def test_archive_comment_is_metadata_without_value_disclosure(self):
        self.write(self.left)
        self.write(self.right, comment=b"private-comment-canary")
        result = compare(self.left, self.right)
        self.assertTrue(result["archive_comment_changed"])
        self.assertNotIn("private-comment-canary", json.dumps(result))

    def test_unmodeled_container_bytes_are_visible(self):
        self.write(self.left)
        self.right.write_bytes(b"PREFIX" + self.left.read_bytes())
        result = compare(self.left, self.right)
        self.assertTrue(result["payload_equal"])
        self.assertTrue(result["unclassified_container_change"])
        self.assertFalse(result["byte_equal"])

    def test_duplicate_names_are_rejected(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.write(self.left, [("a", b"one"), ("a", b"two")])
        with self.assertRaisesRegex(ArchiveError, "duplicate_member_name"):
            inspect_archive(self.left)

    def test_invalid_zip_is_refused(self):
        self.left.write_bytes(b"not a zip")
        with self.assertRaisesRegex(ArchiveError, "invalid_or_unsupported_zip"):
            inspect_archive(self.left)

    def test_corrupt_member_fails_even_when_both_inputs_are_identical(self):
        self.write(self.left)
        raw = bytearray(self.left.read_bytes())
        name_length, extra_length = struct.unpack_from("<HH", raw, 26)
        raw[30 + name_length + extra_length] ^= 1
        self.left.write_bytes(raw)
        with self.assertRaisesRegex(ArchiveError, "invalid_or_unsupported_zip"):
            compare(self.left, self.left)

    def test_encrypted_flag_is_refused(self):
        self.write(self.left)
        raw = bytearray(self.left.read_bytes())
        central = raw.index(b"PK\x01\x02")
        struct.pack_into("<H", raw, 6, 1)
        struct.pack_into("<H", raw, central + 8, 1)
        self.left.write_bytes(raw)
        with self.assertRaisesRegex(ArchiveError, "encrypted_member"):
            inspect_archive(self.left)

    def test_unsupported_compression_is_refused(self):
        self.write(self.left, compression=zipfile.ZIP_BZIP2)
        with self.assertRaisesRegex(ArchiveError, "unsupported_compression"):
            inspect_archive(self.left)

    def test_special_file_type_is_refused(self):
        self.write(self.left, mode=stat.S_IFIFO | 0o600)
        with self.assertRaisesRegex(ArchiveError, "unsupported_member_type"):
            inspect_archive(self.left)

    def test_inconsistent_directory_type_is_refused(self):
        self.write(self.left, mode=stat.S_IFDIR | 0o755)
        with self.assertRaisesRegex(ArchiveError, "ambiguous_member_type"):
            inspect_archive(self.left)

    def test_no_extraction_of_traversal_or_symlinks(self):
        self.write(self.left, [("../outside", b"never written"), ("/absolute", b"never written")])
        before = sorted(path.name for path in self.root.iterdir())
        result = inspect_archive(self.left)
        self.assertEqual(sorted(result["members"]), ["../outside", "/absolute"])
        self.assertEqual(before, sorted(path.name for path in self.root.iterdir()))

    def test_names_are_not_casefolded(self):
        self.write(self.left, [("README", b"same")])
        self.write(self.right, [("readme", b"same")])
        self.assertFalse(compare(self.left, self.right)["payload_equal"])

    def test_size_and_entry_limits(self):
        self.write(self.left, [("a", b"abcd"), ("b", b"abcd")])
        for limits, code in (
            (Limits(max_archive_bytes=1), "archive_size_limit"),
            (Limits(max_entries=1), "entry_count_limit"),
            (Limits(max_member_bytes=3), "member_size_limit"),
            (Limits(max_total_bytes=7), "total_size_limit"),
        ):
            with self.subTest(code=code), self.assertRaisesRegex(ArchiveError, code):
                inspect_archive(self.left, limits)

    def test_ratio_limit(self):
        self.write(self.left, [("dense", b"x" * 100000)], compression=zipfile.ZIP_DEFLATED)
        with self.assertRaisesRegex(ArchiveError, "compression_ratio_limit"):
            inspect_archive(self.left, Limits(max_ratio=2))

    def test_time_budget(self):
        self.write(self.left)
        with self.assertRaisesRegex(ArchiveError, "time_budget_exceeded"):
            inspect_archive(self.left, Limits(timeout_seconds=1e-12))

    def test_invalid_limits(self):
        for name, value in (
            ("max_entries", 0),
            ("max_member_bytes", True),
            ("max_ratio", float("nan")),
            ("timeout_seconds", -1),
            ("max_ratio", True),
        ):
            with self.subTest(name=name, value=value), self.assertRaises(ArchiveError):
                replace(Limits(), **{name: value})

    def test_missing_and_directory_inputs(self):
        for path in (self.root, self.left):
            with self.subTest(path=path), self.assertRaisesRegex(ArchiveError, "input_not_file"):
                inspect_archive(path)

    def test_json_is_deterministic_and_omits_payloads_and_input_paths(self):
        self.write(self.left, [("a", b"private-payload-canary")])
        self.write(self.right, [("a", b"changed-payload-canary")])
        command = [str(self.left), str(self.right), "--json"]
        with contextlib.redirect_stdout(io.StringIO()) as first:
            self.assertEqual(main(command), 1)
        with contextlib.redirect_stdout(io.StringIO()) as second:
            self.assertEqual(main(command), 1)
        self.assertEqual(first.getvalue(), second.getvalue())
        self.assertNotIn("payload-canary", first.getvalue())
        self.assertNotIn(str(self.root), first.getvalue())

    def test_cli_default_strict_text_and_json(self):
        self.write(self.left)
        self.write(self.right, year=2021)
        command = [str(self.left), str(self.right)]
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(command), 0)
        self.assertIn("timestamp", output.getvalue())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main([*command, "--strict", "--json"]), 1)
        self.right.write_bytes(self.left.read_bytes())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main([*command, "--strict"]), 0)

    def test_cli_error_codes(self):
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(main([str(self.left), str(self.right)]), 2)
            self.assertEqual(main([str(self.left), str(self.right), "--max-entries", "0"]), 2)
        self.assertIn("invalid_limits", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
