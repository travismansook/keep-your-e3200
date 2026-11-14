# Linux release process

Mac and Linux/Pi live in **travismansook/keep-your-e3200**. Each platform has its own download and version. Keep application updates separate from installing/reflashing Raspberry Pi OS.

1. Bump `VERSION` in `src/linux_config.py` using Debian-compatible ordering: `0.1.0~preview1`, `0.1.0~preview2`, `0.1.0~preview3`, then `0.1.0`, etc. Update the matching README download links, Linux guide and release notes. A `~preview` sorts before its final version. The root `VERSION` belongs to Mac and stays unchanged for a Linux-only update.
2. Update the beginner guide and validation record. Never call an untested build Raspberry Pi validated.
3. Run the automated suite and shell syntax checks. Build using `python3 packaging/build_linux.py`. The builder needs only Python and can run on macOS. No compilation on the user's Pi is required.
4. On a Linux test host, inspect/install the .deb, run the namespace test, and validate the real Pi Wi-Fi/Ethernet delivery check. Before the first stable release, test an initial install (stopped/disabled), full-mode acquisition/renewal, compatibility-only mode, cable unplug/replug, Wi-Fi loss/recovery, power cycle, active-service upgrade, stopped-service upgrade, enabled/disabled boot preference preservation, and deliberate downgrade. Save the observations; synthetic tests aren't a replacement for these.
5. Attach the versioned `_all.deb`, the beginner bundle and `SHA256SUMS.txt` to the GitHub release. Source is available in the repo and bundle. Do not commit binary release assets into the source folder, publish private profiles, or replace an existing version's assets with different bytes.
6. In release notes, say what changed, who should update, known limits, and the one update command. The same wrapper accepts initial install or `--update`. The .deb scripts preserve generated settings/leases and restart only a previously active service; they do not enable first installations automatically.

A manually downloaded .deb can be upgraded with `sudo apt install ./keep-your-e3200_VERSION_all.deb`. A future signed apt repository can automate checking for updates, but is not needed for an initial GitHub project. Do not add an unauthenticated updater running downloaded code as root.

## GitHub workflow

**Build Linux and Raspberry Pi preview** runs for relevant pushes/pull requests and can also be run manually. It checks the source, inspects the built .deb, verifies checksums and runs the packet test in isolated Linux virtual networks. Those checks do not start the helper on a home network or prove real-radio/reboot behavior. Downloads are retained as workflow artifacts.

Normal pushes do **not** publish a release. To publish after review, manually run the workflow with **publish** enabled. That input defaults to false. Publishing waits for the build checks, downloads the already-built artifacts, verifies their checksums, and creates a **prerelease** such as `linux-v0.1.0-preview3` with `--latest=false`. It does not overwrite the Mac latest release or replace existing assets under the same tag. [GitHub CLI release flags](https://cli.github.com/manual/gh_release_create).

The Mac release trigger watches only its own version, builder and release notes. Linux package/build changes do not trigger a Mac release. Before publication, check the workflow run for the reviewed source commit and confirm that all build/packet tests passed. A local workflow definition is not evidence of a completed CI run; link actual results in the validation record.

The portable preview bundle uses NetworkManager already provided by current Pi OS. Other network managers are not configured or replaced by its installer. The executable program is architecture-independent Python; distro libraries supply the native ARM64/x86-64 pieces. The preview intentionally requires a 64-bit OS because the packet-capture ABI has not been validated on 32-bit time64 systems.
