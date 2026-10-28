# Keep Your E3200 v0.1.1 — Mac preview

A ready-to-open combined helper for two DHCP-related problems when keeping a Verizon E3200 behind a CHR30A: the extender's compatibility/yellow-light condition and wired clients missing automatic IPv4.

This update simplifies the setup wording: connect directly to the E3200. A network switch is optional, and the FAQ explains why I used a gigabit switch in my own setup. The address-forwarding behavior is unchanged.

## Download and open

Choose **Keep-Your-E3200-macOS-AppleSilicon.zip** for an M-series Mac, or **Keep-Your-E3200-macOS-Intel.zip** for an Intel Mac. Requires macOS 15+.

Unzip and open **Keep Your E3200.command**. It is one executable with its runtime included: no building, Python installation or code editing. Connect the Mac to home Wi-Fi and plug its Ethernet cable directly into an Ethernet port on the E3200, then follow the setup questions. Check the extender's chosen address on the router first. Keep the host awake and leave the window open; Ctrl+C stops both components.

[Setup guide](https://github.com/travismansook/e3200-chr30a-helper/blob/main/docs/setup.md) · [FAQ](https://github.com/travismansook/e3200-chr30a-helper/blob/main/docs/faq.md) · [Behind the scenes](https://github.com/travismansook/e3200-chr30a-helper/blob/main/docs/behind-the-scenes.md)

## What to expect

- Guided first-run setup and private saved settings.
- One E3200-specific compatibility response on Wi-Fi.
- General Ethernet DHCP forwarding; ordinary addresses still come from the CHR30A.
- Both components start/stop together; integrity checks and parent monitoring.
- No supporting files beside the movable executable. Private logs/leases use Application Support.
- Complete modified dnsmasq corresponding source and license notices included; export with `--extract-source NEW_FOLDER`.

Community preview: unsigned by an Apple Developer identity and not notarized. See the setup guide for Apple's app-opening instructions. Offline/native build tests are separate from live network validation. The original workaround worked with my Mac and Stream TV; this generalized release needs more field testing. It is not a firmware upgrade, a fix for every yellow light, or a vendor-supported pairing.

**Windows, Linux and Raspberry Pi combined support are planned for later.** Those downloads are not included here. GitHub's automatic Source code links are for developers; end users should choose a named Mac ZIP above.
