"""The Pico platform: a device's files as the firmware before the base kept them, its name, setup mode's saving, the
Wi-Fi fallback and BOOTSEL."""
import json

import pytest

from base import pico
from base.mqtt import MQTT_SETTINGS
from base.passwords import check_password, hash_password
from base.pico import setup
from base.pico.bootsel import HOLD_MS, Bootsel
from base.pico.crypto import encrypt_password
from base.pico.wlan import Wlan
from base.settings import BASE_SETTINGS, Settings, merge


class Product:
    NAME = 'Pico PIR'
    VERSION = '2.0.0'
    SETUP_SSID = 'PicoPIR-SETUP'
    NAME_PREFIX = 'PicoPIR-'


@pytest.fixture
def board(tmp_path, monkeypatch):
    """The board's root in a temporary folder, with a product."""
    monkeypatch.setattr(pico, 'ROOT', str(tmp_path).replace('\\', '/') + '/')
    monkeypatch.setattr(pico, 'product', Product)
    monkeypatch.setattr(pico, '_name', None)
    return tmp_path


def settings(board):
    return Settings(str(board / 'config.json'), merge(BASE_SETTINGS, MQTT_SETTINGS, pico.SETTINGS), codec=pico.Codec)


def write(board, name, data):
    (board / name).write_text(json.dumps(data))


def read(board, name):
    return json.loads((board / name).read_text())


def test_a_devices_config_is_read_and_kept_as_the_old_firmware_wrote_it(board):
    iv, encrypted = encrypt_password('broker secret')
    web_hash = hash_password('page secret')
    write(board, 'config.json', {
        'device': {'device_name': '', 'log_level': 2, 'watchdog': True, 'ntp_server': 'pool.ntp.org',
                   'utc_offset_min': 60, 'dst': 'eu', 'pir_pin': 22},
        'wlan': {'ssid': '', 'password': '', 'connect_timeout': 30, 'reconnect_wait': 30, 'max_retries': 0},
        'mqtt': {'enabled': True, 'broker_address': 'broker', 'user': 'pir', 'password_iv': iv,
                 'password_enc': encrypted, 'clean': True, 'queue_len': 1, 'ha_discovery': True,
                 'topic_base': '/home/device/{name}', 'ha_prefix': 'homeassistant'},
        'web': {'password_hash': web_hash}})
    s = settings(board)
    assert s.get('device', 'log_level') == 2 and s.get('device', 'dst') == 'eu'
    assert s.reveal('mqtt', 'password') == 'broker secret'
    assert check_password('page secret', s.get('web', 'password'))
    assert s.view()['mqtt']['password_set'] and s.view()['web']['password_set']
    # Saving keeps the old layout, so the old firmware can read it after a rollback
    s.update({'device': {'log_level': 1}})
    saved = read(board, 'config.json')
    assert saved['web'] == {'password_hash': web_hash}
    assert (saved['mqtt']['password_iv'], saved['mqtt']['password_enc']) == (iv, encrypted)
    assert 'password' not in saved['mqtt']
    assert saved['device']['log_level'] == 1
    assert saved['wlan']['fallback'] is True  # new settings are added; the old firmware ignores them


def test_passwords_typed_into_the_file_are_kept_as_the_old_firmware_would(board):
    write(board, 'config.json', {'mqtt': {'password': 'typed'}, 'web': {'password': 'also typed'}})
    s = settings(board)
    assert s.reveal('mqtt', 'password') == 'typed'
    assert s.get('mqtt', 'password') != 'typed'
    assert check_password('also typed', s.get('web', 'password'))


def test_a_new_mqtt_password_is_kept_encrypted(board):
    s = settings(board)
    s.update({'mqtt': {'password': 'new one'}})
    saved = read(board, 'config.json')['mqtt']
    assert 'new one' not in json.dumps(saved)
    assert settings(board).reveal('mqtt', 'password') == 'new one'


def test_the_name_set_on_the_page_wins_then_setup_modes_then_config_jsons(board):
    assert pico.device_name() == 'PicoPIR-A1B2C3'  # from the board's id
    write(board, 'config.json', {'device': {'device_name': 'from-config'}})
    pico._name = None
    assert pico.device_name() == 'from-config'
    write(board, 'provisioning.json', {'device_name': 'from-setup', 'ssid': 'x', 'password': 'y'})
    pico._name = None
    assert pico.device_name() == 'from-setup'
    write(board, 'device_name.json', {'name': 'from-page'})
    pico._name = None
    assert pico.device_name() == 'from-page'


def test_a_rename_is_cleaned_and_kept_for_the_next_start(board):
    assert pico.rename('Hall way!') is None
    assert read(board, 'device_name.json') == {'name': 'Hall-way'}
    assert pico.rename('') is not None
    assert pico.rename('x' * 33) is not None


def test_setup_mode_saves_the_network_and_clears_a_forgotten_web_password(board):
    write(board, 'config.json', {'web': {'password_hash': hash_password('forgotten')}, 'device': {'log_level': 1}})
    write(board, 'device_name.json', {'name': 'old-name'})
    assert pico._save_setup('Hall', 'Home', 'wifi secret') == 'Hall'
    saved = read(board, 'provisioning.json')
    assert saved['ssid'] == 'Home' and saved['device_name'] == 'Hall'
    assert 'wifi secret' not in json.dumps(saved)
    assert read(board, 'config.json')['web']['password_hash'] == ''
    assert not (board / 'device_name.json').exists()
    assert pico._wifi() == ('Home', 'wifi secret')


def test_without_setup_modes_file_a_hand_written_network_is_used(board):
    assert pico._wifi() == ('', '')
    write(board, 'config.json', {'wlan': {'ssid': 'Home', 'password': 'pw'}})
    assert pico._wifi() == ('Home', 'pw')


def test_setup_mode_is_asked_for_once(board):
    assert not pico._take_setup_request()
    (board / 'setup_request').write_text('1')
    assert pico._take_setup_request()
    assert not pico._take_setup_request()


def test_how_long_setup_mode_runs_comes_from_the_settings(board):
    assert pico._fallback_for_s() == 600
    write(board, 'config.json', {'wlan': {'fallback_for_min': 20}})
    assert pico._fallback_for_s() == 1200
    write(board, 'config.json', {'wlan': {'fallback_for_min': 'lots'}})
    assert pico._fallback_for_s() == 600


def test_the_setup_page_lists_networks_strongest_first_and_escapes_them():
    scan = [(b'Weak', b'', 1, -80, 3, 0), (b'<Strong>', b'', 6, -40, 3, 0), (b'Weak', b'', 11, -60, 3, 0),
            (b'', b'', 1, -30, 3, 1)]
    networks = setup.strongest(scan)
    assert networks == ['<Strong>', 'Weak']
    page = setup.form(Product, networks, 'Hall', error='<b>', ssid='Weak')
    assert '&lt;Strong&gt;' in page and '<Strong>' not in page
    assert '<option value="Weak" selected>' in page
    assert '&lt;b&gt;' in page


class Led:
    def __init__(self):
        self.state = (True, False, 0)

    def set(self, on, flash=False, interval=0):
        self.state = (on, flash, interval)

    def get(self):
        return self.state


class Wifi:
    """The wlan settings, as Settings.get gives them."""

    def __init__(self, **values):
        self.values = dict({'connect_timeout': 30, 'reconnect_wait': 30, 'max_retries': 0, 'fallback': True,
                            'fallback_after_min': 5, 'fallback_for_min': 10}, **values)

    def get(self, section, key):
        return self.values[key]


def wlan(**values):
    return Wlan('Home', 'pw', Wifi(**values), Led(), lambda: None, 'hall')


def test_the_fallback_waits_its_minutes_from_the_start():
    w = wlan()
    assert not w.fallback_due(w.started + 5 * 60 - 1)
    assert w.fallback_due(w.started + 5 * 60)


def test_the_fallback_never_comes_once_wifi_has_connected_or_when_its_off():
    w = wlan()
    w.ever_connected = True
    assert not w.fallback_due(w.started + 3600)
    assert not wlan(fallback=False).fallback_due(0 + 10 ** 9)


def test_the_fallback_comes_when_there_are_no_more_attempts():
    w = wlan(max_retries=1)  # the one attempt is made on starting
    assert w.fallback_due(w.started)


def test_networks_are_scanned_only_the_first_time(monkeypatch):
    import network
    scans = []
    monkeypatch.setattr(network.WLAN, 'scan', lambda self: scans.append(1) or [])
    w = wlan()
    w.connect()
    w.connect()
    assert len(scans) == 1


def test_bootsel_held_for_hold_ms_asks_for_setup_mode_and_shows_it_on_the_led():
    led = Led()
    button = Bootsel(led, lambda: None)
    assert not button.update(True, 1000)
    assert led.state[1]  # flashing: the press is seen
    assert not button.update(True, 1000 + HOLD_MS - 1)
    assert button.update(True, 1000 + HOLD_MS)


def test_letting_go_of_bootsel_starts_again_and_puts_the_led_back():
    led = Led()
    button = Bootsel(led, lambda: None)
    button.update(True, 0)
    assert not button.update(False, HOLD_MS - 100)
    assert led.state == (True, False, 0)
    assert not button.update(True, HOLD_MS)
    assert not button.update(True, 2 * HOLD_MS - 1)
