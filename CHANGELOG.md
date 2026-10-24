# Changelog

## 0.1.0 — 2026-10-24

- Compare every member by exact name, kind, byte size and streamed SHA-256, with CRC checks.
- Separate payload changes from timestamps, compression, attributes, comments and order.
- Support strict byte comparison, deterministic JSON and explicit size/ratio/time limits.
- Reject duplicate/encrypted/unsupported/corrupt entries; never extract or execute members.
- Check archive/member time-budget failures with a controlled test clock on all platforms.

Supported scope and current limits are documented in README.md.
