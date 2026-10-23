"""Generate three real ZIPs and establish metadata-only and payload-change verdicts."""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path

from zip_content_diff.core import compare


def write(path, entries, year, compression):
    with zipfile.ZipFile(path, "w") as archive:
        for name, contents in entries:
            info = zipfile.ZipInfo(name, (year, 1, 1, 0, 0, 0))
            info.compress_type = compression
            archive.writestr(info, contents)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="zip-content-diff-demo-") as directory:
        root = Path(directory)
        entries = [("readme.txt", b"release notes"), ("app.txt", b"version one")]
        write(root / "a.zip", entries, 2020, zipfile.ZIP_STORED)
        write(root / "b.zip", list(reversed(entries)), 2021, zipfile.ZIP_DEFLATED)
        write(
            root / "c.zip",
            [("readme.txt", b"release notes"), ("app.txt", b"version two")],
            2021,
            zipfile.ZIP_DEFLATED,
        )
        metadata = compare(root / "a.zip", root / "b.zip")
        content = compare(root / "b.zip", root / "c.zip")
        assert metadata["payload_equal"] and not metadata["byte_equal"]
        assert metadata["member_order_changed"]
        assert not content["payload_equal"] and content["changed"][0]["name"] == "app.txt"
        print(
            json.dumps(
                {"metadata_only_detected": True, "changed_member": "app.txt"}, sort_keys=True
            )
        )


if __name__ == "__main__":
    main()
