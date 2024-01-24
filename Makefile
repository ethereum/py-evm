.PHONY: clean-pyc clean-build docs

help:
	@echo "clean-build - remove build artifacts"
	@echo "clean-pyc - remove Python file artifacts"
	@echo "lint - fix linting issues with pre-commit"
	@echo "test - run tests quickly with the default Python"
	@echo "coverage - check code coverage quickly with the default Python"
	@echo "docs - generate docs and open in browser (linux-docs for version on linux)"
	@echo "notes - consume towncrier newsfragments/ and update release notes in docs/"
	@echo "release - package and upload a release (does not run notes target)"
	@echo "dist - package"

clean: clean-build clean-pyc

clean-build:
	rm -fr build/
	rm -fr dist/

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -rf {} +

lint:
	@pre-commit run --all-files --show-diff-on-failure || ( \
		echo "\n\n\n * pre-commit should have fixed the errors above. Running again to make sure everything is good..." \
		&& pre-commit run --all-files --show-diff-on-failure \
	)

test:
	pytest tests

coverage:
	coverage run --source eth
	coverage report -m
	coverage html
	open htmlcov/index.html

build-docs:
	sphinx-apidoc -o docs/ . setup.py "*conftest*"
	$(MAKE) -C docs clean
	$(MAKE) -C docs html
	$(MAKE) -C docs doctest

build-docs-ci:
	$(MAKE) -C docs latexpdf
	$(MAKE) -C docs epub

validate-newsfragments:
	./newsfragments/validate_files.py
	towncrier build --draft

validate-docs: build-docs validate-newsfragments

validate-docs-ci: build-docs build-docs-ci validate-newsfragments

docs: build-docs
	open docs/_build/html/index.html

linux-docs: build-docs
	xdg-open docs/_build/html/index.html

package: clean
	python setup.py sdist bdist_wheel
	python scripts/release/test_package.py

notes:
	# Let UPCOMING_VERSION be the version that is used for the current bump
	$(eval UPCOMING_VERSION=$(shell bumpversion $(bump) --dry-run --list | grep new_version= | sed 's/new_version=//g'))
	# Now generate the release notes to have them included in the release commit
	towncrier build --yes --version $(UPCOMING_VERSION)
	# Before we bump the version, make sure that the towncrier-generated docs will build
	make build-docs
	git commit -m "Compile release notes for v$(UPCOMING_VERSION)"

release: check-bump clean
	# require that you be on a branch that's linked to upstream/main
	git status -s -b | head -1 | grep "\.\.upstream/main"
	# require that upstream is configured for ethereum/py-evm
	@git remote -v | grep -E "upstream\tgit@github.com:ethereum/py-evm.git \(push\)|upstream\thttps://(www.)?github.com/ethereum/py-evm \(push\)"
	# verify that docs build correctly
	./newsfragments/validate_files.py is-empty
	# verify that docs build correctly
	make build-docs
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
