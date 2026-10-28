---
name: pico-update
description: Build a Pico product (PlasmaStick, Pico PIR) and update a device over Wi-Fi, keeping passwords and addresses out of the output. Use whenever new firmware goes to a Pico on the network.
argument-hint: "<plasmastick|picopir> <device name or IP>"
---

Update a Pico device over Wi-Fi. Arguments: $ARGUMENTS (the product, then the device: a name such as `hallway`,
looked up as `hallway.local`, or an IP address).

1. In one PowerShell call, dot-source the session helper and build:
   `. E:\Projects\EarthstormSoftware\app-base\tools\pico-session.ps1 -Product <product> -Device <device>` and then
   `& "$PicoRepo\scripts\deploy.ps1" -BuildOnly`. Stop if a password is not set or the device doesn't resolve,
   and say which.
2. Say what is going: the product's version (`src/version.py` or `product.py`), the branch, and the total size from
   the build's "KB in all" line.
3. In the same kind of call (the variables don't outlive a call), run
   `py "$PicoRepo\scripts\wifi_update.py" --host $PicoIp --files "$PicoRepo\build\files.json"` in the background,
   with every line passed through `ForEach-Object { "$_".Replace($PicoIp, '<ip>') }`, and wait for the notification.
4. Report what it sent and removed, the version the device came back on and its free memory (`/api/info`'s
   `mem_free`). Suggest `/pico-check` next.

When it fails, read the device's answer before retrying:
- `not a firmware file` for `*.gz`: the device's updater predates gzipped web files. Send one update without them
  first (the code, with the plain `www` files from `src/` in their place), then the full one.
- `not enough space`: the update needs its size plus 16 KB free while the old version is still there. Don't split
  it into batches that leave the new files beside the old ones: that fills the flash (it happened on a 1.4.4
  PlasmaStick). Use USB (`/pico-usb`) instead.
- A PlasmaStick before 1.4.5 can't read a manifest over 1 KB or list many files: update it to 1.4.5 first (the
  `bridge-1.4.3` branch: only `ota`, `httpserver` and `version` change), then to 2.0 in one update.
- No answer after the restart: a Pico can take several minutes to rejoin Wi-Fi. Check `/api/info`'s uptime before
  calling it lost; the updater puts the old version back by itself if the new one doesn't start.

Never print the passwords, the IP address or the Wi-Fi name, and don't commit anything from `build\`.
