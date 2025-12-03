import os
import re
import requests

def make_filename(url):
    url_without_scheme = re.sub(r'^https?://', '', url)
    filename = re.sub(r'[^a-zA-Z0-9]', '-', url_without_scheme)
    filename = re.sub(r'-+', '-', filename)
    filename = filename.strip('-')
    return f"{filename}.html"

def download(url, output_dir=None):
    if output_dir is None:
        output_dir = os.getcwd()

    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as e:
        raise e

    filename = make_filename(url)
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(response.text)

    return filepath
