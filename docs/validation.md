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

Offline tests cover DHCP identity/transaction preservation, the configured extender's exclusion, detector exclusion, real-server matching, unsolicited/mismatched responses, expiry/duplicates, renewal conversion, malformed input, checksums, VLAN parsing and client-MAC matching. Configuration tests cover address-plan validation, duplicate fields, ownership/symlink rules, both connection roles and changed networks. Lifecycle tests use inert child processes and non-elevating shims.

Native builds compile the included engine and run source/frozen `--self-test` checks. These parse configurations and compile capture filters. CI does not start a DHCP listener, transmit real DHCP packets, or change network settings.

## Not established by these checks

- E3200 operation with a G3100, including a wireless connection to that router instead of coax; I have not tested this combination.
- Universal compatibility, every wired client, unusual VLANs or enterprise networks.
- The newly generalized download's live acquisition and renewal on both Mac architectures.
- Natural timed renewal/rebinding across a long observation window.
- Reliable reacquisition after extender power loss or host restart.
- Multi-day operation or automatic service startup after host reboot.
- Windows, Linux or Raspberry Pi operation of this combined forwarder.
- Full Verizon-supported SON/mesh integration or an internal firmware repair.

For a new real setup, confirm E3200 lease acceptance, fresh wired-client acquisition, renewal, controlled restart/reacquisition, stable Wi-Fi/coax, clean shutdown, and normal DHCP for unrelated devices. Do not treat READY, a passing build or a single working web page as all of those acceptance checks.
