from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core import ArchiveError, Limits, compare


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare ZIP member bytes and explain metadata drift"
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument("--json", action="store_true", help="Deterministic machine-readable output")
    parser.add_argument("--strict", action="store_true", help="Fail on any archive byte difference")
    defaults = Limits()
    for name in ("max_archive_bytes", "max_entries", "max_member_bytes", "max_total_bytes"):
        parser.add_argument(
            "--" + name.replace("_", "-"), type=int, default=getattr(defaults, name)
        )
    parser.add_argument("--max-ratio", type=float, default=defaults.max_ratio)
    parser.add_argument("--timeout-seconds", type=float, default=defaults.timeout_seconds)
    args = parser.parse_args(argv)
    try:
        policy = Limits(**{key: getattr(args, key) for key in defaults.__dataclass_fields__})
        result = compare(args.left, args.right, policy)
        if args.json:
            print(json.dumps(result, sort_keys=True))
        else:
            print(
                f"Payload equal: {result['payload_equal']}; "
                f"archive bytes equal: {result['byte_equal']}"
            )
            for key in ("added", "removed", "changed", "metadata_changes"):
                for entry in result[key]:
                    print(f"{key}: {json.dumps(entry, sort_keys=True)}")
            for key in (
                "member_order_changed",
                "archive_comment_changed",
                "unclassified_container_change",
            ):
                if result[key]:
                    print(key)
        return int(not result["byte_equal" if args.strict else "payload_equal"])
    except ArchiveError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    except OSError:
        print('{"error": "input_io_error"}', file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print('{"error": "interrupted"}', file=sys.stderr)
        return 130
