"""The Pi's screen going dark and waking (pi.Screen), on a backlight in a temporary folder and a clock that's set by hand."""
import pytest

from base import pi
from base.settings import Settings, merge


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class Display:
    """Anything with on(), off() and set_brightness() will do."""

    def __init__(self):
        self.calls = []

    def on(self):
        self.calls.append('on')

    def off(self):
        self.calls.append('off')

    def set_brightness(self, percent):
        self.calls.append(('brightness', percent))


@pytest.fixture
def backlight(tmp_path):
    folder = tmp_path / '10-0045'
    folder.mkdir()
    (folder / 'max_brightness').write_text('255')
    (folder / 'bl_power').write_text('0')
    (folder / 'brightness').write_text('255')
    return folder


def make(timeout=60, redraw=None):
    clock, display = Clock(), Display()
    screen = pi.Screen(display, timeout, clock, redraw)
    display.calls.clear()
    return screen, clock, display


def test_it_starts_on_in_case_the_app_stopped_while_it_was_off():
    display = Display()
    pi.Screen(display, 60, Clock())
    assert display.calls == ['on']


def test_it_goes_dark_after_the_timeout_and_not_before():
    screen, clock, display = make(60)
    clock.now += 59
    assert screen.tick() is False and screen.awake
    clock.now += 1
    assert screen.tick() is True
    assert not screen.awake and display.calls == ['off']
    assert screen.tick() is False  # already dark: nothing more to do


def test_input_keeps_it_awake():
    screen, clock, display = make(60)
    clock.now += 50
    assert screen.input() is True
    clock.now += 50
    assert screen.tick() is False and screen.awake


def test_a_timeout_of_zero_never_sleeps():
    screen, clock, display = make(0)
    clock.now += 10 ** 6
    assert screen.tick() is False and screen.awake and display.calls == []


def test_the_touch_that_wakes_it_does_nothing_else_until_it_lifts():
    screen, clock, display = make(60)
    screen.sleep()
    display.calls.clear()
    assert screen.input() is False  # down: wakes it
    assert screen.awake and display.calls == ['on']
    assert screen.input() is False  # still down
    assert screen.input(lifted=True) is False  # up
    assert screen.input() is True  # the next touch is the app's


def test_a_key_press_wakes_it_and_is_used_by_nobody():
    screen, clock, display = make(60)
    screen.sleep()
    assert screen.input(lifted=True) is False
    assert screen.awake and screen.input(lifted=True) is True


def test_a_screen_that_needs_redrawing_is_redrawn_once_it_is_awake():
    seen = []
    screen, clock, display = make(60, redraw=lambda: seen.append(screen.awake))
    screen.sleep()
    screen.input(lifted=True)
    assert seen == [True]


def test_with_no_display_it_still_knows_it_is_asleep():
    screen = pi.Screen(None, 60, Clock())
    screen.sleep()
    assert not screen.awake
    screen.wake()
    assert screen.awake


def test_the_settings_give_its_timeout_and_brightness(tmp_path):
    settings = Settings(str(tmp_path / 'config.json'), merge(pi.SETTINGS))
    assert settings.get('screen', 'timeout_minutes') == 0  # never, as v1.1's console is
    screen, clock, display = make(60)
    settings.update({'screen': {'timeout_minutes': 5, 'brightness': 40}})
    screen.apply(settings)
    assert screen.timeout == 300 and display.calls == [('brightness', 40)]


def test_the_settings_are_checked(tmp_path):
    settings = Settings(str(tmp_path / 'config.json'), merge(pi.SETTINGS))
    assert settings.update({'screen': {'timeout_minutes': -1}})
    assert settings.update({'screen': {'brightness': 101}})


def test_a_backlight_goes_off_and_on_by_its_power(backlight):
    found = pi.Backlight.find(backlight.parent)
    found.off()
    assert (backlight / 'bl_power').read_text() == '4'
    found.on()
    assert (backlight / 'bl_power').read_text() == '0'


def test_a_backlights_brightness_follows_its_curve(backlight):
    found = pi.Backlight.find(backlight.parent)
    found.set_brightness(100)
    assert (backlight / 'brightness').read_text() == '255'
    found.set_brightness(5)
    least = int((backlight / 'brightness').read_text())
    found.set_brightness(50)
    half = int((backlight / 'brightness').read_text())
    assert 1 <= least < half < 255


def test_no_backlight_is_none(tmp_path):
    assert pi.Backlight.find(tmp_path) is None
    assert pi.Backlight.find(tmp_path / 'missing') is None


def test_an_hdmi_screen_asks_the_os(monkeypatch):
    asked = []
    monkeypatch.setattr(pi, '_request', lambda *args, given=None: asked.append(args))
    hdmi = pi.HdmiScreen()
    hdmi.off()
    hdmi.on()
    hdmi.set_brightness(30)  # no backlight: nothing to do
    assert asked == [('screen-sleep',), ('screen-wake',)]


def test_an_hdmi_screen_the_os_cannot_turn_off_is_not_fatal(monkeypatch):
    def refuse(*args, given=None):
        raise pi.RequestError('no')
    monkeypatch.setattr(pi, '_request', refuse)
    pi.HdmiScreen().off()


def test_open_uses_the_backlight_when_there_is_one(backlight, monkeypatch):
    monkeypatch.setattr(pi.Backlight, 'FOLDER', backlight.parent)
    screen = pi.Screen.open()
    assert isinstance(screen.display, pi.Backlight)


def test_open_uses_hdmi_only_where_the_os_can_turn_it_off(tmp_path, monkeypatch):
    monkeypatch.setattr(pi.Backlight, 'FOLDER', tmp_path)
    monkeypatch.setattr(pi, 'display_connected_hdmi', lambda: True)
    monkeypatch.setattr(pi, 'os_screen', lambda: False)
    assert pi.Screen.open().display is None
    monkeypatch.setattr(pi, 'os_screen', lambda: True)
    assert isinstance(pi.Screen.open().display, pi.HdmiScreen)
    monkeypatch.setattr(pi, 'display_connected_hdmi', lambda: False)
    assert pi.Screen.open().display is None


# The input devices, for an app that doesn't draw on the screen

@pytest.fixture
def devices(tmp_path, monkeypatch):
    """/dev/input and /sys/class/input in a temporary folder: event files with a name each."""
    dev, sys_input = tmp_path / 'dev', tmp_path / 'sys'
    dev.mkdir()
    monkeypatch.setattr(pi.Inputs, 'FOLDER', dev)
    monkeypatch.setattr(pi.Inputs, 'NAMES', sys_input)

    def add(event, name):
        (dev / event).write_bytes(b'')
        (sys_input / event / 'device').mkdir(parents=True)
        (sys_input / event / 'device' / 'name').write_text(name + '\n')
    add.dev = dev
    return add


def watch():
    added, removed, used = [], [], []
    inputs = pi.Inputs(lambda fd, callback: added.append(fd), removed.append, lambda: used.append(1))
    return inputs, added, removed, used


def test_every_input_device_is_watched_but_the_hdmi_jack(devices):
    devices('event0', 'Chicony USB Keyboard')
    devices('event1', 'vc4-hdmi')
    devices('event2', '10-0038 generic ft5x06 (79)')
    inputs, added, _, _ = watch()
    inputs.scan()
    assert sorted(inputs.fds) == ['event0', 'event2'] and len(inputs) == 2
    inputs.scan()
    assert len(added) == 2  # each once


def test_a_device_plugged_in_later_is_watched_and_one_unplugged_is_let_go(devices):
    devices('event0', 'Keyboard')
    inputs, added, removed, _ = watch()
    inputs.scan()
    devices('event3', 'Mouse')
    inputs.scan()
    assert len(inputs) == 2
    # event0 goes (a file that's open can't be deleted on Windows, so the folder is swapped for one without it)
    after = devices.dev.parent / 'after'
    after.mkdir()
    (after / 'event3').write_bytes(b'')
    pi.Inputs.FOLDER = after
    inputs.scan()
    assert list(inputs.fds) == ['event3'] and len(removed) == 1


def test_no_input_devices_is_none_to_watch(tmp_path, monkeypatch):
    monkeypatch.setattr(pi.Inputs, 'FOLDER', tmp_path / 'missing')
    inputs, _, _, _ = watch()
    inputs.scan()
    assert len(inputs) == 0


def test_input_to_read_is_used_and_thrown_away():
    import os
    read, write = os.pipe()
    inputs, _, _, used = watch()
    os.write(write, b'x' * 48)
    inputs.activity(read)
    assert used == [1]
    os.close(read)
    os.close(write)


def test_a_screen_that_nothing_could_wake_stays_on():
    screen, clock, display = make(60)
    screen.can_wake = False
    clock.now += 1000
    assert screen.tick() is False and screen.awake


def test_the_brightness_is_only_written_when_it_changes(tmp_path):
    settings = Settings(str(tmp_path / 'config.json'), merge(pi.SETTINGS))
    screen, clock, display = make(60)
    screen.apply(settings)
    screen.apply(settings)
    assert display.calls == [('brightness', 100)]
    settings.update({'screen': {'brightness': 30}})
    screen.apply(settings)
    assert display.calls[-1] == ('brightness', 30) and len(display.calls) == 2


def test_an_app_that_draws_on_the_screen_runs_its_own(tmp_path, monkeypatch):
    import asyncio
    mark = tmp_path / 'display'
    mark.write_text('')
    monkeypatch.setattr(pi, 'DISPLAY_MARK', mark)
    opened = []
    monkeypatch.setattr(pi.Screen, 'open', classmethod(lambda cls, *args, **kwargs: opened.append(1)))
    asyncio.run(pi.screen(None))
    assert opened == []  # it returned at once, and didn't look for a display


def test_a_pi_with_no_display_has_nothing_to_turn_off(tmp_path, monkeypatch):
    import asyncio
    monkeypatch.setattr(pi, 'DISPLAY_MARK', tmp_path / 'none')
    monkeypatch.setattr(pi.Backlight, 'FOLDER', tmp_path)
    monkeypatch.setattr(pi, 'os_screen', lambda: False)
    settings = Settings(str(tmp_path / 'config.json'), merge(pi.SETTINGS))
    asyncio.run(asyncio.wait_for(pi.screen(settings), 5))  # returns, rather than looping
