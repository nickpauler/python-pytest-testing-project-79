.PHONY: install build package-install lint test run

# Установка зависимостей
install:
	uv pip install -r requirements.txt

# Сборка пакета
build:
	uv pip install hatch
	hatch build

# Установка пакета в систему
package-install:
	uv pip install dist/page_loader-0.1.0-py2.py3-none-any.whl

# Запуск линтера
lint:
	uv pip install flake8
	flake8 page_loader tests

# Запуск тестов
test:
	uv pip install pytest requests_mock
	pytest

# Запуск с тестовым URL
run:
	uv pip install requests
	page-loader --output . https://example.com
