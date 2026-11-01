# Roadmap

App Base is what the Earthstorm devices have in common, taken out of the projects that copy it today: PlasmaStick
Controller and Pico PIR (MicroPython on a Pico W) share about 1,600 identical lines and about 1,000 more that do the
same jobs but have drifted apart. Juggle apps (CPython on a Pi running Juggle OS) need the same web page, settings,
API and MQTT. Each fix should be made once.

## Design

### Two layers

- **Portable** (MicroPython and CPython): the web server (Microdot) with the cross-site check and the optional
  password; settings with defaults, checks and atomic saves; the `/api/info` and `/api/config` conventions; the
  page's shared style and script (tabs, health chips, forms); MQTT with the retained `status`, `info` and `state`
  topics and Home Assistant discovery; logging; password hashing; a light model (below).
- **Pico** (MicroPython only): Wi-Fi and the setup hotspot, the captive DNS, Wi-Fi updates and their rollback, the
  watchdog, NTP and the clock, the BOOTSEL button, the onboard LED. On a Pi, Juggle OS does all of these.

Small differences between the two Pythons (`asyncio` and `uasyncio`, `binascii`, ticks, `gc`) are kept in one
`compat` module, so the rest is written once.

### The same on a Pico and a Pi

Whatever a Pico product's page can change, a Juggle app's can too, through the base, so a product works the same
on either. Where Juggle OS owns the setting, the base asks it (below):

| On the page | Pico | Juggle app |
|---|---|---|
| The product's own settings, MQTT, the web password, the log level | The product | The same (the app's state, `/data/app-state`) |
| Updates over the network (`/api/update`, `deploy.ps1 -WiFi`), with a trial and going back by itself | The Pico layer | Juggle OS installs the new app, which has to keep running, or it puts the old one back |
| Restart | The board | The app (systemd starts it again); a Pi restart too |
| Reset settings | The product | The same (the app's state) |
| The clock: NTP server, time zone | Offset and summer time rule | Juggle OS's time zone (a name, as at flashing) and NTP server |
| The watchdog (a stalled event loop restarts it) | The board's hardware watchdog | systemd's watchdog for the app (`WatchdogSec`, the base telling it the loop is alive); the Pi's hardware watchdog stays the OS's |
| The device name | The product | Shown; changed in Juggle OS's setup mode, which the page restarts into (`/api/setup-mode`): it's the Pi's network name, which SSH and `juggle` know it by |
| Factory reset (forgets Wi-Fi) | Starts setup mode | `/api/factory-reset`: Juggle OS forgets its settings and starts setup mode (its hotspot and HTTPS setup page) |
| Wi-Fi network | Setup mode only | The same: Juggle OS's setup mode, or flashing |
| The Wi-Fi fallback: setup mode when Wi-Fi doesn't connect (on or off, after how many minutes, for how many) | The Pico layer (now a fixed 5 attempts, and 10 minutes; to come with Pico PIR) | `/api/wifi`: Juggle OS's `wifi_fallback` setting (`app-request wifi-fallback`), used at the next start |

Juggle OS's setup mode is its roadmap's step 7 (in the release after v0.4): the page offers the name, Wi-Fi fallback
and factory reset only on an OS that has it (`os.setup` in /api/info, `data-os-setup` on the page). Before that, the
name and Wi-Fi are set when flashing.

Juggle OS needs a few things for this (its roadmap's next step): a way for the app, which normally isn't root, to
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
reconnects. paho-mqtt was the first thought, but it isn't in Juggle OS's image, runs its own thread, and is far
bigger than what's needed.

### How products use it

A copy, not a git submodule (decided 2026-10-27): each product keeps the base in `src/base/`.

- A product's repo then works from a plain clone or GitHub's "Download ZIP" (both leave submodules out), and a base
  update is one commit in the product whose diff is the actual change. No `--recursive`, no detached HEAD, no pushing
  two repos in the right order. The Pico's deploy script compiles the copy to `.mpy` as it does the rest of `src/`;
  a Juggle app's `deploy.ps1` sends it with the app. Each product moves to a new base when it suits it (after
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
`juggle-unicorn` needs them. That app is the first user, so the hooks are shaped by a real product.

### 2. Pico PIR onto the base

Its shared code replaced by the vendored base; the Pico layer moves into the base. It gains the schedule (sensing on
or off). Checked on the device.

Decided (2026-10-28):
- **The Pico layer** is `base/pico/`: Wi-Fi (`wlan`), setup mode (`setup`, with the captive DNS), Wi-Fi updates
  (`ota`), NTP and the clock, the watchdog, BOOTSEL and the onboard LED, the name and the stored-password encryption.
  The package itself (`base/pico/__init__.py`) is the platform, as `base/pi.py` is on a Pi. A Juggle app's copy
  carries the folder unused, and a Pico's leaves out `pi.py` and `mqttclient.py`.
- **Devices carry on as they are.** A Pico on the base reads the files it has now: `config.json` in the same layout
  (the web password as `password_hash`, the MQTT password encrypted as `password_iv` and `password_enc`), and
  `provisioning.json` (Wi-Fi) and `device_name.json` beside it. It writes them the same way, so an update that rolls
  back leaves a device the old firmware can still read. `Settings` gets a codec for this (from and to the file),
  and a secret can have a `reveal` (the MQTT password is decrypted only to connect).
- **The same topics and Home Assistant entities**, so Home Assistant keeps its history: `<base>/state` and `<base>/set`
  for a product that isn't a light, through new hooks (`state`, `set`, `ha_entities`), and the unique ids as now.
- **The Wi-Fi fallback** becomes three settings in `wlan` (`fallback`, `fallback_after_min`, `fallback_for_min`), as
  Juggle OS's `wifi_fallback`: on, after 360 minutes (up to 1440: a router can be slow back after a power cut), for
  10 minutes. The page shows them through `/api/wifi`, as on a Pi.
- **Changing Wi-Fi from the page** (asked for on 2026-10-28: setup mode shouldn't be the only way): on a Pico,
  `POST /api/wifi` with a network restarts onto it, on trial. If it doesn't connect within 5 minutes, the network
  before goes back. A network from setup mode is on the same trial, and goes back to setup mode, so a mistyped
  password doesn't wait for the fallback's hours. On a Pi it needs the OS to take a new network from the app, so it's
  Juggle OS's to add (an `app-request wifi`); until then a Pi's page uses setup mode for it.
- **Setup mode from the page**: `/api/setup-mode` and `/api/factory-reset` as on a Pi, and the name through
  `/api/name` (a Pico's name is its own to change, `name_editable`).
- **The clock**: on a Pico, its settings (`device.utc_offset_min`, `dst`, `ntp_server`) are ordinary settings on the
  page; `/api/clock` is a Pi's, where the OS has them.
- **Getting there over Wi-Fi.** A device's current updater only writes `/`, `lib`, `lib/mqtt_as` and `www`, so
  first a bridge release that only lets it write `base/` too (one file, `ota.mpy`), then the release on the base.
  `main.py` and `otaboot` stay as they are (USB only): `main.py` still imports `app`, which becomes
  `run(product)`.
- **Memory**: a sensor on the base loads about 70 KB of bytecode, against about 59 KB before, so about 10 KB less
  heap than the 80-90 KB free now. Measured on the device; if it's short, the light parts of `mqtt.py` move out so
  a sensor doesn't load them.

### 3. PlasmaStick onto the base

The same, including its light model, groups (on the new topic, and the old one for this version) and schedule.
Checked on the device.

### 4. A template

A minimal product of each kind (Pico and Juggle), to start new ones from.

Done (2026-10-30), on v0.4.0: **Juggle Hello** (the example Juggle OS app, rebuilt on the base) and **Pico Hello** (a
new repo). Each has one setting, a greeting, on its page, the API, its MQTT state and set topics and in Home
Assistant (a text box), with the base's Device and MQTT tabs (and a Pico's Network tab), deploys over USB or SSH and
over the network, and tests; their READMEs say how to start a new product from them. Checked: Juggle Hello on a Pi 2
(all of Juggle OS's checks, the greeting from the API, an update over the network keeping it), Pico Hello on a new
Pico W (setup mode, the page, the web password, two updates over Wi-Fi; about 96 KB of heap free at rest). Pico
Hello's `wifi_update.py` reaches a `.local` name by its IPv4 address: with Python 3.14 on Windows, an IPv6 link-local
address fails to connect, and PlasmaStick's and Pico PIR's copies need the same fix.

### 5. 1.0

What a product, a page or a client relies on, read through as Juggle OS's app contract was (2026-11-01), so 1.x only
adds to it: the product's hooks and the `base.*` names it imports, the HTTP API, the MQTT topics and payloads and the
Home Assistant ids, the settings files, and what a page uses of `base.js` (`Base.*`, the `data-*` attributes and the
shared tabs). Everything must still fit the smallest Pico. Changed before the freeze:

- **The hooks, all listed**: `device.py`'s list was missing `RESET_KEEPS` and a Pico's `SETUP_SSID` and
  `NAME_PREFIX`, and the README's half of them.
- **Juggle OS by `JUGGLE` only**: `pi.py` no longer looks for `app-request` or reads it, which the app contract
  rules out; a Juggle app on App Base 1.0 needs Juggle OS 1.0.
- **No `plasmastick/group/`**: the bridge for PlasmaStick before App Base; every PlasmaStick is on it now.
- **The light's own API**: `light.remake()` (an effect made again, for a product whose settings change how it
  draws) and `light.listeners`, so no product touches the light's private parts (PlasmaStick did).
- **`device.change(section, values)`**: a product's settings changed from MQTT (or anywhere but the page) as the page
  does it, applied, published, and with a restart for one that needs it. Each product did the first two itself, and
  none restarted.
- **The shared tabs come from the base**: the Device, MQTT and (on a Pico) Network tabs were about 155 lines copied
  into every product's page, outside the copy check; the page now says where they go.
- **One key style**: the light's MQTT payloads and the mode parameters are snake_case, as the HTTP API and the
  settings are (`{"state", "mode", "parameters", "brightness"}`, `colour`, `speed`, ...). They were PlasmaStick 1.x's
  (`"State"`, `"ModeParameters"`). The modes' names stay as they are (Home Assistant shows them as effects).
- **`home/device/{name}`** as the default topic base, without the leading slash (an empty first level, which `home/#`
  doesn't match). A device keeps the topic base it has saved; the Earthstorm devices were moved to it by hand.
- **`os` in a Pi's `/api/info`** (`version`, `build`, `slot`) comes from files outside the app contract, so each may
  be null. They could join the contract in a Juggle OS minor release.
