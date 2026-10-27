"""What an ApplPi app asks the OS for setup mode and the Wi-Fi fallback (pi.py), with app-request stood in for."""
import json

import pytest

from base import pi


@pytest.fixture
def os_request(tmp_path, monkeypatch):
    """app-request as a file (what os_setup() reads) and the requests made of it (what _request() would run)."""
    def given(text):
        path = tmp_path / 'app-request'
        path.write_text(text, encoding='utf-8')
        monkeypatch.setattr(pi, 'APP_REQUEST', str(path))
        monkeypatch.setattr(pi, '_setup', None)

    asked = []

    def request(*args):
        asked.append(list(args))
        if args == ('settings',):
            return json.dumps({'time_zone': 'Europe/London', 'ntp': '',
                               'wifi_fallback': {'enabled': True, 'after_minutes': 5, 'for_minutes': 10}})
        return ''
    monkeypatch.setattr(pi, '_request', request)
    given.asked = asked
    return given


def test_setup_mode_is_offered_only_when_the_os_has_it(os_request):
    os_request('...  app-request restart  ...')
    assert pi.os_setup() is False
    with pytest.raises(pi.RequestError):
        pi.setup_mode()
    with pytest.raises(pi.RequestError):
        pi.wifi_fallback()
    assert os_request.asked == []


def test_without_app_request_there_is_no_setup_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(pi, 'APP_REQUEST', str(tmp_path / 'none'))
    monkeypatch.setattr(pi, '_setup', None)
    assert pi.os_setup() is False


def test_the_wifi_fallback_comes_from_the_os_and_goes_back_to_it(os_request):
    os_request('...  app-request factory-reset  ...')
    assert pi.os_setup() is True
    assert pi.wifi_fallback() == {'enabled': True, 'after_minutes': 5, 'for_minutes': 10}
    pi.set_wifi_fallback(False, 3, 20)
    assert os_request.asked[-1] == ['wifi-fallback', 'off', '3', '20']


def test_setup_mode_and_factory_reset_are_asked_of_the_os(os_request):
    os_request('...  app-request factory-reset  ...')
    pi.setup_mode()
    pi.factory_reset()
    assert os_request.asked == [['setup'], ['factory-reset']]
