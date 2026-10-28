import pytest

from base import schedule

EVERY_DAY = [0, 1, 2, 3, 4, 5, 6]
MODES = ('Colour', 'Rainbows')
# 2026-10-27 (a Tuesday) as days since 1970, and its local midnight in seconds
DAY = 20753
MIDNIGHT = DAY * 86400


def check(events):
    return schedule.schedule_settings(MODES)['schedule']['events'].check(events)


def test_weekday():
    assert schedule.weekday(DAY) == 1  # Tuesday


@pytest.mark.parametrize('event', [
    {'days': [], 'at': '18:00', 'action': 'on'},
    {'days': [7], 'at': '18:00', 'action': 'on'},
    {'days': [0], 'at': '24:00', 'action': 'on'},
    {'days': [0], 'at': 'noon', 'action': 'on'},
    {'days': [0], 'at': '18:00', 'action': 'dim'},
    {'days': [0], 'at': '18:00', 'action': 'on', 'mode': 'Fire'},
    {'days': [0], 'at': '18:00', 'action': 'on', 'brightness': 0},
    {'days': [0], 'at': 'sunset', 'offset': 181, 'action': 'on'},
])
def test_bad_events_are_refused(event):
    assert check([event])


def test_at_most_eight_events():
    event = {'days': EVERY_DAY, 'at': '18:00', 'action': 'on'}
    assert check([event] * 8) is None
    assert check([event] * 9)


def test_due_finds_the_events_in_order():
    events = [{'days': EVERY_DAY, 'at': '23:00', 'action': 'off'},
              {'days': [1], 'at': '18:30', 'action': 'on', 'mode': 'Rainbows'},
              {'days': [2], 'at': '19:00', 'action': 'on'}]
    found = schedule.due(events, MIDNIGHT + 18 * 3600, MIDNIGHT + 23 * 3600, 0, None, None)
    assert [e['at'] for e in found] == ['18:30', '23:00']


def test_latest_is_what_the_light_should_be_doing():
    events = [{'days': EVERY_DAY, 'at': '07:00', 'action': 'on'}, {'days': EVERY_DAY, 'at': '23:00', 'action': 'off'}]
    assert schedule.latest(events, MIDNIGHT + 12 * 3600, 0, None, None)['action'] == 'on'
    assert schedule.latest(events, MIDNIGHT + 2 * 3600, 0, None, None)['action'] == 'off'  # yesterday's


def test_sunset_needs_the_location_and_follows_it():
    event = {'days': EVERY_DAY, 'at': 'sunset', 'offset': 30, 'action': 'on'}
    assert schedule.event_minute(event, DAY, 0, None, None) is None
    # London in late October: sunset about 16:40 UTC, so 17:10 with the offset
    minute = schedule.event_minute(event, DAY, 0, 51.5, -0.13)
    assert 17 * 60 <= minute <= 17 * 60 + 20


class Light:
    def __init__(self):
        self.calls = []

    def set(self, **change):
        self.calls.append(change)


class Device:
    def __init__(self, light=None, product=None):
        self.light = light
        self.product = product


def test_events_act_on_the_light():
    light = Light()
    schedule.run_event(Device(light), {'action': 'on', 'at': '18:00', 'mode': 'Rainbows', 'brightness': 40})
    schedule.run_event(Device(light), {'action': 'off', 'at': '23:00'})
    assert light.calls == [{'on': True, 'mode': 'Rainbows', 'brightness': 40}, {'on': False}]


class Sensor:
    def __init__(self):
        self.calls = []

    def scheduled(self, device, on):
        self.calls.append(on)


def test_another_products_events_go_to_its_scheduled():
    product = Sensor()
    schedule.run_event(Device(product=product), {'action': 'off', 'at': '08:00'})
    schedule.run_event(Device(product=product), {'action': 'on', 'at': '18:00'})
    assert product.calls == [False, True]


def test_another_products_events_have_no_mode():
    assert schedule.event_error({'days': [0], 'at': '08:00', 'action': 'on', 'mode': 'Rainbows'}, ()) is not None
    assert schedule.event_error({'days': [0], 'at': '08:00', 'action': 'on'}, ()) is None
