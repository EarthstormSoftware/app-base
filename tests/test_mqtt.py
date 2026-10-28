import json

import pytest

from base import discovery, lightmqtt, lightwatch, mqtt


class Product:
    NAME = 'Unicorn'
    VERSION = '0.1.0'
    MODEL = 'Unicorn HAT'


def test_topics_follow_the_base_and_prefix():
    t = mqtt.topics('lamp', '/home/{name}', 'ha', light=True, sensors=('uptime_s',))
    assert t['status'] == '/home/lamp/status'
    assert t['control'] == '/home/lamp/control'
    assert t['ha_set'] == '/home/lamp/ha/set'
    assert t['ha_light'] == 'ha/light/lamp/config'
    assert t['ha_sensor_uptime_s'] == 'ha/sensor/lamp/uptime_s/config'


def test_a_device_that_isnt_a_light_has_no_light_topics():
    assert set(mqtt.topics('pir')) == {'status', 'info'}


def test_only_published_topics_are_retained():
    t = mqtt.topics('lamp', light=True)
    assert t['control'] not in mqtt.retained(t)
    assert t['ha_set'] not in mqtt.retained(t)
    assert t['state'] in mqtt.retained(t)


@pytest.mark.parametrize('value', ['', 'a/', 'a//b', 'a/+', 'a/#', ' a', '{device}', 'x' * 101])
def test_bad_topic_bases_are_refused(value):
    assert mqtt.topic_base_error(value)


def test_the_name_placeholder_is_only_for_the_topic_base():
    assert mqtt.topic_base_error('/home/{name}') is None
    assert mqtt.ha_prefix_error('{name}')


@pytest.mark.parametrize('address, expected', [
    ('broker', ('broker', 1883)),
    ('broker.lan:1884', ('broker.lan', 1884)),
    ('[fd00::1]:1885', ('fd00::1', 1885)),
    ('fd00::1', ('fd00::1', 1883)),
])
def test_broker_addresses(address, expected):
    assert mqtt.broker(address) == expected


@pytest.mark.parametrize('address', ['broker:x', 'broker:0', 'broker:70000', 'a b'])
def test_bad_broker_addresses_are_refused(address):
    assert mqtt.broker_error(address)


def test_info_has_the_figures_the_platform_has():
    payload = json.loads(mqtt.info_payload({'version': '1', 'uptime_s': 5, 'load': 0.1, 'other': 1}))
    assert payload == {'version': '1', 'uptime_s': 5, 'load': 0.1}


def test_home_assistant_state_in_colour_and_white():
    state = {'State': True, 'Mode': 'Colour', 'ModeParameters': {'Colour': '#ff8000'}, 'Brightness': 50}
    payload = json.loads(lightmqtt.ha_state_payload(state))
    assert payload == {'state': 'ON', 'color_mode': 'rgb', 'effect': 'Colour', 'brightness': 50,
                       'color': {'r': 255, 'g': 128, 'b': 0}}
    state['ModeParameters'] = {'Colour': '#ffb46b', 'Kelvin': 2700}
    payload = json.loads(lightmqtt.ha_state_payload(state))
    assert payload['color_mode'] == 'color_temp' and payload['color_temp'] == 370


def test_discovery_describes_the_light_and_its_device():
    t = mqtt.topics('lamp', light=True)
    config = json.loads(discovery.light('lamp', t, Product, ('Colour', 'Rainbows')))
    assert config['command_topic'] == t['ha_set']
    assert config['effect_list'] == ['Colour', 'Rainbows']
    assert config['device'] == {'identifiers': ['lamp'], 'name': 'lamp', 'manufacturer': 'Earthstorm Software',
                                'model': 'Unicorn HAT', 'sw_version': '0.1.0'}


def test_control_messages():
    assert lightmqtt.parse_control({'MessageType': 'StateChange', 'Parameters': {'State': False}}) == {'on': False}
    assert lightmqtt.parse_control({'MessageType': 'BrightnessChange', 'Parameters': {'Brightness': 20}}) == \
        {'brightness': 20}
    assert lightmqtt.parse_control({'MessageType': 'ModeChange',
                               'Parameters': {'Mode': 'Colour', 'ModeParameters': {'Colour': '#00ff00'}}}) == \
        {'mode': 'Colour', 'parameters': {'Colour': '#00ff00'}}


@pytest.mark.parametrize('payload', [[], {'MessageType': 'Explode'}, {'MessageType': 'StateChange'},
                                     {'MessageType': 'StateChange', 'Parameters': {'State': 'on'}}])
def test_bad_control_messages_are_refused(payload):
    with pytest.raises(ValueError):
        lightmqtt.parse_control(payload)


def test_home_assistant_commands():
    modes = ('Colour', 'Rainbows')
    assert lightmqtt.parse_ha_command({'state': 'ON', 'brightness': 49.6, 'transition': 2}, modes) == \
        {'on': True, 'brightness': 50, 'transition_ms': 2000}
    assert lightmqtt.parse_ha_command({'color': {'r': 1, 'g': 2, 'b': 3}}, modes) == \
        {'mode': 'Colour', 'parameters': {'Colour': '#010203'}}
    assert lightmqtt.parse_ha_command({'color_temp': 370}, modes) == {'mode': 'Colour', 'parameters': {'Kelvin': 2703}}
    assert lightmqtt.parse_ha_command({'effect': 'Rainbows'}, modes) == {'mode': 'Rainbows'}
    assert lightmqtt.parse_ha_command({'state': 'ON', 'brightness': 0}, modes)['brightness'] == 1


@pytest.mark.parametrize('text, now', [
    ('{"motion": true, "count": 3}', True), ('{"motion": false}', False), ('ON', True), ('OFF', False),
    ('true', True), ('0', False), ('', False), ('ding', True), ('{"State": "on"}', True), ('{"other": 1}', True),
])
def test_what_a_watched_message_means(text, now):
    assert lightwatch.watched(text) is now


@pytest.mark.parametrize('pattern, topic, matches', [
    ('a/b', 'a/b', True), ('a/+', 'a/b', True), ('a/#', 'a/b/c', True), ('a/+', 'a/b/c', False),
    ('a/b', 'a/c', False), ('a/b/c', 'a/b', False),
])
def test_topic_matching(pattern, topic, matches):
    assert lightwatch.topic_matches(pattern, topic) is matches


def test_alert_messages():
    assert lightmqtt.parse_alert('') == {}
    assert lightmqtt.parse_alert('{"Colour": "#0000ff", "Seconds": 5, "Other": 1}') == {'colour': '#0000ff', 'seconds': 5}
    assert lightmqtt.parse_alert('{"Active": false}') is None


@pytest.mark.parametrize('payload', [{}, {'state': 'on'}, {'effect': 'Fire'}, {'brightness': 101},
                                     {'color': {'r': 300, 'g': 0, 'b': 0}}, {'color_temp': True}])
def test_bad_home_assistant_commands_are_refused(payload):
    with pytest.raises(ValueError):
        lightmqtt.parse_ha_command(payload, ('Colour',))
