import gzip

from base import web


def test_a_gzipped_file_is_sent_as_it_is_stored(tmp_path):
    (tmp_path / 'index.html.gz').write_bytes(gzip.compress(b'<p>hi</p>'))
    response = web._file(str(tmp_path / 'index.html'), 'text/html; charset=utf-8')
    try:
        assert response.headers['Content-Encoding'] == 'gzip'
        assert response.headers['Content-Type'] == 'text/html; charset=utf-8'
        assert response.headers['Cache-Control'] == 'no-store'
        assert gzip.decompress(response.body.read()) == b'<p>hi</p>'
    finally:
        response.body.close()


def test_a_plain_file_is_sent_without_one(tmp_path):
    (tmp_path / 'index.html').write_bytes(b'<p>hi</p>')
    response = web._file(str(tmp_path / 'index.html'), 'text/html; charset=utf-8')
    try:
        assert 'Content-Encoding' not in response.headers
        assert response.body.read() == b'<p>hi</p>'
    finally:
        response.body.close()
