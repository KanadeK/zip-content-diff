# Requirements and design

## User and core scenario

Release maintainers need to tell payload drift from container metadata without extracting archives.

## Architecture

Bounded raw hash → ZIP directory policy checks → streamed CRC/SHA-256 member reads → exact-name/kind/payload comparison and independent metadata verdicts. All results are deterministic.

## Acceptance criteria

- Changed, added and removed member bytes produce a payload difference.
- Timestamp/order/compression drift remains separately visible when payload bytes match.
- Duplicate names, corruption, encryption, unsupported methods and exceeded budgets fail.
- No member is extracted/executed; unmodeled raw-byte changes are explicitly reported.

## Scope and maintenance

Python standard library; only STORE/DEFLATE. Central directory is loaded by zipfile; cooperative time/byte budgets are not a memory or CPU sandbox. No recursive/signature audit.

No server, database service, paid API, account credential or telemetry is required. CI only verifies/builds; it does not create source commits. See README for actual commands.
