import argparse
import os
import sys

from page_loader.page_loader import download, logger


def main():
    parser = argparse.ArgumentParser(
        description="Page Loader: скачивает веб-страницу")
    parser.add_argument("url", help="URL страницы для загрузки")
    parser.add_argument("-o", "--output", help="Директория для сохранения",
                        default=os.getcwd())

    args = parser.parse_args()

    try:
        file_path = download(args.url, args.output)
        logger.info(f"Страница успешно загружена в: {file_path}")
        print(file_path)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
