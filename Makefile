SHELL := /usr/bin/env bash

docker-up:
	docker compose up -d --wait
test:
	 pytest -svv

test-docker: docker-up
	pytest -svv; docker compose down

test-speed: docker-up
	pytest -x --speedtest -m speed_test -svv; docker compose down

test-skip-live:
	SKIP_LIVE_TESTS=true pytest

test-coverage:
	coverage run --source collectfasta -m pytest

clean:
	rm -rf Collectfasta.egg-info __pycache__ build dist

build: clean
	python3 -m pip install --upgrade wheel twine setuptools
	python3 setup.py sdist bdist_wheel

distribute: build
	python3 -m twine upload dist/*

test-distribute: build
	python3 -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*

lint:
	flake8
	sorti --check .
	black --check .
	mypy .

format:
	sorti .
	black .
