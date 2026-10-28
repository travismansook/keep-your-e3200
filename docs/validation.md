# What has actually been tested?

[← Back](../README.md)

## Original network observations

The project comes from a CHR30A and E3200 hardware 1103, firmware 3.8.0.3, joined over coax. Earlier logs showed the extender rejecting a router offer for missing vendor class information; supplying option 60 alone exposed a second rejection for missing option 125. With both compatibility fields, the original prototype obtained an accepted lease and restored its settings page. The yellow-light cycle cleared during the observed trial. That is evidence for this DHCP-related condition, not every yellow light.

For the later wired-client issue, native DHCP requests were observed on downstream Ethernet but not on a simultaneous Wi-Fi capture or in the CHR30A server log at corresponding times. Those observations do not pinpoint the exact internal dropping component.

With the original Mac-based forwarding workaround:

- A Mac USB Ethernet client obtained a real CHR30A-issued IPv4 address using DHCP.
- A manually triggered Mac renewal received a matching CHR30A acknowledgement; the user confirmed internet still worked.
- A Stream TV USB Ethernet client obtained a matching CHR30A acknowledgement, and the user confirmed website access with TV Wi-Fi off.
- Direct IPv4 checks over Mac Ethernet succeeded, including the previously failing Speedtest page.

The original forwarder required no per-client entries. The successful manual renewal does not independently prove a natural timed renewal exercised the nonzero-`ciaddr` conversion path. Private addresses, device identities and raw logs are intentionally not published.

## Reusable release checks

The public release replaces personal interface names, device identities and addresses with validated settings and a guided setup. Those configuration changes and the native downloadable executables need field validation independently of the earlier personal launcher.

Offline tests cover DHCP identity/transaction preservation, the configured extender's exclusion, detector exclusion, real-server matching, unsolicited/mismatched responses, expiry/duplicates, renewal conversion, malformed input, checksums, VLAN parsing and client-MAC matching. Configuration tests cover address-plan validation, duplicate fields, ownership/symlink rules, both connection roles and changed networks. Lifecycle tests use inert child processes and non-elevating shims.

Native builds compile the included engine and run source/frozen `--self-test` checks. These parse configurations and compile capture filters. CI does not start a DHCP listener, transmit real DHCP packets, or change network settings.

## Not established by these checks

- E3200 operation with a G3100, including a wireless connection to that router instead of coax; this combination has not been tested by this project.
- Universal compatibility, every wired client, unusual VLANs or enterprise networks.
- The newly generalized download's live acquisition and renewal on both Mac architectures.
- Natural timed renewal/rebinding across a long observation window.
- Reliable reacquisition after extender power loss or host restart.
- Multi-day operation or automatic service startup after host reboot.
- Windows, Linux or Raspberry Pi operation of this combined forwarder.
- Full Verizon-supported SON/mesh integration or an internal firmware repair.

For a new real setup, confirm E3200 lease acceptance, fresh wired-client acquisition, renewal, controlled restart/reacquisition, stable Wi-Fi/coax, clean shutdown, and normal DHCP for unrelated devices. Do not treat READY, a passing build or a single working web page as all of those acceptance checks.
