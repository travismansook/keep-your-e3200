# Linux preview validation — November 14, 2026

## Initial Raspberry Pi trial — 0.1.0~preview1

I installed the preview on a **Raspberry Pi 4 Model B with 1 GB RAM**, using Raspberry Pi OS Lite 64-bit and an 8 GB microSD card. The diagnostic screenshot showed kernel `6.18.50+rpt-rpi-v8`, a verified home Wi-Fi router, an active Ethernet link, and `throttled=0x0`.

The isolated Linux network-namespace test passed on the Pi: DHCP OFFER, ACK and renewal replies reached the simulated client, and the raw-IP local UDP/interface delivery check passed. These packets stayed inside temporary virtual networks; the test did not use my home router as its simulated DHCP server.

With the Mac helper stopped, I then confirmed that an actual device connected through the E3200 by Ethernet, with Wi-Fi off and automatic addressing, received IPv4 and had internet access. This is an initial live result, not a saved capture of every request or a long-term reliability test. The E3200's existing long lease is not evidence of a fresh compatibility lease from the Pi.

## Quality-of-life update — 0.1.0~preview2

The complete development suite passed **122 tests**, including 43 Linux-specific cases. Six Linux shell scripts passed syntax checks, and all four Linux Python modules passed compilation checks.

New regressions cover:

- A real foreground-terminal Ctrl+C closes an inert live log viewer, reaps its process, and returns directly to a usable Home menu. The viewer executes no service-control command. Other tests check journal errors, interrupt exit codes and one-time recent logs. The test uses an inert viewer instead of running journalctl on the Mac.
- Normal terminal backspace and arrow-key editing; blank/invalid mode choices retry instead of selecting a mode; confirmations accept either case and optional `y`/`n`.
- Setup offers saved adapter/address defaults and keeps a custom lease duration. Cancelling does not save over the existing setup.
- Initial service startup does not instruct an already running service to repeat setup. Damaged reports show unknown readiness. Diagnose distinguishes the router from the Pi and still reports useful checks when Ethernet is unavailable.
- Boot preferences do not implicitly start or stop the service. An explicit manual start clears an old systemd failure limit before trying again.
- Unchanged supervisor status is written/logged once instead of repeatedly. A slower component startup reports that Wi-Fi is already verified.
- Isolated shell-script tests verify package selection when an older download remains, checksum rejection before package installation, preservation of the previous cached package, and clearing an obsolete active-service restart marker. These replace OS/package commands; they do not run real apt/dpkg/systemd upgrades.

The new package still needs its own Pi trial. Packet forwarding and address-assignment rules were not changed in this update. The update does not change any existing installed Pi or Mac files until it is installed.

## GitHub candidate — 0.1.0~preview3

The prepared GitHub source starts from the published Mac v0.3.0 baseline, adds the Linux implementation and platform-specific forwarding branches, and includes the preview2 quality-of-life fixes. Unreleased Mac recovery experiments are excluded. The root Mac version remains 0.3.0.

This exact candidate's automated suite passed **105 tests: 62 existing Mac/shared checks and 43 Linux-specific checks**. The earlier 122-test development run above also included 17 unpublished Mac tests. The smaller release count reflects that separation, not removal of Linux coverage. Workflow/issue-form YAML syntax, Linux shell scripts, links, package metadata and checksums are checked separately during preparation.

Preview3 updates the package/guide/release preparation under a fresh version instead of replacing preview2 files with different contents. It still needs its own Pi update/menu trial, and GitHub CI has not run merely because its workflow is prepared. The Linux workflow requires explicit manual publication and marks its release as a prerelease without replacing Mac Latest.

## Earlier development checks — preview1, November 13

- The full automated suite passed **99 tests** after adding the initial Linux implementation and packaging checks.
- After a final status-display improvement, the Linux-focused suite passed **21 tests**. This includes a new test ensuring an old READY report is not shown as current after the service restarts. There were 100 distinct tests at that point; the final targeted check was used instead of rerunning unchanged Mac tests.
- Inert child-process tests cover full/compatibility modes, Wi-Fi loss and recovery, Ethernet reconnect while compatibility stays alive, fatal child shutdown and cleanup, and status transitions. These do not start DHCP or capture packets.
- Protocol tests reuse the existing request/reply gate: preserve client identity/XID, reject unknown server replies and unsolicited packets, handle renewals, exclude the E3200 and mesh probes, reject malformed/fragmented traffic, suppress duplicates and bound pending requests.
- Linux raw-IP tests cover byte order, checksums, device binding, neighbor refresh, wrong router identity, and rejecting a delivery self-test on the wrong interface.
- Package tests inspect the Debian ar/control/data archives, executable modes, dependency metadata, maintainer scripts, file MD5sums and bundle SHA256 sums. They verify initial installation has no automatic start/enable and upgrade scripts remember whether the old service was running. These tests do not execute apt/dpkg/systemd.
- Installer and maintainer scripts passed shell syntax checks. Python files passed compilation checks. The CLI version command returned `0.1.0~preview1`.

## Still required on Linux / the Pi

Install the new update and verify its menu, real journalctl viewer, Ctrl+C return, startup reports and retained settings. Beyond the initial working client, validate live DHCP renewal through the E3200, a fresh E3200 compatibility lease, Ethernet unplug/replug, Wi-Fi loss/recovery, and reboot startup. Test actual apt/dpkg upgrades with the service running/stopped and boot startup enabled/disabled. A deliberately tested downgrade is needed before promising rollback across future settings-schema changes.

Keep the Mac helper stopped during the live Pi compatibility trial. Existing long leases or a reachable E3200 page alone do not prove the new responder is functioning. Record a fresh E3200 DHCP acknowledgement and check the extender's actual state.

## Release scope

Preview only. No router settings were changed during GitHub preparation, and the Mac executable download was not replaced. Initial Pi installation and live-client evidence apply to preview1. Preview2 development checks and the preview3 source-candidate checks are separate from the remaining live update/recovery tests. GitHub CI and release results must be recorded after those actions actually run.
