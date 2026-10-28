"""MQTT for a product that isn't a light (Pico PIR): its state and set topics and its own Home Assistant entities."""
import json

import pytest

from base import mqtt
from base.settings import Settings, merge, BASE_SETTINGS


class Sensor:
    NAME = 'Pico PIR'
    VERSION = '2.0.0'
    MANUFACTURER = 'Raspberry Pi'
    MODEL = 'Pico W'
    SETTINGS = {}
    HA_ENTITIES = (('binary_sensor', 'motion'), ('switch', 'sensing'))

    def __init__(self):
        self.commands = []

    def state(self, device):
        return {'motion': True}

    def set(self, device, command):
        self.commands.append(command)
        return None

    def ha_entity(self, device, key, t):
        if key == 'motion':
            return {'name': 'Motion', 'device_class': 'motion'}
        return {'name': 'Sensing', 'command_topic': t['set']}


class Platform:
    NAME_EDITABLE = True

    @staticmethod
    def device_name():
        return 'hall'

    @staticmethod
    def health():
        return {'uptime_s': 5}


class Device:
    def __init__(self, tmp_path, product):
        self.product = product
        self.platform = Platform
        self.light = None
        self.settings = Settings(str(tmp_path / 'config.json'), merge(BASE_SETTINGS, mqtt.MQTT_SETTINGS))

    def info(self):
        return {'version': self.product.VERSION, 'uptime_s': 5}


def test_a_products_topics_are_as_pico_pir_had_them():
    t = mqtt.topics('hall', product_state=True, entities=Sensor.HA_ENTITIES)
    assert t['state'] == '/home/device/hall/state'
    assert t['set'] == '/home/device/hall/set'
    assert t['ha_motion'] == 'homeassistant/binary_sensor/hall/motion/config'
    assert t['ha_sensing'] == 'homeassistant/switch/hall/sensing/config'
    assert t['set'] not in mqtt.retained(t)
    assert t['state'] in mqtt.retained(t) and t['ha_motion'] in mqtt.retained(t)


def test_an_entity_gets_what_every_entity_has():
    t = mqtt.topics('hall', product_state=True, entities=Sensor.HA_ENTITIES)
    config = json.loads(mqtt.ha_entity_payload('hall', t, Sensor, 'motion', {'name': 'Motion'}))
    assert config['unique_id'] == 'hall_motion'
    assert config['state_topic'] == t['state']
    assert config['availability_topic'] == t['status']
    assert config['device'] == {'identifiers': ['hall'], 'name': 'hall', 'manufacturer': 'Raspberry Pi',
                                'model': 'Pico W', 'sw_version': '2.0.0'}


def test_commands_go_to_the_product_unless_retained(tmp_path):
    product = Sensor()
    m = mqtt.Mqtt(Device(tmp_path, product))
    t = m.topics
    assert m._handle(t['set'], '{"enabled": false}', False) is None
    assert product.commands == [{'enabled': False}]
    assert m._handle(t['set'], '{"enabled": true}', True) == 'commands should not be retained'
    assert product.commands == [{'enabled': False}]


@pytest.mark.parametrize('text', ['[]', '{}', '"on"'])
def test_a_command_must_be_an_object(text):
    with pytest.raises(ValueError):
        mqtt.parse_set(text)
