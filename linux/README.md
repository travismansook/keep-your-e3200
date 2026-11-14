# Linux / Raspberry Pi setup

[← Keep Your E3200](https://github.com/travismansook/keep-your-e3200) · [FAQ](https://github.com/travismansook/keep-your-e3200/blob/main/docs/faq.md) · [Release notes](RELEASE_NOTES.md)

Keep the E3200 useful with a CHR30A. This version moves the compatibility responder and Ethernet DHCP workaround off the Mac and onto an always-on Linux computer.

**Community preview with initial Raspberry Pi 4 testing.** I installed the first preview on my Pi 4 with 1 GB RAM, passed the isolated Linux DHCP delivery test, and confirmed that an actual Ethernet device received IPv4 and internet access. Reboot recovery, cable reconnection, a fresh E3200 compatibility lease and longer-term renewals still need verification. No custom extender firmware is installed. [Testing record →](VALIDATION.md)

The GitHub candidate, **0.1.0~preview3**, includes the live-log menu, clearer address/startup messages, saved setup defaults and update fixes. Its updated package still needs its own Pi trial. The Mac and Linux/Pi downloads are in the same repo, with separate versions.

## What you need

- Raspberry Pi 4 Model B, including the 1 GB model.
- Raspberry Pi OS **Lite, 64-bit**, current Debian Bookworm/Trixie-based release with NetworkManager, Python 3.11+, and systemd. No desktop required. The same package is suitable for compatible Debian ARM64/x86-64 computers; native dependencies come from apt.
- 8 GB microSD minimum for Lite; that is enough to begin, with limited room for updates. A healthy 16/32 GB card gives more headroom later.
- Suitable USB-C power. The official 27 W Raspberry Pi supply provides the 5 V output the Pi 4 needs; a 27 W label on an unknown charger alone does not establish its 5 V current rating.
- Home Wi-Fi, plus the Pi's Ethernet cable connected to an E3200 LAN port for the full mode. Your existing gigabit switch can provide that connection too.
- E3200 connected by coax to the CHR30A's MoCA module. The helper doesn't create a wireless E3200-to-CHR30A backhaul.

## Prepare the card on your Mac

1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
2. Select Raspberry Pi 4, then **Raspberry Pi OS Lite (64-bit)**. Select the microSD carefully: writing erases the selected card.
3. Set hostname **e3200-pi**, your own username/password, home Wi-Fi name/password/country, and your timezone. Enable SSH for remote access. Use an SSH public key if you already have one; otherwise choose a strong SSH password. Do not share it in chat.
4. Write, verify and eject the card. Insert it into the Pi, then connect power. Initially leave Ethernet disconnected so SSH uses Wi-Fi.
5. Wait for the first boot, then on the Mac open Terminal and connect using your chosen username, for example:

```sh
ssh yourname@e3200-pi.local
```

Replace `yourname` with the username you chose in Imager. If you chose a different hostname, use it instead of `e3200-pi`. Already using a compatible Linux computer? Skip card preparation and install in its local Terminal.

If `.local` doesn't resolve, find e3200-pi in the router's device list and use its Wi-Fi IPv4 address. Verify the SSH host fingerprint on first connection if you have a way to check it from the Pi. There is no universal default `pi` password. Update the OS normally before installation; keep at least a few hundred MB free on the 8 GB card.

## Download and install — no compiling

**Recommended: use the single .deb installer** from the [Linux/Pi preview release](https://github.com/travismansook/keep-your-e3200/releases/tag/linux-v0.1.0-preview3). Choose **keep-your-e3200_0.1.0~preview3_all.deb**. It installs the application and lets the package manager handle dependencies.

On the Pi/Linux Terminal, you can download and install it directly:

```sh
cd ~
wget "https://github.com/travismansook/keep-your-e3200/releases/download/linux-v0.1.0-preview3/keep-your-e3200_0.1.0~preview3_all.deb"
sudo apt install ./keep-your-e3200_0.1.0~preview3_all.deb
```

If `wget` is unavailable, install it with `sudo apt install wget`, or use the Mac copy method below. The package asks for confirmation before installing. No compiling, OS reinstall or separate Python setup is needed.

<details>
<summary>Downloaded the .deb on your Mac instead?</summary>

Assuming it is in Downloads, run this in a **Mac Terminal window**, replacing `yourname` with your Pi username:

```sh
scp ~/Downloads/keep-your-e3200_0.1.0~preview3_all.deb yourname@e3200-pi.local:~/
```

Then, in the Pi's Terminal session:

```sh
sudo apt install ~/keep-your-e3200_0.1.0~preview3_all.deb
```

</details>

## Configure the helper

```sh
keep-your-e3200 setup
```

The .deb installs any missing Python, distro-provided dnsmasq-base, libpcap and networking dependencies through apt. It installs **no general-purpose DHCP pool** and does not start or enable the helper automatically. Use an existing NetworkManager setup; this preview does not provide a migration from another network manager.

Choose **Wi-Fi + Ethernet** for the full helper. The wizard detects your router, asks for the E3200's **LAN1 MAC** from the back sticker, the address already reserved for it on your router, and an offered lease duration. Dotted sticker addresses work. Keep the existing E3200 reservation from the Mac setup; do not add another reservation for the same address.

Then prepare the Pi's dedicated Ethernet connection:

```sh
keep-your-e3200 prepare-ethernet
```

Read and confirm the prompt while SSH uses **Wi-Fi**. This creates a NetworkManager profile only for the chosen Ethernet adapter: link-local addressing, no default route, no NAT. The Pi stays online through Wi-Fi; ordinary Ethernet clients still receive addresses from the CHR30A. Existing Ethernet profiles are retained. Plug in the Ethernet cable and allow a moment for activation.

## Switch from the Mac

**Stop the Mac helper before starting this helper.** Do not run two compatibility responders for the same E3200. Existing leases aren't erased by stopping the Mac helper.

```sh
keep-your-e3200 diagnose
keep-your-e3200 start
keep-your-e3200 status
```

`diagnose` checks the selected home Wi-Fi/router identity and displays Ethernet, disk and Pi power flags. It does not send DHCP. A single router ping may refresh the neighbor cache.

`active` only means systemd has the supervisor running. Look at the current report: **both components running**, **compatibility only**, **Ethernet waiting**, or **home Wi-Fi paused**. These messages explain what to do next. The helper doesn't claim internet works simply because a process exists.

### Which address am I looking at?

Diagnose shows the **main router IPv4** and **this Pi's Wi-Fi IPv4** separately. They should be different: for example, the router might be `192.168.1.1` while the Pi uses `192.168.1.24`.

The Pi's **dedicated helper Ethernet connection** intentionally uses a local-only `169.254.x.x` address. The Pi stays online through Wi-Fi. Other wired devices connected to the E3200 should receive their normal home-network IPv4 addresses from the CHR30A; a self-assigned `169.254.x.x` address on those clients is still a sign to investigate.

Test the TV with Wi-Fi off and Ethernet on DHCP; reconnect its hub and verify IPv4 plus a webpage. Test another Ethernet device on DHCP, including renewal. When a brief interruption is acceptable, restart the E3200 once while the Pi compatibility component is running, so it makes a fresh DHCP request to the new helper. Check the Pi log for the E3200 address acknowledgement, then verify the extender settings page and normal service. A settings page that still opens on an old one-year lease is not proof that the new compatibility responder works. Observe beyond the first successful connection and through lease renewal before declaring a permanent fix.

Once those tests pass, enable startup after reboot:

```sh
keep-your-e3200 enable
```

This enables future boot startup; it does not start a stopped service immediately. Reboot when convenient and verify Status again. **Closing SSH or the menu does not stop the background service.** Power off properly with `sudo poweroff` before removing power or the microSD card.

## Daily controls

Run `keep-your-e3200` for Home. Choose **13 · View live logs** to watch detailed entries arrive, like the Mac version. Press **Ctrl+C** to return directly Home; closing the viewer leaves the background helper in its current state. Choose **9 · View recent detailed logs** for a one-time view of the latest entries.

You can also use:

| Command | What it does |
|---|---|
| `keep-your-e3200 status` | Current service state, boot setting, explanation and next step |
| `keep-your-e3200 stop` | Stops both helper components |
| `keep-your-e3200 start` | Starts the background service |
| `keep-your-e3200 review` | Reviews saved settings, not a live lease check |
| `keep-your-e3200 lease` | Confirms and saves a new offered E3200 lease; stop first |
| `keep-your-e3200 logs --follow` | Detailed live logs; Ctrl+C ends the viewer only |
| `keep-your-e3200 disable` | Disables boot startup; does not stop the currently running service |
| `keep-your-e3200 restore-ethernet` | Removes only this helper's dedicated Ethernet profile; stop first |

To change setup, stop the helper with **2**, choose **4 · Setup / replace settings**, then start it again with **1**. Saved adapter choices, the extender address and the existing lease duration are offered as defaults; press Return to keep a bracketed value. The mode question still requires an explicit choice. Setup changes are written only after you confirm the final summary. Choose **6** to change just the lease, with confirmation. Yes/no questions accept `yes`, `no`, `y` and `n`, in either case.

Enabling automatic startup affects future reboots. Disabling it leaves a currently running helper running; choose **2 · Stop helper** to stop it now. Stop and boot-setting actions confirm what changed. Reviewing settings before first-time setup explains how to configure the helper instead of reporting a file-permission problem.

Loss of the selected Ethernet link reopens forwarding after the same adapter returns. Compatibility can continue on verified Wi-Fi while Ethernet waits. Loss of home Wi-Fi pauses both components and retries; the saved gateway hardware identity protects against automatically serving a different network with the same private addresses. A reboot is handled by systemd only after boot startup is enabled. Fatal errors are logged and retried with rate limiting, not hidden behind a permanent READY label.

Changing the offered lease affects future offers after restart. It does not retroactively change the extender's already accepted lease expiry. The main router controls other devices' leases.

## Storage, files and removal

Program: `/opt/keep-your-e3200`; settings: `/etc/keep-your-e3200/profile.json`; runtime status and rotating logs: `/var/lib/keep-your-e3200`; sockets/locks/config: `/run/keep-your-e3200`. Dedicated detailed logs are bounded to about **6 MiB**. The OS also manages its system journal; check disk space periodically on an 8 GB card. This program doesn't change global journal settings.

To stop using it, run `keep-your-e3200 stop`, `keep-your-e3200 disable`, and optionally `keep-your-e3200 restore-ethernet`. Files are left in place so your configuration/lease history can be recovered. Removing installed program files is optional; apt dependencies may be used by other programs and should not be blindly removed.

## Testing and limits

The optional developer test below uses temporary Linux network namespaces and virtual interfaces, **not your home network**. It needs root. It tests actual Linux packet forwarding/self-delivery/privilege dropping without touching physical interface configuration:

```sh
sudo python3 linux/test_network_namespace.py
```

Run it after installing dependencies if you want the kernel-level check before cutover. A pass still doesn't prove the Pi Wi-Fi chipset will transmit the forwarded DHCP frames correctly. The live home-network acquisition/renewal/reboot tests remain necessary. If the delivery self-test fails, the forwarding component will not pretend to be ready: share `keep-your-e3200 logs` for diagnosis.

Supports the current Linux preview only; this is not the Mac `.command` renamed, and it is not an Android APK. It changes no E3200 firmware and doesn't fix every possible Wi-Fi disconnection. Wi-Fi-only mode provides only the E3200 compatibility responder. Both modes require the host to remain powered and connected.

References: [Raspberry Pi setup](https://www.raspberrypi.com/documentation/computers/getting-started.html), [Lite downloads](https://www.raspberrypi.com/software/operating-systems/), [NetworkManager properties](https://networkmanager.dev/docs/api/latest/nm-settings-nmcli.html).

## Updates and GitHub releases

You do not compile this application and do not reflash the microSD for app updates. Each GitHub release can contain a versioned `keep-your-e3200_VERSION_all.deb` and the ready-to-copy source/installer bundle. `all` means architecture-independent Python; apt selects the native library packages for your Pi or PC. Keep one repository and increase the package version for each release; don't replace an asset with different code under the same version.

**Download the newer .deb and install it with the same apt command.** For this release:

```sh
sudo apt install ./keep-your-e3200_0.1.0~preview3_all.deb
```

Use the path where you downloaded the file. Quit an old menu with **0**, then reopen `keep-your-e3200` to load the updated application. Your settings and leases are kept; a previously running helper is restarted, and the boot preference is preserved. Check Status for current readiness. First installations remain stopped and disabled.

<details>
<summary>Optional installer bundle and cached rollback package</summary>

The release also offers **Keep-Your-E3200-Linux-Preview.tar.gz**. Extract it, open the resulting `Keep-Your-E3200-Linux-Preview` folder in Terminal and run `sudo ./linux/install.sh` to install, or the same wrapper below to update:

```sh
sudo ./linux/install.sh --update
```

It uses Debian's package manager, preserves generated settings and leases, and restarts the service only if it was previously running. The enabled/disabled boot preference stays unchanged. This wrapper also retains the previous downloaded .deb at `/var/cache/keep-your-e3200/previous.deb` after an update. To deliberately go back, use `sudo apt install --allow-downgrades /var/cache/keep-your-e3200/previous.deb`. Test downgrade compatibility before relying on it for future versions that change settings formats.

Older `.deb` downloads can remain in the extracted folder: the installer selects the package named in the new release's verified checksum manifest. It refuses a changed or incomplete download before invoking the package manager.

Advanced users can install a downloaded .deb directly with `sudo apt install ./keep-your-e3200_VERSION_all.deb`; direct installation doesn't create the wrapper's extra cached copy. New installations remain stopped and disabled until you configure/start them. Removing the package stops/disables it but retains generated settings, lease data and logs.

</details>

A signed apt repository for unattended app updates can come later; this preview does not download or apply app updates automatically. Keep the regular OS security-update process separate.
