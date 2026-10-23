# Selection research

Research date: 2026-10-23. Public, bounded comparison; not a claim that no other similar tool exists.

### 2. ZIP release comparison

- **Problem/users:** maintainers see different release archive hashes and need to distinguish changed member bytes from timestamp, ordering, compression, and permission metadata changes.
- **Evidence:** [Reproducible Builds documentation](https://reproducible-builds.org/docs/archives/) describes archive metadata as a reproducibility source. The long-lived [zipcmp manual](https://libzip.org/documentation/zipcmp/) demonstrates established demand for comparing archives. [libzip changes](https://libzip.org/news/) record timestamp comparison as a real feature.
- **Alternatives:** `zipcmp` compares names, sizes and CRCs, with optional metadata checks; [diffoscope](https://diffoscope.org/) provides much deeper multi-format comparisons and should be preferred when available and needed. ZIP/Python comparison scripts also exist.
- **Improvement:** portable Python-only CLI, SHA-256 over every decompressed member rather than trusting CRC equality, deterministic JSON, metadata field names without dumping file contents, explicit byte-equality and payload-equality verdicts, and configurable entry/size/ratio budgets. Reject ambiguous duplicate names. Never extract.
- **Feasibility/maintenance:** standard-library `zipfile`; generated ZIP fixtures can vary one dimension at a time and corrupt CRCs. Does not promise recursive diffoscope-like inspection or a hardened sandbox for hostile archives.
