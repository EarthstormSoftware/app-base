"""How a light starts: the setup default, the user's default, the last state, and device.power_on."""
import json

import pytest

from base.light import Light, LIGHT_SETTINGS
from base.settings import Settings, merge


class Output:
    count = 4

    def show(self, frame):
        pass


class Sparkle:
    def __init__(self, count, parameters, light):
        pass

    @staticmethod
    def check(parameters):
        return None if parameters.get('style', 1) != 'bad' else 'no such style'


MODES = {'Sparkle': Sparkle}


def settings(tmp_path, **device):
    made = Settings(str(tmp_path / 'config.json'), merge(LIGHT_SETTINGS))
    if device:
        assert made.update({'device': device})[0] is None
    return made


def start(tmp_path, powered_up=True, **device):
    """A light starting, with these settings and whatever it remembers."""
    return Light(Output(), settings(tmp_path, **device), MODES, memory=str(tmp_path / 'light.json'),
                 powered_up=powered_up)


def went_off_as(tmp_path, **state):
    kept = {'on': True, 'mode': 'Sparkle', 'parameters': {'speed': 3}, 'brightness': 20}
    kept.update(state)
    (tmp_path / 'light.json').write_text(json.dumps(kept))


def test_the_first_start_is_the_setup_default(tmp_path):
    light = start(tmp_path)
    assert (light.on, light.mode, light.parameters, light.brightness) == (True, 'Colour', {'colour': '#ffb46b'}, 66)


def test_a_change_comes_back_after_a_power_cut(tmp_path):
    light = start(tmp_path)
    light.set(mode='Sparkle', parameters={'speed': 3}, brightness=20)
    light.keep()
    again = start(tmp_path)
    assert (again.on, again.mode, again.parameters, again.brightness) == (True, 'Sparkle', {'speed': 3}, 20)


def test_off_comes_back_off(tmp_path):
    went_off_as(tmp_path, on=False)
    assert start(tmp_path).on is False


@pytest.mark.parametrize('power_on, was_on, on', [('restore', False, False), ('restore', True, True),
                                                  ('on', False, True), ('off', True, False)])
def test_power_on_says_whether_its_on_and_the_look_stays(tmp_path, power_on, was_on, on):
    went_off_as(tmp_path, on=was_on)
    light = start(tmp_path, power_on=power_on)
    assert light.on is on and (light.mode, light.brightness) == ('Sparkle', 20)


def test_on_with_the_default_ignores_the_last_look(tmp_path):
    went_off_as(tmp_path, on=False)
    light = start(tmp_path, power_on='default', default_brightness=40)
    assert light.on and (light.mode, light.parameters, light.brightness) == ('Colour', {'colour': '#ffb46b'}, 40)


@pytest.mark.parametrize('power_on', ['on', 'off', 'default'])
def test_a_restart_always_comes_back_as_it_was(tmp_path, power_on):
    went_off_as(tmp_path, on=False)
    light = start(tmp_path, powered_up=False, power_on=power_on)
    assert not light.on and (light.mode, light.brightness) == ('Sparkle', 20)


def test_a_power_on_that_changes_it_is_what_a_restart_then_finds(tmp_path):
    went_off_as(tmp_path, on=True)
    start(tmp_path, power_on='off').keep()
    assert start(tmp_path, powered_up=False, power_on='off').on is False


@pytest.mark.parametrize('text', ['not json', '[]', '{"on": true}',
                                  '{"on": 1, "mode": "Colour", "parameters": {}, "brightness": 20}',
                                  '{"on": true, "mode": "Gone", "parameters": {}, "brightness": 20}',
                                  '{"on": true, "mode": "Colour", "parameters": {}, "brightness": 200}',
                                  '{"on": true, "mode": "Sparkle", "parameters": {"style": "bad"}, "brightness": 20}'])
def test_a_last_state_it_cant_use_is_the_default(tmp_path, text):
    (tmp_path / 'light.json').write_text(text)
    light = start(tmp_path)
    assert (light.on, light.mode, light.brightness) == (True, 'Colour', 66)


def test_keeping_writes_only_a_change(tmp_path):
    went_off_as(tmp_path)
    light = start(tmp_path)
    (tmp_path / 'light.json').write_text('left alone')
    light.keep()
    assert (tmp_path / 'light.json').read_text() == 'left alone'
    light.set(brightness=21)
    light.keep()
    assert json.loads((tmp_path / 'light.json').read_text())['brightness'] == 21


def test_an_alert_isnt_remembered(tmp_path):
    went_off_as(tmp_path)
    light = start(tmp_path)
    light.alert(test=True)
    (tmp_path / 'light.json').write_text('left alone')
    light.keep()
    assert (tmp_path / 'light.json').read_text() == 'left alone'


def test_forgetting_leaves_nothing_and_keeps_nothing(tmp_path):
    went_off_as(tmp_path)
    light = start(tmp_path)
    light.forget()
    light.set(brightness=21)
    light.keep()
    assert not (tmp_path / 'light.json').exists()


def test_saving_the_look_of_an_effect_and_going_back_to_it(tmp_path):
    light = start(tmp_path)
    light.set(mode='Sparkle', parameters={'speed': 3, 'style': 2}, brightness=20)
    assert not light.at_default()
    assert light.settings.update({'device': light.look()})[0] is None
    assert light.at_default()
    light.set(mode='Colour', parameters={'colour': '#00ff00'}, brightness=90)
    assert not light.at_default()
    assert light.to_default() is None
    assert (light.mode, light.parameters, light.brightness) == ('Sparkle', {'speed': 3, 'style': 2}, 20)


def test_going_back_drops_parameters_the_default_didnt_have(tmp_path):
    light = start(tmp_path, default_mode='Sparkle', default_parameters={'Sparkle': {'speed': 3}})
    light.set(parameters={'style': 2})
    light.to_default()
    assert light.parameters == {'speed': 3} and light.at_default()


def test_saving_a_colour_keeps_it_as_the_default_colour(tmp_path):
    light = start(tmp_path)
    light.set(parameters={'colour': '#00FF00'}, brightness=30)
    light.settings.update({'device': light.look()})
    assert light.settings.get('device', 'default_colour') == '#00ff00'
    assert light.at_default()


def test_going_back_leaves_on_or_off_alone(tmp_path):
    light = start(tmp_path)
    light.set(on=False)
    light.to_default()
    assert light.on is False


def test_default_parameters_for_another_mode_arent_used(tmp_path):
    light = start(tmp_path, default_mode='Colour', default_parameters={'Sparkle': {'speed': 3}})
    assert light.parameters == {'colour': '#ffb46b'}


def test_default_parameters_it_cant_use_are_left_out(tmp_path):
    light = start(tmp_path, default_mode='Sparkle', default_parameters={'Sparkle': {'style': 'bad'}})
    assert (light.mode, light.parameters) == ('Sparkle', {})


@pytest.mark.parametrize('old, new', [(True, 'restore'), (False, 'off')])
def test_the_old_tick_box_becomes_power_on(tmp_path, old, new):
    (tmp_path / 'config.json').write_text(json.dumps({'device': {'default_state': old, 'default_brightness': 50}}))
    made = settings(tmp_path)
    assert made.get('device', 'power_on') == new and made.get('device', 'default_brightness') == 50


def test_a_power_on_already_chosen_wins_over_the_old_tick_box(tmp_path):
    (tmp_path / 'config.json').write_text(json.dumps({'device': {'default_state': False, 'power_on': 'on'}}))
    assert settings(tmp_path).get('device', 'power_on') == 'on'


def test_power_on_must_be_one_of_the_four(tmp_path):
    assert 'power_on' in settings(tmp_path).update({'device': {'power_on': 'toggle'}})[0]
