#!/usr/bin/env python
from setuptools import (
    find_packages,
    setup,
)

extras_require = {
    "benchmark": [
        "termcolor>=1.1.0",
        "web3>=6.0.0",
    ],
    "dev": [
        "build>=0.9.0",
        "bumpversion>=0.5.3",
        "ipython",
        "pre-commit>=3.4.0",
        "tox>=4.0.0",
        "twine",
        "wheel",
    ],
    "docs": [
        "py-evm>=0.8.0b1",
        "sphinx>=6.0.0",
        "sphinx_rtd_theme>=1.0.0",
        "sphinxcontrib-asyncio>=0.2.0",
        "towncrier>=21,<22",
    ],
    "eth": [
        "cached-property>=1.5.1",
        "eth-bloom>=1.0.3",
        "eth-keys>=0.4.0",
        "eth-typing>=3.3.0",
        "eth-utils>=2.0.0",
        "lru-dict>=1.1.6",
        "py-ecc>=1.4.7",
        "rlp>=3.0.0",
        "trie>=2.0.0",
    ],
    # The eth-extra sections is for libraries that the evm does not
    # explicitly need to function and hence should not depend on.
    # Installing these libraries may make the evm perform better than
    # using the default fallbacks though.
    "eth-extra": [
        "blake2b-py>=0.2.0",
        "coincurve>=18.0.0",
    ],
    "test": [
        "factory-boy>=3.0.0",
        "hypothesis>=5,<6",
        "pytest>=7.0.0",
        "pytest-asyncio>=0.20.0",
        "pytest-cov>=4.0.0",
        "pytest-timeout>=2.0.0",
        "pytest-xdist>=3.0",
    ],
}


extras_require["dev"] = (
    extras_require["dev"]
    + extras_require["docs"]
    + extras_require["eth"]
    + extras_require["test"]
)

install_requires = extras_require["eth"]

with open("README.md") as readme_file:
    long_description = readme_file.read()

setup(
    name="py-evm",
    # *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
    version="0.9.0-beta.1",
    description="Python implementation of the Ethereum Virtual Machine",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Ethereum Foundation",
    author_email="snakecharmers@ethereum.org",
    url="https://github.com/ethereum/py-evm",
    include_package_data=True,
    py_modules=["eth"],
    install_requires=install_requires,
    python_requires=">=3.8, <4",
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
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
