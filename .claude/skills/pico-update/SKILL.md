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
   with `*>&1` (the scripts print with Write-Host, which `2>&1` misses) and every line passed through
   `ForEach-Object { "$_".Replace($PicoIp, '<ip>') }`, and wait for the notification.
4. Report what it sent and removed, the version the device came back on and its free memory (`/api/info`'s
   `mem_free`). Suggest `/pico-check` next.

When it fails, read the device's answer before retrying:
- `not a firmware file` for `*.gz`: the device's updater predates gzipped web files. Send one update without them
  first (the code, with the plain `www` files from `src/` in their place), then the full one.
- `HTTP 500 ... ValueError` on begin: an early 2.0 can't read a manifest over 1 KB (about 8 files). Send
  `base/pico/web.mpy` and `base/pico/ota.mpy` alone first; after that it takes any size (hallway, 2026-10-28).
- `not enough space`: the update needs its files in whole 4 KB blocks, its folders (two blocks each) and 16 KB,
  while the old version is still there. Don't split it into batches that leave the new files beside the old ones: that fills the flash (it happened on a 1.4.4
  PlasmaStick). Use USB (`/pico-usb`) instead.
- A PlasmaStick on 1.4.2 (to 1.4.4) can't take 2.0 in one go: it reads each file whole, can't read a manifest
  over 1 KB, and its flash (640 KB, every file at least a 4 KB block) has no room for 1.4 and 2.0 side by side.
  Done on porch, kitchen-left and kitchen-right, 2026-10-28. The bridge's `wifi_update.py` (branch
  `bridge-1.4.3`, which has `--only` and `--remove`) with the bridge build's `files.json` for steps 1-2, and the
  product's `app-base` build for 3-4:
  1. `--only ota.mpy,httpserver.mpy,version.mpy` takes it to 1.4.5. 1.4.2 needs 6 KB in one piece for
     httpserver: restart it first, and if it still fails ("Bad request" or a dropped connection), turn its MQTT
     off (POST /api/config `{"mqtt": {"enabled": false}}`, restart): 88 KB free instead of about 60. Turn it on
     again once it's on 2.0 (POST `{"mqtt": {"enabled": true}}`, restart).
  2. `--only www/index.html.gz --remove www/index.html` (frees about 40 KB).
  3. 2.0's files that 1.4 doesn't use, 8 at a time with the bridge updater and the 2.0 build: every path in
     `files.json` but app, asynchttp, effects, lib/mqtt_as/__init__, version and www/index.html.gz. 1.4 runs on.
     (One whole 2.0 update makes a manifest of about 5 KB, which 1.4.5 can't reliably read.)
  4. The product's own `wifi_update.py`, as normal: it swaps the rest and removes 1.4's modules in one small update.
  Don't send 1.4.2 a whole build: the `.mpy` files embed their source path, so a build from another folder differs
  in every file.
- No answer after the restart: a Pico can take several minutes to rejoin Wi-Fi. Check `/api/info`'s uptime before
  calling it lost; the updater puts the old version back by itself if the new one doesn't start.

Never print the passwords, the IP address or the Wi-Fi name, and don't commit anything from `build\`.
