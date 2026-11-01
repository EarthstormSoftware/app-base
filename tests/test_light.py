import pytest

from base import light as light_module
from base.light import Light, LIGHT_SETTINGS
from base.settings import Settings, merge


class Output:
    count = 4

    def show(self, frame):
        self.frame = frame


class Finishes:
    """An effect that ends after its first frame."""

    def __init__(self, count, parameters, light):
        self.finished = False

    def frame(self, now):
        self.finished = True
        return [(255, 255, 255)] * 4


@pytest.fixture
def clock(monkeypatch):
    now = [1000]
    monkeypatch.setattr(light_module, 'ticks_ms', lambda: now[0])
    return now


def first(light, now):
    """The first LED of the frame at now, rounded."""
    return tuple(round(c) for c in light.frame(now)[0][0])


def make(tmp_path, alerts=False, modes=None):
    settings = Settings(str(tmp_path / 'config.json'), merge(LIGHT_SETTINGS))
    settings.update({'alert': {'enabled': alerts}, 'device': {'transition_ms': 0}})
    return Light(Output(), settings, modes)


def test_an_alert_needs_alerts_on_unless_its_a_test(tmp_path, clock):
    light = make(tmp_path)
    assert light.alert() == 'Alerts are switched off'
    assert light.alert(test=True) is None and light.alerting


def test_an_alert_flashes_then_the_light_carries_on(tmp_path, clock):
    light = make(tmp_path, alerts=True)
    light.set(on=False)
    told = []
    light.listeners.append(lambda l: told.append(l.alerting))
    assert light.alert(colour='#00ff00', seconds=2, on_ms=300, off_ms=200, brightness=100) is None
    assert first(light, clock[0] + 100) == (0, 255, 0)
    assert first(light, clock[0] + 400) == (0, 0, 0)
    assert first(light, clock[0] + 600) == (0, 255, 0)
    assert first(light, clock[0] + 2100) == (0, 0, 0)  # over: back to off
    assert not light.alerting and told == [True, False]
    assert light.state()['state'] is False


def test_an_alert_again_starts_it_again_without_telling_twice(tmp_path, clock):
    light = make(tmp_path, alerts=True)
    told = []
    light.listeners.append(lambda l: told.append(l.alerting))
    light.alert(seconds=1)
    clock[0] += 800
    light.alert(seconds=1)
    light.frame(clock[0] + 900)  # 1.7 s after the first: over, if it hadn't started again
    assert light.alerting
    assert told == [True]


@pytest.mark.parametrize('change, error', [({'colour': 'red'}, 'colour'), ({'seconds': 0}, 'seconds'),
                                           ({'on_ms': 10}, 'on_ms'), ({'brightness': 101}, 'brightness')])
def test_bad_alerts_are_refused(tmp_path, clock, change, error):
    assert error in make(tmp_path, alerts=True).alert(**change)


def test_a_finished_effect_turns_the_light_off(tmp_path, clock):
    light = make(tmp_path, modes={'Once': Finishes})
    light.set(on=True, mode='Once')
    pixels, _ = light.frame(clock[0])
    assert pixels == [(0, 0, 0)] * 4 and light.on is False


class Counted:
    """An effect that counts how often it's made."""
    made = 0

    def __init__(self, count, parameters, light):
        Counted.made += 1

    def frame(self, now):
        return [(255, 255, 255)] * 4


def test_remake_makes_the_effect_again(tmp_path, clock):
    light = make(tmp_path, modes={'Counted': Counted})
    light.set(on=True, mode='Counted')
    light.frame(clock[0])
    light.frame(clock[0] + 20)
    made = Counted.made
    light.remake()  # a product setting that changes how it draws
    light.frame(clock[0] + 40)
    assert Counted.made == made + 1
