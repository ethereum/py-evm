#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import (
    setup,
    find_packages,
)


extras_require = {
    "eth": [
        "cached-property>=1.5.1,<2",
        "eth-bloom>=1.0.3",
        "eth-keys>=0.4.0,<0.5.0",
        "eth-typing>=3.3.0,<4.0.0",
        "eth-utils>=2.0.0,<3.0.0",
        "lru-dict>=1.1.6",
        "mypy-extensions>=1.0.0",
        "py-ecc>=1.4.7,<7.0.0",
        "rlp>=3,<4",
        "trie>=2.0.0,<3",
    ],
    # The eth-extra sections is for libraries that the evm does not
    # explicitly need to function and hence should not depend on.
    # Installing these libraries may make the evm perform better than
    # using the default fallbacks though.
    "eth-extra": [
        "blake2b-py>=0.2.0,<0.3.0",
        "coincurve>=18.0.0",
    ],
    "test": [
        "factory-boy==2.11.1",
        "hypothesis>=5,<6",
        "pexpect>=4.6, <5",
        "pytest>=6.2.4,<7",
        "pytest-asyncio>=0.10.0,<0.11",
        "pytest-cov==2.5.1",
        "pytest-timeout>=2.0.0,<3",
        "pytest-watch>=4.1.0,<5",
        "pytest-xdist>=3.0",
        "importlib-metadata<5.0;python_version<'3.8'",
    ],
    "lint": [
        "flake8==6.0.0",  # flake8 claims semver but adds new warnings at minor releases, leave it pinned.
        "flake8-bugbear==23.3.23",  # flake8-bugbear does not follow semver, leave it pinned.
        "isort>=5.10.1",
        "mypy==1.4.0",  # mypy does not follow semver, leave it pinned.
        "pydocstyle>=6.0.0",
        "black>=23",
        "types-setuptools",
        "importlib-metadata<5.0;python_version<'3.8'",
    ],
    "benchmark": [
        "termcolor>=1.1.0,<2.0.0",
        "web3>=4.1.0,<5.0.0",
    ],
    "docs": [
        "py-evm>=0.2.0-a.14",
        # We need to have pysha for autodoc to be able to extract API docs
        "Sphinx>=1.5.5,<2",
        "jinja2>=3.0.0,<3.1.0",  # jinja2<3.0 or >=3.1.0 cause doc build failures.
        "sphinx_rtd_theme>=0.1.9",
        "sphinxcontrib-asyncio>=0.2.0,<0.4",
        "towncrier>=21,<22",
    ],
    "dev": [
        "bumpversion>=0.5.3,<1",
        "wheel",
        "setuptools>=36.2.0",
        # Fixing this dependency due to: requests 2.20.1 has requirement
        # idna<2.8,>=2.5, but you'll have idna 2.8 which is incompatible.
        "idna==2.7",
        # idna 2.7 is not supported by requests 2.18
        "requests>=2.20,<3",
        "tox>=4.0.0",
        "twine",
    ],
}


extras_require["dev"] = (
    extras_require["dev"]
    + extras_require["eth"]
    + extras_require["test"]
    + extras_require["lint"]
    + extras_require["docs"]
)

install_requires = extras_require["eth"]

with open("README.md") as readme_file:
    long_description = readme_file.read()

setup(
    name="py-evm",
    # *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
    version="0.8.0-beta.1",
    description="Python implementation of the Ethereum Virtual Machine",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Ethereum Foundation",
    author_email="piper@pipermerriam.com",
    url="https://github.com/ethereum/py-evm",
    include_package_data=True,
    py_modules=["eth"],
    install_requires=install_requires,
    extras_require=extras_require,
    license="MIT",
    zip_safe=False,
    keywords="ethereum blockchain evm",
    packages=find_packages(exclude=["tests", "tests.*"]),
    package_data={"eth": ["py.typed"]},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
