# Frequently asked questions

[← Back to Keep Your E3200](../README.md)

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

Keep the normal network preference that works for you; the helper does not change your connection order, IP settings, router pool, or reservations. The original trial kept Ethernet first for normal internet traffic.

## Will this slow down my internet or route everything through my computer?

The helper only handles DHCP address messages. Downloads, video, and games do not pass through the helper as an internet proxy. The helper's Wi-Fi speed therefore is not a cap on your devices' ordinary Ethernet speed. This project does not promise a particular throughput or latency.

## Does it fix the yellow light and the Ethernet ports?

It combines the two relevant workarounds: an E3200-specific compatibility address offer, and forwarding of ordinary wired clients' DHCP exchanges to the CHR30A. It can address the failures observed in the original setup.

A yellow light can have other causes, such as a real connection or signal problem. Check power and coax/cables too. This is not a repair for a damaged port, broken cable, or every E3200 fault.

## Does the E3200 assign the wired devices their addresses now?

**The CHR30A still assigns ordinary devices their addresses.** The helper transports their requests and the router's replies. The separate compatibility component answers only the one configured E3200. It does not create a new general address pool.

## Why did Google work when another website did not?

Having IPv6 can let some services work even when a device is missing usable IPv4. In the original investigation, the TV and Mac had that partial-connectivity pattern on Ethernet. It is a clue, not proof of this exact fault in every home. [Troubleshooting →](troubleshooting.md)

## Do I have to add every Ethernet device to the helper?

No client list is required for the general forwarder. You configure the E3200 once; ordinary wired clients keep using automatic DHCP. Live checks in the original setup covered a Mac and Stream TV, not every device or unusual network arrangement.

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
