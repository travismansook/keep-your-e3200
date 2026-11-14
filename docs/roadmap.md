# Platforms and next steps

[← Back](../README.md)

| Platform | Combined helper status |
| --- | --- |
| Apple Silicon Mac, macOS 15+ | First native download; reusable release has offline/build checks, with original-network evidence documented separately. |
| Intel Mac, macOS 15+ | Native download/build validation; live Ethernet DHCP testing remains needed. |
| Windows | Planned later. Requires Windows-specific capture, reply delivery, privilege and lifecycle work. |
| Linux computers | Preview for compatible 64-bit Debian-based systems with NetworkManager and systemd. Ready-made .deb; broader Linux hardware/distro testing remains needed. |
| Raspberry Pi | Included in that Linux preview. Initial Pi 4 Model B / 1 GB installation, isolated packet delivery and live Ethernet-client internet access were checked. The new build and recovery checks remain pending. |

This is the current project for the combined workaround. My earlier [E3200 DHCP Helper](https://github.com/travismansook/e3200-dhcp-helper) records the original compatibility-only investigation; it is linked as project history. Current Mac and Linux/Pi downloads are provided here.

The Linux preview includes start/stop controls, optional boot startup, a live log viewer and automatic recovery logic. Before a stable release, I still need to verify the updated package on the Pi, a fresh E3200 compatibility lease, live client renewal, cable/Wi-Fi recovery, reboot startup, upgrades and longer operation. [Testing record →](../linux/VALIDATION.md)

Other Linux package formats, more hardware coverage, Windows support and an optional signed apt update repository can come later. The .deb installer already supports application updates without compiling or reflashing the Pi. No delivery date or universal compatibility claim is implied.
