"""What a Pico runs must not need what only CPython has: the tests run on CPython, so a missing name shows up only on
a device, as a NameError when that line runs."""
import ast
import errno
from pathlib import Path

import pytest

from base import compat, mqtt

BASE = Path(compat.__file__).parent
PI_ONLY = {'pi.py', 'piweb.py', 'mqttclient.py'}
# CPython's kinds of OSError (and a few more), none of which MicroPython has
MISSING = {
    'BlockingIOError', 'BrokenPipeError', 'ChildProcessError', 'ConnectionAbortedError', 'ConnectionError',
    'ConnectionRefusedError', 'ConnectionResetError', 'FileExistsError', 'FileNotFoundError', 'InterruptedError',
    'IsADirectoryError', 'ModuleNotFoundError', 'NotADirectoryError', 'PermissionError', 'ProcessLookupError',
    'RecursionError', 'TimeoutError', 'UnicodeDecodeError', 'UnicodeEncodeError',
}


def pico_modules():
    return sorted(p for p in BASE.rglob('*.py') if p.name not in PI_ONLY)


def names(node):
    """The bare names under node, leaving out compat.py's CPython side (the else of its MICROPYTHON tests)."""
    if isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == 'MICROPYTHON':
        children = node.body
    else:
        if isinstance(node, ast.Name):
            yield node.id, node.lineno
        children = ast.iter_child_nodes(node)
    for child in children:
        yield from names(child)


@pytest.mark.parametrize('path', pico_modules(), ids=lambda p: p.relative_to(BASE).as_posix())
def test_only_names_micropython_has(path):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    assert [(name, line) for name, line in names(tree) if name in MISSING] == []


def test_a_refused_connection_says_so():
    assert 'refused' in mqtt.failure(ConnectionRefusedError(errno.ECONNREFUSED, 'Connection refused'))


@pytest.mark.parametrize('error, said', [
    (OSError('Wi-Fi not connected'), 'Could not connect: Wi-Fi not connected.'),
    (OSError(), 'Could not connect: OSError.'),
])
def test_other_failures_say_what_happened(error, said):
    assert mqtt.failure(error) == said
