#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup, find_packages


deps = {
    'eth': [
        "cryptography>=2.0.3,<3.0.0",
        "eth-bloom>=1.0.3,<2.0.0",
        "eth-keys>=0.2.1,<1.0.0",
        "eth-typing>=2.0.0,<3.0.0",
        "eth-utils>=1.3.0,<2.0.0",
        "lru-dict>=1.1.6",
        "mypy_extensions>=0.4.1,<1.0.0",
        "py-ecc>=1.4.7,<2.0.0",
        "pyethash>=0.1.27,<1.0.0",
        "rlp>=1.1.0,<2.0.0",
        "trie>=1.3.8,<2.0.0",
    ],
    # The eth-extra sections is for libraries that the evm does not
    # explicitly need to function and hence should not depend on.
    # Installing these libraries may make the evm perform better than
    # using the default fallbacks though.
    'eth-extra': [
        "coincurve>=10.0.0,<11.0.0",
        "eth-hash[pysha3];implementation_name=='cpython'",
        "eth-hash[pycryptodome];implementation_name=='pypy'",
        "plyvel==1.0.5",
    ],
    'test': [
        "hypothesis==3.69.5",
        "pexpect>=4.6, <5",
        # pinned to <3.7 until async fixtures work again
        # https://github.com/pytest-dev/pytest-asyncio/issues/89
        "pytest>=3.6,<3.7",
        "pytest-asyncio==0.9.0",
        "pytest-cov==2.5.1",
        "pytest-watch>=4.1.0,<5",
        "pytest-xdist==1.18.1",
    ],
    'lint': [
        "flake8==3.5.0",
        "mypy==0.641",
    ],
    'benchmark': [
        "termcolor>=1.1.0,<2.0.0",
        "web3>=4.1.0,<5.0.0",
    ],
    'doc': [
        "py-evm>=0.2.0-alpha.14",
        "pytest~=3.2",
        # Sphinx pined to `<1.8.0`: https://github.com/sphinx-doc/sphinx/issues/3494
        "Sphinx>=1.5.5,<1.8.0",
        "sphinx_rtd_theme>=0.1.9",
        "sphinxcontrib-asyncio>=0.2.0",
    ],
    'dev': [
        "bumpversion>=0.5.3,<1",
        "wheel",
        "setuptools>=36.2.0",
        # Fixing this dependency due to: pytest 3.6.4 has requirement pluggy<0.8,>=0.5, but you'll have pluggy 0.8.0 which is incompatible.
        "pluggy==0.7.1",
        # Fixing this dependency due to: requests 2.20.1 has requirement idna<2.8,>=2.5, but you'll have idna 2.8 which is incompatible.
        "idna==2.7",
        # idna 2.7 is not supported by requests 2.18
        "requests>=2.20,<3",
        "tox==2.7.0",
        "twine",
    ],
}


deps['dev'] = (
    deps['dev'] +
    deps['eth'] +
    deps['eth-extra'] +
    deps['test'] +
    deps['doc'] +
    deps['lint']
)


install_requires = deps['eth']

setup(
    name='py-evm',
    # *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
    version='0.2.0-alpha.40',
    description='Python implementation of the Ethereum Virtual Machine',
    long_description_markdown_filename='README.md',
    author='Ethereum Foundation',
    author_email='piper@pipermerriam.com',
    url='https://github.com/ethereum/py-evm',
    include_package_data=True,
    py_modules=['eth'],
    install_requires=install_requires,
    extras_require=deps,
    setup_requires=['setuptools-markdown'],
    license='MIT',
    zip_safe=False,
    keywords='ethereum blockchain evm',
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
)
