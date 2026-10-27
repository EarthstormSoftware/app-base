# App Base

What the Earthstorm devices have in common, written once: the web page and JSON API, settings, MQTT and Home
Assistant, a light model with modes, fades, alerts, groups and a schedule, and the page's shared style and script.
It runs under CPython, for [ApplPi OS](https://github.com/EarthstormSoftware/applpi-os) apps, and is written to run
under MicroPython on a Pico W too (that layer comes next).

Its first user is [ApplPi Unicorn](https://github.com/EarthstormSoftware/applpi-unicorn). The design and the steps
are in [docs/roadmap.md](docs/roadmap.md).

## What's in it

| Module | Does |
|---|---|
| `device.py` | Puts a product together and runs it: `run(product)` |
| `settings.py` | Settings with defaults and checks, saved as JSON whole or not at all |
| `web.py`, `www/` | The page's routes and the API, with the cross-site check and the optional password; the shared style and script |
| `light.py` | The light model: on or off, a mode with parameters, brightness, fades, alerts |
| `mqtt.py`, `mqttclient.py` | MQTT (state, commands, alerts, groups, Home Assistant discovery) and a small asyncio client |
| `schedule.py` | The schedule: events at times, or at sunrise or sunset |
| `pi.py` | The platform on ApplPi OS: the state folder, the Pi's name, health and clock |
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

and optionally `MANUFACTURER` and `MODEL` (for Home Assistant), `info(device)`, `routes(app, device)`,
`applied(device, changed)`, `tasks(device)`, `mqtt_topics(device)` and `mqtt_message(device, topic, text)`.
`device.py` lists them. Its `main.py` is `import product; from base.device import run; run(product)`, and its page
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
