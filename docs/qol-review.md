# Launcher quality-of-life review — v0.3.0

This review covers the launcher experience, not a new live-network certification.

## Paths reviewed

- First launch, returning launch, and both connection modes.
- All setup questions, defaults, help, cancellation and saved-profile reuse.
- Home, Settings, review, lease confirmation, full setup, Back and Quit.
- Startup checks, password guidance, failure recovery, running status, disconnect/wait/resume, Ctrl+C and shutdown messages.
- Saved-file errors and interrupted or failed writes, plus log visibility and location guidance.
- Text layout on ordinary and narrower terminals.

## Changes from the review

- Setup accepts cancel at each question without replacing saved values.
- Mode selection offers Back to configured users; first-time users can cancel.
- Full setup preserves the existing lease and suggests the matching adapter.
- Home includes Help with connection checks, shortcuts and the log location.
- Setup/startup failures offer Retry, Home or Quit instead of always closing.
- Unreadable profiles offer deliberate reconfiguration or Quit; the old file is retained until successful setup.
- Section dividers fit narrower terminals.
- Password guidance explains invisible typing; startup and error wording now match the Home/reconnect behavior.

The previous improvements remain: review waits for Return, lease edits require yes/no confirmation, feedback stays visible, saved-file replacement is atomic, and the full compact technical logs remain visible.

## Verification and limits

All 62 automated checks passed for this build. Targeted navigation, cancellation, persistence and failure tests are included in tests/test_qol.py, alongside the existing input, settings and lifecycle checks. Both packaged source modes receive offline startup checks. Packaging is inspected for the current version and sources. The release workflow requires source and frozen offline startup checks on native Apple Silicon and Intel runners before publishing. Broader live-network testing remains separate. No live DHCP services, VPN changes, sleep/wake trials or long-running network trials were started for this review.

Deliberate boundaries: Home stops this helper; there is no background Home mode. Setup cancellation exits the current wizard rather than stepping back through individual answers. Windows/Linux and autostart remain outside this Mac launcher change.
