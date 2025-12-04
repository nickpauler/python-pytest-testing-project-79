import logging
import os
import tempfile

import pytest
import requests
import requests_mock

from page_loader.page_loader import make_filename, download

# Настройка логирования для читаемого вывода
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
    """Тестирование скачивания страницы с явным output_dir"""
    url = "https://ru.hexlet.io/courses"
    test_page_text = "<html><body>Test Page</body></html>"
    expected_filename = os.path.join(temp_dir, "ru-hexlet-io-courses.html")

    with requests_mock.Mocker() as m:
        m.get(url, text=test_page_text)  # Подмена запроса

        logger.info("Downloading: %s", url)
        file_path = download(url, temp_dir)
        logger.info("Saved to: %s", file_path)

        # Проверка, что файл создан и корректен
        assert os.path.exists(file_path)
        assert file_path == expected_filename

        # Проверка содержимого файла
        with open(file_path, encoding="utf-8") as file:
            assert file.read() == test_page_text

        # Проверка, что requests.get(url) был вызван ОДИН раз
        assert len(m.request_history) == 1
        # Проверка, что запрос был сделан по нужному URL
        assert m.request_history[0].url == url
        # Проверка, что это именно GET-запрос
        assert m.request_history[0].method == "GET"


def test_download_default_directory(temp_dir, monkeypatch):
    """download() без output_dir должен сохранять файл в текущую директорию"""
    url = "https://ru.hexlet.io/courses"
    test_page_text = "<html><body>Test Page</body></html>"

    expected_filename = "ru-hexlet-io-courses.html"

    # Меняем текущую директорию на временную
    old_cwd = os.getcwd()
    os.chdir(temp_dir)

    try:
        with requests_mock.Mocker() as m:
            m.get(url, text=test_page_text)

            logger.info("Downloading with default directory: %s", url)
            file_path = download(url)

            # Путь должен указывать на файл внутри temp_dir
            assert os.path.exists(file_path)
            expected_path = os.path.join(temp_dir, expected_filename)
            assert os.path.realpath(file_path) == os.path.realpath(expected_path)


            with open(file_path, encoding="utf-8") as file:
                assert file.read() == test_page_text

            # Проверяем сетевой вызов
            assert len(m.request_history) == 1
            assert m.request_history[0].url == url
            assert m.request_history[0].method == "GET"
    finally:
        os.chdir(old_cwd)
