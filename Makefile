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

lint-eth2:
	tox -epy37-lint-eth2

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
	./newsfragments/validate_files.py
	towncrier --draft

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
	# Let UPCOMING_VERSION be the version that is used for the current bump
	$(eval UPCOMING_VERSION=$(shell bumpversion $(bump) --dry-run --list | grep new_version= | sed 's/new_version=//g'))
	# Now generate the release notes to have them included in the release commit
	towncrier --yes --version $(UPCOMING_VERSION)
	# Before we bump the version, make sure that the towncrier-generated docs will build
	make build-docs
	# We need --allow-dirty because of the generated release_notes file but it is safe because the
	# previous dry-run runs *without* --allow-dirty which ensures it's really just the release notes
	# file that we are allowing to sit here dirty, waiting to get included in the release commit.
	bumpversion --allow-dirty $(bump)
	git push upstream && git push upstream --tags
	python setup.py sdist bdist_wheel
	twine upload dist/*
	git config commit.gpgSign "$(CURRENT_SIGN_SETTING)"

create-docker-image: clean
	docker build -t ethereum/trinity:latest -t ethereum/trinity:$(version) .

sdist: clean
	python setup.py sdist bdist_wheel
	ls -l dist

install-git-lfs:
	apt-get install -y git-lfs