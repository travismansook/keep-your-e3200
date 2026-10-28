# Platform plans

[← Back](../README.md)

| Platform | Combined helper status |
| --- | --- |
| Apple Silicon Mac, macOS 15+ | First native download; reusable release has offline/build checks, with original-network evidence documented separately. |
| Intel Mac, macOS 15+ | Native download/build validation; live Ethernet DHCP testing remains needed. |
| Windows | Planned later. Requires Windows-specific capture, reply delivery, privilege and lifecycle work. |
| Linux computers | Planned later. Requires Linux networking implementation and live testing. |
| Raspberry Pi | Planned as part of Linux support. Both Wi-Fi and Ethernet, privileges, restart recovery and power-loss behavior must be validated. |

My earlier [compatibility-only project](https://github.com/travismansook/e3200-dhcp-helper) has Windows/Linux workflows. Those do not yet implement this project's general Ethernet DHCP forwarder. Reusing its user interface or configuration approach will not by itself establish working combined support.

For future always-on support, I plan to include start/stop controls, startup after reboot, safe duplicate-instance handling, clean shutdown, and documented acquisition/renewal/restart tests. No delivery date or support guarantee is implied.
