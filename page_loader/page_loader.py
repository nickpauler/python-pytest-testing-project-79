import os
import re
import requests


def make_filename(url):
    """Формирует имя файла на основе URL"""
    url = url.split("//")[-1]
    name = re.sub(r'\W+', '-', url).strip('-')
    return f"{name}.html"


def download(url, output_dir=os.getcwd()):
    """Скачивает страницу по URL и сохраняет в файл"""
    response = requests.get(url)
    response.raise_for_status()

    filename = make_filename(url)
    file_path = os.path.join(output_dir, filename)

    with open(file_path, "w", encoding="utf-8") as file:
        file.write(response.text)

    return file_path
