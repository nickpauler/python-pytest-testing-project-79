install:
	pip install -e .

test:
	pytest

lint:
	flake8 page_loader tests

build:
	python3 -m build

package-install:
	pip install -e .

.PHONY: install test lint build package-install
