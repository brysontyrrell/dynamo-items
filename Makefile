SHELL := /bin/bash

install:
	python3 -m pip install --editable '.[dev]'

uninstall:
	python3 -m pip uninstall -y -r <(python3 -m pip freeze)

clean:
	rm -rf build/ dist/ dynamo_items.egg-info .ruff_cache/

lint:
	black --check dynamo_items
	ruff check dynamo_items

format:
	black dynamo_items # You can have it any color you want...
	ruff check --select I001 --fix dynamo_items # Only fixes import order

build:
	python3 -m build --sdist --wheel
