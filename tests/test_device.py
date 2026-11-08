"""The device as a product sees it (device.py): changing its settings as the page does."""
import asyncio
import types

from base.device import Device
from base.settings import Setting, is_text


def platform(tmp_path):
    return types.SimpleNamespace(
        state_path=lambda name: str(tmp_path / name), device_name=lambda: 'hall', NAME_EDITABLE=False,
        health=lambda: {}, SENSORS=())


def product(applied):
    return types.SimpleNamespace(
        NAME='Hello', VERSION='1.0.0', __file__=__file__, applied=lambda device, changed: applied.append(changed),
        SETTINGS={'hello': {'greeting': Setting('Hello', is_text(20)),
                            'port': Setting(80, restart=True)}})


def test_a_change_is_saved_and_applied_as_from_the_page(tmp_path):
    applied = []
    device = Device(product(applied), platform(tmp_path))
    assert device.change({'hello': {'greeting': 'Hi'}}) is None
    assert device.settings.get('hello', 'greeting') == 'Hi'
    assert applied == [{('hello', 'greeting')}]
    assert 'Hi' in (tmp_path / 'config.json').read_text()


def test_a_change_that_cant_be_used_changes_nothing(tmp_path):
    applied = []
    device = Device(product(applied), platform(tmp_path))
    assert 'hello.greeting' in device.change({'hello': {'greeting': 'x' * 21}})
    assert device.settings.get('hello', 'greeting') == 'Hello'
    assert applied == []


def test_a_change_that_needs_a_restart_restarts(tmp_path):
    restarted = []
    p = platform(tmp_path)
    p.restart = lambda: restarted.append(True)

    async def change():
        device = Device(product([]), p)
        assert device.change({'hello': {'port': 8080}}) is None
        assert device.change({'hello': {'greeting': 'Hi'}}) is None  # no restart for this one
        await asyncio.sleep(0.5)
    asyncio.run(change())
    assert restarted == [True]


def light_product():
    class Output:
        count = 1

        def show(self, frame):
            pass

    return types.SimpleNamespace(NAME='Lamp', VERSION='1.0.0', __file__=__file__, SETTINGS={}, LIGHT_MODES={},
                                 output=lambda device: Output())


def test_a_reset_brings_back_the_setup_default(tmp_path):
    device = Device(light_product(), platform(tmp_path))
    device.light.set(parameters={'colour': '#00ff00'}, brightness=20)
    device.change({'device': device.light.look()})
    device.light.keep()
    assert (tmp_path / 'light.json').exists()
    device.reset()
    assert not (tmp_path / 'light.json').exists()
    light = Device(light_product(), platform(tmp_path)).light
    assert (light.parameters, light.brightness) == ({'colour': '#ffb46b'}, 66)


def test_a_restart_saves_a_change_made_just_before_it(tmp_path):
    p = platform(tmp_path)
    p.restart = lambda: None
    p.powered_up = lambda: False

    async def restart():
        device = Device(light_product(), p)
        device.light.set(brightness=20)
        await device.restart_soon()
    asyncio.run(restart())
    assert Device(light_product(), p).light.brightness == 20
