#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup, find_packages


deps = {
    'evm': [
        "aiohttp>=2.3.1,<3.0.0",
        "async_lru>=0.1.0,<1.0.0",
        "cryptography>=2.0.3,<3.0.0",
        "cytoolz>=0.9.0,<1.0.0",
        "eth-bloom>=1.0.0,<2.0.0",
        "eth-utils>=1.0.1,<2.0.0",
        "pyethash>=0.1.27,<1.0.0",
        "py-ecc>=1.4.2,<2.0.0",
        "rlp>=1.0.1,<2.0.0",
        "eth-keys>=0.2.0b3,<1.0.0",
        "trie>=1.3.5,<2.0.0",
        "lru-dict>=1.1.6",
    ],
    # The evm-extra sections is for libraries that the evm does not
    # explicitly need to function and hence should not depend on.
    # Installing these libraries may make the evm perform better than
    # using the default fallbacks though.
    'evm-extra': [
        "coincurve>=7.0.0,<8.0.0",
        "plyvel==1.0.4",
        "eth-hash[pycryptodome]",
    ],
    'p2p': [
        "aiohttp>=2.3.1,<3.0.0",
        "async_lru>=0.1.0,<1.0.0",
        "pysha3>=1.0.0,<2.0.0",
        "upnpclient>=0.0.8,<1",
    ],
    'trinity': [
        "ipython>=6.2.1,<7.0.0",
        "plyvel==1.0.4",
        "coincurve>=7.0.0,<8.0.0",
        "web3>=4.1.0,<5.0.0",
        # required for rlp>=1.0.0
        "eth-account>=0.2.1,<1",
    ],
    'test': [
        "hypothesis==3.44.26",
        "pytest~=3.2",
        "pytest-asyncio==0.8.0",
        "pytest-cov==2.5.1",
        "pytest-logging>=2015.11.4",
        "pytest-xdist==1.18.1",
        "pytest-watch>=4.1.0,<5",
    ],
    'lint': [
        "flake8==3.5.0",
        "mypy<0.600",
    ],
    'doc': [
        "py-evm>=0.2.0-alpha.14",
        "pytest~=3.2",
        "Sphinx>=1.5.5,<2.0.0",
        "sphinx_rtd_theme>=0.1.9",
        "sphinxcontrib-asyncio>=0.2.0",
    ],
    'dev': [
        "bumpversion>=0.5.3,<1",
        "wheel",
        "tox==2.7.0",
    ],
}

deps['dev'] = (
    deps['dev'] +
    deps['evm'] +
    deps['evm-extra'] +
    deps['p2p'] +
    deps['trinity'] +
    deps['test'] +
    deps['doc'] +
    deps['lint']
)

# As long as evm, p2p and trinity are managed together in the py-evm
# package, someone running a `pip install py-evm` should expect all
# dependencies for evm, p2p and trinity to get installed.
install_requires = deps['evm'] + deps['p2p'] + deps['trinity']

setup(
    name='py-evm',
    # *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
    version='0.2.0-alpha.17',
    description='Python implementation of the Ethereum Virtual Machine',
    long_description_markdown_filename='README.md',
    author='Piper Merriam',
    author_email='piper@pipermerriam.com',
    url='https://github.com/ethereum/py-evm',
    include_package_data=True,
    py_modules=['evm', 'trinity', 'p2p'],
    install_requires=install_requires,
    extras_require=deps,
    setup_requires=['setuptools-markdown'],
    license='MIT',
    zip_safe=False,
    keywords='ethereum blockchain evm',
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.5',
    ],
    # trinity
    entry_points={
        'console_scripts': ['trinity=trinity:main'],
    },
)
