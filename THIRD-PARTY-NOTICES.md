# Third-party software

Original helper code is MIT licensed; see LICENSE. The downloadable program runs dnsmasq as a separate executable, under its own license.

## dnsmasq 2.93

Copyright Simon Kelley and other upstream contributors. Licensed under GPL version 2 or later; the complete license is in `third_party/dnsmasq-COPYING`.

This project uses a modified Darwin build. The patch adjusts outgoing IPv4 source/interface handling and diagnostic reporting on macOS. It does not add a general DHCP address pool. `third_party/SOURCE.json` pins the official upstream source and the reviewed `macos-relay.patch`. The release builder downloads that official source with checksum verification, applies the patch, and includes the complete modified corresponding source and its build files inside every executable download.

Native downloads include that same corresponding source archive and license. To export the included notices and source, run the downloaded executable with `--extract-source NEW_FOLDER`. `--licenses` prints this notice. Neither command starts a network service.

## Python and PyInstaller

Native downloads embed Python through PyInstaller, so users do not need a Python installation. Python is distributed under the PSF license and associated notices. PyInstaller is distributed under GPL 2.0 or later with its bootloader exception. Their license texts are included in the native download and exported by `--extract-source` alongside these notices. PyInstaller is pinned to 6.22.3 for release builds.

No Verizon firmware, real device serial numbers, network logs, credentials, or personally configured launcher is distributed here. Verizon and product names identify the equipment being discussed; this is an independent community project.
