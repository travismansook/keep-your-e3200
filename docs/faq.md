# Frequently asked questions

[← Back to Keep Your E3200](../README.md)

## What are the benefits?

**A router upgrade does not have to mean losing a useful extender.** The biggest benefit is a chance to keep the E3200 working as an extra Wi-Fi coverage point, with usable Ethernet connections, instead of leaving it unused.

- **An extra extender after your upgrade.** If you keep your E3200 when moving to a CHR30A, you can give it another job covering a room or area that could use a stronger signal. Keep its working coax connection; this helper targets the address-assignment problems in that setup.
- **Keep wired devices online.** The combined helper gets ordinary Ethernet clients' address requests through to the main router, so they can use automatic IPv4 instead of needing a manual address on each device.
- **Get the E3200's settings page back.** Once the extender accepts its IPv4 address, you can open its network settings at that address again.
- **Make more use of hardware you already have.** Reusing the E3200 can avoid another extender purchase and keep useful equipment out of storage or the waste stream. Allow for the host computer's electricity costs.
- **One guided launcher for both problems.** Compatibility help and Ethernet address forwarding start and stop together, without flashing custom firmware or building the program yourself.

### Why is keeping the old E3200 such a big deal?

In my experience upgrading from a **CR1000A to a CHR30A main router**, keeping the old E3200 is a big part of what makes this project useful. Verizon may replace the old extender with **another CHR30A acting as an access point**, potentially at no extra charge. If Verizon also lets you keep the E3200, the opportunity is especially useful: **use the replacement access point and put the retained E3200 back to work as an additional extender.** You gain another possible coverage location from equipment you would otherwise stop using.

That is an opportunity from my experience, not a promise of free equipment or permission to keep every Verizon-owned device. Confirm the replacement cost and whether the E3200 must be returned with Verizon for your account. Verizon documents the [CHR30A's router and extender roles](https://www.verizon.com/support/residential/internet/equipment/routers/wi-fi-access-point), but the E3200 workaround here remains an independent community project.

The E3200 keeps its original hardware capabilities. This does not upgrade it to Wi-Fi 7 or guarantee better coverage in every home. The helper must remain available, and the public release still needs broader field testing. [What has been tested →](validation.md)

## What do I need to connect the E3200 over coax?

**The main CHR30A router needs the MoCA Expansion Module installed.** The module provides its coax connection. Connect the CHR30A and E3200 through your home's working coax wiring. See [Verizon's MoCA module instructions](https://www.verizon.com/support/residential/internet/equipment/routers/wi-fi-access-point).

**The E3200 cannot connect wirelessly back to the CHR30A.** My tested setup uses coax between them; the helper does not replace that physical connection. The E3200 can still provide Wi-Fi to phones, laptops and other devices—the restriction is on its connection back to this main router.

**What about the G3100?** I have not tested the E3200 with a G3100 to determine whether this setup works wirelessly instead of over coax. The results documented here apply to the CHR30A with coax; the wireless restriction above should not be read as a claim about every Verizon router.

## Do I need to keep this running all the time?

**Plan to leave it running whenever you want this setup to work reliably.** Keep the host awake with its Wi-Fi and Ethernet connections available.

The helper is needed for address requests, not every internet packet. An existing lease may continue working after you close it, so the effect is not always immediate. New devices, renewals, restarts, or lost addresses can need the helper again.

## Can I just run it once and choose a one-year lease?

That is not a reliable substitute for an available helper. A lease has an expiry, and the E3200 normally tries to renew before then. Restarting or losing an address can cause an earlier request.

Start with a **one-hour E3200 lease** while checking that it works and renews. One day or one year can be selected later, but neither removes the need to keep the host available. Changing this setting affects a new or renewed E3200 lease, not a lease it already accepted. The CHR30A controls ordinary devices' leases separately.

## Could I leave it running on a Raspberry Pi?

**That is a planned option for a future Linux version. The current executable is for Mac and will not run on a Raspberry Pi.**

A Pi is attractive because it is small and can use little power. This workaround needs both Wi-Fi and Ethernet, so a future Pi setup would need both connections and a supported Linux implementation. Some Pi models need an extra Ethernet adapter. Do not buy hardware assuming this release already supports it. [Platform plans →](roadmap.md)

## What about an old laptop or spare computer?

An already-owned spare Mac can avoid an extra hardware purchase. It needs a supported Mac version, Wi-Fi, Ethernet, and reliable power. Keep the screen off if desired, but keep the computer awake. An adapter may be needed if it has no Ethernet port.

Windows and Linux laptops are planned for later. The old project's Windows/Linux compatibility-only downloads do not include this combined Ethernet workaround.

## Will leaving a laptop on use more electricity?

It depends on the computer. Screen-off idle consumption is the useful number; the wattage printed on its charger is its capacity, not its constant consumption. A plug-in power meter gives a better estimate.

For illustration, at **20 cents per kWh**, a device averaging **3 watts** all day costs about **$5.26 per year**; **10 watts** costs about **$17.52 per year**; **20 watts** costs about **$35.04 per year**. These are example calculations, not measurements of your computer or promises about a particular Pi. A free laptop can remain cheaper overall than buying a smaller device just to save that difference.

## Why does the Mac need Wi-Fi and Ethernet at the same time?

They have different jobs. Ethernet lets the helper hear address requests on the E3200's wired side. Wi-Fi provides the working path used for the compatibility response and for getting ordinary requests to the real router. The combined setup needs both.

Keep the normal network preference that works for you; the helper does not change your connection order, IP settings, router pool, or reservations. I kept Ethernet first for normal internet traffic in my working setup.

## Will this slow down my internet or route everything through my computer?

The helper only handles DHCP address messages. Downloads, video, and games do not pass through the helper as an internet proxy. The helper's Wi-Fi speed therefore is not a cap on your devices' ordinary Ethernet speed. This project does not promise a particular throughput or latency.

## Does it fix the yellow light and the Ethernet ports?

It combines the two relevant workarounds: an E3200-specific compatibility address offer, and forwarding of ordinary wired clients' DHCP exchanges to the CHR30A. It targets the failures I saw on my network.

A yellow light can have other causes, such as a real connection or signal problem. Check power and coax/cables too. This is not a repair for a damaged port, broken cable, or every E3200 fault.

## Does the E3200 assign the wired devices their addresses now?

**The CHR30A still assigns ordinary devices their addresses.** The helper transports their requests and the router's replies. The separate compatibility component answers only the one configured E3200. It does not create a new general address pool.

## Why did Google work when another website did not?

Having IPv6 can let some services work even when a device is missing usable IPv4. My TV and Mac had that partial-connectivity pattern on Ethernet during the investigation. It is a clue, not proof of this exact fault in every home. [Troubleshooting →](troubleshooting.md)

## Do I have to add every Ethernet device to the helper?

No client list is required for the general forwarder. You configure the E3200 once; ordinary wired clients keep using automatic DHCP. I verified the original workaround with my Mac and Stream TV. I have not tested every device or unusual network arrangement.

## Can I close the window or shut down the Mac?

Ctrl+C stops both helper components. Closing its terminal window or shutting down the host also makes the helper unavailable. Existing leases might keep working for a time, but later requests can fail. Keep it open if you depend on this workaround.

The program keeps the Mac awake while its managed helper is running. It is not an installed startup service, and recovery after host reboot has not been field-verified. Reopen it after restarting the host.

## Is it a permanent firmware fix? Is it supported by Verizon?

No. It is an independent computer-hosted workaround. It does not flash the extender, replace router firmware, or establish full Verizon mesh/SON compatibility. Verizon's current compatibility guidance does not support the older extenders with the CHR30A. [Official guidance](https://www.verizon.com/support/residential/internet/equipment/routers/wi-fi-access-point)

## Is it free? Does it send my information anywhere?

The project is open source and has no subscription. You supply the host computer and its electricity.

There is no telemetry or account sign-in. Your settings and logs stay in your Mac's private Application Support folder. Startup performs a small IPv4 connectivity check against Google's standard connectivity-check endpoint; normal operation talks on your home network. Logs can contain local IP/MAC addresses, so remove those before posting them publicly.

## Can I use more than one E3200, or run two helpers together?

This preview configures one E3200. Run one applicable compatibility responder for that extender, and avoid duplicate combined helpers. Multiple-extender management has not been implemented or field-tested.

## Do I have to build it, install Python, or understand networking?

**Use the executable download in Releases.** Python and the DHCP engine are included. You only need to connect both links, identify the E3200, check its address on your router, and follow the setup questions. The source code and developer build instructions are optional. [Start here →](setup.md)
