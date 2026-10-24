# zip-content-diff

Explain why two ZIP releases differ: changed payload bytes, or container metadata.

The CLI reads every member in bounded chunks and compares SHA-256 digests. It reports added,
removed and changed members separately from timestamps, compression, attributes, comments and order.
It works with ordinary ZIP files and ZIP-based wheels/JARs without extracting or executing them.

[中文说明](README.zh-CN.md) · [Report contract](docs/report.md) · [Contributing](CONTRIBUTING.md)

## Install and try

Requires Python 3.11+. Runtime dependencies: none.

```console
git clone https://github.com/KanadeK/zip-content-diff.git
cd zip-content-diff
python -m venv .venv
```

Activate it (`.venv\Scripts\Activate.ps1` in PowerShell, `source .venv/bin/activate` on POSIX), then:

```console
python -m pip install .
zip-content-diff --version
python scripts/demo.py
zip-content-diff old-release.zip new-release.zip --json
zip-content-diff old-release.zip new-release.zip --strict
```

The demo creates synthetic ZIPs in a temporary directory, proves timestamp/compression/order drift
has identical payloads, then changes a member and proves the content difference is detected.
No server, external data or native archive utility is required.

Default exit code is `0` for equal member names, kinds and content, even if archive bytes differ.
It is `1` for a payload difference. `--strict` returns `1` for **any byte difference**.
Errors/invalid or over-budget archives return `2`; interruption returns `130`.
For release reproducibility, use `--strict`: permission and other metadata changes can matter.

## What the result means

- `byte_equal`: whole-file SHA-256 and length match.
- `payload_equal`: member names, member kinds and decompressed SHA-256/length match.
- `metadata_changes`: common-member names and differing metadata **field names**.
- `member_order_changed` / `archive_comment_changed`: container-level differences.
- `unclassified_container_change`: bytes differ while payload and tracked metadata match;
  unmodeled local headers, padding or container details may explain this. It is not declared identical.

Symlinks are compared as symlink entries with target bytes; they are never followed. Directories
are entries too: an explicit empty directory present on only one side is an added/removed member.
Names are compared exactly, with no case folding or path normalization. Duplicate names and
NUL-truncated names are rejected rather than silently merged. CRC checks are performed by Python
while all member data is read, in addition to SHA-256 comparisons.

Reports contain member names and hashes, but no file contents or input filesystem paths.
Names/hashes can still be sensitive. No output file is created: redirect stdout if a saved report
is wanted, taking care not to redirect into either input archive. Console names use JSON escaping
to avoid raw terminal control characters. No network calls or telemetry are implemented.

## Resource policy

| Default, per archive | Limit |
|---|---:|
| Compressed archive bytes | 64 MiB |
| Entries | 10,000 |
| Individual decompressed member | 64 MiB |
| Total decompressed member bytes | 256 MiB |
| Member expansion ratio | 1,000 |
| Cooperative processing time | 30 seconds |

Each can be set through `--max-archive-bytes`, `--max-entries`, `--max-member-bytes`,
`--max-total-bytes`, `--max-ratio`, and `--timeout-seconds`. Advertised sizes are checked before
decompression and actual bytes are checked while streaming. Only STORE and DEFLATE are supported;
encrypted and other compression methods return an error. Both archives are fully inspected even
when their raw hashes match, so corruption or policy violations are not bypassed.

Python's ZIP reader loads the central directory before the entry-count check. The archive-byte cap
limits that input, but this is not an OS memory/CPU sandbox; cooperative timing cannot interrupt a
single blocking filesystem or decompressor call. Use resource isolation for hostile inputs. Keep
files stable while comparing. Embedded/nested archives are compared as member bytes, not recursed.
This is not an authenticity, signature, malware, safe-extraction or package-installability check.

## Alternatives, testing and cleanup

[zipcmp](https://libzip.org/documentation/zipcmp/) is a mature native comparator with CRC and metadata
options. [diffoscope](https://diffoscope.org/) offers much deeper format-specific analysis. Prefer
those when their capabilities fit. This project focuses on a portable Python CLI, full member
SHA-256 verification, deterministic JSON, and explicit resource policies.

See [CONTRIBUTING.md](CONTRIBUTING.md) for runnable quality/build/clean-install checks and
[SECURITY.md](SECURITY.md) for reporting. Uninstall with `python -m pip uninstall zip-content-diff`.
The demo cleans its temporary files; the tool creates no cache or global state. MIT © 2026 KanadeK.
