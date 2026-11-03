# Keep Your E3200 v0.3.0 — Easier setup, settings and reconnection

Keep using your E3200 with a CHR30A, with clearer setup and easier day-to-day controls.

## What changed

- **Home and Settings:** review your saved setup, change only the E3200 lease duration, run full setup again, or find help and your log folder. Review stays visible until you press Return.
- **Confirmed lease changes:** see the current and proposed durations before saving. Yes/no confirmation accepts either letter case; cancel leaves your settings unchanged. Changes affect future offers after restarting the helper, not leases already accepted.
- **Ethernet reconnects:** in the recommended mode, a recoverable disconnect pauses forwarding and retries the same selected adapter automatically. E3200 compatibility stays running over Wi-Fi if it had already started. The waiting message explains recognition delays and what to try if reconnection fails.
- **Clearer setup:** required mode selection, LAN1 MAC sticker instructions, dotted/colon/hyphen MAC support, address-reservation help and error-specific guidance. Backspace cannot erase the question label.
- **Better navigation and recovery:** Ctrl+C stops this helper and returns Home; setup supports cancel; mode selection supports Back. Setup preserves the existing lease and matching adapter defaults. Errors offer Retry, Home or Quit, and saved settings use atomic replacement.
- **VPN guidance:** startup reminds you to disconnect a VPN on the helper Mac. A failed Wi-Fi test now explains possible VPN/timeout causes rather than claiming the Mac definitely has no IPv4 internet.

The full compact technical logs remain visible. The CHR30A still assigns ordinary devices' addresses and leases.

## Download and update

Choose **Keep-Your-E3200-macOS-AppleSilicon.zip** for an M-series Mac or **Keep-Your-E3200-macOS-Intel.zip** for an Intel Mac. Requires macOS 15+. Extract the ZIP and open its single **Keep Your E3200.command** file. Python and the DHCP engine are included.

Stop the older helper before opening the new one. Existing saved settings are reused; you do not need to delete them. Once configured, choose **Start helper**, **Settings**, **Quit**, or **Help and troubleshooting** from Home.

Both modes need home Wi-Fi with working IPv4. Recommended mode also uses Mac Ethernet. The E3200 still needs its coax connection to the CHR30A and the router's MoCA Expansion Module. Keep the helper window open while relying on it. **Home stops the helper; it does not run in the background there.**

## Checks and limits

62 automated checks cover configuration, terminal input, navigation, confirmation, cancellation, persistence, simulated reconnects, shutdown and DHCP packet handling. The release workflow builds both Mac architectures and requires source and frozen offline startup checks in both connection modes before publishing. These are not live-network acceptance tests.

My original workaround worked with my Mac and Stream TV. Broader live compatibility, natural timed renewal and multi-day operation still need field testing. Concurrent Mac VPN operation is not validated. This remains a community preview, not a firmware upgrade or Verizon-supported pairing. Windows, Linux and Raspberry Pi combined support remain planned.

The downloads are not notarized or signed with an Apple Developer identity. Modified dnsmasq corresponding source and licenses are embedded; export them with `--extract-source NEW_FOLDER`.

[Setup guide](https://github.com/travismansook/keep-your-e3200/blob/main/docs/setup.md) · [FAQ](https://github.com/travismansook/keep-your-e3200/blob/main/docs/faq.md) · [Validation](https://github.com/travismansook/keep-your-e3200/blob/main/docs/validation.md)
