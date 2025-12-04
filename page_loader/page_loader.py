import logging
import os
import re
import sys
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

# Настройка логирования для читаемого вывода
logging.basicConfig(level=logging.INFO,
                    format="%(levelname)s: %(message)s",
                    stream=sys.stderr)
logger = logging.getLogger(__name__)


def make_filename(url, extension=None):
    """Генерирует безопасное имя файла на основе URL и расширения"""
    parsed = urlparse(url)
    path = parsed.netloc + parsed.path
    # Отделяем расширение заранее
    root, ext_from_path = os.path.splitext(path)
    clean_name = re.sub(r'\W+', '-', root).strip('-')

    # Определяем расширение
    if extension:
        ext = extension
    else:
        ext = ext_from_path.lstrip('.') or 'html'

    filename = f"{clean_name}.{ext}"
    logger.debug(f"Сформировано имя файла '{filename}' из URL '{url}'")
    return f"{clean_name}.{ext}"


def download_resource(resource_url, save_path):
    """Скачивает и сохраняет ресурс"""
    logger.debug(f"Попытка загрузить ресурс: {resource_url}")
    try:
        response = requests.get(resource_url)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Ошибка сети при загрузке ресурса {resource_url}: {e}")
        raise

    try:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'wb') as f:
            f.write(response.content)
    except OSError as e:
        logger.error(f"Ошибка при сохранении ресурса {save_path}: {e}")
        raise
    logger.info(f"Ресурс успешно сохранён: {save_path}")


def is_local_resource(resource_url, base_url):
    """Проверяет, что ресурс принадлежит тому же хосту"""
    is_local = urlparse(resource_url).netloc in ('', urlparse(base_url).netloc)
    logger.debug(f"Ресурс '{resource_url}' локальный: {is_local}")
    return is_local


def download(url, output_dir=os.getcwd()):
    """Главная функция: скачивает HTML-страницу и связанные ресурсы."""
    logger.info(f"Начало загрузки страницы: {url}")
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Ошибка при запросе страницы {url}: {e}")
        raise

    # Проверяем, что директория существует
    if not os.path.exists(output_dir):
        raise Exception(f"Ошибка: директория {output_dir} не существует")

    soup = BeautifulSoup(response.text, 'html.parser')
    base_name = make_filename(url, 'html').replace('.html', '')
    resource_dir = os.path.join(output_dir, f"{base_name}_files")

    # Создаём папку для ресурсов
    try:
        os.makedirs(resource_dir)
        logger.debug(f"Создана директория для ресурсов: {resource_dir}")
    except OSError as e:
        raise Exception(
            f"Ошибка при создании директории {resource_dir}: {e}") from e

    tags = soup.find_all(['img', 'link', 'script'])
    logger.debug(f"Найдено {len(tags)} тегов с потенциальными ресурсами")
    for tag in tags:
        attr = 'src' if tag.name in ['img', 'script'] else 'href'
        link = tag.get(attr)
        if not link:
            logger.debug(f"Пропущен тег <{tag.name}> без атрибута {attr}")
            continue

        full_url = urljoin(url, link)
        if not is_local_resource(full_url, url):
            logger.debug(f"Пропущен внешний ресурс: {full_url}")
            continue

        resource_filename = make_filename(full_url)
        resource_path = os.path.join(resource_dir, resource_filename)

        try:
            logger.info(f"Загрузка ресурса: {full_url}")
            download_resource(full_url, resource_path)
            tag[attr] = f"{base_name}_files/{resource_filename}"
        except requests.RequestException as e:
            logger.warning(f"Не удалось скачать ресурс {full_url}: {e}")

    # Сохраняем изменённый HTML
    html_path = os.path.join(output_dir, f"{base_name}.html")

    try:
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        logger.info(f"HTML успешно сохранён: {html_path}")
    except OSError as e:
        raise Exception(
            f"Ошибка при сохранении HTML-файла {html_path}: {e}") from e

    logger.info(f"Загрузка страницы завершена: {url}")
    return html_path
