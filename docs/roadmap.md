# Roadmap

App Base is what the Earthstorm devices have in common, taken out of the projects that copy it today: PlasmaStick
Controller and Pico PIR (MicroPython on a Pico W) share about 1,600 identical lines and about 1,000 more that do the
same jobs but have drifted apart. ApplPi apps (CPython on a Pi running ApplPi OS) need the same web page, settings,
API and MQTT. Each fix should be made once.

## Design

### Two layers

- **Portable** (MicroPython and CPython): the web server (Microdot) with the cross-site check and the optional
  password; settings with defaults, checks and atomic saves; the `/api/info` and `/api/config` conventions; the
  page's shared style and script (tabs, health chips, forms); MQTT with the retained `status`, `info` and `state`
  topics and Home Assistant discovery; logging; password hashing; a light model (below).
- **Pico** (MicroPython only): Wi-Fi and the setup hotspot, the captive DNS, Wi-Fi updates and their rollback, the
  watchdog, NTP and the clock, the BOOTSEL button, the onboard LED. On a Pi, ApplPi OS does all of these.

Small differences between the two Pythons (`asyncio` and `uasyncio`, `binascii`, ticks, `gc`) are kept in one
`compat` module, so the rest is written once.

### The same on a Pico and a Pi

Whatever a Pico product's page can change, an ApplPi app's can too, through the base, so a product works the same
on either. Where ApplPi OS owns the setting, the base asks it (below):

| On the page | Pico | ApplPi app |
|---|---|---|
| The product's own settings, MQTT, the web password, the log level | The product | The same (the app's state, `/data/app-state`) |
| Updates over the network (`/api/update`, `deploy.ps1 -WiFi`), with a trial and going back by itself | The Pico layer | ApplPi OS installs the new app, which has to keep running, or it puts the old one back |
| Restart | The board | The app (systemd starts it again); a Pi restart too |
| Reset settings | The product | The same (the app's state) |
| The clock: NTP server, time zone | Offset and summer time rule | ApplPi OS's time zone (a name, as at flashing) and NTP server |
| The watchdog (a stalled event loop restarts it) | The board's hardware watchdog | systemd's watchdog for the app (`WatchdogSec`, the base telling it the loop is alive); the Pi's hardware watchdog stays the OS's |
| The device name | The product | Shown; changed in ApplPi OS's setup mode, which the page restarts into (`/api/setup-mode`): it's the Pi's network name, which SSH and `applpi` know it by |
| Factory reset (forgets Wi-Fi) | Starts setup mode | `/api/factory-reset`: ApplPi OS forgets its settings and starts setup mode (its hotspot and HTTPS setup page) |
| Wi-Fi network | Setup mode only | The same: ApplPi OS's setup mode, or flashing |
| The Wi-Fi fallback: setup mode when Wi-Fi doesn't connect (on or off, after how many minutes, for how many) | The Pico layer (now a fixed 5 attempts, and 10 minutes; to come with Pico PIR) | `/api/wifi`: ApplPi OS's `wifi_fallback` setting (`app-request wifi-fallback`), used at the next start |

ApplPi OS's setup mode is its roadmap's step 7 (in the release after v0.4): the page offers the name, Wi-Fi fallback
and factory reset only on an OS that has it (`os.setup` in /api/info, `data-os-setup` on the page). Before that, the
name and Wi-Fi are set when flashing.

ApplPi OS needs a few things for this (its roadmap's next step): a way for the app, which normally isn't root, to
ask it to install a new app version (with the trial and going back), set the time zone and NTP server, restart
the Pi, and start setup mode, and nothing else. For example, `sudo` allowed for the `app` user on those commands only.

### Products as plugins

Not a framework: a product is a module with hooks the base calls, as `product.py` is now. It gives:
- its name, version and default settings, and the checks for its own settings;
- which settings need a restart;
- its status fields for `/api/info`, its extra API routes and its MQTT control messages;
- its Home Assistant entities;
- its page's own tabs, around the shared ones.

### The light model

PlasmaStick and the Unicorn HAT are both lights: on or off, a mode with its parameters (`Colour`, `Kelvin`,
`Speed`, ...), a brightness, fades between them, and Home Assistant's JSON light schema with the modes as effects.
That moves from PlasmaStick into the base, with the product giving its modes and drawing them on its LEDs.

**Alerts** are too (asked for on 2026-10-27): with alerts switched on, an alert interrupts the light, on or off,
flashing a colour for a while, and then it carries on as it was; from the API, MQTT, Home Assistant (a button and a
switch) or another device's topic that the light watches (motion starting rings once). See the Unicorn's roadmap.

**Groups** are part of the light model: lights given the same group name follow each other through a retained MQTT
topic (power, mode, the colour in Colour mode, and the brightness unless that's turned off), and a member that
starts or joins takes the group's state. Being in the base, different products can share a group (the Unicorn HAT
following a PlasmaStick). The topic becomes product-neutral, `earthstorm/group/<group>`; PlasmaStick also listens on
its old `plasmastick/group/<group>` for one version, so existing groups carry on while devices are updated. A member
keeps power and brightness in step and ignores a mode it doesn't have (and its parameters), as members already
ignore what doesn't apply to them.

### The schedule

Any product can have one (decided 2026-10-27): up to 8 events, each on chosen days at a time, or at sunrise or
sunset plus or minus some minutes (from the device's location), and after a restart, once the clock is set, the
latest event's action is done, so a power cut doesn't leave things wrong. The engine is the base's (`schedule.py`, with the page's editor in `base.js`); the actions are
the product's: the light model gives on, off, a mode and a brightness, and Pico PIR (its first other user) sensing on
or off. The clock comes from the platform: NTP with an offset and summer time rule on a Pico, the OS's NTP and time
zone on a Pi; the base only asks it for the local time.

### MQTT

The same topics, messages and Home Assistant discovery on both. The client differs: `mqtt_as` on the Pico (it needs
MicroPython's `network`), and on CPython the base's own small asyncio client (`mqttclient.py`, MQTT 3.1.1, about 200
lines), behind the same few calls (connect with a will, publish, subscribe, the next message, close); `base.mqtt`
reconnects. paho-mqtt was the first thought, but it isn't in ApplPi OS's image, runs its own thread, and is far
bigger than what's needed.

### How products use it

A copy, not a git submodule (decided 2026-10-27): each product keeps the base in `src/base/`.

- A product's repo then works from a plain clone or GitHub's "Download ZIP" (both leave submodules out), and a base
  update is one commit in the product whose diff is the actual change. No `--recursive`, no detached HEAD, no pushing
  two repos in the right order. The Pico's deploy script compiles the copy to `.mpy` as it does the rest of `src/`;
  an ApplPi app's `deploy.ps1` sends it with the app. Each product moves to a new base when it suits it (after
  testing on its device).
- `update-base.ps1` (in this repo, run from a product) copies a tagged release into the product's `src/base/` and
  writes `src/base/VERSION`: the tag, the commit and each file's SHA-256. `-From ..\app-base` copies a local working
  copy instead (recorded as such), for developing the base and a product together; a tagged release is copied in
  before the product is released.
- The copy isn't edited in a product: each product's tests check `src/base/` against `VERSION` and fail if it has
  been changed, so a fix goes into this repo first.
- A submodule would suit a large base that changes daily with several people on it; this isn't that.

### Tests

Host-side pytest for the portable layer under CPython, as the Pico projects already do with stand-ins for
MicroPython's modules, so most of it is tested without a device.

## Steps

### 1. The portable layer, with the Unicorn HAT app

Taken from Pico PIR (the newer of the two), and the light model, groups and the schedule from PlasmaStick, as
`applpi-unicorn` needs them. That app is the first user, so the hooks are shaped by a real product.

### 2. Pico PIR onto the base

Its shared code replaced by the vendored base; the Pico layer moves into the base. It gains the schedule (sensing on
or off). Checked on the device.

### 3. PlasmaStick onto the base

The same, including its light model, groups (on the new topic, and the old one for this version) and schedule.
Checked on the device.

### 4. A template

A minimal product of each kind (Pico and ApplPi), to start new ones from.
