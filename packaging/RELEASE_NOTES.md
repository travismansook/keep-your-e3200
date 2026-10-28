# Keep Your E3200 v0.2.0 — Choose your connection mode

The Mac launcher now lets you choose how to run it:

- **Wi-Fi + Ethernet — Recommended:** E3200 compatibility and automatic IPv4 forwarding for wired devices. Press Return to select this default.
- **Wi-Fi only:** E3200 compatibility without a Mac Ethernet cable. The Ethernet IPv4 fix is explicitly OFF.

Both modes still require the E3200's coax connection to the CHR30A. The main router needs its MoCA Expansion Module. Ordinary devices still get their addresses and lease lengths from the main router.

## Your setup, at a glance

Before startup, the launcher lists the mode, E3200 IP/MAC, router, DNS, connections, offered E3200 lease duration and run time. The configured offer is separate from proof that the extender accepted its lease.

Existing E3200 settings are reusable in either mode. A Wi-Fi-first setup asks for an Ethernet adapter only when you later choose the recommended mode. The mode menu appears on each interactive launch; Ctrl+C stops everything started by the chosen mode.

## Download

Choose **Keep-Your-E3200-macOS-AppleSilicon.zip** for an M-series Mac or **Keep-Your-E3200-macOS-Intel.zip** for an Intel Mac. Requires macOS 15+. Each ZIP contains one **Keep Your E3200.command** executable with Python and the DHCP engine included. No building or Python installation is needed.

[Setup guide](https://github.com/travismansook/e3200-chr30a-helper/blob/main/docs/setup.md) · [FAQ](https://github.com/travismansook/e3200-chr30a-helper/blob/main/docs/faq.md) · [Validation](https://github.com/travismansook/e3200-chr30a-helper/blob/main/docs/validation.md)

Keep the host awake and connected for the selected mode. Community preview: these builds are not notarized or signed with an Apple Developer identity. See the setup guide for Apple's app-opening instructions. Complete modified dnsmasq corresponding source and licenses are embedded; export them with `--extract-source NEW_FOLDER`.

The original workaround worked with my Mac and Stream TV. This release checks both modes offline and starts neither live DHCP nor packet capture in CI. The new menu and Wi-Fi-only packaging still need live field testing. This is not a firmware upgrade, a fix for every yellow light or a vendor-supported pairing. Windows, Linux and Raspberry Pi combined support remain planned.
