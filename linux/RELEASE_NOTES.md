# Keep Your E3200 — Linux / Raspberry Pi 0.1.0-preview4

An always-on Linux/Pi option for keeping an E3200 useful with a CHR30A. This preview includes the local build's menu and quality-of-life improvements, with a corrected installer filename for GitHub downloads. Mac downloads remain separate in this same repository.

## Download the installer

Choose **keep-your-e3200_0.1.0-preview4_all.deb** for Raspberry Pi OS Lite 64-bit or compatible Debian-based Linux with NetworkManager and systemd. No building or compiling is required. The package manager installs the required software.

The optional **Keep-Your-E3200-Linux-Preview.tar.gz** includes the ready-made .deb, installer wrapper, guide and relevant source. **SHA256SUMS.txt** contains the release-file checksums. GitHub's automatic source archives are optional developer downloads.

Install the downloaded package:

```sh
sudo apt install ./keep-your-e3200_0.1.0-preview4_all.deb
```

For a first installation, follow the [Linux/Pi setup guide](https://github.com/travismansook/keep-your-e3200/blob/main/linux/README.md). Installation leaves the helper stopped and boot startup disabled until you configure and start it. Stop any older Mac/compatibility helper before starting the Pi helper for the same E3200.

For an update, install the newer .deb the same way. Saved settings and leases are kept, boot preference is preserved, and a previously running service is restarted. Quit an old menu and reopen `keep-your-e3200` afterward. You do not reflash the microSD or repeat setup.

## Download filename correction

GitHub normalized the tilde in preview3's installer asset name. Preview4 uses the download-safe filename **keep-your-e3200_0.1.0-preview4_all.deb**, while its internal Debian package version remains **0.1.0~preview4** for correct prerelease upgrade ordering. The guide, direct download links and checksums use the same filename.

## What is included

- **Wi-Fi + Ethernet — recommended:** E3200 compatibility help plus DHCP forwarding for ordinary wired devices. The CHR30A remains their address allocator.
- Wi-Fi-only compatibility mode, guided setup, settings review and confirmed lease changes.
- Background operation with optional startup after reboot. Closing SSH or the menu leaves the service running.
- **13 · View live logs:** Ctrl+C closes the viewer and returns Home. Recent detailed logs remain option 9.
- Clear router/Pi address labels, readable leases, saved setup defaults and normal keyboard editing.
- Status and next-step messages for startup, lost connections and errors. Unchanged status is no longer repeatedly written/logged.
- Update handling for older installer downloads and obsolete restart markers.

The Pi needs home Wi-Fi and an Ethernet connection to the E3200 for the full mode. The E3200 still needs coax to the main CHR30A's MoCA Expansion Module. The helper changes no E3200 firmware and does not transport ordinary internet traffic.

## Testing and remaining work

I installed the first local preview on a **Pi 4 Model B with 1 GB RAM**. Its isolated Linux DHCP OFFER/ACK/renewal test passed, and an actual Ethernet device using automatic addressing with Wi-Fi off received IPv4 and internet access.

The [GitHub Linux build checks](https://github.com/travismansook/keep-your-e3200/actions/runs/43567482692) passed all **105 automated tests**, package inspection/checksums and isolated Linux DHCP OFFER/ACK/renewal delivery.

This updated candidate still needs its own Pi trial. A fresh E3200 compatibility lease, live renewals, cable/Wi-Fi recovery, reboot startup, actual package upgrades and longer operation remain to be verified. Other Linux hardware is not field-validated. [Detailed testing record](https://github.com/travismansook/keep-your-e3200/blob/main/linux/VALIDATION.md).

This is a **prerelease**, not a claim of a permanent firmware repair or universal device compatibility. It does not replace the Mac latest download.
