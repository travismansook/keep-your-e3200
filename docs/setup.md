# Open the helper and get started

[← Back](../README.md) · [FAQ](faq.md) · [Troubleshooting](troubleshooting.md)

## 1. Choose the executable download

Open [Releases](https://github.com/travismansook/e3200-chr30a-helper/releases/latest). Download the ZIP matching your Mac:

- **Apple Silicon**: Macs with an Apple M-series chip.
- **Intel**: Macs with an Intel processor.

You can check your chip in **Apple menu → About This Mac**. Both downloads require macOS 15 or later.

Double-click the ZIP to extract **Keep Your E3200.command**. That is the program. It includes its runtime and DHCP engine; you do not need Python, Terminal commands, or a build environment. You can move the executable anywhere on your Mac, with no supporting folders next to it.

The **Source code** links GitHub adds automatically are for developers. Choose the named Mac ZIP above them instead.

## 2. Connect the equipment

**For coax, the main CHR30A router must have its MoCA Expansion Module installed.** It supplies the router's coax connection. Keep the E3200 connected back to it through your home's working coax wiring. [Verizon's module instructions →](https://www.verizon.com/support/residential/internet/equipment/routers/wi-fi-access-point)

The E3200 cannot connect wirelessly back to the CHR30A. It can still provide Wi-Fi to your devices, but this tested setup needs the coax connection between the extender and main router.

I have not tested an E3200 with a G3100, including a wireless connection back to that router instead of coax. These instructions describe my tested CHR30A setup.

On the helper Mac:

1. Connect **Wi-Fi** to your normal home network.
2. Plug an **Ethernet cable** from the Mac's Ethernet port or adapter directly into an Ethernet port on the E3200.
3. Keep both connections available. The helper does not change the Mac's network order or settings; I kept Ethernet first in my working setup.

An Ethernet connection showing a self-assigned `169.254…` address is one symptom this workaround may help with. The Mac's Wi-Fi must already have working IPv4 and be on your home network. [Why both are needed](faq.md#why-does-the-mac-need-wi-fi-and-ethernet-at-the-same-time)

## 3. Have two E3200 details ready

**The extender's MAC address:** the six pairs printed on its label or shown on its settings page. Enter the E3200 identity, not the address of your Mac, USB adapter, or second router.

**An address protected for that extender:** choose an unused local IPv4 address on your router's network. Check the router's device list, reservations, automatic DHCP range, and any manually assigned devices. Reserve the address for the E3200 or exclude it from ordinary automatic assignment. This helper does not change the router for you.

For example, a home with router `192.168.1.1` and subnet mask `255.255.255.0` might set aside `192.168.1.250` for the extender. **That is an example, not an address everyone should copy.** Your router's allowed reservation range may differ. Do not reuse an address already assigned to your Mac or another device.

If you need to open the CHR30A, use its usual settings address on your network and your own administrator credentials. Do not paste passwords or device details into a public GitHub issue.

## 4. Open and follow the questions

Double-click **Keep Your E3200.command**. It opens a Terminal window with a short setup flow:

1. Choose the Ethernet connection leading to your E3200.
2. Confirm the detected router address.
3. Enter the E3200 MAC address and the unused address you protected.
4. Confirm you checked the address plan.
5. Choose an E3200 lease length. **Start with one hour** so you can verify renewal.

The program saves these choices privately, so the next launch can reuse them. If administrator access is requested, enter your Mac's administrator password. Terminal does not show characters as you type a password; press Return afterward.

Wait for:

```text
READY: E3200 and Ethernet helpers are running. Ctrl+C stops both.
```

Mac downloads are community builds: unsigned by an Apple Developer identity and not notarized. If macOS blocks the app, review the download's origin and use [Apple's instructions for opening an app from an unidentified developer](https://support.apple.com/en-us/102445). Do not disable Gatekeeper globally.

## 5. Check the result

- After the E3200 accepts its address, try opening **its chosen address** in your browser. A number displayed earlier is not proof it has accepted a current lease.
- Leave an Ethernet device on **automatic/DHCP**. Reconnect or renew that device's Ethernet connection and look for a usable IPv4 address from the CHR30A, rather than only IPv6 or `169.254…`.
- Try normal websites on that wired device. A successful app on Wi-Fi does not establish that its Ethernet path is working.
- Check renewal and later reconnection too; a single success is not a guarantee of long-term operation.

Leave the helper window open and the Mac awake while relying on this workaround. The managed helper keeps the Mac awake while running; reopen it after restarting the host. Host reboot recovery and multi-day operation of this public release still need field testing.

## Stop or change the setup

**Stop:** press Ctrl+C in the helper's window. Both components stop together. The same executable also has a `--stop` option for troubleshooting.

**Change saved choices:** open Terminal, drag the executable into it to insert its path, add a space and `--setup`, then press Return. This opens the guided setup again; no code editing is needed.

Logs and the private profile are in `~/Library/Application Support/E3200 CHR30A Helper`. Temporary runtime files are cleaned after a normal stop. A force-killed process can leave files in macOS's temporary area; its supervisor is designed to stop both components when the parent disappears.

Stop the earlier compatibility-only helper before using this combined version. Do not run duplicate DHCP helpers.
