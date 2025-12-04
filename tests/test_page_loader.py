import logging
import os
import tempfile

import pytest
import requests
import requests_mock

from page_loader.page_loader import make_filename, download

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@pytest.fixture
def temp_dir():
    """Фикстура для создания временной директории"""
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield tmpdirname


def test_make_filename():
    """Тестирование создания имени файла из URL"""
    urls = [
        ("https://ru.hexlet.io/courses", "ru-hexlet-io-courses.html"),
        ("http://example.com/path/page", "example-com-path-page.html"),
        ("https://test.com/some-page?query=1",
         "test-com-some-page-query-1.html"),
    ]

    for url, expected in urls:
        assert make_filename(url) == expected


@pytest.mark.parametrize("status_code", [404, 500])
def test_response_errors(temp_dir, status_code):
    """Тестирование обработки ошибок 404 и 500"""
    url = f"https://site.com/error-{status_code}"

    with requests_mock.Mocker() as m:
        m.get(url, status_code=status_code)

        logger.info("Requested URL: %s (Expected error %s)", url, status_code)

        with pytest.raises(requests.exceptions.HTTPError):
            download(url, temp_dir)


@pytest.mark.parametrize("invalid_path, expected_exception", [
    ("C:\\this\\path\\does\\not\\exist", FileNotFoundError),
    ("C:\\Windows\\System32\\config", PermissionError),
])
def test_storage_errors(invalid_path, expected_exception):
    """Тестирование ошибок при сохранении"""
    url = "https://site.com/blog/about"

    with requests_mock.Mocker() as m:
        m.get(url, text="<html></html>")

        with pytest.raises(expected_exception):
            download(url, invalid_path)


def test_download(temp_dir):
    """Тестирование скачивания страницы с локальными ресурсами"""
    url = "https://ru.hexlet.io/courses"

    test_page_html = '''<html>
<head>
    <link rel="stylesheet" href="/assets/style.css">
    <link rel="stylesheet" href="https://cdn.example.com/external.css">
</head>
<body>
    <img src="/photos/logo.png">
    <img src="https://external.com/image.jpg">
</body>
</html>'''

    expected_html_filename = os.path.join(temp_dir, "ru-hexlet-io-courses.html")
    expected_assets_dir = os.path.join(temp_dir, "ru-hexlet-io-courses_files")

    with requests_mock.Mocker() as m:
        m.get(url, text=test_page_html)

        m.get("https://ru.hexlet.io/assets/style.css", text="body { color: red; }")
        m.get("https://ru.hexlet.io/photos/logo.png", content=b"fake-png-data")

        m.get("https://cdn.example.com/external.css", text="external")
        m.get("https://external.com/image.jpg", content=b"external-image")

        logger.info("Downloading: %s", url)
        file_path = download(url, temp_dir)
        logger.info("Saved to: %s", file_path)

        assert os.path.exists(file_path)
        assert file_path == expected_html_filename

        assert os.path.isdir(expected_assets_dir)

        expected_css_file = os.path.join(expected_assets_dir, "ru-hexlet-io-assets-style.css")
        expected_img_file = os.path.join(expected_assets_dir, "ru-hexlet-io-photos-logo.png")

        assert os.path.exists(expected_css_file), f"CSS file not found: {expected_css_file}"
        assert os.path.exists(expected_img_file), f"PNG file not found: {expected_img_file}"

        with open(expected_css_file, "r", encoding="utf-8") as f:
            assert "body { color: red; }" in f.read()

        with open(expected_img_file, "rb") as f:
            assert f.read() == b"fake-png-data"

        with open(file_path, encoding="utf-8") as f:
            modified_html = f.read()

            assert "ru-hexlet-io-courses_files" in modified_html
            assert "ru-hexlet-io-assets-style.css" in modified_html
            assert "ru-hexlet-io-photos-logo.png" in modified_html

            assert "https://cdn.example.com/external.css" in modified_html
            assert "https://external.com/image.jpg" in modified_html

        request_urls = [req.url for req in m.request_history]

        assert len(request_urls) == 3
        assert url in request_urls
        assert "https://ru.hexlet.io/assets/style.css" in request_urls
        assert "https://ru.hexlet.io/photos/logo.png" in request_urls

        assert "https://cdn.example.com/external.css" not in request_urls
        assert "https://external.com/image.jpg" not in request_urls


def test_download_default_directory(temp_dir):
    """download() без output_dir должен сохранять файл в текущую директорию"""
    url = "https://ru.hexlet.io/courses"
    test_page_text = "<html><body>Test Page</body></html>"

    expected_filename = "ru-hexlet-io-courses.html"

    old_cwd = os.getcwd()
    os.chdir(temp_dir)

    try:
        with requests_mock.Mocker() as m:
            m.get(url, text=test_page_text)

            logger.info("Downloading with default directory: %s", url)
            file_path = download(url)

            assert os.path.exists(file_path)
            expected_path = os.path.join(temp_dir, expected_filename)
            assert os.path.realpath(file_path) == os.path.realpath(expected_path)

            with open(file_path, encoding="utf-8") as file:
                assert file.read() == test_page_text

            assert len(m.request_history) == 1
            assert m.request_history[0].url == url
            assert m.request_history[0].method == "GET"
    finally:
        os.chdir(old_cwd)


def test_storage_errors_not_directory(temp_dir):
    """output_dir указывает на файл, а не директорию — ожидаем NotADirectoryError"""
    url = "https://site.com/blog/about"

    file_path = os.path.join(temp_dir, "not_a_dir.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("data")

    with requests_mock.Mocker() as m:
        m.get(url, text="<html></html>")

        with pytest.raises(NotADirectoryError):
            download(url, file_path)
