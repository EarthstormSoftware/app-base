"""The Pico's MQTT client (base/pico/mqtt.py), with mqtt_as stood in for: messages come through its callback."""
import asyncio
import sys
import types

import pytest


class _MQTTClient:
    def __init__(self, config):
        self.config = config
        self.connected = True
        self._has_connected = False
        self._isconnected = True

    def isconnected(self):
        return self.connected


@pytest.fixture
def client(monkeypatch):
    fake = types.ModuleType('mqtt_as')
    fake.config = {'queue_len': 0, 'subs_cb': None}
    fake.MQTTClient = _MQTTClient
    fake.MQTT_base = object
    monkeypatch.setitem(sys.modules, 'mqtt_as', fake)
    from base.pico import mqtt
    monkeypatch.setattr(mqtt, '_Managed', None)
    return mqtt.Client('hallway', 'broker', queue_len=1)


def test_messages_come_through_the_callback_with_a_queue_of_one(client):
    assert client._client.config['queue_len'] == 0  # callback mode, not mqtt_as's queue
    client._client.config['subs_cb'](b'/home/device/x/set', b'{"enabled": false}', False)
    assert asyncio.run(client.message()) == ('/home/device/x/set', '{"enabled": false}', False)


def test_the_oldest_goes_when_more_arrive_than_the_queue_holds(client):
    client._received(b't', b'first', False)
    client._received(b't', b'second', True)
    assert asyncio.run(client.message()) == ('t', 'second', True)


def test_the_messages_end_when_the_connection_drops(client):
    client._client.connected = False
    assert asyncio.run(client.message()) is None
