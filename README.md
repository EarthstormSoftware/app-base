# App Base

What the Earthstorm devices have in common, written once: the web page and JSON API, settings, MQTT and Home
Assistant, a light model with modes, fades, alerts, groups and a schedule, and the page's shared style and script.
It runs under CPython, for [Juggle OS](https://github.com/EarthstormSoftware/juggle-os) apps, and under MicroPython
on a Pico W, where it also does what the OS does on a Pi (Wi-Fi, setup mode, updates over Wi-Fi, the clock).

[PlasmaStick Controller](https://github.com/EarthstormSoftware/plasmastick-controller) (a light) and
[Pico PIR](https://github.com/EarthstormSoftware/pico-pir) (a sensor) run on it on a Pico W. A new product starts from
[Juggle Hello](https://github.com/EarthstormSoftware/juggle-hello) (a Juggle OS app) or [Pico Hello](https://github.com/EarthstormSoftware/pico-hello) (a Pico W),
each the smallest product on the base. The design and the steps are in [docs/roadmap.md](docs/roadmap.md).

## What's in it

| Module | Does |
|---|---|
| `device.py` | Puts a product together and runs it: `run(product)` |
| `settings.py` | Settings with defaults and checks, saved as JSON whole or not at all |
| `web.py`, `www/` | The page's routes and the API, with the cross-site check and the optional password; the shared style and script |
| `light.py` | The light model: on or off, a mode with parameters, brightness, fades, alerts |
| `mqtt.py`, `mqttclient.py` | MQTT (state, commands, alerts, groups, Home Assistant discovery) and a small asyncio client |
| `schedule.py` | The schedule: events at times, or at sunrise or sunset |
| `pi.py` | The platform on Juggle OS: the state folder, the Pi's name, health and clock |
| `pico/` | The platform on a Pico W: Wi-Fi with the fallback to setup mode, setup mode's hotspot and page, updates over Wi-Fi with a rollback (`otaboot.py` goes on the board's root), NTP and local time, the watchdog, BOOTSEL and the LED, the MQTT client (mqtt_as, from the product's `lib/`), and its own routes. It keeps a device's files as the firmware before the base did |
| `compat.py` | The differences between CPython and MicroPython |
| `microdot.py` | [Microdot](https://github.com/miguelgrinberg/microdot), the web server |

## A product

A product is a module, `product.py`, with hooks the base calls:

```python
NAME = 'Unicorn'
VERSION = '0.1.0'
SETTINGS = {'device': {'rotation': Setting(0, is_one_of(0, 90, 180, 270))}}   # its own, next to the base's
LIGHT_MODES = {'Rainbows': Rainbows}   # a light: its effects beyond Colour

def output(device): ...    # a light: its LEDs (count, show(frame))
```

and optionally:

- `MANUFACTURER` and `MODEL` (for Home Assistant), `RESET_KEEPS` (settings a reset keeps), `www` (its page's folder)
- `info(device)`, `routes(app, device)`, `applied(device, changed)`, `tasks(device)`
- `mqtt_topics(device)` and `mqtt_message(device, topic, text)`; not a light: `state(device)`, `set(device, command)`,
  `scheduled(device, on)`, and `HA_ENTITIES` with `ha_entity(device, key, topics)`
- a light: `MIN_LEVEL`, `MODE_ORDER`
- on a Pico: `SETUP_SSID` and `NAME_PREFIX` (required), `setup_held()`, `Codec` (a settings file laid out its own way)

`device.py` says what each does, and what a product may use of the device: `settings`, `change(updates)` (settings
changed as the page does), `state_changed()`, `light`, `info()` and `platform`. Its `main.py` is
`import product; from base.device import run; run(product)` (on a Pico, through `app.py`), and its page
(`www/index.html`) uses `/base.css` and `/base.js`.

## Using it in a product

A product keeps a copy of the base, not a submodule, so a plain clone or a ZIP of it works:

```powershell
..\app-base\update-base.ps1 -Product app            # this working copy, while developing both
..\app-base\update-base.ps1 -Product app -Tag v0.1.0   # a release
```

That writes `base\VERSION` with where it came from and each file's SHA-256. The product's tests check the copy
against it, so the copy isn't edited in the product: a fix goes in here first.

## Tests

`py -m pytest` (Python 3.11 or later).

## Licence

MIT. See [LICENSE](LICENSE). Microdot is MIT too: see [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).
