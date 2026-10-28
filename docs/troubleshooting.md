# When something does not work

[← Back](../README.md) · [Setup](setup.md) · [FAQ](faq.md)

| What you see | What to try |
| --- | --- |
| macOS blocks the downloaded program | Confirm you downloaded it from this repo's Release, then follow the Apple app-opening link in the setup guide. The builds are not notarized. |
| No Ethernet connection is offered in setup | Reconnect the Mac's adapter and cable directly to an Ethernet port on the E3200. Check the link lights. A software helper cannot repair a missing physical link. |
| “Connect the Mac to your home Wi-Fi as well as Ethernet” | Enable the Mac's Wi-Fi and join the home network. Both paths are required. |
| “The Wi-Fi network differs from setup” | Reconnect to the home network used during setup. If you intentionally changed that network, run `--setup` again. |
| Another helper is already active | Stop the other helper's Terminal window with Ctrl+C first. Do not start another DHCP service alongside it. |
| The adapter changed | Reconnect the selected adapter, or run `--setup` to choose a new one. Interface numbers and adapter identities can differ across Macs. |
| The E3200 turns yellow and connected devices lose internet access | Check the actual coax/Ethernet connection, chosen MAC and address plan. Wait for evidence of accepted DHCP, not merely an old displayed address. Other yellow-light causes are outside this workaround. |
| The E3200 page does not open | Use the address you chose for the extender, not the Mac's address. Confirm a recent accepted lease and check the router/device logs. |
| A wired device still has only IPv6 or `169.254…` | Confirm the helper reached READY, the device is using DHCP, and its cable is connected to an Ethernet port on the E3200. Reconnect that device or renew its lease. Avoid changing all devices to manual addresses. |
| It worked until the Mac slept, restarted, or the window closed | Reopen the helper and verify both Mac connections. Existing leases can mask that the helper is unavailable until a later request. |

## What READY means

The local forwarding/interface check passed and both components started. It does **not** prove that your particular extender has accepted a lease or that every client works. Verify acquisition, renewal and reconnection on your own equipment.

## Asking for help

Use the issue template and share your router/extender models, Mac chip/macOS version, release version, which connections are in use, and the exact symptom. Remove real IP/MAC addresses, passwords, serial numbers and other private information from logs or screenshots before posting them.

The helper does not automatically change your router pool, reservations, DNS configuration or network priority. It should not be used to mask a physical network fault. The public combined release is a preview; more live testing is needed.
