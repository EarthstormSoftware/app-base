---
name: pico-usb
description: Inspect a Pico connected by USB (its files and free flash), deploy a product's firmware to it with deploy.ps1, and read its start-up log. Use when a device needs USB: a first install, an update too big for Wi-Fi, or one that doesn't start.
argument-hint: "<plasmastick|picopir> [inspect|deploy|log]"
---

Work with a Pico on USB. Arguments: $ARGUMENTS (the product, then what to do: `inspect` only looks, `log` only reads
the start-up log, and `deploy`, the default, does all three in order).

1. Find the board: `py -m mpremote connect list` (Raspberry Pi's USB ID is 2e8a). If there's none, ask the user to
   plug it in; if there are several, ask which port.
2. **Inspect** before changing anything: with `py -m mpremote run` and a short script, print `os.statvfs('/')` as
   total and free KB, then every file with its size, grouped by folder (`update/` and `prev/` are a Wi-Fi update's
   staging and backups). Say what takes the space. Don't print `config.json`, `provisioning.json` or anything under
   `secrets`: their contents are the device's Wi-Fi and passwords.
3. **Deploy:** from the product's folder (`E:\Projects\EarthstormSoftware\plasmastick-controller` or `...\pico-pir`,
   on the branch the user wants), run `.\scripts\deploy.ps1` in the background and wait. It keeps the device's
   settings, name and Wi-Fi, and removes files the new version doesn't have. Never pass `-ResetConfig`, `-Wipe` or
   `-PreserveProvisioning:$false` unless the user asked for that.
4. **Log:** `py scripts\device_log.py --reset --until-ready --seconds 120 --quiet` and report its SUMMARY,
   MILESTONE, HEAP and PROBLEM lines. Lines can carry the Wi-Fi name or addresses: quote only what's needed and
   blank those out.
5. After a deploy, inspect again for the free flash, and suggest `/pico-check`.
