# Why this project exists

[← Back](../README.md)

The starting point was simple: keep an existing E3200 after upgrading the main router to a CHR30A. Replacing working equipment should not be the first assumption when there is a specific interoperability failure to understand.

Device logs showed the extender rejecting address offers that lacked compatibility information. A narrowly scoped responder addressed that first problem. A second investigation then found that wired clients behind the extender could have IPv6 while IPv4 address requests failed. Capturing both paths and comparing router logs led to the combined transport workaround.

The result is a guided Mac launcher with two coordinated components, private configuration, bounded forwarding state, readiness checks and managed shutdown. The everyday instructions explain symptoms and actions; the protocol and implementation details live separately.

The engineering work includes packet-level diagnosis, separation of two DHCP roles, preserving the real router as ordinary clients' address authority, lifecycle supervision, reusable configuration validation, native packaging, privacy-conscious examples and explicit validation limits.

The original personal setup produced working results for a Mac and Stream TV. Reusable packaging and offline tests make the investigation easier to share; they do not turn it into a universally verified product. Windows, Linux and low-power dedicated hosting are future work.
