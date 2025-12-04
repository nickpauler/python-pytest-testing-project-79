import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import requests
import requests_mock
from bs4 import BeautifulSoup

from page_loader import cli
from page_loader.page_loader import (download_resource, is_local_resource,
                                     make_filename, download)

# Настройка логирования для читаемого вывода
logging.basicConfig(level=logging.DEBUG,
                    format="%(levelname)s: %(message)s",
                    stream=sys.stderr)
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
        ("https://ru.wikipedia.org/wiki/Покрытие_кода",
         "ru-wikipedia-org-wiki-Покрытие_кода.html"),
    ]

    logger.info("Проверяем генерацию имён файлов из URL")
    for url, expected in urls:
        result = make_filename(url)
        logger.debug(f"{url} -> {result}")
        assert result == expected


@pytest.mark.parametrize("status_code", [404, 500])
def test_response_errors(temp_dir, status_code):
    """Тестирование обработки ошибок 404 и 500"""
    url = f"https://site.com/error-{status_code}"

    with requests_mock.Mocker() as m:
        m.get(url, status_code=status_code)
        logger.info("Проверяем обработку ошибки HTTP %s для %s",
                    status_code, url)

        with pytest.raises(requests.exceptions.HTTPError):
            download(url, temp_dir)
            logger.debug("Ошибка %s корректно вызвала исключение",
                         status_code)


def test_storage_errors(monkeypatch, tmp_path):
    """Тест: проверяем поведение при ошибке доступа к директории"""
    url = "https://site.com/blog/about"

    monkeypatch.setattr(os.path, "exists", lambda path: False)
    logger.info("Проверяем поведение при PermissionError")

    with requests_mock.Mocker() as m:
        m.get(url, text="<html></html>")
        with pytest.raises(Exception, match="не существует"):
            download(url, tmp_path / "some_dir")
        logger.debug("PermissionError корректно вызвал исключение")


def test_resource_dir_creation_error(monkeypatch, tmp_path):
    """Тестирование ошибки при создании папки для ресурсов"""
    url = "https://site.com/page"
    html = "<html><body><img src='/img.png'></body></html>"

    with requests_mock.Mocker() as m:
        m.get(url, text=html)
        logger.info(
            "Проверяем исключение при создании директории для ресурсов")

        # Подменяем os.makedirs, чтобы вызвать ошибку
        monkeypatch.setattr(
            os,
            "makedirs",
            lambda *a, **kw: (_ for _ in ()).throw(OSError("Нет доступа")))

        with pytest.raises(Exception, match="Ошибка при создании директории"):
            download(url, tmp_path)

        logger.debug(
            "Исключение корректно выброшено: ошибка создания папки ресурсов")


def test_download(temp_dir):
    """Тестирование скачивания страницы"""
    url = "https://ru.hexlet.io/courses"
    test_page_text = "<html><body>Test Page</body></html>"
    expected_filename = os.path.join(temp_dir, "ru-hexlet-io-courses.html")
    expected_html = BeautifulSoup(
        test_page_text, "html.parser").prettify()

    with requests_mock.Mocker() as m:
        m.get(url, text=test_page_text)  # Подмена запроса
        logger.info("Начинаем тест скачивания страницы %s", url)

        file_path = download(url, temp_dir)
        logger.debug("Файл сохранён по пути: %s", file_path)

        # Проверка, что файл создан и корректен
        assert os.path.exists(file_path)
        assert file_path == expected_filename

        # Проверка содержимого файла
        with open(file_path, encoding="utf-8") as file:
            assert file.read() == expected_html

        # Проверка, что requests.get(url) был вызван ОДИН раз
        assert len(m.request_history) == 1
        # Проверка, что запрос был сделан по нужному URL
        assert m.request_history[0].url == url
        # Проверка, что это именно GET-запрос
        assert m.request_history[0].method == "GET"
        logger.info("Тест скачивания страницы успешно пройден")


def test_download_with_images(tmp_path):
    """Тестирование скачивания изображений и замены ссылок"""
    url = "https://ru.hexlet.io/courses"
    html_content = '''
    <html>
      <body>
        <img src="/assets/professions/python.png" />
      </body>
    </html>
    '''
    img_url = "https://ru.hexlet.io/assets/professions/python.png"
    # Загружаем реальную картинку из fixtures
    real_image_path = Path(__file__).parent / "fixtures/python.png"
    img_content = real_image_path.read_bytes()

    expected_img_filename = "ru-hexlet-io-assets-professions-python.png"
    expected_img_path = os.path.join(tmp_path, "ru-hexlet-io-courses_files",
                                     expected_img_filename)
    expected_html_path = os.path.join(tmp_path, "ru-hexlet-io-courses.html")

    # Используем requests_mock, чтобы подменить запросы
    with requests_mock.Mocker() as m:
        # Подмена запроса HTML
        m.get(url, text=html_content)
        # Подмена запроса изображения
        m.get(img_url, content=img_content)
        logger.info("Проверяем скачивание изображения и замену ссылки")

        file_path = download(url, tmp_path)

        # Проверка: HTML сохранён
        assert os.path.exists(expected_html_path)
        assert file_path == expected_html_path

        # Проверка: изображение сохранено
        assert os.path.exists(expected_img_path)

        # Проверка: файл совпадает с оригиналом
        downloaded_image = Path(expected_img_path).read_bytes()
        assert downloaded_image == img_content

        with open(expected_html_path, encoding="utf-8") as file:
            html = file.read()
            logger.debug("Проверяем замену src внутри HTML")
            assert (
                    f'src="ru-hexlet-io-courses_files/{expected_img_filename}"'
                    in html)
            logger.info("Тест скачивания изображения успешно пройден")


def test_download_with_link_and_script(tmp_path):
    """Тестирование скачивания локальных link и script ресурсов"""
    url = "https://ru.hexlet.io/courses"
    html_content = '''
    <html>
      <head>
        <link href="/assets/application.css" rel="stylesheet">
        <script src="/packs/js/runtime.js"></script>
      </head>
      <body></body>
    </html>
    '''
    css_url = "https://ru.hexlet.io/assets/application.css"
    js_url = "https://ru.hexlet.io/packs/js/runtime.js"
    css_data = b"body { background: white; }"
    js_data = b"console.log('ok');"

    expected_css = "ru-hexlet-io-assets-application.css"
    expected_js = "ru-hexlet-io-packs-js-runtime.js"
    expected_dir = tmp_path / "ru-hexlet-io-courses_files"
    expected_html = tmp_path / "ru-hexlet-io-courses.html"

    with requests_mock.Mocker() as m:
        m.get(url, text=html_content)
        m.get(css_url, content=css_data)
        m.get(js_url, content=js_data)

        logger.info("Проверяем скачивание CSS и JS ресурсов")
        download(url, tmp_path)

        # Проверяем, что ресурсы скачаны
        assert (expected_dir / expected_css).exists()
        assert (expected_dir / expected_js).exists()

        # Проверяем, что содержимое совпадает
        assert (expected_dir / expected_css).read_bytes() == css_data
        assert (expected_dir / expected_js).read_bytes() == js_data

        html = expected_html.read_text(encoding="utf-8")
        logger.debug("Проверяем, что ссылки в HTML заменены на локальные пути")

        assert f'href="ru-hexlet-io-courses_files/{expected_css}"' in html
        assert f'src="ru-hexlet-io-courses_files/{expected_js}"' in html

        logger.info("Тест скачивания CSS и JS ресурсов успешно пройден")


def test_download_network_error(tmp_path):
    """Тестирование ошибки при сетевом сбое"""
    url = "https://badsite.io/page"
    logger.info("Проверяем обработку сетевого сбоя при загрузке %s", url)

    with requests_mock.Mocker() as m:
        m.get(url, exc=requests.exceptions.ConnectionError("Сеть недоступна"))

        with pytest.raises(requests.RequestException):
            download(url, tmp_path)

    logger.info("Тест сетевого сбоя успешно пройден")


def test_download_resource_permission_error(monkeypatch, tmp_path):
    """Тестирование ошибки при невозможности записать файл"""
    url = "https://hexlet.io/resource"
    logger.info("Проверяем PermissionError при сохранении ресурса %s", url)

    # Используем requests_mock, чтобы подменить запросы
    with requests_mock.Mocker() as m:
        m.get(url, content=b"fake data")

        monkeypatch.setattr(
            "builtins.open",
            lambda *a, **kw: (_ for _ in ()).throw(
                PermissionError("Нет доступа")))

        # Проверяем, что PermissionError выбрасывается
        with pytest.raises(PermissionError):
            download_resource(url, tmp_path / "test.png")

    logger.info("Тест PermissionError успешно пройден")


def test_download_resource_http_error(monkeypatch, tmp_path):
    """Тестирование warning при ошибке загрузки ресурса"""
    url = "https://hexlet.io/page"
    html = '<html><body><img src="/broken.png"></body></html>'
    broken_url = "https://hexlet.io/broken.png"

    logger.info("Проверяем обработку HTTP-ошибки при загрузке ресурса %s",
                broken_url)
    with requests_mock.Mocker() as m:
        m.get(url, text=html)
        m.get(broken_url, status_code=404)

        download(url, tmp_path)

    html_path = tmp_path / "hexlet-io-page.html"
    logger.debug("Проверяем, что HTML-файл создан: %s", html_path)
    assert html_path.exists()

    content = html_path.read_text(encoding="utf-8")
    logger.debug("Проверяем, что ссылка на сломанный ресурс осталась в HTML")
    assert "broken.png" in content
    logger.info("Тест обработки ошибки загрузки ресурса успешно пройден")


def test_download_html_save_error(monkeypatch, tmp_path):
    """Тестирование ошибки при сохранении HTML-файла"""
    url = "https://example.com"
    html = "<html></html>"

    logger.info("Проверяем поведение при ошибке сохранения HTML-файла для %s",
                url)
    with requests_mock.Mocker() as m:
        m.get(url, text=html)

        def fake_open(*args, **kwargs):
            raise OSError("Ошибка записи файла")

        monkeypatch.setattr("builtins.open", fake_open)

        with pytest.raises(Exception,
                           match="Ошибка при сохранении HTML-файла"):
            download(url, tmp_path)
    logger.info("Тест ошибки сохранения HTML успешно пройден")


def test_skip_external_resources(tmp_path):
    """Тестирование внешние ресурсы (другой домен) не скачиваются"""
    url = "https://ru.hexlet.io/courses"
    html = '<html><body><img src="https://external.com/img.png"></body></html>'

    logger.info(
        "Проверяем, что внешние ресурсы не скачиваются при загрузке %s", url)
    with requests_mock.Mocker() as m:
        m.get(url, text=html)
        path = download(url, tmp_path)
        saved_html = Path(path).read_text(encoding="utf-8")

    logger.debug("Проверяем, что ссылка осталась внешней в HTML")
    assert "https://external.com/img.png" in saved_html
    logger.info("Тест пропуска внешних ресурсов успешно пройден")


def test_download_empty_html(tmp_path):
    """Тестирование скачивания страницы без контента"""
    url = "https://example.com/empty"

    logger.info("Проверяем скачивание страницы без контента %s", url)
    with requests_mock.Mocker() as m:
        m.get(url, text="")
        path = download(url, tmp_path)

    logger.debug("Проверяем, что файл создан: %s", path)
    assert Path(path).exists()
    logger.debug("Проверяем, что HTML пустой")
    assert Path(path).read_text() == ""
    logger.info("Тест скачивания пустой страницы успешно пройден")


def test_cli_exit_code(monkeypatch):
    """Тестирование CLI завершается с кодом 1 при ошибке"""
    logger.info("Проверяем CLI — завершение с кодом 1 при ошибке загрузки")

    result = subprocess.run(["python", "-m", "page_loader.cli",
                             "https://nonexistent.site/page"],
                            capture_output=True,
                            text=True)

    logger.debug("CLI stderr: %s", result.stderr.strip())
    logger.debug("CLI stdout: %s", result.stdout.strip())

    assert result.returncode == 1
    assert "Ошибка" in result.stderr or "Ошибка" in result.stdout
    logger.info("Тест CLI завершения с ошибкой успешно пройден")


def test_cli_main_help(capsys, monkeypatch):
    """Тестирование запуска CLI с аргументом --help"""
    logger.info("Запускаем тест: проверка вывода справки (--help)")

    # Подменяем sys.argv, чтобы симулировать вызов из консоли
    monkeypatch.setattr(sys, "argv", ["page-loader", "--help"])
    logger.debug("Подменён sys.argv: %s", sys.argv)

    try:
        cli.main()
    except SystemExit as e:
        logger.debug("CLI завершился с кодом выхода: %s", e.code)
        # argparse вызывает SystemExit при --help
        assert e.code == 0

    captured = capsys.readouterr()
    logger.debug("Вывод CLI: %s", captured.out.strip())
    assert "usage" in captured.out.lower()
    logger.info("Тест CLI '--help' успешно пройден")


def test_cli_no_args(monkeypatch):
    """Тестирование CLI без аргументов завершается с ошибкой"""
    logger.info("Проверяем CLI без аргументов — ожидается ошибка")

    monkeypatch.setattr(sys, "argv", ["page-loader"])
    with pytest.raises(SystemExit) as e:
        cli.main()

    logger.debug("CLI завершился с кодом выхода: %s", e.value.code)
    assert e.value.code != 0
    logger.info("Тест CLI без аргументов успешно пройден")


def test_cli_download_success(capsys, monkeypatch, tmp_path):
    """Тестирование CLI успешно завершается при корректных аргументах"""
    url = "https://example.com"
    fake_file = tmp_path / "example-com.html"

    logger.info("Проверяем успешную загрузку через CLI с URL: %s",
                url)

    # Подмена download() чтобы не трогать сеть
    monkeypatch.setattr(
        "page_loader.cli.download", lambda u, o: str(fake_file))
    monkeypatch.setattr(
        sys, "argv", ["page-loader", url, "-o", str(tmp_path)])

    cli.main()
    captured = capsys.readouterr()
    logger.debug("CLI вывод: %s", captured.out.strip())

    assert str(fake_file) in captured.out
    logger.info("Тест успешной работы CLI успешно пройден")


def test_is_local_resource():
    """Тестирование локальных и внешних ресурсов"""
    base = "https://hexlet.io"
    logger.info("Проверяем функцию is_local_resource")

    assert is_local_resource("/assets/img.png", base)
    assert is_local_resource("https://hexlet.io/img.png", base)
    logger.debug("Локальные ресурсы корректно определены")

    assert not is_local_resource("https://google.com/img.png", base)
    assert not is_local_resource("//cdn.hexlet.io/img.png",
                                 "https://example.com")
    logger.debug("Внешние ресурсы корректно определены")

    logger.info("Тест функции is_local_resource успешно пройден")
