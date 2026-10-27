"""The client against a small broker that speaks just enough MQTT 3.1.1 to check it."""
import asyncio
import struct

import pytest

from base.mqttclient import Client, MqttError, _length


class Broker:
    def __init__(self, return_code=0):
        self.return_code = return_code
        self.connect = None  # the CONNECT packet's body
        self.received = []  # (kind, flags, body)
        self.writer = None
        self.got = asyncio.Event()

    async def start(self):
        self.server = await asyncio.start_server(self.serve, '127.0.0.1', 0)
        return self.server.sockets[0].getsockname()[1]

    async def read(self, reader):
        header = (await reader.readexactly(1))[0]
        length, shift = 0, 0
        while True:
            byte = (await reader.readexactly(1))[0]
            length |= (byte & 0x7f) << shift
            if not byte & 0x80:
                break
            shift += 7
        return header >> 4, header & 0x0f, await reader.readexactly(length)

    async def serve(self, reader, writer):
        self.writer = writer
        _, _, self.connect = await self.read(reader)
        writer.write(bytes([0x20, 2, 0, self.return_code]))
        try:
            while True:
                kind, flags, body = await self.read(reader)
                self.received.append((kind, flags, body))
                self.got.set()
                if kind == 8:  # SUBSCRIBE: grant QoS 1
                    writer.write(bytes([0x90, 3]) + body[:2] + b'\x01')
        except asyncio.IncompleteReadError:
            pass

    def send_publish(self, topic, message, qos=0, retain=False):
        body = struct.pack('!H', len(topic)) + topic.encode() + (b'\x00\x07' if qos else b'') + message.encode()
        self.writer.write(bytes([0x30 | qos << 1 | retain]) + _length(len(body)) + body)

    async def wait_for(self, kind):
        while not any(k == kind for k, _, _ in self.received):
            self.got.clear()
            await asyncio.wait_for(self.got.wait(), 2)
        return next(r for r in self.received if r[0] == kind)


def run(coroutine):
    return asyncio.run(coroutine)


def test_connects_with_the_will_and_login():
    async def go():
        broker = Broker()
        port = await broker.start()
        client = Client('lamp', '127.0.0.1', port, 'user', 'secret', will=('t/status', 'offline', True))
        await client.connect()
        client.close(goodbye=True)
        body = broker.connect
        assert body[:6] == b'\x00\x04MQTT' and body[6] == 4
        assert body[7] == 0x80 | 0x40 | 0x20 | 0x04 | 0x02
        assert b'lamp' in body and b't/status' in body and b'offline' in body and b'secret' in body
    run(go())


def test_a_refused_login_says_why():
    async def go():
        broker = Broker(return_code=5)
        port = await broker.start()
        with pytest.raises(MqttError, match='user and password'):
            await Client('lamp', '127.0.0.1', port).connect()
    run(go())


def test_publishes_retained_and_subscribes():
    async def go():
        broker = Broker()
        port = await broker.start()
        client = Client('lamp', '127.0.0.1', port)
        await client.connect()
        await client.publish('t/state', '{"State": true}', retain=True)
        await client.subscribe('t/control')
        kind, flags, body = await broker.wait_for(3)
        assert flags == 0x01 and body.endswith(b'{"State": true}')
        kind, flags, body = await broker.wait_for(8)
        assert flags == 0x02 and b't/control' in body
        client.close()
    run(go())


def test_receives_and_acknowledges_qos_1():
    async def go():
        broker = Broker()
        port = await broker.start()
        client = Client('lamp', '127.0.0.1', port)
        await client.connect()
        broker.send_publish('t/control', '{"a": 1}', qos=1, retain=True)
        assert await asyncio.wait_for(client.message(), 2) == ('t/control', '{"a": 1}', True)
        kind, _, body = await broker.wait_for(4)
        assert body == b'\x00\x07'
        client.close()
    run(go())


def test_a_dropped_connection_ends_the_messages():
    async def go():
        broker = Broker()
        port = await broker.start()
        client = Client('lamp', '127.0.0.1', port)
        await client.connect()
        broker.writer.close()
        assert await asyncio.wait_for(client.message(), 2) is None
        with pytest.raises(OSError):
            await client.publish('t', 'x')
    run(go())
