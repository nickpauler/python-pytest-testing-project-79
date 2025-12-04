import os
import re
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup


def make_filename(url, extension=''):
    """Создает имя файла из URL (без расширения в url!)."""
    url_without_scheme = re.sub(r'^https?://', '', url)
    filename = re.sub(r'[^a-zA-Z0-9]', '-', url_without_scheme)
    filename = re.sub(r'-+', '-', filename).strip('-')

    if extension:
        return f"{filename}{extension}"
    return f"{filename}.html"


def make_dir_name(url):
    """Создает имя директории для ресурсов."""
    url_without_scheme = re.sub(r'^https?://', '', url)
    dirname = re.sub(r'[^a-zA-Z0-9]', '-', url_without_scheme)
    dirname = re.sub(r'-+', '-', dirname).strip('-')
    return f"{dirname}_files"


def is_local_resource(url, base_url):
    """Проверяет, является ли ресурс локальным."""
    parsed_resource = urlparse(url)
    parsed_base = urlparse(base_url)

    if not parsed_resource.scheme and not parsed_resource.netloc:
        return True

    resource_host = parsed_resource.hostname or parsed_resource.netloc
    base_host = parsed_base.hostname or parsed_base.netloc

    return resource_host == base_host


def download_resource(url, output_path):
    """Скачивает один ресурс."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        with open(output_path, 'wb') as f:
            f.write(response.content)
        return True
    except Exception:
        return False


def download(url, output_dir=None):
    """Основная функция загрузки страницы с ресурсами."""
    if output_dir is None:
        output_dir = os.getcwd()

    # Проверяем, что директория существует
    if not os.path.exists(output_dir):
        raise FileNotFoundError(f"Output directory does not exist: {output_dir}")

    # Проверяем, что это именно директория, а не файл
    if not os.path.isdir(output_dir):
        raise NotADirectoryError(f"Output path is not a directory: {output_dir}")

    # Скачиваем главную страницу
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as e:
        raise e

    html_content = response.text
    soup = BeautifulSoup(html_content, 'html.parser')

    assets_dir_name = make_dir_name(url)
    assets_dir_path = os.path.join(output_dir, assets_dir_name)

    tags_attrs = [
        ('img', 'src'),
        ('link', 'href'),
        ('script', 'src'),
    ]

    resources_downloaded = False

    for tag_name, attr_name in tags_attrs:
        tags = soup.find_all(tag_name)
        for tag in tags:
            resource_url = tag.get(attr_name)
            if not resource_url:
                continue

            full_resource_url = urljoin(url, resource_url)

            if not is_local_resource(full_resource_url, url):
                continue

            if not resources_downloaded:
                os.makedirs(assets_dir_path, exist_ok=True)
                resources_downloaded = True

            parsed = urlparse(full_resource_url)

            extension = os.path.splitext(parsed.path)[1] or ''

            path_without_ext = os.path.splitext(parsed.path)[0]
            if parsed.query:
                path_without_ext += '?' + parsed.query

            full_path = parsed.netloc + path_without_ext

            resource_filename = make_filename(full_path, extension)
            resource_filepath = os.path.join(assets_dir_path, resource_filename)

            download_resource(full_resource_url, resource_filepath)

            new_path = os.path.join(assets_dir_name, resource_filename)
            tag[attr_name] = new_path

    html_filename = make_filename(url)
    html_filepath = os.path.join(output_dir, html_filename)

    with open(html_filepath, 'w', encoding='utf-8') as f:
        f.write(soup.prettify())

    return html_filepath
