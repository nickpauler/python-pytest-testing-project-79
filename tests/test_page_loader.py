import os
import tempfile
import requests_mock
from page_loader.download import download

def test_download_successful():
    url = 'https://ru.hexlet.io/courses'
    content = '<html><body>Test</body></html>'
    expected_filename = 'ru-hexlet-io-courses.html'

    with tempfile.TemporaryDirectory() as tmpdirname:
        with requests_mock.Mocker() as m:
            m.get(url, text=content)

            result_path = download(url, tmpdirname)

            assert result_path == os.path.join(tmpdirname, expected_filename)
            assert os.path.exists(result_path)
            with open(result_path, 'r') as f:
                assert f.read() == content
