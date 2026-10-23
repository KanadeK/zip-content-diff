# Report v1

The `--json` output schema is `zip-content-diff/v1`. Lists are sorted by exact decoded member
name, metadata field lists are sorted, and JSON keys are sorted. Output has no clock value or
input absolute paths. The same stable inputs and policy therefore produce the same JSON bytes.

`changed` includes member hashes and kinds on both sides. A symlink-to-file change counts as a
payload change even when target bytes and regular file contents happen to match. Permission bits
remain metadata and can still be significant. `unchanged_payload_members` includes common members
whose payloads match, including members with metadata drift.

Tracked fields: timestamp, compression, compressed byte size, external/internal attributes,
creator system/version, extraction version, flags, and hashes of extra fields/member comments.
Archive comment and common-member ordering are compared separately. Raw archive differences not
explained by this set are explicitly reported. No claim of a complete ZIP specification audit is made.
