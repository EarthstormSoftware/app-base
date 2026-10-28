"""A light whose output draws itself (a Pico's LED strip): one paint per change, effects drawing into the strip with
the level, and nothing drawn while nothing changes."""
import asyncio

from base.light import Light, LIGHT_SETTINGS
from base.settings import Settings, merge


class Strip:
    """What effects draw into."""
    def __init__(self):
        self.frames = []


class Output:
    count = 3

    def __init__(self):
        self.strip = Strip()
        self.calls = []

    def paint(self, colour, level):
        self.calls.append(('paint', tuple(colour), round(level, 3)))

    def clear(self):
        self.calls.append(('clear',))


class Sparkle:
    def __init__(self, count, parameters, light):
        self.speed = None

    def frame(self, strip, level):
        strip.frames.append((self.speed, round(level, 3)))
        return 10


def light(tmp_path, on=True):
    settings = Settings(str(tmp_path / 'config.json'), merge(LIGHT_SETTINGS))
    settings.update({'device': {'default_state': on, 'transition_ms': 0, 'default_brightness': 100}})
    return Light(Output(), settings, {'Sparkle': Sparkle})


def run_for(lt, ms):
    async def go():
        task = asyncio.create_task(lt.run())
        await asyncio.sleep(ms / 1000)
        task.cancel()
    asyncio.run(go())


def test_a_still_colour_is_painted_once(tmp_path):
    lt = light(tmp_path)
    run_for(lt, 150)
    assert lt.output.calls == [('paint', (255, 180, 107), 1.0)]


def test_off_clears_once(tmp_path):
    lt = light(tmp_path, on=False)
    run_for(lt, 100)
    assert lt.output.calls == [('clear',)]


def test_an_effect_draws_into_the_strip_with_its_speed_and_the_level(tmp_path):
    lt = light(tmp_path)
    lt.set(mode='Sparkle', parameters={'Speed': 7}, brightness=100, transition_ms=0)
    run_for(lt, 100)
    frames = lt.output.strip.frames
    assert len(frames) >= 3  # every 10 ms, as it asks
    assert frames[0] == (7, 1.0)
    assert lt.output.calls == []  # it drew; the light didn't paint over it


def test_an_alert_flashes_with_paints_only_as_it_changes(tmp_path):
    lt = light(tmp_path)
    lt.alert(colour='#ff0000', seconds=1, on_ms=50, off_ms=50, brightness=100, test=True)
    run_for(lt, 180)
    paints = [c for c in lt.output.calls if c[0] == 'paint']
    assert paints[0] == ('paint', (255, 0, 0), 1.0)
    assert ('paint', (0, 0, 0), 0) in paints
    assert len(paints) <= 6  # one per change, not one per frame


class Twinkle:
    """An effect with defaults: the state shows them, as PlasmaStick's does."""
    def __init__(self, count, parameters, light):
        pass

    @staticmethod
    def defaults(light):
        return {'Speed': light.speed(), 'Style': 'Twinkle'}


def test_the_state_shows_an_effects_defaults_unless_given(tmp_path):
    settings = Settings(str(tmp_path / 'config.json'), merge(LIGHT_SETTINGS))
    lt = Light(Output(), settings, {'Twinkle': Twinkle})
    lt.set(mode='Twinkle')
    assert lt.state()['ModeParameters'] == {'Speed': 5, 'Style': 'Twinkle'}
    lt.set(parameters={'Speed': 8})
    assert lt.state()['ModeParameters'] == {'Speed': 8, 'Style': 'Twinkle'}
