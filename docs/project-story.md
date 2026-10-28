# Why I made Keep Your E3200

[← Back](../README.md)

I wanted to keep using my E3200 after upgrading my main router from a CR1000A to a CHR30A. It was still useful equipment, and I wanted to understand why the new setup stopped working before giving up on it.

The possibility of keeping it as an extra extender made that worthwhile. If Verizon provides another CHR30A as the replacement access point and lets you retain the E3200, the old extender can cover another area instead of sitting unused. That is a big part of why I wanted to share this project. Replacement costs and return requirements depend on your arrangement with Verizon.

My E3200's logs showed it rejecting address offers that lacked compatibility information. A responder limited to that extender addressed the first problem and restored access to its settings page. Then I found a second issue: devices plugged into the E3200 or its switch could have IPv6 while their IPv4 address requests failed. Some sites worked, while others would not load.

Comparing captures from both network paths with the router's logs led to the combined forwarding workaround. My Mac and Stream TV could obtain IPv4 addresses from the CHR30A again, without manually setting an address on every client.

I brought both workarounds into one guided Mac launcher. It coordinates the two components, keeps settings private, checks that they are ready, and stops them together. I kept the everyday instructions separate from the protocol and implementation details so you can use the helper without working through the whole investigation.

Behind the scenes, the project covers packet-level diagnosis, two separate DHCP roles, preserving the main router as the source of ordinary clients' addresses, process supervision, configuration validation, native packaging and offline tests.

The original workaround worked on my network with my Mac and Stream TV. The reusable download makes that work easier to share, but I still need broader field testing before claiming it works in every home. Windows, Linux and support for a small dedicated host such as a Raspberry Pi are future work.
