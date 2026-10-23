# Security

Version 0.1.x is the current development line. Security fixes take priority over new features.
Use only data you are authorized to process. Filesystem parents and the current machine must
be trusted; concurrent malicious file replacement is outside the tool's threat model.

Report a vulnerability privately through [GitHub private vulnerability reporting](https://github.com/KanadeK/zip-content-diff/security/advisories/new)
when enabled. If that form is unavailable, open an issue requesting a private contact without
including an exploit, secret, or private file. Do not post sensitive samples publicly.

The tool is local software, not an isolation sandbox. Review the README for size limits,
output contents and format-specific limitations. No telemetry is implemented.
