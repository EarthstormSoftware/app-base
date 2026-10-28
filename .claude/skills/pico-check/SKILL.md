---
name: pico-check
description: Check a running Pico device over the network - the product's smoke test (HTTP, page, MQTT, Home Assistant), its free memory, and an optional soak that watches for restarts. Use after an update or a change on a device.
argument-hint: "<plasmastick|picopir> <device name or IP> [soak seconds]"
---

Check a Pico device. Arguments: $ARGUMENTS (the product, the device, and optionally a soak length in seconds).

1. In one PowerShell call, dot-source
   `E:\Projects\EarthstormSoftware\app-base\tools\pico-session.ps1 -Product <product> -Device <device>`, then run
   `py "$PicoRepo\scripts\smoke_test.py" --host $PicoIp` (add `--soak <seconds>` if given) in the background,
   with `*>&1` and every line passed through `ForEach-Object { "$_".Replace($PicoIp, '<ip>') }`. Wait for the notification.
2. Before testing a device people use (a kitchen light, say), ask the user whether anyone is using it:
   a press of its button or a Home Assistant command during the test looks like a failed check.
   Report the PASS/FAIL/SKIP counts and quote each FAIL. Known baseline: a PlasmaStick in an MQTT group with other
   lights fails the brightness checks, because the group sets it back. Say so rather than calling it a regression.
3. Report the version, uptime and `mem_free` from `/api/info`. Compare the free memory with the last figure in the
   project's notes (about 66 KB for Pico PIR 2.0 on hallway, about 45 KB for PlasmaStick 2.0 on porch at rest, 37 KB animating); a drop of more than 5 KB needs a reason.
4. During a soak, an uptime that goes down means a restart: say when, and suggest `/pico-usb <product> log` to find
   out why.

Never print the passwords, the IP address or the Wi-Fi name.
