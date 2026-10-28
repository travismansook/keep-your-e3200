<p align="center"><img src="assets/banner.svg" width="100%" alt="Keep Your E3200 — new CHR30A router, same E3200 extender"></p>

<p align="center">
  <a href="https://github.com/travismansook/keep-your-e3200/releases/latest"><strong>Download for Mac</strong></a>
  &nbsp; · &nbsp; <a href="docs/setup.md">Getting started</a>
  &nbsp; · &nbsp; <a href="docs/faq.md">FAQ</a>
  &nbsp; · &nbsp; <a href="docs/behind-the-scenes.md">Behind the scenes</a>
</p>

# Keep Your E3200

**Switched to a Verizon CHR30A? Keep your E3200—and get its wired devices online again.**

## Why keep it?

**Your old E3200 can become an extra Wi-Fi coverage point after your router upgrade.** Put it to work in another room, keep its Ethernet ports useful, and get more use out of hardware you already have.

That is a big part of why I wanted to keep mine. If Verizon replaces your old extender with **another CHR30A acting as an access point at no extra charge** and lets you keep the E3200, you can use the replacement **and** put the retained E3200 back to work as an additional extender. Confirm replacement costs and whether you can keep the old equipment with Verizon for your account.

## Why I needed a helper

I started this project after upgrading my main router from a **CR1000A to a CHR30A**. I wanted to keep using my **E3200 extender connected over coax**, but the equipment no longer worked together as expected.

My E3200 cycled through a yellow-light problem. **When it turned yellow, it lost its internet connection, causing devices connected through it to disconnect.** My earlier logs showed the recovery cycle repeating roughly every **three minutes**, with most interruptions lasting **9–11 seconds**. I couldn’t access the E3200’s network settings page at its IP address. Later, devices connected by Ethernet through the extender could get IPv6 but missed the IPv4 address they needed—so some sites worked and others failed.

**One helper addresses both problems:**

- **Keep the E3200 connected and access its settings again.** The compatibility fix addresses the yellow-light disconnect cycle I experienced. Once the extender accepts its IPv4 address, you can open its network settings page at the address you chose during setup.
- **Get Ethernet devices online automatically.** The Ethernet fix helps devices plugged into the E3200 receive an IPv4 address from the main router, so you do not have to enter an address manually on each device.

## Two problems. One helper.

| What you notice | What the helper does |
| --- | --- |
| **The E3200 turns yellow and loses internet access, causing disconnects, or its settings page will not open** because it rejects the router's address offer. | Gives the E3200 an address offer with the compatibility information it expects, restoring access to its network settings page at its accepted IPv4 address. |
| **Ethernet devices say connected, but cannot reach some sites**, and do not get a usable IPv4 address automatically. | Gets their address requests through to the CHR30A and sends the router's replies back to the wired side. |

Your CHR30A stays the main router. Your devices' normal internet traffic keeps using the network directly. The helper handles address messages; it does not put all your traffic through the Mac.

> **A workaround, with clear limits.** This targets the two address-assignment problems described above. It is not a firmware upgrade or a fix for every yellow light. The combined workaround worked with my Mac and Stream TV; the reusable release needs testing in more homes. [What has been tested →](docs/validation.md)

## Download. Open. Follow the questions.

### 1 · Download the right Mac file

**[Get the executable from Releases →](https://github.com/travismansook/keep-your-e3200/releases/latest)**

Choose **Apple Silicon** for an M-series Mac or **Intel** for an Intel Mac. Requires **macOS 15 or later**. The ZIP contains one file: **Keep Your E3200.command**. No building, Python installation, or code editing is needed.

### 2 · Choose how to connect the Mac

The launcher offers two modes:

| Mode | Mac connections | What it does |
| --- | --- | --- |
| **1. Wi-Fi + Ethernet — Recommended** | Home Wi-Fi plus an Ethernet cable directly into the E3200 | Runs the compatibility fix and helps wired devices obtain IPv4 automatically. |
| **2. Wi-Fi only** | Home Wi-Fi; no Mac Ethernet cable needed | Runs only the E3200 compatibility fix. It does **not** fix wired devices missing IPv4. |

Keep the extender's coax connection to the router in either mode. **The main CHR30A needs its MoCA Expansion Module installed.** Wi-Fi-only refers to the Mac, not a wireless connection between the E3200 and CHR30A. [Connection requirements →](docs/faq.md#what-do-i-need-to-connect-the-e3200-over-coax)

### 3 · Open the helper

Unzip the download and double-click **Keep Your E3200.command**. The guided setup reads your connections and asks for your E3200's MAC address and an unused address you have set aside on the router. It requests administrator access when needed.

Choose a mode; pressing Return selects **Wi-Fi + Ethernet — Recommended**. Your setup summary shows the E3200 address, router/DNS, connections and offered lease length. Wait for **READY**, which names the mode running. Leave the window open and the Mac awake. **Ctrl+C** stops everything started by that mode.

**[First-time setup, including Mac's download warning →](docs/setup.md)**

## Do I need to leave it running?

**Yes—plan to keep the helper running and its host awake, with the connections required by your selected mode available.** Devices can need it when they first connect, renew their addresses, restart, or lose a lease. They may keep working for a while after it closes, but that is not a permanent fix.

An existing spare Mac can be a practical host. A small Linux computer or **Raspberry Pi** could be a future always-on option, but **this Mac download will not run on a Pi**. Windows, Linux, and Raspberry Pi support are planned for later; they are not included in this release.

**[Read the FAQ: leases, power, speed, and always-on options →](docs/faq.md)**

## Which project should I use?

This is the **combined compatibility + Ethernet helper for Mac**. My earlier [E3200 DHCP Helper](https://github.com/travismansook/e3200-dhcp-helper) focuses on the extender's own address/compatibility problem and has separate Windows, Mac, and Linux workflows. Those platform downloads do not contain this new Ethernet forwarder.

Run only one applicable helper at a time. If you already use the earlier program, stop it before starting this one.

## Want the story—or the details?

- **[FAQ](docs/faq.md)** — answers without the networking jargon.
- **[Setup guide](docs/setup.md)** — what to connect, what to enter, and how to stop.
- **[Troubleshooting](docs/troubleshooting.md)** — what to check when something does not work.
- **[Behind the scenes](docs/behind-the-scenes.md)** — the DHCP behavior, design, source, and developer instructions.
- **[Validation record](docs/validation.md)** — observed results and what still needs field testing.
- **[Project story](docs/project-story.md)** — why I made this and how the investigation became this tool.
- **[Roadmap](docs/roadmap.md)** — Windows, Linux, and Raspberry Pi plans.

This project is independent of Verizon. Verizon currently [does not support pairing the CHR30A with previous-generation extenders](https://www.verizon.com/support/residential/internet/equipment/routers/wi-fi-access-point). The helper does not turn it into a fully supported Verizon mesh system.

Original code: [MIT license](LICENSE). Bundled components retain their [own licenses](THIRD-PARTY-NOTICES.md).
