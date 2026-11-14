# What has actually been tested?

[← Back](../README.md)

## What I observed on my network

My setup uses a CHR30A and an E3200 with hardware version 1103 and firmware 3.8.0.3, joined over coax. My earlier logs showed the extender rejecting a router offer for missing vendor class information; supplying option 60 alone exposed a second rejection for missing option 125. With both compatibility fields, my prototype obtained an accepted lease and restored access to the extender's settings page. My earlier backhaul log recorded 20 disconnect/reconnection cycles; later cycles repeated roughly every three minutes, with most disconnected intervals lasting 9–11 seconds. The yellow-light cycle cleared during the successful compatibility trial. That is evidence for this DHCP-related condition, not every yellow light.

When I investigated the later wired-client issue, I could see native DHCP requests on downstream Ethernet but not on a simultaneous Wi-Fi capture or in the CHR30A server log at corresponding times. Those observations do not pinpoint the exact internal dropping component.

With my original Mac-based forwarding workaround:

- My Mac USB Ethernet client obtained a real CHR30A-issued IPv4 address using DHCP.
- I manually renewed the Mac lease, received a matching CHR30A acknowledgement, and confirmed that internet access still worked.
- My Stream TV USB Ethernet client obtained a matching CHR30A acknowledgement, and I confirmed website access with its Wi-Fi off.
- Direct IPv4 checks over my Mac Ethernet connection succeeded, including the previously failing Speedtest page.

My original forwarder required no per-client entries. The successful manual renewal does not independently prove a natural timed renewal exercised the nonzero-`ciaddr` conversion path. I have kept my private addresses, device identities and raw logs out of this repository.

## Reusable release checks

To make the public release reusable, I replaced my personal interface names, device identities and addresses with validated settings and a guided setup. Those configuration changes and the native downloadable executables need field validation separately from my earlier personal launcher.

Offline tests cover DHCP identity/transaction preservation, the configured extender's exclusion, detector exclusion, real-server matching, unsolicited/mismatched responses, expiry/duplicates, renewal conversion, malformed input, checksums, VLAN parsing and client-MAC matching. Configuration tests cover address-plan validation, duplicate fields, ownership/symlink rules, both connection roles and changed networks. Lifecycle tests use inert child processes and non-elevating shims. Mode tests cover old-profile migration, Wi-Fi-only first setup with no Ethernet hardware, saved-setting reuse, switching back to full mode, network validation and the offered-lease summary. Both modes are checked for signal shutdown, component death and parent/terminal disappearance; Wi-Fi-only tests assert that no forwarder starts.

Native builds compile the included engine and run source/frozen `--self-test` checks in both modes. These parse configurations and compile capture filters. CI does not start a DHCP listener, transmit real DHCP packets, or change network settings.

## Not established by these checks

- E3200 operation with a G3100, including a wireless connection to that router instead of coax; I have not tested this combination.
- Universal compatibility, every wired client, unusual VLANs or enterprise networks.
- The newly generalized download's live acquisition and renewal on both Mac architectures.
- Natural timed renewal/rebinding across a long observation window.
- Reliable reacquisition after extender power loss or host restart.
- Multi-day operation or automatic service startup after host reboot.
- Windows operation of this combined forwarder. Linux/Pi now has a separate preview and [testing record](../linux/VALIDATION.md).
- Full Verizon-supported SON/mesh integration or an internal firmware repair.

For a new real setup, confirm E3200 lease acceptance, fresh wired-client acquisition, renewal, controlled restart/reacquisition, stable Wi-Fi/coax, clean shutdown, and normal DHCP for unrelated devices. Do not treat READY, a passing build or a single working web page as all of those acceptance checks.

The v0.2.0 mode menu and Wi-Fi-only packaging have offline/native startup validation; they have not been newly exercised on live hardware. The earlier Wi-Fi-side responder and Mac Wi-Fi IPv4 observations provide background evidence, not a new universal Wi-Fi-client test.

## v0.3.0 launcher and reconnect checks

The update adds 62 automated checks in total, including real-terminal input/navigation checks and inert-process reconnect/shutdown tests. The simulated reconnect tests confirm that the E3200 component retains its process while forwarding restarts, the selected adapter identity is checked, and shutdown remains responsive while waiting. Settings tests cover review pauses, yes/no confirmation, cancel, unchanged selections, atomic saving and simulated save failures. Recovery tests cover setup cancellation, Back, Help, damaged-profile handling, preserved defaults and Retry/Home choices.

Native release builds must pass source and frozen offline startup checks for both connection modes on Apple Silicon and Intel before publishing. These checks do not establish live DHCP or VPN compatibility. Home intentionally stops the helper. See the [launcher QoL review](qol-review.md) for the review scope.

## Linux and Raspberry Pi preview

The initial preview was installed on my Pi 4 Model B with 1 GB RAM. The isolated Linux DHCP OFFER/ACK/renewal test passed, and an actual Ethernet client with Wi-Fi off received IPv4 and internet access. These observations do not prove every client, a fresh extender compatibility lease, or long-term recovery. [Full Linux evidence and remaining checks →](../linux/VALIDATION.md)

The GitHub candidate uses the published Mac v0.3.0 baseline, with the Linux implementation and platform-specific forwarding branches added. Private Mac test-build changes are not part of this Linux release. Existing Mac downloads remain v0.3.0; the Linux preview has its own version and download. The [Linux GitHub checks](https://github.com/travismansook/keep-your-e3200/actions/runs/43567482692) passed 105 automated tests, built/inspected the package, verified checksums and passed the isolated Linux packet test on November 14. Real Pi recovery and fresh E3200 compatibility-lease checks remain separate. Public prerelease creation is an explicitly requested step after passing build checks.
