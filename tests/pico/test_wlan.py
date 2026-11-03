import asyncio

import network
import pytest

from base.pico import wlan as wifi

SETTINGS = {'connect_timeout': 30, 'reconnect_wait': 30, 'max_retries': 0, 'fallback': False,
            'fallback_after_min': 360}


class _Settings:
    def get(self, section, key):
        return SETTINGS[key]


class _Led:
    def set(self, *args):
        pass


@pytest.fixture
def wlan():
    return wifi.Wlan('Home', 'secret', _Settings(), _Led(), setup_mode=None, hostname='test')


def test_a_failed_first_join_is_tried_again_soon(wlan):
    wlan._failed('Could not connect: status -1')
    assert wlan.state == wifi.WAITING
    assert wlan._retry_wait() == wifi.FIRST_RETRY_S


def test_later_failures_wait_the_reconnect_wait(wlan):
    wlan._failed('Could not connect: status -1')
    wlan.connect()
    wlan._failed('Could not connect: status -1')
    assert wlan._retry_wait() == 30


def test_a_dropped_connection_waits_the_reconnect_wait(wlan):
    wlan._connected()
    wlan.connect()
    wlan._failed('Connecting timed out')
    assert wlan._retry_wait() == 30


class _Stop(Exception):
    pass


async def _stop(ms):
    raise _Stop


def _join_fails(wlan, monkeypatch, status):
    """One pass of run() while the join fails with status; returns what it logged."""
    logged = []
    monkeypatch.setattr(wifi.Log, 'info', lambda tag, message: logged.append(message))
    monkeypatch.setattr(wifi.Log, 'warn', lambda tag, message: logged.append(message))
    monkeypatch.setattr(wifi, 'sleep_ms', _stop)
    monkeypatch.setattr(wlan.wlan, 'status', lambda: status)
    with pytest.raises(_Stop):
        asyncio.run(wlan.run())
    return logged


def test_a_wrong_password_on_the_first_join_is_said_to_be_misleading(wlan, monkeypatch):
    monkeypatch.setattr(network, 'STAT_WRONG_PASSWORD', -3, raising=False)
    logged = _join_fails(wlan, monkeypatch, -3)
    assert logged[0] == 'Could not connect: wrong password (status -3); trying again in 5 s'
    assert logged[-1].startswith('"Wrong password" can be misleading')


def test_a_wrong_password_later_is_not(wlan, monkeypatch):
    monkeypatch.setattr(network, 'STAT_WRONG_PASSWORD', -3, raising=False)
    wlan._failed('Could not connect: status -1')
    wlan.connect()
    logged = _join_fails(wlan, monkeypatch, -3)
    assert not any('misleading' in message for message in logged)


def test_another_failure_on_the_first_join_is_not(wlan, monkeypatch):
    monkeypatch.setattr(network, 'STAT_WRONG_PASSWORD', -3, raising=False)
    logged = _join_fails(wlan, monkeypatch, -1)
    assert not any('misleading' in message for message in logged)


def test_the_status_is_named_where_the_port_has_a_constant(monkeypatch):
    monkeypatch.setattr(network, 'STAT_NO_AP_FOUND', -2, raising=False)
    assert wifi._status_name(-2) == 'no ap found (status -2)'
    assert wifi._status_name(-9) == 'status -9'
