"""What a Juggle app asks the OS (pi.py), by the contract it gives (JUGGLE), with app-request stood in for."""
import json

import pytest

from base import pi


@pytest.fixture
def os_request(monkeypatch):
    """The contract the OS gives (JUGGLE), and the requests made of app-request (what _request() would run)."""
    def given(juggle):
        if juggle is None:
            monkeypatch.delenv('JUGGLE', raising=False)
        else:
            monkeypatch.setenv('JUGGLE', juggle)

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


def test_juggle_1_0_has_every_request(os_request):
    os_request('1.0')
    assert pi.juggle() == (1, 0)
    assert pi.os_requests() is True
    assert pi.os_setup() is True
    assert pi.os_wifi() is True


@pytest.mark.parametrize('value', [None, '', '1', 'one.two', '1.x', '.1'])
def test_without_a_usable_juggle_nothing_is_offered_or_asked(os_request, value):
    # A PC, or an OS before 1.0: whatever files it has, only the version says what's there
    os_request(value)
    assert pi.juggle() is None
    assert (pi.os_requests(), pi.os_setup(), pi.os_wifi()) == (False, False, False)
    for ask in (pi.setup_mode, pi.factory_reset, pi.wifi_fallback, lambda: pi.change_wifi('Upstairs', 'secret')):
        with pytest.raises(pi.RequestError, match='Juggle OS 1.0'):
            ask()
    assert os_request.asked == []


def test_a_later_minor_has_what_came_before_and_another_major_has_none_of_it(os_request):
    os_request('1.3')
    assert pi.os_wifi() is True
    os_request('2.0')
    assert pi.os_wifi() is False


def test_the_wifi_fallback_comes_from_the_os_and_goes_back_to_it(os_request):
    os_request('1.0')
    assert pi.wifi_fallback() == {'enabled': True, 'after_minutes': 5, 'for_minutes': 10}
    pi.set_wifi_fallback(False, 3, 20)
    assert os_request.asked[-1] == ['wifi-fallback', 'off', '3', '20']


def test_setup_mode_and_factory_reset_are_asked_of_the_os(os_request):
    os_request('1.0')
    pi.setup_mode()
    pi.factory_reset()
    assert os_request.asked == [['setup'], ['factory-reset']]


def test_a_new_wifi_network_goes_to_the_os_with_its_password_on_stdin(os_request):
    os_request('1.0')
    pi.change_wifi('Upstairs', 'secret password')
    assert os_request.asked[-1] == ['wifi', 'Upstairs']  # not the password: it would show in the process list
    assert os_request.stdin[-1] == 'secret password\n'
