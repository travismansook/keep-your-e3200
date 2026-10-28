# Behind the scenes

[← Back to the simple explanation](../README.md)

## The two DHCP paths

My network was CHR30A → coax/MoCA → E3200 → gigabit switch → Ethernet devices. I used a gigabit switch for extra Ethernet ports; you can connect directly to the E3200 without one. My Mac was connected to both the downstream Ethernet and home Wi-Fi. During the investigation, I confirmed that the Mac's Wi-Fi connection was associated with the E3200 radio.

The recommended `full` mode runs both components. The `compatibility` mode runs only the responder on Wi-Fi; no Ethernet forwarder, capture or Ethernet adapter is required. Both modes use the same one-extender compatibility configuration.

The two components have different scopes:

| Component | Scope | Address authority |
| --- | --- | --- |
| Compatibility responder | One configured E3200 MAC, on Wi-Fi only | Static E3200 address chosen/protected by the operator |
| Ethernet forwarder | Ordinary, non-extender client transactions observed on downstream Ethernet | Actual CHR30A DHCP offers/acknowledgements |

The responder uses dnsmasq with DNS disabled (`port=0`), a static-only range, one MAC host entry, and an ignore rule for unmatched clients. It advertises the real gateway and DNS. DHCP option 60 is `ARCADYAN`. Option 125 carries a compatibility profile with enterprise 3561, OUI `880355`, a fictitious serial, and product class `G3100`. This compatibility identity does not change the physical router or establish full SON integration.

The general forwarder observes DHCP requests on the selected Ethernet connection, preserves the client identity/transaction ID, transmits over the selected Wi-Fi path, and accepts matching replies only from the configured real router. It sends those genuine replies back to Ethernet. It excludes the configured extender and the special detector vendor classes. No ordinary-client address pool or per-client list is created.

For renewal requests with nonzero `ciaddr`, it uses an INIT-REBOOT-style broadcast form requesting the existing address, allowing the real server's response to return through the observed path. This transformation has synthetic coverage; the successful live manual renewal on my network does not independently prove a natural T1 exchange exercised that branch.

The forwarder rejects malformed/fragmented input, relayed requests, identity mismatches, unsolicited replies, mismatched servers/transactions and duplicates. Rate limits and bounded transaction caches keep state limited. MAC filtering is scope control, not authentication.

## Why the compatibility responder stays on Wi-Fi

During my trials, moving the E3200-specific compatibility response onto downstream Ethernet caused unwanted backhaul behavior. The combined design retains the working Wi-Fi-side scope. Ordinary wired clients receive the CHR30A's replies through the other component.

Do not turn this into a broad DHCP server, move the extender responder to the wired side, or add unrelated interface changes as a convenience. The fact that a Mac is attached to both links does not mean it is configured as an IP router, NAT gateway or general bridge. It transports DHCP only.

## Runtime and shutdown

The guided program validates the operator's private settings and the connections required by the selected mode. It verifies and copies its bundled components into a private temporary directory, then invokes the existing shell supervisor. In full mode, the worker starts the forwarder first and waits for readiness before starting the extender responder. Either component failing stops both. In compatibility mode it starts only the extender responder. Both paths retain the same parent watcher and shutdown supervision.

The supervisor handles Ctrl+C, SIGTERM, SIGHUP, stop requests, trial expiry, and parent disappearance. It holds the authority needed to stop its children; cleanup does not require a new sudo prompt. `caffeinate` watches the public parent. Each component has its own process group and bounded shutdown handling. Graceful exit cleans the temporary bundle. A SIGKILL cannot run parent-side filesystem cleanup, so temporary remnants are possible even though the watchdog stops the networking components.

Settings, leases, logs and private lock files live under `~/Library/Application Support/E3200 CHR30A Helper`. They are never written beside the executable. I have included examples and synthetic fixtures in this repository, keeping my private configuration and raw network logs out of it.

## Repository layout

| Path | Purpose |
| --- | --- |
| `src/desktop.py` | Guided setup, private profile, resource verification, internal worker dispatch and parent lifecycle |
| `src/configuration.py` | Address/identity validation and read-only Mac discovery |
| `src/forwarder.py` | Bounded DHCP transport and Darwin packet delivery |
| `src/combined_worker.py` | Start/stop/readiness coordination |
| `src/launcher.template.command` | Privileged process supervision and network preflight |
| `packaging/` | Native executable build and release description |
| `third_party/` | Reviewed dnsmasq patch, official source/checksum metadata and license; full corresponding source is included in each executable download |
| `tests/` | Offline protocol, configuration and lifecycle coverage |

## Developer workflow (optional)

End users should download the executable from Releases. These commands are only for working on the source:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install pyinstaller==6.22.3
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python packaging/build_release.py
```

Build on a native macOS runner with Apple command-line build tools. The engine is compiled from the pinned, complete modified source. PyInstaller creates one native executable containing Python, the engine, corresponding source and license notices. Native downloads require macOS 15+. Apple Silicon and Intel builds are separate; neither is a Windows/Linux build.

The build startup-tests both the source entry point and frozen executable with `--self-test`. This validates offline filter compilation and dnsmasq configuration parsing, for both modes and does not run a live DHCP service. The executable also supports `--mode full`, `--mode compatibility`, `--version`, `--setup`, `--stop`, `--dry-run`, `--licenses` and `--extract-source NEW_FOLDER`.

## Sources and boundaries

- [DHCP protocol / RFC 2131](https://www.rfc-editor.org/rfc/rfc2131.html)
- [dnsmasq upstream](https://thekelleys.org.uk/dnsmasq/doc.html)
- [Verizon CHR30A compatibility guidance](https://www.verizon.com/support/residential/internet/equipment/routers/wi-fi-access-point)
- [Original compatibility-only project](https://github.com/travismansook/e3200-dhcp-helper)

My captures establish a failing path and a working transport workaround on my network. They do not locate the precise dropping branch inside E3200/CHR30A firmware. The project includes no firmware patch, signing bypass, privileged extender access, VPN fix, or vendor-support claim.

Older saved profiles without a mode load as full mode. New Wi-Fi-only profiles can omit Ethernet hardware by storing null adapter fields. Interactive launches always default to the recommended full mode; switching a Wi-Fi-first profile to full mode requires adapter setup. Validation-only runs never prompt for setup or persist mode changes. The startup summary reports configured extender lease duration, separately from main-router client leases.
