.PHONY: clean-pyc clean-build docs

help:
	@echo "clean-build - remove build artifacts"
	@echo "clean-pyc - remove Python file artifacts"
	@echo "lint - check style with flake8"
	@echo "test - run tests quickly with the default Python"
	@echo "testall - run tests on every Python version with tox"
	@echo "coverage - check code coverage quickly with the default Python"
	@echo "docs - generate Sphinx HTML documentation, including API docs"
	@echo "release - package and upload a release"

clean: clean-build clean-pyc

clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr *.egg-info

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +

lint:
	tox -epy3{6,5}-lint

test:
	py.test --tb native tests

test-all:
	tox

coverage:
	coverage run --source eth
	coverage report -m
	coverage html
	open htmlcov/index.html

build-docs:
	cd docs/; sphinx-build -W -T -E . _build/html

doctest:
	cd docs/; sphinx-build -T -b doctest . _build/doctest

validate-docs: build-docs doctest

docs: build-docs
	open docs/_build/html/index.html

linux-docs: build-docs
	readlink -f docs/_build/html/index.html

package: clean
	python setup.py sdist bdist_wheel
	python scripts/release/test_package.py

release: clean
	CURRENT_SIGN_SETTING=$(git config commit.gpgSign)
	git config commit.gpgSign true
	bumpversion $(bump)
	git push upstream && git push upstream --tags
	python setup.py sdist bdist_wheel
	twine upload dist/*
	git config commit.gpgSign "$(CURRENT_SIGN_SETTING)"

sdist: clean
	python setup.py sdist bdist_wheel
	ls -l dist
