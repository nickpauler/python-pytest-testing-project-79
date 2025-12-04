.PHONY: install build package-install lint test run

# Установка зависимостей
install:
	pip install -r requirements.txt
	pip install pytest-cov

# Сборка пакета
build:
	pip install hatch
	hatch build

# Установка пакета в систему
package-install:
	pip install dist/page_loader-0.1.0-py2.py3-none-any.whl

# Запуск линтера
lint:
	pip install flake8
	flake8 page_loader tests

# Запуск тестов
test:
	pytest --cov=page_loader --cov-report=xml --cov-report=term

# Запуск с тестовым URL
run:
	pip install requests
	page-loader --output . https://example.com
