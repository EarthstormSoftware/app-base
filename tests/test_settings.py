"""Settings kept in a platform's own file layout (a codec), and secrets kept in a form that's undone to use them."""
import json

from base.settings import Settings, Setting, is_int


class Codec:
    """Keeps the secret under another name, as a Pico's config.json does."""

    @staticmethod
    def load(stored):
        mqtt = dict(stored.get('mqtt', {}))
        mqtt['password'] = mqtt.pop('password_enc', '')
        return dict(stored, mqtt=mqtt)

    @staticmethod
    def dump(values):
        mqtt = dict(values['mqtt'])
        mqtt['password_enc'] = mqtt.pop('password')
        return dict(values, mqtt=mqtt)


SCHEMA = {'mqtt': {
    'port': Setting(1883, is_int(1, 65535)),
    'password': Setting('', secret=True, store=lambda v: v[::-1], reveal=lambda v: v[::-1]),
}}


def test_the_file_is_read_and_written_in_its_own_layout(tmp_path):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps({'mqtt': {'port': 1884, 'password_enc': 'terces'}}))
    settings = Settings(str(path), SCHEMA, codec=Codec)
    assert settings.get('mqtt', 'port') == 1884
    assert settings.reveal('mqtt', 'password') == 'secret'
    assert settings.view()['mqtt'] == {'port': 1884, 'password_set': True}
    settings.update({'mqtt': {'password': 'new'}})
    assert json.loads(path.read_text()) == {'mqtt': {'port': 1884, 'password_enc': 'wen'}}


def test_without_a_reveal_a_secret_is_used_as_kept(tmp_path):
    settings = Settings(str(tmp_path / 'config.json'), {'web': {'password': Setting('', secret=True)}})
    settings.update({'web': {'password': 'open'}})
    assert settings.reveal('web', 'password') == 'open'


def test_a_file_that_isnt_an_object_gives_the_defaults(tmp_path):
    path = tmp_path / 'config.json'
    path.write_text('[1, 2]')
    assert Settings(str(path), SCHEMA, codec=Codec).get('mqtt', 'port') == 1883


def test_a_platforms_and_a_products_codecs_both_apply(tmp_path):
    from base.device import _codec

    class Product:
        @staticmethod
        def load(stored):
            return dict(stored, mqtt=dict(stored['mqtt'], port=stored['mqtt'].pop('old_port')))

        @staticmethod
        def dump(values):
            mqtt = dict(values['mqtt'])
            mqtt['old_port'] = mqtt.pop('port')
            return dict(values, mqtt=mqtt)

    path = tmp_path / 'config.json'
    path.write_text(json.dumps({'mqtt': {'old_port': 1884, 'password_enc': 'terces'}}))
    settings = Settings(str(path), SCHEMA, codec=_codec(Codec, Product))
    assert settings.get('mqtt', 'port') == 1884 and settings.reveal('mqtt', 'password') == 'secret'
    settings.update({'mqtt': {'port': 1885}})
    assert json.loads(path.read_text()) == {'mqtt': {'old_port': 1885, 'password_enc': 'terces'}}
