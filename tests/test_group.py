import json

import pytest

from base import lightmqtt, mqtt
from base.light import Light, LIGHT_SETTINGS
from base.settings import Settings, merge


class Output:
    count = 1

    def show(self, frame):
        pass


class Rainbows:
    def __init__(self, count, parameters, light):
        pass


@pytest.fixture
def light(tmp_path):
    settings = Settings(str(tmp_path / 'config.json'), merge(LIGHT_SETTINGS))
    light = Light(Output(), settings, {'Rainbows': Rainbows})
    light.set(on=True, mode='Colour', parameters={'Colour': '#ff0000'}, brightness=50)
    return light


def state(on=True, mode='Colour', parameters=None, brightness=50):
    return {'State': on, 'Mode': mode, 'ModeParameters': parameters or {}, 'Brightness': brightness, 'From': 'other'}


def test_the_payload_is_the_state_with_the_parameters_that_define_the_mode(light):
    payload = json.loads(lightmqtt.group_payload(light, 'unicorn'))
    assert payload == {'State': True, 'Mode': 'Colour', 'ModeParameters': {'Colour': '#ff0000'}, 'Brightness': 50,
                       'From': 'unicorn'}
    light.set(parameters={'Kelvin': 2700})
    assert json.loads(lightmqtt.group_payload(light, 'unicorn'))['ModeParameters'] == {'Kelvin': 2700}


def test_its_own_state_coming_back_changes_nothing(light):
    payload = json.loads(lightmqtt.group_payload(light, 'unicorn'))
    assert lightmqtt.group_change(payload, light, True) == {}


def test_follows_power_colour_and_brightness(light):
    change = lightmqtt.group_change(state(False, parameters={'Colour': '#00FF00'}, brightness=20), light, True)
    assert change == {'on': False, 'mode': 'Colour', 'parameters': {'Colour': '#00FF00'}, 'brightness': 20}


def test_brightness_can_be_its_own(light):
    assert lightmqtt.group_change(state(brightness=20), light, False) == {}


def test_a_mode_it_doesnt_have_is_left_out(light):
    assert lightmqtt.group_change(state(False, mode='Fire'), light, True) == {'on': False}


def test_a_speed_change_restarts_nothing_but_is_followed(light):
    light.set(mode='Rainbows', parameters={'Speed': 5})
    assert lightmqtt.group_change(state(mode='Rainbows', parameters={'Speed': 5}), light, True) == {}
    assert lightmqtt.group_change(state(mode='Rainbows', parameters={'Speed': 8}), light, True) == \
        {'mode': 'Rainbows', 'parameters': {'Speed': 8}}


@pytest.mark.parametrize('payload', [[], {'State': 'on', 'Mode': 'Colour', 'Brightness': 50},
                                     {'State': True, 'Mode': 'Colour', 'Brightness': 0}])
def test_unusable_states_are_refused(light, payload):
    with pytest.raises(ValueError):
        lightmqtt.group_change(payload, light, True)


def test_changes_made_following_the_group_are_marked(light):
    seen = []
    light.listeners.append(lambda l: seen.append(l.local))
    light.set(brightness=70)
    light.set(brightness=30, local=False)
    assert seen == [True, False] and light.local is True


def test_group_names():
    assert lightmqtt.group_error('living_room-1') is None
    assert lightmqtt.group_error('living room')
    assert lightmqtt.group_error('x' * 33)


def test_group_topics_are_never_cleared():
    t = mqtt.topics('lamp', light=True, group='lounge')
    assert t['group'] == 'earthstorm/group/lounge' and t['group_old'] == 'plasmastick/group/lounge'
    assert t['group'] not in mqtt.retained(t) and t['group_old'] not in mqtt.retained(t)
