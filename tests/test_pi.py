"""What a Juggle app asks the OS for setup mode and the Wi-Fi fallback (pi.py), with app-request stood in for."""
import json

import pytest

from base import pi


@pytest.fixture
def os_request(tmp_path, monkeypatch):
    """app-request as a file (what os_setup() reads) and the requests made of it (what _request() would run)."""
    monkeypatch.delenv('JUGGLE', raising=False)

    def given(text):
        path = tmp_path / 'app-request'
        path.write_text(text, encoding='utf-8')
        monkeypatch.setattr(pi, 'APP_REQUEST', str(path))
        monkeypatch.setattr(pi, '_setup', None)
        monkeypatch.setattr(pi, '_wifi', None)

    asked = []
    given_in = []

    def request(*args, given=None):
        asked.append(list(args))
        given_in.append(given)
        if args == ('settings',):
            return json.dumps({'time_zone': 'Europe/London', 'ntp': '',
                               'wifi_fallback': {'enabled': True, 'after_minutes': 5, 'for_minutes': 10}})
        return ''
    monkeypatch.setattr(pi, '_request', request)
    given.asked = asked
    given.stdin = given_in
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


def test_a_new_wifi_network_goes_to_the_os_with_its_password_on_stdin(os_request):
    os_request('...  app-request wifi <ssid>  app-request networks  app-request factory-reset  ...')
    assert pi.os_wifi() is True
    pi.change_wifi('Upstairs', 'secret password')
    assert os_request.asked[-1] == ['wifi', 'Upstairs']  # not the password: it would show in the process list
    assert os_request.stdin[-1] == 'secret password\n'


def test_wifi_changes_are_offered_only_when_the_os_takes_them(os_request):
    os_request('...  app-request factory-reset  ...')
    assert pi.os_wifi() is False
    with pytest.raises(pi.RequestError):
        pi.change_wifi('Upstairs', 'secret password')
    assert os_request.asked == []


def test_an_os_that_says_its_juggle_version_is_believed_over_app_request(os_request, monkeypatch):
    os_request('...  app-request restart  ...')  # app-request's text no longer decides
    monkeypatch.setenv('JUGGLE', '1.0')
    assert pi.juggle() == (1, 0)
    assert pi.os_requests() is True
    assert pi.os_setup() is True
    assert pi.os_wifi() is True


def test_a_later_minor_has_what_came_before_and_another_major_has_none_of_it(os_request, monkeypatch):
    os_request('...  app-request networks  app-request factory-reset  ...')
    monkeypatch.setenv('JUGGLE', '1.3')
    assert pi.os_wifi() is True
    monkeypatch.setattr(pi, '_wifi', None)
    monkeypatch.setenv('JUGGLE', '2.0')
    assert pi.os_wifi() is False


@pytest.mark.parametrize('value', ['', '1', 'one.two', '1.x', '.1'])
def test_without_a_usable_juggle_the_os_is_asked_as_before(os_request, monkeypatch, value):
    os_request('...  app-request factory-reset  ...')
    monkeypatch.setenv('JUGGLE', value)
    assert pi.juggle() is None
    assert pi.os_setup() is True
    assert pi.os_wifi() is False
