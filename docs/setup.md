# Mac setup: open the helper and get started

[← Back](../README.md) · [FAQ](faq.md) · [Troubleshooting](troubleshooting.md)

**Using Linux or a Raspberry Pi?** Follow the [Linux/Pi setup guide](../linux/README.md). This page describes the Mac download.

## 1. Choose the executable download

Open [Releases](https://github.com/travismansook/keep-your-e3200/releases/latest). Download the ZIP matching your Mac:

- **Apple Silicon**: Macs with an Apple M-series chip.
- **Intel**: Macs with an Intel processor.

You can check your chip in **Apple menu → About This Mac**. Both downloads require macOS 15 or later.

Double-click the ZIP to extract **Keep Your E3200.command**. That is the program. It includes its runtime and DHCP engine; you do not need Python, Terminal commands, or a build environment. You can move the executable anywhere on your Mac, with no supporting folders next to it.

The **Source code** links GitHub adds automatically are for developers. Choose the named Mac ZIP above them instead.

## 2. Connect the equipment

**For coax, the main CHR30A router must have its MoCA Expansion Module installed.** It supplies the router's coax connection. Keep the E3200 connected back to it through your home's working coax wiring. [Verizon's module instructions →](https://www.verizon.com/support/residential/internet/equipment/routers/wi-fi-access-point)

The E3200 cannot connect wirelessly back to the CHR30A. It can still provide Wi-Fi to your devices, but this tested setup needs the coax connection between the extender and main router.

I have not tested an E3200 with a G3100, including a wireless connection back to that router instead of coax. These instructions describe my tested CHR30A setup.

On the helper Mac, connect to your normal **home Wi-Fi with working IPv4**. Then choose:

- **Wi-Fi + Ethernet — Recommended:** also plug the Mac's Ethernet cable directly into an Ethernet port on the E3200. Keep both connections available.
- **Wi-Fi only:** leave the Mac's Ethernet cable disconnected. Only the E3200 compatibility fix runs; automatic IPv4 for wired clients is not repaired by this mode.

The helper does not change the Mac's network order or settings. I kept Ethernet first in my full setup. A self-assigned `169.254…` Ethernet address is one symptom the recommended mode may help with. [Why the recommended mode uses both connections](faq.md#why-does-the-mac-need-wi-fi-and-ethernet-at-the-same-time)

## 3. Find the details the helper asks for

You can leave the helper window open while you check these details. It waits for your answers; there is no countdown.

| Question | What to enter | Where to find it |
| --- | --- | --- |
| **Ethernet connection** (recommended mode) | The number beside the Mac adapter connected to the E3200, such as `1`. | The launcher lists connected adapters. An address starting with `169.254` means that adapter has no usable IPv4 yet; you can still select it. |
| **Main CHR30A router address** | Your main router's local address, often `192.168.1.1`. | On the Mac: **Apple menu → System Settings → Wi-Fi → Details** beside your home network → **TCP/IP → Router**. Use the **Router** value, not the Mac's IP address. The launcher offers the detected value. |
| **E3200 LAN1 MAC** | The six pairs printed beside **LAN1 MAC:**, such as `02.00.00.00.00.AA`. | Check the sticker on the **back of the E3200**, just under **Serial#**. Copy the **LAN1 MAC** value. |
| **Address reserved for your E3200 settings page** | The address you reserve for **this E3200** using the steps below. Reuse an existing reservation for the same extender. | Your main router's address reservation list. This is the address you will open in a browser to reach the E3200 after it accepts its lease. |

Look on the rear sticker under **Serial#** for **LAN1 MAC:**. Enter only its address, without the words `LAN1 MAC:`. **Dots, colons and hyphens all work**, and letters can be uppercase or lowercase. For example, `02.00.00.00.00.AA` is automatically saved as `02:00:00:00:00:aa`. The example is only a format example; use the address on your own sticker. Do not use the serial number, a Wi-Fi radio MAC, or your Mac/USB adapter MAC. You do not need to open the E3200's own settings page to find it.

### Reserve an address for the E3200

A **reservation** tells your main router to keep a particular address for your extender. The helper needs that same address. It does not create the reservation or change your router settings for you.

1. In your browser, open the **main router address** from the table above, such as `https://192.168.1.1`. Sign in with your router's administrator password. Use your custom password if you changed it; otherwise check the router's administrator label. This may differ from your Wi-Fi password.
2. Go to **Network Settings → IPv4 Address Distribution → Connection List**. You may need to select **Advanced** first. Menu names can vary with the router software.
3. Look for the entry whose MAC address matches your **E3200**. If an address is already reserved for that exact device, reuse it. If the entry exists but is not reserved, edit that entry to make it a static connection. Avoid adding a second entry for the same device.
4. If there is no existing entry, choose **Add static connection**. A static connection is the router's name for an address reservation. Enter a name such as **E3200**, the E3200 MAC address, and an available address within the router's allowed range. Check its device/reservation list and any devices you configured manually so that the address is not in use elsewhere.
5. To see the allowed range, open the edit/settings entry on **IPv4 Address Distribution** and read **Start IP Address** and **End IP Address**. You do not need to change those values. For example, `192.168.1.250` could work on a `192.168.1.x` network **only if** it is allowed and available. It is not a universal default.
6. Click **Apply** or save. Return to the helper and enter that **same address** when it asks for the E3200 settings-page address.

**“IP address is not in the allowed DHCP range”?** Choose an available address within the allowed range you checked above. You do not need to expand the range just to copy the example.

**“IP address/name already exists”?** Check the existing entry and its MAC address. An existing reservation for your E3200 can be reused. An address belonging to another device cannot. Edit the matching entry instead of adding a duplicate.

If you already have an address excluded from automatic assignment specifically for this E3200, you can reuse that plan after checking that no other device uses the address. The beginner instructions above use a reservation.

Reference: [Verizon's CHR30A user guide](https://www.verizon.com/content/dam/support/pdf/CHR30A-wi-fi-access-point-user-guide.pdf), under **IPv4 address distribution / DHCP Connection List**. Keep your administrator password private.

## 4. Open and follow the questions

Double-click **Keep Your E3200.command**. It opens a Terminal window with a short setup flow:

**Type an answer, then press Return (Enter).** A value in **[brackets]** is the default: press Return without typing to accept it. For example, at `Main CHR30A router address [192.168.1.1]:`, press Return if that is your router. The cursor waiting beside a question means the helper is waiting for you; it is not stuck.

1. Choose a mode: type **1** for **Wi-Fi + Ethernet — Recommended**, or **2** for **Wi-Fi only**, then press Return. There is no default at this opening menu. Blank or invalid answers are rejected until you enter 1 or 2. Only the recommended mode asks you to choose the Ethernet connection leading to the E3200.
2. Confirm the detected router address.
3. Enter the **LAN1 MAC** from the rear sticker, then the settings-page address you reserved for it. The launcher shows instructions before both questions. At the address question, type **?** for the full reservation guide; it then returns to the same question.
4. Check the address and MAC shown together. Type **yes**, then press Return, only after you have saved the matching reservation or checked your existing exclusion. Uppercase and lowercase both work. Blank or unrecognized answers ask again; **no** cancels without changing saved settings or starting the helper.
5. Choose an E3200 lease length. **Start with one hour** so you can verify renewal. This is how long the extender keeps an accepted address before renewal; it does not shut the helper down after an hour. Other devices' lease lengths come from your main router.

The program saves your E3200 settings privately for reuse in either mode. After setup, Home offers **Start helper**, **Settings**, **Quit**, and **Help and troubleshooting**. Start helper opens the mode menu; type **1** or **2**, or **back** to return Home. During setup, **cancel** leaves without saving. If you first set up Wi-Fi only and later choose the recommended mode, setup asks for an Ethernet connection and offers your existing E3200 details as defaults. If administrator access is requested, enter your Mac's administrator password. Terminal does not show characters as you type a password; press Return afterward.

Before starting, **Your setup** lists the selected mode, E3200 IP/MAC, main router, DNS, Mac connections and **E3200 lease offered**. That lease length applies to the extender; ordinary devices' leases come from the main router. The configured offer is not proof of an accepted lease.

Wait for **READY**, which explicitly says either both helpers are running or Wi-Fi-only compatibility is running with the Ethernet IPv4 fix **OFF**.

**Using a VPN on the helper Mac? Disconnect it before startup.** A Mac VPN can block the direct Wi-Fi check or local router traffic. Keep it disconnected while relying on this workaround until your VPN configuration has been tested with the helper; reconnecting may interrupt it. The launcher shows this reminder on every run and does not change VPN settings. A failed check alone does not prove that your internet is offline.

Mac downloads are community builds: unsigned by an Apple Developer identity and not notarized. If macOS blocks the app, review the download's origin and use [Apple's instructions for opening an app from an unidentified developer](https://support.apple.com/en-us/102445). Do not disable Gatekeeper globally.

## 5. Check the result

- After the E3200 accepts its address, try opening **its chosen address** in your browser. A number displayed earlier is not proof it has accepted a current lease.
- **In the recommended mode**, leave an Ethernet device on **automatic/DHCP**. Reconnect or renew that device's Ethernet connection and look for a usable IPv4 address from the CHR30A, rather than only IPv6 or `169.254…`.
- **In the recommended mode**, try normal websites on that wired device. A successful app on Wi-Fi does not establish that its Ethernet path is working.
- Check renewal and later reconnection too; a single success is not a guarantee of long-term operation.

Leave the helper window open and the Mac awake while relying on this workaround. The managed helper keeps the Mac awake while running; reopen it after restarting the host. Keep home Wi-Fi connected in either mode, and the Mac Ethernet cable connected in the recommended mode. Host reboot recovery and multi-day operation of this public release still need field testing.

## Stop or change the setup

**Unplugged Ethernet while the recommended mode was running?** Leave the window open and keep home Wi-Fi connected. The launcher pauses the Ethernet component and retries every few seconds. Reconnect the same adapter and cable on the selected connection; it reopens the connections, checks delivery again and reports when forwarding resumes. The E3200 compatibility component stays running over Wi-Fi. A different adapter needs setup again. Reconnect behavior still needs testing across more adapters and networks.

**Home:** press Ctrl+C while the helper is running. It stops the helper before returning to Home; forwarding is paused there. Choose Start helper to resume, Settings to edit, or Quit to close.

**Stop:** press Ctrl+C in the helper's window. Everything started by the selected mode stops together. The same executable also has a `--stop` option for troubleshooting.

**Change saved choices:** stop the helper with Ctrl+C, then reopen it. After first-time setup, the main menu offers **Start helper**, **Settings**, **Quit**, and **Help and troubleshooting**. Settings lets you review the saved setup, change only the E3200 lease duration, or run full setup again. A lease change applies to future offers after restarting; it does not immediately change an already accepted lease. Review stays visible until you press Return. A lease change shows the current and proposed durations and asks for yes/no confirmation before saving. Cancel or no keeps the existing duration; save/cancel feedback also waits for Return. Failed saves retain the previous profile. The `--setup` and `--settings` options are also available in Terminal.

Logs and the private profile are in `~/Library/Application Support/E3200 CHR30A Helper`. Temporary runtime files are cleaned after a normal stop. A force-killed process can leave files in macOS's temporary area; its supervisor is designed to stop everything started by the selected mode when the parent disappears.

Stop the earlier compatibility-only helper before using this combined version. Do not run duplicate DHCP helpers.
